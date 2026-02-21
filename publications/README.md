# Publications Dashboard

This dashboard displays GCF (Giraffe Conservation Foundation) publications from the Zotero library.

## Features

- **Password Protection**: Secure access to the publications dashboard
- **Zotero Integration**: Automatically fetches publications tagged with "GCF" from the GCF Reports External Zotero library
- **Publications by Year**: Visual summary showing the distribution of publications over time
- **Filtering**: Filter publications by year and type
- **Export**: Download all publications data as CSV

## Data Source

The dashboard connects to a GCF Zotero group library (ID: 5147968, Collection: 55G83VRS) and displays all items tagged with "GCF".

## Publication Information Displayed

For each publication, the dashboard shows:
- Title
- Authors
- Year
- Publication type
- Journal/publication title (if available)
- URL link (if available)
- DOI (if available)

## Password

A password is required to access this dashboard. 

### Setup

1. Create a `.streamlit` folder in the root directory if it doesn't exist
2. Create a `secrets.toml` file inside the `.streamlit` folder
3. Add the following content (see `secrets_template.toml` for reference):

```toml
[passwords]
publications_password = "your-password-here"
```

For local development without secrets.toml, the default password is "admin".

## Usage

The dashboard is automatically accessible from the main Twigatools app sidebar as "📚 Publications".

## Technical Details

- **Zotero Library ID**: 5147968
- **Collection Key**: 55G83VRS
- **Library Type**: Group
- **Tag Filter**: GCF
- **Update Frequency**: Real-time (fetches latest data on each load)
