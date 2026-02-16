"""
Custom template tags for admin views
"""
from django import template

register = template.Library()


@register.filter
def attr(obj, attribute):
    """
    Get attribute from object dynamically
    Usage: {{ object|attr:field_name }}
    """
    try:
        # First try to get the attribute directly
        value = getattr(obj, attribute, None)
        
        # If it's a callable (like a method), call it
        if callable(value):
            try:
                value = value()
            except:
                pass
        
        # Handle choice fields - try to get display value
        display_method = f'get_{attribute}_display'
        if hasattr(obj, display_method):
            try:
                return getattr(obj, display_method)()
            except:
                pass
        
        return value
    except:
        return None


@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary
    Usage: {{ dict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def status_color(status):
    """
    Return appropriate color class based on status
    Usage: {{ status|status_color }}
    """
    status_colors = {
        # General statuses
        'ACTIVE': 'green',
        'INACTIVE': 'gray',
        'PENDING': 'yellow',
        'COMPLETED': 'blue',
        'CANCELLED': 'red',
        
        # Enrollment statuses
        'APPLIED': 'blue',
        'DOC_CHECK': 'yellow',
        'REGISTERED': 'indigo',
        'ENROLLED': 'green',
        'ON_HOLD': 'yellow',
        'CERTIFIED': 'purple',
        'WITHDRAWN': 'red',
        'TRANSFERRED': 'orange',
        'EXPIRED': 'gray',
        
        # Assessment statuses
        'SUBMITTED': 'blue',
        'ASSESSED': 'indigo',
        'MODERATED': 'purple',
        'FINALIZED': 'green',
        
        # Result statuses
        'C': 'green',  # Competent
        'NYC': 'red',  # Not Yet Competent
        
        # Invoice/Payment statuses
        'DRAFT': 'gray',
        'SENT': 'blue',
        'PAID': 'green',
        'OVERDUE': 'red',
        'PARTIALLY_PAID': 'yellow',
        'VOID': 'gray',
        
        # Session statuses
        'SCHEDULED': 'blue',
        'IN_PROGRESS': 'yellow',
        'DONE': 'green',
        
        # Corporate statuses
        'PROSPECT': 'gray',
        'APPROVED': 'green',
        'CONTRACTED': 'indigo',
        'REPORTING': 'purple',
        'CLOSED': 'gray',
    }
    
    return status_colors.get(str(status).upper(), 'gray')


@register.filter
def truncate_chars(value, max_length):
    """
    Truncate string to max_length characters
    Usage: {{ value|truncate_chars:50 }}
    """
    if value is None:
        return ''
    value = str(value)
    if len(value) <= max_length:
        return value
    return value[:max_length] + '...'


@register.simple_tag
def url_replace(request, field, value):
    """
    Replace a GET parameter in the URL
    Usage: {% url_replace request 'page' 2 %}
    """
    query = request.GET.copy()
    query[field] = value
    return query.urlencode()


@register.filter
def percentage(value, total):
    """
    Calculate percentage
    Usage: {{ value|percentage:total }}
    """
    try:
        if total == 0:
            return 0
        return int((value / total) * 100)
    except:
        return 0


@register.filter
def widget_type(field):
    """
    Get the widget type/class name for a form field
    Usage: {{ field|widget_type }}
    """
    try:
        return field.field.widget.__class__.__name__
    except:
        return ''


@register.filter
def replace(value, args):
    """
    Replace a string with another
    Usage: {{ value|replace:"old,new" }}
    """
    try:
        old, new = args.split(',')
        return str(value).replace(old, new)
    except:
        return value


@register.filter
def abs_value(value):
    """
    Return absolute value of a number
    Usage: {{ value|abs_value }}
    """
    try:
        return abs(int(value))
    except (ValueError, TypeError):
        return value


@register.filter
def split(value, delimiter=','):
    """
    Split a string by delimiter
    Usage: {{ "a,b,c"|split:"," }}
    """
    try:
        return str(value).split(delimiter)
    except:
        return [value]
