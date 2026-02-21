"""
Streaming upload module for camera trap images
Uploads directly from ZIP to Google Cloud Storage without loading all images into memory
"""

import zipfile
import io
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st

def extract_exif_date_fast(image_data):
    """Fast EXIF date extraction - minimal processing"""
    try:
        img = Image.open(io.BytesIO(image_data))
        exif = img._getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    return dt, dt.strftime('%Y%m%d')
        return None, None
    except:
        return None, None

def generate_new_filename(original_name, country, site, station, camera, date_str):
    """Generate standardized filename"""
    import os
    name_without_ext, ext = os.path.splitext(original_name)
    return f"{country}_{site}_{station}_{camera}_{date_str}_{name_without_ext}{ext.upper()}"

def stream_upload_from_zip(zip_file, bucket, metadata, progress_callback=None):
    """
    Stream upload images directly from ZIP to GCS
    
    Args:
        zip_file: Uploaded ZIP file object
        bucket: GCS bucket object
        metadata: Dict with country, site, station, camera, camera_type, fallback_date
        progress_callback: Optional callback function for progress updates
        
    Returns:
        dict: Upload statistics
    """
    country = metadata['country'].upper()
    site = metadata['site'].upper()
    station = metadata['station'].upper()
    camera = metadata['camera'].upper()
    camera_type = metadata['camera_type']
    fallback_date = metadata['survey_date']
    
    results = {
        'uploaded': 0,
        'skipped': 0,
        'failed': 0,
        'total': 0,
        'details': []
    }
    
    # First pass: count total images
    zip_data = zip_file.getvalue()
    with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zip_ref:
        image_files = [f for f in zip_ref.filelist 
                      if not f.is_dir() and 
                      any(f.filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif'])]
        results['total'] = len(image_files)
    
    if results['total'] == 0:
        return results
    
    # Second pass: process and upload
    with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zip_ref:
        for idx, file_info in enumerate(image_files):
            try:
                # Get just the filename (not full path in ZIP)
                original_name = file_info.filename.split('/')[-1]
                
                # Read image data from ZIP
                image_data = zip_ref.read(file_info.filename)
                
                # Skip files over 50MB
                size_mb = len(image_data) / (1024 * 1024)
                if size_mb > 50:
                    results['skipped'] += 1
                    results['details'].append({
                        'file': original_name,
                        'status': 'Skipped (>50MB)',
                        'size_mb': f"{size_mb:.2f}"
                    })
                    if progress_callback:
                        progress_callback(idx + 1, results['total'], original_name, 'skipped')
                    continue
                
                # Extract EXIF date (fast)
                dt_obj, date_str = extract_exif_date_fast(image_data)
                
                # Use fallback date if no EXIF
                if not date_str:
                    date_str = fallback_date.strftime('%Y%m%d')
                    month_key = f"{fallback_date.year}{fallback_date.month:02d}"
                else:
                    month_key = f"{dt_obj.year}{dt_obj.month:02d}"
                
                # Generate new filename
                new_filename = generate_new_filename(
                    original_name, country, site, station, camera, date_str
                )
                
                # Build GCS path: camera_trap/TYPE/yyyymm/STATION/STATION_CAMERA/filename
                full_camera = f"{station}_{camera}"
                blob_path = f"camera_trap/{camera_type}/{month_key}/{station}/{full_camera}/{new_filename}"
                
                # Check if exists
                blob = bucket.blob(blob_path)
                if blob.exists():
                    results['skipped'] += 1
                    results['details'].append({
                        'file': original_name,
                        'new_name': new_filename,
                        'status': 'Already exists',
                        'path': blob_path
                    })
                    if progress_callback:
                        progress_callback(idx + 1, results['total'], original_name, 'exists')
                    continue
                
                # Upload directly to GCS (no local storage)
                blob.upload_from_string(
                    image_data,
                    content_type='image/jpeg'
                )
                
                results['uploaded'] += 1
                results['details'].append({
                    'file': original_name,
                    'new_name': new_filename,
                    'status': 'Success',
                    'path': blob_path,
                    'size_mb': f"{size_mb:.2f}",
                    'date_source': 'EXIF' if dt_obj else 'Fallback'
                })
                
                if progress_callback:
                    progress_callback(idx + 1, results['total'], original_name, 'success')
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'file': original_name if 'original_name' in locals() else file_info.filename,
                    'status': f'Error: {str(e)}',
                })
                if progress_callback:
                    progress_callback(idx + 1, results['total'], 
                                    original_name if 'original_name' in locals() else file_info.filename, 
                                    'error')
    
    return results
