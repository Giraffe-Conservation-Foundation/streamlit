# Wildbook ID Book Generator

Generate professional photo identification books from Wildbook annotation exports.

## Features

- **Side-by-side photo layout**: Left and right side photos on each page
- **Individual information**: Shows ID, sex, and nickname for each animal
- **High-quality images**: 800x800px downloads with 300 DPI PDF output
- **Custom title page**: Background image support with location information
- **Smart filename**: Downloads as "IDbook_YYYYMM_LocationID.pdf"

## How to Use

1. **Export from Wildbook**: 
   - Go to Wildbook → Search → Encounter Search
   - Set your filters and search
   - Go to Export tab → Click "Encounter Annotation Export"

2. **Upload the file**: Use the file uploader in the app

3. **Generate**: Click "Generate ID Book" to create your photo identification book

## Deployment

This app is deployed on Streamlit Cloud. The main file is `app.py` and dependencies are listed in `requirements.txt`.

## Background Image

Place your background image as `GCF_background_logo.png` in this directory for automatic detection.
