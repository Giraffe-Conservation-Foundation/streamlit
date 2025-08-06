# Giraffe Conservation Image Management System

## 🎯 Project Overview

This Streamlit application provides a complete workflow for managing giraffe conservation images with Google Cloud Storage integration. The system handles authentication, site selection, image processing, standardized renaming, and cloud upload.

## ✨ Features

### 1. 🔐 Google Cloud Authentication
- **Service Account Key Upload**: Secure authentication using JSON key files
- **Application Default Credentials**: Integration with gcloud CLI
- **Bucket Access Verification**: Automatic testing of storage permissions

### 2. 📍 Site Selection Interface  
- **Predefined Sites**: Conservation areas across Kenya
- **Custom Site Entry**: Flexibility for new locations
- **Metadata Collection**: Survey date, photographer, camera details
- **Data Validation**: Ensures complete information capture

### 3. 📸 Advanced Image Processing
- **Multi-format Support**: JPG, JPEG, PNG, TIFF, TIF files
- **Batch Upload**: Process multiple images simultaneously  
- **Image Validation**: Automatic format and integrity checking
- **Smart Compression**: Reduces file sizes while maintaining quality
- **Metadata Extraction**: Captures image dimensions, format, EXIF data

### 4. 🏷️ Standardized Naming Convention
- **Consistent Format**: `{SITE}_{YYYYMMDD}_{INDEX}_{PHOTOGRAPHER}.ext`
- **Clean Site Names**: Removes special characters, standardizes format
- **Sequential Numbering**: Automatic indexing for batch operations
- **Preview System**: Review all changes before processing

### 5. ☁️ Cloud Storage Integration
- **Google Cloud Storage**: Direct upload to GCS buckets
- **Organized Structure**: Automatic folder organization by site/date
- **Rich Metadata**: Comprehensive tagging for searchability
- **Progress Tracking**: Real-time upload status and completion reports
- **Error Handling**: Robust failure detection and reporting
- **Backup Creation**: Optional metadata backup files

### 6. 📊 Comprehensive Reporting
- **Upload Statistics**: Success rates, file sizes, timing
- **Compression Reports**: Space savings through optimization
- **Error Logs**: Detailed failure analysis
- **Metadata Backup**: JSON files for audit trails

## 🚀 Quick Start Guide

### Prerequisites
1. **Python 3.8+** installed
2. **Google Cloud Project** with Storage API enabled  
3. **Service Account** with Storage permissions OR gcloud CLI configured

### Installation

1. **Navigate to the project directory**:
   ```bash
   cd "G:\My Drive\Data management\IMAG_dataManagement\autoManagement"
   ```

2. **Install dependencies** (already done in this setup):
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   streamlit run app.py
   ```
   
   Or use the launcher:
   ```bash
   python launcher.py
   ```
   
   Or double-click: `run_app.bat`

### Google Cloud Setup

#### Option A: Service Account (Recommended)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to IAM & Admin > Service Accounts
3. Create new service account or select existing one
4. Add role: "Storage Admin" or "Storage Object Admin"
5. Generate and download JSON key file
6. Upload the key file in the app's authentication step

#### Option B: Application Default Credentials
1. Install [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
2. Run: `gcloud auth application-default login`
3. Follow browser authentication prompts
4. Select "Application Default Credentials" in the app

## 📱 Using the Application

### Step 1: Authentication
- Choose authentication method (Service Account Key or Default Credentials)
- Upload JSON key file or use gcloud credentials
- Verify successful connection to Google Cloud

### Step 2: Site Selection
- Select conservation site from dropdown menu
- Enter custom site if not listed
- Fill in survey metadata:
  - Survey date
  - Photographer name
  - Camera model (optional)
  - Additional notes (optional)

### Step 3: Image Processing
- Upload multiple images using the file uploader
- Review automatic filename generation
- Check compression and optimization results
- Preview uploaded images and metadata

### Step 4: Cloud Upload
- Specify Google Cloud Storage bucket name
- Review/modify folder structure
- Configure upload options:
  - Overwrite existing files
  - Add timestamp to folders
  - Create metadata backup
  - Enable detailed reporting
- Execute upload and monitor progress

## 🗂️ File Organization

### Local Structure
```
autoManagement/
├── app.py              # Main Streamlit application
├── utils.py            # Utility functions for image processing
├── config.py           # Configuration settings
├── requirements.txt    # Python dependencies
├── launcher.py         # Application launcher script
├── run_app.bat        # Windows batch file launcher
└── README.md          # This documentation
```

### Cloud Storage Structure
```
your-bucket/
├── giraffe_images/
│   ├── MASAI_MARA/
│   │   ├── 2024/
│   │   │   ├── 01/
│   │   │   │   ├── MASAI_MARA_20240131_0001.jpg
│   │   │   │   ├── MASAI_MARA_20240131_0002.jpg
│   │   │   │   └── upload_metadata_20240131_143022.json
│   │   │   └── 02/
│   │   └── 2025/
│   ├── SAMBURU_NATIONAL_RESERVE/
│   └── AMBOSELI_NATIONAL_PARK/
```

### Filename Convention
- **Format**: `{SITE}_{YYYYMMDD}_{INDEX}_{PHOTOGRAPHER}.ext`
- **Examples**: 
  - `MASAI_MARA_20240131_0001_JDOE.jpg`
  - `SAMBURU_NATIONAL_RESERVE_20240201_0023.png`

## 🔧 Configuration

### Bucket Settings
Edit `BUCKET_NAME` in `config.py` or `app.py`:
```python
BUCKET_NAME = "your-conservation-bucket"
```

### Site Options  
Modify `SITE_OPTIONS` in `app.py`:
```python
SITE_OPTIONS = [
    "Your Conservation Site 1",
    "Your Conservation Site 2",
    # Add more sites as needed
]
```

### Upload Settings
Adjust compression and size limits in `utils.py`:
```python
MAX_FILE_SIZE_MB = 50
COMPRESSION_QUALITY = 85
```

## 🛡️ Security & Best Practices

### Credential Management
- ✅ **DO**: Store service account keys securely
- ✅ **DO**: Use least-privilege IAM roles (Storage Object Admin)
- ❌ **DON'T**: Commit credentials to version control
- ❌ **DON'T**: Share service account keys

### Data Handling
- ✅ **DO**: Validate all uploaded images
- ✅ **DO**: Use compression to optimize storage
- ✅ **DO**: Create metadata backups
- ✅ **DO**: Monitor upload success rates

### Production Deployment
- Consider using Workload Identity for GKE deployments
- Implement proper error logging and monitoring
- Set up automated backup procedures
- Use Cloud IAM conditions for fine-grained access control

## 🐛 Troubleshooting

### Common Issues

#### Authentication Problems
- **Symptom**: "Authentication failed" errors
- **Solutions**: 
  - Verify service account has Storage permissions
  - Check if Storage API is enabled in your project
  - Ensure JSON key file is valid and not expired

#### Upload Failures
- **Symptom**: Images fail to upload
- **Solutions**:
  - Verify bucket name exists and is accessible
  - Check bucket permissions and IAM roles
  - Ensure sufficient storage quota
  - Verify network connectivity

#### Image Processing Issues
- **Symptom**: Images fail validation or processing
- **Solutions**:
  - Check file formats (supported: JPG, JPEG, PNG, TIFF, TIF)
  - Verify images are not corrupted
  - Check file size limits
  - Ensure sufficient disk space for processing

#### Performance Issues
- **Symptom**: Slow upload or processing
- **Solutions**:
  - Enable image compression
  - Reduce batch sizes for large files
  - Check internet connection speed
  - Monitor memory usage during processing

### Getting Help
1. Check application logs in the Streamlit interface
2. Review Google Cloud Storage documentation
3. Verify IAM permissions in Google Cloud Console
4. Test with smaller image batches first

## 📋 Dependencies

Core packages (see `requirements.txt`):
- `streamlit>=1.28.0` - Web application framework
- `google-cloud-storage>=2.10.0` - Google Cloud Storage client
- `google-auth>=2.23.0` - Google authentication
- `pandas>=2.0.0` - Data manipulation
- `Pillow>=10.0.0` - Image processing

## 🤝 Contributing

This system is designed for giraffe conservation research. When extending functionality:
1. Maintain the standardized naming convention
2. Preserve metadata throughout the pipeline
3. Ensure robust error handling
4. Follow conservation data best practices
5. Test thoroughly with various image formats

## 📄 License

This project is for conservation research purposes. Please ensure compliance with your organization's data handling policies and local regulations regarding wildlife research data.

---

**🦒 Giraffe Conservation Foundation - Data Management System**  
*Supporting conservation through organized data management*
