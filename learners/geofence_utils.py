"""
Geofencing utilities for attendance verification.

Implements Haversine formula for calculating distance between GPS coordinates
and checking if a point falls within a geofenced area.
"""
import math


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth (in meters).
    Uses the Haversine formula.
    
    Args:
        lat1, lon1: Latitude and longitude of first point (decimal degrees)
        lat2, lon2: Latitude and longitude of second point (decimal degrees)
    
    Returns:
        Distance in meters (float)
    """
    # Convert decimal degrees to radians
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in meters
    earth_radius_m = 6371000
    
    # Calculate distance
    distance = earth_radius_m * c
    
    return distance


def is_within_geofence(check_lat, check_lon, center_lat, center_lon, radius_meters):
    """
    Check if a GPS coordinate is within a geofenced radius.
    
    Args:
        check_lat, check_lon: Coordinates to check (decimal degrees)
        center_lat, center_lon: Center of geofence (decimal degrees)
        radius_meters: Geofence radius in meters
    
    Returns:
        (within_fence: bool, distance: float)
        - within_fence: True if coordinate is within geofence
        - distance: Actual distance from center in meters
    """
    distance = haversine_distance(check_lat, check_lon, center_lat, center_lon)
    within_fence = distance <= radius_meters
    
    return within_fence, distance


def format_distance(distance_meters):
    """
    Format distance in meters to human-readable string.
    
    Args:
        distance_meters: Distance in meters (float)
    
    Returns:
        Formatted string (e.g., "1.2 km" or "350 m")
    """
    if distance_meters >= 1000:
        return f"{distance_meters / 1000:.1f} km"
    else:
        return f"{int(distance_meters)} m"


def get_geofence_status(attendance):
    """
    Get comprehensive geofence status for an attendance record.
    
    Args:
        attendance: WorkplaceAttendance instance
    
    Returns:
        Dictionary with:
        - has_gps: bool - whether attendance has GPS data
        - has_employer_location: bool - whether employer has GPS coordinates
        - can_check: bool - whether geofence check is possible
        - within_fence: bool or None - whether within geofence (None if can't check)
        - distance: float or None - distance in meters (None if can't check)
        - distance_display: str - formatted distance string
        - radius: int - geofence radius in meters
        - status_class: str - CSS class for badge (green/yellow/red)
        - status_text: str - human-readable status
    """
    result = {
        'has_gps': False,
        'has_employer_location': False,
        'can_check': False,
        'within_fence': None,
        'distance': None,
        'distance_display': '—',
        'radius': 5000,
        'status_class': 'gray',
        'status_text': 'No GPS data',
    }
    
    # Check if attendance has GPS coordinates
    if attendance.gps_latitude and attendance.gps_longitude:
        result['has_gps'] = True
    else:
        return result
    
    # Check if employer has GPS coordinates
    employer = attendance.placement.host_employer
    if not (employer.gps_latitude and employer.gps_longitude):
        result['status_text'] = 'Employer location not set'
        return result
    
    result['has_employer_location'] = True
    result['can_check'] = True
    result['radius'] = employer.geofence_radius_meters
    
    # Calculate distance and check geofence
    within_fence, distance = is_within_geofence(
        attendance.gps_latitude,
        attendance.gps_longitude,
        employer.gps_latitude,
        employer.gps_longitude,
        employer.geofence_radius_meters
    )
    
    result['within_fence'] = within_fence
    result['distance'] = distance
    result['distance_display'] = format_distance(distance)
    
    # Determine status
    if within_fence:
        result['status_class'] = 'green'
        result['status_text'] = f'✓ Within geofence ({result["distance_display"]})'
    else:
        result['status_class'] = 'red'
        result['status_text'] = f'⚠ Outside geofence ({result["distance_display"]})'
    
    return result
