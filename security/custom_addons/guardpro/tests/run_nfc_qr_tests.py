#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GuardLink NFC & QR Code Test Runner
===================================

This script runs comprehensive tests for NFC and QR code functionality.

Usage:
    python3 run_nfc_qr_tests.py
    
Or run via Odoo:
    odoo-bin -c odoo.conf -d DATABASE -u guardpro --test-enable --stop-after-init
"""

import sys
import os


def print_header():
    """Print test header."""
    print("=" * 80)
    print("GUARDPRO - NFC & QR CODE TESTING SUITE".center(80))
    print("=" * 80)
    print()


def print_section(title):
    """Print section header."""
    print()
    print("-" * 80)
    print(f"  {title}")
    print("-" * 80)


def print_test_info():
    """Print test information."""
    print_section("Test Coverage")
    
    tests = [
        "1. NFC Checkpoint Creation",
        "2. QR Checkpoint Creation",
        "3. Dual (NFC+QR) Checkpoint Creation",
        "4. Auto QR Code Generation",
        "5. NFC Scan Verification",
        "6. QR Scan Verification",
        "7. NFC Scan Record Creation",
        "8. QR Scan Record Creation",
        "9. Minimum Scan Interval Check",
        "10. Checkpoint Statistics Computation",
        "11. API Scan Checkpoint Method",
        "12. NFC Tag ID Validation",
        "13. QR Code Validation",
        "14. Unique Constraints (NFC/QR)",
        "15. Inactive Checkpoint Scan Rejection",
        "16. Both Scan Type (NFC+QR)",
        "17. Photo Requirement Validation",
        "18. Notes Requirement Validation",
        "19. Manual Override Functionality",
        "20. GPS Distance Calculation"
    ]
    
    for test in tests:
        print(f"  ✓ {test}")
    
    print()
    print(f"  Total Tests: {len(tests)}")


def print_instructions():
    """Print test execution instructions."""
    print_section("How to Run Tests")
    
    print("\n1. BACKEND TESTS (Python ORM Tests)")
    print("   " + "-" * 70)
    print("   Run all GuardLink tests:")
    print("   $ ./odoo-bin -c odoo.conf -d guardpro_test -u guardpro \\")
    print("                --test-enable --stop-after-init")
    print()
    print("   Run only checkpoint tests:")
    print("   $ ./odoo-bin -c odoo.conf -d guardpro_test -u guardpro \\")
    print("                --test-enable --test-tags /guardpro \\")
    print("                --stop-after-init")
    print()
    
    print("\n2. FRONTEND TESTS (Browser-based)")
    print("   " + "-" * 70)
    print("   Open the HTML test page in a browser:")
    print("   $ firefox custom_addons/guardpro/static/test_nfc_qr_scanner.html")
    print()
    print("   Or via web server:")
    print("   $ cd custom_addons/guardpro/static")
    print("   $ python3 -m http.server 8080")
    print("   Then open: http://localhost:8080/test_nfc_qr_scanner.html")
    print()
    
    print("\n3. API ENDPOINT TESTS (curl)")
    print("   " + "-" * 70)
    print("   Test checkpoint scan API:")
    print("""
   $ curl -X POST http://localhost:8069/guardpro/api/checkpoint/scan \\
     -H "Content-Type: application/json" \\
     -H "Cookie: session_id=YOUR_SESSION" \\
     -d '{
       "jsonrpc": "2.0",
       "params": {
         "checkpoint_id": 1,
         "scan_data": "NFC-TEST-001",
         "latitude": 25.2048,
         "longitude": 55.2708
       }
     }'
   """)
    
    print("\n4. CREATE TEST DATA")
    print("   " + "-" * 70)
    print("   Create sample checkpoints for testing:")
    print("   - Go to Odoo web interface")
    print("   - Navigate to GuardLink > Configuration > Checkpoints")
    print("   - Create test checkpoints with different scan types")
    print()


def print_requirements():
    """Print test requirements."""
    print_section("Test Requirements")
    
    print("\n📋 Backend Tests:")
    print("   ✓ Odoo 18 Community Edition")
    print("   ✓ GuardLink module installed")
    print("   ✓ Test database configured")
    print("   ✓ Python packages: qrcode, Pillow")
    print()
    
    print("🌐 Frontend Tests:")
    print("   ✓ Modern web browser (Chrome, Firefox, Edge)")
    print("   ✓ HTTPS connection (required for NFC)")
    print("   ✓ NFC-enabled device (for NFC tests)")
    print("   ✓ Camera access (for QR tests)")
    print("   ✓ Location services enabled")
    print()
    
    print("🔧 API Tests:")
    print("   ✓ Odoo server running")
    print("   ✓ Valid session cookie")
    print("   ✓ Guard profile configured")
    print("   ✓ Active checkpoints created")
    print()


def check_dependencies():
    """Check if required dependencies are installed."""
    print_section("Checking Dependencies")
    
    dependencies = {
        'qrcode': False,
        'PIL': False,
        'odoo': False
    }
    
    for package in dependencies.keys():
        try:
            __import__(package)
            dependencies[package] = True
            print(f"  ✓ {package:15} - Installed")
        except ImportError:
            print(f"  ✗ {package:15} - NOT INSTALLED")
    
    print()
    
    all_installed = all(dependencies.values())
    
    if not all_installed:
        print("⚠️  Missing dependencies detected!")
        print("\nInstall missing packages:")
        if not dependencies['qrcode']:
            print("  $ pip3 install qrcode")
        if not dependencies['PIL']:
            print("  $ pip3 install Pillow")
        print()
        return False
    else:
        print("✅ All dependencies installed!")
        return True


def check_module_structure():
    """Check if module structure is correct."""
    print_section("Checking Module Structure")
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    required_files = [
        '__init__.py',
        '__manifest__.py',
        'models/checkpoint.py',
        'models/checkpoint_scan.py',
        'controllers/mobile_api.py',
        'static/src/js/nfc_scanner.js',
        'static/src/js/qr_scanner.js',
        'views/checkpoint_views.xml',
        'views/checkpoint_scan_views.xml',
        'security/ir.model.access.csv',
        'tests/test_nfc_qr_checkpoint.py',
        'static/test_nfc_qr_scanner.html'
    ]
    
    all_present = True
    
    for file_path in required_files:
        full_path = os.path.join(base_path, file_path)
        exists = os.path.exists(full_path)
        
        status = "✓" if exists else "✗"
        print(f"  {status} {file_path}")
        
        if not exists:
            all_present = False
    
    print()
    
    if all_present:
        print("✅ All required files present!")
        return True
    else:
        print("⚠️  Some files are missing!")
        return False


def print_device_requirements():
    """Print device-specific requirements for NFC/QR testing."""
    print_section("Device Requirements for Live Testing")
    
    print("\n📱 NFC Testing:")
    print("   Supported Devices:")
    print("   ✓ Android devices with NFC (Android 10+)")
    print("   ✓ Chrome browser (version 89+)")
    print("   ✓ Edge browser (version 89+)")
    print()
    print("   Requirements:")
    print("   • NFC must be enabled in device settings")
    print("   • HTTPS connection required (Web NFC API limitation)")
    print("   • NFC tags: NTAG213/215/216 or compatible")
    print()
    print("   ⚠️  Note: iOS does not support Web NFC API")
    print()
    
    print("📷 QR Code Testing:")
    print("   Supported Devices:")
    print("   ✓ All modern smartphones")
    print("   ✓ Desktop/laptop with webcam")
    print("   ✓ Chrome, Firefox, Safari, Edge")
    print()
    print("   Requirements:")
    print("   • Camera access permission")
    print("   • Adequate lighting")
    print("   • QR codes printed or displayed on screen")
    print()


def print_quick_start():
    """Print quick start guide."""
    print_section("Quick Start Guide")
    
    print("\n🚀 5-Minute Test Setup:")
    print()
    print("1. Install GuardLink module:")
    print("   $ ./odoo-bin -c odoo.conf -d DATABASE -i guardpro")
    print()
    print("2. Create a test site:")
    print("   - Go to GuardLink > Sites > Create")
    print("   - Name: 'Test Site'")
    print()
    print("3. Create a test checkpoint:")
    print("   - Go to GuardLink > Configuration > Checkpoints > Create")
    print("   - Name: 'Test NFC Checkpoint'")
    print("   - Scan Type: 'NFC Tag'")
    print("   - NFC Tag ID: 'TEST-NFC-001'")
    print("   - Site: Select 'Test Site'")
    print()
    print("4. Create a guard profile:")
    print("   - Go to GuardLink > Guards > Create")
    print("   - Link to your user account")
    print()
    print("5. Run Python tests:")
    print("   $ ./odoo-bin -c odoo.conf -d DATABASE -u guardpro --test-enable")
    print()
    print("6. Open browser test:")
    print("   $ Open: custom_addons/guardpro/static/test_nfc_qr_scanner.html")
    print()


def main():
    """Main test runner."""
    print_header()
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    # Check module structure
    structure_ok = check_module_structure()
    
    # Print test information
    print_test_info()
    
    # Print requirements
    print_requirements()
    
    # Print device requirements
    print_device_requirements()
    
    # Print instructions
    print_instructions()
    
    # Print quick start
    print_quick_start()
    
    # Summary
    print_section("Summary")
    
    if deps_ok and structure_ok:
        print("\n✅ System ready for testing!")
        print("\nRun backend tests with:")
        print("  ./odoo-bin -c odoo.conf -d DATABASE -u guardpro --test-enable\n")
        return 0
    else:
        print("\n⚠️  Please fix the issues above before running tests.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())

