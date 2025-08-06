import streamlit as st
import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import zipfile
import os
from datetime import datetime
import tempfile
import shutil

# Note: set_page_config is handled by the main Twiga Tools app
# st.set_page_config(
#     page_title="GiraffeSpotter ID book generator",
#     page_icon="📚",
#     layout="wide"
# )

# --- CONSTANTS ---
VIEWPOINT_PREFERENCE = ['left', 'right']  # Only left and right
UNIDENTIFIED_FOLDER = "Unidentified_annotations"

# --- UTILITY FUNCTIONS ---

def clean_nickname(nickname_value):
    """Clean nickname value to handle NaN, None, and empty strings"""
    if nickname_value is None:
        return ''
    if pd.isna(nickname_value):
        return ''
    nickname_str = str(nickname_value).strip()
    if nickname_str.lower() in ['nan', 'none', '']:
        return ''
    return nickname_str

def read_excel_file(uploaded_file):
    """Read the uploaded Excel file and return as DataFrame"""
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        return df, None
    except Exception as e:
        return None, str(e)

def process_annotations(df, include_unidentified=False):
    """Process the annotations DataFrame to group by individual ID"""
    processed_rows = []
    location_id = "Unknown Location"  # Default value
    
    for idx, row in df.iterrows():
        # Extract location ID from first row (assuming all rows have same location)
        if idx == 0:
            location_id = row.get('Encounter.locationID', 'Unknown Location') or 'Unknown Location'
        
        # Find all annotation numbers by looking at ViewPoint columns
        viewpoint_cols = [col for col in df.columns if col.startswith('Annotation') and col.endswith('.ViewPoint')]
        
        for viewpoint_col in viewpoint_cols:
            if pd.notna(row[viewpoint_col]):
                # Extract annotation number
                ann_num = viewpoint_col.split('.')[0].replace('Annotation', '')
                
                # Check if required fields exist
                image_url_col = f'Encounter.mediaAsset{ann_num}.imageUrl'
                bbox_col = f'Annotation{ann_num}.bbox'
                media_asset_col = f'Encounter.mediaAsset{ann_num}'
                
                # Also check for alternative column names
                if image_url_col not in df.columns:
                    # Try alternative naming patterns
                    alt_image_cols = [col for col in df.columns if f'mediaAsset{ann_num}' in col and 'imageUrl' in col]
                    if alt_image_cols:
                        image_url_col = alt_image_cols[0]
                
                if bbox_col not in df.columns:
                    # Try alternative naming patterns
                    alt_bbox_cols = [col for col in df.columns if f'Annotation{ann_num}' in col and 'bbox' in col]
                    if alt_bbox_cols:
                        bbox_col = alt_bbox_cols[0]
                
                # Check if we have the minimum required fields
                has_image_url = image_url_col in df.columns and pd.notna(row[image_url_col])
                has_bbox = bbox_col in df.columns and pd.notna(row[bbox_col])
                
                if has_image_url and has_bbox:
                    processed_row = {
                        'individual_id': row.get('Name0.value', UNIDENTIFIED_FOLDER) or UNIDENTIFIED_FOLDER,
                        'viewpoint': row[viewpoint_col],
                        'image_url': row[image_url_col],
                        'bbox': row[bbox_col],
                        'media_asset': row.get(media_asset_col, f'image_{ann_num}.jpg'),
                        'encounter_id': row.get('Encounter.id', 'unknown'),
                        # Extract additional information - updated column names
                        'sex': row.get('IndividualSummary.sex', row.get('Individual.sex', 'Unknown')),
                        'nickname': clean_nickname(row.get('Name1.value', '') or row.get('Individual.nickname', '') or '')
                    }
                    processed_rows.append(processed_row)
    
    # Convert to DataFrame and group by individual
    processed_df = pd.DataFrame(processed_rows)
    
    if processed_df.empty:
        return {}
    
    # Clean individual IDs
    processed_df['individual_id'] = processed_df['individual_id'].str.strip()
    processed_df['individual_id'] = processed_df['individual_id'].replace('', UNIDENTIFIED_FOLDER)
    
    # Filter unidentified if not wanted
    if not include_unidentified:
        processed_df = processed_df[processed_df['individual_id'] != UNIDENTIFIED_FOLDER]
    
    # Group by individual and select left/right annotations
    grouped = {}
    for individual_id, group in processed_df.groupby('individual_id'):
        selected_annotations = select_left_right_annotations(group)
        if selected_annotations:
            grouped[individual_id] = selected_annotations
    
    return grouped, location_id

def select_left_right_annotations(annotations_df):
    """Select one left and one right annotation for each individual"""
    selected = []
    
    # Look for exact left viewpoint
    left_matches = annotations_df[annotations_df['viewpoint'].str.lower() == 'left']
    if not left_matches.empty:
        selected.append(left_matches.iloc[0].to_dict())
    else:
        # Look for viewpoint containing 'left'
        left_similar = annotations_df[annotations_df['viewpoint'].str.contains('left', case=False, na=False)]
        if not left_similar.empty:
            selected.append(left_similar.iloc[0].to_dict())
    
    # Look for exact right viewpoint
    right_matches = annotations_df[annotations_df['viewpoint'].str.lower() == 'right']
    if not right_matches.empty:
        selected.append(right_matches.iloc[0].to_dict())
    else:
        # Look for viewpoint containing 'right'
        right_similar = annotations_df[annotations_df['viewpoint'].str.contains('right', case=False, na=False)]
        if not right_similar.empty:
            selected.append(right_similar.iloc[0].to_dict())
    
    # If we don't have both left and right, fill with any available
    remaining = annotations_df.copy()
    for sel in selected:
        # Remove already selected annotations
        remaining = remaining[remaining['viewpoint'] != sel['viewpoint']]
    
    while len(selected) < 2 and not remaining.empty:
        selected.append(remaining.iloc[0].to_dict())
        remaining = remaining.drop(remaining.index[:1])
    
    return selected

def download_and_crop_image(image_url, bbox_str, max_size=(800, 800)):  # Increased for much better quality
    """Download image and crop according to bounding box"""
    try:
        # Parse bounding box - handle different formats
        if isinstance(bbox_str, str):
            # Remove brackets and split
            bbox_clean = bbox_str.replace('[', '').replace(']', '').replace(' ', '')
            bbox_parts = bbox_clean.split(',')
            if len(bbox_parts) != 4:
                return None, f"Invalid bounding box format: expected 4 values, got {len(bbox_parts)}"
            bbox = [float(x) for x in bbox_parts]  # Use float first, then convert to int
            bbox = [int(x) for x in bbox]
        else:
            return None, f"Bounding box is not a string: {type(bbox_str)}"
        
        # Validate URL
        if not image_url or not isinstance(image_url, str) or not image_url.startswith('http'):
            return None, f"Invalid image URL: {image_url}"
        
        # Download image with better error handling
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(image_url, timeout=30, headers=headers)
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}: Failed to download image"
        
        if len(response.content) == 0:
            return None, "Downloaded image is empty"
        
        # Open and validate image
        try:
            img = Image.open(io.BytesIO(response.content))
            img.load()  # Force load to validate image
        except Exception as img_err:
            return None, f"Cannot open image: {str(img_err)}"
        
        # Get image dimensions
        img_width, img_height = img.size
        
        # Validate and adjust bounding box
        x, y, width, height = bbox
        
        # Ensure bounding box is within image bounds
        x = max(0, min(x, img_width - 1))
        y = max(0, min(y, img_height - 1))
        width = min(width, img_width - x)
        height = min(height, img_height - y)
        
        if width <= 0 or height <= 0:
            return None, f"Invalid crop dimensions: {width}x{height}"
        
        # Crop image using bbox [x, y, width, height] -> [x1, y1, x2, y2]
        crop_box = (x, y, x + width, y + height)
        
        cropped = img.crop(crop_box)
        
        # Resize to max_size while maintaining aspect ratio
        try:
            # Try newer Pillow syntax first
            cropped.thumbnail(max_size, Image.Resampling.LANCZOS)
        except AttributeError:
            # Fallback to older Pillow syntax
            cropped.thumbnail(max_size, Image.LANCZOS)
        
        return cropped, None
        
    except Exception as e:
        error_msg = f"Error processing image: {str(e)}"
        return None, error_msg

def create_id_book_page(individual_id, annotations):
    """Create a single page for an individual's ID book with left and right photos"""
    if not annotations:
        return None
    
    # Page dimensions (Portrait A4-like proportions, higher resolution for better quality)
    page_width, page_height = 1200, 1600  # Much larger for better quality
    img_width, img_height = 500, 500  # Increased image size for better quality
    margin = 50
    
    # Create page
    page = Image.new('RGB', (page_width, page_height), 'white')
    draw = ImageDraw.Draw(page)
    
    # Try to load fonts (increased sizes for larger page)
    try:
        title_font = ImageFont.truetype("arial.ttf", 64)  # Increased for higher resolution
        info_font = ImageFont.truetype("arial.ttf", 32)   # Increased for higher resolution
        label_font = ImageFont.truetype("arial.ttf", 24)  # Increased for higher resolution
    except:
        title_font = ImageFont.load_default()
        info_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
    
    # Get individual information (from first annotation)
    first_annotation = annotations[0]
    sex = first_annotation.get('sex', 'Unknown')
    nickname = first_annotation.get('nickname', '')
    
    # Title
    title = f"Individual ID: {individual_id}"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((page_width - title_width) // 2, 70), title, fill='black', font=title_font)  # Adjusted for larger page
    
    # Additional information
    info_y = 160  # Adjusted for larger page
    if nickname and nickname.strip() and nickname != individual_id:
        nickname_text = f"Nickname: {nickname}"
        nickname_bbox = draw.textbbox((0, 0), nickname_text, font=info_font)
        nickname_width = nickname_bbox[2] - nickname_bbox[0]
        draw.text(((page_width - nickname_width) // 2, info_y), nickname_text, fill='black', font=info_font)
        info_y += 50  # Increased spacing for larger fonts
    
    sex_text = f"Sex: {sex}"
    sex_bbox = draw.textbbox((0, 0), sex_text, font=info_font)
    sex_width = sex_bbox[2] - sex_bbox[0]
    draw.text(((page_width - sex_width) // 2, info_y), sex_text, fill='black', font=info_font)
    
    # Position images side by side (adjusted for higher resolution)
    left_x = (page_width // 2) - img_width - 50  # More spacing
    right_x = (page_width // 2) + 50
    img_y = 350  # Adjusted for larger page layout
    
    # Process annotations and place them - NO DUPLICATION
    left_annotation = None
    right_annotation = None
    
    for annotation in annotations:
        viewpoint = annotation['viewpoint'].lower()
        if 'left' in viewpoint and left_annotation is None:
            left_annotation = annotation
        elif 'right' in viewpoint and right_annotation is None:
            right_annotation = annotation
    
    # If we don't have specific left/right, use the first available for the appropriate side
    # But DON'T duplicate - only use each annotation once
    if left_annotation is None and right_annotation is None:
        # If no specific left/right viewpoints, put the first annotation on the left
        if annotations:
            left_annotation = annotations[0]
    elif left_annotation is None and len(annotations) > 1:
        # Look for a different annotation that's not already used for right
        for annotation in annotations:
            if annotation != right_annotation:
                left_annotation = annotation
                break
    elif right_annotation is None and len(annotations) > 1:
        # Look for a different annotation that's not already used for left
        for annotation in annotations:
            if annotation != left_annotation:
                right_annotation = annotation
                break
    
    # DO NOT duplicate the same image for both sides
    
    # Draw left image
    if left_annotation:
        image, error = download_and_crop_image(left_annotation['image_url'], left_annotation['bbox'], (img_width, img_height))
        if image:
            # Center the image
            img_w, img_h = image.size
            paste_x = left_x + (img_width - img_w) // 2
            paste_y = img_y + (img_height - img_h) // 2
            page.paste(image, (paste_x, paste_y))
            
            # Label
            draw.text((left_x, img_y + img_height + 20), "Left Side", fill='black', font=label_font)  # More spacing
        else:
            # Error placeholder
            draw.rectangle([left_x, img_y, left_x + img_width, img_y + img_height], outline='red', width=2)
            draw.text((left_x + 10, img_y + img_height//2), f"Error: {error[:30]}...", fill='red', font=label_font)
    else:
        # Empty placeholder for left side
        draw.rectangle([left_x, img_y, left_x + img_width, img_y + img_height], outline='lightgray', width=1, fill='white')
        draw.text((left_x + img_width//2 - 50, img_y + img_height//2), "No Left Image", fill='gray', font=label_font)
    
    # Draw right image
    if right_annotation:
        image, error = download_and_crop_image(right_annotation['image_url'], right_annotation['bbox'], (img_width, img_height))
        if image:
            # Center the image
            img_w, img_h = image.size
            paste_x = right_x + (img_width - img_w) // 2
            paste_y = img_y + (img_height - img_h) // 2
            page.paste(image, (paste_x, paste_y))
            
            # Label
            draw.text((right_x, img_y + img_height + 20), "Right Side", fill='black', font=label_font)  # More spacing
        else:
            # Error placeholder
            draw.rectangle([right_x, img_y, right_x + img_width, img_y + img_height], outline='red', width=2)
            draw.text((right_x + 10, img_y + img_height//2), f"Error: {error[:30]}...", fill='red', font=label_font)
    else:
        # Empty placeholder for right side
        draw.rectangle([right_x, img_y, right_x + img_width, img_y + img_height], outline='lightgray', width=1, fill='white')
        draw.text((right_x + img_width//2 - 50, img_y + img_height//2), "No Right Image", fill='gray', font=label_font)
    
    return page

def create_summary_page(grouped_annotations, location_id="Unknown Location"):
    """Create a summary page with statistics and optional background image"""
    page_width, page_height = 800, 1067  # Higher resolution portrait A4 (A4 ratio but larger)
    page = Image.new('RGB', (page_width, page_height), 'white')
    
    # Try to load and use background image
    background_image_path = None
    
    # Look for background image files in multiple locations
    search_paths = [
        ".",  # Current directory (wildbook_id_generator)
        "..",  # Parent directory (main folder)
        os.path.join("..", "shared"),  # Shared folder
    ]
    
    for search_dir in search_paths:
        for ext in ['png', 'jpg', 'jpeg']:
            for name in ['GCF_background_logo', 'background', 'cover', 'title_background', 'id_book_background']:
                test_path = os.path.join(search_dir, f"{name}.{ext}")
                if os.path.exists(test_path):
                    background_image_path = test_path
                    break
            if background_image_path:
                break
        if background_image_path:
            break
    
    # Apply background image if found
    if background_image_path:
        try:
            bg_img = Image.open(background_image_path)
            # Resize background to fill the page
            bg_img_resized = bg_img.resize((page_width, page_height), Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1)
            page.paste(bg_img_resized, (0, 0))
        except Exception as e:
            st.write(f"⚠️ Could not load background image {background_image_path}: {str(e)}")
    
    draw = ImageDraw.Draw(page)
    
    try:
        title_font = ImageFont.truetype("arial.ttf", 42)  # Increased for higher resolution
        text_font = ImageFont.truetype("arial.ttf", 24)   # Increased for higher resolution
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # Title with location ID - white text without background
    title = f"ID Book: {location_id}"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (page_width - title_width) // 2
    title_y = 130  # Adjusted for larger page
    
    draw.text((title_x, title_y), title, fill='white', font=title_font)
    
    # Statistics - simplified
    total_individuals = len(grouped_annotations)
    
    stats_text = [
        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Total Individuals: {total_individuals}",
    ]
    
    # Draw text with white color (no background)
    y_offset = 260  # Adjusted for larger page
    for line in stats_text:
        if line.strip():  # Only process non-empty lines
            text_bbox = draw.textbbox((0, 0), line, font=text_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_x = (page_width - text_width) // 2
            
            draw.text((text_x, y_offset), line, fill='white', font=text_font)
        y_offset += 40  # Increased spacing for larger fonts
    
    return page

# --- STREAMLIT APP ---

#st.title("GiraffeSpotter ID book generator")
st.markdown("Generate a photo ID book from a GiraffeSpotter (Wildbook) annotation export")

# How to use instructions - moved to top
st.markdown("""
### How to use:

1. **Export data from GiraffeSpotter (Wildbook)**: 
   - Go to GiraffeSpotter → Search → Encounter Search
   - Set your filters (location) and search
   - Go to Export tab → Click "Encounter Annotation Export"

2. **Upload the file**: Use the file uploader below

3. **Generate**: Click "Generate ID Book" to create and download your photo ID book
""")

# Sidebar configuration
st.sidebar.header("Configuration")

include_unidentified = st.sidebar.checkbox(
    "Include unidentified individuals",
    value=False,
    help="Include encounters without assigned individual IDs"
)

# File upload
st.header("1. Upload Wildbook Annotation Export")
uploaded_file = st.file_uploader(
    "Choose Excel file (.xlsx or .xls)",
    type=['xlsx', 'xls'],
    help="Upload the annotation export file from Wildbook"
)

if uploaded_file:
    # Read and process file
    with st.spinner("Reading Excel file..."):
        df, error = read_excel_file(uploaded_file)
    
    if error:
        st.error(f"Error reading file: {error}")
        st.stop()
    
    st.success(f"File loaded successfully! Found {len(df)} rows.")
    
    # Show file preview
    with st.expander("Preview file contents"):
        st.dataframe(df.head())
        st.write(f"Columns: {', '.join(df.columns.tolist())}")
    
    # Process annotations
    st.header("2. Process Annotations")
    
    with st.spinner("Processing annotations..."):
        result = process_annotations(
            df, 
            include_unidentified=include_unidentified
        )
        
        # Handle the return value (grouped_annotations, location_id)
        if isinstance(result, tuple):
            grouped_annotations, location_id = result
        else:
            # Fallback for backward compatibility
            grouped_annotations = result
            location_id = "Unknown Location"
    
    if not grouped_annotations:
        st.warning("No valid annotations found in the file.")
        st.stop()
    
    # Show processing results
    st.success(f"Found {len(grouped_annotations)} individuals with annotations")
    
    # Statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Individuals", len(grouped_annotations))
    with col2:
        total_annotations = sum(len(annotations) for annotations in grouped_annotations.values())
        st.metric("Total Annotations", total_annotations)
    with col3:
        avg_annotations = total_annotations / len(grouped_annotations) if grouped_annotations else 0
        st.metric("Avg per Individual", f"{avg_annotations:.1f}")
    
    # Show individual breakdown
    with st.expander("Individual breakdown"):
        breakdown_data = []
        for individual_id, annotations in grouped_annotations.items():
            viewpoints = [ann['viewpoint'] for ann in annotations]
            breakdown_data.append({
                'Individual ID': individual_id,
                'Annotation Count': len(annotations),
                'Viewpoints': ', '.join(viewpoints)
            })
        
        breakdown_df = pd.DataFrame(breakdown_data)
        st.dataframe(breakdown_df)
    
    # Generate ID Book
    st.header("3. Generate ID Book")
    
    if st.button("Generate ID Book", type="primary"):
        with st.spinner("Generating ID book..."):
            pages = []
            progress_bar = st.progress(0)
            
            # Create summary page
            summary_page = create_summary_page(grouped_annotations, location_id)
            pages.append(summary_page)
            
            # Create individual pages
            total_individuals = len(grouped_annotations)
            for i, (individual_id, annotations) in enumerate(grouped_annotations.items()):
                progress_bar.progress((i + 1) / total_individuals)
                
                st.write(f"Processing individual: {individual_id}")
                page = create_id_book_page(individual_id, annotations)
                if page:
                    pages.append(page)
            
            if pages:
                # Convert all pages to PDF
                pdf_buffer = io.BytesIO()
                
                # Convert first page to RGB if needed and save as PDF
                first_page = pages[0]
                if first_page.mode != 'RGB':
                    first_page = first_page.convert('RGB')
                
                # Convert remaining pages to RGB if needed
                remaining_pages = []
                for page in pages[1:]:
                    if page.mode != 'RGB':
                        page = page.convert('RGB')
                    remaining_pages.append(page)
                
                # Save as PDF with higher quality settings
                first_page.save(
                    pdf_buffer, 
                    format='PDF', 
                    save_all=True, 
                    append_images=remaining_pages,
                    optimize=False,  # Disable optimization to maintain quality
                    resolution=300.0  # High DPI for better quality
                )
                pdf_buffer.seek(0)
                
                st.success(f"ID book generated successfully! Created {len(pages)} pages in PDF format.")
                
                # Download button for PDF
                # Create filename in format: IDbook_YYYYMM_locationID
                current_date = datetime.now()
                year_month = current_date.strftime('%Y%m')
                # Clean location_id for filename (remove special characters)
                clean_location_id = "".join(c for c in location_id if c.isalnum() or c in (' ', '-', '_')).rstrip()
                clean_location_id = clean_location_id.replace(' ', '_')
                filename = f"IDbook_{year_month}_{clean_location_id}.pdf"
                
                st.download_button(
                    label="📥 Download ID Book (PDF)",
                    data=pdf_buffer.getvalue(),
                    file_name=filename,
                    mime="application/pdf"
                )
                
                # Show preview of first few pages
                st.subheader("Preview")
                for i, page in enumerate(pages[:3]):  # Show first 3 pages
                    st.write(f"**Page {i+1}**")
                    st.image(page, width=800)  # Larger preview to show higher quality
                    if i < 2:  # Don't show separator after last preview
                        st.divider()
            else:
                st.error("No pages were generated. Please check the debug output above.")

else:
    st.info("Please upload a Wildbook annotation export file to get started.")
