#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple script to create a test CCTV camera.
Run with: python3 odoo-18.0/odoo-bin shell -d <database> -c odoo.conf < custom_addons/guardpro/scripts/test_cctv_setup.py
Or use: odoo-bin shell -d <database> and paste this code
"""

# Find or create test client
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
else:
    print(f"✓ Using existing test client: {test_client.name}")

# Find or create test site
test_site = env['client.site'].search([
    ('code', '=', 'TEST-SITE-001')
], limit=1)

if not test_site:
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

# Check if test camera already exists
existing_camera = env['cctv.camera'].search([
    ('code', '=', 'TEST-CAM-001')
], limit=1)

if existing_camera:
    print(f"✓ Test camera already exists: {existing_camera.name} (ID: {existing_camera.id})")
    camera = existing_camera
    # Update stream URL to latest test stream
    camera.write({
        'stream_url': 'https://bitdash-a.akamaihd.net/content/sintel/hls/playlist.m3u8',
        'stream_type': 'hls',
        'status': 'online',
    })
    print(f"✓ Updated camera stream URL")
else:
    # Create test camera with free HLS stream
    camera = env['cctv.camera'].create({
        'name': 'Test Camera - Free HLS Stream',
        'code': 'TEST-CAM-001',
        'site_id': test_site.id,
        'camera_type': 'fixed',
        'stream_url': 'https://bitdash-a.akamaihd.net/content/sintel/hls/playlist.m3u8',
        'stream_type': 'hls',
        'status': 'online',
        'is_active': True,
        'location_description': 'Test camera using free online HLS stream (Sintel demo video)',
    })
    print(f"✓ Created test camera: {camera.name} (ID: {camera.id})")

# Display information
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
print(f"\nOr access directly via URL (after logging in):")
print(f"  /guardpro/cctv/view/{camera.id}")
print("="*60)








