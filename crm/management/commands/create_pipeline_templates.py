from django.core.management.base import BaseCommand
from crm.models import Pipeline, PipelineStage
from tenants.models import Campus


class Command(BaseCommand):
    help = 'Create pipeline templates for production'

    def handle(self, *args, **options):
        # Get Head Office campus
        campus = Campus.objects.get(id=30)
        
        self.stdout.write("Creating Pipeline Templates...")
        self.stdout.write("=" * 60)
        
        # Pipeline 1: Grade 9 Future Learner
        p1, created = Pipeline.objects.get_or_create(
            campus=campus,
            name="Grade 9 Future Learner Journey",
            defaults={
                'description': "Long-term nurturing pipeline for Grade 9 learners.",
                'learner_type': 'SCHOOL_LEAVER_FUTURE',
                'default_communication_frequency_days': 90,
                'is_default': True,
                'is_active': True,
                'color': '#8B5CF6',
                'icon': 'fa-seedling'
            }
        )
        
        if created or p1.stages.count() < 8:
            existing = list(p1.stages.values_list('code', flat=True))
            stages = [
                {'name': 'New Inquiry', 'code': 'NEW', 'order': 1, 'is_entry_stage': True, 'color': '#6366F1', 'win_probability': 5},
                {'name': 'Career Discovery', 'code': 'CAREER_DISCOVERY', 'order': 2, 'communication_frequency_days': 30, 'color': '#8B5CF6', 'win_probability': 10},
                {'name': 'Subject Guidance', 'code': 'SUBJECT_GUIDANCE', 'order': 3, 'communication_frequency_days': 30, 'color': '#A855F7', 'win_probability': 15},
                {'name': 'Grade 10 Nurture', 'code': 'GR10_NURTURE', 'order': 4, 'communication_frequency_days': 90, 'is_nurture_stage': True, 'color': '#7C3AED', 'win_probability': 20},
                {'name': 'Grade 11 Nurture', 'code': 'GR11_NURTURE', 'order': 5, 'communication_frequency_days': 60, 'is_nurture_stage': True, 'color': '#6D28D9', 'win_probability': 35},
                {'name': 'Ready to Convert', 'code': 'READY_CONVERT', 'order': 6, 'communication_frequency_days': 14, 'color': '#10B981', 'win_probability': 50},
                {'name': 'Converted', 'code': 'WON', 'order': 7, 'is_won_stage': True, 'color': '#059669', 'win_probability': 100},
                {'name': 'Not Interested', 'code': 'LOST', 'order': 8, 'is_lost_stage': True, 'color': '#EF4444', 'win_probability': 0},
            ]
            for s in stages:
                if s['code'] not in existing:
                    PipelineStage.objects.create(pipeline=p1, **s)
            self.stdout.write(f"  Grade 9 Pipeline: {p1.stages.count()} stages")
        
        # Pipeline 2: Grade 12 Ready Now
        p2, created = Pipeline.objects.get_or_create(
            campus=campus,
            name="Grade 12 Ready Now",
            defaults={
                'description': "Active enrollment pipeline for Grade 12 learners.",
                'learner_type': 'SCHOOL_LEAVER_READY',
                'default_communication_frequency_days': 7,
                'is_default': True,
                'is_active': True,
                'color': '#3B82F6',
                'icon': 'fa-graduation-cap'
            }
        )
        
        if created or p2.stages.count() < 10:
            existing = list(p2.stages.values_list('code', flat=True))
            stages = [
                {'name': 'New Lead', 'code': 'NEW', 'order': 1, 'is_entry_stage': True, 'color': '#60A5FA', 'win_probability': 10},
                {'name': 'First Contact', 'code': 'CONTACTED', 'order': 2, 'communication_frequency_days': 3, 'color': '#3B82F6', 'win_probability': 20},
                {'name': 'Career Assessment', 'code': 'ASSESSMENT', 'order': 3, 'communication_frequency_days': 7, 'color': '#2563EB', 'win_probability': 35},
                {'name': 'Programme Selection', 'code': 'PROGRAMME_SELECT', 'order': 4, 'communication_frequency_days': 5, 'color': '#1D4ED8', 'win_probability': 50},
                {'name': 'Quote/Proposal', 'code': 'PROPOSAL', 'order': 5, 'communication_frequency_days': 3, 'color': '#1E40AF', 'win_probability': 65},
                {'name': 'Decision Pending', 'code': 'DECISION', 'order': 6, 'communication_frequency_days': 2, 'color': '#F59E0B', 'win_probability': 75},
                {'name': 'Application Started', 'code': 'APPLICATION', 'order': 7, 'communication_frequency_days': 2, 'color': '#10B981', 'win_probability': 90},
                {'name': 'Enrolled', 'code': 'WON', 'order': 8, 'is_won_stage': True, 'color': '#059669', 'win_probability': 100},
                {'name': 'Lost - Other Institution', 'code': 'LOST_COMPETITOR', 'order': 9, 'is_lost_stage': True, 'color': '#EF4444', 'win_probability': 0},
                {'name': 'Lost - Postponed', 'code': 'LOST_POSTPONED', 'order': 10, 'is_lost_stage': True, 'color': '#F97316', 'win_probability': 0},
            ]
            for s in stages:
                if s['code'] not in existing:
                    PipelineStage.objects.create(pipeline=p2, **s)
            self.stdout.write(f"  Grade 12 Pipeline: {p2.stages.count()} stages")
        
        # Pipeline 3: Adult Career Starter
        p3, created = Pipeline.objects.get_or_create(
            campus=campus,
            name="Adult Career Starter",
            defaults={
                'description': "Pipeline for adults and gap year students ready to start their career journey.",
                'learner_type': 'ADULT',
                'default_communication_frequency_days': 7,
                'is_default': True,
                'is_active': True,
                'color': '#10B981',
                'icon': 'fa-briefcase'
            }
        )
        
        if created or p3.stages.count() < 11:
            existing = list(p3.stages.values_list('code', flat=True))
            stages = [
                {'name': 'New Inquiry', 'code': 'NEW', 'order': 1, 'is_entry_stage': True, 'color': '#34D399', 'win_probability': 10},
                {'name': 'Initial Consultation', 'code': 'CONSULTATION', 'order': 2, 'communication_frequency_days': 5, 'color': '#10B981', 'win_probability': 20},
                {'name': 'Skills Assessment', 'code': 'SKILLS_ASSESS', 'order': 3, 'communication_frequency_days': 7, 'color': '#059669', 'win_probability': 30},
                {'name': 'Career Pathway', 'code': 'CAREER_PATH', 'order': 4, 'communication_frequency_days': 5, 'color': '#047857', 'win_probability': 45},
                {'name': 'Funding Exploration', 'code': 'FUNDING', 'order': 5, 'communication_frequency_days': 5, 'color': '#065F46', 'win_probability': 55},
                {'name': 'Proposal Sent', 'code': 'PROPOSAL', 'order': 6, 'communication_frequency_days': 3, 'color': '#3B82F6', 'win_probability': 70},
                {'name': 'Negotiation', 'code': 'NEGOTIATION', 'order': 7, 'communication_frequency_days': 2, 'color': '#F59E0B', 'win_probability': 80},
                {'name': 'Enrollment Processing', 'code': 'ENROLLMENT', 'order': 8, 'communication_frequency_days': 2, 'color': '#8B5CF6', 'win_probability': 95},
                {'name': 'Enrolled', 'code': 'WON', 'order': 9, 'is_won_stage': True, 'color': '#059669', 'win_probability': 100},
                {'name': 'Lost - Timing', 'code': 'LOST_TIMING', 'order': 10, 'is_lost_stage': True, 'color': '#F97316', 'win_probability': 0},
                {'name': 'Lost - Competitor', 'code': 'LOST_COMPETITOR', 'order': 11, 'is_lost_stage': True, 'color': '#EF4444', 'win_probability': 0},
            ]
            for s in stages:
                if s['code'] not in existing:
                    PipelineStage.objects.create(pipeline=p3, **s)
            self.stdout.write(f"  Adult Pipeline: {p3.stages.count()} stages")
        
        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 60)
        for p in Pipeline.objects.filter(campus=campus):
            self.stdout.write(f"\n{p.name}")
            self.stdout.write(f"  Type: {p.get_learner_type_display()}")
            self.stdout.write(f"  Stages: {p.stages.count()}")
            for s in p.stages.all():
                marker = ""
                if s.is_entry_stage: marker = " [ENTRY]"
                elif s.is_won_stage: marker = " [WON]"
                elif s.is_lost_stage: marker = " [LOST]"
                elif s.is_nurture_stage: marker = " [NURTURE]"
                self.stdout.write(f"    {s.order}. {s.name}{marker}")
        
        self.stdout.write(self.style.SUCCESS("\nPipeline templates created successfully!"))
