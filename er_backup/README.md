# ER Backup Tool

## High Performance Incremental Backup for EarthRanger

This module provides a high-performance backup solution for EarthRanger data, specifically designed to handle large date ranges (2016-present) efficiently.

### Key Features

- **Month-by-month processing**: Handles years of data efficiently without memory issues
- **Resume capability**: Continue interrupted backups from where they left off
- **Bulk downloads**: Downloads all observations at once instead of per-animal requests
- **Progress persistence**: Saves backup state between sessions
- **Incremental processing**: Processes one month at a time with progress tracking

### Architecture

This follows the standard Streamlit multipage project structure:
- `pages/10_ER_Backup.py` - Simple launcher that imports and runs this module
- `er_backup/app.py` - Main application logic and user interface
- `backup_progress/` - Directory for storing backup progress files (created at runtime)

### Dependencies

- `streamlit` - Web application framework
- `pandas` - Data manipulation and analysis
- `ecoscope` - EarthRanger API integration library
- `pathlib` - Path handling utilities

### Usage

The tool is accessed through the Streamlit multipage interface. Users can:
1. Authenticate with EarthRanger credentials
2. Select data types to backup (observations, events)
3. Choose date ranges with quick presets
4. Monitor progress with real-time metrics
5. Download complete backup as ZIP file with monthly organization

### Performance Optimizations

- **Bulk API calls**: Single request per month instead of per-animal
- **Session caching**: Reuse subject and group data across months
- **Memory efficient**: Process and save data incrementally
- **API rate limiting**: Built-in delays to prevent server overload

### Output Format

Backups are saved as ZIP files containing:
- Monthly CSV files organized by date
- Metadata file with backup information
- Progress tracking for resume capability

Each CSV includes comprehensive data with left-joined animal and group details for easy analysis.
