#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick test script for CCTV camera - connects to running Odoo instance.
Usage: python3 test_cctv_quick.py
"""

import xmlrpc.client
import sys

# Odoo connection settings
url = "http://localhost:8069"
db = "odoo"  # Change if your database name is different
username = "admin"  # Change to your admin username
password = "admin"  # Change to your admin password

try:
    # Connect to Odoo
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    uid = common.authenticate(db, username, password, {})
    
    if not uid:
        print("✗ Authentication failed. Please check your credentials.")
        sys.exit(1)
    
    print(f"✓ Connected to Odoo (UID: {uid})")
    
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
    
    # Find or create test client
    client_ids = models.execute_kw(
        db, uid, password,
        'res.partner', 'search',
        [[['name', '=', 'Test Client'], ['is_company', '=', True]]],
        {'limit': 1}
    )
    
    if client_ids:
        client_id = client_ids[0]
        print(f"✓ Using existing test client (ID: {client_id})")
    else:
        client_id = models.execute_kw(
            db, uid, password,
            'res.partner', 'create',
            [{'name': 'Test Client', 'is_company': True}]
        )
        print(f"✓ Created test client (ID: {client_id})")
    
    # Find or create test site
    site_ids = models.execute_kw(
        db, uid, password,
        'client.site', 'search',
        [[['code', '=', 'TEST-SITE-001']]],
        {'limit': 1}
    )
    
    if site_ids:
        site_id = site_ids[0]
        print(f"✓ Using existing test site (ID: {site_id})")
    else:
        site_id = models.execute_kw(
            db, uid, password,
            'client.site', 'create',
            [{
                'name': 'Test Site',
                'code': 'TEST-SITE-001',
                'client_id': client_id,
                'latitude': 25.2048,
                'longitude': 55.2708,
                'status': 'active',
            }]
        )
        print(f"✓ Created test site (ID: {site_id})")
    
    # Find or create test camera
    camera_ids = models.execute_kw(
        db, uid, password,
        'cctv.camera', 'search',
        [[['code', '=', 'TEST-CAM-001']]],
        {'limit': 1}
    )
    
    if camera_ids:
        camera_id = camera_ids[0]
        # Update camera with latest test stream
        models.execute_kw(
            db, uid, password,
            'cctv.camera', 'write',
            [[camera_id], {
                'stream_url': 'https://bitdash-a.akamaihd.net/content/sintel/hls/playlist.m3u8',
                'stream_type': 'hls',
                'status': 'online',
            }]
        )
        print(f"✓ Updated existing test camera (ID: {camera_id})")
    else:
        camera_id = models.execute_kw(
            db, uid, password,
            'cctv.camera', 'create',
            [{
                'name': 'Test Camera - Free HLS Stream',
                'code': 'TEST-CAM-001',
                'site_id': site_id,
                'camera_type': 'fixed',
                'stream_url': 'https://bitdash-a.akamaihd.net/content/sintel/hls/playlist.m3u8',
                'stream_type': 'hls',
                'status': 'online',
                'is_active': True,
                'location_description': 'Test camera using free online HLS stream (Sintel demo video)',
            }]
        )
        print(f"✓ Created test camera (ID: {camera_id})")
    
    # Get camera details
    camera_data = models.execute_kw(
        db, uid, password,
        'cctv.camera', 'read',
        [[camera_id]],
        {'fields': ['name', 'code', 'stream_url', 'stream_type', 'status', 'site_id']}
    )[0]
    
    print("\n" + "="*60)
    print("CCTV Camera Test Setup Complete")
    print("="*60)
    print(f"Camera ID: {camera_id}")
    print(f"Camera Name: {camera_data['name']}")
    print(f"Camera Code: {camera_data['code']}")
    print(f"Stream Type: {camera_data['stream_type']}")
    print(f"Stream URL: {camera_data['stream_url']}")
    print(f"Status: {camera_data['status']}")
    print("\nTo view the camera:")
    print(f"  1. Log into Odoo at {url}")
    print(f"  2. Go to: CCTV Monitoring > View Camera")
    print(f"  3. Select site: Test Site")
    print(f"  4. Select camera: {camera_data['name']}")
    print(f"  5. Click 'View Camera'")
    print(f"\nOr access directly via URL (after logging in):")
    print(f"  {url}/guardpro/cctv/view/{camera_id}")
    print("="*60)
    print("\n✓ Test camera is ready for testing!")
    
except Exception as e:
    print(f"\n✗ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)








