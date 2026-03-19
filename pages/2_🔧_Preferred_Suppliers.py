"""
Preferred Suppliers — GCF recommended tech equipment list.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

add_sidebar_logo()

st.title("Preferred Suppliers")
st.markdown("GCF recommended tech equipment for field operations.")

data = [
    {
        "Type":            "Camera",
        "Model":           "Sony Cyber-shot DSC-HX400V",
        "Price (Z/N)":     "",
        "Notes":           "Discontinued",
        "Link (NAM/SA)":   "https://luckytechcameras.com/products/sony-cyber-shot-dsc-hx400v-digital-camera-used",
        "Link (USA)":      "",
    },
    {
        "Type":            "Camera",
        "Model":           "Nikon P900 / P950 / P1000",
        "Price (Z/N)":     "NAD 8,000",
        "Notes":           "Buy in USA if possible",
        "Link (NAM/SA)":   "https://www.ormsdirect.co.za/collections/bridge-cameras",
        "Link (USA)":      "https://luckytechcameras.com/products/nikon-coolpix-p950-digital-bridge-camera-used",
    },
    {
        "Type":            "Phone",
        "Model":           "Blackview BV5300 Pro Rugged",
        "Price (Z/N)":     "ZAR 2,800",
        "Notes":           "Used by PPF, tested by CM — better battery/functionality than UleFone",
        "Link (NAM/SA)":   "https://www.takealot.com/blackview-bv5300-pro-rugged-android-14-smartphone-4gb-64gb-dual/PLID96437249",
        "Link (USA)":      "",
    },
    {
        "Type":            "GPS",
        "Model":           "Garmin eTrex SE / 22x",
        "Price (Z/N)":     "ZAR 3,500",
        "Notes":           "",
        "Link (NAM/SA)":   "https://www.garmin.com/en-ZA/p/835742/",
        "Link (USA)":      "",
    },
    {
        "Type":            "Computer / Laptop",
        "Model":           "No specific brand",
        "Price (Z/N)":     "",
        "Notes":           "Minimum 8 GB RAM, 512 GB SSD, Intel Core i3 CPU",
        "Link (NAM/SA)":   "",
        "Link (USA)":      "",
    },
    {
        "Type":            "Radio",
        "Model":           "MotoTrbo R2 NKP VHF Portable – Digital",
        "Price (Z/N)":     "NAD 6,000",
        "Notes":           "",
        "Link (NAM/SA)":   "https://www.radioelectronic.com.na",
        "Link (USA)":      "",
    },
    {
        "Type":            "Ground-to-Air Radio",
        "Model":           "Icom IC-A25 Airband Portable",
        "Price (Z/N)":     "NAD 10,000",
        "Notes":           "",
        "Link (NAM/SA)":   "https://www.radioelectronic.com.na",
        "Link (USA)":      "",
    },
    {
        "Type":            "Tracking Unit",
        "Model":           "SpoorTrack Iridium Giraffe Tail",
        "Price (Z/N)":     "USD 850",
        "Notes":           "USD 30 activation fee · USD 37.50 / month data",
        "Link (NAM/SA)":   "https://spoortrack.com/product/bird-trackers/",
        "Link (USA)":      "",
    },
    {
        "Type":            "Tracking Unit",
        "Model":           "Gsat Solar",
        "Price (Z/N)":     "USD 209",
        "Notes":           "USD 75.84 annual data · 4 locations / day",
        "Link (NAM/SA)":   "https://www.gsatsolar.com/pricing",
        "Link (USA)":      "",
    },
]

df = pd.DataFrame(data)

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Link (NAM/SA)": st.column_config.LinkColumn("Link (NAM/SA)", display_text="🔗 Open"),
        "Link (USA)":    st.column_config.LinkColumn("Link (USA)",    display_text="🔗 Open"),
    },
)
