#!/usr/bin/env python
"""Check production database state and identify unlinked data."""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from learners.models import Learner
from academics.models import Qualification, Module, ImplementationPlan, Enrollment
from logistics.models import Cohort, ScheduleSession
from core.models import FacilitatorProfile
from tenants.models import Campus

User = get_user_model()

print("=" * 60)
print("PRODUCTION DATABASE SUMMARY")
print("=" * 60)

# Learners
print("\n--- LEARNERS ---")
learners = Learner.objects.all()
print(f"Total Learners: {learners.count()}")
enrollments = Enrollment.objects.all()
print(f"Total Enrollments: {enrollments.count()}")
unenrolled_ids = Learner.objects.exclude(
    id__in=Enrollment.objects.values_list('learner_id', flat=True)
).values_list('id', flat=True)
print(f"Learners WITHOUT enrollment: {len(unenrolled_ids)}")

# Qualifications
print("\n--- QUALIFICATIONS ---")
quals = Qualification.objects.all()
print(f"Total Qualifications: {quals.count()}")
for q in quals[:10]:
    module_count = Module.objects.filter(qualification=q).count()
    print(f"  • {q.saqa_id}: {q.title[:45]}... ({module_count} modules)")

# Implementation Plans  
print("\n--- IMPLEMENTATION PLANS ---")
plans = ImplementationPlan.objects.all()
print(f"Total Implementation Plans: {plans.count()}")
for p in plans[:5]:
    print(f"  • {p.name} (Qualification: {p.qualification})")

# Cohorts
print("\n--- COHORTS ---")
cohorts = Cohort.objects.all()
print(f"Total Cohorts: {cohorts.count()}")
cohorts_no_qual = Cohort.objects.filter(qualification__isnull=True)
print(f"Cohorts WITHOUT qualification: {cohorts_no_qual.count()}")
cohorts_no_fac = Cohort.objects.filter(facilitator__isnull=True)
print(f"Cohorts WITHOUT facilitator: {cohorts_no_fac.count()}")
for c in cohorts[:8]:
    enroll_count = Enrollment.objects.filter(cohort=c).count()
    session_count = ScheduleSession.objects.filter(cohort=c).count()
    print(f"  • {c.name}: qual={c.qualification_id}, fac={c.facilitator_id}, {enroll_count} enrollments, {session_count} sessions")

# Facilitators
print("\n--- FACILITATORS ---")
fac_profiles = FacilitatorProfile.objects.all()
print(f"Facilitator Profiles: {fac_profiles.count()}")
for fp in fac_profiles[:5]:
    print(f"  • {fp.user.email} - campuses: {list(fp.campuses.values_list('name', flat=True))}")

fac_users = User.objects.filter(groups__name='Facilitator')
print(f"Users in 'Facilitator' group: {fac_users.count()}")

# Campuses
print("\n--- CAMPUSES ---")
campuses = Campus.objects.all()
print(f"Total Campuses: {campuses.count()}")
for c in campuses[:5]:
    print(f"  • {c.code}: {c.name}")

# Schedule Sessions
print("\n--- SCHEDULE SESSIONS ---")
sessions = ScheduleSession.objects.all()
print(f"Total Schedule Sessions: {sessions.count()}")

print("\n" + "=" * 60)
