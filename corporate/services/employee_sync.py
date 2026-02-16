"""
Employee Snapshot Sync Service

Provides functionality to:
- Create employee demographic snapshots
- Sync snapshot data to WSP/ATR employee data
- Sync snapshot data to EE workforce profiles
- Compare snapshots for variance reporting
"""
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.utils import timezone


class EmployeeSnapshotService:
    """
    Service for managing employee demographic snapshots and syncing
    data between WSP/ATR and EE modules.
    """
    
    OCCUPATIONAL_LEVEL_MAPPING = {
        # Map from OccupationalLevelData choices to WSPATREmployeeData choices
        'TOP_MANAGEMENT': 'TOP_MANAGEMENT',
        'SENIOR_MANAGEMENT': 'SENIOR_MANAGEMENT',
        'PROFESSIONAL': 'PROFESSIONAL',
        'SKILLED_TECHNICAL': 'SKILLED_TECHNICAL',
        'SEMI_SKILLED': 'SEMI_SKILLED',
        'UNSKILLED': 'UNSKILLED',
        'NON_PERMANENT': None,  # WSP/ATR doesn't have non-permanent level
    }
    
    @classmethod
    def create_snapshot_from_import(cls, client, snapshot_date, snapshot_type, 
                                    occupational_data, created_by=None, source_description=''):
        """
        Create a new employee snapshot from imported data.
        
        Args:
            client: CorporateClient instance
            snapshot_date: Date the snapshot represents
            snapshot_type: Type of snapshot (MONTHLY, QUARTERLY, etc.)
            occupational_data: List of dicts with occupational level data:
                [
                    {
                        'occupational_level': 'TOP_MANAGEMENT',
                        'african_male': 1,
                        'african_female': 0,
                        ...
                    },
                    ...
                ]
            created_by: User who created the snapshot
            source_description: Description of the data source
            
        Returns:
            ClientEmployeeSnapshot instance
        """
        from corporate.models import ClientEmployeeSnapshot, OccupationalLevelData
        
        with transaction.atomic():
            # Create the snapshot
            snapshot = ClientEmployeeSnapshot.objects.create(
                client=client,
                campus=client.campus if hasattr(client, 'campus') else None,
                snapshot_date=snapshot_date,
                snapshot_type=snapshot_type,
                source_description=source_description,
                created_by=created_by,
            )
            
            # Create occupational level data rows
            for level_data in occupational_data:
                OccupationalLevelData.objects.create(
                    snapshot=snapshot,
                    occupational_level=level_data.get('occupational_level'),
                    african_male=level_data.get('african_male', 0),
                    coloured_male=level_data.get('coloured_male', 0),
                    indian_male=level_data.get('indian_male', 0),
                    white_male=level_data.get('white_male', 0),
                    foreign_national_male=level_data.get('foreign_national_male', 0),
                    african_female=level_data.get('african_female', 0),
                    coloured_female=level_data.get('coloured_female', 0),
                    indian_female=level_data.get('indian_female', 0),
                    white_female=level_data.get('white_female', 0),
                    foreign_national_female=level_data.get('foreign_national_female', 0),
                    disabled_male=level_data.get('disabled_male', 0),
                    disabled_female=level_data.get('disabled_female', 0),
                )
            
            return snapshot
    
    @classmethod
    def sync_snapshot_to_wspatr(cls, snapshot, wspatr_service_year):
        """
        Sync employee snapshot data to WSP/ATR service year employee data.
        
        Args:
            snapshot: ClientEmployeeSnapshot instance
            wspatr_service_year: WSPATRServiceYear instance
            
        Returns:
            List of WSPATREmployeeData instances created/updated
        """
        from corporate.models import WSPATREmployeeData
        
        results = []
        
        with transaction.atomic():
            for occ_data in snapshot.occupational_data.all():
                # Skip non-permanent as WSP/ATR doesn't have this level
                wspatr_level = cls.OCCUPATIONAL_LEVEL_MAPPING.get(occ_data.occupational_level)
                if not wspatr_level:
                    continue
                
                # Update or create WSP/ATR employee data
                employee_data, created = WSPATREmployeeData.objects.update_or_create(
                    service_year=wspatr_service_year,
                    occupational_level=wspatr_level,
                    defaults={
                        'african_male': occ_data.african_male,
                        'coloured_male': occ_data.coloured_male,
                        'indian_male': occ_data.indian_male,
                        'white_male': occ_data.white_male,
                        'foreign_male': occ_data.foreign_national_male,
                        'african_female': occ_data.african_female,
                        'coloured_female': occ_data.coloured_female,
                        'indian_female': occ_data.indian_female,
                        'white_female': occ_data.white_female,
                        'foreign_female': occ_data.foreign_national_female,
                        'disabled_male': occ_data.disabled_male,
                        'disabled_female': occ_data.disabled_female,
                    }
                )
                results.append(employee_data)
        
        return results
    
    @classmethod
    def sync_snapshot_to_ee(cls, snapshot, ee_service_year):
        """
        Sync employee snapshot data to EE service year and link the snapshot.
        
        For EE, we keep the workforce profile data in the snapshot itself
        (via OccupationalLevelData) and just link the snapshot to the service year.
        
        Args:
            snapshot: ClientEmployeeSnapshot instance
            ee_service_year: EEServiceYear instance
            
        Returns:
            Updated EEServiceYear instance
        """
        # Link the snapshot to the EE service year
        ee_service_year.employee_snapshot = snapshot
        ee_service_year.save(update_fields=['employee_snapshot'])
        
        return ee_service_year
    
    @classmethod
    def get_latest_snapshot(cls, client, snapshot_type=None):
        """
        Get the most recent employee snapshot for a client.
        
        Args:
            client: CorporateClient instance
            snapshot_type: Optional filter by snapshot type
            
        Returns:
            ClientEmployeeSnapshot instance or None
        """
        from corporate.models import ClientEmployeeSnapshot
        
        queryset = ClientEmployeeSnapshot.objects.filter(client=client)
        if snapshot_type:
            queryset = queryset.filter(snapshot_type=snapshot_type)
        
        return queryset.order_by('-snapshot_date').first()
    
    @classmethod
    def compare_snapshots(cls, snapshot1, snapshot2):
        """
        Compare two employee snapshots and return variance data.
        
        Args:
            snapshot1: Earlier ClientEmployeeSnapshot instance
            snapshot2: Later ClientEmployeeSnapshot instance
            
        Returns:
            Dict with variance data by occupational level
        """
        comparison = {
            'snapshot1_date': snapshot1.snapshot_date,
            'snapshot2_date': snapshot2.snapshot_date,
            'total_variance': 0,
            'occupational_levels': {},
        }
        
        # Get all occupational levels from both snapshots
        levels_1 = {d.occupational_level: d for d in snapshot1.occupational_data.all()}
        levels_2 = {d.occupational_level: d for d in snapshot2.occupational_data.all()}
        
        all_levels = set(levels_1.keys()) | set(levels_2.keys())
        
        for level in all_levels:
            data1 = levels_1.get(level)
            data2 = levels_2.get(level)
            
            total1 = data1.total if data1 else 0
            total2 = data2.total if data2 else 0
            variance = total2 - total1
            
            comparison['occupational_levels'][level] = {
                'previous_total': total1,
                'current_total': total2,
                'variance': variance,
                'variance_percentage': round((variance / total1 * 100), 1) if total1 > 0 else 0,
                'demographics': cls._compare_demographics(data1, data2),
            }
            comparison['total_variance'] += variance
        
        comparison['previous_total'] = snapshot1.total_employees
        comparison['current_total'] = snapshot2.total_employees
        comparison['total_variance_percentage'] = round(
            (comparison['total_variance'] / comparison['previous_total'] * 100), 1
        ) if comparison['previous_total'] > 0 else 0
        
        return comparison
    
    @classmethod
    def _compare_demographics(cls, data1, data2):
        """Helper to compare demographic breakdown between two occupational level records."""
        fields = [
            'african_male', 'coloured_male', 'indian_male', 'white_male', 'foreign_national_male',
            'african_female', 'coloured_female', 'indian_female', 'white_female', 'foreign_national_female',
            'disabled_male', 'disabled_female',
        ]
        
        comparison = {}
        for field in fields:
            val1 = getattr(data1, field, 0) if data1 else 0
            val2 = getattr(data2, field, 0) if data2 else 0
            comparison[field] = {
                'previous': val1,
                'current': val2,
                'variance': val2 - val1,
            }
        
        return comparison
    
    @classmethod
    def create_snapshot_from_wspatr(cls, wspatr_service_year, created_by=None):
        """
        Create a new employee snapshot from existing WSP/ATR employee data.
        Useful for creating an EE snapshot from existing WSP/ATR data.
        
        Args:
            wspatr_service_year: WSPATRServiceYear instance with employee_data
            created_by: User who created the snapshot
            
        Returns:
            ClientEmployeeSnapshot instance
        """
        from corporate.models import ClientEmployeeSnapshot, OccupationalLevelData
        
        # Determine snapshot date (end of WSP/ATR financial year)
        snapshot_date = wspatr_service_year.cycle_end_date
        
        occupational_data = []
        for emp_data in wspatr_service_year.employee_data.all():
            occupational_data.append({
                'occupational_level': emp_data.occupational_level,
                'african_male': emp_data.african_male,
                'coloured_male': emp_data.coloured_male,
                'indian_male': emp_data.indian_male,
                'white_male': emp_data.white_male,
                'foreign_national_male': emp_data.foreign_male,
                'african_female': emp_data.african_female,
                'coloured_female': emp_data.coloured_female,
                'indian_female': emp_data.indian_female,
                'white_female': emp_data.white_female,
                'foreign_national_female': emp_data.foreign_female,
                'disabled_male': emp_data.disabled_male,
                'disabled_female': emp_data.disabled_female,
            })
        
        return cls.create_snapshot_from_import(
            client=wspatr_service_year.client,
            snapshot_date=snapshot_date,
            snapshot_type='WSP_ATR',
            occupational_data=occupational_data,
            created_by=created_by,
            source_description=f'Created from WSP/ATR {wspatr_service_year.financial_year_display}',
        )
    
    @classmethod
    def verify_snapshot(cls, snapshot, verified_by):
        """
        Mark a snapshot as verified.
        
        Args:
            snapshot: ClientEmployeeSnapshot instance
            verified_by: User who verified the snapshot
            
        Returns:
            Updated ClientEmployeeSnapshot instance
        """
        snapshot.is_verified = True
        snapshot.verified_by = verified_by
        snapshot.verified_at = timezone.now()
        snapshot.save(update_fields=['is_verified', 'verified_by', 'verified_at'])
        return snapshot
    
    @classmethod
    def get_ee_occupational_summary(cls, ee_service_year):
        """
        Get a summary of workforce profile for EE reporting.
        
        Args:
            ee_service_year: EEServiceYear instance
            
        Returns:
            Dict with summary data by occupational level
        """
        snapshot = ee_service_year.employee_snapshot
        if not snapshot:
            return None
        
        summary = {
            'snapshot_date': snapshot.snapshot_date,
            'total_employees': snapshot.total_employees,
            'levels': [],
        }
        
        for occ_data in snapshot.occupational_data.all():
            summary['levels'].append({
                'level': occ_data.occupational_level,
                'level_display': occ_data.get_occupational_level_display(),
                'total': occ_data.total,
                'total_male': occ_data.total_male,
                'total_female': occ_data.total_female,
                'total_african': occ_data.total_african,
                'total_coloured': occ_data.total_coloured,
                'total_indian': occ_data.total_indian,
                'total_white': occ_data.total_white,
                'total_foreign': occ_data.total_foreign,
                'total_disabled': occ_data.total_disabled,
            })
        
        return summary
