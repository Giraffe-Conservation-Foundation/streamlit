"""
Example of how to integrate your logo - Quick Setup Guide
========================================================

Step 1: Save your logo as 'logo.png' in the same folder as app.py

Step 2: Find this section in the main() function of app.py:
```
<!-- Option 1: Uncomment to add a logo image from file -->
<!-- <img src="data:image/png;base64,{base64_logo}" width="80"> -->
```

Step 3: Replace it with:
```python
# Load and display logo
logo_base64 = load_logo_base64("logo.png")
if logo_base64:
    st.markdown(f'''
    <div class="main-header">
        <div class="logo-container">
            <img src="data:image/png;base64,{logo_base64}" width="80" style="margin-right: 1rem;">
            <div>
                <div class="logo-title">Giraffe Conservation Foundation</div>
                <div class="logo-subtitle">Image Management System</div>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
else:
    # Fallback to text-only header
    st.markdown('''
    <div class="main-header">
        <div class="logo-container">
            <div>
                <div class="logo-title">🦒 Giraffe Conservation Foundation</div>
                <div class="logo-subtitle">Image Management System</div>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
```

That's it! Your logo will appear next to the title.
"""
