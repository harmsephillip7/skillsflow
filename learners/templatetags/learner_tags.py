"""
Custom template tags for learner management views
"""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a variable key
    Usage: {{ mydict|get_item:keyvar }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def percentage(value, total):
    """
    Calculate percentage
    Usage: {{ value|percentage:total }}
    """
    try:
        return (float(value) / float(total)) * 100
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def multiply(value, arg):
    """
    Multiply a value by an argument
    Usage: {{ value|multiply:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def subtract(value, arg):
    """
    Subtract arg from value
    Usage: {{ value|subtract:arg }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """
    Divide value by arg
    Usage: {{ value|divide:arg }}
    """
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.simple_tag
def status_color(status):
    """
    Get the Tailwind color class for an enrollment status
    """
    colors = {
        'APPLIED': 'slate',
        'DOC_CHECK': 'amber',
        'REGISTERED': 'blue',
        'ENROLLED': 'indigo',
        'ACTIVE': 'green',
        'ON_HOLD': 'orange',
        'COMPLETED': 'teal',
        'CERTIFIED': 'emerald',
        'WITHDRAWN': 'red',
        'TRANSFERRED': 'purple',
        'EXPIRED': 'gray',
    }
    return colors.get(status, 'gray')
