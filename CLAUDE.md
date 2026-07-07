# Twiga Tools — Working Memory

## Project
**Twiga Tools** — GCF (Giraffe Conservation Foundation) multi-page Streamlit conservation platform.
- **Repo:** https://github.com/Giraffe-Conservation-Foundation/streamlit
- **Live app:** https://twiga-tools-gcf.streamlit.app
- **Local path:** `G:\My Drive\Data management\streamlit`
- **Main entry:** `twiga_tools.py` (pages in `pages/` directory)
- **Pattern:** Each page = `pages/{N}_{emoji}_{Name}.py` → imports `{dashboard_dir}/app.py`

## Key Integrations
| Integration | How | Used For |
|---|---|---|
| **EarthRanger** | `ecoscope` → `EarthRangerIO` | Core subject/event data. URL: `twiga.pamdas.org` |
| **Google Cloud Storage** | `google-cloud-storage` | Image storage, standardised naming |
| **Google Sheets** | `gspread` | GPS stock sheet, embargo tracking |
| **Wildbook/GiraffeSpotter** | bulk import CSV | Individual animal ID database |
| **CITES/Species+** | REST API | Giraffe trade monitoring |
| **Google Earth Engine** | `pystac-client` + `planetary-computer` | Habitat/translocation assessment |
| **ArcGIS** | `arcgis<2.3,>=2.1` | Spatial analysis (GAD dashboard) |

## Dashboards (page → module)
| Page | Module | What it does |
|---|---|---|
| GPS Unit Check | `unit_check_dashboard/` | Device health: battery, fixes, provider status. Upload `unit_update` events |
| Unit Performance Report | `unit_performance_dashboard/` | Quarterly SpoorTrack/Savannah/GSat performance report (deployments, battery, fix rate) → downloadable .docx styled like the GCF_unitPerformance Google Doc |
| GPS Data Availability | `gps_availability_dashboard/` | Subject group GPS summary + embargo overlay |
| Post-Tagging Dashboard | `tagging_dashboard/` | First 48h after collar deployment |
| Genetic Dashboard | `genetic_dashboard/` | Biological sample status tracking + bulk event upload |
| Translocation Dashboard | `translocation_dashboard/` | Translocation events + mapping |
| Life History | `life_history_dashboard/` | Full event timeline for any ER subject |
| Mortality Dashboard | `mortality_dashboard/` | Death events tracking |
| Twiga Dash | `twiga_dash/` | Live GPS collar summary for all subjects |
| NANW Dashboard | `nanw_dashboard/` | Namibia West monitoring events |
| ZAF Dashboard | `zaf_dashboard/` | South Africa survey encounters |
| EHGR Dashboard | `ehgr_dashboard/` | East Africa giraffe research |
| Survey Data Upload | `survey_upload/` | Bulk image upload → GCS |
| Camera Trap Upload | `camera_trap_upload/` | Camera trap image batch rename + upload |
| ER2WB Converter | `er2wb_dashboard/` | EarthRanger → Wildbook import formatter |
| SMART2WB Converter | `smart2wb_dashboard/` | SMART patrol → Wildbook import formatter |
| Wildbook ID Generator | `wildbook_id_generator/` | PDF photo ID books from Wildbook exports |
| SECR Analysis | `secr_analysis/` | Population estimation (R + Python) |
| GAD / Translocation Assessment | `gad_dashboard/` | GEE + ArcGIS habitat suitability |
| CITES Trade Database | `cites_dashboard/` | Live CITES trade data for giraffes |
| Publications | `publications/` | Research output tracking |

## EarthRanger Event Schema
| Category | Types | Notes |
|---|---|---|
| `monitoring` | `unit_update` | GPS unit activated/deactivated. Fields: `unitupdate_unitid` (source UUID), `unitupdate_action`, `unitupdate_country`, `unitupdate_subject`, `unitupdate_notes` |
| `monitoring_nam` | `giraffe_survey_encounter_nam` | Namibia survey |
| `monitoring_zaf` | `giraffe_survey_encounter_zaf` | South Africa survey |
| `veterinary` | `giraffe_translocation`, mortality types | Vet interventions |

## GPS Providers
SpoorTrack, Savannah Tracking, Ceres (mapipedia), GSat (gsatsolar), Africa Wildlife Tracking

## Shared Utilities
- `shared/config.py` — GCS bucket config, site options
- `shared/utils.py` — Image processing, standardised filename generation
- `shared/logo.png` + `add_sidebar_logo()` — Consistent branding

## File Naming Conventions
- **Survey images:** `COUNTRY_SITE_YYYYMMDD_INITIALS_ORIGINALNAME.ext`
- **Camera trap:** `COUNTRY_SITE_STATION_CAMERA_YYYYMMDD_ORIGINALNAME.ext`
- **GCS path:** `giraffe_images/{SITE}/{YEAR}/{MONTH}/`

## Secrets (Streamlit Cloud)
`gps_stock_sheet_id`, `embargo_sheet_url` (also nested `[embargo].embargo_sheet_url`),
`gcp_service_account`, `gee_service_account`, EarthRanger credentials

## Memory Index
→ Full details: `C:\Users\court\.claude\projects\G--My-Drive-Data-management-streamlit\memory\`
- `MEMORY.md` — index
- `project_streamlit_app.md` — full app architecture reference
- `project_embargo_tracking.md` — student embargo overlay feature
