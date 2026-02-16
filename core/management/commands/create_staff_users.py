"""
Management command to create staff users from provided data.
Creates User accounts with optional role assignments.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import User


# Staff data extracted from provided list
STAFF_DATA = [
    # Name, Email, Role/Title (if specified)
    ("Elsie Harmse", "elsie@uxi-ad.co.za", ""),
    ("Stefan Hattingh", "stefan@ietisa.co.za", ""),
    ("Phillip Harmse", "phillip@uxi-ad.co.za", ""),
    ("Jacomine Groenewald", "finance@uxi-ad.co.za", "Finance"),
    ("Gerda Rappard", "gerda@uxi-ad.co.za", "Executive PA - Elsie"),
    ("Ju-Ané Rossouw", "j.rossouw@uxi-ad.co.za", "Executive PA - Phillip"),
    ("Cynthia Fose", "reception-headoffice@uxi-ad.co.za", "Reception"),
    ("Kimberley Rowan", "education@uxi-ad.co.za", "Executive"),
    ("Sean Fenn", "sean@uxi-ad.co.za", "Learning Resource Manager"),
    ("Willy Matthiae", "operations@africaskills.co.za", "Faculty Manager"),
    ("Sylvia Rasmeni", "sylvia@uxi-ad.co.za", "ETQA Practitioner"),
    ("Anita Botha", "anita.botha@uxi-ad.co.za", "Instructional Designer"),
    ("Algene Esterhuizen", "algene@uxi-ad.co.za", "Accreditation Officer"),
    ("Anita Ngabase", "anita@uxi-ad.co.za", "Accreditation Officer"),
    ("Sandiswa Dyani", "blueprint1@uxi-ad.co.za", "Printing"),
    ("Grant Botha", "itsupport@uxi-ad.co.za", "IT Support - UXi Online"),
    ("Thabani Ngcobo", "itdev1@uxi-ad.co.za", "IT Dev - UXi Online"),
    ("Chris Mutombo", "itdev@uxi-ad.co.za", "IT Dev - UXi Online"),
    ("Gunther Kietzmann", "gunther@africaskills.co.za", "Faculty Manager - Civil"),
    ("Sandra Ncube", "admin1@uxi-ad.co.za", "Executive Admin"),
    ("Samantha Maralack", "registrar1@uxi-ad.co.za", "Registrar"),
    ("Brenda Bokwe", "tradetest1@uxi-ad.co.za", "EISA"),
    ("Anyé Strauss", "anye@uxi-ad.co.za", "UXi Connect"),
    ("Gerhard Olivier", "gerhard@uxi-ad.co.za", "SaM Manager"),
    ("Janke Page", "janke@uxi-ad.co.za", "Legal & Employer Compliance"),
    ("Rudi Cooke", "rudi@uxi-ad.co.za", "Business Development Coordinator"),
    ("Marnus Du Toit", "marnus@africaskills.co.za", "Southern Region Schools Marketing Officer"),
    ("Jacques Gombault", "jacques@africaskills.co.za", "Northern Region Schools Marketing Officer"),
    ("Megan Firth", "mfirth@uxi-ad.co.za", "Marketing Specialist"),
    ("Jan Greyling", "jan@uxi-ad.co.za", "Media Lead"),
    ("Magda Pretorius", "magda@uxi-ad.co.za", "Learners & Events"),
    ("Thomas Boucher", "thomas@uxi-ad.co.za", "Corporate Sales"),
    ("Lizelle Pienaar", "lizellep@uxi-ad.co.za", "Key Account Manager"),
    ("Graham McFarlane", "kam@uxi-ad.co.za", "Key Account Manager"),
    ("Erika Ackermann", "finance10@uxi-ad.co.za", "Group Accounting Manager"),
    ("Ilonka van der Merwe", "finance1@uxi-ad.co.za", "Financial Manager"),
    ("Simone Odendal", "finance12@uxi-ad.co.za", "Financial Manager"),
    ("Joslyn Johannes", "payrolladministrator@uxi-ad.co.za", "Payroll Administrator"),
    ("Albert van Zyl", "hrmanager@uxi-ad.co.za", "HR Manager"),
    ("Tonelle Alberts", "hradmin@uxi-ad.co.za", "HR Admin"),
    ("Philip Harmse", "quality@uxi-ad.co.za", "Quality"),
    ("Jeanette Botha", "qms@uxi-ad.co.za", "QMS"),
    ("Elmerie van Rooyen", "elmerie@uxi-ad.co.za", ""),
    ("Dillon Crozett", "it@uxi-ad.co.za", "IT"),
    ("Ricardo Rautenbach", "ricardo@uxi-ad.co.za", ""),
    ("Morne Smith", "morne@uxi-ad.co.za", ""),
    ("Alex Engelke", "alex@uxi-ad.co.za", ""),
    ("Anyé Strauss", "anye@uxi-ad.co.za", ""),
    ("Cwayita Fadana", "projectadmin1@africaskills.co.za", "Project Admin"),
    ("Bulelwa Mahe", "projectadmin2@africaskills.co.za", "Project Admin"),
    ("Novadia Solomons", "projectadmin3@africaskills.co.za", "Project Admin"),
    ("Kimber Jafta", "kimber@africaskills.co.za", ""),
    ("Unathi Sesman", "admin.assist3@africaskills.co.za", "Admin Assistant"),
    ("Olothando September", "admin.intern@africaskills.co.za", "Admin Intern"),
    ("Princess Madubedube", "assc.stipends@africaskills.co.za", "Stipends Associate"),
    ("Laetitia Puren", "admin3@africaskills.co.za", "Admin"),
    ("Nondumiso Masimini", "assc.workplace@africaskills.co.za", "Workplace Associate"),
    ("Leandre Swartz", "wp5@africaskills.co.za", "Workplace"),
    ("Johanelle Kotze", "sales.admin@uxi-ad.co.za", "Sales Admin"),
    ("Jo-Mary Scholtz", "finance5@uxi-ad.co.za", "Finance"),
    ("Roan Marshall", "finance11@uxi-ad.co.za", "Finance"),
    ("Rowelia Titus", "finance8@uxi-ad.co.za", "Finance"),
    ("Geraldine Maka", "finance9@africaskills.co.za", "Finance"),
    ("Josua Visser", "salesandmarketing1@africaskills.co.za", "Sales & Marketing"),
    ("Lindiwe Jack", "reception.georgetech@africaskills.co.za", "Reception - GeorgeTech"),
    ("Lubabalo Nopondo", "lubabalon@africaskills.co.za", ""),
    ("Mikayla Arries", "mikayla.arries@africaskills.co.za", ""),
    ("Danie de Beer", "sm.georgetech@africaskills.co.za", "Site Manager - GeorgeTech"),
    ("Allister Alexander", "allister@africaskills.co.za", "Electrical"),
    ("Rohan Vermaak", "rohan@africaskills.co.za", "Electrical / Solar PV"),
    ("Hylton Jantjies", "electrical2@africaskills.co.za", "Electrical"),
    ("Seipati Mokhoaetsane", "seipati@africaskills.co.za", "Electrical"),
    ("Kabelo Puoeng", "kabelo@africaskills.co.za", "Electrical / Electronics"),
    ("Charl Grobbelaar", "mechanicalfitter@africaskills.co.za", "Mechanical Fitter"),
    ("Lawrence Ndlovu", "dieselandauto@africaskills.co.za", "Diesel & Auto"),
    ("Hein Brouwer", "hein@africaskills.co.za", ""),
]


class Command(BaseCommand):
    help = 'Create staff users from the provided data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        created_count = 0
        skipped_count = 0
        
        # Get or create a system user for created_by
        system_user = User.objects.filter(is_superuser=True).first()
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        for name, email, role in STAFF_DATA:
            # Parse name
            parts = name.strip().split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''
            
            # Check if user exists
            if User.objects.filter(email=email).exists():
                self.stdout.write(f'  Skipping {email} - already exists')
                skipped_count += 1
                continue
            
            if dry_run:
                self.stdout.write(f'  Would create: {first_name} {last_name} <{email}>')
                if role:
                    self.stdout.write(f'    Role/Title: {role}')
                created_count += 1
            else:
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            password='SkillsFlow2026!',  # Default password
                            is_active=True,
                            is_staff=False,
                        )
                        self.stdout.write(self.style.SUCCESS(f'  Created: {user.get_full_name()} <{email}>'))
                        created_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error creating {email}: {e}'))
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count} users'))
        self.stdout.write(f'Skipped: {skipped_count} users (already exist)')
        
        if not dry_run and created_count > 0:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Default password for all new users: SkillsFlow2026!'))
            self.stdout.write('Users should change their password on first login.')
