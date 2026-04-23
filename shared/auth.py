"""
Shared authentication helpers for Twiga Tools.

Two login flows are provided:

* `require_gcf_login()` — Google OIDC via `st.login()`, restricted to
  @giraffeconservation.org Workspace accounts. Use for pages that only need
  to verify the user is a GCF staff member (no EarthRanger interaction).
  Examples: GAD, CITES, Publications, Survey data backup.

* `require_earthranger_login(session_key_prefix="er")` — username/password
  login to EarthRanger (twiga.pamdas.org) via `ecoscope.io.earthranger.EarthRangerIO`.
  The resulting client is cached in `st.session_state` so the user signs in
  once per browser session and every ER-backed page reuses the same session.

Both helpers call `st.stop()` if the user is not authenticated so downstream
code can assume a valid session.
"""

from __future__ import annotations

import re
from typing import Optional

import streamlit as st


# ─── Constants ────────────────────────────────────────────────────────────────
ALLOWED_DOMAIN = "giraffeconservation.org"
ER_SERVER = "https://twiga.pamdas.org"

# Session state keys for the shared EarthRanger session
_ER_CLIENT_KEY = "er_client"
_ER_USERNAME_KEY = "er_username"
_ER_AUTHENTICATED_KEY = "er_authenticated"


# ═══════════════════════════════════════════════════════════════════════════════
# Google OIDC (GCF staff) login
# ═══════════════════════════════════════════════════════════════════════════════
def require_gcf_login(page_label: Optional[str] = None) -> None:
    """
    Gate a page behind Google OIDC, restricted to the GCF domain.

    Call at the top of any page that is GCF-internal but does NOT need
    an EarthRanger session.

    Args:
        page_label: Optional page name to show in the sign-in prompt
                    (e.g. "GAD", "CITES Trade Database").
    """
    label = f" to access {page_label}" if page_label else ""

    # Local dev bypass: if no auth provider is configured, skip the gate entirely.
    try:
        _auth_configured = "auth" in st.secrets
    except Exception:
        _auth_configured = False

    if not _auth_configured:
        st.sidebar.info("🛠️ Local dev — auth bypassed")
        return

    if not getattr(st, "user", None) or not getattr(st.user, "is_logged_in", False):
        st.markdown("### 🔐 Log in with your GCF Google account")
        st.info(
            f"Sign in with your **@{ALLOWED_DOMAIN}** Google account{label}."
        )
        with st.expander("ℹ️ How to sign in", expanded=False):
            st.markdown(
                f"""
1. Click **Sign in with Google** below.
2. You'll be redirected to **Google's own sign-in page** — the same one you
   use for Gmail. Enter your **@{ALLOWED_DOMAIN}** email and password there
   (plus 2FA if enabled).
3. Google sends you back to Twiga Tools automatically.

**You do not create a separate password for Twiga Tools.** Your GCF Google
account is your login. If you can check Gmail with your GCF account, you
can use this page.

**Who can sign in:** anyone with an **@{ALLOWED_DOMAIN}** Google Workspace
account. Other addresses (Gmail, partner orgs) will be rejected — speak to
Courtney if you need access but don't have a GCF account.
                """
            )
        col1, _ = st.columns([1, 3])
        if col1.button("Sign in with Google", type="primary", key=f"gcf_login_{page_label or 'default'}"):
            try:
                st.login()
            except Exception:
                st.error(
                    "Google authentication is not configured in this environment. "
                    "This page requires a GCF Google account on the live app."
                )
                st.stop()
        st.stop()

    email = (st.user.email or "").lower()
    if not email.endswith(f"@{ALLOWED_DOMAIN}"):
        st.error(f"Access is restricted to @{ALLOWED_DOMAIN} accounts.")
        st.caption(f"Signed in as {st.user.email}")
        if st.button("Log out", key=f"gcf_logout_reject_{page_label or 'default'}"):
            st.logout()
        st.stop()

    # Sidebar controls (shown on every authenticated page)
    with st.sidebar:
        st.caption(f"👤 {st.user.email}")
        if st.button("Log out", use_container_width=True, key=f"gcf_logout_{page_label or 'default'}"):
            st.logout()


# ═══════════════════════════════════════════════════════════════════════════════
# EarthRanger login (shared across ER-backed pages)
# ═══════════════════════════════════════════════════════════════════════════════
def require_earthranger_login(page_label: Optional[str] = None):
    """
    Gate a page behind an EarthRanger (twiga.pamdas.org) login.

    On success, an authenticated `ecoscope.io.earthranger.EarthRangerIO`
    client is cached in `st.session_state` under `er_client`, so every
    ER-backed page that calls this helper reuses the same session — the
    user only signs in once per browser session.

    Returns:
        The authenticated `EarthRangerIO` client.

    Args:
        page_label: Optional page name to show in the sign-in prompt
                    (e.g. "NANW Survey Dashboard", "Genetic Dashboard").
    """
    # Already signed in? Render sidebar controls and return the cached client.
    if st.session_state.get(_ER_AUTHENTICATED_KEY) and _ER_CLIENT_KEY in st.session_state:
        with st.sidebar:
            st.caption(f"🌍 ER: {st.session_state.get(_ER_USERNAME_KEY, '?')}")
            if st.button("Sign out of EarthRanger", use_container_width=True, key="er_logout_sidebar"):
                clear_earthranger_login()
                st.rerun()
        return st.session_state[_ER_CLIENT_KEY]

    # Not signed in — show login form.
    label = f" to access {page_label}" if page_label else ""
    st.markdown("### 🔐 Log in with your EarthRanger account")
    st.info(
        f"Enter your **EarthRanger** (twiga.pamdas.org) username and password{label}. "
        "This is the same login you use for the EarthRanger web app or mobile app — "
        "it is **not** your GCF Google password."
    )
    with st.expander("ℹ️ How EarthRanger login works", expanded=False):
        st.markdown(
            f"""
- This page reads data from **EarthRanger** ({ER_SERVER}), so you need an
  EarthRanger account with the appropriate permissions.
- Your EarthRanger credentials are **different** from your @{ALLOWED_DOMAIN}
  Google account. If you don't have an EarthRanger account, speak to Courtney.
- You only sign in **once per browser session** — every Twiga Tools page that
  reads EarthRanger data will reuse this login automatically.
- Click **Sign out of EarthRanger** in the sidebar to end the session.
            """
        )

    with st.form("er_login_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        username = c1.text_input("EarthRanger username", key="er_username_input")
        password = c2.text_input("EarthRanger password", type="password", key="er_password_input")
        submit = st.form_submit_button("Sign in to EarthRanger", type="primary")

    if not submit:
        st.stop()

    if not username or not password:
        st.error("Both username and password are required.")
        st.stop()

    # Import lazily so pages that don't need ER don't pay the import cost.
    try:
        from ecoscope.io.earthranger import EarthRangerIO
    except ImportError as e:
        st.error(f"EarthRanger client library missing: {e}")
        st.stop()

    try:
        with st.spinner("Signing in to EarthRanger…"):
            er_io = EarthRangerIO(server=ER_SERVER, username=username, password=password)
            # Cheap call to verify credentials actually work.
            er_io.get_sources(limit=1)
    except Exception as e:
        st.error(f"EarthRanger sign-in failed: {e}")
        st.stop()

    st.session_state[_ER_CLIENT_KEY] = er_io
    st.session_state[_ER_USERNAME_KEY] = username
    st.session_state[_ER_AUTHENTICATED_KEY] = True
    st.success(f"Signed in to EarthRanger as **{username}**.")
    st.rerun()


def clear_earthranger_login() -> None:
    """Drop the cached EarthRanger session. Call on explicit sign-out."""
    for k in (_ER_CLIENT_KEY, _ER_USERNAME_KEY, _ER_AUTHENTICATED_KEY):
        st.session_state.pop(k, None)


def get_earthranger_client():
    """Return the cached EarthRanger client, or None if not signed in."""
    if not st.session_state.get(_ER_AUTHENTICATED_KEY):
        return None
    return st.session_state.get(_ER_CLIENT_KEY)


# ═══════════════════════════════════════════════════════════════════════════════
# Google Cloud Storage helpers (shared across GCS-backed pages)
# ═══════════════════════════════════════════════════════════════════════════════
def get_storage_client():
    """
    Build a GCS client from the shared service account in app secrets.

    Cached in session_state so repeated calls in the same session reuse the
    same client.
    """
    if "gcs_client" in st.session_state:
        return st.session_state.gcs_client

    try:
        from google.cloud import storage
        from google.oauth2 import service_account
    except ImportError as e:
        st.error(f"Google Cloud libraries missing: {e}")
        st.stop()

    try:
        creds_info = dict(st.secrets["gcp_service_account"])
    except KeyError:
        st.error("Missing `gcp_service_account` in app secrets. Ask an admin.")
        st.stop()

    try:
        credentials = service_account.Credentials.from_service_account_info(creds_info)
        client = storage.Client(credentials=credentials)
        st.session_state.gcs_client = client
        return client
    except Exception as e:
        st.error(f"Failed to initialise Cloud Storage client: {e}")
        st.stop()


def load_buckets(client=None) -> list[str]:
    """Return the list of bucket names accessible to the service account.

    Tries two strategies in order:
    1. ``list_buckets()`` — requires Storage Admin / Legacy Bucket Reader at
       project level. Works when the SA has broad project permissions.
    2. Secrets fallback — reads ``st.secrets["gcs_buckets"]["buckets"]`` (a
       TOML array of bucket names). Use this when the SA only has per-bucket
       IAM and cannot list all project buckets.
    """
    if "available_buckets" in st.session_state:
        return st.session_state.available_buckets

    if client is None:
        client = get_storage_client()

    # Strategy 1: project-level bucket listing
    try:
        names = [b.name for b in client.list_buckets()]
        if names:
            st.session_state.available_buckets = names
            return names
    except Exception:
        pass  # fall through to secrets fallback

    # Strategy 2: explicit bucket list in secrets
    try:
        names = list(st.secrets["gcs_buckets"]["buckets"])
        if names:
            st.session_state.available_buckets = names
            return names
    except Exception:
        pass

    st.error(
        "Could not discover any GCS buckets. "
        "Either grant the service account the **Storage Legacy Bucket Reader** "
        "role at project level, or add a `[gcs_buckets]` section to app secrets "
        "listing the bucket names explicitly.\n\n"
        "```toml\n[gcs_buckets]\nbuckets = [\"gcf_nam_ehgr\", \"gcf_ken_snn\"]\n```"
    )
    st.stop()


def extract_countries_sites_from_buckets(bucket_names: list[str]) -> dict[str, list[str]]:
    """Map gcf_<country>_<site> buckets into {country: [sites]}."""
    out: dict[str, set[str]] = {}
    for name in bucket_names:
        lower = name.lower()
        if not lower.startswith("gcf"):
            continue
        parts = re.split(r"[_\-]", lower)
        if len(parts) >= 3:
            country, site = parts[1].upper(), parts[2].upper()
            out.setdefault(country, set()).add(site)
    return {c: sorted(s) for c, s in sorted(out.items())}


def resolve_bucket_name(country: str, site: str, bucket_names: list[str]) -> Optional[str]:
    """Find the actual bucket matching `gcf_<country>_<site>` case-insensitively."""
    expected = f"gcf_{country.lower()}_{site.lower()}"
    for b in bucket_names:
        if b.lower().replace("-", "_") == expected:
            return b
    return None
