# 🦒 Twiga Tools - GCF Conservation Platform

**Twiga Tools** is an integrated Streamlit platform developed by the Giraffe Conservation Foundation for conservation research, data management, and wildlife monitoring.

## 🌟 About Twiga Tools

"Twiga" means "giraffe" in Swahili, and this platform brings together essential conservation tools in one unified interface. Select from multiple specialized applications designed to support giraffe conservation efforts across Africa.

## 🛠️ Integrated Tools

### 🆔 Wildbook ID Generator
**Status: ✅ Production Ready**
- Generate unique IDs for giraffe individuals in Wildbook database
- Features: ID validation, batch generation, export functionality
- Perfect for research teams managing individual animal records

### 📊 NANW Event Dashboard  
**Status: ✅ Production Ready**
- Event tracking and subject history visualization
- Northern Africa/Namibia West conservation monitoring
- Features: Real-time tracking, data export, interactive visualizations

### 📸 Image Management System
**Status: ✅ Production Ready**
- Complete workflow for managing giraffe conservation images
Features: Google Cloud Storage integration, automated processing, standardized naming
- Handles bulk image uploads with metadata management

### 🌍 EarthRanger Integration
**Status: 🚧 In Development**
- Integration with EarthRanger conservation platform
- Features: Wildlife tracking, conservation area monitoring, alert management
- Expected release: Q4 2025

## 🚀 Quick Start

### 🌐 Using Twiga Tools (Recommended)

**Deploy the unified platform:**

1. **Streamlit Cloud Setup:**
   - Repository: `https://github.com/Giraffe-Conservation-Foundation/streamlit`
   - Main file: `twiga_tools.py`
   - Single URL provides access to all conservation tools

2. **Local Development:**
   ```bash
   git clone https://github.com/Giraffe-Conservation-Foundation/streamlit.git
   cd streamlit
   pip install -r requirements.txt
   streamlit run twiga_tools.py
   ```

### 🔧 Individual Tool Development

Each tool is self-contained in its directory:

```bash
# Work on a specific tool
cd wildbook_id_generator
pip install -r requirements.txt  
streamlit run app.py
```

📖 **See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions**

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

## 📋 Platform Status

| Tool | Status | Last Updated | Purpose |
|------|--------|--------------|---------|
| Wildbook ID Generator | ✅ Production | Aug 2025 | Individual animal identification |
| NANW Event Dashboard | ✅ Production | Aug 2025 | Conservation monitoring |
| Image Management System | ✅ Production | Aug 2025 | Photo processing & storage |
| EarthRanger Integration | 🚧 Development | Aug 2025 | Wildlife tracking platform |

## 🏗️ Repository Structure

```
streamlit/
├── 🎯 twiga_tools.py             # Main unified application
├── 🆔 wildbook_id_generator/     # Wildbook ID generator tool
├── 📊 nanw_dashboard/            # NANW event dashboard  
├── 🌍 source_dashboard/         # Source tracking dashboard
├── 📸 image_management/          # Image processing system
├── 📂 shared/                    # Common utilities & assets
├── 📚 docs/                      # Documentation & guides
├── 📋 requirements.txt           # All dependencies
└── 🚀 DEPLOYMENT.md              # Deployment instructions
```

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes in the appropriate project directory
3. Test your changes locally
4. Commit your changes: `git commit -m "Description of changes"`
5. Push to the branch: `git push origin feature/your-feature-name`
6. Create a Pull Request

## 🔒 Security & Configuration

### 🛡️ Security Best Practices

**This is a PUBLIC repository** - please follow these security guidelines:

- ✅ **Never commit credentials**: Service account keys, passwords, API tokens
- ✅ **Use environment variables**: Store sensitive data in `.env` files (excluded by `.gitignore`)
- ✅ **Template configuration**: Use placeholder values in config files
- ✅ **Local secrets only**: Keep actual credentials on your local machine only

### 🔧 Configuration Management

- Each project may require different environment variables
- Use `.env` files for local development (already in `.gitignore`)
- Replace placeholder values in `shared/config.py` with your actual settings locally
- See individual project READMEs for specific security requirements

### 📋 Before Going Live Checklist

- [ ] All placeholder values replaced with environment variables
- [ ] No hardcoded credentials in source code
- [ ] Service account JSON files stored locally only
- [ ] Production credentials stored in secure deployment environment

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
