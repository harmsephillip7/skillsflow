"""
Logistics app models
Cohorts, Venues, Scheduling, Attendance, and Logbook tracking
"""
from django.db import models
from django.utils import timezone
from core.models import AuditedModel, User
from tenants.models import TenantAwareModel, Campus


# Consistent phase type colors for UI (Kanban and dashboards)
PHASE_TYPE_COLORS = {
    'INDUCTION': 'indigo',
    'INSTITUTIONAL': 'blue',
    'WORKPLACE_STINT': 'green',
    'INTEGRATION': 'purple',
    'TRADE_TEST': 'amber',
    'ASSESSMENT': 'rose',
}


class Cohort(TenantAwareModel):
    """
    Training cohort/group
    E.g., "PM NQF5 - Jan 2025 Group A"
    """
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('OPEN', 'Open for Enrollment'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    
    qualification = models.ForeignKey(
        'academics.Qualification', 
        on_delete=models.PROTECT, 
        related_name='cohorts'
    )
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Capacity
    max_capacity = models.PositiveIntegerField()
    current_count = models.PositiveIntegerField(default=0)  # Denormalized for performance
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    
    # Primary facilitator
    facilitator = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='facilitated_cohorts'
    )
    
    # Notes
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def available_slots(self):
        return max(0, self.max_capacity - self.current_count)
    
    def update_count(self):
        """Update current count from enrollments"""
        self.current_count = self.enrollments.filter(
            status__in=['ENROLLED', 'ACTIVE']
        ).count()
        self.save(update_fields=['current_count'])


class Venue(AuditedModel):
    """
    Physical or virtual venue for training sessions
    """
    VENUE_TYPES = [
        ('CLASSROOM', 'Classroom'),
        ('LAB', 'Computer Lab'),
        ('WORKSHOP', 'Workshop'),
        ('BOARDROOM', 'Boardroom'),
        ('VIRTUAL', 'Virtual/Online'),
        ('WORKPLACE', 'Workplace'),
        ('EXTERNAL', 'External Venue'),
    ]
    
    campus = models.ForeignKey(
        Campus, 
        on_delete=models.CASCADE, 
        related_name='venues'
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    venue_type = models.CharField(max_length=20, choices=VENUE_TYPES)
    
    # Capacity
    capacity = models.PositiveIntegerField()
    
    # Facilities
    equipment = models.JSONField(default=list, blank=True)  # ["Projector", "Whiteboard", etc.]
    
    # Virtual venues
    meeting_url = models.URLField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['campus', 'name']
        unique_together = ['campus', 'code']
    
    def __str__(self):
        return f"{self.campus.code} - {self.name}"


class ScheduleSession(AuditedModel):
    """
    Scheduled training session
    """
    SESSION_TYPES = [
        ('LECTURE', 'Lecture'),
        ('PRACTICAL', 'Practical'),
        ('ASSESSMENT', 'Assessment'),
        ('REVISION', 'Revision'),
        ('WORKSHOP', 'Workshop'),
        ('ORIENTATION', 'Orientation'),
    ]
    
    cohort = models.ForeignKey(
        Cohort, 
        on_delete=models.CASCADE, 
        related_name='sessions'
    )
    module = models.ForeignKey(
        'academics.Module', 
        on_delete=models.PROTECT, 
        related_name='sessions'
    )
    venue = models.ForeignKey(
        Venue, 
        on_delete=models.PROTECT, 
        related_name='sessions'
    )
    facilitator = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='facilitated_sessions'
    )
    
    # Timing
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # Type
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='LECTURE')
    topic = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    
    # Cancellation
    is_cancelled = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='cancelled_sessions'
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # QR Code for attendance
    qr_code = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['date', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['venue', 'date', 'start_time'],
                name='unique_venue_booking'
            ),
            models.UniqueConstraint(
                fields=['facilitator', 'date', 'start_time'],
                name='unique_facilitator_booking'
            ),
        ]
    
    def __str__(self):
        return f"{self.cohort.code} - {self.module.code} - {self.date}"
    
    def generate_qr_code(self):
        """Generate unique QR code for this session"""
        import hashlib
        data = f"{self.id}-{self.date}-{self.start_time}"
        self.qr_code = hashlib.sha256(data.encode()).hexdigest()[:20]
        self.save(update_fields=['qr_code'])
        return self.qr_code


class Attendance(AuditedModel):
    """
    Attendance record for a session
    Supports QR code and manual capture
    """
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('EXCUSED', 'Excused'),
        ('LEFT_EARLY', 'Left Early'),
    ]
    
    CHECK_IN_METHODS = [
        ('QR', 'QR Code Scan'),
        ('MANUAL', 'Manual Register'),
        ('BIOMETRIC', 'Biometric'),
        ('AUTO', 'Auto-marked'),
    ]
    
    session = models.ForeignKey(
        ScheduleSession, 
        on_delete=models.CASCADE, 
        related_name='attendance_records'
    )
    enrollment = models.ForeignKey(
        'academics.Enrollment', 
        on_delete=models.CASCADE, 
        related_name='attendance_records'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABSENT')
    
    # Check-in details
    check_in_method = models.CharField(max_length=20, choices=CHECK_IN_METHODS, default='MANUAL')
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    
    # Recording
    recorded_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='recorded_attendance'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['session', 'enrollment']
        ordering = ['session', 'enrollment']
        verbose_name_plural = 'Attendance Records'
    
    def __str__(self):
        return f"{self.enrollment} - {self.session.date} - {self.status}"


class LogbookTracker(AuditedModel):
    """
    Tracks physical logbook movement
    """
    STATUS_CHOICES = [
        ('ISSUED', 'Issued to Learner'),
        ('WITH_LEARNER', 'With Learner'),
        ('WITH_ADMIN', 'Returned to Admin'),
        ('WITH_ASSESSOR', 'With Assessor'),
        ('MODERATION', 'In Moderation'),
        ('ARCHIVED', 'Archived'),
        ('LOST', 'Lost/Missing'),
    ]
    
    enrollment = models.ForeignKey(
        'academics.Enrollment', 
        on_delete=models.CASCADE, 
        related_name='logbooks'
    )
    logbook_number = models.CharField(max_length=50, unique=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ISSUED')
    current_holder = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='held_logbooks'
    )
    
    # Dates
    issued_date = models.DateField()
    last_status_change = models.DateTimeField(auto_now=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-issued_date']
        verbose_name = 'Logbook Tracker'
        verbose_name_plural = 'Logbook Trackers'
    
    def __str__(self):
        return f"{self.logbook_number} - {self.enrollment}"


class LogbookMovement(AuditedModel):
    """
    Tracks logbook handover history
    """
    logbook = models.ForeignKey(
        LogbookTracker, 
        on_delete=models.CASCADE, 
        related_name='movements'
    )
    
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    from_holder = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='logbook_handovers_from'
    )
    to_holder = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='logbook_handovers_to'
    )
    
    moved_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        related_name='logbook_movements'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Logbook Movement'
        verbose_name_plural = 'Logbook Movements'
    
    def __str__(self):
        return f"{self.logbook} - {self.from_status} → {self.to_status}"


# ============================================================================
# Cohort Implementation Plan Models
# ============================================================================

class CohortImplementationPlan(AuditedModel):
    """
    Implementation copy of an ImplementationPlan for a specific cohort.
    Allows on-the-fly adjustments while maintaining reference to the master template.
    """
    DELIVERY_MODE_CHOICES = [
        ('FULL_TIME', 'Full-Time (Contact)'),
        ('PART_TIME', 'Part-Time'),
        ('BLENDED', 'Blended Learning'),
        ('DISTANCE', 'Distance Learning'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    cohort = models.OneToOneField(
        Cohort,
        on_delete=models.CASCADE,
        related_name='implementation_plan'
    )
    
    # Reference to original template
    source_template = models.ForeignKey(
        'academics.ImplementationPlan',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cohort_implementations',
        help_text="Original template this was copied from"
    )
    
    # Copied configuration (can be modified)
    name = models.CharField(max_length=200)
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_MODE_CHOICES)
    total_weeks = models.PositiveIntegerField()
    contact_days_per_week = models.PositiveIntegerField(default=5)
    hours_per_day = models.PositiveIntegerField(default=6)
    classroom_hours_per_day = models.PositiveIntegerField(default=2)
    practical_hours_per_day = models.PositiveIntegerField(default=4)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Modification tracking
    modification_log = models.JSONField(
        default=list,
        help_text="Log of modifications made to the plan"
    )
    # Structure: [{"date": "...", "user": "...", "change": "...", "reason": "..."}]
    
    class Meta:
        verbose_name = 'Cohort Implementation Plan'
        verbose_name_plural = 'Cohort Implementation Plans'
    
    def __str__(self):
        return f"{self.cohort.code} - {self.name}"
    
    def log_modification(self, user, change_description, reason=""):
        """Log a modification to the plan"""
        from django.utils import timezone
        entry = {
            'date': timezone.now().isoformat(),
            'user': user.get_full_name() if user else 'System',
            'user_id': user.id if user else None,
            'change': change_description,
            'reason': reason
        }
        if not self.modification_log:
            self.modification_log = []
        self.modification_log.append(entry)
        self.save(update_fields=['modification_log'])
    
    @property
    def has_modifications(self):
        """Check if plan has been modified from template"""
        return len(self.modification_log) > 0
    
    @property
    def variance_from_template(self):
        """Calculate variance from original template"""
        if not self.source_template:
            return None
        
        variance = {
            'total_weeks_diff': self.total_weeks - self.source_template.total_weeks,
            'modified_phases': 0,
            'modified_slots': 0,
        }
        
        for phase in self.phases.all():
            if phase.source_phase and (
                phase.duration_weeks != phase.source_phase.duration_weeks or
                phase.actual_start != phase.planned_start or
                phase.actual_end != phase.planned_end
            ):
                variance['modified_phases'] += 1
        
        return variance
    
    def generate_schedule_sessions(self, start_date=None):
        """
        Generate ScheduleSession records from the implementation plan phases and module slots.
        This populates the actual calendar for facilitators.
        
        If the cohort is linked to a NOT (via NOTIntake), it will use allocated resources
        (facilitator, venue) from the NOT's resource requirements.
        """
        from datetime import timedelta
        from academics.models import LessonPlanTemplate
        
        if not start_date:
            start_date = self.cohort.start_date
        
        current_date = start_date
        sessions_created = []
        
        # Try to get allocated resources from NOT
        facilitator = self.cohort.facilitator
        venue_id = 1  # Default fallback
        
        # Check if cohort is linked to a NOT via NOTIntake
        if hasattr(self.cohort, 'not_intakes') and self.cohort.not_intakes.exists():
            not_intake = self.cohort.not_intakes.first()
            if not_intake and not_intake.training_notification:
                not_obj = not_intake.training_notification
                
                # Get allocated facilitator from NOT resources
                facilitator_resource = not_obj.resource_requirements.filter(
                    resource_type='FACILITATOR',
                    status='ALLOCATED',
                    assigned_user__isnull=False
                ).first()
                if facilitator_resource and facilitator_resource.assigned_user:
                    facilitator = facilitator_resource.assigned_user
                
                # Get allocated venue from NOT resources
                venue_resource = not_obj.resource_requirements.filter(
                    resource_type='VENUE',
                    status='ALLOCATED'
                ).first()
                if venue_resource:
                    # Check if there's an allocation period with a venue
                    allocation = venue_resource.allocation_periods.filter(
                        venue__isnull=False,
                        is_archived=False
                    ).first()
                    if allocation and allocation.venue_id:
                        venue_id = allocation.venue_id
        
        for phase in self.phases.filter(phase_type='INSTITUTIONAL').order_by('sequence'):
            # Update phase dates
            phase.actual_start = current_date
            
            for slot in phase.module_slots.order_by('sequence'):
                for day_num in range(slot.total_days):
                    # Skip weekends
                    while current_date.weekday() >= 5:
                        current_date += timedelta(days=1)
                    
                    # Create morning classroom session (2 hours)
                    classroom_session = ScheduleSession.objects.create(
                        cohort=self.cohort,
                        module=slot.module,
                        venue_id=venue_id,
                        facilitator=facilitator,
                        date=current_date,
                        start_time='08:00',
                        end_time='10:00',
                        session_type='LECTURE',
                        topic=f"{slot.module.code} - Day {day_num + 1} Theory"
                    )
                    sessions_created.append(classroom_session)
                    
                    # Create afternoon practical session (4 hours)
                    practical_session = ScheduleSession.objects.create(
                        cohort=self.cohort,
                        module=slot.module,
                        venue_id=venue_id,
                        facilitator=facilitator,
                        date=current_date,
                        start_time='10:30',
                        end_time='14:30',
                        session_type='PRACTICAL',
                        topic=f"{slot.module.code} - Day {day_num + 1} Practical"
                    )
                    sessions_created.append(practical_session)
                    
                    current_date += timedelta(days=1)
            
            phase.actual_end = current_date - timedelta(days=1)
            phase.save()
            
            # For workplace stints, just advance the date
            if phase.phase_type == 'WORKPLACE_STINT':
                current_date += timedelta(weeks=phase.duration_weeks)
        
        return sessions_created


class CohortImplementationPhase(AuditedModel):
    """
    Implementation phase for a cohort's implementation plan.
    Tracks planned vs actual dates for schedule variance monitoring.
    """
    PHASE_TYPE_CHOICES = [
        ('INDUCTION', 'Induction'),
        ('INSTITUTIONAL', 'Institutional Training'),
        ('WORKPLACE_STINT', 'Workplace Stint'),
        ('INTEGRATION', 'Integration'),
        ('TRADE_TEST', 'Trade Test Preparation'),
        ('ASSESSMENT', 'Assessment'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('DELAYED', 'Delayed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    cohort_implementation_plan = models.ForeignKey(
        CohortImplementationPlan,
        on_delete=models.CASCADE,
        related_name='phases'
    )
    
    # Reference to source template phase
    source_phase = models.ForeignKey(
        'academics.ImplementationPhase',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cohort_implementations'
    )
    
    # Phase details (copied from template, can be modified)
    phase_type = models.CharField(max_length=20, choices=PHASE_TYPE_CHOICES)
    name = models.CharField(max_length=100)
    sequence = models.PositiveIntegerField()
    duration_weeks = models.PositiveIntegerField()
    year_level = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    
    # Planned dates (calculated from template)
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    
    # Actual dates (can be adjusted)
    actual_start = models.DateField(null=True, blank=True)
    actual_end = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Adjustment tracking
    adjustment_reason = models.TextField(blank=True, help_text="Reason for schedule adjustment")
    adjusted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='adjusted_phases'
    )
    adjusted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['cohort_implementation_plan', 'sequence']
        verbose_name = 'Cohort Implementation Phase'
        verbose_name_plural = 'Cohort Implementation Phases'
    
    def __str__(self):
        return f"{self.cohort_implementation_plan.cohort.code} - {self.name}"
    
    @property
    def is_delayed(self):
        """Check if phase is behind schedule"""
        if self.actual_start and self.planned_start:
            return self.actual_start > self.planned_start
        return False
    
    @property
    def days_variance(self):
        """Calculate days variance from plan"""
        if self.actual_start and self.planned_start:
            return (self.actual_start - self.planned_start).days
        return 0
    
    def adjust_dates(self, new_start, new_end, reason, user):
        """Adjust phase dates with logging"""
        from django.utils import timezone
        
        old_start = self.actual_start
        old_end = self.actual_end
        
        self.actual_start = new_start
        self.actual_end = new_end
        self.adjustment_reason = reason
        self.adjusted_by = user
        self.adjusted_at = timezone.now()
        self.save()
        
        # Log the modification in the parent implementation plan
        self.cohort_implementation_plan.log_modification(
            user,
            f"Phase '{self.name}' dates adjusted: {old_start} - {old_end} → {new_start} - {new_end}",
            reason
        )
    
    @property
    def color(self):
        """Get consistent color for phase type"""
        return PHASE_TYPE_COLORS.get(self.phase_type, 'gray')
    
    @property
    def days_until_planned_end(self):
        """Days remaining until planned end date"""
        if not self.planned_end:
            return None
        today = timezone.now().date()
        return (self.planned_end - today).days
    
    @property
    def is_at_risk(self):
        """Check if phase is at risk (within 7 days of planned end and not completed)"""
        if self.status == 'COMPLETED':
            return False
        days_remaining = self.days_until_planned_end
        if days_remaining is None:
            return False
        return days_remaining <= 7 and days_remaining >= 0
    
    @property
    def is_overdue(self):
        """Check if phase is past planned end date and not completed"""
        if self.status == 'COMPLETED':
            return False
        days_remaining = self.days_until_planned_end
        if days_remaining is None:
            return False
        return days_remaining < 0
    
    def get_module_progress(self):
        """Calculate completion percentage based on module slots"""
        total_slots = self.module_slots.count()
        if total_slots == 0:
            return 100 if self.status == 'COMPLETED' else 0
        
        completed_slots = self.module_slots.filter(status='COMPLETED').count()
        return int((completed_slots / total_slots) * 100)
    
    def update_dates_from_progress(self, save=True):
        """Update actual dates based on module slot progress"""
        module_slots = self.module_slots.all()
        if not module_slots.exists():
            return
        
        # Set actual_start when first module slot starts
        started_slots = module_slots.exclude(actual_start_date__isnull=True)
        if started_slots.exists() and not self.actual_start:
            self.actual_start = started_slots.order_by('actual_start_date').first().actual_start_date
            if self.status == 'PENDING':
                self.status = 'IN_PROGRESS'
        
        # Set actual_end when all module slots complete
        all_completed = all(slot.status == 'COMPLETED' for slot in module_slots)
        if all_completed and not self.actual_end:
            completed_slots = module_slots.exclude(actual_end_date__isnull=True)
            if completed_slots.exists():
                self.actual_end = completed_slots.order_by('-actual_end_date').first().actual_end_date
            else:
                self.actual_end = timezone.now().date()
            self.status = 'COMPLETED'
        
        if save:
            self.save()


class CohortImplementationModuleSlot(AuditedModel):
    """
    Implementation module slot for a cohort phase.
    Tracks actual delivery vs planned.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('SKIPPED', 'Skipped'),
    ]
    
    cohort_implementation_phase = models.ForeignKey(
        CohortImplementationPhase,
        on_delete=models.CASCADE,
        related_name='module_slots'
    )
    
    # Reference to source template slot
    source_slot = models.ForeignKey(
        'academics.ImplementationModuleSlot',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cohort_implementations'
    )
    
    # Module details (copied from template)
    module = models.ForeignKey(
        'academics.Module',
        on_delete=models.PROTECT,
        related_name='cohort_slots'
    )
    sequence = models.PositiveIntegerField()
    classroom_sessions = models.PositiveIntegerField(default=1)
    practical_sessions = models.PositiveIntegerField(default=1)
    total_days = models.PositiveIntegerField()
    
    # Actual delivery tracking
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    actual_days_used = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    completion_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['cohort_implementation_phase', 'sequence']
        verbose_name = 'Cohort Implementation Module Slot'
        verbose_name_plural = 'Cohort Implementation Module Slots'
    
    def __str__(self):
        return f"{self.cohort_implementation_phase.cohort_implementation_plan.cohort.code} - {self.module.code}"
    
    @property
    def variance_days(self):
        """Days variance from planned"""
        if self.actual_days_used and self.total_days:
            return self.actual_days_used - self.total_days
        return 0
