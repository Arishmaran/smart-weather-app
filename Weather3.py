import requests
import streamlit as st
import json
import base64
from datetime import datetime

# ----------------------------
# Session state for login
# ----------------------------
if "role" not in st.session_state:
    st.session_state.role = None
if "user" not in st.session_state:
    st.session_state.user = None

# ----------------------------
# GitHub config for Community Reports
# ----------------------------
GITHUB_TOKEN = st.secrets["github"]["token"]
REPO_OWNER = st.secrets["github"]["repo_owner"]
REPO_NAME = st.secrets["github"]["repo_name"]

JSON_PATH = "reports.json"
IMAGES_FOLDER = "images"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# Replace with your real admin emails
AUTHORIZED_ADMINS = ["admin1@example.com", "admin2@example.com"]

# ----------------------------
# Helper functions for GitHub
# ----------------------------
def get_reports():
    """Fetch reports.json from GitHub"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{JSON_PATH}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        content = r.json()
        file_sha = content.get("sha")
        data = base64.b64decode(content.get("content", "")).decode()
        if not data.strip():
            return [], file_sha
        try:
            return json.loads(data), file_sha
        except json.JSONDecodeError:
            return [], file_sha
    else:
        return [], None

def update_reports(new_report):
    """Upload image + update JSON in GitHub"""
    # Upload image
    file_name = f"{IMAGES_FOLDER}/{int(datetime.now().timestamp())}_{new_report['image_file'].name}"
    file_bytes = new_report['image_file'].getvalue()
    encoded_image = base64.b64encode(file_bytes).decode()
    url_upload = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_name}"
    r = requests.put(url_upload, headers=HEADERS, json={
        "message": f"Upload image {file_name}",
        "content": encoded_image
    })
    if r.status_code not in [200, 201]:
        st.error("Failed to upload image to GitHub")
        st.stop()

    image_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{file_name}"
    new_report['image_url'] = image_url
    del new_report['image_file']

    # Update JSON
    reports, sha = get_reports()
    new_report["id"] = max([r.get("id", 0) for r in reports] + [0]) + 1
    new_report["comments"] = []
    new_report["timestamp"] = datetime.now().isoformat()
    reports.append(new_report)

    encoded_json = base64.b64encode(json.dumps(reports, indent=2).encode()).decode()
    url_json = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{JSON_PATH}"
    r2 = requests.put(url_json, headers=HEADERS, json={
        "message": "Update reports.json",
        "content": encoded_json,
        "sha": sha
    })
    if r2.status_code not in [200, 201]:
        st.error("Failed to update reports.json")
        st.stop()

# ----------------------------
# Page Setup
# ----------------------------
st.set_page_config(page_title="Weather & Community Dashboard", layout="wide")
st.title("🌦️ Weather & Community Dashboard")

# ----------------------------
# Login
# ----------------------------
if st.session_state.role is None:
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
    # ----------------------------
    # Dashboard Navigation
    # ----------------------------
    st.sidebar.success(f"Logged in as {st.session_state.role}: {st.session_state.user}")
    if st.sidebar.button("Logout"):
        st.session_state.role = None
        st.session_state.user = None
        st.rerun()

    dashboard_type = st.sidebar.radio("Select Dashboard", ["Citizen", "Admin", "Community"])

    # ----------------------------
    # Citizen Dashboard
    # ----------------------------
    if dashboard_type == "Citizen":
        st.header("🌍 Citizen Weather Dashboard")
        st.info("Citizen-specific features (weather, local alerts, etc.) will go here.")

    # ----------------------------
    # Admin Dashboard
    # ----------------------------
    elif dashboard_type == "Admin":
        st.header("🛠️ Admin Dashboard")
        st.info("Admin-specific features (aggregated risks, analytics, etc.) will go here.")

    # ----------------------------
    # Community Dashboard
    # ----------------------------
    else:
        st.header("📸 Community Weather Reports")

        st.subheader("Post a New Report")
        with st.form("report_form"):
            caption = st.text_area("Add a caption about current weather")
            uploaded_img = st.file_uploader("Upload an image", type=["jpg","jpeg","png"])
            submitted = st.form_submit_button("Post Report")
            if submitted:
                if not caption or not uploaded_img:
                    st.error("Please fill all fields and upload an image")
                else:
                    new_report = {
                        "name": st.session_state.user,
                        "caption": caption.strip(),
                        "image_file": uploaded_img
                    }
                    update_reports(new_report)
                    st.success("✅ Report posted successfully!")
                    st.rerun()

        st.markdown("---")
        st.subheader("All Community Reports")
        reports, sha = get_reports()

        if reports:
            for report in sorted(reports, key=lambda x: x["timestamp"], reverse=True):
                st.image(report["image_url"], use_container_width=True)
                st.write(f"**{report['name']}**: {report['caption']}")
                st.write(f"_Posted at {report['timestamp']}_")

                # Delete post: Admins can delete any, Citizens only their own
                if st.session_state.role == "Admin" or st.session_state.user == report["name"]:
                    if st.button("Delete Post", key=f"delpost_{report['id']}"):
                        reports = [r for r in reports if r["id"] != report["id"]]
                        encoded_json = base64.b64encode(json.dumps(reports, indent=2).encode()).decode()
                        url_json = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{JSON_PATH}"
                        r2 = requests.put(url_json, headers=HEADERS, json={
                            "message": f"Delete report {report['id']}",
                            "content": encoded_json,
                            "sha": sha
                        })
                        if r2.status_code in [200, 201]:
                            st.success("✅ Post deleted successfully")
                            st.rerun()
                        else:
                            st.error("Failed to delete post")

                # Show comments
                if report.get("comments"):
                    st.write("💬 Comments:")
                    for idx, c in enumerate(report["comments"]):
                        st.write(f"- {c}")
                        comment_owner = c.split(":")[0].strip()
                        if st.session_state.role == "Admin" or st.session_state.user == comment_owner:
                            if st.button("Delete Comment", key=f"delcomment_{report['id']}_{idx}"):
                                report["comments"].pop(idx)
                                encoded_json = base64.b64encode(json.dumps(reports, indent=2).encode()).decode()
                                url_json = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{JSON_PATH}"
                                r2 = requests.put(url_json, headers=HEADERS, json={
                                    "message": f"Delete comment {idx} on report {report['id']}",
                                    "content": encoded_json,
                                    "sha": sha
                                })
                                if r2.status_code in [200, 201]:
                                    st.success("✅ Comment deleted")
                                    st.rerun()
                                else:
                                    st.error("Failed to delete comment")

                # Add new comment
                with st.form(f"comment_form_{report['id']}"):
                    comment_text = st.text_input("Add a comment", key=f"comment_text_{report['id']}")
                    comment_submitted = st.form_submit_button("Post Comment")
                    if comment_submitted:
                        if not comment_text:
                            st.error("Enter a comment")
                        else:
                            report.setdefault("comments", []).append(f"{st.session_state.user}: {comment_text.strip()}")
                            encoded_json = base64.b64encode(json.dumps(reports, indent=2).encode()).decode()
                            url_json = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{JSON_PATH}"
                            r2 = requests.put(url_json, headers=HEADERS, json={
                                "message": f"Add comment on report {report['id']}",
                                "content": encoded_json,
                                "sha": sha
                            })
                            if r2.status_code in [200, 201]:
                                st.success("✅ Comment posted")
                                st.rerun()
                            else:
                                st.error("Failed to post comment")
        else:
            st.info("No reports yet. Be the first to post!")




