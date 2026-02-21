# Publications Dashboard - Streamlit Cloud Setup Instructions

## Required Secrets Configuration

To deploy the Publications dashboard on Streamlit Cloud, you need to add the following secrets:

### 1. Navigate to Streamlit Cloud
- Go to your app settings on Streamlit Cloud
- Click on "Secrets" in the left sidebar

### 2. Add Password Secret

Add the following to your secrets configuration:

```toml
[passwords]
publications_password = "0814893127"
```

### 3. Save and Redeploy

After saving the secrets, the app will automatically redeploy with the password protection enabled.

## Local Development

For local development:
1. Create a `.streamlit` folder in the project root (if it doesn't exist)
2. Create a `secrets.toml` file inside `.streamlit/`
3. Add the same secret configuration as above

Note: The `.streamlit/` folder is already in `.gitignore` to prevent secrets from being committed to the repository.

If no secrets file exists locally, the app will use "admin" as the default password for testing.
