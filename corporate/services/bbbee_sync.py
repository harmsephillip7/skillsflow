"""
B-BBEE Data Sync Service

Provides functionality to:
- Sync employee snapshot data to Management Control element
- Sync WSP/ATR training data to Skills Development element
- Calculate enterprise type based on turnover
- Auto-calculate EME/QSE B-BBEE levels
- Create linked service years between B-BBEE, EE, and WSP/ATR
"""
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.utils import timezone


class BBBEESyncService:
    """
    Service for managing B-BBEE data synchronization between modules.
    
    Links:
    - Skills Development element ↔ WSP/ATR training data
    - Management Control element ↔ EE/Employee Snapshot demographics
    """
    
    # EME threshold is R10 million
    EME_THRESHOLD = Decimal('10000000')
    # QSE threshold is R50 million
    QSE_THRESHOLD = Decimal('50000000')
    
    # Management level mapping from OccupationalLevelData
    # B-BBEE categories don't map 1:1 to EE occupational levels
    MANAGEMENT_LEVEL_MAPPING = {
        'TOP_MANAGEMENT': 'exec',  # Executive/C-Suite
        'SENIOR_MANAGEMENT': 'senior_mgmt',  # Senior Management
        'PROFESSIONAL': 'middle_mgmt',  # Middle Management (Professionally Qualified)
        'SKILLED_TECHNICAL': 'junior_mgmt',  # Junior Management/Supervisors
    }
    
    @classmethod
    def determine_enterprise_type(cls, annual_turnover):
        """
        Determine enterprise classification based on annual turnover.
        
        Args:
            annual_turnover: Decimal amount of annual turnover
            
        Returns:
            str: 'EME', 'QSE', or 'GENERIC'
        """
        if annual_turnover is None:
            return 'GENERIC'
            
        if annual_turnover <= cls.EME_THRESHOLD:
            return 'EME'
        elif annual_turnover <= cls.QSE_THRESHOLD:
            return 'QSE'
        else:
            return 'GENERIC'
    
    @classmethod
    def calculate_eme_level(cls, black_ownership_percentage, black_women_ownership_percentage=None):
        """
        Calculate automatic B-BBEE level for Exempted Micro Enterprises.
        
        EME with 100% black ownership = Level 1
        EME with 51%+ black ownership = Level 2
        Other EME = Level 4
        
        Bonus: Black women ownership 30%+ gets one level uplift (max Level 1)
        
        Args:
            black_ownership_percentage: Decimal percentage of black ownership
            black_women_ownership_percentage: Decimal percentage of black women ownership
            
        Returns:
            tuple: (level_code, level_display)
        """
        if black_ownership_percentage is None:
            return ('LEVEL_4', 'Level 4')
        
        base_level = 4
        
        if black_ownership_percentage >= Decimal('100'):
            base_level = 1
        elif black_ownership_percentage >= Decimal('51'):
            base_level = 2
        
        # Black women bonus (30%+)
        if black_women_ownership_percentage and black_women_ownership_percentage >= Decimal('30'):
            base_level = max(1, base_level - 1)  # Cannot go below Level 1
        
        return (f'LEVEL_{base_level}', f'Level {base_level}')
    
    @classmethod
    def calculate_qse_level(cls, black_ownership_percentage, black_women_ownership_percentage=None):
        """
        Calculate automatic B-BBEE level for Qualifying Small Enterprises.
        
        QSE with 100% black ownership = Level 1
        QSE with 51%+ black ownership = Level 2
        Other QSE uses simplified scorecard (but these are auto-recognition rules)
        
        Args:
            black_ownership_percentage: Decimal percentage of black ownership
            black_women_ownership_percentage: Decimal percentage of black women ownership
            
        Returns:
            tuple: (level_code, level_display) or (None, None) if not auto-recognized
        """
        if black_ownership_percentage is None:
            return (None, None)  # Needs full QSE scorecard
        
        if black_ownership_percentage >= Decimal('100'):
            return ('LEVEL_1', 'Level 1')
        elif black_ownership_percentage >= Decimal('51'):
            return ('LEVEL_2', 'Level 2')
        
        return (None, None)  # Needs full QSE scorecard
    
    @classmethod
    def sync_management_control_from_snapshot(cls, bbbee_service_year, employee_snapshot=None):
        """
        Sync employee demographic data to B-BBEE Management Control element.
        
        Args:
            bbbee_service_year: BBBEEServiceYear instance
            employee_snapshot: Optional ClientEmployeeSnapshot instance
                              (uses service_year's linked snapshot if not provided)
            
        Returns:
            ManagementControlProfile instance
        """
        from corporate.models import ManagementControlProfile
        
        snapshot = employee_snapshot or bbbee_service_year.employee_snapshot
        if not snapshot:
            return None
        
        # Link the snapshot to service year if not already linked
        if not bbbee_service_year.employee_snapshot:
            bbbee_service_year.employee_snapshot = snapshot
            bbbee_service_year.save(update_fields=['employee_snapshot'])
        
        with transaction.atomic():
            # Get or create Management Control profile
            profile, created = ManagementControlProfile.objects.get_or_create(
                service_year=bbbee_service_year
            )
            
            # Initialize counters
            exec_total = 0
            exec_black = 0
            exec_black_female = 0
            senior_mgmt_total = 0
            senior_mgmt_black = 0
            senior_mgmt_black_female = 0
            middle_mgmt_total = 0
            middle_mgmt_black = 0
            middle_mgmt_black_female = 0
            junior_mgmt_total = 0
            junior_mgmt_black = 0
            junior_mgmt_black_female = 0
            
            # Process occupational level data
            for occ_data in snapshot.occupational_data.all():
                mgmt_category = cls.MANAGEMENT_LEVEL_MAPPING.get(occ_data.occupational_level)
                if not mgmt_category:
                    continue
                
                # Calculate totals (exclude foreign nationals for B-BBEE)
                total = occ_data.total - (occ_data.foreign_national_male or 0) - (occ_data.foreign_national_female or 0)
                # Black = African, Coloured, Indian (as defined in B-BBEE Act)
                black_male = (occ_data.african_male or 0) + (occ_data.coloured_male or 0) + (occ_data.indian_male or 0)
                black_female = (occ_data.african_female or 0) + (occ_data.coloured_female or 0) + (occ_data.indian_female or 0)
                black_total = black_male + black_female
                
                if mgmt_category == 'exec':
                    exec_total += total
                    exec_black += black_total
                    exec_black_female += black_female
                elif mgmt_category == 'senior_mgmt':
                    senior_mgmt_total += total
                    senior_mgmt_black += black_total
                    senior_mgmt_black_female += black_female
                elif mgmt_category == 'middle_mgmt':
                    middle_mgmt_total += total
                    middle_mgmt_black += black_total
                    middle_mgmt_black_female += black_female
                elif mgmt_category == 'junior_mgmt':
                    junior_mgmt_total += total
                    junior_mgmt_black += black_total
                    junior_mgmt_black_female += black_female
            
            # Update profile with calculated values
            profile.exec_total = exec_total
            profile.exec_black = exec_black
            profile.exec_black_female = exec_black_female
            profile.senior_mgmt_total = senior_mgmt_total
            profile.senior_mgmt_black = senior_mgmt_black
            profile.senior_mgmt_black_female = senior_mgmt_black_female
            profile.middle_mgmt_total = middle_mgmt_total
            profile.middle_mgmt_black = middle_mgmt_black
            profile.middle_mgmt_black_female = middle_mgmt_black_female
            profile.junior_mgmt_total = junior_mgmt_total
            profile.junior_mgmt_black = junior_mgmt_black
            profile.junior_mgmt_black_female = junior_mgmt_black_female
            
            profile.save()
            
            return profile
    
    @classmethod
    def sync_skills_development_from_wspatr(cls, bbbee_service_year, wspatr_service_year=None):
        """
        Sync WSP/ATR training data to B-BBEE Skills Development element.
        
        Args:
            bbbee_service_year: BBBEEServiceYear instance
            wspatr_service_year: Optional WSPATRServiceYear instance
                                (uses service_year's linked WSP/ATR if not provided)
            
        Returns:
            SkillsDevelopmentElement instance
        """
        from corporate.models import SkillsDevelopmentElement
        
        wspatr = wspatr_service_year or bbbee_service_year.wspatr_service_year
        if not wspatr:
            return None
        
        # Link the WSP/ATR to service year if not already linked
        if not bbbee_service_year.wspatr_service_year:
            bbbee_service_year.wspatr_service_year = wspatr
            bbbee_service_year.save(update_fields=['wspatr_service_year'])
        
        with transaction.atomic():
            # Get or create Skills Development element
            skills_dev, created = SkillsDevelopmentElement.objects.get_or_create(
                service_year=bbbee_service_year
            )
            
            # Initialize counters
            total_skills_spend = Decimal('0.00')
            black_skills_spend = Decimal('0.00')
            black_female_skills_spend = Decimal('0.00')
            
            learnerships_total = 0
            learnerships_black = 0
            learnerships_black_female = 0
            
            internships_total = 0
            internships_black = 0
            
            bursaries_total = 0
            bursaries_black = 0
            bursaries_spend = Decimal('0.00')
            
            # Process training data from ATR (actual spend)
            for training in wspatr.training_data.filter(data_type='ACTUAL'):
                cost = training.actual_cost or training.estimated_cost or Decimal('0.00')
                total_skills_spend += cost
                
                # Calculate black learners
                black_male = (training.african_male or 0) + (training.coloured_male or 0) + (training.indian_male or 0)
                black_female = (training.african_female or 0) + (training.coloured_female or 0) + (training.indian_female or 0)
                black_total = black_male + black_female
                total_learners = training.total_learners if hasattr(training, 'total_learners') else 0
                
                # Apportion cost to black learners
                if total_learners > 0:
                    black_proportion = Decimal(black_total) / Decimal(total_learners)
                    black_female_proportion = Decimal(black_female) / Decimal(total_learners)
                    black_skills_spend += cost * black_proportion
                    black_female_skills_spend += cost * black_female_proportion
                
                # Track learnerships
                if training.intervention_type == 'LEARNERSHIP':
                    total_male = (training.african_male or 0) + (training.coloured_male or 0) + \
                                (training.indian_male or 0) + (training.white_male or 0)
                    total_female = (training.african_female or 0) + (training.coloured_female or 0) + \
                                  (training.indian_female or 0) + (training.white_female or 0)
                    learnerships_total += total_male + total_female
                    learnerships_black += black_total
                    learnerships_black_female += black_female
                
                # Track internships
                elif training.intervention_type == 'INTERNSHIP':
                    total_male = (training.african_male or 0) + (training.coloured_male or 0) + \
                                (training.indian_male or 0) + (training.white_male or 0)
                    total_female = (training.african_female or 0) + (training.coloured_female or 0) + \
                                  (training.indian_female or 0) + (training.white_female or 0)
                    internships_total += total_male + total_female
                    internships_black += black_total
                
                # Track bursaries
                elif training.intervention_type == 'BURSARY':
                    total_male = (training.african_male or 0) + (training.coloured_male or 0) + \
                                (training.indian_male or 0) + (training.white_male or 0)
                    total_female = (training.african_female or 0) + (training.coloured_female or 0) + \
                                  (training.indian_female or 0) + (training.white_female or 0)
                    bursaries_total += total_male + total_female
                    bursaries_black += black_total
                    bursaries_spend += cost
            
            # Update Skills Development element
            skills_dev.total_skills_spend = total_skills_spend
            skills_dev.black_skills_spend = black_skills_spend
            skills_dev.black_female_skills_spend = black_female_skills_spend
            
            skills_dev.learnerships_total = learnerships_total
            skills_dev.learnerships_black = learnerships_black
            skills_dev.learnerships_black_female = learnerships_black_female
            
            skills_dev.internships_total = internships_total
            skills_dev.internships_black = internships_black
            
            skills_dev.bursaries_total = bursaries_total
            skills_dev.bursaries_black = bursaries_black
            skills_dev.bursaries_spend = bursaries_spend
            
            skills_dev.save()
            
            return skills_dev
    
    @classmethod
    def link_service_years(cls, bbbee_service_year, ee_service_year=None, wspatr_service_year=None):
        """
        Link B-BBEE service year to EE and WSP/ATR service years.
        
        Args:
            bbbee_service_year: BBBEEServiceYear instance
            ee_service_year: Optional EEServiceYear to link
            wspatr_service_year: Optional WSPATRServiceYear to link
            
        Returns:
            Updated BBBEEServiceYear instance
        """
        updates = []
        
        if ee_service_year:
            bbbee_service_year.ee_service_year = ee_service_year
            updates.append('ee_service_year')
            
            # Also link employee snapshot if EE has one
            if ee_service_year.employee_snapshot:
                bbbee_service_year.employee_snapshot = ee_service_year.employee_snapshot
                updates.append('employee_snapshot')
        
        if wspatr_service_year:
            bbbee_service_year.wspatr_service_year = wspatr_service_year
            updates.append('wspatr_service_year')
        
        if updates:
            bbbee_service_year.save(update_fields=updates)
        
        return bbbee_service_year
    
    @classmethod
    def find_matching_service_years(cls, bbbee_service_year):
        """
        Find EE and WSP/ATR service years that match the B-BBEE financial year.
        
        Args:
            bbbee_service_year: BBBEEServiceYear instance
            
        Returns:
            dict: {'ee_service_year': ..., 'wspatr_service_year': ...}
        """
        from corporate.models import EEServiceYear, WSPATRServiceYear
        
        client = bbbee_service_year.client
        financial_year = bbbee_service_year.financial_year
        
        result = {
            'ee_service_year': None,
            'wspatr_service_year': None,
        }
        
        # EE uses Oct-Sept cycle, so look for matching year
        # B-BBEE FY2025 (ending Feb 2025) would match EE year 2024-2025
        try:
            ee_year = EEServiceYear.objects.filter(
                client=client,
                reporting_year=financial_year
            ).first()
            result['ee_service_year'] = ee_year
        except Exception:
            pass
        
        # WSP/ATR uses Apr-Mar cycle
        try:
            wspatr_year = WSPATRServiceYear.objects.filter(
                client=client,
                financial_year=financial_year
            ).first()
            result['wspatr_service_year'] = wspatr_year
        except Exception:
            pass
        
        return result
    
    @classmethod
    def create_bbbee_service_year(cls, subscription, financial_year, year_end_month=None, 
                                   auto_link=True, auto_sync=False):
        """
        Create a new B-BBEE service year with optional auto-linking to EE/WSP/ATR.
        
        Args:
            subscription: ClientServiceSubscription instance
            financial_year: Year the financial year ends (e.g., 2025)
            year_end_month: Month financial year ends (1-12), defaults to client's year-end
            auto_link: Whether to automatically find and link matching EE/WSP/ATR years
            auto_sync: Whether to automatically sync data from linked years
            
        Returns:
            BBBEEServiceYear instance
        """
        from corporate.models import BBBEEServiceYear
        
        client = subscription.client
        
        # Determine year-end month from client if not provided
        if year_end_month is None:
            year_end_month = getattr(client, 'financial_year_end_month', 2)  # Default Feb
        
        # Determine enterprise type from annual revenue
        annual_turnover = getattr(client, 'annual_revenue', None)
        enterprise_type = cls.determine_enterprise_type(annual_turnover)
        
        with transaction.atomic():
            service_year = BBBEEServiceYear.objects.create(
                subscription=subscription,
                client=client,
                financial_year=financial_year,
                year_end_month=year_end_month,
                enterprise_type=enterprise_type,
                annual_turnover=annual_turnover,
                status='NOT_STARTED'
            )
            
            if auto_link:
                # Find and link matching service years
                matches = cls.find_matching_service_years(service_year)
                cls.link_service_years(
                    service_year,
                    ee_service_year=matches.get('ee_service_year'),
                    wspatr_service_year=matches.get('wspatr_service_year')
                )
                
                if auto_sync:
                    # Sync data from linked years
                    if service_year.employee_snapshot or (matches.get('ee_service_year') and 
                                                          matches['ee_service_year'].employee_snapshot):
                        cls.sync_management_control_from_snapshot(service_year)
                    
                    if service_year.wspatr_service_year:
                        cls.sync_skills_development_from_wspatr(service_year)
            
            return service_year
    
    @classmethod
    def calculate_total_score(cls, bbbee_service_year):
        """
        Calculate total B-BBEE score from element scores.
        
        Generic scorecard maximum: 109 points
        - Ownership: 25 points
        - Management Control: 19 points
        - Skills Development: 20 points
        - Enterprise & Supplier Development: 40 points
        - Socio-Economic Development: 5 points
        
        Args:
            bbbee_service_year: BBBEEServiceYear instance
            
        Returns:
            Decimal: Total score
        """
        total = Decimal('0.00')
        
        try:
            if hasattr(bbbee_service_year, 'ownership_structure'):
                total += bbbee_service_year.ownership_structure.calculated_score or Decimal('0.00')
        except Exception:
            pass
        
        try:
            if hasattr(bbbee_service_year, 'management_profile'):
                total += bbbee_service_year.management_profile.calculated_score or Decimal('0.00')
        except Exception:
            pass
        
        try:
            if hasattr(bbbee_service_year, 'skills_development'):
                total += bbbee_service_year.skills_development.calculated_score or Decimal('0.00')
        except Exception:
            pass
        
        try:
            if hasattr(bbbee_service_year, 'esd_element'):
                total += bbbee_service_year.esd_element.calculated_score or Decimal('0.00')
        except Exception:
            pass
        
        try:
            if hasattr(bbbee_service_year, 'sed_element'):
                total += bbbee_service_year.sed_element.calculated_score or Decimal('0.00')
        except Exception:
            pass
        
        return total
    
    @classmethod
    def determine_level_from_score(cls, total_score, enterprise_type='GENERIC'):
        """
        Determine B-BBEE level from total score.
        
        Generic scorecard levels:
        - Level 1: ≥100 points (135% B-BBEE recognition)
        - Level 2: 95-99 points (125% recognition)
        - Level 3: 90-94 points (110% recognition)
        - Level 4: 80-89 points (100% recognition)
        - Level 5: 75-79 points (80% recognition)
        - Level 6: 70-74 points (60% recognition)
        - Level 7: 55-69 points (50% recognition)
        - Level 8: 40-54 points (10% recognition)
        - Non-Compliant: <40 points (0% recognition)
        
        Args:
            total_score: Decimal total score
            enterprise_type: 'EME', 'QSE', or 'GENERIC'
            
        Returns:
            tuple: (level_code, level_display, recognition_percentage)
        """
        if total_score >= 100:
            return ('LEVEL_1', 'Level 1', Decimal('135'))
        elif total_score >= 95:
            return ('LEVEL_2', 'Level 2', Decimal('125'))
        elif total_score >= 90:
            return ('LEVEL_3', 'Level 3', Decimal('110'))
        elif total_score >= 80:
            return ('LEVEL_4', 'Level 4', Decimal('100'))
        elif total_score >= 75:
            return ('LEVEL_5', 'Level 5', Decimal('80'))
        elif total_score >= 70:
            return ('LEVEL_6', 'Level 6', Decimal('60'))
        elif total_score >= 55:
            return ('LEVEL_7', 'Level 7', Decimal('50'))
        elif total_score >= 40:
            return ('LEVEL_8', 'Level 8', Decimal('10'))
        else:
            return ('NON_COMPLIANT', 'Non-Compliant', Decimal('0'))
    
    @classmethod
    def create_all_elements(cls, bbbee_service_year):
        """
        Create all B-BBEE element records for a service year.
        
        Args:
            bbbee_service_year: BBBEEServiceYear instance
            
        Returns:
            dict: Dictionary of created element instances
        """
        from corporate.models import (
            OwnershipStructure, ManagementControlProfile,
            SkillsDevelopmentElement, ESDElement, SEDElement
        )
        
        elements = {}
        
        with transaction.atomic():
            # Ownership
            ownership, _ = OwnershipStructure.objects.get_or_create(
                service_year=bbbee_service_year
            )
            elements['ownership'] = ownership
            
            # Management Control
            management, _ = ManagementControlProfile.objects.get_or_create(
                service_year=bbbee_service_year
            )
            elements['management'] = management
            
            # Skills Development
            skills, _ = SkillsDevelopmentElement.objects.get_or_create(
                service_year=bbbee_service_year
            )
            elements['skills'] = skills
            
            # Enterprise & Supplier Development
            esd, _ = ESDElement.objects.get_or_create(
                service_year=bbbee_service_year
            )
            elements['esd'] = esd
            
            # Socio-Economic Development
            sed, _ = SEDElement.objects.get_or_create(
                service_year=bbbee_service_year
            )
            elements['sed'] = sed
        
        return elements
    
    @classmethod
    def get_verification_requirements(cls, enterprise_type):
        """
        Get verification requirements based on enterprise type.
        
        Args:
            enterprise_type: 'EME', 'QSE', or 'GENERIC'
            
        Returns:
            dict: Verification requirements and notes
        """
        if enterprise_type == 'EME':
            return {
                'requires_verification': False,
                'document_required': 'Sworn Affidavit',
                'automatic_level': True,
                'notes': (
                    'EMEs do not require verification by a verification agency. '
                    'A sworn affidavit confirming annual turnover and black ownership '
                    'percentage is sufficient. Turnover must be ≤R10 million.'
                ),
                'auto_level_rules': (
                    '100% black-owned = Level 1\n'
                    '51%+ black-owned = Level 2\n'
                    'Other = Level 4\n'
                    '+30% black women ownership = 1 level bonus'
                )
            }
        elif enterprise_type == 'QSE':
            return {
                'requires_verification': True,
                'document_required': 'B-BBEE Certificate or Sworn Affidavit (if 51%+ black-owned)',
                'automatic_level': False,  # Only if 51%+ black-owned
                'notes': (
                    'QSEs (R10-50 million turnover) use a simplified scorecard. '
                    'QSEs with 51%+ black ownership can submit a sworn affidavit for '
                    'automatic Level 1/2 recognition. Others require verification.'
                ),
                'auto_level_rules': (
                    '100% black-owned = Level 1 (affidavit)\n'
                    '51%+ black-owned = Level 2 (affidavit)\n'
                    'Other = Requires simplified scorecard verification'
                )
            }
        else:  # GENERIC
            return {
                'requires_verification': True,
                'document_required': 'B-BBEE Certificate from SANAS-accredited agency',
                'automatic_level': False,
                'notes': (
                    'Generic enterprises (>R50 million turnover) require full verification '
                    'using the generic scorecard by a SANAS-accredited B-BBEE verification agency.'
                ),
                'scorecard_elements': {
                    'Ownership': 25,
                    'Management Control': 19,
                    'Skills Development': 20,
                    'Enterprise & Supplier Development': 40,
                    'Socio-Economic Development': 5,
                    'Total': 109
                }
            }
