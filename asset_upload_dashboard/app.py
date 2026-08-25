"""
📦 Asset Upload

Simple form to add new records — with an optional PDF receipt attachment — to
the GCF Asset Register (GCF_assets) ArcGIS Online feature layer.

Mirrors the GAD "➕ Submit Data" tab's UX (see gad_dashboard/app.py):
plain form -> validate -> arcgis.features.FeatureLayer.edit_features() ->
success/error message. Dropdown options for country/programme, assigned-to,
asset category, and the category->type filter are pulled live from the
layer's own existing records (cached 10 min) rather than hardcoded, so they
stay in sync automatically. Each asset's point location is derived from its
country's existing-asset centroid — no manual map/pin step. Asset ID is
auto-generated as a "GCF-" + base36 (0-9, A-Z) running code.
"""

import os
import string
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from arcgis.features import FeatureLayer
from arcgis.gis import GIS

# Shared GCF Google OIDC login helper
_streamlit_root = Path(__file__).parent.parent
if str(_streamlit_root) not in sys.path:
    sys.path.insert(0, str(_streamlit_root))
from shared.auth import require_gcf_login

# ======== Configuration ========

AGOL_URL = "https://services1.arcgis.com/uMBFfFIXcCOpjlID/arcgis/rest/services/GCF_assets/FeatureServer/0"

# Windhoek, Namibia — GCF HQ. Fallback location only, used when a selected
# country/programme area has no existing assets yet to derive a centroid from.
DEFAULT_CENTER = (-22.5609, 17.0658)

# "GCF-" + base36 (digits 0-9, letters A-Z) running code, e.g. GCF-00A3F.
# Base36 keeps IDs short while covering far more values than plain digits
# (36^5 ≈ 60 million) — chosen over plain numeric since Courtney's existing
# ~900 legacy asset_id values are numeric-only; a longer alphanumeric code
# reads as clearly distinct from those at a glance. Purely-numeric suffixes
# still decode fine under base36 (digits mean the same thing), so this picks
# up cleanly from any numeric IDs this app already generated before this change.
ASSET_ID_PREFIX = "GCF-"
ASSET_ID_WIDTH = 5
_BASE36_ALPHABET = string.digits + string.ascii_uppercase

# Master Asset Registry dashboard (ArcGIS Online), embedded read-only in the
# second tab — same embedding pattern as the KEEP dashboard (pages/22_KEEP.py).
DASHBOARD_URL = "https://giraffecf.maps.arcgis.com/apps/dashboards/6890c9e6ba3846caa78e01ae085cd640"

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

# Coded value domain, pulled from the live layer schema (2026-08-25).
# label -> stored code. Keep in sync if the domain changes in ArcGIS Online.
# This is a true ArcGIS domain field (a fixed list enforced by the layer), so
# — unlike country/assigned/category — it doesn't get a free-text fallback:
# a typed value wouldn't match the domain and would fail to save.
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
_TYPE_LABEL_TO_CODE = dict(ASSET_TYPE_CHOICES)
_TYPE_CODE_TO_LABEL = {code: label for label, code in ASSET_TYPE_CHOICES}
ASSET_STATUS_CHOICES = ["Available", "Checked Out", "In Repair", "Lost", "Retired"]
ASSET_CONDITION_CHOICES = ["Excellent", "Good", "Fair", "Poor", "Damaged"]

_PLACEHOLDER_TYPE = "Select a type"
_PLACEHOLDER_STATUS = "Select a status"
_PLACEHOLDER_CONDITION = "Select a condition"
_PLACEHOLDER_CATEGORY = "Select a category"
_PLACEHOLDER_COUNTRY = "Select a country / programme area"


# ======== ID helpers ========

def _to_base36(n: int, width: int = ASSET_ID_WIDTH) -> str:
    if n <= 0:
        digits = "0"
    else:
        digits = ""
        while n > 0:
            n, r = divmod(n, 36)
            digits = _BASE36_ALPHABET[r] + digits
    return digits.rjust(width, "0")


# ======== Date helpers ========
# esriFieldTypeDateOnly fields (acquisition_date) expect a plain "YYYY-MM-DD"
# string. esriFieldTypeDate fields (purchase_date) expect epoch milliseconds
# (UTC). The arcgis python API doesn't do this conversion automatically for
# raw dict-based edit_features() calls.

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
            "(`st.secrets['arcgis']['asset_token']`). Ask Courtney to add one."
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


@st.cache_data(ttl=600, show_spinner=False)
def _load_dropdown_options():
    """Pull distinct country/assigned/category values, a default lat/lon
    centroid per country, and which asset types have historically been used
    with each category — all live from the layer's existing records.

    Returns (countries, assigned, categories, country_centroids, category_type_map)
    - countries, assigned, categories: sorted list[str]
    - country_centroids: dict[str, tuple[float, float]]
    - category_type_map: dict[str, list[str]] — asset type LABELS seen for
      each category, used to narrow the Asset type dropdown once a category
      is picked. A category with no history yet isn't in this dict — the
      form falls back to showing all asset types for it.
    Returns empty results (never raises) if the query fails — the form still
    works, just with empty dropdowns.
    """
    if not TOKEN:
        return [], [], [], {}, {}
    try:
        gis = _get_gis()
        feature_layer = FeatureLayer(AGOL_URL, gis=gis)
        result = feature_layer.query(
            where="1=1",
            out_fields="country_code,asset_assigned,asset_category,asset_type",
            return_geometry=True,
        )
    except Exception:
        return [], [], [], {}, {}

    countries, assigned, categories = set(), set(), set()
    country_points: dict[str, list[tuple[float, float]]] = {}
    category_types: dict[str, set[str]] = {}

    for f in result.features:
        attrs = f.attributes or {}
        geom = f.geometry or {}
        c = (attrs.get("country_code") or "").strip()
        a = (attrs.get("asset_assigned") or "").strip()
        cat = (attrs.get("asset_category") or "").strip()
        t_code = (attrs.get("asset_type") or "").strip()

        if c:
            countries.add(c)
            x, y = geom.get("x"), geom.get("y")
            if x is not None and y is not None:
                country_points.setdefault(c, []).append((y, x))
        if a:
            assigned.add(a)
        if cat:
            categories.add(cat)
        if cat and t_code:
            t_label = _TYPE_CODE_TO_LABEL.get(t_code, t_code)
            category_types.setdefault(cat, set()).add(t_label)

    country_centroids = {
        c: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        for c, pts in country_points.items()
        if pts
    }
    category_type_map = {c: sorted(types) for c, types in category_types.items()}

    return sorted(countries), sorted(assigned), sorted(categories), country_centroids, category_type_map


def _next_asset_id(feature_layer) -> str:
    """Next 'GCF-' + base36 running code, based on the highest existing one."""
    try:
        result = feature_layer.query(
            where=f"asset_id LIKE '{ASSET_ID_PREFIX}%'",
            out_fields="asset_id",
            return_geometry=False,
        )
        max_n = 0
        for f in result.features:
            raw = (f.attributes.get("asset_id") or "").strip()
            if raw.startswith(ASSET_ID_PREFIX):
                suffix = raw[len(ASSET_ID_PREFIX):]
                try:
                    max_n = max(max_n, int(suffix, 36))
                except ValueError:
                    pass
        return f"{ASSET_ID_PREFIX}{_to_base36(max_n + 1)}"
    except Exception:
        return f"{ASSET_ID_PREFIX}{_to_base36(1)}"


def submit_asset_to_agol(attributes: dict, lat: float, lon: float, pdf_file=None):
    """Add one new asset record, then (optionally) attach a PDF receipt to it.

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
                    attachment_message = "PDF receipt attached successfully."
                else:
                    attachment_message = (
                        "The asset record was saved, but the PDF receipt failed to "
                        "upload. You can add it manually in ArcGIS Online."
                    )
            except Exception as e:
                attachment_message = (
                    f"The asset record was saved, but the PDF receipt failed to "
                    f"upload ({e}). You can add it manually in ArcGIS Online."
                )
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        return True, message, attachment_message

    except Exception as e:
        return False, f"Error submitting data: {e}", None


# ======== Main application ========

def _render_add_asset_tab(feature_layer, has_attachments):
    with st.expander("ℹ️ How this works", expanded=False):
        st.markdown(
            """
1. Fill in the asset details below — fields marked **\\*** are required.
2. Attach a PDF receipt if you have one.
3. Click **Submit Asset** — you'll get a confirmation once it's saved.

- The Asset ID is generated automatically — you don't need to enter one.
- Location is set automatically based on the country/programme area you pick.
- Contact Courtney if you need to edit or remove a record submitted in error.
            """
        )

    countries, assigned_people, categories, country_centroids, category_type_map = _load_dropdown_options()
    next_id = _next_asset_id(feature_layer)
    st.info(f"🆔 Next Asset ID: **{next_id}** (generated automatically)")

    # -- Group 1: category / type / country / assigned --------------------------
    # These live OUTSIDE the form (not inside st.form) so that picking a
    # category can immediately narrow the Asset type options below it —
    # widgets inside a form only update on submit, which would break that.
    st.subheader("Asset details")

    asset_name = st.text_input("Asset name *", placeholder="e.g. Dell Latitude laptop")

    col1, col2 = st.columns(2)
    with col1:
        category_choice = st.selectbox(
            "Asset category *", [_PLACEHOLDER_CATEGORY] + categories, key="asset_category_select"
        )
        type_options = category_type_map.get(category_choice) or [label for label, _ in ASSET_TYPE_CHOICES]
        asset_type_label = st.selectbox(
            "Asset type *", [_PLACEHOLDER_TYPE] + type_options, key="asset_type_select"
        )
    with col2:
        country_choice = st.selectbox(
            "Country / Programme area *", [_PLACEHOLDER_COUNTRY] + countries, key="asset_country_select"
        )
        assigned_choice = st.selectbox(
            "Assigned to", ["Unassigned"] + assigned_people, key="asset_assigned_select"
        )

    st.markdown("---")

    with st.form("asset_submission_form", clear_on_submit=False):
        # -- Group 2: item identification ----------------------------------
        c1, c2 = st.columns(2)
        with c1:
            manufacturer = st.text_input("Manufacturer")
            asset_serial = st.text_input("Serial number")
        with c2:
            model = st.text_input("Model / description")
            asset_condition = st.selectbox(
                "Asset condition *", [_PLACEHOLDER_CONDITION] + ASSET_CONDITION_CHOICES
            )
        asset_status = st.selectbox("Asset status *", [_PLACEHOLDER_STATUS] + ASSET_STATUS_CHOICES)

        st.markdown("---")

        # -- Group 3: funding / cost -----------------------------------------
        grant_name = st.text_input("Grant name (if applicable)")
        c3, c4 = st.columns(2)
        purchase_date = c3.date_input("Purchase date", value=None)
        acquisition_date = c4.date_input("Acquisition date", value=None)
        acquisition_cost = st.number_input("Cost (N$)", min_value=0.0, value=0.0, step=1.0)

        st.markdown("---")

        # -- Group 4: notes ---------------------------------------------------
        notes = st.text_area("Notes")

        st.markdown("---")
        pdf_file = None
        if has_attachments:
            pdf_file = st.file_uploader("PDF receipt (optional)", type=["pdf"])
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
            if category_choice == _PLACEHOLDER_CATEGORY:
                errors.append("Please select an asset category.")
            if asset_type_label == _PLACEHOLDER_TYPE:
                errors.append("Please select an asset type.")
            if asset_status == _PLACEHOLDER_STATUS:
                errors.append("Please select an asset status.")
            if asset_condition == _PLACEHOLDER_CONDITION:
                errors.append("Please select an asset condition.")
            if country_choice == _PLACEHOLDER_COUNTRY:
                errors.append("Please select a country / programme area.")

            if errors:
                st.error("**Please fix the following:**")
                for e in errors:
                    st.error(f"- {e}")
            else:
                asset_type_code = _TYPE_LABEL_TO_CODE.get(asset_type_label, asset_type_label)
                final_assigned = None if assigned_choice == "Unassigned" else assigned_choice
                lat, lon = country_centroids.get(country_choice, DEFAULT_CENTER)
                asset_id = _next_asset_id(feature_layer)  # re-check right before submit

                attributes = {
                    "asset_id": asset_id,
                    "asset_name": asset_name,
                    "asset_category": category_choice,
                    "asset_type": asset_type_code,
                    "country_code": country_choice,
                    "asset_assigned": final_assigned,
                    "manufacturer": manufacturer or None,
                    "model": model or None,
                    "asset_serial": asset_serial or None,
                    "asset_condition": asset_condition,
                    "asset_status": asset_status,
                    "grant_name": grant_name or None,
                    "purchase_date": _date_to_epoch_ms(purchase_date),
                    "acquisition_date": _date_only_str(acquisition_date),
                    "acquisition_cost": acquisition_cost or None,
                    "notes": notes or None,
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
                    st.cache_data.clear()  # refresh dropdown options + next ID
                else:
                    st.error(f"❌ {message}")
                    st.info("Please check your AGOL token has write permissions and try again.")


def _render_dashboard_tab():
    st.caption("Live view of the Master Asset Registry (read-only).")
    components.iframe(DASHBOARD_URL, height=1000, scrolling=True)


def main():
    require_gcf_login(page_label="Asset Upload")

    st.title("📦 Asset Upload")
    st.caption("Add a new asset record to the GCF Asset Register")
    st.markdown("---")

    feature_layer, has_attachments = _get_layer_context()
    if feature_layer is None:
        return

    tab_add, tab_dashboard = st.tabs(["➕ Add Asset", "📊 Registry Dashboard"])

    with tab_add:
        _render_add_asset_tab(feature_layer, has_attachments)

    with tab_dashboard:
        _render_dashboard_tab()


if __name__ == "__main__":
    main()
