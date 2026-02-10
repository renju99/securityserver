# -*- coding: utf-8 -*-
"""Unit Tests for Geographic Utilities."""

from odoo.tests import TransactionCase, tagged
from ..common import geo_utils


@tagged('post_install', '-at_install', 'guardpro')
class TestGeoUtils(TransactionCase):
    """Test cases for geo_utils module."""
    
    def test_haversine_distance_meters(self):
        """Test Haversine distance calculation in meters."""
        # Dubai Marina coordinates (approximately 1km apart)
        lat1, lon1 = 25.0819, 55.1391
        lat2, lon2 = 25.0909, 55.1391
        
        distance = geo_utils.haversine_distance(lat1, lon1, lat2, lon2, unit='meters')
        
        # Should be approximately 1000 meters (allow 5% tolerance)
        self.assertAlmostEqual(distance, 1000, delta=50)
    
    def test_haversine_distance_km(self):
        """Test Haversine distance calculation in kilometers."""
        lat1, lon1 = 25.0819, 55.1391
        lat2, lon2 = 25.0909, 55.1391
        
        distance = geo_utils.haversine_distance(lat1, lon1, lat2, lon2, unit='km')
        
        # Should be approximately 1 km
        self.assertAlmostEqual(distance, 1.0, delta=0.05)
    
    def test_validate_coordinates_valid(self):
        """Test validation of valid GPS coordinates."""
        # Valid coordinates (Dubai)
        valid, error = geo_utils.validate_coordinates(25.2048, 55.2708)
        
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_validate_coordinates_invalid_latitude(self):
        """Test validation of invalid latitude."""
        # Latitude out of range
        valid, error = geo_utils.validate_coordinates(95.0, 55.2708)
        
        self.assertFalse(valid)
        self.assertIn('Latitude', error)
    
    def test_validate_coordinates_invalid_longitude(self):
        """Test validation of invalid longitude."""
        # Longitude out of range
        valid, error = geo_utils.validate_coordinates(25.2048, 185.0)
        
        self.assertFalse(valid)
        self.assertIn('Longitude', error)
    
    def test_check_point_in_circle_inside(self):
        """Test point inside circular geofence."""
        # Center of circle
        center_lat, center_lon = 25.2048, 55.2708
        
        # Point 100 meters away (should be inside 500m radius)
        point_lat, point_lon = 25.2058, 55.2708
        
        inside = geo_utils.check_point_in_circle(
            point_lat, point_lon,
            center_lat, center_lon,
            radius_meters=500
        )
        
        self.assertTrue(inside)
    
    def test_check_point_in_circle_outside(self):
        """Test point outside circular geofence."""
        center_lat, center_lon = 25.2048, 55.2708
        
        # Point 1000 meters away (should be outside 500m radius)
        point_lat, point_lon = 25.2148, 55.2708
        
        inside = geo_utils.check_point_in_circle(
            point_lat, point_lon,
            center_lat, center_lon,
            radius_meters=500
        )
        
        self.assertFalse(inside)
    
    def test_check_point_in_polygon(self):
        """Test point in polygon using ray casting."""
        # Simple square polygon
        polygon = [
            {"lat": 25.200, "lng": 55.270},
            {"lat": 25.210, "lng": 55.270},
            {"lat": 25.210, "lng": 55.280},
            {"lat": 25.200, "lng": 55.280}
        ]
        
        # Point inside square
        inside = geo_utils.check_point_in_polygon(25.205, 55.275, polygon)
        self.assertTrue(inside)
        
        # Point outside square
        outside = geo_utils.check_point_in_polygon(25.190, 55.275, polygon)
        self.assertFalse(outside)
    
    def test_calculate_bearing(self):
        """Test bearing calculation."""
        # Moving north
        bearing = geo_utils.calculate_bearing(25.200, 55.270, 25.210, 55.270)
        
        # Should be approximately 0 degrees (north)
        self.assertLess(bearing, 5)
    
    def test_get_cardinal_direction(self):
        """Test cardinal direction conversion."""
        self.assertEqual(geo_utils.get_cardinal_direction(0), 'N')
        self.assertEqual(geo_utils.get_cardinal_direction(45), 'NE')
        self.assertEqual(geo_utils.get_cardinal_direction(90), 'E')
        self.assertEqual(geo_utils.get_cardinal_direction(180), 'S')
        self.assertEqual(geo_utils.get_cardinal_direction(270), 'W')
    
    def test_calculate_path_distance(self):
        """Test path distance calculation."""
        # Path with 3 points, approximately 2km total
        path = [
            {"lat": 25.200, "lng": 55.270},
            {"lat": 25.210, "lng": 55.270},  # ~1km
            {"lat": 25.220, "lng": 55.270}   # ~1km
        ]
        
        distance = geo_utils.calculate_path_distance(path)
        
        # Should be approximately 2000 meters
        self.assertAlmostEqual(distance, 2000, delta=100)
    
    def test_format_distance_meters(self):
        """Test distance formatting in meters."""
        formatted = geo_utils.format_distance(500)
        self.assertEqual(formatted, "500 m")
    
    def test_format_distance_kilometers(self):
        """Test distance formatting in kilometers."""
        formatted = geo_utils.format_distance(1500)
        self.assertEqual(formatted, "1.5 km")



