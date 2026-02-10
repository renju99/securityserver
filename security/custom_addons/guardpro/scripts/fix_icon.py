#!/usr/bin/env python3
"""
Script to fix Odoo module icon issues.
Converts icon to proper format for Odoo App Store compatibility.
"""

import sys
import os
from pathlib import Path

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not available. Install with: pip install Pillow")

def fix_icon(icon_path):
    """Fix icon file for Odoo compatibility."""
    icon_path = Path(icon_path)
    
    if not icon_path.exists():
        print(f"Error: Icon file not found at {icon_path}")
        return False
    
    if not PIL_AVAILABLE:
        print("Error: PIL/Pillow is required to fix the icon")
        print("Install with: pip install Pillow")
        return False
    
    try:
        # Open the image
        img = Image.open(icon_path)
        print(f"Current icon properties:")
        print(f"  Format: {img.format}")
        print(f"  Mode: {img.mode}")
        print(f"  Size: {img.size}")
        
        # Check if it needs conversion
        needs_fix = False
        issues = []
        
        # Check for transparency (RGBA/LA/P modes can cause issues)
        if img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P' and 'transparency' in img.info:
                needs_fix = True
                issues.append("Has transparency (P mode with transparency)")
            elif img.mode in ('RGBA', 'LA'):
                needs_fix = True
                issues.append(f"Has transparency ({img.mode} mode)")
        
        # Check size (should be square and reasonable size)
        if img.size[0] != img.size[1]:
            needs_fix = True
            issues.append(f"Not square ({img.size[0]}x{img.size[1]})")
        
        if img.size[0] < 64 or img.size[0] > 512:
            needs_fix = True
            issues.append(f"Size not optimal ({img.size[0]}x{img.size[1]})")
        
        if not needs_fix:
            print("\n✓ Icon appears to be in good format!")
            print("If it still shows as white cube, try:")
            print("  1. Restart Odoo server")
            print("  2. Clear browser cache")
            print("  3. Update Apps List in Odoo")
            return True
        
        print(f"\nIssues found: {', '.join(issues)}")
        print("Creating fixed version...")
        
        # Create backup
        backup_path = icon_path.with_suffix('.png.backup')
        img.save(backup_path, 'PNG')
        print(f"Backup saved to: {backup_path}")
        
        # Convert to RGB if it has transparency
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img
        
        # Resize to optimal size if needed (128x128 or 256x256)
        if img.size[0] != img.size[1] or img.size[0] not in (64, 128, 256, 512):
            target_size = 256  # Optimal size for Odoo
            if img.size[0] < 128:
                target_size = 128
            elif img.size[0] > 512:
                target_size = 512
            img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
            print(f"Resized to {target_size}x{target_size}")
        
        # Save as optimized PNG
        img.save(icon_path, 'PNG', optimize=True)
        print(f"\n✓ Icon fixed and saved to: {icon_path}")
        print(f"  Format: PNG")
        print(f"  Mode: {img.mode}")
        print(f"  Size: {img.size}")
        print("\nNext steps:")
        print("  1. Restart Odoo server")
        print("  2. Go to Apps > Update Apps List")
        print("  3. Clear browser cache if needed")
        
        return True
        
    except Exception as e:
        print(f"Error processing icon: {e}")
        return False

if __name__ == '__main__':
    icon_path = Path(__file__).parent.parent / 'static' / 'description' / 'icon.png'
    
    if len(sys.argv) > 1:
        icon_path = Path(sys.argv[1])
    
    success = fix_icon(icon_path)
    sys.exit(0 if success else 1)

