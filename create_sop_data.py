#!/usr/bin/env python
"""
Script to create sample SOP data for the SkillsFlow application.
Run with: python create_sop_data.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import date
from workflows.models import SOPCategory, SOP, SOPStep


def create_sop_data():
    """Create sample SOP categories, SOPs, and steps."""
    
    print("Creating SOP Categories...")
    
    # Create Categories
    categories = {
        'TRAINING': SOPCategory.objects.create(
            name='Training & Enrollment',
            code='TRAINING',
            description='Procedures for learner enrollment, training delivery, and assessment processes',
            icon='academic-cap',
            color='blue',
            sort_order=1,
            
        ),
        'FINANCE': SOPCategory.objects.create(
            name='Finance & Invoicing',
            code='FINANCE',
            description='Financial procedures including invoicing, payments, and grant claims',
            icon='currency-dollar',
            color='green',
            sort_order=2,
            
        ),
        'HR': SOPCategory.objects.create(
            name='Human Resources',
            code='HR',
            description='HR procedures for staff management, performance reviews, and onboarding',
            icon='users',
            color='rose',
            sort_order=3,
            
        ),
        'CORPORATE': SOPCategory.objects.create(
            name='Corporate Clients',
            code='CORPORATE',
            description='Procedures for managing corporate client relationships and WSP/ATR submissions',
            icon='office-building',
            color='purple',
            sort_order=4,
            
        ),
    }
    print(f"  Created {len(categories)} categories")
    
    print("\nCreating SOPs...")
    
    # =====================================================
    # TRAINING SOPs
    # =====================================================
    
    # SOP 1: New Learner Enrollment
    sop_enrollment = SOP.objects.create(
        category=categories['TRAINING'],
        name='New Learner Enrollment',
        code='TRN-001',
        description='Complete process for enrolling a new learner into a training programme',
        purpose='Ensures consistent and compliant learner enrollment with all required documentation',
        version='1.0',
        effective_date=date.today(),
        icon='user-add',
        estimated_duration='30 minutes',
        
        is_published=True,
    )
    
    steps_enrollment = [
        {'order': 1, 'title': 'Create Learner Profile', 
         'description': 'Navigate to the learner management section and create a new learner profile with all personal details.',
         'app_url_name': 'admin:learner_list', 'app_url_label': 'Go to Learners',
         'responsible_role': 'Admin', 'tips': 'Ensure ID number is validated before proceeding'},
        {'order': 2, 'title': 'Select Programme & Intake',
         'description': 'Choose the appropriate training programme and intake for the learner.',
         'app_url_name': 'admin:intakes', 'app_url_label': 'View Intakes',
         'responsible_role': 'Admin'},
        {'order': 3, 'title': 'Upload Required Documents',
         'description': 'Upload all mandatory documents including ID copy, proof of residence, and highest qualification.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Admin', 'tips': 'Documents must be clear and legible'},
        {'order': 4, 'title': 'Create Enrollment Record',
         'description': 'Create the enrollment linking the learner to the programme and intake.',
         'app_url_name': 'admin:enrollment_list', 'app_url_label': 'Go to Enrollments',
         'responsible_role': 'Admin'},
        {'order': 5, 'title': 'Assign to Training Site',
         'description': 'If applicable, assign the learner to their training campus or workplace.',
         'app_url_name': 'admin:campus_list', 'app_url_label': 'View Campuses',
         'responsible_role': 'Admin', 'is_optional': True},
        {'order': 6, 'title': 'Send Welcome Communication',
         'description': 'Send the learner their welcome pack with programme details and start date.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Admin'},
    ]
    
    for step_data in steps_enrollment:
        SOPStep.objects.create(sop=sop_enrollment, **step_data)
    
    # SOP 2: Assessment Submission
    sop_assessment = SOP.objects.create(
        category=categories['TRAINING'],
        name='Portfolio of Evidence (PoE) Submission',
        code='TRN-002',
        description='Process for submitting and processing learner portfolio of evidence',
        purpose='Standardizes the PoE submission workflow to ensure quality and compliance',
        version='1.0',
        effective_date=date.today(),
        icon='document-text',
        estimated_duration='20 minutes',
        
        is_published=True,
    )
    
    steps_assessment = [
        {'order': 1, 'title': 'Verify Learner Eligibility',
         'description': 'Check that the learner has completed all required modules and is eligible for assessment.',
         'app_url_name': 'admin:enrollment_list', 'app_url_label': 'Check Enrollments',
         'responsible_role': 'Assessor'},
        {'order': 2, 'title': 'Review PoE Contents',
         'description': 'Review the submitted portfolio against the assessment criteria.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Assessor', 'tips': 'Use the assessment rubric for consistency'},
        {'order': 3, 'title': 'Record Assessment Outcome',
         'description': 'Record the assessment result (Competent/Not Yet Competent) in the system.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Assessor'},
        {'order': 4, 'title': 'Submit for Moderation',
         'description': 'If competent, submit for internal moderation before certification.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Assessor'},
    ]
    
    for step_data in steps_assessment:
        SOPStep.objects.create(sop=sop_assessment, **step_data)
    
    # SOP 3: Certification Process
    sop_certification = SOP.objects.create(
        category=categories['TRAINING'],
        name='Learner Certification',
        code='TRN-003',
        description='Process for issuing certificates to competent learners',
        purpose='Ensures certificates are only issued to learners who have met all requirements',
        version='1.0',
        effective_date=date.today(),
        icon='badge-check',
        estimated_duration='15 minutes',
        
        is_published=True,
    )
    
    steps_certification = [
        {'order': 1, 'title': 'Verify Completion Status',
         'description': 'Confirm the learner has completed all modules and passed all assessments.',
         'app_url_name': 'admin:enrollment_list', 'app_url_label': 'View Enrollment',
         'responsible_role': 'Admin'},
        {'order': 2, 'title': 'Generate Certificate',
         'description': 'Generate the certificate with correct details and certificate number.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Admin'},
        {'order': 3, 'title': 'Quality Check',
         'description': 'Verify all details on the certificate are correct.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Quality Assurance', 'tips': 'Double-check learner name spelling and ID number'},
        {'order': 4, 'title': 'Issue Certificate',
         'description': 'Mark enrollment as certified and record issue date.',
         'app_url_name': 'admin:enrollment_list', 'app_url_label': 'Update Enrollment',
         'responsible_role': 'Admin'},
    ]
    
    for step_data in steps_certification:
        SOPStep.objects.create(sop=sop_certification, **step_data)
    
    # =====================================================
    # FINANCE SOPs
    # =====================================================
    
    # SOP 4: Invoice Creation
    sop_invoice = SOP.objects.create(
        category=categories['FINANCE'],
        name='Create Client Invoice',
        code='FIN-001',
        description='Process for creating and sending invoices to corporate clients',
        purpose='Standardizes invoicing to ensure accurate billing and timely payment',
        version='1.0',
        effective_date=date.today(),
        icon='document',
        estimated_duration='15 minutes',
        
        is_published=True,
    )
    
    steps_invoice = [
        {'order': 1, 'title': 'Verify Training Delivery',
         'description': 'Confirm training has been delivered as per the agreement before invoicing.',
         'app_url_name': 'admin:enrollment_list', 'app_url_label': 'Check Enrollments',
         'responsible_role': 'Finance'},
        {'order': 2, 'title': 'Create Invoice',
         'description': 'Create a new invoice with correct amounts and line items.',
         'app_url_name': 'admin:invoice_list', 'app_url_label': 'Go to Invoices',
         'responsible_role': 'Finance'},
        {'order': 3, 'title': 'Attach Supporting Documents',
         'description': 'Attach attendance registers and any other required proof of delivery.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Finance'},
        {'order': 4, 'title': 'Submit for Approval',
         'description': 'Submit invoice for management approval before sending to client.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Finance'},
        {'order': 5, 'title': 'Send to Client',
         'description': 'Email invoice to client with payment terms and bank details.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Finance'},
    ]
    
    for step_data in steps_invoice:
        SOPStep.objects.create(sop=sop_invoice, **step_data)
    
    # SOP 5: Payment Recording
    sop_payment = SOP.objects.create(
        category=categories['FINANCE'],
        name='Record Client Payment',
        code='FIN-002',
        description='Process for recording payments received from clients',
        purpose='Ensures accurate payment tracking and invoice reconciliation',
        version='1.0',
        effective_date=date.today(),
        icon='cash',
        estimated_duration='10 minutes',
        
        is_published=True,
    )
    
    steps_payment = [
        {'order': 1, 'title': 'Verify Payment Receipt',
         'description': 'Confirm payment has been received in the bank account.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Finance'},
        {'order': 2, 'title': 'Match to Invoice',
         'description': 'Find the corresponding invoice and verify the payment amount.',
         'app_url_name': 'admin:invoice_list', 'app_url_label': 'View Invoices',
         'responsible_role': 'Finance'},
        {'order': 3, 'title': 'Record Payment',
         'description': 'Record the payment against the invoice with payment date and reference.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Finance'},
        {'order': 4, 'title': 'Send Receipt',
         'description': 'Email payment receipt to the client.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Finance'},
    ]
    
    for step_data in steps_payment:
        SOPStep.objects.create(sop=sop_payment, **step_data)
    
    # =====================================================
    # HR SOPs
    # =====================================================
    
    # SOP 6: New Employee Onboarding
    sop_onboarding = SOP.objects.create(
        category=categories['HR'],
        name='New Employee Onboarding',
        code='HR-001',
        description='Complete onboarding process for new staff members',
        purpose='Ensures new employees are properly set up and integrated into the company',
        version='1.0',
        effective_date=date.today(),
        icon='user-add',
        estimated_duration='1 hour',
        
        is_published=True,
    )
    
    steps_onboarding = [
        {'order': 1, 'title': 'Create Employee Profile',
         'description': 'Create a new user account and staff profile in the system.',
         'app_url_name': 'admin:user_list', 'app_url_label': 'Go to Users',
         'responsible_role': 'HR'},
        {'order': 2, 'title': 'Assign Department & Position',
         'description': 'Link the employee to their department and assign their job position.',
         'app_url_name': 'hr_admin:staff_list', 'app_url_label': 'View Staff',
         'responsible_role': 'HR'},
        {'order': 3, 'title': 'Set Up System Access',
         'description': 'Configure appropriate system permissions based on their role.',
         'app_url_name': 'admin:user_list', 'app_url_label': 'Manage Permissions',
         'responsible_role': 'IT Admin'},
        {'order': 4, 'title': 'Complete Employment Documents',
         'description': 'Ensure all employment contracts and HR documents are signed.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'HR'},
        {'order': 5, 'title': 'Schedule Orientation',
         'description': 'Arrange orientation sessions with relevant departments.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'HR'},
    ]
    
    for step_data in steps_onboarding:
        SOPStep.objects.create(sop=sop_onboarding, **step_data)
    
    # SOP 7: Performance Review
    sop_performance = SOP.objects.create(
        category=categories['HR'],
        name='Performance Review Process',
        code='HR-002',
        description='Quarterly performance review process for staff',
        purpose='Standardizes performance evaluation and feedback processes',
        version='1.0',
        effective_date=date.today(),
        icon='clipboard-check',
        estimated_duration='45 minutes',
        
        is_published=True,
    )
    
    steps_performance = [
        {'order': 1, 'title': 'Review KPIs',
         'description': 'Review the employee position KPIs and task assignments.',
         'app_url_name': 'hr_admin:position_list', 'app_url_label': 'View Positions',
         'responsible_role': 'Manager'},
        {'order': 2, 'title': 'Gather Feedback',
         'description': 'Collect feedback from colleagues and stakeholders if applicable.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Manager', 'is_optional': True},
        {'order': 3, 'title': 'Complete Review Form',
         'description': 'Fill out the performance review form with ratings and comments.',
         'app_url_name': 'hr_admin:staff_list', 'app_url_label': 'Staff Reviews',
         'responsible_role': 'Manager'},
        {'order': 4, 'title': 'Schedule Review Meeting',
         'description': 'Schedule a one-on-one meeting with the employee to discuss results.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Manager'},
        {'order': 5, 'title': 'Document Development Goals',
         'description': 'Record agreed development goals and action items.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Manager'},
    ]
    
    for step_data in steps_performance:
        SOPStep.objects.create(sop=sop_performance, **step_data)
    
    # =====================================================
    # CORPORATE SOPs
    # =====================================================
    
    # SOP 8: New Client Setup
    sop_client = SOP.objects.create(
        category=categories['CORPORATE'],
        name='New Corporate Client Setup',
        code='CORP-001',
        description='Process for setting up a new corporate client in the system',
        purpose='Ensures proper documentation and system setup for new clients',
        version='1.0',
        effective_date=date.today(),
        icon='office-building',
        estimated_duration='25 minutes',
        
        is_published=True,
    )
    
    steps_client = [
        {'order': 1, 'title': 'Verify Client Documentation',
         'description': 'Check all required documentation has been received (CIPC, Tax clearance, etc.)',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Sales'},
        {'order': 2, 'title': 'Create Client Profile',
         'description': 'Create the corporate client profile in the CRM system.',
         'app_url_name': 'admin:corporate_list', 'app_url_label': 'Go to Clients',
         'responsible_role': 'Admin'},
        {'order': 3, 'title': 'Link SDF',
         'description': 'Link the Skills Development Facilitator to the client account.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Admin'},
        {'order': 4, 'title': 'Set Up Billing',
         'description': 'Configure billing preferences and payment terms.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Finance'},
        {'order': 5, 'title': 'Schedule Kick-off Meeting',
         'description': 'Arrange kick-off meeting to discuss training needs.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'Account Manager'},
    ]
    
    for step_data in steps_client:
        SOPStep.objects.create(sop=sop_client, **step_data)
    
    # SOP 9: WSP Submission
    sop_wsp = SOP.objects.create(
        category=categories['CORPORATE'],
        name='WSP/ATR Submission',
        code='CORP-002',
        description='Process for preparing and submitting WSP and ATR documents',
        purpose='Ensures timely and accurate submission of mandatory SETA documents',
        version='1.0',
        effective_date=date.today(),
        icon='document-report',
        estimated_duration='2 hours',
        
        is_published=True,
    )
    
    steps_wsp = [
        {'order': 1, 'title': 'Gather Training Data',
         'description': 'Compile all training records for the reporting period.',
         'app_url_name': 'admin:enrollment_list', 'app_url_label': 'View Enrollments',
         'responsible_role': 'SDF'},
        {'order': 2, 'title': 'Complete WSP Template',
         'description': 'Fill out the WSP template with planned training for next year.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'SDF'},
        {'order': 3, 'title': 'Complete ATR Template',
         'description': 'Fill out the ATR template with actual training delivered.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'SDF'},
        {'order': 4, 'title': 'Client Review & Sign-off',
         'description': 'Send documents to client for review and signature.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'SDF'},
        {'order': 5, 'title': 'Submit to SETA',
         'description': 'Submit the WSP/ATR to the relevant SETA portal before deadline.',
         'app_url_name': '', 'app_url_label': '',
         'responsible_role': 'SDF', 'tips': 'Submit at least 2 days before deadline to allow for corrections'},
        {'order': 6, 'title': 'Record Submission',
         'description': 'Record the submission confirmation in the client profile.',
         'app_url_name': 'admin:corporate_list', 'app_url_label': 'Update Client',
         'responsible_role': 'SDF'},
    ]
    
    for step_data in steps_wsp:
        SOPStep.objects.create(sop=sop_wsp, **step_data)
    
    print(f"  Created {SOP.objects.count()} SOPs")
    print(f"  Created {SOPStep.objects.count()} steps")
    
    print("\n" + "="*50)
    print("SOP DATA CREATION COMPLETE!")
    print("="*50)
    print(f"\nCategories: {SOPCategory.objects.count()}")
    print(f"SOPs: {SOP.objects.count()}")
    print(f"Steps: {SOPStep.objects.count()}")
    print("\nYou can now view SOPs at /workflows/sops/")


if __name__ == '__main__':
    # Check if data already exists
    if SOPCategory.objects.exists():
        print("SOP data already exists!")
        response = input("Do you want to delete existing data and recreate? (yes/no): ")
        if response.lower() == 'yes':
            print("Deleting existing SOP data...")
            SOPStep.objects.all().delete()
            SOP.objects.all().delete()
            SOPCategory.objects.all().delete()
            create_sop_data()
        else:
            print("Aborted.")
    else:
        create_sop_data()
