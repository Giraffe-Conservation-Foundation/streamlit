import streamlit as st
import pandas as pd
from datetime import datetime
from ecoscope.io.earthranger import EarthRangerIO
from pandas import json_normalize



# # get subjects, text
# def get_subjects_for_group(group_name):
#     er = EarthRangerIO(
#         server="https://twiga.pamdas.org",
#         username=username,
#         password=password
#     )
#     subjects_df = er.get_subjects(group_name=group_name, include_inactive=True)
#     return subjects_df
# group_name = "AGO_Iona_giraffe"  # Replace with your actual group name
# subjects_df = get_subjects_for_group(group_name)
# print(subjects_df.columns)
# 
# # get groups, test
# def get_subject_groups():
# er = EarthRangerIO(
# server="https://twiga.pamdas.org",
# username=username,
# password=password
# )
# groups = er._get("subjectgroups/", include_inactive=False, flat=True)
# return groups


#### ER AUTHENTICATION #########################################################
def er_login(username, password):
    try:
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        er.get_subjects(limit=1)
        return True
    except Exception:
        return False

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "password" not in st.session_state:
    st.session_state["password"] = ""

if not st.session_state["authenticated"]:
    st.title("Login to EarthRanger Dashboard")
    username = st.text_input("EarthRanger Username")
    password = st.text_input("EarthRanger Password", type="password")
    if st.button("Login"):
        if er_login(username, password):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.session_state["password"] = password
            st.success("Login successful!")
            st.experimental_rerun()
        else:
            st.error("Invalid credentials. Please try again.")
    st.stop()

username = st.session_state["username"]
password = st.session_state["password"]

#### GET SUBJECT GROUPS ########################################################
def get_subject_groups():
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    groups = er._get("subjectgroups/", include_inactive=False, flat=True)
    return groups

groups = get_subject_groups()
df_groups = pd.DataFrame(groups)



# Sidebar: select subject group by name
exclude_patterns = ["AF_giraffe", "AF_livestock", "people", "AF_other", "New_subjects", "Adopt", "Donor", "MOZ_MWA", "NUST", "Movebank", "Interface", "Ishaqbini", "WildscapeVet", "geofence", "cattle", "kudu", "buffalo", "topi", "kob", "tiang", "rhino", "wildebeest", "elephant", "eland", "oryx", "zebra", "springbok", "roan", "sable", "lion"]
pattern = "|".join(exclude_patterns)
df_groups = df_groups[~df_groups["name"].str.contains(pattern, case=False, na=False)]
st.sidebar.header("Select Subject Group")
group_names = df_groups["name"].sort_values().tolist()
selected_group_name = st.sidebar.selectbox("Subject Group", group_names, key="group_select")

# Get the group ID for the selected group name
selected_group_id = df_groups[df_groups["name"] == selected_group_name]["id"].iloc[0]

# Get subjects for selected group
def get_subjects_for_group(group_id):
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    subjects_df = er.get_subjects(subject_group_id=group_id, include_inactive=True)
    return subjects_df

subjects_df = get_subjects_for_group(selected_group_id)

# Second filter: select individual subject (NOW after subjects_df is updated)
subject_names = subjects_df["name"].sort_values().tolist()
selected_subject_name = st.sidebar.selectbox("Select Individual", subject_names, key="subject_select")

# Filter the DataFrame for the selected individual
individual_df = subjects_df[subjects_df["name"] == selected_subject_name]



#### GET SUBJECTS FOR SELECTED GROUP ###########################################
def get_subjects_for_group(group_id):
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    subjects_df = er.get_subjects(subject_group_id=group_id, include_inactive=True)
    return subjects_df

subjects_df = get_subjects_for_group(selected_group_id)

# Filter for wildlife/giraffe only
subjects_df = subjects_df[
    (subjects_df["subject_type"] == "wildlife") &
    (subjects_df["subject_subtype"] == "giraffe")
]



#### SHOW SUBJECT NAMES TABLE ##################################################
st.title(f"Subjects in Group: {selected_group_name}")
if "name" in subjects_df.columns and not subjects_df.empty:
    st.dataframe(subjects_df[["name"]], use_container_width=True)
else:
    st.write("No subject names found for this group.")

# Show details for the selected individual
st.subheader(f"Details for: {selected_subject_name}")
if not individual_df.empty:
    st.dataframe(individual_df, use_container_width=True)
else:
    st.write("No data found for this individual.")



# 
# ## -- events add on // works stand alone, but id != name for subjects, needs to match up
# username = "CMarneweck"
# password="ViewGiraffe123"
# subject_id = "99e731f9-d063-4b56-a9ed-b5190956cad9"
# 
# def load_data():
#     er = EarthRangerIO(
#         server="https://twiga.pamdas.org",
#         username=username,
#         password=password
#     )
#     event_cat = "veterinary"
#     event_type = "immob"
#     since = "2025-01-01T00:00:00Z"
#     until = "2025-07-29T23:59:59Z"
# 
#     events = er.get_events(
#         event_category=event_cat,
#         since=since,
#         until=until,
#         include_details=True,
#         include_notes=False
#     )
# 
#     return events
# events = load_data()
# events_df = json_normalize(events.to_dict(orient="records"))
# print(events_df.columns)
# events_for_giraffe = events_df[events_df["event_details.giraffe_id"] == subject_id]
# columns_to_show = {
#     "event_dttm": "time",
#     "event_type": "event_type",
#     "event_category": "event_category",
#     "event_serial": "serial_number",
#     "event_url": "url",
#     "event_lat": "location.latitude", 
#     "event_lon": "location.longitude",
#     "giraffe_id": "event_details.giraffe_id",
#     "giraffe_age": "event_details.immob_age",
#     "giraffe_sex": "event_details.immob_sex",
#     "gps_tags": "event_details.gps_tags"
# }
# table_df = events_for_giraffe.loc[:, columns_to_show.keys()].rename(columns=columns_to_show)
# 
# ## --


























# #### DATA LOADING ##############################################################
# @st.cache_data(ttl=3600)
# def load_all_events():
#     er = EarthRangerIO(
#         server="https://twiga.pamdas.org",
#         username=username,
#         password=password
#     )
#     # Get all events (you may want to filter by date or category for performance)
#     events = er.get_events(
#         since="2024-01-01T00:00:00Z",
#         until="2025-12-31T23:59:59Z",
#         include_details=True,
#         include_notes=True
#     )
#     flat = json_normalize(events.to_dict(orient="records"))
#     return flat
# 
# df = load_all_events()
# 
# # Standardize giraffe ID column (adjust if needed)
# giraffe_id_col = "giraffe_id" if "giraffe_id" in df.columns else "event_details.giraffe_id"
# if giraffe_id_col not in df.columns:
#     st.error("No giraffe ID column found in event data.")
#     st.stop()
# 
# df["evt_dttm"] = pd.to_datetime(df.get("time", df.get("evt_dttm", None)), errors="coerce")
# df = df.dropna(subset=["evt_dttm"])
# 
# #### SIDEBAR: SELECT GIRAFFE ID ################################################
# st.sidebar.header("Select Giraffe ID")
# giraffe_ids = sorted(df[giraffe_id_col].dropna().unique())
# selected_id = st.sidebar.selectbox("Giraffe ID", giraffe_ids)
# 
# #### FILTER EVENTS FOR SELECTED ID #############################################
# events_for_id = df[df[giraffe_id_col] == selected_id].copy()
# events_for_id = events_for_id.sort_values("evt_dttm", ascending=False)
# 
# #### DASHBOARD #################################################################
# st.title(f"🦒 All Events for Giraffe ID: {selected_id}")
# 
# # Show summary metrics
# st.metric("Total events", len(events_for_id))
# event_types = events_for_id["event_type"].value_counts()
# st.write("**Event type breakdown:**")
# st.dataframe(event_types)
# 
# # Show timeline of events
# st.subheader("Event Timeline")
# timeline_df = events_for_id[["evt_dttm", "event_type", "event_category", "reported_by.name", "location.latitude", "location.longitude"]]
# st.dataframe(timeline_df, use_container_width=True)
# 
# # Show map of events (if location available)
# st.subheader("Event Locations")
# map_df = events_for_id.dropna(subset=["location.latitude", "location.longitude"])
# if not map_df.empty:
#     st.map(map_df[["location.latitude", "location.longitude"]])
# else:
#     st.info("No location data for events.")
# 
# # Show details for immobilisation, mortality, etc.
# st.subheader("Detailed Event Records")
# for evt_type in ["immobilisation", "mortality"]:
#     evt_df = events_for_id[events_for_id["event_type"].str.contains(evt_type, case=False, na=False)]
#     if not evt_df.empty:
#         st.write(f"**{evt_type.capitalize()} Events:**")
#         st.dataframe(evt_df, use_container_width=True)
# 
# # Optionally, show all raw event details
# with st.expander("Show all raw event details"):
#     st.dataframe(events_for_id, use_container_width=True)
