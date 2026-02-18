#!/usr/bin/env python
"""Create a learner with a user account for testing"""
import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import User
from learners.models import Learner
from tenants.models import Campus

# Get a campus
campus = Campus.objects.first()
if not campus:
    print("ERROR: No campus found. Please create a campus first.")
    exit(1)

email = "student@demo.com"
password = "student123"

# Check if user exists
existing_user = User.objects.filter(email=email).first()
if existing_user:
    print("=" * 55)
    print("  LEARNER ACCOUNT EXISTS")
    print("=" * 55)
    print(f"  Email:    {email}")
    print(f"  Password: student123")
    print("=" * 55)
    print("  Portal:   http://127.0.0.1:8000/student/")
    print("=" * 55)
    exit(0)

# Create user
user = User.objects.create_user(
    email=email, 
    password=password, 
    first_name="Test", 
    last_name="Student", 
    is_active=True
)
user.email_verified = True
user.save()

# Create learner profile
learner = Learner.objects.create(
    user=user,
    campus=campus,
    learner_number="STU001",
    first_name="Test",
    last_name="Student",
    date_of_birth=date(1995, 5, 15),
    gender="M",
    population_group="A",
    citizenship="SA",
    disability_status="N",
    socio_economic_status="E",
    email=email,
    phone_mobile="0821234567",
)

print("=" * 55)
print("  LEARNER ACCOUNT CREATED")
print("=" * 55)
print(f"  Name:     Test Student")
print(f"  Email:    {email}")
print(f"  Password: {password}")
print("=" * 55)
print("  Portal:   http://127.0.0.1:8000/student/")
print("=" * 55)
