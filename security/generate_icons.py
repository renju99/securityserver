from PIL import Image, ImageDraw, ImageFont

def create_icon(size, path):
    try:
        img = Image.new('RGB', (size, size), color = '#1B365D') # Berkeley Blue
        d = ImageDraw.Draw(img)
        # Draw a simple 'B' or shield shape if possible, keeping it simple
        margin = size // 4
        d.rectangle([margin, margin, size-margin, size-margin], outline="#FFD700", width=2) # Gold border
        d.text((size//2 - 5, size//2 - 10), "B", fill="#FFFFFF") # White text
        img.save(path, 'PNG')
        print(f"Generated {path}")
    except Exception as e:
        print(f"Error generating {path}: {e}")

base_dir = '/home/azureuser/security/guard_mobile_app/app/src/main/res/'
sizes = {
    'mipmap-hdpi': 72,
    'mipmap-mdpi': 48,
    'mipmap-xhdpi': 96,
    'mipmap-xxhdpi': 144,
    'mipmap-xxxhdpi': 192
}

for folder, size in sizes.items():
    import os
    if not os.path.exists(f"{base_dir}/{folder}"):
        os.makedirs(f"{base_dir}/{folder}")
        
    path = f"{base_dir}/{folder}/ic_launcher.png"
    create_icon(size, path)
