"""
Publications Dashboard
Display GCF publications from Zotero library
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict
import sys
from pathlib import Path

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

try:
    from shared.utils import add_sidebar_logo
except ImportError:
    def add_sidebar_logo():
        pass

# Custom CSS for better styling
st.markdown("""
<style>
    .section-header {
        color: #db580f;
        font-size: 1.8rem;
        font-weight: bold;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #db580f;
    }
    .metric-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #dee2e6;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        color: #db580f;
    }
    .metric-label {
        font-size: 1.1rem;
        color: #6c757d;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ======== Authentication Functions ========

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        try:
            # Try to get password from secrets
            if st.session_state["password"] == st.secrets["passwords"]["publications_password"]:
                st.session_state["password_correct"] = True
                del st.session_state["password"]  # don't store password
            else:
                st.session_state["password_correct"] = False
        except Exception as e:
            # For local development without secrets.toml, use a default password
            if st.session_state["password"] == "admin":
                st.session_state["password_correct"] = True
                del st.session_state["password"]
            else:
                st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.write("*Please enter password to access the Publications Dashboard.*")
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

# ======== Zotero Functions ========

def get_zotero_gcf_publications(library_id, library_type="group", api_key=None, tag="GCF", collection_key=None):
    """
    Fetch publications with specific tag from Zotero library
    
    Args:
        library_id (str): Zotero library ID 
        library_type (str): 'group' or 'user' library
        api_key (str): Zotero API key (optional for public libraries)
        tag (str): Tag to filter by (default: "GCF")
        collection_key (str): Specific collection/subfolder key (optional)
    
    Returns:
        list: List of publications with details
    """
    try:
        # Base URL for Zotero API
        base_url = f"https://api.zotero.org/{library_type}s/{library_id}"
        
        # Build URL
        if collection_key:
            url = f"{base_url}/collections/{collection_key}/items"
        else:
            url = f"{base_url}/items"
        
        # Parameters
        params = {
            "format": "json",
            "tag": tag,  # Filter by tag
            "itemType": "-attachment",  # Exclude attachments
            "limit": 100  # Adjust as needed
        }
        
        # Headers
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Make request
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        items = response.json()
        
        publications = []
        for item in items:
            data = item.get("data", {})
            
            # Extract year from date
            date_str = data.get("date", "")
            year = "Unknown"
            if date_str:
                # Try to extract year from various date formats
                for fmt in ["%Y", "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"]:
                    try:
                        dt = datetime.strptime(date_str[:10], fmt)
                        year = str(dt.year)
                        break
                    except:
                        # If it's just a 4-digit year
                        if len(date_str) >= 4 and date_str[:4].isdigit():
                            year = date_str[:4]
                            break
            
            # Extract authors
            creators = data.get("creators", [])
            authors = []
            for creator in creators:
                if creator.get("creatorType") in ["author", "editor"]:
                    last_name = creator.get("lastName", "")
                    first_name = creator.get("firstName", "")
                    if last_name and first_name:
                        authors.append(f"{last_name}, {first_name}")
                    elif last_name:
                        authors.append(last_name)
            
            authors_str = "; ".join(authors) if authors else "Unknown"
            
            publications.append({
                "title": data.get("title", "Untitled"),
                "authors": authors_str,
                "year": year,
                "date": date_str,
                "item_type": data.get("itemType", "Unknown"),
                "publication_title": data.get("publicationTitle", ""),
                "url": data.get("url", ""),
                "doi": data.get("DOI", ""),
                "tags": [tag.get("tag", "") for tag in data.get("tags", [])]
            })
        
        return publications
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching Zotero data: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Error processing Zotero data: {str(e)}")
        return []

def main():
    """Main application function"""
    
    # Add logo to sidebar
    add_sidebar_logo()
    
    # Check password
    if not check_password():
        return
    
    # Page title
    st.title("📚 GCF Publications")
    st.markdown("Research and documentation from the Giraffe Conservation Foundation")
    st.markdown("---")
    
    # Zotero configuration
    zotero_library_id = "5147968"
    library_type = "group"
    zotero_api_key = "yWn1NPGtfjZOVDyeulrhcczL"
    collection_key = "55G83VRS"
    
    st.info("📚 Connected to GCF Zotero library (Collection: 55G83VRS)")
    
    # Fetch publications
    with st.spinner("Fetching GCF publications from Zotero..."):
        publications = get_zotero_gcf_publications(
            library_id=zotero_library_id,
            library_type=library_type,
            api_key=zotero_api_key,
            tag="GCF",
            collection_key=collection_key
        )
    
    if not publications:
        st.warning("No publications found with the 'GCF' tag.")
        return
    
    # Filter out invalid years
    publications = [pub for pub in publications if pub['year'] not in ["0000", "9999", "Unknown"]]
    
    if not publications:
        st.warning("No valid publications found after filtering.")
        return
    
    # Summary metrics
    st.markdown('<div class="section-header">📊 Publication Summary</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(publications)}</div>
            <div class="metric-label">Total Publications</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Count by year
    year_counts = defaultdict(int)
    for pub in publications:
        year_counts[pub['year']] += 1
    
    # Sort years (no need to handle Unknown since we filtered it out)
    sorted_years = sorted(year_counts.keys())
    
    with col2:
        latest_year = sorted_years[0] if sorted_years else "N/A"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{latest_year}</div>
            <div class="metric-label">Most Recent Year</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        num_years = len(sorted_years)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{num_years}</div>
            <div class="metric-label">Years Covered</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Publications by year chart
    st.markdown('<div class="section-header">📈 Publications by Year</div>', unsafe_allow_html=True)
    
    if year_counts:
        # Create dataframe for chart
        chart_data = pd.DataFrame([
            {"Year": year, "Count": count} 
            for year, count in year_counts.items()
        ]).sort_values("Year")
        
        if not chart_data.empty:
            fig = px.bar(
                chart_data, 
                x="Year", 
                y="Count",
                title="Number of Publications per Year",
                labels={"Count": "Number of Publications"},
                color_discrete_sequence=["#db580f"]
            )
            fig.update_layout(
                xaxis_title="Year",
                yaxis_title="Number of Publications",
                showlegend=False,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Summary table
        st.markdown("### Summary by Year")
        summary_df = pd.DataFrame([
            {"Year": year, "Number of Publications": count}
            for year, count in sorted(year_counts.items(), reverse=True)
        ])
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    # List all publications
    st.markdown('<div class="section-header">📚 All Publications</div>', unsafe_allow_html=True)
    
    # Filter options
    col1, col2 = st.columns(2)
    
    with col1:
        filter_year = st.selectbox(
            "Filter by Year",
            ["All"] + sorted_years,
            index=0
        )
    
    with col2:
        # Get unique item types
        item_types = sorted(list(set([pub['item_type'] for pub in publications])))
        filter_type = st.selectbox(
            "Filter by Type",
            ["All"] + item_types,
            index=0
        )
    
    # Filter publications
    filtered_pubs = publications
    if filter_year != "All":
        filtered_pubs = [pub for pub in filtered_pubs if pub['year'] == filter_year]
    if filter_type != "All":
        filtered_pubs = [pub for pub in filtered_pubs if pub['item_type'] == filter_type]
    
    # Sort by year (descending)
    filtered_pubs = sorted(filtered_pubs, key=lambda x: x['year'], reverse=True)
    
    st.write(f"Showing {len(filtered_pubs)} publication(s)")
    
    # Display publications as a table
    if filtered_pubs:
        # Create DataFrame for display
        table_data = []
        for pub in filtered_pubs:
            # Create hyperlink if URL exists
            title_with_link = pub['title']
            if pub['url']:
                title_with_link = f'[{pub["title"]}]({pub["url"]})'
            
            table_data.append({
                "Title": title_with_link,
                "Authors": pub['authors'],
                "Year": pub['year'],
                "Type": pub['item_type'],
                "Journal/Publication": pub['publication_title'],
                "DOI": pub['doi'],
                "URL": pub['url']
            })
        
        display_df = pd.DataFrame(table_data)
        st.dataframe(display_df, use_container_width=True, hide_index=True, column_config={
            "Title": st.column_config.LinkColumn("Title", width="large"),
        })

if __name__ == "__main__":
    main()
