#!/usr/bin/env python3
"""
Quick test script to verify logo processing works correctly
"""

from PIL import Image
import base64
import io

def test_logo_processing():
    try:
        # Load the logo
        with Image.open('logo.png') as img:
            print(f"Original: Size: {img.size}, Mode: {img.mode}")
            
            # DON'T convert RGBA to RGB - preserve transparency!
            print(f"Keeping original format: Size: {img.size}, Mode: {img.mode}")
            
            # Resize if too large
            if img.width > 150:
                aspect_ratio = img.height / img.width
                new_width = 150
                new_height = int(new_width * aspect_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"Resized: Size: {img.size}, Mode: {img.mode}")
            
            # Save processed image for verification (this will preserve transparency)
            img.save('logo_processed.png')
            print("Processed image saved as 'logo_processed.png' (transparency preserved)")
            
            print("✅ Logo processing successful - transparency preserved for default background!")
            return True
            
    except Exception as e:
        print(f"Error processing logo: {str(e)}")
        return False

if __name__ == "__main__":
    test_logo_processing()
