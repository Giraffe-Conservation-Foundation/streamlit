# Giraffe Conservation Image Management System

A Streamlit web application for managing giraffe conservation images with Google Cloud Storage integration.

## Features

1. **Google Cloud Authentication**: Secure login to Google Cloud Storage
2. **Site Selection**: Choose from predefined sites or add custom locations
3. **Image Renaming**: Automatically rename images with standardized convention
4. **Cloud Upload**: Upload processed images to Google Cloud Storage buckets

## Setup Instructions

### Prerequisites

1. **Python 3.8+** installed on your system
2. **Google Cloud Project** with Storage API enabled
3. **Service Account** with Storage permissions (or gcloud CLI configured)

### Installation

1. **Clone or download this repository**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Google Cloud Setup**:
   
   **Option A: Service Account Key (Recommended)**
   - Go to Google Cloud Console > IAM & Admin > Service Accounts
   - Create a new service account or use existing one
   - Grant "Storage Admin" or "Storage Object Admin" permissions
   - Download the JSON key file
   - Keep this file secure and ready to upload in the app

   **Option B: Application Default Credentials**
   - Install Google Cloud CLI
   - Run: `gcloud auth application-default login`
   - Follow the authentication prompts

4. **Configure the application**:
   - Edit `config.py` to set your bucket name and project ID
   - Modify site options if needed

### Running the Application

1. **Start the Streamlit app**:
   ```bash
   streamlit run app.py
   ```

2. **Open your browser** to the displayed URL (usually http://localhost:8501)

## Usage Guide

### Step 1: Authentication
- Choose your authentication method
- Upload service account JSON file OR use default credentials
- Verify successful connection

### Step 2: Site Selection
- Select the site from the dropdown menu
- Add custom site if needed
- Fill in metadata (survey date, photographer, etc.)

### Step 3: Image Processing
- Upload multiple images (JPG, PNG, TIFF supported)
- Review the automatically generated filenames
- Preview uploaded images

### Step 4: Cloud Upload
- Specify the Google Cloud Storage bucket
- Set the folder structure (optional)
- Upload images with metadata

## File Naming Convention

Images are renamed using this pattern:
```
{SITE_NAME}_{YYYYMMDD}_{INDEX}.{extension}
```

Examples:
- `MASAI_MARA_20240131_0001.jpg`
- `SAMBURU_NATIONAL_RESERVE_20240131_0002.png`

## Folder Structure in GCS

Default folder structure in Google Cloud Storage:
```
giraffe_images/
  ├── {site_name}/
  │   ├── {year}/
  │   │   ├── {month}/
  │   │   │   ├── image_files...
```

## Configuration

### Bucket Configuration
Edit the `BUCKET_NAME` variable in `app.py` or `config.py`:
```python
BUCKET_NAME = "your-gcs-bucket-name"
```

### Site Options
Modify the `SITE_OPTIONS` list in `app.py` to add/remove sites:
```python
SITE_OPTIONS = [
    "Your Site 1",
    "Your Site 2",
    # ... add more sites
]
```

## Security Notes

- **Never commit service account keys to version control**
- Store credentials securely
- Use least-privilege access (Storage Object Admin instead of Owner)
- Consider using Workload Identity for production deployments

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Verify service account has correct permissions
   - Check if Storage API is enabled in your project
   - Ensure JSON key file is valid

2. **Upload Failures**:
   - Verify bucket name is correct
   - Check bucket permissions
   - Ensure bucket exists in the specified project

3. **Image Processing Issues**:
   - Supported formats: JPG, JPEG, PNG, TIFF, TIF
   - Check file size limits
   - Verify image files are not corrupted

### Getting Help

- Check Google Cloud Storage documentation
- Verify IAM permissions in Google Cloud Console
- Review application logs in the Streamlit interface

## Requirements

See `requirements.txt` for complete list of dependencies:
- streamlit>=1.28.0
- google-cloud-storage>=2.10.0
- google-auth>=2.23.0
- pandas>=2.0.0
- Pillow>=10.0.0

## License

This project is for conservation research purposes. Please ensure compliance with your organization's data handling policies.
