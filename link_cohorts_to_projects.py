#!/usr/bin/env python
"""
Script to automatically link Cohorts to TrainingNotifications via NOTIntake records.
This will enable the projects view to show accurate learner counts.

Run with: python link_cohorts_to_projects.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Production database
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_ONKug26jTQIz@ep-quiet-wave-a8v9o984.eastus2.azure.neon.tech/neondb?sslmode=require'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.db import transaction
from core.models import TrainingNotification, NOTIntake
from logistics.models import Cohort
from academics.models import Enrollment


def analyze_data():
    """Analyze current state of data"""
    print("\n" + "="*60)
    print("DATA ANALYSIS")
    print("="*60)
    
    # Count cohorts
    total_cohorts = Cohort.objects.count()
    active_cohorts = Cohort.objects.filter(status__in=['ACTIVE', 'OPEN']).count()
    
    # Count cohorts already linked
    linked_cohort_ids = NOTIntake.objects.exclude(cohort__isnull=True).values_list('cohort_id', flat=True)
    unlinked_cohorts = Cohort.objects.exclude(id__in=linked_cohort_ids)
    
    print(f"\nCohorts:")
    print(f"  Total: {total_cohorts}")
    print(f"  Active: {active_cohorts}")
    print(f"  Already linked to projects: {len(linked_cohort_ids)}")
    print(f"  Unlinked: {unlinked_cohorts.count()}")
    
    # Count TrainingNotifications
    total_nots = TrainingNotification.objects.count()
    active_statuses = ['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'IN_PROGRESS', 'APPROVED', 'NOTIFICATIONS_SENT']
    active_nots = TrainingNotification.objects.filter(status__in=active_statuses).count()
    
    # Count NOTIntakes
    total_intakes = NOTIntake.objects.count()
    intakes_with_cohort = NOTIntake.objects.exclude(cohort__isnull=True).count()
    
    print(f"\nTrainingNotifications (Projects):")
    print(f"  Total: {total_nots}")
    print(f"  Active: {active_nots}")
    
    print(f"\nNOTIntakes:")
    print(f"  Total: {total_intakes}")
    print(f"  With cohort linked: {intakes_with_cohort}")
    print(f"  Without cohort: {total_intakes - intakes_with_cohort}")
    
    # Show unlinked cohorts with enrollments
    print(f"\nUnlinked Cohorts with Active Learners:")
    for cohort in unlinked_cohorts[:10]:
        enrollment_count = Enrollment.objects.filter(cohort=cohort, status__in=['ACTIVE', 'ENROLLED']).count()
        if enrollment_count > 0:
            print(f"  {cohort.code} - {cohort.name}: {enrollment_count} learners")
    
    return unlinked_cohorts


def get_matching_strategy():
    """Determine the best strategy to link cohorts to projects"""
    print("\n" + "="*60)
    print("MATCHING STRATEGY")
    print("="*60)
    
    # Check if we have any TrainingNotifications
    nots = TrainingNotification.objects.all()
    cohorts = Cohort.objects.all()
    
    if not nots.exists():
        print("No TrainingNotifications found. Will create projects from cohorts.")
        return 'create_from_cohorts'
    
    if not cohorts.exists():
        print("No Cohorts found. Nothing to link.")
        return 'nothing_to_do'
    
    # Try to find matching patterns
    # Strategy 1: Match by qualification and client
    print("\nChecking for matching patterns...")
    
    # Strategy 2: Each cohort becomes a project
    print("Strategy: Create NOTIntake for each cohort, linked to closest matching project")
    return 'match_or_create'


def link_cohorts_to_projects(dry_run=True):
    """
    Link unlinked cohorts to TrainingNotifications.
    
    Strategy:
    1. For each unlinked cohort, find the best matching TrainingNotification:
       - Same corporate client
       - Same qualification
       - Overlapping date range
    2. If no match found, create a new TrainingNotification for the cohort
    3. Create NOTIntake to link them
    """
    from django.db.models.signals import post_save
    from core.task_signals import auto_create_cohort_implementation_plan
    
    print("\n" + "="*60)
    print("LINKING COHORTS TO PROJECTS")
    print("="*60)
    
    if dry_run:
        print("\n*** DRY RUN - No changes will be made ***\n")
    
    # Temporarily disconnect signals that might cause issues
    post_save.disconnect(auto_create_cohort_implementation_plan, sender=NOTIntake)
    
    try:
        # Get unlinked cohorts
        linked_cohort_ids = NOTIntake.objects.exclude(cohort__isnull=True).values_list('cohort_id', flat=True)
        unlinked_cohorts = Cohort.objects.exclude(id__in=linked_cohort_ids)
        
        if not unlinked_cohorts.exists():
            print("All cohorts are already linked to projects!")
            return
        
        # Get active TrainingNotifications
        active_statuses = ['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'IN_PROGRESS', 'APPROVED', 'NOTIFICATIONS_SENT']
        active_nots = list(TrainingNotification.objects.filter(status__in=active_statuses))
        
        links_created = 0
        projects_created = 0
        
        with transaction.atomic():
            for cohort in unlinked_cohorts:
                best_match = None
                best_score = 0
                
                # Find best matching TrainingNotification
                for not_project in active_nots:
                    score = 0
                    
                    # Match by date overlap
                    if not_project.planned_start_date and cohort.start_date:
                        # Same year and month is good
                        if (not_project.planned_start_date.year == cohort.start_date.year and
                            not_project.planned_start_date.month == cohort.start_date.month):
                            score += 3
                        elif not_project.planned_start_date.year == cohort.start_date.year:
                            score += 1
                    
                    # Match by qualification keyword in title
                    if cohort.qualification and not_project.title:
                        qual_name = cohort.qualification.title.lower()
                        not_title = not_project.title.lower()
                        # Check if any significant word matches
                        qual_words = [w for w in qual_name.split() if len(w) > 3]
                        for word in qual_words:
                            if word in not_title:
                                score += 2
                                break
                    
                    # Match by campus
                    if hasattr(cohort, 'campus') and cohort.campus and not_project.delivery_campus:
                        if cohort.campus == not_project.delivery_campus:
                            score += 2
                    
                    if score > best_score:
                        best_score = score
                        best_match = not_project
                
                enrollment_count = Enrollment.objects.filter(cohort=cohort, status__in=['ACTIVE', 'ENROLLED']).count()
                
                if best_match and best_score >= 2:
                    # Good match found - create NOTIntake
                    print(f"\nLinking: {cohort.code} -> {best_match.reference_number} ({best_match.title})")
                    print(f"  Score: {best_score}, Learners: {enrollment_count}")
                    
                    if not dry_run:
                        # Get next intake number
                        existing_intakes = NOTIntake.objects.filter(training_notification=best_match).count()
                        
                        NOTIntake.objects.create(
                            training_notification=best_match,
                            cohort=cohort,
                            intake_number=existing_intakes + 1,
                            name=cohort.name,
                            original_cohort_size=enrollment_count,
                            status='ACTIVE' if cohort.status in ['ACTIVE', 'OPEN'] else 'PLANNED',
                            intake_date=cohort.start_date
                        )
                    links_created += 1
                    
                else:
                    # No good match - create new TrainingNotification
                    print(f"\nNo match for: {cohort.code} - {cohort.name}")
                    print(f"  Creating new project, Learners: {enrollment_count}")
                    
                    if not dry_run:
                        # Create new TrainingNotification
                        new_not = TrainingNotification.objects.create(
                            title=f"{cohort.qualification.title if cohort.qualification else cohort.name}",
                            project_type='SKILLS_PROGRAMME',  # Default
                            status='IN_PROGRESS',
                            planned_start_date=cohort.start_date,
                            planned_end_date=cohort.end_date,
                            delivery_campus=getattr(cohort, 'campus', None),
                            target_learners=enrollment_count,
                        )
                        
                        # Create NOTIntake
                        NOTIntake.objects.create(
                            training_notification=new_not,
                            cohort=cohort,
                            intake_number=1,
                            name=cohort.name,
                            original_cohort_size=enrollment_count,
                            status='ACTIVE' if cohort.status in ['ACTIVE', 'OPEN'] else 'PLANNED',
                            intake_date=cohort.start_date
                        )
                        
                        # Add to active_nots for future matching
                        active_nots.append(new_not)
                        projects_created += 1
                    
                    links_created += 1
            
            if dry_run:
                print("\n*** DRY RUN COMPLETE - Rolling back ***")
                transaction.set_rollback(True)
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Cohorts processed: {unlinked_cohorts.count()}")
        print(f"Links {'would be' if dry_run else ''} created: {links_created}")
        print(f"New projects {'would be' if dry_run else ''} created: {projects_created}")
    
    finally:
        # Reconnect signal
        post_save.connect(auto_create_cohort_implementation_plan, sender=NOTIntake)


def simple_link_all():
    """
    Simpler approach: Link ALL unlinked cohorts to the first available project,
    or create intakes for each in a single project.
    """
    print("\n" + "="*60)
    print("SIMPLE LINKING - All cohorts to available projects")
    print("="*60)
    
    # Get unlinked cohorts with enrollments
    linked_cohort_ids = NOTIntake.objects.exclude(cohort__isnull=True).values_list('cohort_id', flat=True)
    unlinked_cohorts = Cohort.objects.exclude(id__in=linked_cohort_ids).order_by('start_date')
    
    # Get active TrainingNotifications
    active_statuses = ['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'IN_PROGRESS', 'APPROVED', 'NOTIFICATIONS_SENT']
    active_nots = list(TrainingNotification.objects.filter(status__in=active_statuses))
    
    print(f"\nUnlinked cohorts: {unlinked_cohorts.count()}")
    print(f"Available projects: {len(active_nots)}")
    
    if not active_nots:
        print("\nNo projects available to link to!")
        return
    
    with transaction.atomic():
        # Distribute cohorts across projects
        for i, cohort in enumerate(unlinked_cohorts):
            # Round-robin assignment to projects
            project = active_nots[i % len(active_nots)]
            
            enrollment_count = Enrollment.objects.filter(cohort=cohort, status__in=['ACTIVE', 'ENROLLED']).count()
            
            # Get next intake number for this project
            existing_intakes = NOTIntake.objects.filter(training_notification=project).count()
            
            print(f"Linking: {cohort.code} ({enrollment_count} learners) -> {project.reference_number}")
            
            NOTIntake.objects.create(
                training_notification=project,
                cohort=cohort,
                intake_number=existing_intakes + 1,
                name=cohort.name or f"Cohort {cohort.code}",
                original_cohort_size=enrollment_count,
                status='ACTIVE' if cohort.status in ['ACTIVE', 'OPEN'] else 'PLANNED',
                intake_date=cohort.start_date
            )
    
    print("\n✓ All cohorts linked successfully!")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Link cohorts to projects')
    parser.add_argument('--execute', action='store_true', help='Execute smart linking without prompts')
    parser.add_argument('--simple', action='store_true', help='Execute simple linking (distribute evenly)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes only')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("COHORT TO PROJECT LINKING SCRIPT")
    print("="*60)
    
    # First, analyze the data
    unlinked = analyze_data()
    
    if not unlinked.exists():
        print("\n✓ All cohorts are already linked!")
        sys.exit(0)
    
    # Handle command-line arguments
    if args.dry_run:
        link_cohorts_to_projects(dry_run=True)
    elif args.execute:
        link_cohorts_to_projects(dry_run=False)
        print("\n✓ Linking complete!")
    elif args.simple:
        simple_link_all()
    else:
        # Interactive mode
        print("\n" + "-"*60)
        choice = input("\nOptions:\n  1. Dry run (preview changes)\n  2. Execute smart linking\n  3. Execute simple linking (distribute evenly)\n  4. Exit\n\nChoice [1-4]: ").strip()
        
        if choice == '1':
            link_cohorts_to_projects(dry_run=True)
        elif choice == '2':
            confirm = input("\nThis will modify the production database. Continue? (yes/no): ").strip().lower()
            if confirm == 'yes':
                link_cohorts_to_projects(dry_run=False)
                print("\n✓ Linking complete!")
            else:
                print("Cancelled.")
        elif choice == '3':
            confirm = input("\nThis will distribute cohorts evenly across projects. Continue? (yes/no): ").strip().lower()
            if confirm == 'yes':
                simple_link_all()
            else:
                print("Cancelled.")
        else:
            print("Exiting.")
