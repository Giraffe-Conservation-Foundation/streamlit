# Adding Your Company Logo to the Giraffe Image Management System

## Option 1: Using a Local Logo File (Recommended)

1. **Save your logo file** in the same folder as `app.py`
   - Supported formats: PNG, JPG, JPEG, SVG
   - Recommended: PNG with transparent background
   - Suggested size: 200x80 pixels or similar aspect ratio

2. **Update the code** in `app.py` in the main() function:

Replace this line:
```html
<!-- Option 1: Uncomment to add a logo image from file -->
<!-- <img src="data:image/png;base64,{base64_logo}" width="80"> -->
```

With this (assuming your logo is named `logo.png`):
```python
# Load the logo
logo_base64 = load_logo_base64("logo.png")
if logo_base64:
    st.markdown(f"""
    <div class="main-header">
        <div class="logo-container">
            <img src="data:image/png;base64,{logo_base64}" width="80" style="margin-right: 1rem;">
            <div>
                <div class="logo-title">Giraffe Conservation Foundation</div>
                <div class="logo-subtitle">Image Management System</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
```

## Option 2: Using a Logo URL

If your logo is hosted online, replace this line:
```html
<!-- Option 2: Uncomment to add a logo image from URL -->
<!-- <img src="https://your-logo-url.com/logo.png" width="80" style="margin-right: 1rem;"> -->
```

With:
```html
<img src="https://your-actual-logo-url.com/logo.png" width="80" style="margin-right: 1rem;">
```

## Option 3: Using Streamlit's st.image() (Alternative)

You can also use Streamlit's built-in image function by replacing the header section with:

```python
# Header with logo
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    subcol1, subcol2 = st.columns([1, 4])
    with subcol1:
        st.image("logo.png", width=100)  # Adjust width as needed
    with subcol2:
        st.markdown("""
        <div style="padding-top: 1rem;">
            <h1 style="color: #2E8B57; margin-bottom: 0;">Giraffe Conservation Foundation</h1>
            <h3 style="color: #4F4F4F; margin-top: 0;">Image Management System</h3>
        </div>
        """, unsafe_allow_html=True)
```

## Logo File Requirements

- **Format**: PNG (preferred), JPG, or SVG
- **Size**: Recommended 200-400px width
- **Background**: Transparent (for PNG)
- **Location**: Same folder as app.py

## File Structure
```
autoManagement/
├── app.py
├── utils.py
├── logo.png          ← Your logo file here
├── requirements.txt
└── other files...
```

## Example Logo Names
- `logo.png`
- `gcf_logo.png`
- `company_logo.jpg`
- `giraffe_foundation_logo.png`

Choose the option that works best for your setup!
