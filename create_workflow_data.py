#!/usr/bin/env python
"""
Script to create comprehensive workflow data for SkillsFlow ERP
Including: Training Process, Finance Process, HR Process
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import User
from workflows.models import (
    WorkflowDefinition, WorkflowType,
    ProcessFlow, ProcessStage, ProcessStageTransition,
    Milestone, Task
)
from datetime import date, timedelta

# Get admin user for created_by fields
admin_user = User.objects.get(email='admin@skillsflow.co.za')

print("=" * 60)
print("Creating Workflow Data for SkillsFlow ERP")
print("=" * 60)

# ============================================================
# 1. WORKFLOW DEFINITIONS (Legacy workflow system)
# ============================================================
print("\n1. Creating Workflow Definitions...")

workflow_definitions = [
    {
        'name': 'Learner Onboarding',
        'workflow_type': 'learner_onboarding',
        'description': 'Complete learner registration and onboarding process',
        'stages': [
            {'code': 'registration', 'name': 'Registration', 'order': 1},
            {'code': 'document_verification', 'name': 'Document Verification', 'order': 2},
            {'code': 'contract_signing', 'name': 'Contract Signing', 'order': 3},
            {'code': 'orientation', 'name': 'Orientation', 'order': 4},
            {'code': 'onboarding_complete', 'name': 'Onboarding Complete', 'order': 5},
        ],
        'transitions': [
            {'from': 'registration', 'to': 'document_verification'},
            {'from': 'document_verification', 'to': 'contract_signing'},
            {'from': 'contract_signing', 'to': 'orientation'},
            {'from': 'orientation', 'to': 'onboarding_complete'},
        ],
    },
    {
        'name': 'Enrollment Process',
        'workflow_type': 'enrollment',
        'description': 'Learner enrollment in a qualification or skills program',
        'stages': [
            {'code': 'application', 'name': 'Application Received', 'order': 1},
            {'code': 'eligibility_check', 'name': 'Eligibility Check', 'order': 2},
            {'code': 'funding_confirmed', 'name': 'Funding Confirmed', 'order': 3},
            {'code': 'enrolled', 'name': 'Enrolled', 'order': 4},
            {'code': 'training_started', 'name': 'Training Started', 'order': 5},
        ],
        'transitions': [
            {'from': 'application', 'to': 'eligibility_check'},
            {'from': 'eligibility_check', 'to': 'funding_confirmed'},
            {'from': 'funding_confirmed', 'to': 'enrolled'},
            {'from': 'enrolled', 'to': 'training_started'},
        ],
    },
    {
        'name': 'Assessment Journey',
        'workflow_type': 'assessment',
        'description': 'Assessment and competency evaluation process',
        'stages': [
            {'code': 'scheduled', 'name': 'Assessment Scheduled', 'order': 1},
            {'code': 'preparation', 'name': 'Learner Preparation', 'order': 2},
            {'code': 'assessment_day', 'name': 'Assessment Day', 'order': 3},
            {'code': 'marking', 'name': 'Marking & Moderation', 'order': 4},
            {'code': 'results_released', 'name': 'Results Released', 'order': 5},
        ],
        'transitions': [
            {'from': 'scheduled', 'to': 'preparation'},
            {'from': 'preparation', 'to': 'assessment_day'},
            {'from': 'assessment_day', 'to': 'marking'},
            {'from': 'marking', 'to': 'results_released'},
        ],
    },
    {
        'name': 'PoE Submission',
        'workflow_type': 'poe_submission',
        'description': 'Portfolio of Evidence submission and verification',
        'stages': [
            {'code': 'preparation', 'name': 'PoE Preparation', 'order': 1},
            {'code': 'submitted', 'name': 'Submitted', 'order': 2},
            {'code': 'internal_review', 'name': 'Internal Review', 'order': 3},
            {'code': 'external_moderation', 'name': 'External Moderation', 'order': 4},
            {'code': 'approved', 'name': 'Approved', 'order': 5},
        ],
        'transitions': [
            {'from': 'preparation', 'to': 'submitted'},
            {'from': 'submitted', 'to': 'internal_review'},
            {'from': 'internal_review', 'to': 'external_moderation'},
            {'from': 'external_moderation', 'to': 'approved'},
        ],
    },
    {
        'name': 'Certification Process',
        'workflow_type': 'certification',
        'description': 'Certificate application and issuance process',
        'stages': [
            {'code': 'verification', 'name': 'Verification', 'order': 1},
            {'code': 'seta_submission', 'name': 'SETA Submission', 'order': 2},
            {'code': 'seta_approval', 'name': 'SETA Approval', 'order': 3},
            {'code': 'certificate_issued', 'name': 'Certificate Issued', 'order': 4},
            {'code': 'delivered', 'name': 'Delivered to Learner', 'order': 5},
        ],
        'transitions': [
            {'from': 'verification', 'to': 'seta_submission'},
            {'from': 'seta_submission', 'to': 'seta_approval'},
            {'from': 'seta_approval', 'to': 'certificate_issued'},
            {'from': 'certificate_issued', 'to': 'delivered'},
        ],
    },
    {
        'name': 'Invoice Payment',
        'workflow_type': 'invoice_payment',
        'description': 'Invoice generation and payment tracking',
        'stages': [
            {'code': 'draft', 'name': 'Draft', 'order': 1},
            {'code': 'sent', 'name': 'Sent to Client', 'order': 2},
            {'code': 'payment_due', 'name': 'Payment Due', 'order': 3},
            {'code': 'partial_payment', 'name': 'Partial Payment', 'order': 4},
            {'code': 'paid', 'name': 'Paid in Full', 'order': 5},
        ],
        'transitions': [
            {'from': 'draft', 'to': 'sent'},
            {'from': 'sent', 'to': 'payment_due'},
            {'from': 'payment_due', 'to': 'partial_payment'},
            {'from': 'payment_due', 'to': 'paid'},
            {'from': 'partial_payment', 'to': 'paid'},
        ],
    },
    {
        'name': 'Corporate Client Onboarding',
        'workflow_type': 'corporate_onboarding',
        'description': 'Corporate client registration and setup process',
        'stages': [
            {'code': 'lead', 'name': 'Lead', 'order': 1},
            {'code': 'proposal', 'name': 'Proposal Sent', 'order': 2},
            {'code': 'negotiation', 'name': 'Negotiation', 'order': 3},
            {'code': 'contract_signed', 'name': 'Contract Signed', 'order': 4},
            {'code': 'active', 'name': 'Active Client', 'order': 5},
        ],
        'transitions': [
            {'from': 'lead', 'to': 'proposal'},
            {'from': 'proposal', 'to': 'negotiation'},
            {'from': 'negotiation', 'to': 'contract_signed'},
            {'from': 'contract_signed', 'to': 'active'},
        ],
    },
    {
        'name': 'Employee IDP',
        'workflow_type': 'employee_idp',
        'description': 'Individual Development Plan process for employees',
        'stages': [
            {'code': 'draft', 'name': 'Draft', 'order': 1},
            {'code': 'self_assessment', 'name': 'Self Assessment', 'order': 2},
            {'code': 'manager_review', 'name': 'Manager Review', 'order': 3},
            {'code': 'goals_set', 'name': 'Goals Set', 'order': 4},
            {'code': 'in_progress', 'name': 'In Progress', 'order': 5},
            {'code': 'completed', 'name': 'Completed', 'order': 6},
        ],
        'transitions': [
            {'from': 'draft', 'to': 'self_assessment'},
            {'from': 'self_assessment', 'to': 'manager_review'},
            {'from': 'manager_review', 'to': 'goals_set'},
            {'from': 'goals_set', 'to': 'in_progress'},
            {'from': 'in_progress', 'to': 'completed'},
        ],
    },
]

for wf_data in workflow_definitions:
    wf, created = WorkflowDefinition.objects.update_or_create(
        workflow_type=wf_data['workflow_type'],
        defaults={
            'name': wf_data['name'],
            'description': wf_data['description'],
            'stages': wf_data['stages'],
            'transitions': wf_data['transitions'],
            'is_active': True,
            'created_by': admin_user,
            'updated_by': admin_user,
        }
    )
    status = "Created" if created else "Updated"
    print(f"  {status}: {wf.name}")

# ============================================================
# 2. PROCESS FLOWS (New normalized process system)
# ============================================================
print("\n2. Creating Process Flows...")

# Helper function to create process flow with stages and transitions
def create_process_flow(name, entity_type, description, stages_data, transitions_data):
    """Create a process flow with its stages and transitions"""
    process_flow, created = ProcessFlow.objects.update_or_create(
        entity_type=entity_type,
        defaults={
            'name': name,
            'description': description,
            'is_active': True,
            'version': 1,
            'created_by': admin_user,
            'updated_by': admin_user,
        }
    )
    
    # Create stages
    stages = {}
    for stage_data in stages_data:
        stage, _ = ProcessStage.objects.update_or_create(
            process_flow=process_flow,
            code=stage_data['code'],
            defaults={
                'name': stage_data['name'],
                'description': stage_data.get('description', ''),
                'stage_type': stage_data.get('stage_type', 'intermediate'),
                'sequence_order': stage_data['order'],
                'color': stage_data.get('color', 'gray'),
                'icon': stage_data.get('icon', ''),
                'requires_reason_on_entry': stage_data.get('requires_reason', False),
                'is_active': True,
                'created_by': admin_user,
                'updated_by': admin_user,
            }
        )
        stages[stage_data['code']] = stage
    
    # Create transitions
    for trans_data in transitions_data:
        from_stage = stages.get(trans_data['from'])
        to_stage = stages.get(trans_data['to'])
        if from_stage and to_stage:
            ProcessStageTransition.objects.update_or_create(
                process_flow=process_flow,
                from_stage=from_stage,
                to_stage=to_stage,
                defaults={
                    'is_allowed': True,
                    'requires_reason': trans_data.get('requires_reason', False),
                    'requires_approval': trans_data.get('requires_approval', False),
                    'approval_role': trans_data.get('approval_role', ''),
                    'validation_rules': trans_data.get('validation_rules', {}),
                    'created_by': admin_user,
                    'updated_by': admin_user,
                }
            )
    
    return process_flow, created


# ------------ ENROLLMENT PROCESS ------------
enrollment_stages = [
    {'code': 'pending', 'name': 'Pending', 'order': 1, 'stage_type': 'initial', 'color': 'gray', 'icon': 'clock'},
    {'code': 'documents_requested', 'name': 'Documents Requested', 'order': 2, 'color': 'yellow', 'icon': 'document'},
    {'code': 'documents_received', 'name': 'Documents Received', 'order': 3, 'color': 'blue', 'icon': 'check'},
    {'code': 'eligibility_check', 'name': 'Eligibility Check', 'order': 4, 'color': 'purple', 'icon': 'search'},
    {'code': 'funding_application', 'name': 'Funding Application', 'order': 5, 'color': 'indigo', 'icon': 'currency'},
    {'code': 'funding_approved', 'name': 'Funding Approved', 'order': 6, 'color': 'teal', 'icon': 'check-circle'},
    {'code': 'contract_sent', 'name': 'Contract Sent', 'order': 7, 'color': 'cyan', 'icon': 'mail'},
    {'code': 'contract_signed', 'name': 'Contract Signed', 'order': 8, 'color': 'emerald', 'icon': 'pencil'},
    {'code': 'enrolled', 'name': 'Enrolled', 'order': 9, 'stage_type': 'terminal_success', 'color': 'green', 'icon': 'check-circle'},
    {'code': 'declined', 'name': 'Declined', 'order': 10, 'stage_type': 'terminal_failure', 'color': 'red', 'icon': 'x-circle', 'requires_reason': True},
    {'code': 'withdrawn', 'name': 'Withdrawn', 'order': 11, 'stage_type': 'terminal_failure', 'color': 'orange', 'icon': 'arrow-left', 'requires_reason': True},
]

enrollment_transitions = [
    {'from': 'pending', 'to': 'documents_requested'},
    {'from': 'pending', 'to': 'declined', 'requires_reason': True},
    {'from': 'documents_requested', 'to': 'documents_received'},
    {'from': 'documents_requested', 'to': 'withdrawn', 'requires_reason': True},
    {'from': 'documents_received', 'to': 'eligibility_check'},
    {'from': 'eligibility_check', 'to': 'funding_application'},
    {'from': 'eligibility_check', 'to': 'declined', 'requires_reason': True},
    {'from': 'funding_application', 'to': 'funding_approved'},
    {'from': 'funding_application', 'to': 'declined', 'requires_reason': True},
    {'from': 'funding_approved', 'to': 'contract_sent'},
    {'from': 'contract_sent', 'to': 'contract_signed'},
    {'from': 'contract_sent', 'to': 'withdrawn', 'requires_reason': True},
    {'from': 'contract_signed', 'to': 'enrolled'},
]

pf, created = create_process_flow(
    'Enrollment Process',
    'enrollment',
    'Learner enrollment from application to active enrollment',
    enrollment_stages,
    enrollment_transitions
)
print(f"  {'Created' if created else 'Updated'}: {pf.name} ({len(enrollment_stages)} stages)")


# ------------ LEARNER TRAINING PROCESS ------------
learner_stages = [
    {'code': 'registered', 'name': 'Registered', 'order': 1, 'stage_type': 'initial', 'color': 'gray', 'icon': 'user-plus'},
    {'code': 'orientation', 'name': 'Orientation', 'order': 2, 'color': 'blue', 'icon': 'academic-cap'},
    {'code': 'training_active', 'name': 'Training Active', 'order': 3, 'color': 'green', 'icon': 'book-open'},
    {'code': 'workplace_placement', 'name': 'Workplace Placement', 'order': 4, 'color': 'purple', 'icon': 'briefcase'},
    {'code': 'assessment_pending', 'name': 'Assessment Pending', 'order': 5, 'color': 'yellow', 'icon': 'clipboard-check'},
    {'code': 'assessment_complete', 'name': 'Assessment Complete', 'order': 6, 'color': 'teal', 'icon': 'check'},
    {'code': 'poe_preparation', 'name': 'PoE Preparation', 'order': 7, 'color': 'indigo', 'icon': 'folder'},
    {'code': 'poe_submitted', 'name': 'PoE Submitted', 'order': 8, 'color': 'cyan', 'icon': 'upload'},
    {'code': 'moderation', 'name': 'Moderation', 'order': 9, 'color': 'pink', 'icon': 'eye'},
    {'code': 'certification_pending', 'name': 'Certification Pending', 'order': 10, 'color': 'amber', 'icon': 'badge-check'},
    {'code': 'certified', 'name': 'Certified', 'order': 11, 'stage_type': 'terminal_success', 'color': 'green', 'icon': 'star'},
    {'code': 'dropped_out', 'name': 'Dropped Out', 'order': 12, 'stage_type': 'terminal_failure', 'color': 'red', 'icon': 'x', 'requires_reason': True},
    {'code': 'transferred', 'name': 'Transferred', 'order': 13, 'stage_type': 'terminal_failure', 'color': 'orange', 'icon': 'switch-horizontal'},
]

learner_transitions = [
    {'from': 'registered', 'to': 'orientation'},
    {'from': 'orientation', 'to': 'training_active'},
    {'from': 'orientation', 'to': 'dropped_out', 'requires_reason': True},
    {'from': 'training_active', 'to': 'workplace_placement'},
    {'from': 'training_active', 'to': 'assessment_pending'},
    {'from': 'training_active', 'to': 'dropped_out', 'requires_reason': True},
    {'from': 'workplace_placement', 'to': 'assessment_pending'},
    {'from': 'workplace_placement', 'to': 'dropped_out', 'requires_reason': True},
    {'from': 'assessment_pending', 'to': 'assessment_complete'},
    {'from': 'assessment_pending', 'to': 'training_active'},  # Retry
    {'from': 'assessment_complete', 'to': 'poe_preparation'},
    {'from': 'poe_preparation', 'to': 'poe_submitted'},
    {'from': 'poe_submitted', 'to': 'moderation'},
    {'from': 'poe_submitted', 'to': 'poe_preparation'},  # Returned for fixes
    {'from': 'moderation', 'to': 'certification_pending'},
    {'from': 'moderation', 'to': 'poe_preparation'},  # Returned for fixes
    {'from': 'certification_pending', 'to': 'certified'},
]

pf, created = create_process_flow(
    'Learner Training Process',
    'learner',
    'Full learner journey from registration to certification',
    learner_stages,
    learner_transitions
)
print(f"  {'Created' if created else 'Updated'}: {pf.name} ({len(learner_stages)} stages)")


# ------------ INVOICE/FINANCE PROCESS ------------
invoice_stages = [
    {'code': 'draft', 'name': 'Draft', 'order': 1, 'stage_type': 'initial', 'color': 'gray', 'icon': 'document-text'},
    {'code': 'pending_approval', 'name': 'Pending Approval', 'order': 2, 'color': 'yellow', 'icon': 'clock'},
    {'code': 'approved', 'name': 'Approved', 'order': 3, 'color': 'blue', 'icon': 'check'},
    {'code': 'sent', 'name': 'Sent to Client', 'order': 4, 'color': 'purple', 'icon': 'mail'},
    {'code': 'payment_due', 'name': 'Payment Due', 'order': 5, 'color': 'orange', 'icon': 'exclamation'},
    {'code': 'overdue', 'name': 'Overdue', 'order': 6, 'color': 'red', 'icon': 'exclamation-circle'},
    {'code': 'partial_payment', 'name': 'Partial Payment', 'order': 7, 'color': 'amber', 'icon': 'cash'},
    {'code': 'paid', 'name': 'Paid', 'order': 8, 'stage_type': 'terminal_success', 'color': 'green', 'icon': 'check-circle'},
    {'code': 'cancelled', 'name': 'Cancelled', 'order': 9, 'stage_type': 'terminal_failure', 'color': 'gray', 'icon': 'x-circle', 'requires_reason': True},
    {'code': 'written_off', 'name': 'Written Off', 'order': 10, 'stage_type': 'terminal_failure', 'color': 'red', 'icon': 'trash', 'requires_reason': True},
]

invoice_transitions = [
    {'from': 'draft', 'to': 'pending_approval'},
    {'from': 'draft', 'to': 'cancelled', 'requires_reason': True},
    {'from': 'pending_approval', 'to': 'approved', 'requires_approval': True, 'approval_role': 'finance_manager'},
    {'from': 'pending_approval', 'to': 'draft'},  # Returned for edits
    {'from': 'approved', 'to': 'sent'},
    {'from': 'sent', 'to': 'payment_due'},
    {'from': 'payment_due', 'to': 'overdue'},
    {'from': 'payment_due', 'to': 'partial_payment'},
    {'from': 'payment_due', 'to': 'paid'},
    {'from': 'overdue', 'to': 'partial_payment'},
    {'from': 'overdue', 'to': 'paid'},
    {'from': 'overdue', 'to': 'written_off', 'requires_reason': True, 'requires_approval': True, 'approval_role': 'finance_director'},
    {'from': 'partial_payment', 'to': 'paid'},
    {'from': 'partial_payment', 'to': 'overdue'},
]

pf, created = create_process_flow(
    'Invoice Payment Process',
    'invoice',
    'Invoice lifecycle from creation to payment',
    invoice_stages,
    invoice_transitions
)
print(f"  {'Created' if created else 'Updated'}: {pf.name} ({len(invoice_stages)} stages)")


# ------------ CORPORATE CLIENT PROCESS ------------
corporate_stages = [
    {'code': 'lead', 'name': 'Lead', 'order': 1, 'stage_type': 'initial', 'color': 'gray', 'icon': 'sparkles'},
    {'code': 'contacted', 'name': 'Contacted', 'order': 2, 'color': 'blue', 'icon': 'phone'},
    {'code': 'needs_analysis', 'name': 'Needs Analysis', 'order': 3, 'color': 'purple', 'icon': 'clipboard-list'},
    {'code': 'proposal_sent', 'name': 'Proposal Sent', 'order': 4, 'color': 'indigo', 'icon': 'document'},
    {'code': 'negotiation', 'name': 'Negotiation', 'order': 5, 'color': 'yellow', 'icon': 'chat'},
    {'code': 'contract_pending', 'name': 'Contract Pending', 'order': 6, 'color': 'amber', 'icon': 'document-text'},
    {'code': 'contract_signed', 'name': 'Contract Signed', 'order': 7, 'color': 'teal', 'icon': 'pencil'},
    {'code': 'onboarding', 'name': 'Onboarding', 'order': 8, 'color': 'cyan', 'icon': 'user-group'},
    {'code': 'active', 'name': 'Active Client', 'order': 9, 'stage_type': 'terminal_success', 'color': 'green', 'icon': 'check-circle'},
    {'code': 'lost', 'name': 'Lost', 'order': 10, 'stage_type': 'terminal_failure', 'color': 'red', 'icon': 'x-circle', 'requires_reason': True},
    {'code': 'dormant', 'name': 'Dormant', 'order': 11, 'color': 'gray', 'icon': 'moon'},
]

corporate_transitions = [
    {'from': 'lead', 'to': 'contacted'},
    {'from': 'lead', 'to': 'lost', 'requires_reason': True},
    {'from': 'contacted', 'to': 'needs_analysis'},
    {'from': 'contacted', 'to': 'lost', 'requires_reason': True},
    {'from': 'needs_analysis', 'to': 'proposal_sent'},
    {'from': 'needs_analysis', 'to': 'lost', 'requires_reason': True},
    {'from': 'proposal_sent', 'to': 'negotiation'},
    {'from': 'proposal_sent', 'to': 'lost', 'requires_reason': True},
    {'from': 'negotiation', 'to': 'contract_pending'},
    {'from': 'negotiation', 'to': 'proposal_sent'},  # New proposal
    {'from': 'negotiation', 'to': 'lost', 'requires_reason': True},
    {'from': 'contract_pending', 'to': 'contract_signed'},
    {'from': 'contract_pending', 'to': 'lost', 'requires_reason': True},
    {'from': 'contract_signed', 'to': 'onboarding'},
    {'from': 'onboarding', 'to': 'active'},
    {'from': 'active', 'to': 'dormant'},
    {'from': 'dormant', 'to': 'active'},
    {'from': 'dormant', 'to': 'lost', 'requires_reason': True},
]

pf, created = create_process_flow(
    'Corporate Client Process',
    'corporate_client',
    'Corporate client lifecycle from lead to active client',
    corporate_stages,
    corporate_transitions
)
print(f"  {'Created' if created else 'Updated'}: {pf.name} ({len(corporate_stages)} stages)")


# ------------ ASSESSMENT PROCESS ------------
assessment_stages = [
    {'code': 'scheduled', 'name': 'Scheduled', 'order': 1, 'stage_type': 'initial', 'color': 'gray', 'icon': 'calendar'},
    {'code': 'preparation', 'name': 'Preparation', 'order': 2, 'color': 'blue', 'icon': 'book-open'},
    {'code': 'ready', 'name': 'Ready for Assessment', 'order': 3, 'color': 'purple', 'icon': 'check'},
    {'code': 'in_progress', 'name': 'In Progress', 'order': 4, 'color': 'yellow', 'icon': 'play'},
    {'code': 'submitted', 'name': 'Submitted', 'order': 5, 'color': 'indigo', 'icon': 'upload'},
    {'code': 'marking', 'name': 'Marking', 'order': 6, 'color': 'pink', 'icon': 'pencil'},
    {'code': 'moderation', 'name': 'Moderation', 'order': 7, 'color': 'cyan', 'icon': 'eye'},
    {'code': 'results_pending', 'name': 'Results Pending', 'order': 8, 'color': 'amber', 'icon': 'clock'},
    {'code': 'competent', 'name': 'Competent', 'order': 9, 'stage_type': 'terminal_success', 'color': 'green', 'icon': 'check-circle'},
    {'code': 'not_yet_competent', 'name': 'Not Yet Competent', 'order': 10, 'stage_type': 'terminal_failure', 'color': 'orange', 'icon': 'refresh'},
    {'code': 'absent', 'name': 'Absent', 'order': 11, 'stage_type': 'terminal_failure', 'color': 'red', 'icon': 'x', 'requires_reason': True},
]

assessment_transitions = [
    {'from': 'scheduled', 'to': 'preparation'},
    {'from': 'scheduled', 'to': 'absent', 'requires_reason': True},
    {'from': 'preparation', 'to': 'ready'},
    {'from': 'ready', 'to': 'in_progress'},
    {'from': 'ready', 'to': 'absent', 'requires_reason': True},
    {'from': 'in_progress', 'to': 'submitted'},
    {'from': 'submitted', 'to': 'marking'},
    {'from': 'marking', 'to': 'moderation'},
    {'from': 'moderation', 'to': 'results_pending'},
    {'from': 'moderation', 'to': 'marking'},  # Returned for re-marking
    {'from': 'results_pending', 'to': 'competent'},
    {'from': 'results_pending', 'to': 'not_yet_competent'},
]

pf, created = create_process_flow(
    'Assessment Process',
    'assessment',
    'Assessment journey from scheduling to results',
    assessment_stages,
    assessment_transitions
)
print(f"  {'Created' if created else 'Updated'}: {pf.name} ({len(assessment_stages)} stages)")


# ------------ POE SUBMISSION PROCESS ------------
poe_stages = [
    {'code': 'not_started', 'name': 'Not Started', 'order': 1, 'stage_type': 'initial', 'color': 'gray', 'icon': 'folder'},
    {'code': 'in_progress', 'name': 'In Progress', 'order': 2, 'color': 'blue', 'icon': 'pencil'},
    {'code': 'evidence_collection', 'name': 'Evidence Collection', 'order': 3, 'color': 'purple', 'icon': 'collection'},
    {'code': 'review_ready', 'name': 'Ready for Review', 'order': 4, 'color': 'yellow', 'icon': 'eye'},
    {'code': 'facilitator_review', 'name': 'Facilitator Review', 'order': 5, 'color': 'indigo', 'icon': 'user'},
    {'code': 'submitted', 'name': 'Submitted', 'order': 6, 'color': 'cyan', 'icon': 'upload'},
    {'code': 'internal_moderation', 'name': 'Internal Moderation', 'order': 7, 'color': 'pink', 'icon': 'shield-check'},
    {'code': 'external_moderation', 'name': 'External Moderation', 'order': 8, 'color': 'amber', 'icon': 'globe'},
    {'code': 'approved', 'name': 'Approved', 'order': 9, 'stage_type': 'terminal_success', 'color': 'green', 'icon': 'check-circle'},
    {'code': 'returned', 'name': 'Returned for Corrections', 'order': 10, 'color': 'orange', 'icon': 'arrow-left'},
    {'code': 'rejected', 'name': 'Rejected', 'order': 11, 'stage_type': 'terminal_failure', 'color': 'red', 'icon': 'x-circle', 'requires_reason': True},
]

poe_transitions = [
    {'from': 'not_started', 'to': 'in_progress'},
    {'from': 'in_progress', 'to': 'evidence_collection'},
    {'from': 'evidence_collection', 'to': 'review_ready'},
    {'from': 'review_ready', 'to': 'facilitator_review'},
    {'from': 'facilitator_review', 'to': 'submitted'},
    {'from': 'facilitator_review', 'to': 'in_progress'},  # Returned for work
    {'from': 'submitted', 'to': 'internal_moderation'},
    {'from': 'internal_moderation', 'to': 'external_moderation'},
    {'from': 'internal_moderation', 'to': 'returned'},
    {'from': 'external_moderation', 'to': 'approved'},
    {'from': 'external_moderation', 'to': 'returned'},
    {'from': 'external_moderation', 'to': 'rejected', 'requires_reason': True},
    {'from': 'returned', 'to': 'in_progress'},
]

pf, created = create_process_flow(
    'PoE Submission Process',
    'poe_submission',
    'Portfolio of Evidence submission and moderation',
    poe_stages,
    poe_transitions
)
print(f"  {'Created' if created else 'Updated'}: {pf.name} ({len(poe_stages)} stages)")


# ------------ GRANT PROJECT PROCESS ------------
grant_stages = [
    {'code': 'planning', 'name': 'Planning', 'order': 1, 'stage_type': 'initial', 'color': 'gray', 'icon': 'light-bulb'},
    {'code': 'application_prep', 'name': 'Application Preparation', 'order': 2, 'color': 'blue', 'icon': 'document'},
    {'code': 'submitted', 'name': 'Submitted to SETA', 'order': 3, 'color': 'purple', 'icon': 'upload'},
    {'code': 'under_review', 'name': 'Under Review', 'order': 4, 'color': 'yellow', 'icon': 'eye'},
    {'code': 'approved', 'name': 'Approved', 'order': 5, 'color': 'green', 'icon': 'check'},
    {'code': 'moa_signed', 'name': 'MoA Signed', 'order': 6, 'color': 'teal', 'icon': 'pencil'},
    {'code': 'implementation', 'name': 'Implementation', 'order': 7, 'color': 'indigo', 'icon': 'play'},
    {'code': 'reporting', 'name': 'Reporting Phase', 'order': 8, 'color': 'pink', 'icon': 'chart-bar'},
    {'code': 'audit', 'name': 'Audit', 'order': 9, 'color': 'amber', 'icon': 'clipboard-check'},
    {'code': 'completed', 'name': 'Completed', 'order': 10, 'stage_type': 'terminal_success', 'color': 'green', 'icon': 'check-circle'},
    {'code': 'rejected', 'name': 'Rejected', 'order': 11, 'stage_type': 'terminal_failure', 'color': 'red', 'icon': 'x-circle', 'requires_reason': True},
    {'code': 'cancelled', 'name': 'Cancelled', 'order': 12, 'stage_type': 'terminal_failure', 'color': 'gray', 'icon': 'ban', 'requires_reason': True},
]

grant_transitions = [
    {'from': 'planning', 'to': 'application_prep'},
    {'from': 'planning', 'to': 'cancelled', 'requires_reason': True},
    {'from': 'application_prep', 'to': 'submitted'},
    {'from': 'submitted', 'to': 'under_review'},
    {'from': 'under_review', 'to': 'approved'},
    {'from': 'under_review', 'to': 'rejected', 'requires_reason': True},
    {'from': 'approved', 'to': 'moa_signed'},
    {'from': 'moa_signed', 'to': 'implementation'},
    {'from': 'implementation', 'to': 'reporting'},
    {'from': 'implementation', 'to': 'cancelled', 'requires_reason': True},
    {'from': 'reporting', 'to': 'audit'},
    {'from': 'audit', 'to': 'completed'},
    {'from': 'audit', 'to': 'reporting'},  # Issues found, return to reporting
]

pf, created = create_process_flow(
    'Grant Project Process',
    'grant_project',
    'SETA grant project lifecycle',
    grant_stages,
    grant_transitions
)
print(f"  {'Created' if created else 'Updated'}: {pf.name} ({len(grant_stages)} stages)")


# ============================================================
# 3. MILESTONES FOR USER JOURNEYS
# ============================================================
print("\n3. Creating Milestones...")

milestones_data = [
    # Learner Journey Milestones
    {'journey_type': 'learner', 'name': 'registered', 'display_name': 'Registered', 'order': 1, 'points': 10, 'icon': 'user-plus', 'color': 'blue'},
    {'journey_type': 'learner', 'name': 'documents_submitted', 'display_name': 'Documents Submitted', 'order': 2, 'points': 15, 'icon': 'document', 'color': 'purple'},
    {'journey_type': 'learner', 'name': 'orientation_complete', 'display_name': 'Orientation Complete', 'order': 3, 'points': 20, 'icon': 'academic-cap', 'color': 'indigo'},
    {'journey_type': 'learner', 'name': 'first_module', 'display_name': 'First Module Complete', 'order': 4, 'points': 25, 'icon': 'book-open', 'color': 'green'},
    {'journey_type': 'learner', 'name': 'halfway', 'display_name': 'Halfway There', 'order': 5, 'points': 30, 'icon': 'chart-bar', 'color': 'yellow'},
    {'journey_type': 'learner', 'name': 'workplace_started', 'display_name': 'Workplace Started', 'order': 6, 'points': 25, 'icon': 'briefcase', 'color': 'teal'},
    {'journey_type': 'learner', 'name': 'all_assessments', 'display_name': 'All Assessments Complete', 'order': 7, 'points': 40, 'icon': 'clipboard-check', 'color': 'pink'},
    {'journey_type': 'learner', 'name': 'poe_submitted', 'display_name': 'PoE Submitted', 'order': 8, 'points': 35, 'icon': 'folder', 'color': 'cyan'},
    {'journey_type': 'learner', 'name': 'certified', 'display_name': 'Certified!', 'order': 9, 'points': 100, 'icon': 'star', 'color': 'gold'},
    
    # Facilitator Journey Milestones
    {'journey_type': 'facilitator', 'name': 'onboarded', 'display_name': 'Onboarded', 'order': 1, 'points': 10, 'icon': 'user-check', 'color': 'blue'},
    {'journey_type': 'facilitator', 'name': 'first_class', 'display_name': 'First Class Delivered', 'order': 2, 'points': 25, 'icon': 'presentation-chart-bar', 'color': 'green'},
    {'journey_type': 'facilitator', 'name': 'ten_learners', 'display_name': '10 Learners Trained', 'order': 3, 'points': 30, 'icon': 'user-group', 'color': 'purple'},
    {'journey_type': 'facilitator', 'name': 'first_assessment', 'display_name': 'First Assessment Conducted', 'order': 4, 'points': 20, 'icon': 'clipboard', 'color': 'yellow'},
    {'journey_type': 'facilitator', 'name': 'first_certification', 'display_name': 'First Learner Certified', 'order': 5, 'points': 50, 'icon': 'badge-check', 'color': 'gold'},
    {'journey_type': 'facilitator', 'name': 'fifty_learners', 'display_name': '50 Learners Trained', 'order': 6, 'points': 75, 'icon': 'star', 'color': 'pink'},
    
    # Corporate SDF Journey Milestones  
    {'journey_type': 'corporate_sdf', 'name': 'registered', 'display_name': 'Registered as SDF', 'order': 1, 'points': 10, 'icon': 'identification', 'color': 'blue'},
    {'journey_type': 'corporate_sdf', 'name': 'wsp_submitted', 'display_name': 'First WSP Submitted', 'order': 2, 'points': 30, 'icon': 'document-text', 'color': 'purple'},
    {'journey_type': 'corporate_sdf', 'name': 'first_learner', 'display_name': 'First Learner Enrolled', 'order': 3, 'points': 25, 'icon': 'user-add', 'color': 'green'},
    {'journey_type': 'corporate_sdf', 'name': 'grant_approved', 'display_name': 'Grant Approved', 'order': 4, 'points': 50, 'icon': 'cash', 'color': 'yellow'},
    {'journey_type': 'corporate_sdf', 'name': 'atr_submitted', 'display_name': 'ATR Submitted', 'order': 5, 'points': 30, 'icon': 'chart-pie', 'color': 'pink'},
    {'journey_type': 'corporate_sdf', 'name': 'ten_learners_certified', 'display_name': '10 Learners Certified', 'order': 6, 'points': 100, 'icon': 'star', 'color': 'gold'},
]

for ms_data in milestones_data:
    milestone, created = Milestone.objects.update_or_create(
        journey_type=ms_data['journey_type'],
        name=ms_data['name'],
        defaults={
            'display_name': ms_data['display_name'],
            'order': ms_data['order'],
            'points': ms_data['points'],
            'icon': ms_data['icon'],
            'color': ms_data['color'],
            'description': '',
            'completion_criteria': {},
        }
    )

print(f"  Created/Updated {len(milestones_data)} milestones across 3 journey types")


# ============================================================
# 4. SAMPLE TASKS
# ============================================================
print("\n4. Creating Sample Tasks...")

today = date.today()
tasks_data = [
    # Training Tasks
    {'name': 'Review pending enrollment applications', 'description': 'Review and process 5 new enrollment applications', 'priority': 'high', 'due_date': today + timedelta(days=1), 'related_entity_type': 'enrollment'},
    {'name': 'Schedule orientation for new learners', 'description': 'Schedule orientation session for 10 new learners starting next week', 'priority': 'medium', 'due_date': today + timedelta(days=3), 'related_entity_type': 'learner'},
    {'name': 'Upload training materials for NQF 4', 'description': 'Upload updated training materials for NQF Level 4 programme', 'priority': 'medium', 'due_date': today + timedelta(days=5), 'related_entity_type': 'training'},
    {'name': 'Conduct workplace visit', 'description': 'Visit XYZ Company for workplace assessment', 'priority': 'high', 'due_date': today + timedelta(days=2), 'related_entity_type': 'workplace'},
    
    # Finance Tasks
    {'name': 'Generate monthly invoices', 'description': 'Generate invoices for all corporate clients for January 2026', 'priority': 'urgent', 'due_date': today, 'related_entity_type': 'invoice'},
    {'name': 'Follow up on overdue payments', 'description': 'Contact 3 clients with overdue payments exceeding 30 days', 'priority': 'high', 'due_date': today + timedelta(days=1), 'related_entity_type': 'invoice'},
    {'name': 'Process SETA grant claim', 'description': 'Submit grant claim for completed Q4 training', 'priority': 'high', 'due_date': today + timedelta(days=7), 'related_entity_type': 'grant'},
    {'name': 'Reconcile learner payments', 'description': 'Reconcile payments received from self-funded learners', 'priority': 'medium', 'due_date': today + timedelta(days=5), 'related_entity_type': 'payment'},
    
    # HR Tasks
    {'name': 'Review employee leave requests', 'description': 'Process pending leave requests for February', 'priority': 'medium', 'due_date': today + timedelta(days=2), 'related_entity_type': 'hr'},
    {'name': 'Schedule performance reviews', 'description': 'Schedule Q1 performance review meetings for all facilitators', 'priority': 'medium', 'due_date': today + timedelta(days=14), 'related_entity_type': 'hr'},
    {'name': 'Update employee records', 'description': 'Update BBBEE and EE compliance records', 'priority': 'low', 'due_date': today + timedelta(days=21), 'related_entity_type': 'hr'},
    {'name': 'Onboard new facilitator', 'description': 'Complete onboarding checklist for new facilitator joining 20 Jan', 'priority': 'high', 'due_date': today + timedelta(days=6), 'related_entity_type': 'hr'},
    
    # Assessment Tasks
    {'name': 'Mark assessments batch 2025-12', 'description': 'Complete marking for December 2025 assessment batch', 'priority': 'urgent', 'due_date': today + timedelta(days=1), 'related_entity_type': 'assessment'},
    {'name': 'Prepare external moderation pack', 'description': 'Prepare PoE samples for external moderation visit', 'priority': 'high', 'due_date': today + timedelta(days=10), 'related_entity_type': 'moderation'},
    {'name': 'Upload results to SETA portal', 'description': 'Upload learner results to SETA MIS portal', 'priority': 'high', 'due_date': today + timedelta(days=3), 'related_entity_type': 'certification'},
]

for task_data in tasks_data:
    task, created = Task.objects.update_or_create(
        name=task_data['name'],
        defaults={
            'description': task_data['description'],
            'priority': task_data['priority'],
            'due_date': task_data['due_date'],
            'status': 'pending',
            'assigned_to': admin_user,
            'related_entity_type': task_data['related_entity_type'],
            'created_by': admin_user,
            'updated_by': admin_user,
        }
    )

print(f"  Created/Updated {len(tasks_data)} sample tasks")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("WORKFLOW DATA CREATION COMPLETE")
print("=" * 60)
print(f"""
Summary:
  - Workflow Definitions: {WorkflowDefinition.objects.count()}
  - Process Flows: {ProcessFlow.objects.count()}
  - Process Stages: {ProcessStage.objects.count()}
  - Stage Transitions: {ProcessStageTransition.objects.count()}
  - Milestones: {Milestone.objects.count()}
  - Tasks: {Task.objects.count()}

You can view workflows in the admin at:
  - http://127.0.0.1:8000/admin/
""")
