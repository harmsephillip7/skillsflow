"""
Reporting app models
QCTO/SETA exports, report templates, and document generation
"""
from django.db import models
from core.models import AuditedModel, User
from tenants.models import TenantAwareModel


class ReportTemplate(AuditedModel):
    """
    Report template definitions
    """
    REPORT_TYPES = [
        ('QCTO', 'QCTO Export'),
        ('SETA', 'SETA Export'),
        ('NLRD', 'NLRD Upload'),
        ('INTERNAL', 'Internal Report'),
        ('CERTIFICATE', 'Certificate'),
        ('LETTER', 'Letter'),
        ('INVOICE', 'Invoice'),
        ('STATEMENT', 'Statement'),
    ]
    
    OUTPUT_FORMATS = [
        ('PDF', 'PDF'),
        ('EXCEL', 'Excel'),
        ('CSV', 'CSV'),
        ('WORD', 'Word'),
        ('JSON', 'JSON'),
        ('XML', 'XML'),
    ]
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    output_format = models.CharField(max_length=10, choices=OUTPUT_FORMATS, default='PDF')
    
    # Template file (for Word/HTML templates)
    template_file = models.FileField(
        upload_to='report_templates/',
        blank=True
    )
    
    # Template content (for embedded templates)
    template_content = models.TextField(blank=True)
    
    # Configuration
    config = models.JSONField(default=dict, blank=True)
    
    # Permissions
    requires_permission = models.CharField(max_length=100, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['report_type', 'name']
        verbose_name = 'Report Template'
        verbose_name_plural = 'Report Templates'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class SETAExportTemplate(AuditedModel):
    """
    SETA-specific export templates with field mappings
    """
    name = models.CharField(max_length=100)
    seta = models.ForeignKey(
        'learners.SETA',
        on_delete=models.CASCADE,
        related_name='export_templates'
    )
    
    # Type of export
    export_type = models.CharField(max_length=50)  # e.g., 'learner_data', 'completion', 'attendance'
    
    # Field mappings (internal field -> SETA field)
    field_mappings = models.JSONField(default=dict)
    
    # File format
    file_format = models.CharField(max_length=10, default='CSV')
    delimiter = models.CharField(max_length=5, default=',')
    
    # Headers
    include_headers = models.BooleanField(default=True)
    header_row = models.JSONField(default=list, blank=True)
    
    # Validation rules
    validation_rules = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['seta', 'name']
        verbose_name = 'SETA Export Template'
        verbose_name_plural = 'SETA Export Templates'
    
    def __str__(self):
        return f"{self.seta.code} - {self.name}"


class QCTOExportConfig(models.Model):
    """
    QCTO export configuration
    """
    brand = models.OneToOneField(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='qcto_config'
    )
    
    # Provider details
    provider_code = models.CharField(max_length=20)
    provider_etqa_id = models.CharField(max_length=20)
    
    # Default values
    default_funding_source = models.CharField(max_length=10, blank=True)
    default_sponsor_type = models.CharField(max_length=10, blank=True)
    
    # NLRD configuration
    nlrd_submission_enabled = models.BooleanField(default=False)
    nlrd_api_url = models.URLField(blank=True)
    nlrd_api_key = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'QCTO Export Config'
        verbose_name_plural = 'QCTO Export Configs'
    
    def __str__(self):
        return f"QCTO Config - {self.brand.name}"


class ExportJob(AuditedModel):
    """
    Export job queue
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    template = models.ForeignKey(
        ReportTemplate,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='export_jobs'
    )
    
    # Who requested
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='export_jobs'
    )
    
    # Filter parameters
    parameters = models.JSONField(default=dict)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Progress
    progress_percent = models.PositiveIntegerField(default=0)
    progress_message = models.CharField(max_length=200, blank=True)
    
    # Processing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Result
    output_file = models.FileField(
        upload_to='exports/',
        blank=True
    )
    output_filename = models.CharField(max_length=200, blank=True)
    record_count = models.PositiveIntegerField(default=0)
    
    # Errors
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Export Job'
        verbose_name_plural = 'Export Jobs'
    
    def __str__(self):
        return f"{self.template.name if self.template else 'Ad-hoc'} - {self.status}"


class NLRDSubmission(AuditedModel):
    """
    NLRD (National Learner Records Database) submission tracking
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('VALIDATING', 'Validating'),
        ('VALIDATION_ERRORS', 'Validation Errors'),
        ('READY', 'Ready to Submit'),
        ('SUBMITTED', 'Submitted'),
        ('PROCESSING', 'Processing'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('PARTIAL', 'Partially Accepted'),
    ]
    
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='nlrd_submissions'
    )
    
    # Submission details
    submission_type = models.CharField(max_length=50)  # e.g., '26', '27', '28', '29'
    reference_number = models.CharField(max_length=50, blank=True)
    
    # Date range
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Submission file
    submission_file = models.FileField(
        upload_to='nlrd_submissions/',
        blank=True
    )
    
    # Stats
    total_records = models.PositiveIntegerField(default=0)
    accepted_records = models.PositiveIntegerField(default=0)
    rejected_records = models.PositiveIntegerField(default=0)
    
    # Dates
    submitted_at = models.DateTimeField(null=True, blank=True)
    response_received_at = models.DateTimeField(null=True, blank=True)
    
    # Response
    response_file = models.FileField(
        upload_to='nlrd_responses/',
        blank=True
    )
    response_details = models.JSONField(default=dict, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'NLRD Submission'
        verbose_name_plural = 'NLRD Submissions'
    
    def __str__(self):
        return f"NLRD {self.submission_type} - {self.reference_number}"


class NLRDSubmissionRecord(models.Model):
    """
    Individual records in NLRD submission
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('WARNING', 'Accepted with Warnings'),
    ]
    
    submission = models.ForeignKey(
        NLRDSubmission,
        on_delete=models.CASCADE,
        related_name='records'
    )
    
    # Link to learner
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='nlrd_records'
    )
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='nlrd_records'
    )
    
    # Record data
    record_data = models.JSONField(default=dict)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Response
    validation_errors = models.JSONField(default=list, blank=True)
    response_code = models.CharField(max_length=20, blank=True)
    response_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['submission', 'id']
        verbose_name = 'NLRD Submission Record'
        verbose_name_plural = 'NLRD Submission Records'
    
    def __str__(self):
        return f"{self.submission} - {self.learner}"


class GeneratedDocument(AuditedModel):
    """
    Generated documents (certificates, letters, etc.)
    """
    DOCUMENT_TYPES = [
        ('CERTIFICATE', 'Certificate'),
        ('STATEMENT_RESULTS', 'Statement of Results'),
        ('ATTENDANCE_LETTER', 'Attendance Letter'),
        ('ENROLLMENT_LETTER', 'Enrollment Confirmation'),
        ('COMPLETION_LETTER', 'Completion Letter'),
        ('TRANSCRIPT', 'Transcript'),
        ('INVOICE', 'Invoice'),
        ('STATEMENT', 'Account Statement'),
        ('CUSTOM', 'Custom Document'),
    ]
    
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    template = models.ForeignKey(
        ReportTemplate,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='generated_documents'
    )
    
    # Who is it for
    learner = models.ForeignKey(
        'learners.Learner',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='generated_documents'
    )
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='generated_documents'
    )
    
    # Document
    title = models.CharField(max_length=200)
    document_file = models.FileField(upload_to='generated_documents/')
    file_name = models.CharField(max_length=200)
    
    # Reference number (for certificates)
    reference_number = models.CharField(max_length=50, blank=True)
    
    # Issue details
    issue_date = models.DateField()
    
    # Security
    verification_code = models.CharField(max_length=50, blank=True, unique=True)
    
    # Delivery
    emailed = models.BooleanField(default=False)
    emailed_at = models.DateTimeField(null=True, blank=True)
    emailed_to = models.EmailField(blank=True)
    
    # Printing
    printed = models.BooleanField(default=False)
    printed_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Generated Document'
        verbose_name_plural = 'Generated Documents'
    
    def __str__(self):
        return f"{self.document_type} - {self.title}"


class ScheduledReport(AuditedModel):
    """
    Scheduled report generation
    """
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
    ]
    
    name = models.CharField(max_length=100)
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.CASCADE,
        related_name='scheduled_reports'
    )
    
    # Schedule
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    day_of_week = models.PositiveIntegerField(null=True, blank=True)  # 0-6, Monday = 0
    day_of_month = models.PositiveIntegerField(null=True, blank=True)  # 1-31
    time_of_day = models.TimeField()
    
    # Parameters
    parameters = models.JSONField(default=dict)
    
    # Recipients
    recipients = models.ManyToManyField(
        User,
        related_name='subscribed_reports'
    )
    additional_emails = models.TextField(
        blank=True,
        help_text='Comma-separated list of additional email addresses'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    last_run_status = models.CharField(max_length=50, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Scheduled Report'
        verbose_name_plural = 'Scheduled Reports'
    
    def __str__(self):
        return f"{self.name} - {self.frequency}"


class PowerBIConfig(models.Model):
    """
    Power BI integration configuration
    """
    brand = models.OneToOneField(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='powerbi_config'
    )
    
    # Azure AD App registration
    tenant_id = models.CharField(max_length=50)
    client_id = models.CharField(max_length=50)
    client_secret = models.TextField()  # Encrypted
    
    # Workspace
    workspace_id = models.CharField(max_length=50, blank=True)
    
    # Datasets
    datasets = models.JSONField(default=dict, blank=True)
    
    # Embed config
    embed_enabled = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=False)
    last_sync = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Power BI Config'
        verbose_name_plural = 'Power BI Configs'
    
    def __str__(self):
        return f"Power BI - {self.brand.name}"


class PowerBIDataset(models.Model):
    """
    Power BI dataset tracking
    """
    config = models.ForeignKey(
        PowerBIConfig,
        on_delete=models.CASCADE,
        related_name='tracked_datasets'
    )
    
    name = models.CharField(max_length=100)
    dataset_id = models.CharField(max_length=50)
    
    # Tables
    tables = models.JSONField(default=list)
    
    # Refresh
    last_refresh = models.DateTimeField(null=True, blank=True)
    refresh_schedule = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Power BI Dataset'
        verbose_name_plural = 'Power BI Datasets'
    
    def __str__(self):
        return f"{self.config.brand.name} - {self.name}"


class DashboardWidget(AuditedModel):
    """
    Dashboard widgets for reporting
    """
    WIDGET_TYPES = [
        ('NUMBER', 'Number/KPI'),
        ('CHART_BAR', 'Bar Chart'),
        ('CHART_LINE', 'Line Chart'),
        ('CHART_PIE', 'Pie Chart'),
        ('CHART_DOUGHNUT', 'Doughnut Chart'),
        ('TABLE', 'Data Table'),
        ('MAP', 'Map'),
        ('PROGRESS', 'Progress Bar'),
        ('LIST', 'List'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    
    # Data source
    query_config = models.JSONField(default=dict)
    
    # Display config
    display_config = models.JSONField(default=dict)
    
    # Refresh
    auto_refresh = models.BooleanField(default=False)
    refresh_interval_seconds = models.PositiveIntegerField(default=300)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Dashboard Widget'
        verbose_name_plural = 'Dashboard Widgets'
    
    def __str__(self):
        return self.name


class Dashboard(AuditedModel):
    """
    Custom dashboards
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    brand = models.ForeignKey(
        'tenants.Brand',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='dashboards'
    )
    
    # Owner
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dashboards'
    )
    
    # Sharing
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User,
        blank=True,
        related_name='shared_dashboards'
    )
    
    # Layout
    layout_config = models.JSONField(default=dict)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
    
    def __str__(self):
        return self.name


class DashboardWidgetPlacement(models.Model):
    """
    Widget placement on a dashboard
    """
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='widget_placements'
    )
    widget = models.ForeignKey(
        DashboardWidget,
        on_delete=models.CASCADE,
        related_name='placements'
    )
    
    # Position (grid)
    position_x = models.PositiveIntegerField(default=0)
    position_y = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=4)  # Grid units
    height = models.PositiveIntegerField(default=3)
    
    # Widget-specific config overrides
    config_overrides = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['position_y', 'position_x']
        verbose_name = 'Dashboard Widget Placement'
        verbose_name_plural = 'Dashboard Widget Placements'
    
    def __str__(self):
        return f"{self.dashboard.name} - {self.widget.name}"
