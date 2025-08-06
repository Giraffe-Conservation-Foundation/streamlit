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

def extract_countries_sites_from_buckets(bucket_names):
    """Extract country and site combinations from bucket names following gcf_country_site pattern"""
    countries_sites = {}
    
    for bucket_name in bucket_names:
        # Check if bucket follows the gcf_country_site pattern
        if bucket_name.lower().startswith('gcf'):
            parts = bucket_name.lower().split('_')
            # Expected pattern: gcf_country_site or variations with separators
            if len(parts) >= 3:
                # Extract country and site from bucket name
                country = parts[1].upper()  # Convert to uppercase for consistency
                site = parts[2].upper()     # Convert to uppercase for consistency
                
                # Add to countries_sites dictionary
                if country not in countries_sites:
                    countries_sites[country] = []
                
                if site not in countries_sites[country]:
                    countries_sites[country].append(site)
            
            # Also handle patterns with dashes (gcf-country-site)
            elif '-' in bucket_name:
                parts = bucket_name.lower().split('-')
                if len(parts) >= 3:
                    country = parts[1].upper()
                    site = parts[2].upper()
                    
                    if country not in countries_sites:
                        countries_sites[country] = []
                    
                    if site not in countries_sites[country]:
                        countries_sites[country].append(site)
    
    # Sort countries and sites for consistent display
    for country in countries_sites:
        countries_sites[country].sort()
    
    # Store in session state for persistence
    st.session_state.countries_sites = countries_sites
    
    return countries_sites

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
    if 'countries_sites' not in st.session_state:
        st.session_state.countries_sites = {}
    if 'survey_mode' not in st.session_state:
        st.session_state.survey_mode = False
    if 'survey_type' not in st.session_state:
        st.session_state.survey_type = None
    if 'camera_trap_mode' not in st.session_state:
        st.session_state.camera_trap_mode = False
    if 'camera_type' not in st.session_state:
        st.session_state.camera_type = None
    
    # Reset incompatible country/site combinations
    validate_country_site_compatibility()

def validate_country_site_compatibility():
    """Ensure selected country and site are compatible with current structure"""
    countries_sites = st.session_state.get('countries_sites', {})
    current_country = st.session_state.get('selected_country')
    current_site = st.session_state.get('selected_site')
    
    # Check if current country is valid
    if current_country and current_country not in countries_sites:
        st.session_state.selected_country = None
        st.session_state.selected_site = None
        st.session_state.site_selection_complete = False
    
    # Check if current site is valid for the current country
    elif current_country and current_site:
        available_sites = countries_sites.get(current_country, [])
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
                    
                    # Extract country/site combinations from bucket names
                    countries_sites = extract_countries_sites_from_buckets(bucket_names)
                    
                    # Display extracted country/site information
                    if countries_sites:
                        pass  # Countries/sites extracted successfully
                        
                    else:
                        st.warning("⚠️ **No GCF pattern buckets found!**")
                        st.info("Looking for buckets with pattern: `gcf_country_site` (e.g., 'gcf_ago_llnp', 'gcf_nam_ehgr')")
                
                else:
                    st.warning("No buckets found in your project")
                
                # Add a button to proceed to next step
                if countries_sites:
                    if st.button("✅ Continue to Site Selection", type="primary"):
                        st.rerun()
                else:
                    st.error("❌ **Cannot proceed:** No valid location buckets detected")
                    st.info("💡 **Solution:** Ensure your buckets follow the naming pattern `gcf_country_site`")
                
            except Exception as e:
                st.error(f"Authentication failed: {str(e)}")
                
        except Exception as e:
            st.error(f"Error reading service account file: {str(e)}")
    
    else:
        st.info("Please upload your service account JSON key file to continue.")

def site_selection():
    """Handle site selection interface"""
    st.header("📍 Step 2: Configuration & Site Selection")
    
    # Survey type selection (moved from mode detection to Step 2)
    st.subheader("📋 Survey Configuration")
    
    # Get current survey type from session state, with safe fallback
    current_survey_type = st.session_state.get('survey_type', 'survey_vehicle')
    survey_options = ["survey_vehicle", "survey_ground", "survey_aerial"]
    
    # Find the index safely
    try:
        survey_index = survey_options.index(current_survey_type)
    except ValueError:
        survey_index = 0  # Default to first option if current value not found
        current_survey_type = survey_options[0]
    
    survey_type = st.selectbox(
        "Select survey type:",
        survey_options,
        index=survey_index,
        format_func=lambda x: x.replace('survey_', '').replace('_', ' ').title() + " Survey",
        help="Choose the type of survey conducted"
    )
    
    # Store survey type in session state
    st.session_state.survey_type = survey_type
    
    # Country and Site Selection
    st.subheader("🌍 Location Selection")
    
    # Get countries/sites from session state instead of global variable
    countries_sites = st.session_state.get('countries_sites', {})
    
    # Debug information
    with st.expander("🔧 Debug Information", expanded=False):
        st.write("**Session State Keys:**", list(st.session_state.keys()))
        st.write("**Countries/Sites in Session:**", countries_sites)
        st.write("**Available Buckets:**", st.session_state.get('available_buckets', []))
        if st.session_state.get('available_buckets'):
            st.write("**GCF Pattern Buckets:**", [b for b in st.session_state.available_buckets if b.lower().startswith('gcf')])
    
    # Check if we have any countries/sites extracted from buckets
    if not countries_sites:
        st.error("❌ **No countries/sites available**")
        st.info("""
        **Possible causes:**
        - No buckets follow the `gcf_country_site` naming pattern
        - Authentication needs to be refreshed
        - Buckets are not accessible with current credentials
        
        **Expected bucket naming:** `gcf_ago_llnp`, `gcf_nam_ehgr`, etc.
        """)
        
        # Try to re-extract from available buckets if they exist
        if st.session_state.get('available_buckets'):
            st.info("🔄 **Attempting to re-extract countries/sites from available buckets...**")
            available_buckets = st.session_state.get('available_buckets', [])
            countries_sites = extract_countries_sites_from_buckets(available_buckets)
            
            if countries_sites:
                st.success(f"✅ **Re-extracted:** {len(countries_sites)} countries found!")
                st.rerun()  # Refresh to use the newly extracted data
            else:
                st.warning("⚠️ **Re-extraction failed:** No GCF pattern buckets found")
        
        if st.button("🔄 Refresh Authentication", type="secondary"):
            st.session_state.authenticated = False
            st.session_state.countries_sites = {}
            st.rerun()
        return False
    
    # Country selection dropdown with proper error handling
    available_countries = list(countries_sites.keys())
    
    if not available_countries:
        st.error("❌ No countries available from your bucket access")
        return False
    
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
    available_sites = countries_sites[selected_country]
    
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
        
        # Show corresponding bucket that will be used
        expected_bucket = f"gcf_{selected_country.lower()}_{selected_site.lower()}"
        matching_buckets = [b for b in st.session_state.available_buckets 
                          if b.lower().replace('-', '_').replace('.', '_') == expected_bucket]
        
        if not matching_buckets:
            st.warning(f"⚠️ **No exact bucket match found** for pattern `{expected_bucket}`")
        
        # Survey mode: Additional metadata collection
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
        
        # Store metadata in session state (including survey type and mode info)
        st.session_state.metadata = {
            'country': selected_country,
            'site': selected_site,
            'survey_date': survey_date,
            'survey_year': survey_year,
            'survey_month': survey_month,
            'photographer': photographer,
            'initials': photographer.strip().upper(),
            'camera_model': '',
            'notes': ''
        }
        
        # Store survey mode info for upload path generation
        st.session_state.survey_mode = True
        st.session_state.camera_trap_mode = False
        
        # Only show review and continue if photographer initials are filled and exactly 2 characters
        if photographer.strip() and len(photographer.strip()) == 2:
            # Show current selections
            st.subheader("📋 Review Your Selections")
            st.write(f"**Country:** {selected_country}")
            st.write(f"**Site:** {selected_site}")
            st.write(f"**Survey Type:** {survey_type.replace('survey_', '').replace('_', ' ').title()}")
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
        
        # Extract folder name from ZIP file name, but create appropriate folder structure based on mode
        original_folder_name = os.path.splitext(uploaded_files.name)[0]  # Remove .zip extension
        
        # For survey mode: just use yyyymm as folder name
        folder_name = f"{st.session_state.metadata['survey_year']}{st.session_state.metadata['survey_month']:02d}"
        format_description = "YYYYMM (survey mode)"
        
        # Show folder name transformation
        if original_folder_name != folder_name:
            st.info(f"📂 **Folder renamed:** `{original_folder_name}` → `{folder_name}`")
            st.caption(f"Using standardized format: {format_description}")
        
        # Store folder name in session state
        st.session_state.folder_name = folder_name
        st.session_state.uploaded_files = uploaded_files_list
        
        # Display upload summary



        
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
            
            if not zip_extracted:
                st.error("❌ No valid image files found in ZIP!")
                return False
                
        except Exception as e:
            st.error(f"❌ Error processing ZIP file {uploaded_files.name}: {str(e)}")
            return False
        
        # First, analyze all images to determine folder structure based on EXIF dates
        st.info("📅 **Analyzing image dates to determine folder structure...**")
        
        image_months = {}  # Dictionary to group images by YYYYMM
        images_without_exif = []
        
        # Analyze each image for EXIF date
        for img_file in all_images:
            try:
                # Get image data
                if hasattr(img_file, '_data'):
                    image_data = img_file._data
                else:
                    image_data = img_file.getvalue()
                
                # Extract image metadata to get EXIF date
                img_metadata = get_image_metadata(image_data)
                
                if 'datetime_original' in img_metadata:
                    # Use EXIF date
                    img_date = img_metadata['datetime_original']
                    month_key = f"{img_date.year}{img_date.month:02d}"
                else:
                    # No EXIF date, will use fallback date
                    images_without_exif.append(img_file.name)
                    fallback_date = st.session_state.metadata['survey_date']
                    month_key = f"{fallback_date.year}{fallback_date.month:02d}"
                
                # Group images by month
                if month_key not in image_months:
                    image_months[month_key] = []
                image_months[month_key].append(img_file)
                
            except Exception as e:
                st.warning(f"⚠️ Error analyzing {img_file.name}: {str(e)}")
                # Add to fallback month
                fallback_date = st.session_state.metadata['survey_date']
                month_key = f"{fallback_date.year}{fallback_date.month:02d}"
                if month_key not in image_months:
                    image_months[month_key] = []
                image_months[month_key].append(img_file)
        
        # Display analysis results
        total_months = len(image_months)
        if total_months > 1:
            st.success(f"📅 **Multiple months detected!** Images will be organized into {total_months} folders:")
            for month_key in sorted(image_months.keys()):
                count = len(image_months[month_key])
                year = month_key[:4]
                month = month_key[4:6]
                month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
                st.info(f"📁 **{month_key}** ({month_name} {year}): {count} images")
        else:
            month_key = list(image_months.keys())[0]
            year = month_key[:4]
            month = month_key[4:6]
            month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
            st.success(f"📅 **Single month detected:** {month_key} ({month_name} {year}) with {len(all_images)} images")
        
        # Show EXIF analysis summary
        if images_without_exif:
            st.warning(f"⚠️ **{len(images_without_exif)} images without EXIF dates** will use fallback date:")
            with st.expander("View images without EXIF dates"):
                for img_name in images_without_exif:
                    st.write(f"• {img_name}")
        
        # Store the month groupings in session state for later processing
        st.session_state.image_months = image_months
        
        # Process images using utility functions
        processed_images = []
        
        # Get survey info from metadata
        photographer = st.session_state.metadata.get('photographer')
        
        # Process images for each month group
        st.subheader("📋 Processing Results by Month")
        
        for month_key in sorted(image_months.keys()):
            st.write(f"### 📁 Processing folder: {month_key}")
            month_images = image_months[month_key]
            
            # Create preview using batch rename utility for this month's images
            preview_data = batch_rename_preview(
                month_images,
                st.session_state.metadata['country'],
                st.session_state.metadata['site'],
                st.session_state.metadata['survey_date'],
                photographer,
                None,  # station - not used for surveys
                None   # camera - not used for surveys
            )
            
            # Process each image in this month with size checking
            month_processed_images = []
            oversized_files = []
            
            for idx, (uploaded_file, preview) in enumerate(zip(month_images, preview_data)):
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
                
                month_processed_images.append({
                    'original_name': uploaded_file.name,
                    'new_filename': preview['new_name'],
                    'data': compressed_data,
                    'size': len(compressed_data),
                    'original_size': len(image_data),
                    'metadata': img_metadata,
                    'compressed': len(compressed_data) < len(image_data),
                    'date_source': preview.get('date_source', 'Survey Date'),
                    'date_used': preview.get('date_used', 'Unknown'),
                    'datetime_original': preview.get('datetime_original'),
                    'month_folder': month_key  # Add month folder identifier
                })
            
            # Add month's processed images to main list
            processed_images.extend(month_processed_images)
            
            # Show oversized files warning for this month
            if oversized_files:
                st.warning(f"⚠️ **{len(oversized_files)} files skipped in {month_key}** (exceed 50MB limit):")
                for file in oversized_files:
                    st.write(f"• {file}")
            
            # Show summary for this month
            if month_processed_images:
                st.success(f"✅ **{month_key}**: {len(month_processed_images)} images processed successfully")
            else:
                st.warning(f"⚠️ **{month_key}**: No valid images to process")
        
        st.session_state.processed_images = processed_images
        
        if not processed_images:
            st.error("❌ No valid images to process!")
            return False
        
        # Display processing results
        st.subheader("📋 Processing Results Summary")
        
        # Group results by month folder for display
        months_summary = {}
        for img in processed_images:
            month_key = img.get('month_folder', 'unknown')
            if month_key not in months_summary:
                months_summary[month_key] = []
            months_summary[month_key].append(img)
        
        # Show summary for each month folder
        if len(months_summary) > 1:
            st.info(f"📁 **Multiple folders will be created:** {len(months_summary)} different months detected")
            
            for month_key in sorted(months_summary.keys()):
                month_images = months_summary[month_key]
                year = month_key[:4]
                month = month_key[4:6]
                month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
                
                with st.expander(f"📁 **{month_key}** ({month_name} {year}) - {len(month_images)} images", expanded=True):
                    # Create DataFrame for this month
                    df_data = []
                    exif_count = 0
                    survey_count = 0
                    
                    for img in month_images:
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
                            'EXIF DateTime': datetime_str,
                            'Final Size (MB)': f"{img['size'] / (1024*1024):.2f}",
                            'Compressed': '✅' if img['compressed'] else '➖',
                        })
                    
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Show date source summary for this month
                    st.caption(f"📅 Date sources: {exif_count} EXIF, {survey_count} fallback")
        else:
            # Single month - show regular view
            month_key = list(months_summary.keys())[0]
            year = month_key[:4]
            month = month_key[4:6]
            month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
            st.success(f"📁 **Single folder:** {month_key} ({month_name} {year})")
            
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
                    month_info = img.get('month_folder', 'unknown')
                    st.image(pil_image, caption=f"{img['new_filename']} (→{month_info})", use_column_width=True)
                    
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
            folders_count = len(months_summary)
            st.metric("Folders to Create", folders_count)
        
        # Add continue button
        if len(months_summary) > 0 and st.button("✅ Continue to Upload", type="primary"):
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
    
    # Folder path is standardized based on mode
    folder_name = st.session_state.folder_name
    survey_mode = st.session_state.get('survey_mode', False)
    survey_type = st.session_state.get('survey_type', 'survey_vehicle')
    
    st.subheader("📁 Folder Configuration")
    
    if survey_mode:
        # Survey mode: bucket/survey/survey_[type]/yyyymm/
        survey_path = f"survey/{survey_type}/{folder_name}/"
        st.info(f"� **Survey Mode:** {survey_type.replace('_', ' ').title()}")
        st.info(f"�📂 Upload folder structure: `{survey_path}`")
        st.caption(f"Final path: bucket/{survey_path}")
    else:
        # Check if we're in camera trap mode
        camera_trap_mode = st.session_state.get('camera_trap_mode', False)
        camera_type = st.session_state.get('camera_type', 'camera_fence')
        
        if camera_trap_mode:
            # Camera trap mode with station subfolders: bucket/camera_trap/camera_[type]/yyyymm/station/camera/
            station = st.session_state.metadata.get('station', 'UNKNOWN').upper()
            camera = st.session_state.metadata.get('camera', 'UNKNOWN').upper()
            survey_path = f"camera_trap/{camera_type}/{folder_name}/{station}/{camera}/"
            st.info(f"📷 **Camera Trap Mode:** {camera_type.replace('_', ' ').title()}")
            st.info(f"📂 Upload folder structure: `{survey_path}`")
            st.caption(f"Final path: bucket/{survey_path}")
        else:
            # Legacy mode: bucket/folder_name/
            survey_path = f"{folder_name}/"
            st.info(f"🔧 **Legacy Mode**")
            st.info(f"📂 Upload folder: `{folder_name}`")
            st.caption("Format: COUNTRY_SITE_YYYYMM (e.g., AGO_LLNP_202507)")
    
    st.caption("Images will be uploaded to this folder structure in your selected bucket")
    
    # Display folder path that will be created
    folder_path = survey_path
    
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
    
    # Show warning about no overwrite - but proceed automatically
    st.warning("⚠️ **No Overwrite Policy**: Files will be skipped if they already exist in the bucket")
    
    # Auto-start upload (no button required)
    st.info("🚀 **Starting upload with automatic settings:** Auto-compress enabled, backup metadata enabled, detailed report enabled")
    
    # Set all options to enabled automatically
    create_backup = True
    compress_large_images = True  
    notify_completion = True
    
    # Start upload automatically
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
                # Get the correct folder path for this image based on its month
                img_month = img.get('month_folder', 'unknown')
                
                # Survey mode: bucket/survey/survey_[type]/yyyymm/
                survey_mode = st.session_state.get('survey_mode', False)
                survey_type = st.session_state.get('survey_type', 'survey_vehicle')
                img_folder_path = f"survey/{survey_type}/{img_month}/"
                
                # Construct blob name using the image-specific folder path
                    blob_name = img_folder_path + img['new_filename']
                    
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
                        'folder_path': img_folder_path,
                        'month_folder': img_month,
                        'upload_time': datetime.now().isoformat()
                    })
                    
                    uploaded_count += 1
                    progress = (uploaded_count + len(skipped_files)) / total_files
                    progress_bar.progress(progress)
                    year = img_month[:4]
                    month = img_month[4:6]
                    month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
                    status_text.text(f"✅ Uploaded {img['new_filename']} → {img_month} ({month_name} {year}) ({uploaded_count}/{total_files})")
                    
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
                # Group uploads by folder to show accurate summary
                folder_counts = {}
                for detail in upload_details:
                    folder = detail.get('month_folder', 'unknown')
                    if folder not in folder_counts:
                        folder_counts[folder] = 0
                    folder_counts[folder] += 1
                
                if len(folder_counts) > 1:
                    st.success(f"🎉 Successfully uploaded all {uploaded_count} images to {len(folder_counts)} different month folders in gs://{bucket_name}/")
                    for folder, count in sorted(folder_counts.items()):
                        year = folder[:4]
                        month = folder[4:6]
                        month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
                        st.info(f"📁 **{folder}** ({month_name} {year}): {count} images")
                else:
                    folder = list(folder_counts.keys())[0]
                    year = folder[:4]
                    month = folder[4:6]
                    month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
                    # Determine mode for path display
                    survey_mode = st.session_state.get('survey_mode', False)
                    survey_type = st.session_state.get('survey_type', 'survey_vehicle')
                    camera_trap_mode = st.session_state.get('camera_trap_mode', False)
                    camera_type = st.session_state.get('camera_type', 'camera_fence')
                    
                    if survey_mode:
                        path_display = f"survey/{survey_type}/{folder}/"
                    elif camera_trap_mode:
                        path_display = f"camera_trap/{camera_type}/{folder}/"
                    else:
                        path_display = f"{st.session_state.metadata['country']}_{st.session_state.metadata['site']}_{folder}/"
                    
                    st.success(f"🎉 Successfully uploaded all {uploaded_count} images to gs://{bucket_name}/{path_display}")
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
                
                # Upload details grouped by month
                if upload_details:
                    # Group uploads by month folder
                    uploads_by_month = {}
                    for detail in upload_details:
                        month = detail.get('month_folder', 'unknown')
                        if month not in uploads_by_month:
                            uploads_by_month[month] = []
                        uploads_by_month[month].append(detail)
                    
                    if len(uploads_by_month) > 1:
                        st.write("**✅ Successfully Uploaded Files (by Month):**")
                        for month_key in sorted(uploads_by_month.keys()):
                            month_uploads = uploads_by_month[month_key]
                            year = month_key[:4]
                            month = month_key[4:6]
                            month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
                            
                            with st.expander(f"📁 **{month_key}** ({month_name} {year}) - {len(month_uploads)} files", expanded=False):
                                month_df = pd.DataFrame(month_uploads)
                                st.dataframe(month_df, use_container_width=True)
                                total_mb = sum(detail['size_mb'] for detail in month_uploads)
                                st.caption(f"Total size: {total_mb:.2f} MB")
                    else:
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
                
                # Group summary by month
                uploads_by_month = {}
                for detail in upload_details:
                    month = detail.get('month_folder', 'unknown')
                    if month not in uploads_by_month:
                        uploads_by_month[month] = []
                    uploads_by_month[month].append(detail)
                
                summary_info = {
                    'Bucket': bucket_name,
                    'Site': st.session_state.metadata['site'],
                    'Upload Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Total Data Uploaded': f"{sum(detail['size_mb'] for detail in upload_details):.2f} MB",
                    'Folders Created': len(uploads_by_month)
                }
                
                # Show folder details
                if len(uploads_by_month) > 1:
                    summary_info['Upload Structure'] = "Multiple month folders"
                    folder_list = []
                    for month_key in sorted(uploads_by_month.keys()):
                        count = len(uploads_by_month[month_key])
                        year = month_key[:4]
                        month = month_key[4:6]
                        month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
                        folder_list.append(f"{month_key} ({month_name} {year}): {count} files")
                    summary_info['Month Distribution'] = " | ".join(folder_list)
                else:
                    month_key = list(uploads_by_month.keys())[0]
                    year = month_key[:4]
                    month = month_key[4:6]
                    month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
                    summary_info['Upload Structure'] = f"Single folder: {month_key} ({month_name} {year})"
                
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
                        pass  # Logo column, no additional content needed
                    
                    logo_displayed = True
                    
            except Exception as e:
                st.error(f"❌ Error processing logo: {str(e)}")
        
        # Fallback header without logo
        if not logo_displayed:
            pass  # No header needed when called from Twiga Tools
    
    # Landing page (only shown if not authenticated yet)
    if not st.session_state.authenticated:
        st.header("🚗 Survey Upload Tool")
        st.write("Welcome to the survey image upload system.")
        
        # Show process steps 1-6 on landing page
        st.subheader("📋 Upload Process Overview")
        st.info("""
        **Step 1:** Authenticate with Google Cloud
        **Step 2:** Configure survey type and select location  
        **Step 3:** Upload ZIP file with images
        **Step 4:** Review processed images
        **Step 5:** Confirm upload settings
        **Step 6:** Upload to cloud storage
        """)
        
        # Show authentication directly on landing page
        authenticate_google_cloud()
        return  # Don't show the rest of the app until authenticated
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Step 1: Authentication (completed)
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
        if st.session_state.get('survey_type'):
            st.sidebar.write(f"**Survey Type:** {st.session_state.survey_type.replace('_', ' ').title()}")
    
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
