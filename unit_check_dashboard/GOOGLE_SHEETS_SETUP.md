# Google Sheets Setup for GPS Unit Stock Planning

This guide will help you set up Google Sheets integration for the deployment planning feature.

## Step 1: Create a Google Cloud Project (5 minutes)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Name it something like "Twiga Tools"

## Step 2: Enable Google Sheets API

1. In your project, go to **APIs & Services** > **Enable APIs and Services**
2. Search for "Google Sheets API"
3. Click **Enable**

## Step 3: Create Service Account

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **Service Account**
3. Name it: `twiga-tools-sheets`
4. Click **Create and Continue**
5. Skip the optional steps (click **Continue** and **Done**)

## Step 4: Create Service Account Key

1. Click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key** > **Create new key**
4. Choose **JSON** format
5. Click **Create** - this downloads a JSON file
6. **Keep this file safe!** It contains your credentials

## Step 5: Add Credentials to Streamlit Secrets

### For Local Development:

1. In your streamlit folder, create `.streamlit/secrets.toml` if it doesn't exist:
   ```
   G:\My Drive\Data management\streamlit\.streamlit\secrets.toml
   ```

2. Open the downloaded JSON file and copy its contents

3. Add to `secrets.toml` in this format:
   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "your-private-key-id"
   private_key = "-----BEGIN PRIVATE KEY-----\nYour-Private-Key-Here\n-----END PRIVATE KEY-----\n"
   client_email = "your-service-account@your-project.iam.gserviceaccount.com"
   client_id = "your-client-id"
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "your-cert-url"
   ```

### For Streamlit Cloud Deployment:

1. Go to your app settings on Streamlit Cloud
2. Go to **Secrets** section
3. Paste the same content as above
4. Save

## Step 6: Share the Google Sheet (Optional)

After the first run, the app will create a Google Sheet called `GPS_Unit_Stock_Planning`.

To view/edit it directly:
1. Find the sheet in your Google Drive (search for "GPS_Unit_Stock_Planning")
2. Right-click > Share
3. Add your email with Editor access

Or use the service account email from the JSON file to share it programmatically.

## Step 7: Test It!

1. Restart your Streamlit app
2. Go to GPS Unit Check > Deployment Planning tab
3. Try adding a deployment plan or updating stock
4. Check your Google Drive - you should see the sheet created!

## Troubleshooting

### "Google Sheets credentials not found"
- Check that `.streamlit/secrets.toml` exists and has the `[gcp_service_account]` section
- Make sure the private_key includes the newline characters (`\n`)

### "Insufficient Permission"
- Make sure Google Sheets API is enabled in your Google Cloud project
- Check that you copied all fields from the JSON file

### Can't find the spreadsheet
- The app creates it automatically on first save
- Search "GPS_Unit_Stock_Planning" in your Google Drive
- It's created under the service account's drive initially

## Security Notes

⚠️ **Important:**
- Never commit the JSON key file to git
- Never share your `secrets.toml` file
- The `.gitignore` should already exclude `.streamlit/secrets.toml`
- For Streamlit Cloud, secrets are encrypted and stored securely

## Data Structure

The Google Sheet will have 4 worksheets:
1. **deployment_plan** - Your planned deployments
2. **in_hand** - Current stock details
3. **in_mail** - Orders in transit
4. **stock_summary** - Quick counts by type

All data syncs automatically when you update through the app!
