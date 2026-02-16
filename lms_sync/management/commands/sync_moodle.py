"""
Management command to sync data from Moodle LMS.
Syncs users, enrollments, grades, and completion status.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from lms_sync.models import (
    MoodleInstance, MoodleCourse, MoodleUser, MoodleEnrollment,
    MoodleGrade, MoodleCompletion, MoodleSyncLog
)
from lms_sync.services.moodle_client import MoodleClient
from learners.models import Learner


class Command(BaseCommand):
    help = 'Sync data from Moodle LMS (users, grades, completions)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--instance',
            type=int,
            help='Moodle instance ID (uses first active if not specified)'
        )
        parser.add_argument(
            '--sync-type',
            type=str,
            choices=['users', 'grades', 'completions', 'all'],
            default='all',
            help='Type of data to sync'
        )
        parser.add_argument(
            '--course-id',
            type=int,
            help='Only sync specific Moodle course ID'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of courses to process'
        )

    def handle(self, *args, **options):
        instance_id = options.get('instance')
        sync_type = options.get('sync_type', 'all')
        course_id = options.get('course_id')
        limit = options.get('limit')

        # Get Moodle instance
        if instance_id:
            try:
                instance = MoodleInstance.objects.get(pk=instance_id, is_active=True)
            except MoodleInstance.DoesNotExist:
                raise CommandError(f"Moodle instance {instance_id} not found or inactive")
        else:
            instance = MoodleInstance.objects.filter(is_active=True).first()
            if not instance:
                raise CommandError("No active Moodle instance found. Run configure_moodle first.")

        self.stdout.write(f"\nSyncing from: {instance.name}")
        self.stdout.write(f"URL: {instance.base_url}")
        self.stdout.write("-" * 60)

        # Create client
        client = MoodleClient(instance=instance)

        # Create sync log
        sync_log = MoodleSyncLog.objects.create(
            instance=instance,
            sync_type=sync_type.upper(),
            direction='PULL',
            status='STARTED',
            started_at=timezone.now()
        )

        try:
            # Get courses to process
            if course_id:
                courses = MoodleCourse.objects.filter(instance=instance, moodle_id=course_id)
            else:
                # Skip site-level course (usually ID 1) which has all users
                courses = MoodleCourse.objects.filter(
                    instance=instance, 
                    sync_enabled=True
                ).exclude(moodle_id=1)
                if limit:
                    courses = courses[:limit]

            self.stdout.write(f"\nProcessing {courses.count()} courses...")

            total_users = 0
            total_grades = 0
            total_completions = 0

            for course in courses:
                self.stdout.write(f"\n  [{course.moodle_id}] {course.fullname[:50]}...")

                if sync_type in ('users', 'all'):
                    users = self._sync_users(instance, client, course)
                    total_users += users

                if sync_type in ('grades', 'all'):
                    grades = self._sync_grades(instance, client, course)
                    total_grades += grades

                if sync_type in ('completions', 'all'):
                    completions = self._sync_completions(instance, client, course)
                    total_completions += completions

            # Update sync log
            sync_log.status = 'SUCCESS'
            sync_log.completed_at = timezone.now()
            sync_log.records_processed = courses.count()
            sync_log.records_created = total_users + total_grades + total_completions
            sync_log.save()

            # Update instance
            instance.last_sync = timezone.now()
            instance.last_sync_status = 'SUCCESS'
            instance.save()

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("Sync completed!"))
            self.stdout.write(f"  Users synced: {total_users}")
            self.stdout.write(f"  Grades synced: {total_grades}")
            self.stdout.write(f"  Completions synced: {total_completions}")

        except Exception as e:
            sync_log.status = 'FAILED'
            sync_log.completed_at = timezone.now()
            sync_log.error_details = [str(e)]
            sync_log.save()
            raise CommandError(f"Sync failed: {e}")

    def _sync_users(self, instance, client, course):
        """Sync enrolled users for a course."""
        enrolled = client.get_enrolled_users(course.moodle_id)
        
        if 'exception' in enrolled:
            self.stdout.write(f"    Users: Error - {enrolled.get('message', 'Unknown')[:30]}")
            return 0

        count = 0
        for user_data in enrolled:
            # Create or update MoodleUser
            moodle_user, _ = MoodleUser.objects.update_or_create(
                instance=instance,
                moodle_id=user_data['id'],
                defaults={
                    'username': user_data.get('username', '')[:100],
                    'email': user_data.get('email', ''),
                    'is_active': True,
                }
            )

            # Try to link to existing learner by email
            if not moodle_user.learner:
                learner = Learner.objects.filter(
                    email__iexact=moodle_user.email
                ).first()
                if learner:
                    moodle_user.learner = learner
                    moodle_user.save()

            # Create enrollment
            MoodleEnrollment.objects.update_or_create(
                moodle_user=moodle_user,
                moodle_course=course,
                defaults={
                    'status': 'ENROLLED',
                    'enrolled_at': timezone.now(),
                }
            )
            count += 1

        self.stdout.write(f"    Users: {count} synced")
        return count

    def _sync_grades(self, instance, client, course):
        """Sync grades for enrolled users in a course."""
        enrollments = MoodleEnrollment.objects.filter(
            moodle_course=course
        ).select_related('moodle_user')

        count = 0
        errors = 0
        for enrollment in enrollments:
            user_id = enrollment.moodle_user.moodle_id
            
            try:
                # Get grades for this user in this course
                grades_data = client.get_user_grades(course.moodle_id, user_id)
                
                # grades_data is already the usergrades list from get_user_grades
                if not grades_data or not isinstance(grades_data, list):
                    continue
                
                for ug in grades_data:
                    if not isinstance(ug, dict):
                        continue
                    for item in ug.get('gradeitems', []):
                        grade_value = item.get('graderaw')
                        if grade_value is None:
                            continue

                        # Clean percentage (remove % sign if present)
                        percentage_str = item.get('percentageformatted', '')
                        percentage = None
                        if percentage_str:
                            try:
                                percentage = float(percentage_str.replace('%', '').strip())
                            except (ValueError, TypeError):
                                percentage = None

                        MoodleGrade.objects.update_or_create(
                            enrollment=enrollment,
                            grade_item_id=item.get('id', 0),
                            defaults={
                                'item_name': str(item.get('itemname', 'Unknown'))[:200],
                                'item_type': str(item.get('itemtype', 'manual'))[:50],
                                'raw_grade': grade_value,
                                'final_grade': item.get('gradeformatted'),
                                'grade_max': item.get('grademax'),
                                'grade_min': item.get('grademin', 0),
                                'percentage': percentage,
                                'synced_at': timezone.now(),
                            }
                        )
                        count += 1
            except Exception as e:
                errors += 1
                if errors <= 3:  # Only show first 3 errors
                    self.stdout.write(self.style.WARNING(f"      Grade error for user {user_id}: {str(e)[:50]}"))
                # Log error but continue with other enrollments
                continue

        if count > 0 or errors > 0:
            self.stdout.write(f"    Grades: {count} synced ({errors} errors)")
        return count

    def _sync_completions(self, instance, client, course):
        """Sync course completion status."""
        enrollments = MoodleEnrollment.objects.filter(
            moodle_course=course
        ).select_related('moodle_user')

        count = 0
        for enrollment in enrollments:
            user_id = enrollment.moodle_user.moodle_id
            
            try:
                # Get completion status
                completion_data = client.get_course_completion_status(
                    course.moodle_id, user_id
                )
                
                if not completion_data or not isinstance(completion_data, dict):
                    continue
                    
                if 'exception' in completion_data:
                    continue

                status = completion_data.get('completionstatus', {})
                is_completed = status.get('completed', False)
                completions = status.get('completions', [])
                
                # Count completed activities
                completed_count = sum(1 for c in completions if c.get('complete'))
                total_count = len(completions)
                
                percentage = (completed_count / total_count * 100) if total_count > 0 else 0

                MoodleCompletion.objects.update_or_create(
                    enrollment=enrollment,
                    defaults={
                        'is_completed': is_completed,
                        'progress_percentage': percentage,
                        'activities_completed': completed_count,
                        'activities_total': total_count,
                        'synced_at': timezone.now(),
                    }
                )
                count += 1
            except Exception as e:
                # Log error but continue
                continue

        if count > 0:
            self.stdout.write(f"    Completions: {count} synced")
        return count
