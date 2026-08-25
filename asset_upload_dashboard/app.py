"""
📦 Asset Upload

Simple form to add new records — with an optional PDF attachment — to the
GCF Asset Register (GCF_assets) ArcGIS Online feature layer.

Mirrors the GAD "➕ Submit Data" tab's UX (see gad_dashboard/app.py):
plain form -> validate -> arcgis.features.FeatureLayer.edit_features() ->
success/error message. Extended here with a click-to-place map for the
required point geometry, and a PDF attachment step using
FeatureLayer.attachments.add().
"""

import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import folium
import streamlit as st
from arcgis.features import FeatureLayer
from arcgis.gis import GIS
from streamlit_folium import st_folium

# Shared GCF Google OIDC login helper
_streamlit_root = Path(__file__).parent.parent
if str(_streamlit_root) not in sys.path:
    sys.path.insert(0, str(_streamlit_root))
from shared.auth import require_gcf_login

# ======== Configuration ========

AGOL_URL = "https://services1.arcgis.com/uMBFfFIXcCOpjlID/arcgis/rest/services/GCF_assets/FeatureServer/0"

# Windhoek, Namibia — GCF HQ. Used only as the map's starting point;
# change this if GCF HQ isn't the sensible default for most assets.
DEFAULT_CENTER = (-22.5609, 17.0658)

# Get token safely - won't crash if secrets.toml doesn't exist locally.
# Uses a dedicated `asset_token` (separate API key, scoped to the GCF_assets
# layer only) rather than the shared `token` GAD uses, so the two modules'
# ArcGIS credentials can be rotated/scoped independently. Falls back to the
# shared token if `asset_token` isn't set, so this doesn't hard-fail if
# secrets haven't been updated yet.
try:
    _arcgis_secrets = st.secrets.get("arcgis", {})
    TOKEN = _arcgis_secrets.get("asset_token") or _arcgis_secrets.get("token")
except Exception:
    TOKEN = None  # For local development without secrets

# Coded value domains, pulled from the live layer schema (2026-08-25).
# label -> stored code. Keep in sync if the domains change in ArcGIS Online.
ASSET_TYPE_CHOICES = [
    ("IT/tech", "it_tech"),
    ("Digital", "digital"),
    ("Camping", "camping"),
    ("Vehicle", "vehicle"),
    ("Field tech", "field_tech"),
    ("Furniture", "furniture"),
    ("Appliance", "appliance"),
    ("Solar", "solar"),
]
ASSET_STATUS_CHOICES = ["Available", "Checked Out", "In Repair", "Lost", "Retired"]
ASSET_CONDITION_CHOICES = ["Excellent", "Good", "Fair", "Poor", "Damaged"]

_PLACEHOLDER_TYPE = "Select a type"
_PLACEHOLDER_STATUS = "Select a status"
_PLACEHOLDER_CONDITION = "Select a condition"


# ======== Date helpers ========
# esriFieldTypeDateOnly fields (checkout/checkin/acquisition/disposal dates)
# expect a plain "YYYY-MM-DD" string. esriFieldTypeDate fields (purchase_date,
# expected_return) expect epoch milliseconds (UTC).

def _date_only_str(d: date | None) -> str | None:
    return d.strftime("%Y-%m-%d") if d else None


def _date_to_epoch_ms(d: date | None) -> int | None:
    if not d:
        return None
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


# ======== ArcGIS layer helpers ========

@st.cache_resource(show_spinner=False)
def _get_gis():
    if not TOKEN:
        return None
    return GIS("https://www.arcgis.com", token=TOKEN)


def _get_layer_context():
    """Connect to the layer and check whether attachments are turned on.

    Returns (feature_layer, has_attachments) — feature_layer is None if the
    connection failed (an error is already shown to the user in that case).
    """
    if not TOKEN:
        st.error(
            "No ArcGIS token is configured for this app "
            "(`st.secrets['arcgis']['token']`). Ask Courtney to add one."
        )
        return None, False

    try:
        gis = _get_gis()
        feature_layer = FeatureLayer(AGOL_URL, gis=gis)
        has_attachments = bool(feature_layer.properties.get("hasAttachments", False))
        return feature_layer, has_attachments
    except Exception as e:
        st.error(f"Could not connect to the Asset Register layer: {e}")
        return None, False


def submit_asset_to_agol(attributes: dict, lat: float, lon: float, pdf_file=None):
    """Add one new asset record, then (optionally) attach a PDF to it.

    Returns (success: bool, message: str, attachment_message: str | None)
    """
    try:
        if not TOKEN:
            return False, "No AGOL token available. Write access is required.", None

        gis = GIS("https://www.arcgis.com", token=TOKEN)
        feature_layer = FeatureLayer(AGOL_URL, gis=gis)

        geometry = {"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}
        clean_attributes = {k: v for k, v in attributes.items() if v is not None and v != ""}
        new_feature = {"geometry": geometry, "attributes": clean_attributes}

        result = feature_layer.edit_features(adds=[new_feature])
        add_results = result.get("addResults") or []
        if not add_results:
            return False, "No results returned from AGOL.", None

        add_result = add_results[0]
        if not add_result.get("success"):
            err = add_result.get("error", {}).get("description", "Unknown error")
            return False, f"Failed to add record: {err}", None

        object_id = add_result["objectId"]
        message = f"Asset record added successfully (ID {object_id})."

        attachment_message = None
        if pdf_file is not None:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf", delete=False, prefix="asset_upload_"
                ) as tmp:
                    tmp.write(pdf_file.getbuffer())
                    tmp_path = tmp.name

                att_result = feature_layer.attachments.add(object_id, tmp_path)
                success = bool(
                    isinstance(att_result, dict)
                    and att_result.get("addAttachmentResult", {}).get("success")
                )
                if success:
                    attachment_message = "PDF attached successfully."
                else:
                    attachment_message = (
                        "The asset record was saved, but the PDF attachment failed to "
                        "upload. You can add it manually in ArcGIS Online."
                    )
            except Exception as e:
                attachment_message = (
                    f"The asset record was saved, but the PDF attachment failed to "
                    f"upload ({e}). You can add it manually in ArcGIS Online."
                )
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        return True, message, attachment_message

    except Exception as e:
        return False, f"Error submitting data: {e}", None


# ======== Location picker (click-to-place map) ========

def _location_picker():
    st.subheader("📍 Asset location")
    st.caption("Click anywhere on the map to drop a pin at this asset's location.")

    if "asset_pin" not in st.session_state:
        st.session_state.asset_pin = None

    pin = st.session_state.asset_pin
    center = pin or DEFAULT_CENTER
    m = folium.Map(location=center, zoom_start=12 if pin else 6)
    folium.Marker(center, icon=folium.Icon(color="red")).add_to(m)

    map_data = st_folium(m, height=350, width=700, key="asset_location_map")

    clicked = map_data.get("last_clicked") if map_data else None
    if clicked:
        new_pin = (clicked["lat"], clicked["lng"])
        if new_pin != st.session_state.asset_pin:
            st.session_state.asset_pin = new_pin
            st.rerun()

    if st.session_state.asset_pin:
        lat, lon = st.session_state.asset_pin
        st.success(f"📍 Location set: {lat:.5f}, {lon:.5f}")
        with st.expander("Enter coordinates manually instead", expanded=False):
            c1, c2 = st.columns(2)
            man_lat = c1.number_input(
                "Latitude", value=float(lat), format="%.5f", key="asset_manual_lat"
            )
            man_lon = c2.number_input(
                "Longitude", value=float(lon), format="%.5f", key="asset_manual_lon"
            )
            if st.button("Use these coordinates", key="asset_use_manual_coords"):
                st.session_state.asset_pin = (man_lat, man_lon)
                st.rerun()
    else:
        st.info("👆 No location set yet — click on the map above.")


# ======== Main application ========

def main():
    require_gcf_login(page_label="Asset Upload")

    st.title("📦 Asset Upload")
    st.caption("Add a new asset record to the GCF Asset Register")
    st.markdown("---")

    with st.expander("ℹ️ How this works", expanded=False):
        st.markdown(
            """
1. Fill in the asset details below — only a few fields are required, the rest are optional.
2. Click on the map to mark where the asset is located.
3. Attach a PDF (e.g. a receipt or invoice) if you have one.
4. Click **Submit Asset** — you'll get a confirmation once it's saved.

- Fields marked **\\*** are required.
- Contact Courtney if you need to edit or remove a record submitted in error.
            """
        )

    feature_layer, has_attachments = _get_layer_context()
    if feature_layer is None:
        return

    _location_picker()
    st.markdown("---")

    with st.form("asset_submission_form", clear_on_submit=False):
        st.subheader("Asset details")

        col1, col2 = st.columns(2)
        with col1:
            asset_name = st.text_input("Asset name *", placeholder="e.g. Dell Latitude laptop")
            asset_type_label = st.selectbox(
                "Asset type *", [_PLACEHOLDER_TYPE] + [label for label, _ in ASSET_TYPE_CHOICES]
            )
            asset_status = st.selectbox("Asset status *", [_PLACEHOLDER_STATUS] + ASSET_STATUS_CHOICES)
        with col2:
            asset_condition = st.selectbox(
                "Asset condition *", [_PLACEHOLDER_CONDITION] + ASSET_CONDITION_CHOICES
            )
            asset_assigned = st.text_input("Assigned to", placeholder="Name of staff member, if any")
            country_code = st.text_input("Country / Programme area", placeholder="e.g. NAM, KEN, UGA")

        with st.expander("➕ Additional details (optional)", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                asset_id = st.text_input("Asset ID / tag number", placeholder="e.g. GCF-IT-014")
                asset_serial = st.text_input("Serial number")
                manufacturer = st.text_input("Manufacturer")
                model = st.text_input("Model / description")
                asset_category = st.text_input("Asset category")
                grant_name = st.text_input("Grant name")
                project_trip = st.text_input("Current project / trip")
            with c2:
                purchase_date = st.date_input("Purchase date", value=None)
                acquisition_date = st.date_input("Acquisition date", value=None)
                expected_return = st.date_input("Expected return date", value=None)
                checkout_date = st.date_input("Checkout date", value=None)
                checkin_date = st.date_input("Check-in date", value=None)
                disposal_date = st.date_input("Disposal date", value=None)

            c3, c4, c5 = st.columns(3)
            acquisition_cost = c3.number_input(
                "Acquisition cost (N$)", min_value=0.0, value=0.0, step=1.0
            )
            additions_cost = c4.number_input("Additions (N$)", min_value=0.0, value=0.0, step=1.0)
            valued_cost = c5.number_input("Valued cost (N$)", min_value=0, value=0, step=1)

            location_notes = st.text_area("Location notes")
            notes = st.text_area("Notes")

        st.markdown("---")
        pdf_file = None
        if has_attachments:
            pdf_file = st.file_uploader("Attach a PDF (optional)", type=["pdf"])
        else:
            st.info(
                "📎 PDF attachments aren't turned on for this layer yet — ask Courtney to "
                "enable **Attachments** in the layer's settings in ArcGIS Online if you need this."
            )

        submitted = st.form_submit_button(
            "Submit Asset", use_container_width=True, type="primary"
        )

        if submitted:
            errors = []
            if not asset_name:
                errors.append("Asset name is required.")
            if asset_type_label == _PLACEHOLDER_TYPE:
                errors.append("Please select an asset type.")
            if asset_status == _PLACEHOLDER_STATUS:
                errors.append("Please select an asset status.")
            if asset_condition == _PLACEHOLDER_CONDITION:
                errors.append("Please select an asset condition.")
            if st.session_state.get("asset_pin") is None:
                errors.append("Please click on the map above to set this asset's location.")

            if errors:
                st.error("**Please fix the following:**")
                for e in errors:
                    st.error(f"- {e}")
            else:
                asset_type_code = dict(ASSET_TYPE_CHOICES)[asset_type_label]
                lat, lon = st.session_state.asset_pin

                attributes = {
                    "asset_id": asset_id or None,
                    "asset_name": asset_name,
                    "asset_type": asset_type_code,
                    "asset_status": asset_status,
                    "asset_condition": asset_condition,
                    "checkout_date": _date_only_str(checkout_date),
                    "checkin_date": _date_only_str(checkin_date),
                    "asset_assigned": asset_assigned or None,
                    "asset_serial": asset_serial or None,
                    "manufacturer": manufacturer or None,
                    "model": model or None,
                    "purchase_date": _date_to_epoch_ms(purchase_date),
                    "expected_return": _date_to_epoch_ms(expected_return),
                    "location_notes": location_notes or None,
                    "project_trip": project_trip or None,
                    "notes": notes or None,
                    "country_code": country_code or None,
                    "grant_name": grant_name or None,
                    "acquisition_date": _date_only_str(acquisition_date),
                    "acquisition_cost": acquisition_cost or None,
                    "additions_cost": additions_cost or None,
                    "valued_cost": int(valued_cost) if valued_cost else None,
                    "disposal_date": _date_only_str(disposal_date),
                    "asset_category": asset_category or None,
                }

                with st.spinner("Submitting asset record…"):
                    success, message, attachment_message = submit_asset_to_agol(
                        attributes, lat, lon, pdf_file
                    )

                if success:
                    st.success(f"✅ {message}")
                    if attachment_message:
                        if "failed" in attachment_message.lower():
                            st.warning(f"⚠️ {attachment_message}")
                        else:
                            st.success(f"📎 {attachment_message}")
                    st.balloons()
                    st.info("You can submit another asset by filling in the form again.")
                    st.session_state.asset_pin = None
                else:
                    st.error(f"❌ {message}")
                    st.info("Please check your AGOL token has write permissions and try again.")


if __name__ == "__main__":
    main()
