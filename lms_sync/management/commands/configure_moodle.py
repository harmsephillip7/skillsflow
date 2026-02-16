"""
Management command to configure Moodle instance and test connection.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from lms_sync.models import MoodleInstance, MoodleCategory, MoodleCourse
from lms_sync.services.moodle_client import MoodleClient
from tenants.models import Brand


class Command(BaseCommand):
    help = 'Configure a Moodle LMS instance for syncing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='Moodle site URL (e.g., https://moodle.example.com)'
        )
        parser.add_argument(
            '--token',
            type=str,
            help='Moodle Web Services API token'
        )
        parser.add_argument(
            '--brand',
            type=str,
            help='Brand name or ID to associate with this Moodle instance'
        )
        parser.add_argument(
            '--test-only',
            action='store_true',
            help='Only test connection, do not save'
        )
        parser.add_argument(
            '--sync-courses',
            action='store_true',
            help='Sync courses and categories after configuration'
        )

    def handle(self, *args, **options):
        url = options.get('url') or 'https://ecampus.uxieducation.co.za'
        token = options.get('token') or 'e74af13c2aeb40062548f8b4ee5cccd5'
        brand_name = options.get('brand')
        test_only = options.get('test_only', False)
        sync_courses = options.get('sync_courses', False)

        # Clean URL
        url = url.rstrip('/')

        self.stdout.write(f"\nTesting connection to: {url}")
        self.stdout.write("-" * 60)

        # Create client and test connection
        client = MoodleClient(base_url=url, token=token)
        
        try:
            site_info = client.get_site_info()
        except Exception as e:
            raise CommandError(f"Failed to connect: {e}")

        if 'exception' in site_info:
            raise CommandError(f"Moodle API error: {site_info.get('message', 'Unknown error')}")

        # Display site info
        self.stdout.write(self.style.SUCCESS("\n✓ Connection successful!"))
        self.stdout.write(f"  Site Name: {site_info.get('sitename')}")
        self.stdout.write(f"  Version: {site_info.get('release')}")
        self.stdout.write(f"  User: {site_info.get('fullname')} ({site_info.get('username')})")
        
        functions = site_info.get('functions', [])
        self.stdout.write(f"  Available API Functions: {len(functions)}")

        if test_only:
            self.stdout.write("\n--test-only specified, not saving configuration.")
            return

        # Find or create brand
        if brand_name:
            try:
                if brand_name.isdigit():
                    brand = Brand.objects.get(pk=int(brand_name))
                else:
                    brand = Brand.objects.get(name__icontains=brand_name)
            except Brand.DoesNotExist:
                raise CommandError(f"Brand not found: {brand_name}")
        else:
            # Use first brand or create one
            brand = Brand.objects.first()
            if not brand:
                brand = Brand.objects.create(
                    name='UXI Education',
                    code='UXI',
                    is_active=True
                )
                self.stdout.write(f"\nCreated new brand: {brand.name}")

        # Create or update Moodle instance
        instance, created = MoodleInstance.objects.update_or_create(
            brand=brand,
            defaults={
                'name': site_info.get('sitename', 'Moodle'),
                'base_url': url,
                'ws_token': token,
                'sync_enabled': True,
                'auto_create_users': True,
                'auto_enroll': True,
                'sync_grades': True,
                'sync_completions': True,
                'is_active': True,
                'last_sync': timezone.now(),
                'last_sync_status': 'CONFIGURED',
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Created Moodle instance for {brand.name}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Updated Moodle instance for {brand.name}"))

        self.stdout.write(f"  Instance ID: {instance.pk}")
        self.stdout.write(f"  URL: {instance.base_url}")

        if sync_courses:
            self.stdout.write("\n" + "-" * 60)
            self.stdout.write("Syncing categories and courses...")
            self._sync_courses(instance, client)

    def _sync_courses(self, instance, client):
        """Sync categories and courses from Moodle."""
        # Sync categories
        self.stdout.write("\n1. Syncing categories...")
        categories = client.get_categories()
        
        if 'exception' in categories:
            self.stdout.write(self.style.ERROR(f"   Error: {categories.get('message')}"))
            return

        cat_count = 0
        for cat in categories:
            obj, created = MoodleCategory.objects.update_or_create(
                instance=instance,
                moodle_id=cat['id'],
                defaults={
                    'name': cat.get('name', 'Unknown'),
                    'parent_id': cat.get('parent') or None,
                }
            )
            cat_count += 1

        self.stdout.write(self.style.SUCCESS(f"   ✓ Synced {cat_count} categories"))

        # Sync courses
        self.stdout.write("\n2. Syncing courses...")
        courses = client.get_courses()
        
        if 'exception' in courses:
            self.stdout.write(self.style.ERROR(f"   Error: {courses.get('message')}"))
            return

        course_count = 0
        for course in courses:
            # Find matching category
            cat_id = course.get('categoryid')
            moodle_category = None
            if cat_id:
                moodle_category = MoodleCategory.objects.filter(
                    instance=instance,
                    moodle_id=cat_id
                ).first()

            obj, created = MoodleCourse.objects.update_or_create(
                instance=instance,
                moodle_id=course['id'],
                defaults={
                    'shortname': course.get('shortname', '')[:100],
                    'fullname': course.get('fullname', '')[:254],
                    'category': moodle_category,
                    'sync_enabled': True,
                }
            )
            course_count += 1

        self.stdout.write(self.style.SUCCESS(f"   ✓ Synced {course_count} courses"))

        # Update last sync time
        instance.last_sync = timezone.now()
        instance.last_sync_status = 'SUCCESS'
        instance.save()

        self.stdout.write(self.style.SUCCESS("\n✓ Moodle sync complete!"))
