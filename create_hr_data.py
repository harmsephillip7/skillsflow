#!/usr/bin/env python
"""Script to create sample HR data"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import User
from hr.models import StaffProfile, Department, Position, PositionTask
from datetime import date

# Get the admin user
admin_user = User.objects.get(email='admin@skillsflow.co.za')

# Create departments
hr_dept, _ = Department.objects.get_or_create(
    code='HR',
    defaults={
        'name': 'Human Resources',
        'description': 'Human Resources and People Management',
        'created_by': admin_user,
        'updated_by': admin_user
    }
)

it_dept, _ = Department.objects.get_or_create(
    code='IT',
    defaults={
        'name': 'Information Technology',
        'description': 'IT and Systems Development',
        'created_by': admin_user,
        'updated_by': admin_user
    }
)

ops_dept, _ = Department.objects.get_or_create(
    code='OPS',
    defaults={
        'name': 'Operations',
        'description': 'Training Operations and Delivery',
        'created_by': admin_user,
        'updated_by': admin_user
    }
)

print('Created departments: HR, IT, Operations')

# Create positions
it_manager, _ = Position.objects.get_or_create(
    code='ITM-001',
    defaults={
        'title': 'IT Manager',
        'department': it_dept,
        'salary_band': 'MANAGER',
        'job_description_text': 'Manages IT infrastructure and software development',
        'is_active': True,
        'created_by': admin_user,
        'updated_by': admin_user
    }
)

ceo_position, _ = Position.objects.get_or_create(
    code='CEO-001',
    defaults={
        'title': 'Chief Executive Officer',
        'department': ops_dept,
        'salary_band': 'EXECUTIVE',
        'job_description_text': 'Overall leadership and strategic direction',
        'is_active': True,
        'created_by': admin_user,
        'updated_by': admin_user
    }
)

facilitator_pos, _ = Position.objects.get_or_create(
    code='FAC-001',
    defaults={
        'title': 'Training Facilitator',
        'department': ops_dept,
        'salary_band': 'MID',
        'job_description_text': 'Delivers training programs to learners',
        'is_active': True,
        'created_by': admin_user,
        'updated_by': admin_user
    }
)

print('Created positions: CEO, IT Manager, Training Facilitator')

# Create KPI tasks for IT Manager position
tasks_data = [
    {
        'title': 'System Uptime Management',
        'description': 'Ensure all critical systems maintain 99.5% uptime. Target: System uptime >= 99.5% measured monthly',
        'priority': 'CRITICAL',
        'weight': 25,
        'frequency': 'MONTHLY',
    },
    {
        'title': 'Security Compliance',
        'description': 'Maintain security protocols and ensure compliance with data protection regulations. Target: Zero security breaches, pass all compliance audits',
        'priority': 'HIGH',
        'weight': 20,
        'frequency': 'QUARTERLY',
    },
    {
        'title': 'Project Delivery',
        'description': 'Deliver IT projects on time and within budget. Target: 90% of projects delivered on time, within 10% of budget',
        'priority': 'HIGH',
        'weight': 30,
        'frequency': 'QUARTERLY',
    },
    {
        'title': 'Team Development',
        'description': 'Develop and mentor IT team members. Target: Monthly 1-on-1s completed, annual training plans for all team members',
        'priority': 'MEDIUM',
        'weight': 15,
        'frequency': 'MONTHLY',
    },
    {
        'title': 'Documentation',
        'description': 'Maintain up-to-date technical documentation. Target: All systems documented, docs reviewed quarterly',
        'priority': 'LOW',
        'weight': 10,
        'frequency': 'ONGOING',
    },
]

for task_data in tasks_data:
    PositionTask.objects.get_or_create(
        position=it_manager,
        title=task_data['title'],
        defaults={
            'description': task_data['description'],
            'priority': task_data['priority'],
            'weight': task_data['weight'],
            'frequency': task_data['frequency'],
            'is_active': True,
            'created_by': admin_user,
            'updated_by': admin_user
        }
    )

print('Created 5 KPI tasks for IT Manager position')

# Create staff profile for admin user
staff_profile, created = StaffProfile.objects.get_or_create(
    user=admin_user,
    defaults={
        'employee_number': 'EMP001',
        'position': it_manager,
        'department': it_dept,
        'employment_type': 'full_time',
        'employment_status': 'active',
        'date_joined': date(2023, 1, 15),
        'created_by': admin_user,
        'updated_by': admin_user
    }
)

if created:
    print(f'Created staff profile for {admin_user.email} as IT Manager')
else:
    print(f'Staff profile already exists for {admin_user.email}')

print('\nDone! Refresh your profile page at http://127.0.0.1:8000/profile/')
