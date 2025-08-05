# Giraffe Conservation Image Management System Configuration

# Google Cloud Storage Configuration
BUCKET_NAME = "your-gcs-bucket-name"  # Replace with your actual bucket name
PROJECT_ID = "your-gcp-project-id"    # Replace with your GCP project ID

# Image Processing Settings
MAX_FILE_SIZE_MB = 50  # Maximum file size in MB
SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.tiff', '.tif']

# Naming Convention
# Generated filenames will follow this pattern:
# {SITE_NAME}_{YYYYMMDD}_{INDEX}.{extension}
# Example: MASAI_MARA_20240131_0001.jpg

# Site Options (you can modify these)
SITES = [
    "Masai Mara National Reserve",
    "Samburu National Reserve", 
    "Tsavo East National Park",
    "Amboseli National Park",
    "Lake Nakuru National Park",
    "Meru National Park",
    "Laikipia Plateau",
    "Northern Kenya",
    "Southern Kenya"
]
