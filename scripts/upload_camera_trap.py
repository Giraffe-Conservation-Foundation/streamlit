#!/usr/bin/env python3
"""
GCF Camera Trap Upload — Low-bandwidth field script
====================================================
Point the script at a month collection folder, e.g.:
    D:\\NAM\\EHGR\\camera_trap\\camera_fence\\202604

It reads every Station/Camera subfolder inside, renames images using
their EXIF datetime, reorganises them into a clean local folder for
TrapTagger, and uploads to Google Cloud Storage.

LOCAL OUTPUT (alongside the input month folder):
    202604_renamed/
        202604/          ← images whose EXIF date falls in April 2026
            S001/
                S001_C002/
                    NAM_EHGR_S001_C002_20260412_IMAG0013.JPG
                    NAM_EHGR_S001_C002_20260418_IMAG0047.JPG
        202605/          ← images whose EXIF date falls in May 2026
            S001/
                S001_C002/
                    NAM_EHGR_S001_C002_20260501_IMAG0001.JPG

GCS UPLOAD:
    gs://gcf_nam_ehgr/camera_trap/camera_fence/202604/S001/S001_C002/

FILENAME FORMAT:
    {COUNTRY}_{SITE}_{STATION}_{CAMERA}_{YYYYMMDD}_{original_stem}.{EXT}
    e.g. NAM_EHGR_S001_C002_20260412_IMAG0013.JPG

    The original filename stem is preserved, making each file uniquely
    traceable back to the camera card. Safe to run on a second batch
    for the same camera — already-uploaded files are skipped (-n flag).

BATCHING:
    - Run on batch 1 in May  → uploads 202605/ photos
    - Run on batch 2 in June → new 202606/ photos upload fine;
      any remaining 202605/ photos that already exist are skipped (-n flag)

USAGE:
    python upload_camera_trap.py
    python upload_camera_trap.py "D:\\NAM\\EHGR\\camera_trap\\camera_fence\\202604"

REQUIREMENTS:
    pip install Pillow
    gcloud auth login
    gcloud config set project gcf-camera-traps

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EDIT THIS SECTION to add your known station / camera folder names
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Hardcoded site ────────────────────────────────────────────────────────────
COUNTRY = "NAM"
SITE    = "EHGR"

# ── Camera map ────────────────────────────────────────────────────────────────
# Maps every known folder name to (station_id, camera_id).
# Matching is case-insensitive and treats spaces and underscores as the same.
# Multiple keys can map to the same camera (add aliases on extra lines).
# To add a new camera, add a new line following the same pattern.

CAMERA_STATION_MAP = {
    # ── Waterhole cameras ─────────────────────────────────────────────────────
    "Site1_Gruisgat_north":                   ("S001", "C001"),
    "Site1_Gruisgat_south":                   ("S001", "C002"),
    "Site2_Middlepos_Hide":                   ("S002", "C003"),
    "Site3_Mopaniepos_Elephantpath":          ("S003", "C004"),
    "Site3_Mopaniepos_Islandcamera":          ("S003", "C005"),
    "Site3_Mopaniepos_Treecamera":            ("S003", "C006"),
    "Site4_Boesmanspoel_Trough":              ("S004", "C007"),
    "Site5_Mountain_Lodge_MLtrough":          ("S005", "C008"),
    "Site6_Bergpos_Stump":                    ("S006", "C009"),
    "Site7_Boma_Rooipos_hide":                ("S007", "C010"),
    "Site7_Boma_Rooipos_mopane":              ("S007", "C011"),
    "Site7_Boma_Rooipos_south":               ("S007", "C012"),
    "Site8_Nuwepos_Tree":                     ("S008", "C013"),
    "Site9_Grootrante":                       ("S009", "C014"),
    "Site10_Madala_north":                    ("S010", "C015"),
    "Site10_Madala_south":                    ("S010", "C016"),
    "Site11_Bergwater_water":                 ("S011", "C017"),
    "Site11_Bergwater_stump":                 ("S011", "C018"),
    "Site12_Tankpos_tree":                    ("S012", "C019"),
    "Site12_Tankpos_tank":                    ("S012", "C020"),
    "Site13_Grenswag_northeast":              ("S013", "C021"),
    "Site13_Grenswag_northwest":              ("S013", "C022"),
    "Site14_Olifantspos_southfacing":         ("S014", "C023"),
    "Site15_Oupos_Tree":                      ("S026", "C038"),
    "Site15_Oupos_Pole":                      ("S026", "C039"),
    "Site16_Vlakwater_Light":                 ("S027", "C040"),
    "Site16_Vlakwater_Pump":                  ("S027", "C041"),
    "Site17_Leeuslootdam":                    ("S028", "C042"),
    "Site18_Gronddam_LR_Imberbe":             ("S029", "C043"),
    "Site18_Gronddam_LR_Mopane":              ("S029", "C044"),
    "Site19_Leeurante":                       ("S030", "C045"),
    "Site20_Moesoemoeroep_Pole":              ("S031", "C046"),
    "Site20_Moesoemoeroep_Tree":              ("S031", "C047"),
    "Site21_Dadelpos_Stump":                  ("S032", "C048"),
    "Site21_Dadelpos_Tree":                   ("S032", "C049"),
    # ── Fence cameras ─────────────────────────────────────────────────────────
    "Site15_WitgatEH001":                     ("S015", "C024"),
    "EH001 Witgat":                           ("S015", "C024"),  # alias
    "Site16_SafarihoekEH003":                 ("S016", "C025"),
    "EH003 N of Safarihoek":                  ("S016", "C025"),  # alias
    "Site17_FlamingoPanEH004":                ("S017", "C026"),
    "EH004 Flamingo Pan":                     ("S017", "C026"),  # alias
    "Site18_UitspuitSouthernBoundaryEH005":   ("S018", "C027"),
    "Site19_MopaniepanCorner EH006":          ("S019", "C028"),
    # ── Greater Etosha grid cameras ───────────────────────────────────────────
    "Site20_CT64":                            ("S020", "C029"),
    "Site21_CT75":                            ("S021", "C030"),
    "Site22_CT86":                            ("S022", "C031"),
    "Site23_CT97":                            ("S023", "C032"),
    "Site24_CT108":                           ("S024", "C033"),
    "Site25_CT119":                           ("S025", "C034"),
}

# Camera ID replacements keyed by (original_camera_id, effective_from_date_str "YYYYMMDD").
# Applied per image based on EXIF date, so a single folder can straddle a changeover date.
CAMERA_ID_OVERRIDES: dict[tuple[str, str], str] = {
    ("C034", "20260520"): "C050",  # Site25_CT119: physical unit replaced 2026-05-20
}

CAMERA_TYPES = {"camera_fence", "camera_water", "camera_grid"}
IMAGE_EXTS   = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# ─────────────────────────────────────────────────────────────────────────────

import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Resolved at startup by check_dependencies()
_GSUTIL_BIN: str = "gsutil"


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_dependencies() -> None:
    global _GSUTIL_BIN
    # On Windows, gsutil is installed as a .cmd wrapper; try both names.
    gsutil_path = shutil.which("gsutil") or shutil.which("gsutil.cmd")
    if gsutil_path is None:
        print()
        print("  !! Something is missing on this computer.")
        print()
        print("  The upload tool (gsutil) could not be found.")
        print("  Please ask your IT contact or Courtney to install the")
        print("  Google Cloud SDK before running this script.")
        print()
        print("  Install guide: https://cloud.google.com/sdk/docs/install")
        print("  After installing, run these two commands once:")
        print("    gcloud auth login")
        print("    gcloud config set project gcf-camera-traps")
        print()
        input("  Press Enter to close.")
        sys.exit(1)
    _GSUTIL_BIN = gsutil_path
    try:
        import PIL  # noqa: F401
    except ImportError:
        print()
        print("  !! Something is missing on this computer.")
        print()
        print("  The image-reading library (Pillow) is not installed.")
        print("  Please ask your IT contact or Courtney to run this command:")
        print("    pip install Pillow")
        print()
        input("  Press Enter to close.")
        sys.exit(1)


def prompt(label: str, default: str = None) -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {label}{suffix}: ").strip()
    return val or default or ""


def _normalise(name: str) -> str:
    """Lowercase and treat spaces/underscores as the same for fuzzy matching."""
    return name.strip().lower().replace(" ", "_")


def resolve_station_camera(folder_name: str) -> tuple[str, str, bool]:
    """
    Return (station_id, camera_id, was_mapped).
    Looks up CAMERA_STATION_MAP with normalised key; returns a fallback if not found.
    """
    key = _normalise(folder_name)
    for map_key, (station, camera) in CAMERA_STATION_MAP.items():
        if _normalise(map_key) == key:
            return station, camera, True
    # Not in map — make a best-guess from the folder name so the script can
    # still run, but flag it clearly so the user knows to add it to the map.
    digits = re.findall(r"\d+", folder_name)
    station = f"S{int(digits[0]):03d}" if digits else "S000"
    camera  = f"C{int(digits[-1]):03d}" if len(digits) > 1 else "C001"
    return station, camera, False


def apply_camera_id_override(camera_id: str, date_str: str) -> str:
    """Return the effective camera ID for a given image date string (YYYYMMDD).

    Checks CAMERA_ID_OVERRIDES: if this camera_id has a replacement that became
    effective on or before the image date, the new ID is returned instead.
    """
    for (old_id, from_date), new_id in CAMERA_ID_OVERRIDES.items():
        if camera_id == old_id and date_str >= from_date:
            return new_id
    return camera_id


def get_exif_datetime(path: Path) -> datetime | None:
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        with Image.open(path) as img:
            exif = img._getexif()
            if not exif:
                return None
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) == "DateTimeOriginal":
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def auto_detect_from_path(p: Path) -> dict:
    """
    Detect camera_type and input_yyyymm from the folder path.
    Country and site are hardcoded (NAM / EHGR).
    """
    parts_lower = [part.lower() for part in p.parts]

    camera_type = next((ct for ct in CAMERA_TYPES if ct in parts_lower), None)

    input_yyyymm = None
    for part in reversed(p.parts):
        if re.fullmatch(r"\d{6}", part):
            input_yyyymm = part
            break

    return {"camera_type": camera_type, "input_yyyymm": input_yyyymm}


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:

    print()
    print("=" * 60)
    print("   GCF Camera Trap Upload")
    print("   Giraffe Conservation Foundation")
    print("=" * 60)
    print()
    print("  Hello! This tool will:")
    print("  1. Find all the camera trap photos in your folder")
    print("  2. Rename them to the GCF standard file naming format")
    print("  3. Sort them into tidy folders ready for TrapTagger")
    print("  4. Upload them to Google Cloud Storage")
    print()
    print("  Your ORIGINAL photos will NOT be moved or deleted.")
    print("  The renamed copies go into a NEW folder alongside your originals.")
    print()
    print("  If anything looks wrong at any point, you can type N and")
    print("  press Enter to stop safely — nothing will have been changed.")
    print()
    input("  Press Enter to begin...")

    # ── Check tools are installed ─────────────────────────────────────────────
    print()
    print("  Checking that everything needed is installed on this computer...")
    check_dependencies()
    print("  All good — tools are ready.")

    # ── 1. Input folder ───────────────────────────────────────────────────────
    print()
    print("─" * 60)
    print("  STEP 1 OF 5 — Tell me which folder to process")
    print("─" * 60)
    print()
    print("  Please enter the full path to your camera trap month folder.")
    print("  This is the folder that contains all the station subfolders")
    print("  for one collection period.")
    print()
    print("  Example:  D:\\NAM\\EHGR\\camera_trap\\camera_fence\\202604")
    print()

    if len(sys.argv) > 1:
        input_folder = Path(sys.argv[1])
        print(f"  Folder provided: {sys.argv[1]}")
    else:
        raw = input("  Folder path: ").strip()
        input_folder = Path(raw) if raw else Path(".")

    input_folder = input_folder.resolve()

    if not input_folder.is_dir():
        print()
        print("  !! That folder could not be found.")
        print(f"     Path entered: {input_folder}")
        print()
        print("  Please check the path and try again.")
        print("  Tip: You can copy the path from the address bar in File Explorer.")
        print()
        input("  Press Enter to close.")
        sys.exit(1)

    print()
    print(f"  Found it!  Working with folder: {input_folder}")

    # ── 2. Auto-detect config from path ──────────────────────────────────────
    print()
    print("─" * 60)
    print("  STEP 2 OF 5 — Identifying the site and camera type")
    print("─" * 60)
    print()
    print("  Reading the folder path to work out the country, site,")
    print("  and camera trap type automatically...")
    print()

    detected    = auto_detect_from_path(input_folder)
    camera_type = detected["camera_type"]
    input_month = detected["input_yyyymm"]

    print(f"  OK  Country        {COUNTRY}  (fixed)")
    print(f"  OK  Site           {SITE}  (fixed)")

    for label, val in [("Camera type", camera_type), ("Month", input_month)]:
        if val:
            print(f"  OK  {label:<14}  {val}")
        else:
            print(f"  --  {label:<14}  (could not detect — will ask below)")

    if not camera_type:
        print()
        print("  Which type of camera trap is this?")
        print("    1.  Fence cameras")
        print("    2.  Water point cameras")
        print("    3.  Grid cameras")
        print()
        choice = prompt("  Type the number and press Enter", default="1")
        camera_type = {"1": "camera_fence", "2": "camera_water", "3": "camera_grid"}.get(choice, "camera_fence")
        print(f"  Selected: {camera_type}")

    if not input_month:
        print()
        print("  What month is this batch from? (used as a fallback date for any")
        print("  photos where the camera date could not be read)")
        input_month = prompt("  Month (YYYYMM, e.g. 202604)", default=datetime.now().strftime("%Y%m"))

    fallback_date = datetime.strptime(input_month + "01", "%Y%m%d")

    print()
    print("  Confirmed:")
    print(f"    Country:      {COUNTRY}")
    print(f"    Site:         {SITE}")
    print(f"    Camera type:  {camera_type}")
    print(f"    Batch month:  {input_month}")

    # ── 3. Discover station / camera folders ──────────────────────────────────
    print()
    print("─" * 60)
    print("  STEP 3 OF 5 — Scanning for cameras and photos")
    print("─" * 60)
    print()
    print("  Looking through the folder for station and camera subfolders...")
    print()

    cameras_found = []
    unmapped      = []

    for top_dir in sorted(d for d in input_folder.iterdir() if d.is_dir()):
        # Each top-level folder is one camera entry.
        # Images may be nested inside DCIM/100xxx/ etc — find them recursively.
        images = sorted(
            f for f in top_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS
        )
        if not images:
            continue

        station_id, camera_id, mapped = resolve_station_camera(top_dir.name)
        cameras_found.append({
            "folder":     top_dir,
            "station_id": station_id,
            "camera_id":  camera_id,
            "images":     images,
            "mapped":     mapped,
        })
        if not mapped:
            unmapped.append(top_dir.name)

    if not cameras_found:
        print("  !! No photos were found in any station/camera subfolders.")
        print()
        print(f"     Folder searched: {input_folder}")
        print()
        print("  Please check that:")
        print("  - You entered the correct folder path (the month folder)")
        print("  - The folder contains station subfolders with camera subfolders inside")
        print("  - The photos are JPG, PNG, or TIF files")
        print()
        input("  Press Enter to close.")
        sys.exit(1)

    total_images = sum(len(c["images"]) for c in cameras_found)

    print(f"  Found {len(cameras_found)} camera(s) with {total_images} photos total.")
    print()
    print("  Here is what was found and how each folder will be named:")
    print()
    print(f"  {'Folder name':<45}  {'Station / Camera':<16}  {'Photos':>6}  {'Note'}")
    print("  " + "─" * 82)
    for c in cameras_found:
        parsed = f"{c['station_id']} / {c['camera_id']}"
        note   = "name list" if c["mapped"] else "⚠ not in list — guessed"
        print(f"  {c['folder'].name:<45}  {parsed:<16}  {len(c['images']):>6}  {note}")

    if unmapped:
        print()
        unique_unmapped = sorted(set(unmapped))
        print("  NOTE: The following folder names were not in the name list,")
        print("  so the ID was guessed from the digits in the folder name.")
        print("  Please check the table above to make sure the IDs look right.")
        print("  If any are wrong, please contact Courtney to update the name list.")
        print()
        for name in unique_unmapped:
            print(f"    Folder not in name list:  {name}")

    # ── 4. Preview and confirm ────────────────────────────────────────────────
    print()
    print("─" * 60)
    print("  STEP 4 OF 5 — Review and confirm before anything is changed")
    print("─" * 60)

    output_root = input_folder.parent / (input_folder.name + "_renamed")
    bucket      = f"gcf_{COUNTRY.lower()}_{SITE.lower()}"

    print()
    print("  Here is a summary of what is about to happen:")
    print()
    print(f"  Photos found in:  {input_folder}")
    print(f"  ({total_images} photos across {len(cameras_found)} camera(s))")
    print()
    print("  STEP A — Renamed copies will be created here (originals untouched):")
    print(f"    {output_root}")
    print(f"    Organised as: YYYYMM / Station / Station_Camera / photo.JPG")
    print()
    print("  STEP B — Photos will be uploaded to Google Cloud:")
    print(f"    Bucket:  gs://{bucket}")
    print(f"    Path:    camera_trap / {camera_type} / YYYYMM / Station / Station_Camera /")
    print()
    print("  Each photo will be renamed using the date and time it was taken")
    print(f"  (read from the photo itself). Any photos without a date will use")
    print(f"  {fallback_date.strftime('%B %Y')} as a fallback.")
    print()
    print("  Example filename:  "
          f"{COUNTRY}_{SITE}_S001_C002_{input_month}15_IMAG0013.JPG")
    print()
    print("  If you run this script again later with more photos from the same")
    print("  cameras, any photos already uploaded will be skipped automatically.")
    print()

    confirm = input("  Does this look right? Type Y and press Enter to continue, or N to cancel:  ").strip().lower()
    if confirm != "y":
        print()
        print("  Cancelled. Nothing has been changed.")
        print()
        input("  Press Enter to close.")
        sys.exit(0)

    # ── 5. Rename and copy locally ────────────────────────────────────────────
    print()
    print("─" * 60)
    print("  STEP 5A OF 5 — Renaming and organising photos on this computer")
    print("─" * 60)
    print()
    print("  Creating renamed copies now. This may take a few minutes")
    print("  depending on how many photos there are. Please wait...")
    print()

    output_root.mkdir(exist_ok=True)
    no_exif_count = 0
    gcs_manifest: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for cam in cameras_found:
        station_id = cam["station_id"]
        camera_id  = cam["camera_id"]  # base ID from CAMERA_STATION_MAP
        print(f"  Processing camera:  {cam['folder'].name}  →  {station_id}/{camera_id}  ({len(cam['images'])} photos)")

        for img_path in cam["images"]:
            exif_dt = get_exif_datetime(img_path)
            if exif_dt:
                date_str = exif_dt.strftime("%Y%m%d")
            else:
                date_str = fallback_date.strftime("%Y%m%d")
                no_exif_count += 1

            # Apply any date-based camera ID replacement (e.g. physical unit swapped).
            # Images before the override date keep the original ID; images on/after get
            # the new ID.  Both halves land in their own station_cam subfolder.
            effective_camera_id = apply_camera_id_override(camera_id, date_str)
            station_cam = f"{station_id}_{effective_camera_id}"

            month_folder = date_str[:6]
            ext          = img_path.suffix.upper()
            orig_stem    = img_path.stem.upper()
            final_name   = f"{COUNTRY}_{SITE}_{station_id}_{effective_camera_id}_{date_str}_{orig_stem}{ext}"

            out_dir = output_root / month_folder / station_id / station_cam
            out_dir.mkdir(parents=True, exist_ok=True)
            dest = out_dir / final_name
            shutil.copy2(img_path, dest)
            gcs_manifest[month_folder][station_id][station_cam].append(dest)

    renamed_total = sum(
        len(files)
        for months in gcs_manifest.values()
        for stations in months.values()
        for files in stations.values()
    )
    months_found = sorted(gcs_manifest.keys())

    print()
    print(f"  Done!  {renamed_total} photos renamed and organised.")
    print()

    if no_exif_count:
        print(f"  NOTE: {no_exif_count} photo(s) did not have a date stored inside them.")
        print(f"  These were given the fallback date of {fallback_date.strftime('%B %Y')}.")
        print()

    if len(months_found) > 1:
        print(f"  The photos were sorted into {len(months_found)} different month folders")
        print("  based on when each photo was actually taken:")
        for m in months_found:
            count = sum(
                len(files)
                for stations in gcs_manifest[m].values()
                for files in stations.values()
            )
            label = datetime.strptime(m + "01", "%Y%m%d").strftime("%B %Y")
            print(f"    {label} ({m}):  {count} photos")
        print()

    print(f"  Your TrapTagger folder is ready here:")
    print(f"    {output_root}")
    print()
    print("  You can use this folder to upload to TrapTagger now if you like.")

    # ── 6. Upload via gsutil ──────────────────────────────────────────────────
    print()
    print("─" * 60)
    print("  STEP 5B OF 5 — Upload to Google Cloud Storage")
    print("─" * 60)
    print()
    print("  Before uploading, please review the month folders listed above.")
    print()
    print("  If any dates look wrong — for example, a camera whose clock was")
    print("  not set correctly — type N now to skip the upload. You can move")
    print("  those photos to the correct month folder in:")
    print(f"    {output_root}")
    print("  and then run the script again (already-uploaded photos are skipped).")
    print()

    confirm_upload = input("  Ready to upload to Google Cloud? (Y/N):  ").strip().lower()
    if confirm_upload != "y":
        print()
        print("  Upload skipped.")
        print("  Your renamed TrapTagger folder is complete and ready to use.")
        print("  Run this script again on the same folder when you are ready to upload.")
        print()
        input("  Press Enter to close.")
        sys.exit(0)

    print()
    print("  Starting upload. This may take a while on a slow connection.")
    print("  If the connection drops, just run this script again —")
    print("  photos already uploaded will be skipped automatically.")
    print()
    print("  Do NOT close this window until you see the final summary.")
    print()

    any_failed     = False
    total_uploaded = 0

    for month_folder in sorted(gcs_manifest):
        month_label = datetime.strptime(month_folder + "01", "%Y%m%d").strftime("%B %Y")
        print(f"  Uploading {month_label} photos...")
        for station_id in sorted(gcs_manifest[month_folder]):
            for station_cam, file_list in sorted(gcs_manifest[month_folder][station_id].items()):
                gcs_dest = (
                    f"gs://{bucket}/camera_trap/{camera_type}"
                    f"/{month_folder}/{station_id}/{station_cam}/"
                )
                print(f"    {station_cam}:  {len(file_list)} photos  →  cloud")
                result = subprocess.run(
                    [_GSUTIL_BIN, "-m", "cp", "-n"]
                    + [str(f) for f in file_list]
                    + [gcs_dest],
                    shell=(sys.platform == "win32"),
                )
                if result.returncode == 0:
                    total_uploaded += len(file_list)
                    print(f"    {station_cam}:  uploaded successfully")
                else:
                    print()
                    print(f"    !! Upload failed for {station_cam}.")
                    print(f"       This sometimes happens due to a connection problem.")
                    print(f"       Re-run the script on the same folder to try again.")
                    any_failed = True

    print()
    print("=" * 60)
    if not any_failed:
        print("  ALL DONE!")
        print()
        print(f"  {renamed_total} photos renamed on this computer.")
        print(f"  {total_uploaded} photos uploaded to Google Cloud.")
        print()
        print("  Renamed folder for TrapTagger:")
        print(f"    {output_root}")
        print()
        print("  Google Cloud location:")
        print(f"    gs://{bucket}/camera_trap/{camera_type}/")
        print()
        print("  You can close this window.")
    else:
        print("  UPLOAD INCOMPLETE")
        print()
        print("  Some photos could not be uploaded due to a connection problem.")
        print("  Your renamed folder on this computer is complete and fine.")
        print()
        print("  To retry the upload, simply run this script again on the same folder.")
        print("  Photos that were already uploaded successfully will be skipped.")
        print()
        print("  If the problem keeps happening, please contact Courtney.")
    print("=" * 60)
    print()
    input("  Press Enter to close.")


if __name__ == "__main__":
    main()
