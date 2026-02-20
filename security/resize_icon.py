from PIL import Image
import os

source_path = '/home/azureuser/Gemini_Generated_Image_mkc9humkc9humkc9.png'
base_dir = '/home/azureuser/security/guard_mobile_app/app/src/main/res/'

sizes = {
    'mipmap-hdpi': 72,
    'mipmap-mdpi': 48,
    'mipmap-xhdpi': 96,
    'mipmap-xxhdpi': 144,
    'mipmap-xxxhdpi': 192
}

try:
    img = Image.open(source_path)
    print(f"Opened source image: {source_path}")
    
    for folder, size in sizes.items():
        output_dir = os.path.join(base_dir, folder)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        output_path = os.path.join(output_dir, 'ic_launcher.png')
        
        # Resize using LANCZOS for best quality
        resized_img = img.resize((size, size), Image.Resampling.LANCZOS)
        resized_img.save(output_path, 'PNG')
        print(f"Generated {output_path} ({size}x{size})")
        
except Exception as e:
    print(f"Error processing image: {e}")
