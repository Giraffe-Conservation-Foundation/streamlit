# GCF Data Management Tools

This repository contains Streamlit applications for wildlife conservation data management and analysis.

## Applications

### 🦒 Wildbook ID Book Generator
**Location:** `wildbook_id_generator/`
- Generates professional photo identification books from Wildbook annotation exports
- High-quality PDF output with side-by-side giraffe photos
- Custom GCF branding with background images

### 📊 Source Dashboard  
**Location:** `source_dashboard/`
- Real-time tracking device monitoring and analysis
- Multi-source data visualization with manufacturer filtering
- Interactive maps and device status monitoring

## Deployment

Each application can be deployed separately on Streamlit Cloud:

1. **Wildbook ID Generator**: Point to `wildbook_id_generator/app.py`
2. **Source Dashboard**: Point to `source_dashboard/app.py`

## Development

### Structure
```
├── source_dashboard/         # Source tracking dashboard
├── wildbook_id_generator/    # Wildbook ID book generator  
├── shared/                   # Shared utilities and configs
└── README.md                # This file
```

### Adding New Apps
1. Create a new folder: `new_app_name/`
2. Add your main file as `app.py`
3. Include `requirements.txt` with dependencies
4. Add `README.md` with app documentation

## Contact

Giraffe Conservation Foundation
Data Management Team
