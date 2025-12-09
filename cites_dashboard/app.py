"""
CITES Trade Database Dashboard for Giraffe
Live API feed from CITES Trade Database
https://trade.cites.org/
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path

# Path to local trade data CSV
TRADE_DATA_CSV = Path(__file__).parent / "comptabExport_1975_2025__251209.csv"
LAST_DOWNLOAD_DATE = "2025-12-09"

@st.cache_data
def load_local_trade_data():
    """
    Load CITES trade data from local CSV file
    Returns DataFrame and download date
    """
    if TRADE_DATA_CSV.exists():
        try:
            df = pd.read_csv(TRADE_DATA_CSV)
            # Create a unified Quantity column (prioritize importer, fallback to exporter)
            df['Quantity'] = df['Importer reported quantity'].fillna(df['Exporter reported quantity'])
            return df, LAST_DOWNLOAD_DATE
        except Exception as e:
            st.error(f"Error loading local trade data: {str(e)}")
            return None, None
    return None, None

def create_trade_visualizations(df, last_updated):
    """Create visualizations for CITES trade data from CSV"""
    
    if df is None or df.empty:
        st.warning("No trade data available")
        return
    
    # Show last updated date prominently
    st.info(f"📅 **Trade data last downloaded:** {last_updated}")
    st.caption("Note: This data is manually downloaded from https://trade.cites.org/ - it may not reflect the most recent transactions.")
    
    st.markdown("---")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", f"{len(df):,}")
    
    with col2:
        if "Year" in df.columns:
            year_range = f"{int(df['Year'].min())}-{int(df['Year'].max())}"
            st.metric("Year Range", year_range)
    
    with col3:
        if "Exporter" in df.columns:
            st.metric("Exporting Countries", df["Exporter"].nunique())
    
    with col4:
        if "Importer" in df.columns:
            st.metric("Importing Countries", df["Importer"].nunique())
    
    st.markdown("---")
    
    # Trade volume over time
    st.subheader("📊 Trade Volume Over Time")
    if "Year" in df.columns and "Quantity" in df.columns:
        df_clean = df.dropna(subset=["Year", "Quantity"])
        yearly_trade = df_clean.groupby("Year")["Quantity"].sum().reset_index()
        
        fig = px.line(
            yearly_trade,
            x="Year",
            y="Quantity",
            title="Total Giraffe Trade Volume by Year",
            labels={"Year": "Year", "Quantity": "Total Quantity"},
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Trade by purpose
    st.subheader("🎯 Trade by Purpose")
    col1, col2 = st.columns(2)
    
    with col1:
        if "Purpose" in df.columns:
            # Map purpose codes to full descriptions
            purpose_map = {
                'T': 'Commercial',
                'Z': 'Zoo',
                'S': 'Scientific',
                'H': 'Hunting trophy',
                'P': 'Personal',
                'M': 'Medical/Biomedical',
                'E': 'Educational',
                'N': 'Reintroduction',
                'B': 'Breeding in captivity',
                'L': 'Law enforcement'
            }
            
            purpose_counts = df["Purpose"].value_counts().reset_index()
            purpose_counts.columns = ["Purpose", "Count"]
            # Replace codes with descriptions
            purpose_counts["Purpose"] = purpose_counts["Purpose"].map(lambda x: purpose_map.get(x, x))
            
            fig = px.pie(
                purpose_counts,
                values="Count",
                names="Purpose",
                title="Trade Records by Purpose"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if "Term" in df.columns:
            # Map term codes to full descriptions
            term_map = {
                'bodies': 'Bodies',
                'bone': 'Bone',
                'bone carvings': 'Bone carvings',
                'skulls': 'Skulls',
                'skins': 'Skins',
                'trophies': 'Trophies',
                'hair': 'Hair',
                'live': 'Live animals',
                'meat': 'Meat',
                'specimens': 'Specimens',
                'skin pieces': 'Skin pieces',
                'tail': 'Tail'
            }
            
            term_counts = df["Term"].value_counts().head(10).reset_index()
            term_counts.columns = ["Term", "Count"]
            term_counts["Term"] = term_counts["Term"].map(lambda x: term_map.get(x, x.title()))
            
            fig = px.bar(
                term_counts,
                x="Count",
                y="Term",
                title="Top 10 Trade Terms",
                orientation="h"
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
    
    # Trade over time by term
    st.subheader("📈 Trade Volume by Term Over Time")
    
    if "Year" in df.columns and "Term" in df.columns and "Quantity" in df.columns:
        # Map term codes to full descriptions
        term_map = {
            'bodies': 'Bodies',
            'bone': 'Bone',
            'bone carvings': 'Bone carvings',
            'skulls': 'Skulls',
            'skins': 'Skins',
            'trophies': 'Trophies',
            'hair': 'Hair',
            'live': 'Live animals',
            'meat': 'Meat',
            'specimens': 'Specimens',
            'skin pieces': 'Skin pieces',
            'tail': 'Tail'
        }
        
        df_clean = df.dropna(subset=["Year", "Term", "Quantity"])
        # Get top 5 terms for clarity
        top_terms = df_clean.groupby("Term")["Quantity"].sum().nlargest(5).index
        df_top_terms = df_clean[df_clean["Term"].isin(top_terms)].copy()
        df_top_terms["Term"] = df_top_terms["Term"].map(lambda x: term_map.get(x, x.title()))
        term_yearly = df_top_terms.groupby(["Year", "Term"])["Quantity"].sum().reset_index()
        
        fig = px.bar(
            term_yearly,
            x="Year",
            y="Quantity",
            color="Term",
            title="Trade Volume by Term Over Time (Top 5)",
            labels={"Year": "Year", "Quantity": "Total Quantity", "Term": "Term"},
            barmode="stack"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Top exporters and importers
    st.subheader("🌍 Top Trading Countries")
    col1, col2 = st.columns(2)
    
    with col1:
        if "Exporter" in df.columns:
            exporter_counts = df["Exporter"].value_counts().head(15).reset_index()
            exporter_counts.columns = ["Country", "Exports"]
            
            fig = px.bar(
                exporter_counts,
                x="Exports",
                y="Country",
                title="Top 15 Exporting Countries",
                orientation="h"
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if "Importer" in df.columns:
            importer_counts = df["Importer"].value_counts().head(15).reset_index()
            importer_counts.columns = ["Country", "Imports"]
            
            fig = px.bar(
                importer_counts,
                x="Imports",
                y="Country",
                title="Top 15 Importing Countries",
                orientation="h"
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

def main():
    """Main application function"""
    
    st.title("📋 CITES Trade Database - Giraffe")
    
    st.markdown("""
    ### International trade records for **Giraffa camelopardalis**
    
    Data from the [CITES Trade Database](https://trade.cites.org/)
    
    **About CITES:**
    - Convention on International Trade in Endangered Species of Wild Fauna and Flora
    - Giraffe was listed on CITES Appendix II in 2019 (effective 2020)
    - All international commercial trade must be authorized and reported
    """)
    
    st.markdown("---")
    
    # Load local trade data from CSV
    trade_df, last_updated = load_local_trade_data()
    
    if trade_df is not None and not trade_df.empty:
        # Create tabs with trade data
        tab1, tab2, tab3 = st.tabs(["📊 Trade Summary", "📋 Raw Data", "ℹ️ About"])
        
        with tab1:
            st.subheader("📊 CITES Trade Summary")
            create_trade_visualizations(trade_df, last_updated)
        
        with tab2:
            # Filters
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if "Purpose" in trade_df.columns:
                    purposes = sorted(trade_df["Purpose"].dropna().unique())
                    purpose_filter = st.multiselect("Filter by Purpose", purposes)
            
            with col2:
                if "Exporter" in trade_df.columns:
                    exporters = sorted(trade_df["Exporter"].dropna().unique())
                    exporter_filter = st.multiselect("Filter by Exporter", exporters)
            
            with col3:
                if "Importer" in trade_df.columns:
                    importers = sorted(trade_df["Importer"].dropna().unique())
                    importer_filter = st.multiselect("Filter by Importer", importers)
            
            # Apply filters
            filtered_df = trade_df.copy()
            if purpose_filter:
                filtered_df = filtered_df[filtered_df["Purpose"].isin(purpose_filter)]
            if exporter_filter:
                filtered_df = filtered_df[filtered_df["Exporter"].isin(exporter_filter)]
            if importer_filter:
                filtered_df = filtered_df[filtered_df["Importer"].isin(importer_filter)]
            
            st.write(f"Showing **{len(filtered_df):,}** of **{len(trade_df):,}** records")
            st.dataframe(filtered_df, use_container_width=True, height=600)
            
            # Download button
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                "📥 Download Filtered Data",
                csv,
                f"giraffe_cites_trade_filtered.csv",
                "text/csv"
            )
    else:
        # No local trade data available
        st.error("Trade Data File Not Found")
        st.warning(f"""
        Expected file: `comptabExport_1975_2025__251209.csv`
        
        To add trade data:
        1. Visit [https://trade.cites.org/](https://trade.cites.org/)
        2. Search for "Giraffa camelopardalis"
        3. Download the results as CSV
        4. Save in the `cites_dashboard` folder
        5. Restart the app
        """)
        st.stop()
    
    with tab3:
        st.markdown("""
        ### Giraffe and CITES
        
        - **2019**: All giraffe species/subspecies listed on **CITES Appendix II**
        - **Effective**: November 26, 2020
        - **Impact**: All international commercial trade must be authorized and reported
        
        ### CITES Appendix II
        
        Species listed on Appendix II are not necessarily threatened with extinction but may become so 
        unless trade is closely controlled. Trade is permitted with appropriate permits/certificates.
        
        ### Data Source
        
        This dashboard uses the CITES trade database [https://trade.cites.org/](https://trade.cites.org/)
        
        ### Interpreting the Data
        
        **Purpose Codes:**
        - **T**: Commercial
        - **Z**: Zoo
        - **S**: Scientific
        - **H**: Hunting trophy
        - **P**: Personal
        - **M**: Medical (including biomedical research)
        - **E**: Educational
        - **N**: Reintroduction or introduction into the wild
        - **B**: Breeding in captivity or artificial propagation
        - **L**: Law enforcement / judicial / forensic
        
        **Source Codes:**
        - **W**: Specimens taken from the wild
        - **R**: Ranched specimens
        - **D**: Appendix-I animals bred in captivity for commercial purposes
        - **A**: Plants artificially propagated
        - **C**: Animals bred in captivity
        - **F**: Animals born in captivity
        - **U**: Source unknown
        - **I**: Confiscated or seized specimens
        
        ### Limitations
        
        - Data depends on accurate reporting by countries
        - Some records may have incomplete information
        - There can be delays in data submission and processing
        - Not all trade may be reported
        """)

if __name__ == "__main__":
    main()
