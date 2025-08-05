# 🚀 Twiga Tools Deployment Guide

This guide explains how to deploy the **Twiga Tools** unified conservation platform.

## 🌟 Recommended Deployment: Unified Platform

Deploy **Twiga Tools** as a single application that provides access to all conservation tools:

### Streamlit Cloud Configuration
- **Repository:** `https://github.com/Giraffe-Conservation-Foundation/streamlit`
- **Branch:** `main` 
- **Main file path:** `twiga_tools.py`
- **App URL:** `https://twiga-tools-gcf.streamlit.app`

### Local Development
```bash
git clone https://github.com/Giraffe-Conservation-Foundation/streamlit.git
cd streamlit
pip install -r requirements.txt
streamlit run twiga_tools.py
```

## 🔧 Setup Instructions

### Step 1: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub account
3. Select repository: `Giraffe-Conservation-Foundation/streamlit`
4. Set main file: `twiga_tools.py`
5. Choose a memorable app name: `twiga-tools-gcf`

### Step 2: Configure Environment Variables

Add these environment variables in Streamlit Cloud settings:

#### For Image Management System
```
GCP_PROJECT_ID=your-project-id
GCS_BUCKET_NAME=your-bucket-name
```

#### For NANW Dashboard
```
EARTHRANGER_SERVER=https://your-server.pamdas.org
EARTHRANGER_USERNAME=your-username  
EARTHRANGER_PASSWORD=your-password
```

#### For Wildbook ID Generator
```
WILDBOOK_API_URL=https://your-wildbook.org
WILDBOOK_API_KEY=your-api-key
```

### Step 4: Test Deployment

1. Wait for deployment to complete
2. Test each application functionality
3. Verify environment variables are working
4. Check that all dependencies are installed

## 🔒 Security Notes

- ✅ Never put credentials directly in the code
- ✅ Use Streamlit Cloud's environment variable system
- ✅ Keep the `.env.template` file for local development reference
- ✅ Regularly rotate API keys and passwords

## 🐛 Troubleshooting

### Common Issues

1. **Import Error**: Make sure `requirements.txt` includes all dependencies
2. **File Not Found**: Check that file paths are correct in entry point files
3. **Authentication Failed**: Verify environment variables are set correctly
4. **Module Not Found**: Ensure Python path modifications are working

### Debug Steps

1. Check Streamlit Cloud logs for specific error messages
2. Test locally first using the same file structure
3. Verify all required files exist in the repository
4. Check that dependencies match between local and cloud environments

## 📈 Recommended Approach

For your use case, I recommend **Option 1 (Multi-Page Dashboard)** because:

- ✅ Single deployment to manage
- ✅ Unified user experience
- ✅ Easier to maintain
- ✅ Professional appearance
- ✅ Shared authentication and configuration

Users can access all applications from one URL, and you only need to manage one deployment.
