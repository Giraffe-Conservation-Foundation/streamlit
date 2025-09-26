"""
Redirect Page - Source Dashboard Replacement
This page redirects users to the new Unit Check dashboard
"""

import streamlit as st

st.title("🔄 Source Dashboard → Unit Check")
st.info("The Source Dashboard has been replaced with the new **Unit Check** dashboard!")

st.markdown("""
The **Unit Check** dashboard provides the same functionality as the old Source Dashboard but with improved features:

✅ **7-day activity monitoring**  
✅ **Battery level tracking with reference lines**  
✅ **Last location mapping**  
✅ **Manufacturer filtering (SpoorTrack default)**  
✅ **Visual separators for better organization**  

""")

st.markdown("### 🚀 Go to Unit Check Dashboard")
st.markdown("Please use the **Unit Check** page from the sidebar for device monitoring.")

# Add a button to help users navigate
if st.button("📍 Take me to Unit Check", type="primary"):
    st.switch_page("pages/10_🔍_Unit_Check.py")