#!/usr/bin/env python
"""Check project data in production"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import TrainingNotification, NOTIntake
from academics.models import Enrollment
from logistics.models import Cohort

# Check TrainingNotifications
nots = TrainingNotification.objects.all()
print(f'Total TrainingNotifications: {nots.count()}')
active_statuses = ['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'IN_PROGRESS', 'APPROVED', 'NOTIFICATIONS_SENT']
active_nots = nots.filter(status__in=active_statuses)
print(f'Active TrainingNotifications: {active_nots.count()}')

# Check intakes linked
for n in active_nots[:5]:
    intakes = n.intakes.all()
    print(f'  NOT: {n.title or n.reference_number} - {intakes.count()} intakes')
    for i in intakes:
        cohort_enrollments = 0
        if i.cohort:
            cohort_enrollments = Enrollment.objects.filter(cohort=i.cohort, status='ACTIVE').count()
        print(f'    Intake: {i}, Cohort: {i.cohort}, Enrollments: {cohort_enrollments}')

# Check cohorts with enrollments
cohorts_with_enrollments = Cohort.objects.filter(enrollments__isnull=False).distinct().count()
print(f'\nCohorts with enrollments: {cohorts_with_enrollments}')
active_enrollments = Enrollment.objects.filter(status='ACTIVE').count()
print(f'Active enrollments: {active_enrollments}')

# Check if enrollments have linked cohorts that are NOT linked to NOTIntakes
enrollments_cohorts = Enrollment.objects.filter(status='ACTIVE').values_list('cohort_id', flat=True).distinct()
print(f'\nCohort IDs with active enrollments: {list(enrollments_cohorts)[:10]}...')

# Check if any of these cohorts are linked to NOTIntakes
linked_intakes = NOTIntake.objects.filter(cohort_id__in=enrollments_cohorts)
print(f'NOTIntakes linked to these cohorts: {linked_intakes.count()}')
