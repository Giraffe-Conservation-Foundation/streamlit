# 🚀 Deployment Guide

This guide explains how to deploy your GCF Streamlit applications with the organized repository structure.

## 📋 Deployment Options

### Option 1: Multi-Page Dashboard (Recommended)
Deploy a single app that combines all your projects:

**Streamlit Cloud Configuration:**
- Repository: `https://github.com/Giraffe-Conservation-Foundation/streamlit`
- Branch: `main` 
- Main file path: `main_app.py`
- App URL: `https://gcf-streamlit-apps.streamlit.app`

### Option 2: Individual App Deployments
Deploy each application separately:

#### Wildbook ID Generator
- Repository: `https://github.com/Giraffe-Conservation-Foundation/streamlit`
- Branch: `main`
- Main file path: `wildbook_app.py`
- App URL: `https://wildbook-gcf.streamlit.app`

#### NANW Dashboard  
- Repository: `https://github.com/Giraffe-Conservation-Foundation/streamlit`
- Branch: `main`
- Main file path: `nanw_app.py`
- App URL: `https://nanw-gcf.streamlit.app`

#### Image Management System
- Repository: `https://github.com/Giraffe-Conservation-Foundation/streamlit`
- Branch: `main`
- Main file path: `image_app.py`
- App URL: `https://image-management-gcf.streamlit.app`

## 🔧 Setup Instructions

### Step 1: Choose Your Deployment Method
1. **Multi-Page App**: Single deployment, users choose app from sidebar
2. **Individual Apps**: Multiple deployments, one per application

### Step 2: Configure Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub account
3. Select repository: `Giraffe-Conservation-Foundation/streamlit`
4. Choose the appropriate main file:
   - Multi-page: `main_app.py`
   - Individual: `wildbook_app.py`, `nanw_app.py`, or `image_app.py`

### Step 3: Environment Variables

For apps requiring credentials, add these in Streamlit Cloud:

#### Image Management System
```
GCP_PROJECT_ID=your-project-id
GCS_BUCKET_NAME=your-bucket-name
```

#### NANW Dashboard
```
EARTHRANGER_SERVER=https://your-server.pamdas.org
EARTHRANGER_USERNAME=your-username  
EARTHRANGER_PASSWORD=your-password
```

#### Wildbook ID Generator
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
