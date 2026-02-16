#!/usr/bin/env python
"""Create message templates for CRM."""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from crm.communication_models import MessageTemplate
from tenants.models import Campus

# Get or create a default campus
campus = Campus.objects.first()
if not campus:
    print("⚠️  No campus found. Creating a default campus...")
    from tenants.models import Brand
    brand = Brand.objects.first()
    if not brand:
        brand = Brand.objects.create(
            name='SkillsFlow',
            code='SF',
            is_active=True
        )
    campus = Campus.objects.create(
        brand=brand,
        name='Head Office',
        code='HO',
        is_active=True
    )
    print(f"✅ Created campus: {campus.name}")

templates = [
    {
        'name': 'Welcome New Lead',
        'slug': 'welcome-new-lead',
        'description': 'Welcome message for new leads who enquire about courses',
        'channel_type': 'WHATSAPP',
        'category': 'UTILITY',
        'header_type': 'TEXT',
        'header_content': 'Welcome to SkillsFlow!',
        'body': 'Hi {{first_name}}, Thank you for your interest in our training programmes! We are excited to help you on your learning journey. One of our consultants will be in touch shortly.',
        'footer': 'SkillsFlow Training',
        'variables': ['first_name'],
        'status': 'APPROVED',
    },
    {
        'name': 'Course Reminder',
        'slug': 'course-reminder',
        'description': 'Reminder about upcoming course start date',
        'channel_type': 'WHATSAPP',
        'category': 'UTILITY',
        'header_type': 'TEXT',
        'header_content': 'Course Starting Soon!',
        'body': 'Hi {{first_name}}, This is a friendly reminder that your {{course_name}} course starts on {{start_date}}. Please ensure you have completed your registration. We look forward to seeing you!',
        'footer': 'SkillsFlow Training',
        'variables': ['first_name', 'course_name', 'start_date'],
        'status': 'APPROVED',
    },
    {
        'name': 'Follow Up - No Response',
        'slug': 'follow-up-no-response',
        'description': 'Follow up message for leads who have not responded',
        'channel_type': 'WHATSAPP',
        'category': 'MARKETING',
        'header_type': 'NONE',
        'header_content': '',
        'body': 'Hi {{first_name}}, We noticed you enquired about our training programmes recently. We wanted to check if you still need assistance? Reply YES if you would like to chat.',
        'footer': 'SkillsFlow Training',
        'variables': ['first_name'],
        'status': 'APPROVED',
    },
    {
        'name': 'Welcome Email',
        'slug': 'welcome-email',
        'description': 'Welcome email for new learner registrations',
        'channel_type': 'EMAIL',
        'category': 'UTILITY',
        'header_type': 'NONE',
        'header_content': '',
        'email_subject': 'Welcome to SkillsFlow - Your Learning Journey Begins!',
        'body': 'Dear {{first_name}},\n\nWelcome to SkillsFlow Training! We are thrilled to have you join our learning community.\n\nYour registration for {{course_name}} has been received and is being processed.\n\nBest regards,\nThe SkillsFlow Team',
        'variables': ['first_name', 'course_name'],
        'status': 'APPROVED',
    },
    {
        'name': 'Payment Reminder',
        'slug': 'payment-reminder',
        'description': 'Reminder for outstanding payments',
        'channel_type': 'EMAIL',
        'category': 'UTILITY',
        'header_type': 'NONE',
        'header_content': '',
        'email_subject': 'Payment Reminder - {{course_name}}',
        'body': 'Dear {{first_name}},\n\nThis is a friendly reminder that you have an outstanding balance of R{{amount}} for your {{course_name}} course.\n\nPayment Due Date: {{due_date}}\n\nBest regards,\nSkillsFlow Finance Team',
        'variables': ['first_name', 'course_name', 'amount', 'due_date'],
        'status': 'APPROVED',
    },
    {
        'name': 'SMS - Course Reminder',
        'slug': 'sms-course-reminder',
        'description': 'Short SMS reminder for course dates',
        'channel_type': 'SMS',
        'category': 'UTILITY',
        'header_type': 'NONE',
        'header_content': '',
        'body': 'Hi {{first_name}}! Reminder: Your {{course_name}} class is on {{date}} at {{time}}. See you there! - SkillsFlow',
        'variables': ['first_name', 'course_name', 'date', 'time'],
        'status': 'APPROVED',
    },
    {
        'name': 'SMS - Document Request',
        'slug': 'sms-document-request',
        'description': 'Request for outstanding documents',
        'channel_type': 'SMS',
        'category': 'UTILITY',
        'header_type': 'NONE',
        'header_content': '',
        'body': 'Hi {{first_name}}, we still need your {{document_type}} to complete your registration. Please submit ASAP. - SkillsFlow',
        'variables': ['first_name', 'document_type'],
        'status': 'APPROVED',
    },
]

if __name__ == '__main__':
    created = 0
    for t in templates:
        if not MessageTemplate.objects.filter(slug=t['slug']).exists():
            t['campus'] = campus
            MessageTemplate.objects.create(**t)
            print(f"✅ Created: {t['name']} ({t['channel_type']})")
            created += 1
        else:
            print(f"⏭️  Already exists: {t['name']}")

    print(f"\n🎉 Created {created} new templates")
    print(f"📋 Total templates in database: {MessageTemplate.objects.count()}")
