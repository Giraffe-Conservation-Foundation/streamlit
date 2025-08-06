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

# Page configuration - handled by main Twiga Tools app
# st.set_page_config(
#     page_title="Giraffe Image Management System",
#     page_icon="🦒",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# Constants
BUCKET_NAME = "giraffe-conservation-images"  # Replace with your actual bucket name

# Site options - you can modify these based on your requirements
SITE_OPTIONS = [
    "Masai Mara National Reserve",
    "Samburu National Reserve",
    "Tsavo East National Park",
    "Amboseli National Park",
    "Lake Nakuru National Park",
    "Meru National Park",
    "Laikipia Plateau",
    "Northern Kenya",
    "Southern Kenya",
    "Custom Site"
]

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'storage_client' not in st.session_state:
        st.session_state.storage_client = None
    if 'selected_site' not in st.session_state:
        st.session_state.selected_site = None
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'processed_images' not in st.session_state:
        st.session_state.processed_images = []
    if 'available_buckets' not in st.session_state:
        st.session_state.available_buckets = []
    if 'folder_name' not in st.session_state:
        st.session_state.folder_name = None

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
                
                # Store available buckets
                if buckets:
                    bucket_names = [bucket.name for bucket in buckets]
                    st.session_state.available_buckets = bucket_names
                
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
    
    # Site selection dropdown
    selected_site = st.selectbox(
        "Select the site where images were taken:",
        options=SITE_OPTIONS,
        index=0 if st.session_state.selected_site is None else SITE_OPTIONS.index(st.session_state.selected_site) if st.session_state.selected_site in SITE_OPTIONS else 0
    )
    
    # Custom site input if "Custom Site" is selected
    if selected_site == "Custom Site":
        custom_site = st.text_input("Enter custom site name:")
        if custom_site:
            selected_site = custom_site
    
    if selected_site and selected_site != "Custom Site":
        st.session_state.selected_site = selected_site
        
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
            
            photographer = st.text_input("Photographer Name")
        
        with col2:
            camera_model = st.text_input("Camera Model (optional)")
            notes = st.text_area("Additional Notes (optional)")
        
        # Create survey date from year/month
        survey_date = datetime(survey_year, survey_month, 1).date()
        
        # Store metadata in session state
        st.session_state.metadata = {
            'site': selected_site,
            'survey_date': survey_date,
            'survey_year': survey_year,
            'survey_month': survey_month,
            'photographer': photographer,
            'camera_model': camera_model,
            'notes': notes
        }
        
        # Add continue button
        if st.button("✅ Continue to Image Upload", type="primary"):
            st.rerun()
        
        return True
    
    return False

def image_processing():
    """Handle image folder upload, renaming, and processing"""
    st.header("📸 Image Processing")
    
    if not st.session_state.selected_site:
        st.warning("Please select a site first!")
        return False
    
    st.info("📁 Upload all images from a folder. Supported formats: JPG, JPEG, PNG, TIFF, TIF")
    
    # File upload with folder selection capability
    uploaded_files = st.file_uploader(
        "Select all images from your folder",
        type=['jpg', 'jpeg', 'png', 'tiff', 'tif'],
        accept_multiple_files=True,
        help="Select all images from your folder (Ctrl+A to select all files in a folder)"
    )
    
    # Display upload limits
    st.caption("💾 **Upload Limits**: Maximum 2GB total, 50MB per image")
    
    if uploaded_files:
        # Check total size limit (2GB = 2048MB)
        total_size_mb = sum(len(f.getvalue()) for f in uploaded_files) / (1024 * 1024)
        max_size_gb = 2
        max_size_mb = max_size_gb * 1024
        
        if total_size_mb > max_size_mb:
            st.error(f"❌ Total upload size ({total_size_mb:.2f} MB) exceeds the {max_size_gb}GB limit!")
            st.info(f"Please reduce the number of files or compress images. Current limit: {max_size_mb} MB")
            return False
        
        # Extract folder name from file paths (assuming all files come from same folder)
        folder_name = None
        if uploaded_files:
            # Try to extract common folder name from file paths
            first_file_path = uploaded_files[0].name
            if '/' in first_file_path or '\\' in first_file_path:
                # Extract parent folder name
                import os
                folder_name = os.path.dirname(first_file_path).split('/')[-1].split('\\')[-1]
            
            if not folder_name:
                # If no folder path detected, ask user for folder name
                folder_name = st.text_input(
                    "Enter folder name for organization:",
                    value=f"{st.session_state.metadata['site'].replace(' ', '_')}_{st.session_state.metadata['survey_year']}_{st.session_state.metadata['survey_month']:02d}",
                    help="This will be used as the folder name in Google Cloud Storage"
                )
        
        # Store folder name in session state
        st.session_state.folder_name = folder_name
        st.session_state.uploaded_files = uploaded_files
        
        # Process images using utility functions
        processed_images = []
        
        # Create preview using batch rename utility
        preview_data = batch_rename_preview(
            uploaded_files,
            st.session_state.metadata['site'],
            st.session_state.metadata['survey_date'],
            st.session_state.metadata.get('photographer')
        )
        
        # Process each image with size checking
        oversized_files = []
        
        for idx, (uploaded_file, preview) in enumerate(zip(uploaded_files, preview_data)):
            # Read image data
            image_data = uploaded_file.read()
            
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
            
            # Get image metadata
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
                'compressed': len(compressed_data) < len(image_data)
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
        for img in processed_images:
            df_data.append({
                'Original Name': img['original_name'],
                'New Name': img['new_filename'],
                'Original Size (MB)': f"{img['original_size'] / (1024*1024):.2f}",
                'Final Size (MB)': f"{img['size'] / (1024*1024):.2f}",
                'Compressed': '✅' if img['compressed'] else '➖',
                'Format': img['metadata'].get('format', 'Unknown'),
                'Dimensions': f"{img['metadata'].get('width', '?')}x{img['metadata'].get('height', '?')}"
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
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
    
    # Bucket selection dropdown from authenticated buckets
    bucket_name = st.selectbox(
        "Select Google Cloud Storage Bucket:",
        options=st.session_state.available_buckets,
        help="Choose from your available buckets"
    )
    
    # Folder path is same as uploaded folder name
    folder_name = st.session_state.folder_name
    
    # Display folder path that will be created
    folder_path = f"{folder_name}/"
    
    # Additional upload options (removed overwrite option)
    col1, col2 = st.columns(2)
    
    with col1:
        add_timestamp = st.checkbox("Add timestamp to folder", value=False,
                                   help="Adds timestamp to avoid folder conflicts")
        create_backup = st.checkbox("Create backup metadata file", value=True)
    
    with col2:
        notify_completion = st.checkbox("Show detailed completion report", value=True)
        compress_large_images = st.checkbox("Auto-compress large images", value=True)
    
    if add_timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_path = f"{folder_name}_{timestamp}/"
        st.info(f"📂 Final upload path: `{folder_path}`")
    
    # Display upload summary
    total_files = len(st.session_state.processed_images)
    total_size = sum(img['size'] for img in st.session_state.processed_images)
    
    # Review Section
    st.subheader("📋 Review Configuration")
    
    # Display configuration in organized columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Site & Survey Details:**")
        st.write(f"• Site: {st.session_state.metadata['site']}")
        st.write(f"• Survey Period: {st.session_state.metadata['survey_year']}/{st.session_state.metadata['survey_month']:02d}")
        if st.session_state.metadata.get('photographer'):
            st.write(f"• Photographer: {st.session_state.metadata['photographer']}")
    
    with col2:
        st.write("**Upload Details:**")
        st.write(f"• Bucket: {bucket_name}")
        st.write(f"• Folder: {folder_path}")
        st.write(f"• Files: {total_files} images")
        st.write(f"• Total Size: {total_size / (1024*1024):.2f} MB")
    
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
                            'site': st.session_state.metadata['site'],
                            'survey_year': st.session_state.metadata['survey_year'],
                            'survey_month': st.session_state.metadata['survey_month'],
                            'photographer': st.session_state.metadata.get('photographer'),
                            'folder_name': folder_name,
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
            st.rerun()

def main():
    """Main application logic"""
    init_session_state()
    
    # Title and description
    st.title("🦒 Giraffe Conservation Image Management System")
    st.markdown("---")
    
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
    if not st.session_state.selected_site:
        st.sidebar.markdown("### Step 2: Site Selection ❌")
        site_selection()
        return
    else:
        st.sidebar.markdown("### Step 2: Site Selection ✅")
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
