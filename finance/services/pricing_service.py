"""
Pricing Service for Course Pricing Management

Handles price resolution with hierarchical override system:
Level 1: Campus Override     → Most specific, wins first
Level 2: Region Modifier     → Apply region.price_modifier
Level 3: Corporate Strategy  → CorporateClient-linked pricing
Level 4: Brand Default       → Base CoursePricing for brand
Level 5: Intake Override     → Contract-negotiated (existing system)
"""
from decimal import Decimal
from datetime import date
from typing import Optional, Dict, Any, List
from django.db.models import Q
from django.utils import timezone


class PricingService:
    """
    Service class for managing course pricing operations.
    Provides price resolution, future pricing calculations, and workflow management.
    """
    
    def __init__(self, brand=None):
        """
        Initialize the pricing service.
        
        Args:
            brand: Optional Brand instance to scope operations to
        """
        self.brand = brand
    
    # ===== PRICE RESOLUTION =====
    
    def get_effective_price(
        self,
        qualification,
        campus=None,
        corporate_client=None,
        as_of_date: Optional[date] = None,
        include_breakdown: bool = False
    ) -> Dict[str, Any]:
        """
        Get the effective price for a qualification using the pricing hierarchy.
        
        Resolution order (highest priority first):
        1. Campus-specific pricing
        2. Region-modified pricing
        3. Corporate client pricing
        4. Brand default pricing
        
        Args:
            qualification: Qualification instance
            campus: Optional Campus for location-specific pricing
            corporate_client: Optional CorporateClient for corporate pricing
            as_of_date: Date for price lookup (defaults to today)
            include_breakdown: Include detailed fee breakdown
            
        Returns:
            Dict with price information and resolution details
        """
        from finance.models import CoursePricing, PricingStrategy, CoursePricingOverride
        from core.models import Region
        
        target_date = as_of_date or date.today()
        brand = campus.brand if campus else (self.brand or qualification.brand if hasattr(qualification, 'brand') else None)
        
        result = {
            'qualification': qualification,
            'as_of_date': target_date,
            'total_price': None,
            'total_price_vat_inclusive': None,
            'deposit_amount': None,
            'resolution_source': None,
            'pricing': None,
            'applied_modifier': Decimal('1.0000'),
            'strategy': None,
        }
        
        # 1. Check for campus-specific pricing
        if campus:
            campus_pricing = self._find_pricing_by_strategy_type(
                qualification, 'CAMPUS', target_date, campus=campus
            )
            if campus_pricing:
                result.update(self._build_price_result(campus_pricing, 'CAMPUS'))
                if include_breakdown:
                    result['breakdown'] = self._get_fee_breakdown(campus_pricing)
                return result
        
        # 2. Check for region-modified pricing (apply modifier to base)
        if campus and campus.region:
            # Try to get region from ForeignKey or string
            region = None
            if hasattr(campus.region, 'price_modifier'):
                region = campus.region
            else:
                # Legacy: region is still a CharField, try to look up
                try:
                    region = Region.objects.get(code=campus.region)
                except Region.DoesNotExist:
                    try:
                        region = Region.objects.get(name=campus.region)
                    except Region.DoesNotExist:
                        pass
            
            if region and region.price_modifier != Decimal('1.0000'):
                # Get base pricing and apply modifier
                base_pricing = self._find_default_pricing(qualification, brand, target_date)
                if base_pricing:
                    modified_price = base_pricing.total_price * region.effective_price_modifier
                    result.update({
                        'total_price': round(modified_price, 2),
                        'total_price_vat_inclusive': round(
                            modified_price * (1 + base_pricing.vat_rate / 100), 2
                        ) if not base_pricing.prices_include_vat else round(modified_price, 2),
                        'deposit_amount': self._calculate_deposit(base_pricing, modified_price),
                        'resolution_source': 'REGION_MODIFIED',
                        'pricing': base_pricing,
                        'applied_modifier': region.effective_price_modifier,
                        'strategy': base_pricing.pricing_strategy,
                        'region': region,
                    })
                    if include_breakdown:
                        result['breakdown'] = self._get_fee_breakdown(
                            base_pricing, 
                            modifier=region.effective_price_modifier
                        )
                    return result
        
        # 3. Check for corporate client pricing
        if corporate_client:
            corporate_pricing = self._find_pricing_by_strategy_type(
                qualification, 'CORPORATE', target_date, corporate_client=corporate_client
            )
            if corporate_pricing:
                result.update(self._build_price_result(corporate_pricing, 'CORPORATE'))
                if include_breakdown:
                    result['breakdown'] = self._get_fee_breakdown(corporate_pricing)
                return result
        
        # 4. Fall back to brand default pricing
        default_pricing = self._find_default_pricing(qualification, brand, target_date)
        if default_pricing:
            result.update(self._build_price_result(default_pricing, 'BRAND_DEFAULT'))
            if include_breakdown:
                result['breakdown'] = self._get_fee_breakdown(default_pricing)
            return result
        
        # No pricing found
        result['resolution_source'] = 'NOT_FOUND'
        return result
    
    def _find_pricing_by_strategy_type(
        self, 
        qualification, 
        strategy_type: str, 
        target_date: date,
        campus=None,
        corporate_client=None
    ):
        """Find active pricing for a specific strategy type."""
        from finance.models import CoursePricing, PricingStrategy
        
        strategy_filter = {'strategy_type': strategy_type, 'is_active': True}
        if campus:
            strategy_filter['campus'] = campus
        if corporate_client:
            strategy_filter['corporate_client'] = corporate_client
        
        strategies = PricingStrategy.objects.filter(**strategy_filter)
        
        return CoursePricing.objects.filter(
            qualification=qualification,
            pricing_strategy__in=strategies,
            status='ACTIVE',
            effective_from__lte=target_date
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)
        ).order_by('-pricing_strategy__priority', '-effective_from').first()
    
    def _find_default_pricing(self, qualification, brand, target_date: date):
        """Find the default brand pricing."""
        from finance.models import CoursePricing, PricingStrategy
        
        # First try to find pricing with is_default strategy
        default_strategy = PricingStrategy.objects.filter(
            brand=brand,
            strategy_type='STANDARD',
            is_default=True,
            is_active=True
        ).first()
        
        if default_strategy:
            pricing = CoursePricing.objects.filter(
                qualification=qualification,
                pricing_strategy=default_strategy,
                status='ACTIVE',
                effective_from__lte=target_date
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)
            ).order_by('-effective_from').first()
            
            if pricing:
                return pricing
        
        # Fall back to any STANDARD strategy
        return CoursePricing.objects.filter(
            qualification=qualification,
            pricing_strategy__brand=brand,
            pricing_strategy__strategy_type='STANDARD',
            pricing_strategy__is_active=True,
            status='ACTIVE',
            effective_from__lte=target_date
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)
        ).order_by('-pricing_strategy__priority', '-effective_from').first()
    
    def _build_price_result(self, pricing, source: str) -> Dict[str, Any]:
        """Build the price result dictionary from a pricing instance."""
        return {
            'total_price': pricing.total_price,
            'total_price_vat_inclusive': pricing.total_price_vat_inclusive,
            'deposit_amount': pricing.calculated_deposit,
            'resolution_source': source,
            'pricing': pricing,
            'strategy': pricing.pricing_strategy,
        }
    
    def _calculate_deposit(self, pricing, modified_price: Decimal) -> Decimal:
        """Calculate deposit for a modified price."""
        if not pricing.deposit_required:
            return Decimal('0.00')
        if pricing.deposit_type == 'PERCENTAGE':
            vat_inclusive = modified_price
            if not pricing.prices_include_vat:
                vat_inclusive = modified_price * (1 + pricing.vat_rate / 100)
            return round((vat_inclusive * pricing.deposit_percentage) / 100, 2)
        return pricing.deposit_amount
    
    def _get_fee_breakdown(self, pricing, modifier: Decimal = Decimal('1.0000')) -> Dict[str, Decimal]:
        """Get detailed fee breakdown, optionally with modifier applied."""
        return {
            'tuition_fee': round(pricing.tuition_fee * modifier, 2),
            'registration_fee': round(pricing.registration_fee * modifier, 2),
            'material_fee': round(pricing.material_fee * modifier, 2),
            'assessment_fee': round(pricing.assessment_fee * modifier, 2),
            'certification_fee': round(pricing.certification_fee * modifier, 2),
            'vat_rate': pricing.vat_rate,
            'prices_include_vat': pricing.prices_include_vat,
        }
    
    # ===== FUTURE PRICING =====
    
    def calculate_future_prices(
        self,
        base_price: Decimal,
        escalation_percent: Decimal,
        years: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Calculate future prices with escalation.
        
        Args:
            base_price: Starting price
            escalation_percent: Annual escalation percentage
            years: Number of years to calculate
            
        Returns:
            List of dicts with year, price, and cumulative escalation
        """
        results = []
        current_price = base_price
        cumulative = Decimal('1.0000')
        
        for year_offset in range(years):
            if year_offset == 0:
                # Base year - no escalation
                results.append({
                    'year_offset': year_offset,
                    'price': current_price,
                    'escalation_applied': Decimal('0.00'),
                    'cumulative_escalation': cumulative,
                })
            else:
                escalation_multiplier = 1 + (escalation_percent / 100)
                current_price = round(current_price * escalation_multiplier, 2)
                cumulative = cumulative * escalation_multiplier
                results.append({
                    'year_offset': year_offset,
                    'price': current_price,
                    'escalation_applied': escalation_percent,
                    'cumulative_escalation': round(cumulative, 4),
                })
        
        return results
    
    def apply_future_pricing_schedule(self, schedule, user) -> int:
        """
        Apply a future pricing schedule to create new pricing versions.
        
        Args:
            schedule: FuturePricingSchedule instance
            user: User performing the action
            
        Returns:
            Number of pricing records created
        """
        return schedule.apply_to_pricing(user)
    
    # ===== WORKFLOW METHODS =====
    
    def submit_for_approval(self, pricing, user) -> None:
        """Submit pricing for approval."""
        pricing.submit_for_approval(user)
    
    def approve_pricing(self, pricing, user, notes: str = '') -> None:
        """Approve a pending pricing."""
        pricing.approve(user, notes)
    
    def reject_pricing(self, pricing, user, reason: str) -> None:
        """Reject a pending pricing."""
        pricing.reject(user, reason)
    
    def activate_pricing(self, pricing, user) -> None:
        """Activate an approved pricing."""
        pricing.activate(user)
    
    def create_new_version(self, pricing, user):
        """Create a new version of existing pricing."""
        from finance.models import CoursePricing
        return CoursePricing.create_new_version(pricing, user)
    
    # ===== PAYMENT CALCULATIONS =====
    
    def get_payment_options(self, pricing) -> List[Dict[str, Any]]:
        """
        Get all available payment options for a pricing.
        
        Args:
            pricing: CoursePricing instance
            
        Returns:
            List of payment option dicts with calculated amounts
        """
        options = []
        
        for cpt in pricing.available_payment_terms.filter(is_available=True).select_related('payment_term'):
            term = cpt.payment_term
            
            # Calculate amounts with any overrides
            discount = cpt.effective_discount
            instalments = cpt.effective_instalments
            admin_fee = cpt.effective_admin_fee
            
            total = pricing.total_price_vat_inclusive
            
            # Apply discount
            if discount > 0:
                total = total * (1 - discount / 100)
            
            # Add admin fee
            total = total + admin_fee
            
            deposit = pricing.calculated_deposit
            instalment_amount = term.calculate_instalment_amount(total, deposit)
            
            options.append({
                'payment_term': term,
                'course_payment_term': cpt,
                'is_default': cpt.is_default,
                'total_amount': round(total, 2),
                'deposit_amount': deposit,
                'instalment_amount': instalment_amount,
                'number_of_instalments': instalments,
                'discount_applied': discount,
                'admin_fee': admin_fee,
                'description': term.description or term.name,
            })
        
        return sorted(options, key=lambda x: (not x['is_default'], x['total_amount']))
    
    def generate_payment_schedule(
        self,
        pricing,
        payment_term,
        start_date: date
    ) -> List[Dict[str, Any]]:
        """
        Generate a payment schedule for a pricing and payment term.
        
        Args:
            pricing: CoursePricing instance
            payment_term: PaymentTerm or CoursePricingPaymentTerm instance
            start_date: When payments begin
            
        Returns:
            List of payment schedule entries
        """
        from finance.models import CoursePricingPaymentTerm
        
        # Handle both PaymentTerm and CoursePricingPaymentTerm
        if isinstance(payment_term, CoursePricingPaymentTerm):
            term = payment_term.payment_term
            deposit = pricing.calculated_deposit
        else:
            term = payment_term
            deposit = pricing.calculated_deposit
        
        total = pricing.total_price_vat_inclusive
        return term.get_payment_schedule(total, deposit, start_date)
    
    # ===== REPORTING =====
    
    def get_pricing_summary(self, qualification, brand=None) -> Dict[str, Any]:
        """
        Get a summary of all pricing for a qualification.
        
        Args:
            qualification: Qualification instance
            brand: Optional Brand to filter by
            
        Returns:
            Dict with pricing summary information
        """
        from finance.models import CoursePricing
        
        queryset = CoursePricing.objects.filter(qualification=qualification)
        if brand:
            queryset = queryset.filter(pricing_strategy__brand=brand)
        
        active = queryset.filter(status='ACTIVE')
        future = queryset.filter(status__in=['APPROVED', 'ACTIVE'], effective_from__gt=date.today())
        pending = queryset.filter(status='PENDING_APPROVAL')
        
        return {
            'qualification': qualification,
            'total_versions': queryset.count(),
            'active_count': active.count(),
            'future_count': future.count(),
            'pending_approval_count': pending.count(),
            'active_pricing': list(active.select_related('pricing_strategy')),
            'future_pricing': list(future.select_related('pricing_strategy').order_by('effective_from')),
            'pending_pricing': list(pending.select_related('pricing_strategy')),
        }
    
    def compare_pricing_versions(self, pricing1, pricing2) -> Dict[str, Any]:
        """
        Compare two pricing versions and return differences.
        
        Args:
            pricing1: First CoursePricing instance
            pricing2: Second CoursePricing instance
            
        Returns:
            Dict with comparison results
        """
        fields_to_compare = [
            'total_price', 'deposit_amount', 'deposit_percentage',
            'registration_fee', 'material_fee', 'assessment_fee', 
            'certification_fee', 'vat_rate'
        ]
        
        differences = []
        for field in fields_to_compare:
            val1 = getattr(pricing1, field)
            val2 = getattr(pricing2, field)
            if val1 != val2:
                diff_pct = None
                if val1 and val2 and val1 > 0:
                    diff_pct = round(((val2 - val1) / val1) * 100, 2)
                differences.append({
                    'field': field,
                    'old_value': val1,
                    'new_value': val2,
                    'difference': val2 - val1 if val1 and val2 else None,
                    'difference_percent': diff_pct,
                })
        
        return {
            'pricing1': pricing1,
            'pricing2': pricing2,
            'differences': differences,
            'has_changes': len(differences) > 0,
            'total_price_change': pricing2.total_price - pricing1.total_price,
            'total_price_change_percent': round(
                ((pricing2.total_price - pricing1.total_price) / pricing1.total_price) * 100, 2
            ) if pricing1.total_price > 0 else None,
        }
