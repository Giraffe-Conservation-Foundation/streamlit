import streamlit as st
import os
from google.cloud import storage
from google.oauth2 import service_account
import pandas as pd
from PIL import Image
import io
import re
from datetime import datetime
import tempfile
import zipfile
import json
from utils import (
    validate_image_file,
    get_image_metadata,
    generate_standardized_filename,
    calculate_folder_structure,
    create_metadata_dict,
    compress_image_if_needed,
    batch_rename_preview
)

# Page configuration
st.set_page_config(
    page_title="Giraffe Image Management System",
    page_icon="🦒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling (minimal - no forced backgrounds)
st.markdown("""
<style>
    .logo-title {
        color: #2E8B57;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .logo-subtitle {
        color: #4F4F4F;
        font-size: 1.3rem;
        font-weight: 300;
        margin-top: 0;
    }
</style>
""", unsafe_allow_html=True)

# Constants
BUCKET_NAME = "giraffe-conservation-images"  # Replace with your actual bucket name

# Country and site options
COUNTRIES_SITES = {
    "AGO": ["LLNP", "IONP"],
    "NAM": ["EHGR", "UIIFA", "NANW"], 
    "KEN": ["MMNR", "RUNP"]
}

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'storage_client' not in st.session_state:
        st.session_state.storage_client = None
    if 'selected_country' not in st.session_state:
        st.session_state.selected_country = None
    if 'selected_site' not in st.session_state:
        st.session_state.selected_site = None
    if 'site_selection_complete' not in st.session_state:
        st.session_state.site_selection_complete = False
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'processed_images' not in st.session_state:
        st.session_state.processed_images = []
    if 'available_buckets' not in st.session_state:
        st.session_state.available_buckets = []
    if 'folder_name' not in st.session_state:
        st.session_state.folder_name = None
    
    # Reset incompatible country/site combinations
    validate_country_site_compatibility()

def validate_country_site_compatibility():
    """Ensure selected country and site are compatible with current structure"""
    current_country = st.session_state.get('selected_country')
    current_site = st.session_state.get('selected_site')
    
    # Check if current country is valid
    if current_country and current_country not in COUNTRIES_SITES:
        st.session_state.selected_country = None
        st.session_state.selected_site = None
        st.session_state.site_selection_complete = False
    
    # Check if current site is valid for the current country
    elif current_country and current_site:
        available_sites = COUNTRIES_SITES.get(current_country, [])
        if current_site not in available_sites:
            st.session_state.selected_site = None
            st.session_state.site_selection_complete = False

def authenticate_google_cloud():
    """Handle Google Cloud authentication"""
    st.header("🔐 Google Cloud Authentication")
    
    st.write("Upload your Google Cloud Service Account JSON key file to authenticate:")
    
    uploaded_file = st.file_uploader(
        "Choose JSON key file",
        type=['json'],
        help="Download this from Google Cloud Console > IAM & Admin > Service Accounts"
    )
    
    if uploaded_file is not None:
        try:
            # Read the JSON content
            key_data = json.load(uploaded_file)
            
            # Create credentials from the service account info
            credentials = service_account.Credentials.from_service_account_info(key_data)
            
            # Initialize the storage client
            storage_client = storage.Client(credentials=credentials)
            
            # Test the connection
            try:
                # Try to list buckets to verify authentication
                buckets = list(storage_client.list_buckets())
                st.success("✅ Successfully authenticated with Google Cloud!")
                st.session_state.authenticated = True
                st.session_state.storage_client = storage_client
                
                # Display available buckets
                if buckets:
                    bucket_names = [bucket.name for bucket in buckets]
                    st.session_state.available_buckets = bucket_names
                    st.info(f"Found {len(buckets)} bucket(s) in your project")
                    st.write("Available buckets:", bucket_names)
                
                # Add a button to proceed to next step
                if st.button("✅ Continue to Site Selection", type="primary"):
                    st.rerun()
                
            except Exception as e:
                st.error(f"Authentication failed: {str(e)}")
                
        except Exception as e:
            st.error(f"Error reading service account file: {str(e)}")
    
    else:
        st.info("Please upload your service account JSON key file to continue.")

def site_selection():
    """Handle site selection interface"""
    st.header("📍 Site Selection")
    
    # Country selection dropdown with proper error handling
    available_countries = list(COUNTRIES_SITES.keys())
    
    # Get the current country from session state, with fallback
    current_country = st.session_state.get('selected_country')
    if current_country not in available_countries:
        current_country = available_countries[0]  # Default to first country
        st.session_state.selected_country = current_country
    
    # Find index safely
    try:
        country_index = available_countries.index(current_country)
    except ValueError:
        country_index = 0
        st.session_state.selected_country = available_countries[0]
    
    selected_country = st.selectbox(
        "Select the country:",
        options=available_countries,
        index=country_index,
        help="Choose the country where images were taken"
    )
    
    # Store selected country
    st.session_state.selected_country = selected_country
    
    # Site selection dropdown based on selected country with proper error handling
    available_sites = COUNTRIES_SITES[selected_country]
    
    # Get the current site from session state, with fallback
    current_site = st.session_state.get('selected_site')
    if current_site not in available_sites:
        current_site = available_sites[0]  # Default to first site
        st.session_state.selected_site = current_site
    
    # Find index safely
    try:
        site_index = available_sites.index(current_site)
    except ValueError:
        site_index = 0
        st.session_state.selected_site = available_sites[0]
    
    selected_site = st.selectbox(
        "Select the site:",
        options=available_sites,
        index=site_index,
        help="Choose the specific site within the selected country"
    )
    
    if selected_country and selected_site:
        st.session_state.selected_site = selected_site
        st.success(f"✅ Selected: {selected_country} - {selected_site}")
        
        # Additional metadata collection
        col1, col2 = st.columns(2)
        
        with col1:
            # Survey date as YYYY/MM
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            survey_year = st.selectbox("Survey Year", 
                                     options=list(range(current_year - 10, current_year + 2)),
                                     index=10)  # Default to current year
            
            survey_month = st.selectbox("Survey Month",
                                      options=list(range(1, 13)),
                                      format_func=lambda x: f"{x:02d} - {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][x-1]}",
                                      index=current_month-1)  # Default to current month
        
        with col2:
            photographer = st.text_input(
                "Photographer Initials", 
                max_chars=2,
                help="Enter exactly 2 characters (e.g., 'AB')"
            )
        
        # Create survey date from year/month
        survey_date = datetime(survey_year, survey_month, 1).date()
        
        # Store metadata in session state
        st.session_state.metadata = {
            'country': selected_country,
            'site': selected_site,
            'survey_date': survey_date,
            'survey_year': survey_year,
            'survey_month': survey_month,
            'photographer': photographer,
            'initials': photographer.strip().upper(),  # Add initials field for consistency
            'camera_model': '',  # Keep for compatibility but empty
            'notes': ''  # Keep for compatibility but empty
        }
        
        # Only show review and continue if photographer initials are filled and exactly 2 characters
        if photographer.strip() and len(photographer.strip()) == 2:  # Check if photographer initials are exactly 2 chars
            # Show current selections
            st.subheader("📋 Review Your Selections")
            st.write(f"**Country:** {selected_country}")
            st.write(f"**Site:** {selected_site}")
            st.write(f"**Survey Period:** {survey_year}/{survey_month:02d}")
            st.write(f"**Photographer:** {photographer}")
            
            # Manual continue button - only when user clicks
            st.info("👆 Please review your selections above, then click the button below to continue.")
            if st.button("✅ Continue to Image Upload", type="primary"):
                st.session_state.site_selection_complete = True
                st.rerun()
        else:
            # Show a message asking for required fields
            if not photographer.strip():
                st.info("📝 **Please fill in the Photographer Initials** to continue to the next step.")
            elif len(photographer.strip()) != 2:
                st.warning("⚠️ **Photographer Initials must be exactly 2 characters** (e.g., 'AB')")
        
        # NEVER auto-progress - only return True if user has explicitly clicked continue
        return False
    
    return False

def image_processing():
    """Handle image folder upload, renaming, and processing"""
    st.header("📸 Image Processing")
    
    if not st.session_state.selected_site:
        st.warning("Please select a site first!")
        return False
    
    # Explanation of folder upload process
    st.info("📁 **How to upload a folder of images:**")
    st.write("""
    **ZIP your image folder:**
    1. Create a ZIP file containing all your images
    2. Click "Browse files" below
    3. Select your ZIP file
    4. Click "Open"
    
    We'll automatically extract all images from the ZIP file.
    """)
    
    st.info("📅 **Date Handling**: Images will be renamed using their EXIF DateTimeOriginal when available, otherwise the survey date will be used.")
    
    st.info("📂 **Folder Naming**: Upload folders will be automatically renamed to `COUNTRY_SITE_YYYYMM` format (e.g., `AGO_LLNP_202507`)")
    
    # File upload for ZIP files only
    uploaded_files = st.file_uploader(
        "Upload ZIP file containing images",
        type=['zip'],
        accept_multiple_files=False,
        help="Upload a ZIP file containing all your images"
    )
    
    # Display upload limits
    st.caption("💾 **Upload Limits**: Maximum 2GB total, 50MB per image")
    
    if uploaded_files:
        # Convert single file to list for consistency with existing code
        uploaded_files_list = [uploaded_files]
        
        # Check total size limit (2GB = 2048MB)
        total_size_mb = len(uploaded_files.getvalue()) / (1024 * 1024)
        max_size_gb = 2
        max_size_mb = max_size_gb * 1024
        
        if total_size_mb > max_size_mb:
            st.error(f"❌ ZIP file size ({total_size_mb:.2f} MB) exceeds the {max_size_gb}GB limit!")
            st.info(f"Please compress your ZIP file or reduce the number of images. Current limit: {max_size_mb} MB")
            return False
        
        # Extract folder name from ZIP file name, but rename it to country_site_yyyymm format
        original_folder_name = os.path.splitext(uploaded_files.name)[0]  # Remove .zip extension
        
        # Create standardized folder name: country_site_yyyymm
        folder_name = f"{st.session_state.metadata['country']}_{st.session_state.metadata['site']}_{st.session_state.metadata['survey_year']}{st.session_state.metadata['survey_month']:02d}"
        
        # Show folder name transformation
        if original_folder_name != folder_name:
            st.info(f"📂 **Folder renamed:** `{original_folder_name}` → `{folder_name}`")
            st.caption("Using standardized format: COUNTRY_SITE_YYYYMM")
        
        # Store folder name in session state
        st.session_state.folder_name = folder_name
        st.session_state.uploaded_files = uploaded_files_list
        
        # Display upload summary
        st.success(f"📁 **ZIP file uploaded:** `{uploaded_files.name}`")
        st.success(f"📂 **Standardized folder name:** `{folder_name}`")
        st.info(f"📊 File size: {total_size_mb:.2f} MB")
        
        # Extract images from ZIP file
        all_images = []
        zip_extracted = False
        
        # Handle ZIP file extraction (we know it's always a ZIP now)
        try:
            zip_data = uploaded_files.getvalue()
            with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():  # Skip directories
                        file_name = file_info.filename
                        # Check if it's an image file
                        if any(file_name.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']):
                            try:
                                image_data = zip_ref.read(file_name)
                                # Create a mock uploaded file object for consistency
                                class MockUploadedFile:
                                    def __init__(self, name, data):
                                        self.name = name.split('/')[-1]  # Get just the filename
                                        self._data = data
                                    def read(self):
                                        return self._data
                                    def getvalue(self):
                                        return self._data
                                
                                all_images.append(MockUploadedFile(file_name, image_data))
                                zip_extracted = True
                            except Exception as e:
                                st.warning(f"⚠️ Could not extract {file_name} from ZIP: {str(e)}")
            
            if zip_extracted:
                st.success(f"📦 Extracted {len(all_images)} images from ZIP file")
            else:
                st.error("❌ No valid image files found in ZIP!")
                return False
                
        except Exception as e:
            st.error(f"❌ Error processing ZIP file {uploaded_files.name}: {str(e)}")
            return False
        
        st.info(f"📊 Total images to process: {len(all_images)}")
        
        # Process images using utility functions
        processed_images = []
        
        # Create preview using batch rename utility
        preview_data = batch_rename_preview(
            all_images,
            st.session_state.metadata['country'],
            st.session_state.metadata['site'],
            st.session_state.metadata['survey_date'],
            st.session_state.metadata.get('photographer')
        )
        
        # Process each image with size checking
        oversized_files = []
        
        for idx, (uploaded_file, preview) in enumerate(zip(all_images, preview_data)):
            # Read image data - handle both regular uploaded files and extracted ZIP files
            try:
                if hasattr(uploaded_file, '_data'):
                    # This is a MockUploadedFile from ZIP extraction
                    image_data = uploaded_file._data
                else:
                    # This is a regular uploaded file
                    image_data = uploaded_file.getvalue()
            except Exception as e:
                st.error(f"❌ Error reading {uploaded_file.name}: {str(e)}")
                continue
            
            # Check individual file size (50MB limit)
            file_size_mb = len(image_data) / (1024 * 1024)
            if file_size_mb > 50:
                oversized_files.append(f"{uploaded_file.name} ({file_size_mb:.2f} MB)")
                continue
            
            # Validate image
            is_valid, error_msg = validate_image_file(image_data)
            if not is_valid:
                st.error(f"❌ {uploaded_file.name}: {error_msg}")
                continue
            
            # Get image metadata (including EXIF)
            img_metadata = get_image_metadata(image_data)
            
            # Compress if needed
            compressed_data = compress_image_if_needed(image_data)
            
            processed_images.append({
                'original_name': uploaded_file.name,
                'new_filename': preview['new_name'],
                'data': compressed_data,
                'size': len(compressed_data),
                'original_size': len(image_data),
                'metadata': img_metadata,
                'compressed': len(compressed_data) < len(image_data),
                'date_source': preview.get('date_source', 'Survey Date'),
                'date_used': preview.get('date_used', 'Unknown'),
                'datetime_original': preview.get('datetime_original')
            })
        
        # Show oversized files warning
        if oversized_files:
            st.warning(f"⚠️ **{len(oversized_files)} files skipped** (exceed 50MB limit):")
            for file in oversized_files:
                st.write(f"• {file}")
        
        st.session_state.processed_images = processed_images
        
        if not processed_images:
            st.error("❌ No valid images to process!")
            return False
        
        # Display processing results
        st.subheader("📋 Processing Results")
        
        # Create a comprehensive DataFrame for display
        df_data = []
        exif_count = 0
        survey_count = 0
        
        for img in processed_images:
            # Count date sources
            if img.get('date_source') == 'EXIF':
                exif_count += 1
            else:
                survey_count += 1
                
            # Format datetime for display
            datetime_str = "Not available"
            if img.get('datetime_original'):
                datetime_str = img['datetime_original'].strftime('%Y-%m-%d %H:%M:%S')
            
            df_data.append({
                'Original Name': img['original_name'],
                'New Name': img['new_filename'],
                'Date Source': img.get('date_source', 'Survey Date'),
                'Date Used': img.get('date_used', 'Unknown'),
                'EXIF DateTime': datetime_str,
                'Original Size (MB)': f"{img['original_size'] / (1024*1024):.2f}",
                'Final Size (MB)': f"{img['size'] / (1024*1024):.2f}",
                'Compressed': '✅' if img['compressed'] else '➖',
                'Format': img['metadata'].get('format', 'Unknown'),
                'Dimensions': f"{img['metadata'].get('width', '?')}x{img['metadata'].get('height', '?')}"
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        # Show date source summary
        st.info(f"📅 **Date Sources**: {exif_count} images used EXIF date, {survey_count} used survey date")
        
        # Show compression summary
        total_original = sum(img['original_size'] for img in processed_images)
        total_final = sum(img['size'] for img in processed_images)
        compression_saved = total_original - total_final
        
        if compression_saved > 0:
            st.success(f"💾 Space saved through compression: {compression_saved / (1024*1024):.2f} MB")
        
        # Preview some images
        st.subheader("🖼️ Image Preview")
        cols = st.columns(min(3, len(processed_images)))
        
        for idx, img in enumerate(processed_images[:3]):  # Show first 3 images
            with cols[idx]:
                try:
                    pil_image = Image.open(io.BytesIO(img['data']))
                    st.image(pil_image, caption=img['new_filename'], use_column_width=True)
                    
                    # Show image details
                    st.caption(f"📐 {img['metadata'].get('width')}x{img['metadata'].get('height')} px")
                    st.caption(f"📄 {img['metadata'].get('format')} format")
                    
                except Exception as e:
                    st.error(f"Error displaying {img['original_name']}: {str(e)}")
        
        # Show total statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Processed Images", len(processed_images))
        with col2:
            st.metric("Total Size", f"{total_final / (1024*1024):.2f} MB")
        with col3:
            st.metric("Folder Name", folder_name)
        
        # Add continue button
        if folder_name and st.button("✅ Continue to Upload", type="primary"):
            st.rerun()
        
        return True
    
    return False

def upload_to_gcs():
    """Upload processed images to Google Cloud Storage"""
    st.header("☁️ Upload to Google Cloud Storage")
    
    if not st.session_state.processed_images:
        st.warning("No processed images found. Please upload and process images first!")
        return
    
    if not st.session_state.available_buckets:
        st.error("No buckets available. Please check your authentication.")
        return
    
    # Show bucket naming convention info
    st.info("🏗️ **Bucket Auto-Selection**: The system automatically selects buckets following the `gcf_country_site` naming convention")
    
    # Auto-select bucket based on country and site, with manual override option
    st.subheader("🪣 Bucket Selection")
    
    # Generate expected bucket name based on country and site
    expected_bucket = f"gcf_{st.session_state.metadata['country'].lower()}_{st.session_state.metadata['site'].lower()}"
    
    # Find matching bucket (case-insensitive and flexible matching)
    auto_selected_bucket = None
    for bucket in st.session_state.available_buckets:
        # Exact match (case-insensitive)
        if bucket.lower() == expected_bucket.lower():
            auto_selected_bucket = bucket
            break
        # Partial match for variations (e.g., gcf-ago-llnp vs gcf_ago_llnp)
        elif (bucket.lower().replace('-', '_').replace('.', '_') == 
              expected_bucket.lower().replace('-', '_').replace('.', '_')):
            auto_selected_bucket = bucket
            break
    
    # Show auto-selection info
    if auto_selected_bucket:
        st.success(f"🎯 **Auto-selected bucket:** `{auto_selected_bucket}`")
        st.info(f"✨ Based on pattern: `gcf_{st.session_state.metadata['country'].lower()}_{st.session_state.metadata['site'].lower()}`")
        default_bucket = auto_selected_bucket
    else:
        st.warning(f"⚠️ **No matching bucket found** for pattern: `{expected_bucket}`")
        st.info("Please select a bucket manually from the list below.")
        default_bucket = st.session_state.available_buckets[0] if st.session_state.available_buckets else None
    
    # Get index for default selection
    try:
        default_index = st.session_state.available_buckets.index(default_bucket) if default_bucket else 0
    except ValueError:
        default_index = 0
    
    # Bucket selection dropdown with auto-selection
    bucket_name = st.selectbox(
        "Select Google Cloud Storage Bucket:",
        options=st.session_state.available_buckets,
        index=default_index,
        help="Auto-selected based on country/site pattern, but you can change if needed"
    )
    
    # Show pattern matching info
    if bucket_name != auto_selected_bucket and auto_selected_bucket:
        st.info(f"💡 **Note:** You've selected `{bucket_name}` instead of the auto-matched `{auto_selected_bucket}`")
    
    # Show all available buckets for reference
    with st.expander("📋 View All Available Buckets", expanded=False):
        st.write("**Available buckets in your project:**")
        for idx, bucket in enumerate(st.session_state.available_buckets, 1):
            icon = "🎯" if bucket == auto_selected_bucket else "📦"
            selected_icon = " ✅" if bucket == bucket_name else ""
            st.write(f"{icon} `{bucket}`{selected_icon}")
        
        st.caption("🎯 = Auto-matched bucket, ✅ = Currently selected")
    
    # Folder path is standardized as country_site_yyyymm
    folder_name = st.session_state.folder_name
    st.subheader("📁 Folder Configuration")
    st.info(f"📂 Upload folder: `{folder_name}`")
    st.caption("Standardized format: COUNTRY_SITE_YYYYMM (e.g., AGO_LLNP_202507)")
    st.caption("Images will be uploaded to this folder in your selected bucket")
    
    # Display folder path that will be created
    folder_path = f"{folder_name}/"
    
    # Additional upload options (removed overwrite option)
    st.subheader("Upload Options")
    
    # Auto-compression explanation and option
    st.info("🤖 **What is Auto-compress?**")
    st.write("""
    - **Reduces file size** of images larger than 10MB
    - **Saves storage costs** on Google Cloud
    - **Faster uploads** with smaller files
    - **Maintains image quality** using smart compression
    - **Original filename preserved** with quality intact
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        create_backup = st.checkbox("Create backup metadata file", value=True)
        compress_large_images = st.checkbox("Auto-compress large images (recommended)", value=True)
    
    with col2:
        notify_completion = st.checkbox("Show detailed completion report", value=True)
    
    # Use folder name as-is without timestamp option
    st.info(f"📂 Upload path: `{folder_path}`")
    
    # Display upload summary
    st.subheader("📊 Upload Summary")
    total_files = len(st.session_state.processed_images)
    total_size = sum(img['size'] for img in st.session_state.processed_images)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Files to Upload", total_files)
    with col2:
        st.metric("Total Size", f"{total_size / (1024*1024):.2f} MB")
    with col3:
        # Show if bucket was auto-selected or manually chosen
        bucket_status = "🎯 Auto-selected" if bucket_name == auto_selected_bucket else "✋ Manually selected"
        st.metric("Target Bucket", bucket_name, delta=bucket_status)
    
    # Show warning about no overwrite
    st.warning("⚠️ **No Overwrite Policy**: Files will be skipped if they already exist in the bucket")
    
    if st.button("🚀 Upload Images", type="primary"):
        if not bucket_name:
            st.error("Please select a bucket!")
            return
        
        try:
            # Get the bucket
            bucket = st.session_state.storage_client.bucket(bucket_name)
            
            # Create progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            uploaded_count = 0
            failed_uploads = []
            skipped_files = []
            upload_details = []
            
            for idx, img in enumerate(st.session_state.processed_images):
                try:
                    # Construct blob name
                    blob_name = folder_path + img['new_filename']
                    
                    # Check if file exists (NO OVERWRITE ALLOWED)
                    blob = bucket.blob(blob_name)
                    if blob.exists():
                        skipped_files.append(f"{img['new_filename']} (already exists)")
                        continue
                    
                    # Upload image data
                    blob.upload_from_string(img['data'])
                    
                    # Create comprehensive metadata using utility function
                    metadata = create_metadata_dict(
                        st.session_state.metadata['site'],
                        st.session_state.metadata['survey_date'],
                        st.session_state.metadata.get('photographer'),
                        st.session_state.metadata.get('camera_model'),
                        st.session_state.metadata.get('notes'),
                        img['original_name']
                    )
                    
                    # Add image-specific metadata
                    metadata.update({
                        'folder_name': folder_name,
                        'country': st.session_state.metadata['country'],
                        'file_size_bytes': str(img['size']),
                        'original_size_bytes': str(img.get('original_size', img['size'])),
                        'compressed': str(img.get('compressed', False)),
                        'image_format': img['metadata'].get('format', 'Unknown'),
                        'image_width': str(img['metadata'].get('width', 0)),
                        'image_height': str(img['metadata'].get('height', 0)),
                        'survey_year': str(st.session_state.metadata['survey_year']),
                        'survey_month': str(st.session_state.metadata['survey_month'])
                    })
                    
                    blob.metadata = metadata
                    blob.patch()
                    
                    # Track upload details
                    upload_details.append({
                        'filename': img['new_filename'],
                        'size_mb': img['size'] / (1024*1024),
                        'blob_path': blob_name,
                        'upload_time': datetime.now().isoformat()
                    })
                    
                    uploaded_count += 1
                    progress = (uploaded_count + len(skipped_files)) / total_files
                    progress_bar.progress(progress)
                    status_text.text(f"✅ Uploaded {img['new_filename']} ({uploaded_count}/{total_files})")
                    
                except Exception as e:
                    error_msg = f"{img['new_filename']}: {str(e)}"
                    failed_uploads.append(error_msg)
                    st.error(f"❌ Error uploading {error_msg}")
            
            # Create backup metadata file if requested
            if create_backup and uploaded_count > 0:
                try:
                    backup_metadata = {
                        'upload_session': {
                            'timestamp': datetime.now().isoformat(),
                            'country': st.session_state.metadata['country'],
                            'site': st.session_state.metadata['site'],
                            'survey_year': st.session_state.metadata['survey_year'],
                            'survey_month': st.session_state.metadata['survey_month'],
                            'photographer': st.session_state.metadata.get('photographer'),
                            'folder_name': folder_name,
                            'folder_format': 'COUNTRY_SITE_YYYYMM',
                            'bucket_name': bucket_name,
                            'total_files': total_files,
                            'successful_uploads': uploaded_count,
                            'skipped_files': len(skipped_files),
                            'failed_uploads': len(failed_uploads)
                        },
                        'files': upload_details,
                        'skipped_files': skipped_files,
                        'failed_files': failed_uploads
                    }
                    
                    backup_blob_name = f"{folder_path}_upload_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    backup_blob = bucket.blob(backup_blob_name)
                    backup_blob.upload_from_string(json.dumps(backup_metadata, indent=2))
                    st.info(f"📋 Metadata backup saved to: {backup_blob_name}")
                    
                except Exception as e:
                    st.warning(f"⚠️ Could not create metadata backup: {str(e)}")
            
            # Show completion summary
            if uploaded_count == total_files:
                st.success(f"🎉 Successfully uploaded all {uploaded_count} images to gs://{bucket_name}/{folder_path}")
            elif uploaded_count > 0:
                st.warning(f"⚠️ Uploaded {uploaded_count} out of {total_files} images")
                if skipped_files:
                    st.info(f"📋 {len(skipped_files)} files were skipped (already exist)")
            else:
                st.error("❌ No files were uploaded successfully")
            
            # Detailed completion report
            if notify_completion and (uploaded_count > 0 or skipped_files):
                st.subheader("📈 Upload Completion Report")
                
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Files", total_files)
                with col2:
                    st.metric("Uploaded", uploaded_count)
                with col3:
                    st.metric("Skipped", len(skipped_files))
                with col4:
                    st.metric("Failed", len(failed_uploads))
                
                # Upload details
                if upload_details:
                    st.write("**✅ Successfully Uploaded Files:**")
                    details_df = pd.DataFrame(upload_details)
                    st.dataframe(details_df, use_container_width=True)
                
                # Skipped files
                if skipped_files:
                    st.write("**⏭️ Skipped Files (Already Exist):**")
                    for skip in skipped_files:
                        st.write(f"• {skip}")
                
                # Failed uploads
                if failed_uploads:
                    st.write("**❌ Failed Uploads:**")
                    for failure in failed_uploads:
                        st.write(f"• {failure}")
                
                # Final summary
                st.write("**📊 Upload Summary:**")
                summary_info = {
                    'Bucket': bucket_name,
                    'Folder Path': folder_path,
                    'Site': st.session_state.metadata['site'],
                    'Survey Period': f"{st.session_state.metadata['survey_year']}/{st.session_state.metadata['survey_month']:02d}",
                    'Upload Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Total Data Uploaded': f"{sum(detail['size_mb'] for detail in upload_details):.2f} MB"
                }
                
                for key, value in summary_info.items():
                    st.write(f"**{key}:** {value}")
                
        except Exception as e:
            st.error(f"Error accessing bucket '{bucket_name}': {str(e)}")
            st.info("Please check your bucket permissions.")
            
        # Reset button for new upload
        if st.button("🔄 Upload Another Folder", type="secondary"):
            # Clear processed images and folder name to start fresh
            st.session_state.processed_images = []
            st.session_state.folder_name = None
            st.session_state.site_selection_complete = False
            st.rerun()

def main():
    """Main application logic"""
    init_session_state()
    
    # Header with logo
    with st.container():
        # Try to load and display logo
        logo_displayed = False
        
        # Get the absolute path to the logo file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, 'logo.png')
        
        if os.path.exists(logo_path):
            try:
                # Process the logo for better display but preserve transparency
                with Image.open(logo_path) as img:
                    # Keep original format - preserve transparency
                    original_img = img.copy()
                    
                    # Resize if too large (maintain aspect ratio)
                    if img.width > 150:
                        aspect_ratio = img.height / img.width
                        new_width = 150
                        new_height = int(new_width * aspect_ratio)
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Simple layout - let Streamlit handle the background
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        # Display logo with transparency preserved
                        st.image(img, width=120)
                    with col2:
                        st.markdown("""
                        ### Image Management System
                        """)
                    
                    logo_displayed = True
                    
            except Exception as e:
                st.error(f"❌ Error processing logo: {str(e)}")
        
        # Fallback header without logo
        if not logo_displayed:
            st.markdown("""
            # 🦒 Image Management System
            """)
    
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Step 1: Authentication
    if not st.session_state.authenticated:
        st.sidebar.markdown("### Step 1: Authentication ❌")
        authenticate_google_cloud()
        return
    else:
        st.sidebar.markdown("### Step 1: Authentication ✅")
    
    # Step 2: Site Selection
    if not st.session_state.site_selection_complete:
        st.sidebar.markdown("### Step 2: Site Selection ❌")
        site_selection()
        return
    else:
        st.sidebar.markdown("### Step 2: Site Selection ✅")
        st.sidebar.write(f"**Country:** {st.session_state.get('selected_country', 'N/A')}")
        st.sidebar.write(f"**Site:** {st.session_state.selected_site}")
    
    # Step 3: Image Processing
    if not st.session_state.processed_images:
        st.sidebar.markdown("### Step 3: Image Processing ❌")
        image_processing()
        return
    else:
        st.sidebar.markdown("### Step 3: Image Processing ✅")
        st.sidebar.write(f"**Images:** {len(st.session_state.processed_images)} processed")
    
    # Step 4: Upload
    st.sidebar.markdown("### Step 4: Upload to Cloud ⏳")
    upload_to_gcs()
    
    # Reset button
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Reset Application"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()
