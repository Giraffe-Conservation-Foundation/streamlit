"""
Utility functions for image processing and file naming
"""

import os
import re
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import io

def validate_image_file(file_data):
    """
    Validate if the uploaded file is a valid image
    
    Args:
        file_data: Uploaded file data
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        image = Image.open(io.BytesIO(file_data))
        image.verify()
        return True, None
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"

def get_image_metadata(file_data):
    """
    Extract metadata from image file
    
    Args:
        file_data: Image file data
        
    Returns:
        dict: Image metadata including dimensions, format, etc.
    """
    try:
        image = Image.open(io.BytesIO(file_data))
        metadata = {
            'format': image.format,
            'mode': image.mode,
            'width': image.width,
            'height': image.height,
            'size_bytes': len(file_data)
        }
        
        # Try to get EXIF data if available
        if hasattr(image, '_getexif') and image._getexif():
            exif = image._getexif()
            metadata['exif'] = exif
            
            # Extract DateTimeOriginal if available
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'DateTimeOriginal':
                        try:
                            # Parse EXIF date format: 'YYYY:MM:DD HH:MM:SS'
                            dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                            metadata['datetime_original'] = dt
                            metadata['date_taken'] = dt.strftime('%Y%m%d')
                        except ValueError:
                            pass
        
        return metadata
    except Exception as e:
        return {'error': str(e)}

def clean_site_name(site_name):
    """
    Clean site name for use in filenames
    
    Args:
        site_name: Original site name
        
    Returns:
        str: Cleaned site name suitable for filenames
    """
    # Remove special characters and replace spaces with underscores
    clean_name = re.sub(r'[^\w\s-]', '', site_name).strip()
    clean_name = re.sub(r'[-\s]+', '_', clean_name).upper()
    return clean_name

def generate_standardized_filename(original_filename, country, site, survey_date, index, photographer=None, image_metadata=None):
    """
    Generate standardized filename based on conservation naming convention
    Format: COUNTRY_SITE_datetime_INITIALS_ORIGINALNAME
    Uses EXIF DateTimeOriginal if available, otherwise falls back to survey_date
    
    Args:
        original_filename: Original file name
        country: Country code (e.g., 'AGO', 'NAM', 'KEN')
        site: Site code (e.g., 'LLNP', 'EHGR', 'MMNR')
        survey_date: Date of survey (fallback)
        index: Sequential index number (not used in new format)
        photographer: Optional photographer initials
        image_metadata: Optional image metadata containing EXIF data
        
    Returns:
        str: Standardized filename
    """
    # Extract file extension and original name without extension
    name_without_ext, ext = os.path.splitext(original_filename)
    
    # Use EXIF date if available, otherwise use survey date
    if image_metadata and 'date_taken' in image_metadata:
        date_str = image_metadata['date_taken']  # Already in YYYYMMDD format
    else:
        date_str = survey_date.strftime("%Y%m%d")
    
    # Base filename format: COUNTRY_SITE_YYYYMMDD_INITIALS_ORIGINALNAME
    parts = [country.upper(), site.upper(), date_str]
    
    # Add photographer initials if provided
    if photographer:
        clean_photographer = re.sub(r'[^\w]', '', photographer).upper()
        if clean_photographer:
            parts.append(clean_photographer)
    
    # Add original filename (without extension)
    parts.append(name_without_ext)
    
    # Join all parts with underscore and add extension
    base_name = "_".join(parts)
    
    return f"{base_name}{ext.lower()}"

def validate_filename(filename):
    """
    Validate if filename follows the expected convention
    
    Args:
        filename: Filename to validate
        
    Returns:
        tuple: (is_valid, components_dict)
    """
    # Pattern: SITE_YYYYMMDD_INDEX[_PHOTOGRAPHER].ext
    pattern = r'^([A-Z_]+)_(\d{8})_(\d{4})(?:_([A-Z]+))?\.([a-z]+)$'
    match = re.match(pattern, filename)
    
    if match:
        components = {
            'site': match.group(1),
            'date': match.group(2),
            'index': match.group(3),
            'photographer': match.group(4),
            'extension': match.group(5)
        }
        return True, components
    else:
        return False, {}

def calculate_folder_structure(site, survey_date, custom_structure=None):
    """
    Calculate the folder structure for GCS upload
    
    Args:
        site: Site name
        survey_date: Survey date
        custom_structure: Optional custom folder structure
        
    Returns:
        str: Folder path for GCS
    """
    if custom_structure:
        return custom_structure
    
    # Default structure: giraffe_images/SITE/YYYY/MM/
    clean_site = clean_site_name(site)
    year = survey_date.strftime("%Y")
    month = survey_date.strftime("%m")
    
    return f"giraffe_images/{clean_site}/{year}/{month}/"

def create_metadata_dict(site, survey_date, photographer, camera_model, notes, original_filename):
    """
    Create metadata dictionary for GCS blob
    
    Args:
        site: Site name
        survey_date: Survey date
        photographer: Photographer name
        camera_model: Camera model
        notes: Additional notes
        original_filename: Original filename
        
    Returns:
        dict: Metadata dictionary
    """
    metadata = {
        'original_filename': original_filename,
        'site': site,
        'survey_date': str(survey_date),
        'upload_timestamp': datetime.now().isoformat(),
        'conservation_project': 'giraffe_conservation'
    }
    
    if photographer:
        metadata['photographer'] = photographer
    if camera_model:
        metadata['camera_model'] = camera_model
    if notes:
        metadata['notes'] = notes
    
    return metadata

def compress_image_if_needed(image_data, max_size_mb=10, quality=85):
    """
    Compress image if it exceeds maximum size
    
    Args:
        image_data: Original image data
        max_size_mb: Maximum size in MB
        quality: JPEG quality for compression
        
    Returns:
        bytes: Compressed image data
    """
    if len(image_data) <= max_size_mb * 1024 * 1024:
        return image_data
    
    try:
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        # Compress
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)
        compressed_data = output.getvalue()
        
        return compressed_data
    except Exception:
        # If compression fails, return original
        return image_data

def batch_rename_preview(files, country, site, survey_date, photographer=None):
    """
    Preview batch rename operation using EXIF DateTimeOriginal when available
    
    Args:
        files: List of uploaded files
        country: Country code
        site: Site code
        survey_date: Survey date (fallback)
        photographer: Optional photographer initials
        
    Returns:
        list: List of dictionaries with rename preview
    """
    preview = []
    
    for idx, file in enumerate(files, 1):
        # Get file data
        if hasattr(file, '_data'):
            # MockUploadedFile from ZIP extraction
            file_data = file._data
        else:
            # Regular uploaded file
            file_data = file.getvalue()
        
        # Extract image metadata to get EXIF date
        img_metadata = get_image_metadata(file_data)
        
        # Generate new filename using EXIF date if available
        new_name = generate_standardized_filename(
            file.name, country, site, survey_date, idx, photographer, img_metadata
        )
        
        # Determine which date was used
        date_source = "EXIF" if 'date_taken' in img_metadata else "Survey Date"
        date_used = img_metadata.get('date_taken', survey_date.strftime("%Y%m%d"))
        
        preview.append({
            'index': idx,
            'original_name': file.name,
            'new_name': new_name,
            'size_mb': len(file_data) / (1024 * 1024),
            'valid': validate_image_file(file_data)[0],
            'date_source': date_source,
            'date_used': date_used,
            'datetime_original': img_metadata.get('datetime_original')
        })
    
    return preview
