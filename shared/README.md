# Shared Resources

This directory contains shared resources used across multiple GCF Streamlit applications.

## 📁 Contents

### 🖼️ Assets
- `logo.png` - GCF logo for use in applications
- Other shared images and assets

### ⚙️ Configuration
- `config.py` - Common configuration settings
- Shared constants and settings

### 🛠️ Utilities
- `utils.py` - Common utility functions
- Image processing helpers
- Data manipulation functions

## 🔧 Usage

To use shared resources in your project:

```python
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from config import BUCKET_NAME, SITE_OPTIONS
from utils import process_image, validate_file
```

## 📝 Adding New Shared Resources

When adding new shared resources:

1. **Assets**: Place images, icons, and other media files in this directory
2. **Code**: Add reusable functions to `utils.py`
3. **Configuration**: Add shared settings to `config.py`
4. **Documentation**: Update this README with new additions

## 🔒 Security Note

Do not place sensitive information (API keys, credentials, etc.) in shared files. Use environment variables or project-specific configuration files instead.
