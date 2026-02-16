"""
NOT Project Learner Progress Service

Provides comprehensive learner progress tracking within training projects,
including enrollment status, module progress, assessments, and document compliance.
"""

from django.db.models import Count, Q, F, Prefetch
from django.utils import timezone
from datetime import date, timedelta
from collections import defaultdict

from academics.models import Enrollment, LearnerModuleProgress
from assessments.models import AssessmentResult
from core.models import TrainingNotification, NOTIntake
from core.tasks import Task


class LearnerProgressService:
    """
    Service class for aggregating and analyzing learner progress within NOT projects.
    """
    
    def __init__(self, training_notification):
        self.training_notification = training_notification
    
    def get_project_learners(self, include_progress=True):
        """
        Get all learners linked to this project via NOTIntake → Cohort → Enrollment.
        
        Returns:
            QuerySet of Enrollment objects with related learner and progress data.
        """
        from learners.models import Learner
        
        # Get all intakes for this NOT
        intakes = NOTIntake.objects.filter(training_notification=self.training_notification)
        
        # Get all cohorts from those intakes
        cohort_ids = intakes.values_list('cohort_id', flat=True)
        
        # Get all enrollments for those cohorts
        enrollments = Enrollment.objects.filter(
            cohort_id__in=cohort_ids
        ).select_related(
            'learner', 
            'cohort', 
            'cohort__qualification',
            'learner__user'
        )
        
        if include_progress:
            enrollments = enrollments.prefetch_related(
                Prefetch(
                    'learnermoduleprogress_set',
                    queryset=LearnerModuleProgress.objects.select_related('module')
                ),
                Prefetch(
                    'assessment_results',
                    queryset=AssessmentResult.objects.select_related('activity', 'activity__module')
                )
            )
        
        return enrollments
    
    def get_learner_count(self):
        """Get total number of learners in the project."""
        return self.get_project_learners(include_progress=False).count()
    
    def get_progress_summary(self):
        """
        Get overall progress summary for the project.
        
        Returns:
            dict with counts by enrollment status and completion rates.
        """
        enrollments = self.get_project_learners(include_progress=False)
        
        total = enrollments.count()
        if total == 0:
            return {
                'total_learners': 0,
                'enrolled': 0,
                'in_progress': 0,
                'completed': 0,
                'dropped': 0,
                'completion_rate': 0,
            }
        
        # Count by status
        status_counts = enrollments.values('status').annotate(count=Count('id'))
        status_dict = {item['status']: item['count'] for item in status_counts}
        
        completed = status_dict.get('COMPLETED', 0)
        
        return {
            'total_learners': total,
            'enrolled': status_dict.get('ENROLLED', 0) + status_dict.get('ACTIVE', 0),
            'in_progress': status_dict.get('IN_PROGRESS', 0),
            'completed': completed,
            'dropped': status_dict.get('DROPPED', 0) + status_dict.get('WITHDRAWN', 0),
            'completion_rate': round((completed / total) * 100, 1) if total > 0 else 0,
        }
    
    def get_learner_progress_detail(self, enrollment):
        """
        Get detailed progress for a specific learner enrollment.
        
        Args:
            enrollment: Enrollment instance
            
        Returns:
            dict with module progress, assessments, and completion data.
        """
        learner = enrollment.learner
        
        # Module progress
        module_progress = LearnerModuleProgress.objects.filter(
            enrollment=enrollment
        ).select_related('module')
        
        total_modules = module_progress.count()
        completed_modules = module_progress.filter(status='COMPLETED').count()
        
        # Assessment results - filter by enrollment directly
        assessment_results = AssessmentResult.objects.filter(
            enrollment=enrollment
        ).select_related('activity', 'activity__module')
        
        total_assessments = assessment_results.count()
        # Assessed = any result that's been submitted (not DRAFT)
        assessed_count = assessment_results.exclude(status='DRAFT').count()
        # Competent = result is 'C' (Competent)
        competent_count = assessment_results.filter(result='C').count()
        # Not Yet Competent = result is 'NYC'
        not_yet_competent = assessment_results.filter(result='NYC').count()
        # Moderated = status is 'MODERATED' or 'FINALIZED'
        moderated_count = assessment_results.filter(status__in=['MODERATED', 'FINALIZED']).count()
        
        return {
            'enrollment': enrollment,
            'learner': learner,
            'status': enrollment.status,
            
            # Module progress
            'total_modules': total_modules,
            'completed_modules': completed_modules,
            'module_completion_rate': round((completed_modules / total_modules) * 100, 1) if total_modules > 0 else 0,
            'module_progress': list(module_progress),
            
            # Assessment progress
            'total_assessments': total_assessments,
            'assessed_count': assessed_count,
            'pending_assessments': total_assessments - assessed_count,
            'competent_count': competent_count,
            'not_yet_competent_count': not_yet_competent,
            'moderated_count': moderated_count,
            'assessment_completion_rate': round((assessed_count / total_assessments) * 100, 1) if total_assessments > 0 else 0,
            'competency_rate': round((competent_count / assessed_count) * 100, 1) if assessed_count > 0 else 0,
            'assessment_results': list(assessment_results),
        }
    
    def get_all_learners_with_progress(self):
        """
        Get all learners with their progress summaries.
        
        Returns:
            List of dicts with learner info and progress summary.
        """
        enrollments = self.get_project_learners(include_progress=True)
        
        result = []
        for enrollment in enrollments:
            progress = self.get_learner_progress_detail(enrollment)
            result.append(progress)
        
        return result
    
    def get_assessment_summary(self):
        """
        Get assessment summary across all learners in the project.
        
        Returns:
            dict with assessment statistics.
        """
        enrollments = self.get_project_learners(include_progress=False)
        enrollment_ids = enrollments.values_list('id', flat=True)
        
        results = AssessmentResult.objects.filter(
            enrollment_id__in=enrollment_ids
        )
        
        total = results.count()
        if total == 0:
            return {
                'total_assessments': 0,
                'pending': 0,
                'assessed': 0,
                'competent': 0,
                'not_yet_competent': 0,
                'moderated': 0,
            }
        
        return {
            'total_assessments': total,
            'pending': results.filter(status='DRAFT').count(),
            'assessed': results.exclude(status='DRAFT').count(),
            'competent': results.filter(result='C').count(),
            'not_yet_competent': results.filter(result='NYC').count(),
            'moderated': results.filter(status__in=['MODERATED', 'FINALIZED']).count(),
        }


class DocumentComplianceService:
    """
    Service for checking document compliance and managing expiry notifications.
    """
    
    def __init__(self, training_notification):
        self.training_notification = training_notification
    
    def get_required_document_types(self):
        """Get all document types required for this project."""
        from core.models_not_documents import NOTLearnerDocumentType
        return NOTLearnerDocumentType.get_required_for_project(self.training_notification)
    
    def get_learner_document_status(self, learner):
        """
        Get document compliance status for a specific learner.
        
        Returns:
            dict with document status information.
        """
        from core.models_not_documents import NOTLearnerDocument, NOTLearnerDocumentType
        
        required_types = self.get_required_document_types()
        documents = NOTLearnerDocument.objects.filter(
            training_notification=self.training_notification,
            learner=learner
        ).select_related('document_type')
        
        doc_by_type = {doc.document_type_id: doc for doc in documents}
        
        missing = []
        pending = []
        verified = []
        rejected = []
        expired = []
        expiring_soon = []
        
        for doc_type in required_types:
            doc = doc_by_type.get(doc_type.id)
            
            if not doc:
                missing.append(doc_type)
            elif doc.status == 'PENDING' or doc.status == 'UPLOADED':
                pending.append(doc)
            elif doc.status == 'VERIFIED':
                if doc.is_expired:
                    expired.append(doc)
                elif doc.is_expiring_soon:
                    expiring_soon.append(doc)
                else:
                    verified.append(doc)
            elif doc.status == 'REJECTED':
                rejected.append(doc)
            elif doc.status == 'EXPIRED':
                expired.append(doc)
        
        total_required = len(required_types)
        compliant_count = len(verified)
        
        return {
            'learner': learner,
            'total_required': total_required,
            'missing': missing,
            'pending': pending,
            'verified': verified,
            'rejected': rejected,
            'expired': expired,
            'expiring_soon': expiring_soon,
            'compliant_count': compliant_count,
            'compliance_rate': round((compliant_count / total_required) * 100, 1) if total_required > 0 else 100,
            'is_compliant': len(missing) == 0 and len(rejected) == 0 and len(expired) == 0,
        }
    
    def get_project_document_compliance(self):
        """
        Get overall document compliance for all learners in the project.
        
        Returns:
            dict with compliance statistics.
        """
        from core.models_not_documents import NOTLearnerDocument
        
        progress_service = LearnerProgressService(self.training_notification)
        enrollments = progress_service.get_project_learners(include_progress=False)
        
        total_learners = enrollments.count()
        if total_learners == 0:
            return {
                'total_learners': 0,
                'fully_compliant': 0,
                'partially_compliant': 0,
                'non_compliant': 0,
                'compliance_rate': 100,
            }
        
        fully_compliant = 0
        partially_compliant = 0
        non_compliant = 0
        
        for enrollment in enrollments:
            status = self.get_learner_document_status(enrollment.learner)
            
            if status['is_compliant']:
                fully_compliant += 1
            elif status['compliant_count'] > 0:
                partially_compliant += 1
            else:
                non_compliant += 1
        
        return {
            'total_learners': total_learners,
            'fully_compliant': fully_compliant,
            'partially_compliant': partially_compliant,
            'non_compliant': non_compliant,
            'compliance_rate': round((fully_compliant / total_learners) * 100, 1) if total_learners > 0 else 100,
        }
    
    def get_expiring_documents(self, days_ahead=30):
        """
        Get all documents expiring within the specified number of days.
        
        Args:
            days_ahead: Number of days to look ahead for expiring documents.
            
        Returns:
            QuerySet of NOTLearnerDocument instances.
        """
        from core.models_not_documents import NOTLearnerDocument
        
        cutoff_date = date.today() + timedelta(days=days_ahead)
        
        return NOTLearnerDocument.objects.filter(
            training_notification=self.training_notification,
            expiry_date__lte=cutoff_date,
            expiry_date__gte=date.today(),
            status='VERIFIED'
        ).select_related('learner', 'document_type')
    
    def get_expired_documents(self):
        """Get all expired documents for this project."""
        from core.models_not_documents import NOTLearnerDocument
        
        return NOTLearnerDocument.objects.filter(
            training_notification=self.training_notification,
            expiry_date__lt=date.today()
        ).exclude(status='EXPIRED').select_related('learner', 'document_type')
    
    def create_expiry_warning_tasks(self):
        """
        Create tasks for documents that are expiring soon.
        
        Returns:
            Number of tasks created.
        """
        from core.models_not_documents import NOTLearnerDocument
        
        # Get documents expiring soon that haven't had tasks created
        documents = NOTLearnerDocument.objects.filter(
            training_notification=self.training_notification,
            status='VERIFIED',
            expiry_task_created=False,
            expiry_date__isnull=False
        ).select_related('learner', 'document_type', 'training_notification')
        
        tasks_created = 0
        
        for doc in documents:
            if doc.is_expiring_soon or doc.is_expired:
                # Create task
                try:
                    task = Task.objects.create(
                        title=f"Document Expiring: {doc.document_type.name} for {doc.learner}",
                        description=f"""
Document '{doc.document_type.name}' for learner {doc.learner} in project {doc.training_notification.reference_number} 
is {'expired' if doc.is_expired else 'expiring soon'}.

Expiry Date: {doc.expiry_date}
Days until expiry: {doc.days_until_expiry}

Please request an updated document from the learner.
                        """.strip(),
                        task_type='DOCUMENT_EXPIRY',
                        priority='HIGH' if doc.is_expired else 'MEDIUM',
                        training_notification=doc.training_notification,
                        due_date=doc.expiry_date,
                    )
                    
                    doc.expiry_task_created = True
                    doc.save(update_fields=['expiry_task_created'])
                    tasks_created += 1
                    
                except Exception as e:
                    # Log error but continue
                    print(f"Error creating expiry task for document {doc.id}: {e}")
        
        return tasks_created
    
    def mark_expired_documents(self):
        """
        Update status of expired documents.
        
        Returns:
            Number of documents marked as expired.
        """
        expired_docs = self.get_expired_documents()
        count = expired_docs.count()
        expired_docs.update(status='EXPIRED')
        return count


def get_learner_progress_for_project(training_notification):
    """
    Convenience function to get learner progress summary for a project.
    
    Args:
        training_notification: TrainingNotification instance
        
    Returns:
        dict with progress and compliance data.
    """
    progress_service = LearnerProgressService(training_notification)
    compliance_service = DocumentComplianceService(training_notification)
    
    return {
        'progress': progress_service.get_progress_summary(),
        'assessments': progress_service.get_assessment_summary(),
        'compliance': compliance_service.get_project_document_compliance(),
        'learner_count': progress_service.get_learner_count(),
    }


def get_project_learners_list(training_notification, search=None, status_filter=None, compliance_filter=None):
    """
    Get paginated list of learners for a project with optional filters.
    
    Args:
        training_notification: TrainingNotification instance
        search: Optional search query
        status_filter: Optional enrollment status filter
        compliance_filter: Optional compliance status filter
        
    Returns:
        QuerySet of enrollments.
    """
    progress_service = LearnerProgressService(training_notification)
    enrollments = progress_service.get_project_learners(include_progress=False)
    
    if search:
        enrollments = enrollments.filter(
            Q(learner__user__first_name__icontains=search) |
            Q(learner__user__last_name__icontains=search) |
            Q(learner__user__email__icontains=search) |
            Q(learner__id_number__icontains=search)
        )
    
    if status_filter:
        enrollments = enrollments.filter(status=status_filter)
    
    return enrollments
