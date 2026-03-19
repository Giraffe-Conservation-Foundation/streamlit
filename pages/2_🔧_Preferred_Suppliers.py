"""
Preferred Suppliers — GCF recommended tech equipment list.
"""

import sys
from pathlib import Path

import streamlit as st

current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

add_sidebar_logo()

st.title("Preferred Suppliers")
st.markdown("GCF recommended tech equipment for field operations.")

data = [
    {
        "Type":    "Camera",
        "Model":   "Nikon P900 / P950 / P1000",
        "Price":   "NAD 8,000",
        "Notes":   "Buy in USA if possible",
        "Link":    "https://www.ormsdirect.co.za/collections/bridge-cameras",
    },
    {
        "Type":    "Phone",
        "Model":   "Blackview BV5300 Pro Rugged",
        "Price":   "ZAR 2,800",
        "Notes":   "",
        "Link":    "https://www.takealot.com/blackview-bv5300-pro-rugged-android-14-smartphone-4gb-64gb-dual/PLID96437249",
    },
    {
        "Type":    "GPS",
        "Model":   "Garmin eTrex SE / 22x",
        "Price":   "ZAR 3,500",
        "Notes":   "",
        "Link":    "https://www.garmin.com/en-ZA/p/835742/",
    },
    {
        "Type":    "Computer / Laptop",
        "Model":   "No specific brand",
        "Price":   "",
        "Notes":   "Minimum 8 GB RAM, 512 GB SSD, Intel Core i3 CPU",
        "Link":    "",
    },
    {
        "Type":    "Radio",
        "Model":   "MotoTrbo R2 NKP VHF Portable – Digital",
        "Price":   "NAD 6,000",
        "Notes":   "",
        "Link":    "https://www.radioelectronic.com.na",
    },
    {
        "Type":    "Ground-to-Air Radio",
        "Model":   "Icom IC-A25 Airband Portable",
        "Price":   "NAD 10,000",
        "Notes":   "",
        "Link":    "https://www.radioelectronic.com.na",
    },
    {
        "Type":    "Tracking Unit",
        "Model":   "SpoorTrack Iridium Giraffe Tail",
        "Price":   "USD 850",
        "Notes":   "USD 30 activation fee · USD 37.50 / month data",
        "Link":    "https://spoortrack.com/product/bird-trackers/",
    },
    {
        "Type":    "Tracking Unit",
        "Model":   "Gsat Solar",
        "Price":   "USD 209",
        "Notes":   "USD 75.84 annual data · 4 locations / day",
        "Link":    "https://www.gsatsolar.com/pricing",
    },
]

rows_html = ""
for row in data:
    if row["Link"]:
        model_cell = f'<a href="{row["Link"]}" target="_blank">{row["Model"]}</a>'
    else:
        model_cell = row["Model"]
    rows_html += f"""
        <tr>
            <td>{row["Type"]}</td>
            <td>{model_cell}</td>
            <td>{row["Price"]}</td>
            <td>{row["Notes"]}</td>
        </tr>"""

st.markdown(f"""
<style>
    section.main > div {{
        max-width: 1200px;
    }}
    .suppliers-table {{
        border-collapse: collapse;
        font-size: 0.9rem;
        table-layout: auto;
    }}
    .suppliers-table th, .suppliers-table td {{
        white-space: nowrap;
    }}
    .suppliers-table th {{
        text-align: left;
        padding: 8px 16px;
        border-bottom: 2px solid #ddd;
        color: #888;
        font-weight: 600;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .suppliers-table td {{
        padding: 8px 16px;
        border-bottom: 1px solid #eee;
    }}
    .suppliers-table a {{
        color: #1f77b4;
        text-decoration: none;
    }}
    .suppliers-table a:hover {{
        text-decoration: underline;
    }}
</style>
<table class="suppliers-table">
<thead>
        <tr>
            <th>Type</th>
            <th>Model</th>
            <th>Price</th>
            <th>Notes</th>
        </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
</table>
""", unsafe_allow_html=True)
