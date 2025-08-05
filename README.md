# Giraffe Conservation Foundation - Streamlit Applications

This repository contains multiple Streamlit applications developed for the Giraffe Conservation Foundation's data management and visualization needs.

## 📁 Project Structure

### 🆔 [wildbook_id_generator/](./wildbook_id_generator/)
**Wildbook ID Generator**
- Generates unique IDs for giraffe individuals in Wildbook database
- Features: ID validation, batch generation, export functionality
- Status: ✅ Active

### 📊 [nanw_dashboard/](./nanw_dashboard/)
**NANW (Northern Africa/Namibia West) Dashboard**
- Event tracking and subject history visualization
- Features: Event analysis, subject monitoring, data export
- Status: ✅ Active

### 🌍 [earthranger_dashboard/](./earthranger_dashboard/)
**EarthRanger Integration Dashboard**
- Integration with EarthRanger conservation platform
- Features: Wildlife tracking, conservation area monitoring
- Status: 🚧 In Development

### 📸 [image_management/](./image_management/)
**Giraffe Conservation Image Management System**
- Complete workflow for managing giraffe conservation images
- Features: Google Cloud Storage integration, image processing, standardized renaming
- Status: ✅ Active

### 📂 [shared/](./shared/)
**Shared Resources**
- Common utilities, configurations, and assets used across projects
- Logos, common functions, shared constants

### 📚 [docs/](./docs/)
**Documentation & Setup Guides**
- Logo setup instructions and troubleshooting
- Development documentation and guides

## 🚀 Quick Start

Each project is self-contained with its own:
- `README.md` - Project-specific documentation
- `requirements.txt` - Python dependencies
- `app.py` - Main Streamlit application

### Running a Project

1. Navigate to the project directory:
   ```bash
   cd wildbook_id_generator
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

## 🛠️ Development Setup

### Prerequisites
- Python 3.8+
- Git
- Streamlit

### Environment Setup
```bash
# Clone the repository
git clone https://github.com/Giraffe-Conservation-Foundation/streamlit.git
cd streamlit

# Create virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install project dependencies (choose the project you want to work on)
cd wildbook_id_generator
pip install -r requirements.txt
```

## 📋 Project Status

| Project | Status | Last Updated | Maintainer |
|---------|--------|--------------|------------|
| wildbook_id_generator | ✅ Production | 2024-01 | GCF Team |
| nanw_dashboard | ✅ Production | 2024-01 | GCF Team |
| earthranger_dashboard | 🚧 Development | 2024-01 | GCF Team |
| image_management | ✅ Production | 2024-01 | GCF Team |

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes in the appropriate project directory
3. Test your changes locally
4. Commit your changes: `git commit -m "Description of changes"`
5. Push to the branch: `git push origin feature/your-feature-name`
6. Create a Pull Request

## 🔒 Security & Configuration

- Each project may require different environment variables
- Service account keys and sensitive data should never be committed
- Use `.env` files for local development (already in `.gitignore`)
- See individual project READMEs for specific security requirements

## 📞 Support

For questions or issues:
- Check the individual project README files
- Create an issue in this repository
- Contact the GCF development team

## 📄 License

This project is developed for conservation research purposes. Please ensure compliance with your organization's data handling policies and local regulations regarding wildlife research data.

---

**🦒 Giraffe Conservation Foundation**  
*Supporting conservation through technology and data management*
