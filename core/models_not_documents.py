"""
NOT Project Learner Document Tracking Models

This module provides document management for learners within training projects,
including SETA registrations, QCTO confirmations, and compliance tracking.
"""

from django.db import models
from django.utils import timezone
from datetime import date, timedelta

from .models import AuditedModel, User, TrainingNotification


# =============================================================================
# NOT PROJECT LEARNER DOCUMENT TRACKING
# =============================================================================

class NOTLearnerDocumentType(models.Model):
    """
    Configurable document types required for learners in projects.
    Allows different document requirements per project type, funder, or SETA.
    """
    
    CATEGORY_CHOICES = [
        ('REGISTRATION', 'Registration Documents'),
        ('CONFIRMATION', 'SETA/QCTO Confirmations'),
        ('AGREEMENT', 'Agreements & Contracts'),
        ('COMPLIANCE', 'Compliance Documents'),
        ('PROGRESS', 'Progress Reports'),
        ('CERTIFICATION', 'Certification Documents'),
        ('OTHER', 'Other'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    description = models.TextField(blank=True, help_text="Description of this document type")
    
    # Requirements configuration
    is_required = models.BooleanField(default=False, help_text="Is this document mandatory?")
    required_for_project_types = models.JSONField(
        default=list, blank=True,
        help_text="List of project types this is required for (empty = all)"
    )
    required_for_funders = models.JSONField(
        default=list, blank=True,
        help_text="List of funder types this is required for (empty = all)"
    )
    
    # Expiry configuration
    has_expiry = models.BooleanField(default=False, help_text="Does this document type expire?")
    default_validity_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Default validity period in days from issue date"
    )
    expiry_warning_days = models.PositiveIntegerField(
        default=30,
        help_text="Days before expiry to show warning/create task"
    )
    
    # Validation
    accepted_file_types = models.CharField(
        max_length=200, blank=True, default='.pdf,.doc,.docx,.jpg,.jpeg,.png',
        help_text="Comma-separated list of accepted file extensions"
    )
    max_file_size_mb = models.PositiveIntegerField(default=10)
    
    # Display order
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'order', 'name']
        verbose_name = 'Learner Document Type'
        verbose_name_plural = 'Learner Document Types'
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
    
    def is_required_for_project(self, project):
        """Check if this document type is required for a specific project."""
        if not self.is_required:
            return False
        
        # Check project type requirement
        if self.required_for_project_types:
            if project.project_type not in self.required_for_project_types:
                return False
        
        # Check funder requirement
        if self.required_for_funders:
            if project.funder not in self.required_for_funders:
                return False
        
        return True
    
    def archive(self):
        """Archive this document type instead of deleting."""
        self.is_active = False
        self.archived_at = timezone.now()
        self.save(update_fields=['is_active', 'archived_at'])
    
    def restore(self):
        """Restore an archived document type."""
        self.is_active = True
        self.archived_at = None
        self.save(update_fields=['is_active', 'archived_at'])
    
    @classmethod
    def get_required_for_project(cls, project):
        """Get all document types required for a specific project."""
        all_types = cls.objects.filter(is_active=True, is_required=True)
        return [dt for dt in all_types if dt.is_required_for_project(project)]
    
    @classmethod
    def get_all_for_project(cls, project):
        """Get all active document types applicable to a project."""
        all_types = cls.objects.filter(is_active=True)
        result = []
        for dt in all_types:
            # Check if applicable to this project type
            if dt.required_for_project_types and project.project_type not in dt.required_for_project_types:
                continue
            if dt.required_for_funders and project.funder not in dt.required_for_funders:
                continue
            result.append(dt)
        return result


class NOTLearnerDocument(AuditedModel):
    """
    Documents for individual learners within a project.
    Tracks SETA registrations, QCTO confirmations, agreements, etc.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Upload'),
        ('UPLOADED', 'Uploaded - Awaiting Review'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='learner_documents'
    )
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='not_documents'
    )
    document_type = models.ForeignKey(
        NOTLearnerDocumentType,
        on_delete=models.PROTECT,
        related_name='documents'
    )
    
    # File storage
    file = models.FileField(
        upload_to='not/learner_documents/%Y/%m/',
        null=True, blank=True
    )
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Verification
    verified_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_not_learner_docs'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Document details
    reference_number = models.CharField(max_length=100, blank=True, help_text="Document reference number if applicable")
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Expiry notification tracking
    expiry_warning_sent = models.BooleanField(default=False)
    expiry_warning_sent_at = models.DateTimeField(null=True, blank=True)
    expiry_task_created = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['training_notification', 'learner', 'document_type']
        unique_together = ['training_notification', 'learner', 'document_type']
        verbose_name = 'Learner Document'
        verbose_name_plural = 'Learner Documents'
    
    def __str__(self):
        return f"{self.learner} - {self.document_type.name} ({self.training_notification.reference_number})"
    
    def save(self, *args, **kwargs):
        if self.file:
            self.original_filename = self.file.name.split('/')[-1]
            try:
                self.file_size = self.file.size
            except:
                pass
            if self.status == 'PENDING':
                self.status = 'UPLOADED'
        
        # Auto-calculate expiry date if issue date set and document type has default validity
        if self.issue_date and not self.expiry_date and self.document_type.has_expiry:
            if self.document_type.default_validity_days:
                self.expiry_date = self.issue_date + timedelta(days=self.document_type.default_validity_days)
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if document has expired."""
        if self.expiry_date:
            return self.expiry_date < date.today()
        return False
    
    @property
    def is_expiring_soon(self):
        """Check if document is expiring within warning period."""
        if self.expiry_date and self.document_type.expiry_warning_days:
            warning_date = date.today() + timedelta(days=self.document_type.expiry_warning_days)
            return self.expiry_date <= warning_date and not self.is_expired
        return False
    
    @property
    def days_until_expiry(self):
        """Days until document expires (negative if expired)."""
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None
    
    def verify(self, user, notes=''):
        """Mark document as verified."""
        self.status = 'VERIFIED'
        self.verified_by = user
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.save()
    
    def reject(self, user, reason):
        """Reject document with reason."""
        self.status = 'REJECTED'
        self.verified_by = user
        self.verified_at = timezone.now()
        self.rejection_reason = reason
        self.save()
    
    def mark_expired(self):
        """Mark document as expired."""
        self.status = 'EXPIRED'
        self.save(update_fields=['status'])


class NOTProjectDocument(AuditedModel):
    """
    Project-level documents (not learner-specific).
    For bulk registration confirmations, project contracts, funder agreements, etc.
    """
    
    DOCUMENT_TYPE_CHOICES = [
        ('CONTRACT', 'Project Contract'),
        ('BULK_REGISTRATION', 'Bulk Registration Confirmation'),
        ('SETA_APPROVAL', 'SETA Approval Letter'),
        ('QCTO_APPROVAL', 'QCTO Approval'),
        ('FUNDING_AGREEMENT', 'Funding Agreement'),
        ('MOU', 'Memorandum of Understanding'),
        ('SLA', 'Service Level Agreement'),
        ('LEARNER_LIST', 'Approved Learner List'),
        ('PROGRESS_REPORT', 'Progress Report'),
        ('AUDIT_REPORT', 'Audit/Verification Report'),
        ('CERTIFICATE_BATCH', 'Batch Certificate List'),
        ('ATTENDANCE', 'Attendance Register'),
        ('FINANCIAL', 'Financial Document'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_REVIEW', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('SUPERSEDED', 'Superseded'),
    ]
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='project_documents'
    )
    
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='not/project_documents/%Y/%m/')
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Document details
    reference_number = models.CharField(max_length=100, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Review
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_not_project_docs'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Version control
    version = models.PositiveIntegerField(default=1)
    supersedes = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='superseded_by'
    )
    
    class Meta:
        ordering = ['training_notification', 'document_type', '-version']
        verbose_name = 'Project Document'
        verbose_name_plural = 'Project Documents'
    
    def __str__(self):
        return f"{self.training_notification.reference_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        if self.file:
            self.original_filename = self.file.name.split('/')[-1]
            try:
                self.file_size = self.file.size
            except:
                pass
        super().save(*args, **kwargs)
    
    def approve(self, user, notes=''):
        """Approve the document."""
        self.status = 'APPROVED'
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
    
    def reject(self, user, notes):
        """Reject the document."""
        self.status = 'REJECTED'
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
    
    def create_new_version(self, file, user):
        """Create a new version of this document."""
        # Mark current as superseded
        self.status = 'SUPERSEDED'
        self.save()
        
        # Create new version
        new_doc = NOTProjectDocument.objects.create(
            training_notification=self.training_notification,
            document_type=self.document_type,
            title=self.title,
            description=self.description,
            file=file,
            reference_number=self.reference_number,
            version=self.version + 1,
            supersedes=self,
            created_by=user
        )
        return new_doc
    
    @property
    def is_expired(self):
        """Check if document has expired."""
        if self.expiry_date:
            return self.expiry_date < date.today()
        return False
