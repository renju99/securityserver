# -*- coding: utf-8 -*-
"""Geographic Utility Functions.

This module provides reusable geographic calculation functions
for the GuardPro module, including distance calculations and
geofence validation.
"""

import math
import json
import logging
from .constants import EARTH_RADIUS_METERS, EARTH_RADIUS_KM

_logger = logging.getLogger(__name__)


def haversine_distance(lat1, lon1, lat2, lon2, unit='meters'):
    """
    Calculate distance between two GPS points using Haversine formula.
    
    The Haversine formula calculates the great-circle distance between
    two points on a sphere given their longitudes and latitudes.
    
    Args:
        lat1 (float): Latitude of first point in degrees
        lon1 (float): Longitude of first point in degrees
        lat2 (float): Latitude of second point in degrees
        lon2 (float): Longitude of second point in degrees
        unit (str): Unit of measurement ('meters' or 'km'), default 'meters'
        
    Returns:
        float: Distance between the two points in specified unit
        
    Example:
        >>> distance = haversine_distance(25.2048, 55.2708, 25.1972, 55.2744)
        >>> print(f"Distance: {distance:.2f} meters")
        Distance: 1234.56 meters
    """
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Calculate distance
    if unit == 'km':
        return EARTH_RADIUS_KM * c
    else:  # meters (default)
        return EARTH_RADIUS_METERS * c


def validate_coordinates(latitude, longitude):
    """
    Validate GPS coordinates.
    
    Args:
        latitude (float): Latitude value to validate
        longitude (float): Longitude value to validate
        
    Returns:
        tuple: (is_valid, error_message)
        
    Example:
        >>> valid, error = validate_coordinates(25.2048, 55.2708)
        >>> print(valid)  # True
        >>> valid, error = validate_coordinates(95.0, 55.2708)
        >>> print(error)  # "Latitude must be between -90 and 90"
    """
    # Check if values are numeric
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return False, "Coordinates must be numeric values"
    
    # Validate latitude range
    if not (-90 <= latitude <= 90):
        return False, "Latitude must be between -90 and 90"
    
    # Validate longitude range
    if not (-180 <= longitude <= 180):
        return False, "Longitude must be between -180 and 180"
    
    return True, None


def check_point_in_circle(point_lat, point_lon, center_lat, center_lon, radius_meters):
    """
    Check if a point is within a circular geofence.
    
    Args:
        point_lat (float): Latitude of point to check
        point_lon (float): Longitude of point to check
        center_lat (float): Latitude of circle center
        center_lon (float): Longitude of circle center
        radius_meters (float): Radius of circle in meters
        
    Returns:
        bool: True if point is within circle, False otherwise
        
    Example:
        >>> inside = check_point_in_circle(25.2048, 55.2708, 25.2050, 55.2710, 500)
        >>> print(inside)  # True if within 500 meters
    """
    distance = haversine_distance(center_lat, center_lon, point_lat, point_lon)
    return distance <= radius_meters


def check_point_in_polygon(point_lat, point_lon, polygon_coords):
    """
    Check if a point is within a polygon geofence using ray casting algorithm.
    
    The ray casting algorithm counts how many times a ray starting from the point
    crosses the polygon boundary. If the number of crossings is odd, the point is inside.
    
    Args:
        point_lat (float): Latitude of point to check
        point_lon (float): Longitude of point to check
        polygon_coords (str or list): JSON string or list of coordinates
                                      Format: [{"lat": 25.20, "lng": 55.27}, ...]
        
    Returns:
        bool: True if point is within polygon, False otherwise
        
    Example:
        >>> polygon = '[{"lat": 25.20, "lng": 55.27}, {"lat": 25.21, "lng": 55.27}, ...]'
        >>> inside = check_point_in_polygon(25.205, 55.275, polygon)
    """
    try:
        # Parse polygon coordinates if it's a JSON string
        if isinstance(polygon_coords, str):
            polygon = json.loads(polygon_coords)
        else:
            polygon = polygon_coords
        
        # Validate polygon has at least 3 points
        if not isinstance(polygon, list) or len(polygon) < 3:
            _logger.warning('Invalid polygon: must have at least 3 points')
            return False
        
        # Ray casting algorithm
        inside = False
        j = len(polygon) - 1
        
        for i in range(len(polygon)):
            # Get coordinates of polygon edge
            xi, yi = polygon[i]['lng'], polygon[i]['lat']
            xj, yj = polygon[j]['lng'], polygon[j]['lat']
            
            # Check if ray from point crosses edge
            if ((yi > point_lat) != (yj > point_lat)) and \
               (point_lon < (xj - xi) * (point_lat - yi) / (yj - yi) + xi):
                inside = not inside
            
            j = i
        
        return inside
        
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        _logger.error('Error checking point in polygon: %s', str(e))
        return False


def calculate_polygon_area(polygon_coords):
    """
    Calculate the area of a polygon in square meters.
    
    Uses the Shoelace formula (also known as surveyor's formula).
    
    Args:
        polygon_coords (str or list): JSON string or list of coordinates
                                      Format: [{"lat": 25.20, "lng": 55.27}, ...]
        
    Returns:
        float: Area in square meters, or None if calculation fails
    """
    try:
        # Parse polygon coordinates if it's a JSON string
        if isinstance(polygon_coords, str):
            polygon = json.loads(polygon_coords)
        else:
            polygon = polygon_coords
        
        if not isinstance(polygon, list) or len(polygon) < 3:
            return None
        
        # Convert to radians and calculate area
        area = 0.0
        
        for i in range(len(polygon)):
            j = (i + 1) % len(polygon)
            
            lat1 = math.radians(polygon[i]['lat'])
            lat2 = math.radians(polygon[j]['lat'])
            lon1 = math.radians(polygon[i]['lng'])
            lon2 = math.radians(polygon[j]['lng'])
            
            area += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
        
        area = abs(area * EARTH_RADIUS_METERS * EARTH_RADIUS_METERS / 2.0)
        
        return area
        
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        _logger.error('Error calculating polygon area: %s', str(e))
        return None


def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate the bearing (direction) from one point to another.
    
    Args:
        lat1 (float): Latitude of starting point
        lon1 (float): Longitude of starting point
        lat2 (float): Latitude of ending point
        lon2 (float): Longitude of ending point
        
    Returns:
        float: Bearing in degrees (0-360), where 0/360 is North, 90 is East, etc.
        
    Example:
        >>> bearing = calculate_bearing(25.2048, 55.2708, 25.2148, 55.2808)
        >>> print(f"Bearing: {bearing:.1f}° ({get_cardinal_direction(bearing)})")
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    
    bearing_rad = math.atan2(x, y)
    bearing_deg = math.degrees(bearing_rad)
    
    # Normalize to 0-360
    return (bearing_deg + 360) % 360


def get_cardinal_direction(bearing):
    """
    Convert bearing to cardinal direction.
    
    Args:
        bearing (float): Bearing in degrees (0-360)
        
    Returns:
        str: Cardinal direction (N, NE, E, SE, S, SW, W, NW)
        
    Example:
        >>> direction = get_cardinal_direction(45)
        >>> print(direction)  # "NE"
    """
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    index = int((bearing + 22.5) / 45) % 8
    return directions[index]


def calculate_path_distance(coordinates):
    """
    Calculate total distance of a path defined by multiple GPS coordinates.
    
    Args:
        coordinates (list): List of coordinate dictionaries
                          Format: [{"lat": 25.20, "lng": 55.27}, ...]
        
    Returns:
        float: Total distance in meters
        
    Example:
        >>> path = [{"lat": 25.20, "lng": 55.27}, {"lat": 25.21, "lng": 55.28}, ...]
        >>> distance = calculate_path_distance(path)
        >>> print(f"Path length: {distance:.2f} meters")
    """
    if not coordinates or len(coordinates) < 2:
        return 0.0
    
    total_distance = 0.0
    
    for i in range(1, len(coordinates)):
        prev = coordinates[i - 1]
        curr = coordinates[i]
        
        try:
            distance = haversine_distance(
                prev['lat'], prev['lng'],
                curr['lat'], curr['lng']
            )
            total_distance += distance
        except (KeyError, TypeError) as e:
            _logger.warning('Invalid coordinate at index %d: %s', i, str(e))
            continue
    
    return total_distance


def get_bounding_box(coordinates, padding_meters=0):
    """
    Calculate bounding box for a set of coordinates.
    
    Args:
        coordinates (list): List of coordinate dictionaries
        padding_meters (float): Additional padding in meters (optional)
        
    Returns:
        dict: Bounding box with min/max lat/lng
              Format: {"min_lat": float, "max_lat": float, "min_lng": float, "max_lng": float}
    """
    if not coordinates:
        return None
    
    lats = [coord['lat'] for coord in coordinates if 'lat' in coord]
    lngs = [coord['lng'] for coord in coordinates if 'lng' in coord]
    
    if not lats or not lngs:
        return None
    
    # Calculate basic bounding box
    bbox = {
        'min_lat': min(lats),
        'max_lat': max(lats),
        'min_lng': min(lngs),
        'max_lng': max(lngs)
    }
    
    # Apply padding if specified
    if padding_meters > 0:
        # Approximate degrees per meter (rough approximation)
        lat_degrees_per_meter = 1 / 111000
        lng_degrees_per_meter = 1 / (111000 * math.cos(math.radians(bbox['min_lat'])))
        
        padding_lat = padding_meters * lat_degrees_per_meter
        padding_lng = padding_meters * lng_degrees_per_meter
        
        bbox['min_lat'] -= padding_lat
        bbox['max_lat'] += padding_lat
        bbox['min_lng'] -= padding_lng
        bbox['max_lng'] += padding_lng
    
    return bbox


def format_distance(distance_meters):
    """
    Format distance in human-readable form.
    
    Args:
        distance_meters (float): Distance in meters
        
    Returns:
        str: Formatted distance string
        
    Example:
        >>> print(format_distance(500))    # "500 m"
        >>> print(format_distance(1500))   # "1.5 km"
        >>> print(format_distance(15000))  # "15.0 km"
    """
    if distance_meters < 1000:
        return f"{distance_meters:.0f} m"
    else:
        return f"{distance_meters / 1000:.1f} km"



