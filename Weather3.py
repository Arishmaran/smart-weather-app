import requests
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from prophet import Prophet
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import base64
import json

# ----------------------------
# Auto-refresh every 30 mins
# ----------------------------
st_autorefresh(interval=30*60*1000, key="auto_refresh")  # 30 minutes

# ----------------------------
# GitHub config for Community Reports
# ----------------------------
GITHUB_USER = st.secrets["GITHUB_USER"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
JSON_PATH = "reports.json"  # path in repo
IMAGES_FOLDER = "images"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

AUTHORIZED_ADMINS = ["admin1@example.com", "admin2@example.com"]  # <-- change this to your emails

# ----------------------------
# Session state
# ----------------------------
if "role" not in st.session_state:
    st.session_state.role = None
if "user" not in st.session_state:
    st.session_state.user = None

# ----------------------------
# Helper functions for GitHub
# ----------------------------
def get_reports():
    """Fetch reports.json from GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{JSON_PATH}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        content = r.json()
        file_sha = content.get("sha")
        data = base64.b64decode(content.get("content", "")).decode()
        if not data.strip():
            return [], file_sha  # empty file, return empty list
        try:
            return json.loads(data), file_sha
        except json.JSONDecodeError:
            return [], file_sha  # corrupted content, return empty list
    else:
        return [], None  # file does not exist yet

def update_reports(new_report):
    # Upload image first
    file_name = f"{IMAGES_FOLDER}/{int(datetime.now().timestamp())}_{new_report['image_file'].name}"
    file_bytes = new_report['image_file'].getvalue()
    encoded_image = base64.b64encode(file_bytes).decode()
    url_upload = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{file_name}"
    r = requests.put(url_upload, headers=HEADERS, json={
        "message": f"Upload image {file_name}",
        "content": encoded_image
    })
    if r.status_code not in [200, 201]:
        st.error("Failed to upload image to GitHub")
        st.stop()
    
    image_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{file_name}"
    new_report['image_url'] = image_url
    del new_report['image_file']

    # Update JSON
    reports, sha = get_reports()
    new_report["id"] = max([r.get("id", 0) for r in reports]+[0]) + 1
    new_report["comments"] = []
    new_report["timestamp"] = datetime.now().isoformat()
    reports.append(new_report)

    encoded_json = base64.b64encode(json.dumps(reports, indent=2).encode()).decode()
    url_json = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{JSON_PATH}"
    r2 = requests.put(url_json, headers=HEADERS, json={
        "message": "Update reports.json",
        "content": encoded_json,
        "sha": sha
    })
    if r2.status_code not in [200, 201]:
        st.error("Failed to update reports.json")
        st.stop()

# ----------------------------
# Weather & Flood Predictor functions
# ----------------------------
def fetch_weather(latitude, longitude):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=temperature_2m,rain&timezone=Asia/Kolkata"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return None

def fetch_historical_weather(latitude, longitude, days_back=14):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    delta = timedelta(days=7)
    all_times, all_rain = [], []
    current_start = start_date
    while current_start < end_date:
        current_end = min(current_start + delta, end_date)
        url = (f"https



