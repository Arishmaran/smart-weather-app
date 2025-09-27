import streamlit as st
import requests
import json
import base64
from datetime import datetime, timedelta
from prophet import Prophet
import pandas as pd
import folium
from streamlit_folium import st_folium

# ========================
# GITHUB SETTINGS
# ========================
GITHUB_TOKEN = st.secrets["github"]["token"]
REPO_OWNER = st.secrets["github"]["repo_owner"]
REPO_NAME = st.secrets["github"]["repo_name"]
REPORTS_FILE = "reports.json"

AUTHORIZED_ADMINS = ["admin1@example.com", "admin2@example.com"]  # <-- change these


# ========================
# GITHUB HELPERS
# ========================
def github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }


def get_reports():
    """Fetch reports.json from GitHub"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{REPORTS_FILE}"
    response = requests.get(url, headers=github_headers())
    if response.status_code == 200:
        content = response.json()
        data = base64.b64decode(content["content"]).decode("utf-8")
        return json.loads(data), content["sha"]
    return [], None


def update_reports(reports, sha):
    """Update reports.json in GitHub"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{REPORTS_FILE}"
    encoded_content = base64.b64encode(json.dumps(reports, indent=2).encode()).decode()
    message = "Update community reports"
    response = requests.put(url, headers=github_headers(), json={
        "message": message,
        "content": encoded_content,
        "sha": sha
    })
    return response.status_code == 200 or response.status_code == 201


def save_image_to_github(image_file, filename):
    """Save uploaded image to GitHub"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{filename}"
    file_bytes = image_file.getvalue()
    encoded_content = base64.b64encode(file_bytes).decode()
    response = requests.put(url, headers=github_headers(), json={
        "message": f"Upload {filename}",
        "content": encoded_content
    })
    if response.status_code in (200, 201):
        return response.json()["content"]["download_url"]
    return None


# ========================
# WEATHER & FLOOD PREDICTION
# ========================
def get_weather_data(lat, lon):
    """Fetch historical and forecast weather data from Open-Meteo"""
    now = datetime.utcnow()
    past = now - timedelta(days=5)
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,precipitation,rain,showers"
        f"&start_date={past.strftime('%Y-%m-%d')}"
        f"&end_date={now.strftime('%Y-%m-%d')}"
    )
    return requests.get(url).json()


def predict_rainfall(weather_data):
    """Use Prophet to forecast rainfall"""
    df = pd.DataFrame({
        "ds": pd.to_datetime(weather_data["hourly"]["time"]),
        "y": weather_data["hourly"]["rain"]
    })

    model = Prophet(daily_seasonality=True)
    model.fit(df)

    future = model.make_future_dataframe(periods=3, freq="H")
    forecast = model.predict(future)

    avg_rain = forecast["yhat"].iloc[-3:].mean()
    if avg_rain > 20:
        risk = "High"
    elif avg_rain > 10:
        risk = "Medium"
    else:
        risk = "Low"

    return avg_rain, risk


def generate_map(lat, lon, risk):
    """Generate a Folium map with flood risk marker"""
    fmap = folium.Map(location=[lat, lon], zoom_start=10)
    color = "red" if risk == "High" else "orange" if risk == "Medium" else "green"
    folium.Marker(
        [lat, lon],
        popup=f"Flood Risk: {risk}",
        icon=folium.Icon(color=color)
    ).add_to(fmap)
    return fmap


# ========================
# LOGIN SYSTEM
# ========================
if "role" not in st.session_state:
    st.session_state.role = None
if "user" not in st.session_state:
    st.session_state.user = None

st.set_page_config(page_title="Weather & Flood Predictor", layout="wide")

if st.session_state.role is None:
    st.title("🔐 Login Page")

    role_choice = st.radio("Login as:", ["Citizen", "Admin"])

    if role_choice == "Citizen":
        mobile = st.text_input("Enter your mobile number", max_chars=10)
        if st.button("Login as Citizen"):
            if mobile.isdigit() and len(mobile) == 10:
                st.session_state.role = "Citizen"
                st.session_state.user = mobile
                st.success("✅ Logged in as Citizen")
                st.rerun()
            else:
                st.error("Please enter a valid 10-digit mobile number")

    elif role_choice == "Admin":
        email = st.text_input("Enter your Admin email")
        if st.button("Login as Admin"):
            if email in AUTHORIZED_ADMINS:
                st.session_state.role = "Admin"
                st.session_state.user = email
                st.success("✅ Logged in as Admin")
                st.rerun()
            else:
                st.error("❌ Unauthorized email")

else:
    # ========================
    # LOGOUT BUTTON
    # ========================
    with st.sidebar:
        st.markdown(f"👤 Logged in as: **{st.session_state.user}** ({st.session_state.role})")
        if st.button("Logout"):
            st.session_state.role = None
            st.session_state.user = None
            st.rerun()

    # ========================
    # DASHBOARD SELECTION
    # ========================
    dashboard_type = st.sidebar.radio(
        "Choose Dashboard",
        ["Citizen Dashboard", "Admin Dashboard", "Community Dashboard"]
    )

    # Citizen Dashboard
    if dashboard_type == "Citizen Dashboard" and st.session_state.role == "Citizen":
        st.header("🌍 Citizen Weather Alerts")

        lat = st.number_input("Enter Latitude", value=19.0760)
        lon = st.number_input("Enter Longitude", value=72.8777)

        if st.button("Get Forecast"):
            weather_data = get_weather_data(lat, lon)
            avg_rain, risk = predict_rainfall(weather_data)
            st.write(f"📊 Predicted Rainfall: {avg_rain:.2f} mm")
            st.write(f"⚠️ Flood Risk Level: **{risk}**")

            fmap = generate_map(lat, lon, risk)
            st_folium(fmap, width=700, height=500)

    # Admin Dashboard
    elif dashboard_type == "Admin Dashboard" and st.session_state.role == "Admin":
        st.header("🛠️ Admin Risk Reports")

        lat = st.number_input("Enter Latitude", value=19.0760)
        lon = st.number_input("Enter Longitude", value=72.8777)

        if st.button("Analyze Forecast"):
            weather_data = get_weather_data(lat, lon)
            avg_rain, risk = predict_rainfall(weather_data)
            st.write(f"📊 Predicted Rainfall: {avg_rain:.2f} mm")
            st.write(f"⚠️ Flood Risk Level: **{risk}**")

            fmap = generate_map(lat, lon, risk)
            st_folium(fmap, width=700, height=500)

    # Community Dashboard
    elif dashboard_type == "Community Dashboard":
        st.header("🌐 Community Weather Reports")

        reports, sha = get_reports()

        # Add new report
        with st.expander("➕ Add New Report"):
            caption = st.text_area("Caption")
            image_file = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"])
            if st.button("Submit Report"):
                if caption and image_file:
                    img_url = save_image_to_github(image_file, f"images/{image_file.name}")
                    if img_url:
                        new_report = {
                            "user": st.session_state.user,
                            "role": st.session_state.role,
                            "caption": caption,
                            "image": img_url,
                            "time": datetime.utcnow().isoformat(),
                            "comments": []
                        }
                        reports.append(new_report)
                        if update_reports(reports, sha):
                            st.success("✅ Report submitted successfully")
                            st.rerun()
                        else:
                            st.error("❌ Failed to submit report")
                else:
                    st.error("Please add caption and image")

        # Display reports
        st.subheader("📋 Community Reports")
        for idx, r in enumerate(reports):
            st.markdown(f"**{r['user']} ({r['role']})**: {r['caption']}")
            if r.get("image"):
                st.image(r["image"], width=300)
            st.caption(f"🕒 {r['time']}")

            # Show comments
            for c_idx, comment in enumerate(r.get("comments", [])):
                st.write(f"💬 {comment}")

            # Add comment
            new_comment = st.text_input(f"Add comment to report {idx}", key=f"c{idx}")
            if st.button(f"Submit comment {idx}"):
                if new_comment:
                    r["comments"].append(f"{st.session_state.user}: {new_comment}")
                    if update_reports(reports, sha):
                        st.rerun()


