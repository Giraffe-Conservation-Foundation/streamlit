# GEE Service Account Setup for Deployment

## Why Service Account?

When deploying the app to Streamlit Cloud or other hosting platforms, you need **service account** credentials instead of user credentials because:
- No interactive browser authentication available
- Persistent credentials stored in secrets
- Better security for production deployments

## Setup Steps

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Note your Project ID (e.g., `my-giraffe-project-12345`)

### 2. Enable Earth Engine API

1. In Cloud Console, go to APIs & Services > Library
2. Search for "Earth Engine API"
3. Click Enable

### 3. Create Service Account

1. Go to IAM & Admin > Service Accounts
2. Click "Create Service Account"
3. Name it (e.g., `gee-streamlit-app`)
4. Grant role: `Earth Engine Resource Viewer` or `Earth Engine Resource Admin`
5. Click "Create and Continue"
6. Skip optional steps, click "Done"

### 4. Create Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose **JSON** format
5. Click "Create" - a JSON file will download

### 5. Register Service Account with Earth Engine

```bash
# Install gcloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Register the service account with Earth Engine
earthengine --service_account <SERVICE_ACCOUNT_EMAIL> --key_file <PATH_TO_JSON>
```

Replace:
- `<SERVICE_ACCOUNT_EMAIL>`: From step 3 (e.g., `gee-streamlit-app@my-project.iam.gserviceaccount.com`)
- `<PATH_TO_JSON>`: Path to the downloaded JSON key file

### 6. Add to Streamlit Secrets

In `.streamlit/secrets.toml`, add:

```toml
[gee_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "gee-streamlit-app@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-cert-url"
```

**To get these values**, open the downloaded JSON file and copy each field.

**Important**: In the `private_key` field, you need to escape the newlines:
- Replace actual newlines with `\n`
- Keep the quotes around the entire key

### 7. Deploy to Streamlit Cloud

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. In "Advanced settings" > "Secrets", paste your secrets.toml content
5. Deploy!

## Local Development (Alternative)

For local development, you can still use interactive user authentication:

```bash
earthengine authenticate
```

The code will try service account first (if secrets exist), then fall back to user credentials.

## Verify It Works

Test your service account:

```python
import ee

credentials = ee.ServiceAccountCredentials(
    email='YOUR_SERVICE_ACCOUNT_EMAIL',
    key_file='path/to/key.json'
)
ee.Initialize(credentials)

# Test
point = ee.Geometry.Point([-122.0838, 37.4220])
print("Success! Service account works.")
```

## Troubleshooting

### "Earth Engine not authenticated"
- Verify service account has Earth Engine permissions
- Check that all fields in secrets.toml are correct
- Ensure private_key has proper escaping

### "Permission denied"
- Service account needs to be registered with Earth Engine (step 5)
- May take a few minutes to propagate

### "Invalid credentials"
- Double-check all fields from JSON match secrets.toml
- Verify no extra spaces or missing characters
- Check private_key formatting (especially newlines)

## Security Notes

⚠️ **NEVER commit the JSON key file to Git**
⚠️ **NEVER share your secrets publicly**
✅ Add `*.json` and `.streamlit/secrets.toml` to `.gitignore`
✅ Use Streamlit Cloud's secrets management
✅ Rotate keys periodically

## Cost

Google Earth Engine is **free** for:
- Research
- Education  
- Non-profit conservation

Service accounts don't change this - still free! 🎉
