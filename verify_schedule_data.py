#!/usr/bin/env python
"""
Verify Schedule Data Script
============================
Checks that schedule sessions are properly linked to test users.
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from logistics.models import ScheduleSession
from academics.models import Enrollment
from learners.models import Learner
from django.contrib.auth import get_user_model
User = get_user_model()

print("=" * 60)
print("SCHEDULE DATA VERIFICATION")
print("=" * 60)

# Check learner
try:
    learner_user = User.objects.get(email='schedule.learner@skillsflow.co.za')
    learner = Learner.objects.get(user=learner_user)
    print(f'✓ Learner: {learner}')
    
    enrollments = Enrollment.objects.filter(learner=learner, status__in=['ACTIVE', 'ENROLLED', 'REGISTERED'])
    print(f'✓ Enrollments: {enrollments.count()}')
    for e in enrollments:
        print(f'  - {e.enrollment_number} in cohort: {e.cohort}')
    
    cohort_ids = [e.cohort.id for e in enrollments if e.cohort]
    print(f'✓ Cohort IDs: {cohort_ids}')
    
    total = ScheduleSession.objects.filter(cohort_id__in=cohort_ids).count()
    print(f'✓ Total sessions for learner: {total}')
    
    sessions = ScheduleSession.objects.filter(cohort_id__in=cohort_ids).order_by('date', 'start_time')[:5]
    print(f'\nFirst 5 sessions:')
    for s in sessions:
        print(f'  - {s.date} {s.start_time}-{s.end_time}: {s.session_type} {s.module}')
        
except Exception as e:
    print(f'✗ Error with learner: {e}')

# Check facilitator
print("\n" + "-" * 60)
try:
    facilitator_user = User.objects.get(email='schedule.facilitator@skillsflow.co.za')
    print(f'✓ Facilitator: {facilitator_user}')
    
    # Sessions assigned to facilitator
    facilitator_sessions = ScheduleSession.objects.filter(facilitator=facilitator_user).count()
    print(f'  Sessions directly assigned: {facilitator_sessions}')
    
    # Sessions in cohorts facilitated
    from logistics.models import Cohort
    cohorts = Cohort.objects.filter(facilitator=facilitator_user)
    print(f'  Cohorts facilitated: {cohorts.count()}')
    for c in cohorts:
        count = ScheduleSession.objects.filter(cohort=c).count()
        print(f'    - {c.code}: {count} sessions')
        
except Exception as e:
    print(f'✗ Error with facilitator: {e}')

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
