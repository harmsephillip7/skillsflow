"""
Management command to create standard tranche templates for different project types.
These templates define the payment milestones and evidence requirements.
"""
from django.core.management.base import BaseCommand
from core.models import TrancheTemplate, TrancheTemplateItem


class Command(BaseCommand):
    help = 'Creates standard tranche templates for all project types'

    def handle(self, *args, **options):
        created_templates = 0
        created_items = 0
        
        # Define templates for each project type and funder combination
        templates_data = [
            # SETA-funded Apprenticeship (3 years / 36 months)
            {
                'name': 'Standard SETA Apprenticeship',
                'project_type': 'APPRENTICESHIP',
                'funder_type': 'CORPORATE_DG',
                'description': 'Standard 3-year apprenticeship with 9 tranches for SETA discretionary grants',
                'duration_months': 36,
                'total_tranches': 9,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 10},
                    {'sequence': 2, 'type': 'RECRUITMENT', 'name': 'Tranche 2 - Learner Recruitment', 'months': 1, 'percentage': 10},
                    {'sequence': 3, 'type': 'REGISTRATION', 'name': 'Tranche 3 - SETA Registration', 'months': 2, 'percentage': 10},
                    {'sequence': 4, 'type': 'PPE_TOOLBOX', 'name': 'Tranche 4 - PPE & Toolbox Issuance', 'months': 3, 'percentage': 10},
                    {'sequence': 5, 'type': 'ASSESSMENT_1', 'name': 'Tranche 5 - Assessment Cycle 1', 'months': 12, 'percentage': 15},
                    {'sequence': 6, 'type': 'ASSESSMENT_2', 'name': 'Tranche 6 - Assessment Cycle 2', 'months': 24, 'percentage': 15},
                    {'sequence': 7, 'type': 'TRADE_TEST', 'name': 'Tranche 7 - Trade Test', 'months': 34, 'percentage': 10},
                    {'sequence': 8, 'type': 'CERTIFICATION', 'name': 'Tranche 8 - Certification', 'months': 35, 'percentage': 10},
                    {'sequence': 9, 'type': 'FINAL', 'name': 'Tranche 9 - Final Claim', 'months': 36, 'percentage': 10},
                ],
            },
            # Private-funded Apprenticeship
            {
                'name': 'Private Apprenticeship',
                'project_type': 'APPRENTICESHIP',
                'funder_type': 'PRIVATE',
                'description': 'Private-funded apprenticeship with simplified 5 tranches',
                'duration_months': 36,
                'total_tranches': 5,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 20},
                    {'sequence': 2, 'type': 'REGISTRATION', 'name': 'Tranche 2 - Registration', 'months': 2, 'percentage': 20},
                    {'sequence': 3, 'type': 'ASSESSMENT_1', 'name': 'Tranche 3 - Mid-term Assessment', 'months': 18, 'percentage': 20},
                    {'sequence': 4, 'type': 'TRADE_TEST', 'name': 'Tranche 4 - Trade Test', 'months': 34, 'percentage': 20},
                    {'sequence': 5, 'type': 'FINAL', 'name': 'Tranche 5 - Completion', 'months': 36, 'percentage': 20},
                ],
            },
            # SETA-funded Learnership (12 months)
            {
                'name': 'Standard SETA Learnership',
                'project_type': 'LEARNERSHIP',
                'funder_type': 'CORPORATE_DG',
                'description': 'Standard 12-month learnership with 6 tranches for SETA discretionary grants',
                'duration_months': 12,
                'total_tranches': 6,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 15},
                    {'sequence': 2, 'type': 'RECRUITMENT', 'name': 'Tranche 2 - Learner Recruitment', 'months': 1, 'percentage': 15},
                    {'sequence': 3, 'type': 'REGISTRATION', 'name': 'Tranche 3 - SETA Registration', 'months': 2, 'percentage': 15},
                    {'sequence': 4, 'type': 'ASSESSMENT_1', 'name': 'Tranche 4 - Mid-term Assessment', 'months': 6, 'percentage': 20},
                    {'sequence': 5, 'type': 'MODERATION', 'name': 'Tranche 5 - Moderation', 'months': 10, 'percentage': 15},
                    {'sequence': 6, 'type': 'CERTIFICATION', 'name': 'Tranche 6 - Certification & Completion', 'months': 12, 'percentage': 20},
                ],
            },
            # Skills Programme (3-6 months)
            {
                'name': 'Standard Skills Programme',
                'project_type': 'SKILLS_PROGRAM',
                'funder_type': 'CORPORATE_DG',
                'description': 'Short skills programme with 4 tranches',
                'duration_months': 6,
                'total_tranches': 4,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 25},
                    {'sequence': 2, 'type': 'REGISTRATION', 'name': 'Tranche 2 - Registration', 'months': 1, 'percentage': 25},
                    {'sequence': 3, 'type': 'ASSESSMENT_1', 'name': 'Tranche 3 - Assessment', 'months': 4, 'percentage': 25},
                    {'sequence': 4, 'type': 'CERTIFICATION', 'name': 'Tranche 4 - Certification', 'months': 6, 'percentage': 25},
                ],
            },
            # Internship (12 months)
            {
                'name': 'Standard Internship',
                'project_type': 'INTERNSHIP',
                'funder_type': 'CORPORATE_DG',
                'description': 'Standard 12-month internship with 4 tranches',
                'duration_months': 12,
                'total_tranches': 4,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 25},
                    {'sequence': 2, 'type': 'PLACEMENT', 'name': 'Tranche 2 - Workplace Placement', 'months': 1, 'percentage': 25},
                    {'sequence': 3, 'type': 'INTERIM', 'name': 'Tranche 3 - Mid-term Review', 'months': 6, 'percentage': 25},
                    {'sequence': 4, 'type': 'COMPLETION', 'name': 'Tranche 4 - Programme Completion', 'months': 12, 'percentage': 25},
                ],
            },
            # Work Experience (WIL) - 12 months
            {
                'name': 'Standard WIL Programme',
                'project_type': 'WIL',
                'funder_type': 'CORPORATE_DG',
                'description': 'Work Integrated Learning programme with 4 tranches',
                'duration_months': 12,
                'total_tranches': 4,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 25},
                    {'sequence': 2, 'type': 'PLACEMENT', 'name': 'Tranche 2 - Workplace Placement', 'months': 1, 'percentage': 25},
                    {'sequence': 3, 'type': 'INTERIM', 'name': 'Tranche 3 - Mid-term Assessment', 'months': 6, 'percentage': 25},
                    {'sequence': 4, 'type': 'COMPLETION', 'name': 'Tranche 4 - Completion', 'months': 12, 'percentage': 25},
                ],
            },
            # Bursary (12 months)
            {
                'name': 'Standard Bursary Programme',
                'project_type': 'BURSARY',
                'funder_type': 'CORPORATE_DG',
                'description': 'Bursary programme with 3 tranches',
                'duration_months': 12,
                'total_tranches': 3,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 33},
                    {'sequence': 2, 'type': 'INTERIM', 'name': 'Tranche 2 - Mid-year', 'months': 6, 'percentage': 34},
                    {'sequence': 3, 'type': 'COMPLETION', 'name': 'Tranche 3 - Year End', 'months': 12, 'percentage': 33},
                ],
            },
            # Candidacy Programme (18 months)
            {
                'name': 'Standard Candidacy Programme',
                'project_type': 'CANDIDACY',
                'funder_type': 'CORPORATE_DG',
                'description': 'Candidacy programme with 5 tranches',
                'duration_months': 18,
                'total_tranches': 5,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 20},
                    {'sequence': 2, 'type': 'PLACEMENT', 'name': 'Tranche 2 - Workplace Placement', 'months': 2, 'percentage': 20},
                    {'sequence': 3, 'type': 'INTERIM', 'name': 'Tranche 3 - Mid-term Review', 'months': 9, 'percentage': 20},
                    {'sequence': 4, 'type': 'ASSESSMENT_1', 'name': 'Tranche 4 - Final Assessment', 'months': 16, 'percentage': 20},
                    {'sequence': 5, 'type': 'CERTIFICATION', 'name': 'Tranche 5 - Certification', 'months': 18, 'percentage': 20},
                ],
            },
            # Short Course (1-3 months)
            {
                'name': 'Standard Short Course',
                'project_type': 'SHORT_COURSE',
                'funder_type': 'PRIVATE',
                'description': 'Short course with 2 simple tranches',
                'duration_months': 3,
                'total_tranches': 2,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 50},
                    {'sequence': 2, 'type': 'COMPLETION', 'name': 'Tranche 2 - Completion', 'months': 3, 'percentage': 50},
                ],
            },
            # Occupational Certificate (36 months)
            {
                'name': 'Standard OC Programme',
                'project_type': 'OC',
                'funder_type': 'CORPORATE_DG',
                'description': 'Occupational Certificate programme with 9 tranches',
                'duration_months': 36,
                'total_tranches': 9,
                'items': [
                    {'sequence': 1, 'type': 'COMMENCEMENT', 'name': 'Tranche 1 - Commencement', 'months': 0, 'percentage': 10},
                    {'sequence': 2, 'type': 'RECRUITMENT', 'name': 'Tranche 2 - Learner Recruitment', 'months': 1, 'percentage': 10},
                    {'sequence': 3, 'type': 'REGISTRATION', 'name': 'Tranche 3 - QCTO Registration', 'months': 2, 'percentage': 10},
                    {'sequence': 4, 'type': 'LEARNING_MATERIAL', 'name': 'Tranche 4 - Material Issuance', 'months': 3, 'percentage': 10},
                    {'sequence': 5, 'type': 'ASSESSMENT_1', 'name': 'Tranche 5 - Knowledge Module Assessment', 'months': 12, 'percentage': 15},
                    {'sequence': 6, 'type': 'ASSESSMENT_2', 'name': 'Tranche 6 - Practical Module Assessment', 'months': 24, 'percentage': 15},
                    {'sequence': 7, 'type': 'ASSESSMENT_3', 'name': 'Tranche 7 - Work Experience Module', 'months': 30, 'percentage': 10},
                    {'sequence': 8, 'type': 'TRADE_TEST', 'name': 'Tranche 8 - External Integrated Summative Assessment', 'months': 34, 'percentage': 10},
                    {'sequence': 9, 'type': 'CERTIFICATION', 'name': 'Tranche 9 - Certification', 'months': 36, 'percentage': 10},
                ],
            },
        ]
        
        for template_data in templates_data:
            # Create or update template
            template, created = TrancheTemplate.objects.update_or_create(
                project_type=template_data['project_type'],
                funder_type=template_data['funder_type'],
                name=template_data['name'],
                defaults={
                    'description': template_data['description'],
                    'duration_months': template_data['duration_months'],
                    'total_tranches': template_data['total_tranches'],
                    'is_active': True,
                }
            )
            
            if created:
                created_templates += 1
                self.stdout.write(self.style.SUCCESS(f'  ✅ Created template: {template.name}'))
            else:
                self.stdout.write(f'  ℹ️  Updated template: {template.name}')
            
            # Create tranche items
            for item_data in template_data['items']:
                item, item_created = TrancheTemplateItem.objects.update_or_create(
                    template=template,
                    sequence_number=item_data['sequence'],
                    defaults={
                        'tranche_type': item_data['type'],
                        'name': item_data['name'],
                        'months_from_start': item_data['months'],
                        'percentage_of_total': item_data['percentage'],
                        'days_before_deadline_reminder': 14,
                    }
                )
                
                if item_created:
                    created_items += 1
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✨ Tranche Templates Complete!'))
        self.stdout.write(f'   Templates created: {created_templates}')
        self.stdout.write(f'   Tranche items created: {created_items}')
        self.stdout.write(f'   Total templates: {TrancheTemplate.objects.count()}')
        self.stdout.write(f'   Total items: {TrancheTemplateItem.objects.count()}')
