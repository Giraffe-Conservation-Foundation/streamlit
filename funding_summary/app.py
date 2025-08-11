"""
Funding Summary Dashboard
Secure financial donation analysis and reporting
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import hashlib

# Security configuration
FUNDING_PASSWORD_HASH = "5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5"  # Default: "admin123"

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate_funding_access():
    """Handle password authentication for funding data"""
    st.header("🔐 Secure Access Required")
    st.write("This page contains sensitive financial information and requires authentication.")
    
    password = st.text_input(
        "Enter Password",
        type="password",
        help="Contact administrator for access credentials"
    )
    
    if st.button("🔓 Access Funding Dashboard", type="primary"):
        if not password:
            st.error("❌ Password is required")
            return False
        
        if hash_password(password) == FUNDING_PASSWORD_HASH:
            st.success("✅ Access granted!")
            st.session_state.funding_authenticated = True
            st.rerun()
        else:
            st.error("❌ Invalid password")
            return False
    
    return False

def process_funding_excel(uploaded_file):
    """Process uploaded Excel file with multiple funding sheets"""
    try:
        # Read all sheets from the Excel file
        excel_data = pd.read_excel(uploaded_file, sheet_name=None)
        
        st.success(f"✅ Successfully loaded Excel file with {len(excel_data)} sheets")
        
        # Display sheet information
        with st.expander("📋 Sheet Information"):
            for sheet_name, df in excel_data.items():
                st.write(f"**{sheet_name}:** {len(df)} records, {len(df.columns)} columns")
                st.write(f"Columns: {', '.join(df.columns.tolist())}")
        
        return excel_data
        
    except Exception as e:
        st.error(f"❌ Error reading Excel file: {str(e)}")
        return None

def standardize_funding_data(excel_data):
    """Standardize and combine data from all sheets"""
    combined_data = []
    
    # Expected columns mapping (flexible to handle different naming conventions)
    column_mappings = {
        'donor': ['donor', 'donor_name', 'name', 'from', 'contributor'],
        'amount': ['amount', 'donation', 'value', 'sum', 'total'],
        'type': ['type', 'funding_type', 'donor_type', 'category', 'source'],
        'date': ['date', 'donation_date', 'received_date', 'timestamp'],
        'description': ['description', 'notes', 'memo', 'purpose', 'project']
    }
    
    for sheet_name, df in excel_data.items():
        if df.empty:
            continue
            
        # Create a copy and add funding mode
        sheet_df = df.copy()
        sheet_df['funding_mode'] = sheet_name
        
        # Standardize column names
        standardized_df = pd.DataFrame()
        
        for standard_col, possible_names in column_mappings.items():
            found_col = None
            for col in df.columns:
                if col.lower().strip() in [name.lower() for name in possible_names]:
                    found_col = col
                    break
            
            if found_col:
                standardized_df[standard_col] = sheet_df[found_col]
            else:
                standardized_df[standard_col] = None
        
        # Add funding mode
        standardized_df['funding_mode'] = sheet_name
        
        # Add any unmapped columns
        for col in df.columns:
            if col not in [k for mapping in column_mappings.values() for k in mapping]:
                standardized_df[f'extra_{col}'] = sheet_df[col]
        
        combined_data.append(standardized_df)
    
    if combined_data:
        final_df = pd.concat(combined_data, ignore_index=True)
        
        # Clean and process the data
        if 'amount' in final_df.columns:
            # Convert amount to numeric, handling currency symbols and commas
            final_df['amount'] = pd.to_numeric(
                final_df['amount'].astype(str).str.replace(r'[$,£€]', '', regex=True),
                errors='coerce'
            )
        
        if 'date' in final_df.columns:
            # Convert date columns
            final_df['date'] = pd.to_datetime(final_df['date'], errors='coerce')
        
        # Clean text columns
        text_columns = ['donor', 'type', 'description']
        for col in text_columns:
            if col in final_df.columns:
                final_df[col] = final_df[col].astype(str).str.strip()
                final_df[col] = final_df[col].replace(['nan', 'None', ''], None)
        
        return final_df
    
    return pd.DataFrame()

def display_funding_summary(df):
    """Display comprehensive funding analysis"""
    if df.empty:
        st.warning("No funding data available for analysis")
        return
    
    st.header("💰 Funding Summary Analysis")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    valid_amounts = df[df['amount'].notna() & (df['amount'] > 0)]
    
    with col1:
        total_funding = valid_amounts['amount'].sum()
        st.metric("Total Funding", f"${total_funding:,.2f}")
    
    with col2:
        num_donors = df['donor'].nunique()
        st.metric("Unique Donors", num_donors)
    
    with col3:
        num_donations = len(valid_amounts)
        st.metric("Total Donations", num_donations)
    
    with col4:
        avg_donation = valid_amounts['amount'].mean()
        st.metric("Average Donation", f"${avg_donation:,.2f}")
    
    # Funding by type analysis
    st.subheader("📊 Funding Analysis by Type")
    
    if 'type' in df.columns and df['type'].notna().any():
        type_summary = valid_amounts.groupby('type')['amount'].agg(['sum', 'count', 'mean']).round(2)
        type_summary.columns = ['Total Amount', 'Number of Donations', 'Average Donation']
        type_summary = type_summary.sort_values('Total Amount', ascending=False)
        
        # Display funding type table
        st.dataframe(type_summary.style.format({
            'Total Amount': '${:,.2f}',
            'Average Donation': '${:,.2f}'
        }), use_container_width=True)
        
        # Pie chart of funding by type
        fig_pie = px.pie(
            values=type_summary['Total Amount'],
            names=type_summary.index,
            title="Funding Distribution by Type",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(showlegend=True, height=500)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    else:
        st.info("No funding type information available for analysis")
    
    # Funding by mode analysis
    st.subheader("💳 Funding Analysis by Payment Mode")
    
    if 'funding_mode' in df.columns:
        mode_summary = valid_amounts.groupby('funding_mode')['amount'].agg(['sum', 'count', 'mean']).round(2)
        mode_summary.columns = ['Total Amount', 'Number of Donations', 'Average Donation']
        mode_summary = mode_summary.sort_values('Total Amount', ascending=False)
        
        # Bar chart of funding by mode
        fig_bar = px.bar(
            x=mode_summary.index,
            y=mode_summary['Total Amount'],
            title="Funding by Payment Mode",
            labels={'x': 'Payment Mode', 'y': 'Total Amount ($)'},
            color=mode_summary['Total Amount'],
            color_continuous_scale='Blues'
        )
        fig_bar.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_bar, use_container_width=True)
        
        st.dataframe(mode_summary.style.format({
            'Total Amount': '${:,.2f}',
            'Average Donation': '${:,.2f}'
        }), use_container_width=True)

def display_donor_analysis(df):
    """Display donor-specific analysis"""
    st.header("👥 Donor Analysis")
    
    if df.empty or 'donor' not in df.columns:
        st.warning("No donor data available for analysis")
        return
    
    valid_amounts = df[df['amount'].notna() & (df['amount'] > 0)]
    
    if valid_amounts.empty:
        st.warning("No valid donation amounts found")
        return
    
    # Top donors table
    donor_summary = valid_amounts.groupby('donor').agg({
        'amount': ['sum', 'count', 'mean'],
        'type': lambda x: ', '.join(x.dropna().unique()) if 'type' in df.columns else 'N/A',
        'funding_mode': lambda x: ', '.join(x.unique())
    }).round(2)
    
    donor_summary.columns = ['Total Donated', 'Number of Donations', 'Average Donation', 'Funding Types', 'Payment Modes']
    donor_summary = donor_summary.sort_values('Total Donated', ascending=False)
    
    st.subheader("🏆 Top Donors")
    
    # Display top 20 donors
    top_donors = donor_summary.head(20)
    st.dataframe(top_donors.style.format({
        'Total Donated': '${:,.2f}',
        'Average Donation': '${:,.2f}'
    }), use_container_width=True)
    
    # Donor distribution chart
    if len(donor_summary) > 1:
        # Top 10 donors for visualization
        top_10_donors = donor_summary.head(10)
        
        fig_donors = px.bar(
            x=top_10_donors['Total Donated'],
            y=top_10_donors.index,
            orientation='h',
            title="Top 10 Donors by Total Contribution",
            labels={'x': 'Total Donated ($)', 'y': 'Donor'},
            color=top_10_donors['Total Donated'],
            color_continuous_scale='Greens'
        )
        fig_donors.update_layout(height=500, showlegend=False)
        st.plotly_chart(fig_donors, use_container_width=True)

def display_temporal_analysis(df):
    """Display time-based funding analysis"""
    st.header("📅 Temporal Analysis")
    
    if df.empty or 'date' not in df.columns:
        st.warning("No date information available for temporal analysis")
        return
    
    valid_data = df[df['date'].notna() & df['amount'].notna() & (df['amount'] > 0)].copy()
    
    if valid_data.empty:
        st.warning("No valid dated donations found")
        return
    
    # Monthly funding trend
    valid_data['year_month'] = valid_data['date'].dt.to_period('M')
    monthly_summary = valid_data.groupby('year_month')['amount'].agg(['sum', 'count']).reset_index()
    monthly_summary['year_month_str'] = monthly_summary['year_month'].astype(str)
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=monthly_summary['year_month_str'],
        y=monthly_summary['sum'],
        mode='lines+markers',
        name='Monthly Funding',
        line=dict(color='blue', width=3),
        marker=dict(size=8)
    ))
    
    fig_trend.update_layout(
        title="Monthly Funding Trend",
        xaxis_title="Month",
        yaxis_title="Funding Amount ($)",
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig_trend, use_container_width=True)
    
    # Summary statistics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Funding Statistics")
        date_range = f"{valid_data['date'].min().strftime('%Y-%m-%d')} to {valid_data['date'].max().strftime('%Y-%m-%d')}"
        st.write(f"**Date Range:** {date_range}")
        st.write(f"**Months with Funding:** {len(monthly_summary)}")
        st.write(f"**Average Monthly Funding:** ${monthly_summary['sum'].mean():,.2f}")
    
    with col2:
        st.subheader("📈 Monthly Breakdown")
        monthly_display = monthly_summary.copy()
        monthly_display['sum'] = monthly_display['sum'].apply(lambda x: f"${x:,.2f}")
        monthly_display.columns = ['Month', 'Total Amount', 'Number of Donations']
        st.dataframe(monthly_display, use_container_width=True, hide_index=True)

def export_summary_report(df):
    """Generate exportable summary report"""
    st.header("📋 Export Summary Report")
    
    if df.empty:
        st.warning("No data available for export")
        return
    
    # Create summary dataframes
    summaries = {}
    
    valid_amounts = df[df['amount'].notna() & (df['amount'] > 0)]
    
    # Overall summary
    total_funding = valid_amounts['amount'].sum()
    num_donors = df['donor'].nunique()
    num_donations = len(valid_amounts)
    avg_donation = valid_amounts['amount'].mean()
    
    summaries['Overall Summary'] = pd.DataFrame({
        'Metric': ['Total Funding', 'Unique Donors', 'Total Donations', 'Average Donation'],
        'Value': [f"${total_funding:,.2f}", num_donors, num_donations, f"${avg_donation:,.2f}"]
    })
    
    # Funding by type
    if 'type' in df.columns and df['type'].notna().any():
        type_summary = valid_amounts.groupby('type')['amount'].agg(['sum', 'count', 'mean']).round(2)
        type_summary.columns = ['Total Amount', 'Number of Donations', 'Average Donation']
        summaries['Funding by Type'] = type_summary.reset_index()
    
    # Top donors
    if 'donor' in df.columns:
        donor_summary = valid_amounts.groupby('donor').agg({
            'amount': ['sum', 'count', 'mean']
        }).round(2)
        donor_summary.columns = ['Total Donated', 'Number of Donations', 'Average Donation']
        summaries['Top Donors'] = donor_summary.sort_values('Total Donated', ascending=False).head(20).reset_index()
    
    # Create Excel file with multiple sheets
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, summary_df in summaries.items():
            summary_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Include raw data
        df.to_excel(writer, sheet_name='Raw Data', index=False)
    
    output.seek(0)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"funding_summary_report_{timestamp}.xlsx"
    
    st.download_button(
        label="📥 Download Summary Report",
        data=output.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def main():
    """Main funding summary application"""
    # Initialize session state
    if 'funding_authenticated' not in st.session_state:
        st.session_state.funding_authenticated = False
    
    # Check authentication
    if not st.session_state.funding_authenticated:
        authenticate_funding_access()
        return
    
    # Main application interface
    st.title("💰 Funding Summary Dashboard")
    st.markdown("*Secure financial donation analysis and reporting*")
    
    # File upload section
    st.header("📁 Upload Funding Data")
    st.write("Upload an Excel file (.xlsx) with multiple sheets representing different payment modes (PayPal, Cheque, Wire, etc.)")
    
    uploaded_file = st.file_uploader(
        "Choose Excel file",
        type=['xlsx'],
        help="Each sheet should contain donor information, amounts, and funding types"
    )
    
    if uploaded_file is not None:
        # Process the uploaded file
        excel_data = process_funding_excel(uploaded_file)
        
        if excel_data:
            # Standardize the data
            with st.spinner("Processing funding data..."):
                df = standardize_funding_data(excel_data)
            
            if not df.empty:
                st.success(f"✅ Processed {len(df)} funding records from {len(excel_data)} sheets")
                
                # Display the analyses
                display_funding_summary(df)
                display_donor_analysis(df)
                display_temporal_analysis(df)
                export_summary_report(df)
                
                # Raw data viewer (optional)
                with st.expander("🔍 View Raw Data"):
                    st.dataframe(df, use_container_width=True)
                
            else:
                st.error("❌ No valid data found in the uploaded file")
    
    else:
        # Show example format
        st.info("💡 **Expected Excel Format:**")
        st.write("""
        Each sheet should contain columns like:
        - **Donor/Name**: Name of the donor
        - **Amount**: Donation amount (numbers only)
        - **Type**: Funding type (zoo, private, corporate, etc.)
        - **Date**: Date of donation (optional)
        - **Description**: Purpose or notes (optional)
        
        Sheet names represent payment modes: 'PayPal', 'Cheque', 'Wire Transfer', etc.
        """)
    
    # Logout option
    st.sidebar.markdown("---")
    if st.sidebar.button("🔒 Logout"):
        st.session_state.funding_authenticated = False
        st.rerun()

if __name__ == "__main__":
    main()
