"""
Learner Services

Business logic for learner-related operations including
stipend calculations and leave policy management.
"""
import logging
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db.models import Sum, Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class StipendCalculator:
    """
    Calculate monthly stipend for learners based on attendance records
    and leave policy configuration.
    
    Usage:
        calculator = StipendCalculator(placement, month=12, year=2025)
        calculation = calculator.calculate()
        
        # Access breakdown
        print(f"Days worked: {calculation.days_present}")
        print(f"Paid days: {calculation.paid_days}")
        print(f"Net amount: R{calculation.net_amount}")
    """
    
    def __init__(self, placement, month: int, year: int):
        """
        Initialize calculator for a specific placement and period.
        
        Args:
            placement: WorkplacePlacement instance
            month: Month number (1-12)
            year: Year
        """
        self.placement = placement
        self.month = month
        self.year = year
        self.leave_policy = placement.leave_policy
        
        # Get working days in month
        self._calculate_working_days()
    
    def _calculate_working_days(self):
        """Calculate total working days in the month (excluding weekends)."""
        _, days_in_month = monthrange(self.year, self.month)
        
        working_days = 0
        for day in range(1, days_in_month + 1):
            d = date(self.year, self.month, day)
            if d.weekday() < 5:  # Monday to Friday
                working_days += 1
        
        self.total_working_days = working_days
    
    def get_attendance_summary(self) -> Dict[str, int]:
        """
        Get attendance breakdown from WorkplaceAttendance records.
        
        Returns:
            Dict with counts for each attendance type
        """
        from learners.models import WorkplaceAttendance
        
        # Get all attendance records for this placement and period
        records = WorkplaceAttendance.objects.filter(
            placement=self.placement,
            date__year=self.year,
            date__month=self.month
        )
        
        # Count by type
        summary = {
            'PRESENT': 0,
            'ANNUAL': 0,
            'SICK': 0,
            'FAMILY': 0,
            'UNPAID': 0,
            'PUBLIC_HOLIDAY': 0,
            'ABSENT': 0,
            'SUSPENDED': 0,
        }
        
        for record in records:
            if record.attendance_type in summary:
                summary[record.attendance_type] += 1
        
        return summary
    
    def get_leave_allowances(self) -> Dict[str, int]:
        """
        Get leave allowances based on leave policy.
        Pro-rated for placement duration if less than a year.
        
        Returns:
            Dict with maximum allowed paid days for each leave type
        """
        if not self.leave_policy:
            # Default policy
            return {
                'annual_leave': 1,  # ~15 days per year / 12 months
                'sick_leave': 2,
                'family_leave': 0,  # ~3 days per year, grant as needed
            }
        
        # Calculate pro-rata for annual leave based on placement duration
        placement_months = self._get_placement_month_count()
        
        annual_allowance = min(
            self.leave_policy.annual_leave_days_per_year * placement_months // 12,
            self.leave_policy.annual_leave_days_per_year
        )
        
        # Monthly sick leave allowance
        sick_allowance = self.leave_policy.sick_leave_days_per_month
        
        # Family leave - annual allowance
        family_annual = self.leave_policy.family_responsibility_days_per_year
        family_used_ytd = self._get_family_leave_used_ytd()
        family_remaining = max(0, family_annual - family_used_ytd)
        
        return {
            'annual_leave': annual_allowance,
            'sick_leave': sick_allowance,
            'family_leave': family_remaining,
        }
    
    def _get_placement_month_count(self) -> int:
        """Calculate how many months the placement has been active."""
        start = self.placement.start_date
        current = date(self.year, self.month, 1)
        
        months = (current.year - start.year) * 12 + (current.month - start.month) + 1
        return max(1, min(months, 12))
    
    def _get_family_leave_used_ytd(self) -> int:
        """Get family responsibility leave used year-to-date."""
        from learners.models import WorkplaceAttendance
        
        return WorkplaceAttendance.objects.filter(
            placement=self.placement,
            date__year=self.year,
            date__month__lte=self.month,
            attendance_type='FAMILY'
        ).count()
    
    def calculate_paid_days(self, attendance: Dict[str, int], allowances: Dict[str, int]) -> Dict:
        """
        Calculate paid days based on attendance and leave allowances.
        
        Args:
            attendance: Attendance summary from get_attendance_summary()
            allowances: Leave allowances from get_leave_allowances()
            
        Returns:
            Dict with paid days breakdown and totals
        """
        result = {
            'present': attendance['PRESENT'],
            'public_holiday': attendance['PUBLIC_HOLIDAY'],
            'annual_leave_paid': 0,
            'annual_leave_unpaid': 0,
            'sick_leave_paid': 0,
            'sick_leave_unpaid': 0,
            'family_leave_paid': 0,
            'family_leave_unpaid': 0,
            'unpaid_leave': attendance['UNPAID'],
            'absent': attendance['ABSENT'],
            'suspended': attendance['SUSPENDED'],
        }
        
        # Annual leave
        annual_taken = attendance['ANNUAL']
        annual_paid = min(annual_taken, allowances['annual_leave'])
        result['annual_leave_paid'] = annual_paid
        result['annual_leave_unpaid'] = annual_taken - annual_paid
        
        # Sick leave
        sick_taken = attendance['SICK']
        sick_paid = min(sick_taken, allowances['sick_leave'])
        result['sick_leave_paid'] = sick_paid
        result['sick_leave_unpaid'] = sick_taken - sick_paid
        
        # Family leave
        family_taken = attendance['FAMILY']
        family_paid = min(family_taken, allowances['family_leave'])
        result['family_leave_paid'] = family_paid
        result['family_leave_unpaid'] = family_taken - family_paid
        
        # Calculate totals
        result['total_paid_days'] = (
            result['present'] +
            result['public_holiday'] +
            result['annual_leave_paid'] +
            result['sick_leave_paid'] +
            result['family_leave_paid']
        )
        
        result['total_unpaid_days'] = (
            result['annual_leave_unpaid'] +
            result['sick_leave_unpaid'] +
            result['family_leave_unpaid'] +
            result['unpaid_leave'] +
            result['absent'] +
            result['suspended']
        )
        
        return result
    
    def calculate(self, save: bool = True):
        """
        Perform the full stipend calculation.
        
        Args:
            save: If True, saves the calculation to database
            
        Returns:
            StipendCalculation instance (saved or unsaved)
        """
        from learners.models import StipendCalculation
        
        # Get daily rate
        daily_rate = self.placement.stipend_daily_rate
        if not daily_rate:
            logger.warning(f"No daily rate set for placement {self.placement.id}")
            daily_rate = Decimal('0')
        
        # Get attendance breakdown
        attendance = self.get_attendance_summary()
        allowances = self.get_leave_allowances()
        paid_breakdown = self.calculate_paid_days(attendance, allowances)
        
        # Calculate amounts
        gross_amount = daily_rate * paid_breakdown['total_paid_days']
        
        # Build deductions
        deductions = {}
        if paid_breakdown['total_unpaid_days'] > 0:
            deductions['unpaid_days'] = float(daily_rate * paid_breakdown['total_unpaid_days'])
        
        total_deductions = Decimal(sum(deductions.values())) if deductions else Decimal('0')
        net_amount = gross_amount  # Deductions already excluded from paid days
        
        # Create or update calculation
        calculation, created = StipendCalculation.objects.update_or_create(
            placement=self.placement,
            month=self.month,
            year=self.year,
            defaults={
                'total_working_days': self.total_working_days,
                'days_present': attendance['PRESENT'],
                'days_annual_leave': attendance['ANNUAL'],
                'days_sick_leave': attendance['SICK'],
                'days_family_leave': attendance['FAMILY'],
                'days_unpaid_leave': attendance['UNPAID'],
                'days_public_holiday': attendance['PUBLIC_HOLIDAY'],
                'days_absent': attendance['ABSENT'],
                'days_suspended': attendance['SUSPENDED'],
                'daily_rate': daily_rate,
                'gross_amount': gross_amount,
                'deductions': deductions,
                'total_deductions': total_deductions,
                'net_amount': net_amount,
                'status': 'CALCULATED',
                'calculated_at': timezone.now(),
            }
        )
        
        return calculation
    
    @classmethod
    def calculate_for_period(
        cls,
        placements,
        month: int,
        year: int,
        save: bool = True
    ) -> List:
        """
        Calculate stipends for multiple placements.
        
        Args:
            placements: QuerySet or list of WorkplacePlacement instances
            month: Month number
            year: Year
            save: If True, saves calculations to database
            
        Returns:
            List of StipendCalculation instances
        """
        calculations = []
        
        for placement in placements:
            if placement.status != 'ACTIVE':
                continue
                
            try:
                calculator = cls(placement, month, year)
                calculation = calculator.calculate(save=save)
                calculations.append(calculation)
            except Exception as e:
                logger.error(f"Failed to calculate stipend for placement {placement.id}: {e}")
        
        return calculations


class StipendReportGenerator:
    """
    Generate stipend reports for export and review.
    """
    
    @staticmethod
    def generate_monthly_summary(month: int, year: int, client=None) -> Dict:
        """
        Generate a summary report of all stipend calculations for a month.
        
        Args:
            month: Month number
            year: Year
            client: Optional CorporateClient to filter by
            
        Returns:
            Summary dict with totals and breakdown
        """
        from learners.models import StipendCalculation
        
        qs = StipendCalculation.objects.filter(month=month, year=year)
        
        if client:
            qs = qs.filter(
                Q(placement__host__employer__in=client.employees.values_list('employer', flat=True)) |
                Q(placement__lead_employer=client)
            )
        
        aggregates = qs.aggregate(
            total_calculations=Count('id'),
            total_gross=Sum('gross_amount'),
            total_deductions=Sum('total_deductions'),
            total_net=Sum('net_amount'),
            total_days_worked=Sum('days_present'),
        )
        
        status_breakdown = dict(
            qs.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        
        return {
            'month': month,
            'year': year,
            'total_calculations': aggregates['total_calculations'] or 0,
            'total_gross': aggregates['total_gross'] or Decimal('0'),
            'total_deductions': aggregates['total_deductions'] or Decimal('0'),
            'total_net': aggregates['total_net'] or Decimal('0'),
            'total_days_worked': aggregates['total_days_worked'] or 0,
            'status_breakdown': status_breakdown,
        }
    
    @staticmethod
    def export_to_csv(calculations, filename: str = None) -> str:
        """
        Export stipend calculations to CSV format.
        
        Args:
            calculations: QuerySet or list of StipendCalculation instances
            filename: Optional filename
            
        Returns:
            CSV content as string
        """
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Learner Number',
            'Learner Name',
            'Host Employer',
            'Month',
            'Year',
            'Days Present',
            'Leave Days',
            'Absent Days',
            'Daily Rate',
            'Gross Amount',
            'Deductions',
            'Net Amount',
            'Status',
        ])
        
        for calc in calculations:
            learner = calc.placement.learner
            writer.writerow([
                learner.learner_number,
                learner.get_full_name(),
                calc.placement.host.company_name,
                calc.month,
                calc.year,
                calc.days_present,
                calc.days_annual_leave + calc.days_sick_leave + calc.days_family_leave,
                calc.days_absent + calc.days_unpaid_leave,
                calc.daily_rate,
                calc.gross_amount,
                calc.total_deductions,
                calc.net_amount,
                calc.get_status_display(),
            ])
        
        return output.getvalue()
