import os
from PIL import Image

base_dir = '/home/azureuser/security/guard_mobile_app/app/src/main/res/'
dirs = ['mipmap-hdpi', 'mipmap-mdpi', 'mipmap-xhdpi', 'mipmap-xxhdpi', 'mipmap-xxxhdpi']

for d in dirs:
    path = os.path.join(base_dir, d, 'ic_launcher.png')
    if os.path.exists(path):
        try:
            img = Image.open(path)
            img.save(path, 'PNG')
            print(f"Converted {path} to PNG")
        except Exception as e:
            print(f"Error converting {path}: {e}")
