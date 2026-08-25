# Site Overview Dashboard — status

Birds-eye "click a protected area, see what we have" module. Design
discussed 2026-08-15: map (folium, `gad_dashboard` pattern) reads a cached
local summary, plus a per-site **on-demand refresh** button for anything
that needs to be current right now.

**Storage: local JSON, not Google Sheets.** Originally designed around a
Sheets backend for team-wide sharing, but Courtney's current need is her own
local planning, not a shared team view — so `local_store.py` reads/writes
plain JSON files in `site_overview_dashboard/data/` instead. Zero new
secrets, zero cloud dependency, works fully offline. `sheet_io.py` is kept
around unused, documented as the Sheets-based version to swap back in if
this ever needs to become a shared/team feature.

## Current state (2026-08-25 — revisited/rebuilt)

Re-enabled in the sidebar (was accidentally disabled 2026-08-25 — see the
comment in `twiga_tools.py` above the page entry). Two real changes this
pass, both from Courtney's request to revisit this:

**1. Canonical site list redesigned.** The map now shows real protected
areas instead of the two `EXAMPLE_*` placeholder rows — `site_crosswalk.json`
was rebuilt from the 94 real EarthRanger `subject_group`s already present in
`data/site_summaries.json` from an earlier live refresh run (real active-
collar counts included). `site_code` is no longer assumed to equal the ER
`subject_group` name — see the redesign note in `site_registry.py`'s module
docstring for why: EarthRanger is now **opt-in per site** via the
crosswalk's `er_subject_group` column, so a site with that blank just shows
no ER stats yet instead of guessing. In this rebuild `er_subject_group`
happens to equal `site_code` for every row (since the source data *was* the
ER list), so ER stats already populate as soon as you refresh.

Each `site_name` is an **automatic cleanup** of the ER group name (e.g.
`KEN_MaraNorth_giraffe` → "Mara North") — spot-check these, especially
acronym-heavy ones (`KEN_WRTIannex_giraffe` → "WRTI Annex" is a guess).
3 non-site ER groups were excluded from the crosswalk: `KAZA_demo_giraffe`
(a demo group), `TwigaTracker_Interface` (a system group), and
`White_Giraffe_Ishaqbini` (an individual, not a place) — add any of them
back manually if you actually want them tracked.

**2. Map now draws real protected-area boundary shapes**, not just points.
New `boundary_lookup.py` + `scripts/refresh_site_boundaries.py` query
OpenStreetMap's free Nominatim search (no API key) for each site's
`boundary_query` and cache the polygon in `data/site_boundaries.json`. The
map draws that polygon when available, falls back to the old AGOL x/y point
marker when not, and lists anything with neither in a "not on the map yet"
expander. **Nobody has run this yet** — `data/site_boundaries.json` doesn't
exist, so right now every site falls back to the AGOL-point path (which
mostly won't have anything either, since `agol_site_field` is also blank for
every site — see below). Run
`python scripts/refresh_site_boundaries.py` locally to populate it
(~2 minutes for all 94 sites, paced to be polite to Nominatim's free
service).

Clicking a shape/marker on the map now actually selects that site in the
detail panel below (via `st_folium`'s click return value), not just the
dropdown.

## What's real vs stubbed (updated 2026-08-25)

Priority this pass, per Courtney: EarthRanger + GAD first; GiraffeSpotter
once API access is confirmed; Zotero and GQueues deprioritized for now
(both still run, just not a focus).

| Source | Status | Notes |
|---|---|---|
| EarthRanger | **Real**, opt-in per site via `er_subject_group` | Two code paths: batch (`site_registry.get_canonical_sites`) for the refresh script; live single-site (`site_profile._fetch_er_summary_live`) for the on-demand button. `er_subject_group` is filled in for all 94 sites in this rebuild (see above) — just needs a refresh run to populate `er_active_collars` etc. from live data (or trust the counts already cached from the prior run). |
| ArcGIS Online / GAD | **Real, but not yet matched** | Reuses `gad_dashboard.load_gad_data()`, filtered by the crosswalk's `agol_site_field` — which is intentionally **blank for every site** right now. Someone needs to open the live GAD data (GAD page → Summary Table) and confirm what each site's `Site`/`Region1`/`Region0` value actually is, then fill in `agol_site_field` per row. |
| Protected-area boundary (map shape) | **Real, not yet fetched** | `boundary_lookup.py` via OpenStreetMap Nominatim, cached in `data/site_boundaries.json` — see "Current state" above. Run `scripts/refresh_site_boundaries.py` once. |
| GiraffeSpotter / Wildbook | **Stub — pending API access** | No existing live-read integration anywhere in this codebase — `er2wb_dashboard` only *writes* Wildbook import CSVs, it doesn't read encounters back. Needs: the Wildbook instance base URL, an API key or session credential with read access, and confirmation that `wildbook_locality` (currently the same auto-cleaned name as `site_name`) matches the real `Encounter.locationID` values GiraffeSpotter uses (see `er2wb_dashboard/app.py` line ~821 for how those get set on upload). |
| Zotero | **Real, deprioritized** | Uses the `[zotero]` credentials already in the local `.streamlit/secrets.toml`. Open question: those secrets define one global collection, not per-site ones, so sites without their own `zotero_collection` in the crosswalk (i.e. all of them right now) will all show the same document count until Zotero is organized per-site. |
| GQueues | **Partial, deprioritized** | `_fetch_gqueues_summary` in `site_profile.py` is NOT wired up — needs someone to confirm `gqueues_dashboard/app.py`'s actual function signatures. Also depends on `gcp_service_account`, which isn't in the local secrets, so it'll fail locally regardless until that's resolved. |

## How to get fully real data

1. **Boundaries (map shapes):** `python scripts/refresh_site_boundaries.py`
   — no login needed, takes a couple of minutes.
2. **EarthRanger + whatever else is wired up:**
   `python scripts/refresh_site_summaries.py --site AGO_Bicuar_giraffe`
   to test one site first (prints the profile without saving), then
   `python scripts/refresh_site_summaries.py` for all 94. Only prompts for
   an EarthRanger login if at least one site has `er_subject_group` set
   (all of them do in this rebuild) — pass `--skip-er` to skip that and
   just refresh AGOL/Zotero.
3. Reload the Streamlit app.
4. From then on, the app's "Refresh this site now" button updates
   `site_summaries.json` directly for just that site (same file, no
   separate sync step). Boundaries rarely change, so there's no on-demand
   boundary refresh — re-run the script if a `boundary_query` changes.
5. To confirm `agol_site_field` per site: open the GAD page's Summary Table,
   find each site's real `Site`/`Region1`/`Region0` value, and fill it into
   `site_crosswalk.json`.

## Known open items

- **`agol_site_field` needs confirming per site** before GAD population
  estimates will show up — see table above.
- **GiraffeSpotter/Wildbook needs real API access** — see table above.
  Courtney: this is the one thing I can't do without you — the base URL and
  an API key/session credential, please.
- **GQueues fetcher** needs real implementation — see the TODO in
  `site_profile.py`. Deprioritized per Courtney (2026-08-25).
- Some `boundary_query` values are short single-word site names (e.g.
  "Abu, Botswana") that may not resolve cleanly on OpenStreetMap, or may
  match the wrong feature — spot-check `data/site_boundaries.json` after
  running the refresh script, especially anywhere the map looks off.
- **`.github/workflows/site_summary_refresh.yml`** is stale relative to this
  local-JSON design (still references Sheets/GCP secrets) — left disabled
  and uncommitted, would need reworking if this becomes a shared/team
  feature later.

## Unrelated but discovered along the way

The EarthRanger monthly backup workflow (`backup_earthranger.yml`) is
currently failing with exit code 143 (SIGTERM), most likely an
out-of-memory kill on the GitHub-hosted runner (7GB RAM) while
downloading/parsing the growing `GCF_twiga_master.csv` during the append
step. Separate problem from this module — pinned for later per Courtney's
instruction (2026-08-15).

## Files

- `local_store.py` — active storage layer: local JSON read/write for summaries, crosswalk, and boundaries
- `sheet_io.py` — unused, kept for reference (the original Sheets-based version)
- `site_registry.py` — crosswalk schema constants + `get_canonical_sites()` (live ER subject_group list, for matching into `er_subject_group`)
- `site_profile.py` — `get_site_profile()`, the one function both the refresh script and the on-demand button call
- `boundary_lookup.py` — OpenStreetMap Nominatim boundary lookup (new 2026-08-25)
- `app.py` — Streamlit page: map (boundary shapes + point fallback) + table + on-demand refresh
- `data/site_summaries.json` — cached per-site summary output (94 real sites, ER stats populated from a prior run)
- `data/site_crosswalk.json` — the 94-site protected-area list + cross-platform mapping (see "Current state" above)
- `data/site_boundaries.json` — cached OpenStreetMap boundary per site (doesn't exist yet — run the refresh script)
- `../pages/26_🗺️_Site_Overview.py` — page wrapper, registered in `twiga_tools.py`'s Home section
- `../scripts/refresh_site_summaries.py` — run locally to populate/refresh EarthRanger + other source data
- `../scripts/refresh_site_boundaries.py` — run locally to populate map boundary shapes (new 2026-08-25)
- `../.github/workflows/site_summary_refresh.yml` — stale/disabled, see above
