#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for CCTV Camera functionality.
Creates a test camera with a free online stream and verifies it works.
"""

import sys
import os

# Add Odoo to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

try:
    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.tools import config
except ImportError:
    print("Error: Odoo not found. Please run this script from the Odoo directory.")
    sys.exit(1)


def setup_test_camera():
    """Create a test camera with a free online stream."""
    
    # Initialize Odoo
    config.parse_config(['-c', os.path.join(os.path.dirname(__file__), '../../../odoo.conf')])
    odoo.tools.config.parse_config([])
    
    # Get database name from config or use default
    db_name = config.get('db_name', 'odoo')
    
    # Initialize registry
    registry = odoo.registry(db_name)
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # Check if test camera already exists
        existing_camera = env['cctv.camera'].search([
            ('code', '=', 'TEST-CAM-001')
        ], limit=1)
        
        if existing_camera:
            print(f"✓ Test camera already exists: {existing_camera.name} (ID: {existing_camera.id})")
            camera = existing_camera
        else:
            # Find or create a test site
            test_site = env['client.site'].search([
                ('code', '=', 'TEST-SITE-001')
            ], limit=1)
            
            if not test_site:
                # Find or create a test client
                test_client = env['res.partner'].search([
                    ('name', '=', 'Test Client'),
                    ('is_company', '=', True)
                ], limit=1)
                
                if not test_client:
                    test_client = env['res.partner'].create({
                        'name': 'Test Client',
                        'is_company': True,
                    })
                    print(f"✓ Created test client: {test_client.name}")
                
                # Create test site
                test_site = env['client.site'].create({
                    'name': 'Test Site',
                    'code': 'TEST-SITE-001',
                    'client_id': test_client.id,
                    'latitude': 25.2048,  # Dubai coordinates
                    'longitude': 55.2708,
                    'status': 'active',
                })
                print(f"✓ Created test site: {test_site.name}")
            else:
                print(f"✓ Using existing test site: {test_site.name}")
            
            # Create test camera with a free public webcam stream
            # Using a free public webcam that can be embedded
            # Option 1: HLS test stream (requires HLS.js player)
            test_stream_url = "https://bitdash-a.akamaihd.net/content/sintel/hls/playlist.m3u8"
            
            # Option 2: Iframe-embeddable webcam (uncomment to use instead)
            # test_stream_url = "https://www.earthcam.com/usa/newyork/timessquare/?cam=tsrobo1"
            
            camera = env['cctv.camera'].create({
                'name': 'Test Camera - Free Stream',
                'code': 'TEST-CAM-001',
                'site_id': test_site.id,
                'camera_type': 'fixed',
                'stream_url': test_stream_url,
                'stream_type': 'hls',
                'status': 'online',
                'is_active': True,
                'location_description': 'Test camera using free online HLS stream for verification',
            })
            print(f"✓ Created test camera: {camera.name} (ID: {camera.id})")
        
        # Display camera information
        print("\n" + "="*60)
        print("CCTV Camera Test Setup Complete")
        print("="*60)
        print(f"Camera ID: {camera.id}")
        print(f"Camera Name: {camera.name}")
        print(f"Camera Code: {camera.code}")
        print(f"Site: {camera.site_id.name}")
        print(f"Stream Type: {camera.stream_type}")
        print(f"Stream URL: {camera.stream_url}")
        print(f"Status: {camera.status}")
        print("\nTo view the camera:")
        print(f"  1. Log into Odoo")
        print(f"  2. Go to: CCTV Monitoring > View Camera")
        print(f"  3. Select site: {camera.site_id.name}")
        print(f"  4. Select camera: {camera.name}")
        print(f"  5. Click 'View Camera'")
        print(f"\nOr access directly via URL:")
        print(f"  /guardpro/cctv/view/{camera.id}")
        print("="*60)
        
        return camera.id


if __name__ == '__main__':
    try:
        camera_id = setup_test_camera()
        print(f"\n✓ Test camera setup successful! Camera ID: {camera_id}")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error setting up test camera: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)








