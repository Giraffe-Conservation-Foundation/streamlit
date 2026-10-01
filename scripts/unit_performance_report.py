"""
Quarterly GPS Unit Performance Report — headless runner.

Builds the same report as the TwigaTools "Unit Performance Report" page
(pages/25_📡_Unit_Performance_Report.py), but with no Streamlit UI. It:

  1. logs in to EarthRanger with credentials from environment variables,
  2. runs the page's own fetch → analyse → chart → build_docx pipeline
     (imported from unit_performance_dashboard/app.py, so there is one source of truth),
  3. converts the .docx to PDF with LibreOffice (scripts/docx_to_pdf.py, which also
     fills in the table of contents),
  4. emails the PDF, with the .docx attached as well so it can still be edited.

Run by .github/workflows/unit_performance_report.yml on the 1st of Jan/Apr/Jul/Oct.

Local usage (from the repo root):
    python scripts/unit_performance_report.py --no-email --out-dir report_out

Environment variables
    ER_SERVER, ER_USERNAME, ER_PASSWORD     EarthRanger login (same secrets as the backup workflow)
    SMTP_USER, SMTP_PASSWORD                Google Workspace sender + app password
    REPORT_RECIPIENTS                       comma-separated list of recipient addresses
    SMTP_HOST / SMTP_PORT                   optional, default smtp.gmail.com / 465
"""

from __future__ import annotations

import argparse
import gc
import importlib.util
import logging
import os
import shutil
import smtplib
import subprocess
import sys
from datetime import date
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_FILE = REPO_ROOT / "unit_performance_dashboard" / "app.py"
PDF_CONVERTER = Path(__file__).resolve().parent / "docx_to_pdf.py"
DEFAULT_AUTHOR = "Courtney Marneweck, GCF"

log = logging.getLogger("unit_performance_report")


# ─── Helpers ────────────────────────────────────────────────────────────────

def load_app_module():
    """Import unit_performance_dashboard/app.py the same way the Streamlit page does."""
    sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("unit_performance_app", APP_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def uncached(fn):
    """Call the function underneath @st.cache_data.

    Outside a Streamlit server the cache would still hold every full observation
    history in memory for the life of the process; going straight to the wrapped
    function lets each manufacturer's data be freed once it has been analysed."""
    return getattr(fn, "__wrapped__", fn)


def previous_quarter(report_date: date) -> pd.Period:
    """The last *completed* quarter, e.g. a run on 2026-10-01 → 2026Q3."""
    return pd.Timestamp(report_date).to_period("Q") - 1


def quarter_text(q: pd.Period) -> str:
    return f"Q{q.quarter} {q.year}"


def connect_earthranger():
    from ecoscope.io.earthranger import EarthRangerIO

    server = os.environ.get("ER_SERVER", "https://twiga.pamdas.org")
    if not server.startswith("http"):
        server = f"https://{server}"
    log.info("Logging in to EarthRanger at %s", server)
    return EarthRangerIO(
        server=server,
        username=os.environ["ER_USERNAME"],
        password=os.environ["ER_PASSWORD"],
    )


# ─── Report generation (mirrors _main_implementation() in app.py) ───────────

def generate_results(app, er) -> list[dict]:
    """Fetch + analyse every manufacturer. Raises if nothing usable comes back."""
    country_region_map, group_debug = uncached(app.fetch_subject_country_region)(er)
    log.info("Subject groups: %s", group_debug)
    if not country_region_map:
        log.warning("No subject groups resolved — country/region will show as unknown.")

    subject_metadata = uncached(app.fetch_subject_metadata)(er)
    if not subject_metadata:
        raise RuntimeError(
            "Could not resolve any subject names/species from EarthRanger, so the "
            "giraffe-only filter can't be applied. Check the account's subjects/ permissions."
        )

    results = []
    for label, cfg in app.MANUFACTURERS.items():
        log.info("── %s", label)
        sources_df = uncached(app.fetch_manufacturer_sources)(er, cfg["provider"])
        if sources_df.empty:
            log.warning("No %s tracking sources found — skipping.", label)
            continue
        source_ids = tuple(sorted(sources_df["id"].astype(str).unique()))

        assignments_df = uncached(app.fetch_assignments)(er, source_ids)
        if assignments_df.empty:
            log.warning("No deployment history for %s — skipping.", label)
            continue

        since_iso = (
            pd.Timestamp(cfg["since_filter"], tz="UTC").isoformat()
            if cfg.get("since_filter")
            else assignments_df["depStart"].min().isoformat()
        )
        until_iso = pd.Timestamp.now(tz="UTC").isoformat()

        log.info("Fetching observation history for %d units since %s …", len(source_ids), since_iso[:10])
        obs_df = uncached(app.fetch_observation_history)(
            er, source_ids, since_iso, until_iso, cfg["battery_unit"]
        )
        n_reporting = obs_df["source_id"].nunique()
        log.info("  %d observations from %d of %d units", len(obs_df), n_reporting, len(source_ids))
        if obs_df.empty:
            # app.py drops per-unit fetch errors silently, so an empty frame usually
            # means every request failed (auth/network) rather than "no data".
            log.warning("No observations returned for %s — skipping.", label)
            continue

        deactivation_notes = uncached(app.fetch_deactivation_notes)(er, source_ids)

        result = app.analyze_manufacturer(
            label, cfg, sources_df, assignments_df, obs_df, deactivation_notes,
            country_region_map, subject_metadata,
        )
        del obs_df
        gc.collect()

        if result is None:
            log.warning("No usable data for %s — skipping.", label)
            continue
        s = result["summary"]
        log.info("  %d units, %d active, mean fix rate %.2f",
                 len(s), int((s["status"] == "Active").sum()), result["overall_mean_fix_rate"])
        results.append(result)

    if not results:
        raise RuntimeError("No data available for any device type — nothing to report.")
    return results


def headline_lines(results: list[dict]) -> list[str]:
    lines = []
    for r in results:
        s = r["summary"]
        lines.append(
            f"- {r['label']}: {len(s)} units ({int((s['status'] == 'Active').sum())} active), "
            f"mean fix rate {r['overall_mean_fix_rate']:.2f}, "
            f"{r['excellent']} excellent / {r['good']} good / {r['poor']} poor"
        )
    return lines


def docx_to_pdf(docx_path: Path) -> Path:
    """Convert with LibreOffice. Uses the system python (which has the `uno`
    bindings) so the TOC can be updated; falls back to a plain conversion."""
    pdf_path = docx_path.with_suffix(".pdf")
    system_python = shutil.which("python3", path="/usr/bin") or "python3"
    try:
        subprocess.run([system_python, str(PDF_CONVERTER), str(docx_path), str(pdf_path)],
                       check=True, timeout=300)
    except Exception as e:  # noqa: BLE001 — any failure → simpler conversion
        log.warning("UNO conversion failed (%s); falling back to soffice --convert-to.", e)
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
            check=True, timeout=300,
        )
    if not pdf_path.exists():
        raise RuntimeError(f"PDF conversion produced no file at {pdf_path}")
    return pdf_path


# ─── Email ──────────────────────────────────────────────────────────────────

def recipients() -> list[str]:
    raw = os.environ.get("REPORT_RECIPIENTS", "")
    out = [a.strip() for a in raw.replace(";", ",").split(",") if a.strip()]
    if not out:
        raise RuntimeError("REPORT_RECIPIENTS is empty — set it as a repository secret.")
    return out


def send_email(subject: str, body: str, attachments: list[Path] | None = None) -> None:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ["SMTP_USER"]
    to = recipients()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"GCF Twiga Tools <{user}>"
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    for path in attachments or []:
        if path.suffix == ".pdf":
            maintype, subtype = "application", "pdf"
        else:
            maintype, subtype = "application", "vnd.openxmlformats-officedocument.wordprocessingml.document"
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)

    with smtplib.SMTP_SSL(host, port, timeout=60) as smtp:
        smtp.login(user, os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)
    log.info("Emailed %s to %s", subject, ", ".join(to))


# ─── Entry points ───────────────────────────────────────────────────────────

def run(args) -> int:
    report_date = date.fromisoformat(args.report_date) if args.report_date else date.today()
    quarter = previous_quarter(report_date)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    app = load_app_module()
    if not getattr(app, "HAS_LIFELINES", True):
        log.warning("lifelines is not installed — the Kaplan-Meier survival chart will be left out.")
    er = connect_earthranger()
    results = generate_results(app, er)

    comments = {label: "" for label in app.MANUFACTURERS}
    docx_bytes = app.build_docx(args.author, report_date, results, comments)
    docx_path = out_dir / f"GCF_unitPerformance_{report_date.strftime('%y%m%d')}.docx"
    docx_path.write_bytes(docx_bytes.getvalue() if hasattr(docx_bytes, "getvalue") else docx_bytes)
    log.info("Wrote %s", docx_path)

    pdf_path = docx_to_pdf(docx_path)
    log.info("Wrote %s", pdf_path)

    if args.no_email:
        log.info("--no-email set; not sending.")
        return 0

    body = "\n".join([
        f"Hi,",
        "",
        f"Attached is the GPS unit performance report for {quarter_text(quarter)} "
        f"(cumulative since each programme's first deployment, data to {report_date:%d %B %Y}).",
        "",
        "Headlines:",
        *headline_lines(results),
        "",
        "The PDF is the final version; the .docx is attached too if you want to edit it "
        "(open it in Google Docs and add any general comments to the Overall Assessment sections).",
        "",
        "— Generated automatically by the Twiga Tools unit_performance_report workflow.",
    ])
    send_email(f"GPS unit performance report — {quarter_text(quarter)}", body, [pdf_path, docx_path])
    return 0


def notify_failure(args) -> int:
    run_url = os.environ.get("RUN_URL", "(see the GitHub Actions tab)")
    send_email(
        "⚠️ GPS unit performance report failed",
        "The scheduled unit performance report did not complete.\n\n"
        f"Run log: {run_url}\n\n"
        "Fix the problem and start it again from Actions → Quarterly Unit Performance Report → Run workflow.",
    )
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Streamlit warns loudly when its decorators are imported without a server running.
    logging.getLogger("streamlit").setLevel(logging.ERROR)

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--author", default=DEFAULT_AUTHOR)
    ap.add_argument("--out-dir", default="unit_performance_out")
    ap.add_argument("--no-email", action="store_true", help="build the files but don't send them")
    ap.add_argument("--notify-failure", action="store_true", help="send only the failure alert email")
    args = ap.parse_args()

    return notify_failure(args) if args.notify_failure else run(args)


if __name__ == "__main__":
    sys.exit(main())
