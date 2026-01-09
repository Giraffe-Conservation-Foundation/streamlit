import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Translocation Assessment",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Giraffe Translocation Priority Assessment")

st.markdown("""
Interactive maps showing translocation priority areas for giraffe conservation based on 
environmental suitability analysis using Google Earth Engine.
""")

st.info("📱 For best experience, use the fullscreen button in the bottom-right of the map viewer.")

# Create tabs for each species
tab1, tab2, tab3, tab4 = st.tabs(["🦒 Masai Giraffe", "🦒 Northern Giraffe", "🦒 Reticulated Giraffe", "🦒 Southern Giraffe"])

with tab1:
    st.subheader("Masai Giraffe Translocation Priority")
    st.markdown("[Open in Google Earth Engine ↗](https://translocation-priority.projects.earthengine.app/view/masai-giraffe-priority)")
    
    components.iframe(
        "https://translocation-priority.projects.earthengine.app/view/masai-giraffe-priority",
        height=800,
        scrolling=True
    )

with tab2:
    st.subheader("Northern Giraffe Translocation Priority")
    st.markdown("[Open in Google Earth Engine ↗](https://translocation-priority.projects.earthengine.app/view/northern-giraffe-priority)")
    
    components.iframe(
        "https://translocation-priority.projects.earthengine.app/view/northern-giraffe-priority",
        height=800,
        scrolling=True
    )

with tab3:
    st.subheader("Reticulated Giraffe Translocation Priority")
    st.markdown("[Open in Google Earth Engine ↗](https://translocation-priority.projects.earthengine.app/view/reticulated-giraffe-priority)")
    
    components.iframe(
        "https://translocation-priority.projects.earthengine.app/view/reticulated-giraffe-priority",
        height=800,
        scrolling=True
    )

with tab4:
    st.subheader("Southern Giraffe Translocation Priority")
    st.markdown("[Open in Google Earth Engine ↗](https://translocation-priority.projects.earthengine.app/view/southern-giraffe-priority)")
    
    components.iframe(
        "https://translocation-priority.projects.earthengine.app/view/southern-giraffe-priority",
        height=800,
        scrolling=True
    )

st.markdown("---")
st.caption("Data source: Google Earth Engine | Giraffe Conservation Foundation")
