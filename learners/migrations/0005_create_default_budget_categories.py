# Generated migration for default budget categories

from django.db import migrations


def create_default_categories(apps, schema_editor):
    """Create default SA-relevant budget categories"""
    BudgetCategory = apps.get_model('learners', 'BudgetCategory')
    
    default_categories = [
        # Income categories
        {
            'name': 'Stipend',
            'slug': 'stipend',
            'type': 'INCOME',
            'icon': '💰',
            'color': '#22c55e',
            'is_system_category': True,
            'sort_order': 1,
            'description': 'Monthly learnership stipend payment',
            'is_active': True,
        },
        {
            'name': 'Other Income',
            'slug': 'other-income',
            'type': 'INCOME',
            'icon': '💵',
            'color': '#10b981',
            'is_system_category': True,
            'sort_order': 2,
            'description': 'Additional income sources',
            'is_active': True,
        },
        
        # Expense categories - Transport
        {
            'name': 'Taxi',
            'slug': 'taxi',
            'type': 'EXPENSE',
            'icon': '🚕',
            'color': '#f59e0b',
            'is_system_category': True,
            'sort_order': 10,
            'description': 'Daily taxi fares and transport costs (R15-50/day typical)',
            'is_active': True,
        },
        
        # Expense categories - Communication
        {
            'name': 'Airtime',
            'slug': 'airtime',
            'type': 'EXPENSE',
            'icon': '📱',
            'color': '#3b82f6',
            'is_system_category': True,
            'sort_order': 20,
            'description': 'Mobile airtime and data (R50-200/month typical)',
            'is_active': True,
        },
        
        # Expense categories - Living
        {
            'name': 'Food',
            'slug': 'food',
            'type': 'EXPENSE',
            'icon': '🍽️',
            'color': '#10b981',
            'is_system_category': True,
            'sort_order': 30,
            'description': 'Daily meals and groceries (R30-100/day typical)',
            'is_active': True,
        },
        {
            'name': 'Accommodation',
            'slug': 'accommodation',
            'type': 'EXPENSE',
            'icon': '🏠',
            'color': '#8b5cf6',
            'is_system_category': True,
            'sort_order': 40,
            'description': 'Rent, hostel fees, or accommodation costs',
            'is_active': True,
        },
        
        # Expense categories - Financial
        {
            'name': 'Sending Money Home',
            'slug': 'sending-money-home',
            'type': 'EXPENSE',
            'icon': '💸',
            'color': '#ec4899',
            'is_system_category': True,
            'sort_order': 50,
            'description': 'Remittances to family members',
            'is_active': True,
        },
        {
            'name': 'Savings',
            'slug': 'savings',
            'type': 'EXPENSE',
            'icon': '💰',
            'color': '#22c55e',
            'is_system_category': True,
            'sort_order': 60,
            'description': 'Money set aside for savings goals',
            'is_active': True,
        },
        {
            'name': 'Emergency Fund',
            'slug': 'emergency-fund',
            'type': 'EXPENSE',
            'icon': '🛡️',
            'color': '#ef4444',
            'is_system_category': True,
            'sort_order': 65,
            'description': 'Building emergency reserves (3-6 months expenses)',
            'is_active': True,
        },
        {
            'name': 'Stokvel',
            'slug': 'stokvel',
            'type': 'EXPENSE',
            'icon': '🤝',
            'color': '#f97316',
            'is_system_category': True,
            'sort_order': 70,
            'description': 'Stokvel or group savings contributions',
            'is_active': True,
        },
        
        # Expense categories - Personal Development
        {
            'name': 'Education',
            'slug': 'education',
            'type': 'EXPENSE',
            'icon': '📚',
            'color': '#06b6d4',
            'is_system_category': True,
            'sort_order': 80,
            'description': 'Books, stationery, and learning materials',
            'is_active': True,
        },
        
        # Expense categories - Personal Care
        {
            'name': 'Clothing',
            'slug': 'clothing',
            'type': 'EXPENSE',
            'icon': '👕',
            'color': '#a855f7',
            'is_system_category': True,
            'sort_order': 90,
            'description': 'Clothing and footwear',
            'is_active': True,
        },
        {
            'name': 'Personal Care',
            'slug': 'personal-care',
            'type': 'EXPENSE',
            'icon': '🧴',
            'color': '#ec4899',
            'is_system_category': True,
            'sort_order': 100,
            'description': 'Toiletries, hygiene products',
            'is_active': True,
        },
        
        # Expense categories - Entertainment
        {
            'name': 'Entertainment',
            'slug': 'entertainment',
            'type': 'EXPENSE',
            'icon': '🎬',
            'color': '#f97316',
            'is_system_category': True,
            'sort_order': 110,
            'description': 'Leisure activities and entertainment',
            'is_active': True,
        },
        
        # Expense categories - Other
        {
            'name': 'Healthcare',
            'slug': 'healthcare',
            'type': 'EXPENSE',
            'icon': '🏥',
            'color': '#ef4444',
            'is_system_category': True,
            'sort_order': 120,
            'description': 'Medical expenses and clinic visits',
            'is_active': True,
        },
        {
            'name': 'Other Expenses',
            'slug': 'other-expenses',
            'type': 'EXPENSE',
            'icon': '📝',
            'color': '#6b7280',
            'is_system_category': True,
            'sort_order': 999,
            'description': 'Miscellaneous expenses',
            'is_active': True,
        },
    ]
    
    for category_data in default_categories:
        BudgetCategory.objects.get_or_create(
            slug=category_data['slug'],
            defaults=category_data
        )


def reverse_migration(apps, schema_editor):
    """Remove system categories on rollback"""
    BudgetCategory = apps.get_model('learners', 'BudgetCategory')
    BudgetCategory.objects.filter(is_system_category=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('learners', '0004_budgetcategory_expenseentry_financialliteracymodule_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_categories, reverse_migration),
    ]
