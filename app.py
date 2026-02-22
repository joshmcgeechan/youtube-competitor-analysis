"""Streamlit web UI for YouTube Competitor Analysis."""

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent / ".env")

# Add execution/ to path so pipeline imports work
sys.path.insert(0, str(Path(__file__).resolve().parent / "execution"))

from pipeline import run_pipeline

st.set_page_config(
    page_title="YouTube Competitor Analysis",
    page_icon="📊",
    layout="centered",
)

st.title("YouTube Competitor Analysis")
st.caption("Generate a Google Slides report comparing your channel against competitors.")


# --- Password gate ---
def check_password() -> bool:
    """Simple password check using APP_PASSWORD secret."""
    app_password = os.getenv("APP_PASSWORD")
    if not app_password:
        try:
            app_password = st.secrets.get("APP_PASSWORD", "")
        except FileNotFoundError:
            app_password = ""
    if not app_password:
        st.error("APP_PASSWORD not configured. Set it in .env or Streamlit secrets.")
        return False

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    password = st.text_input("Password", type="password", placeholder="Enter password")
    if st.button("Login"):
        if password == app_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()

# --- Main form ---
st.divider()

channel = st.text_input(
    "Your Channel",
    placeholder="@handle",
    help="Your YouTube channel's @handle",
)

competitors_text = st.text_area(
    "Competitor Channels (one per line)",
    placeholder="@competitor1\n@competitor2\n@competitor3\n@competitor4",
    help="Enter 4-7 competitor @handles, one per line",
    height=150,
)

days = st.number_input(
    "Analysis Window (days)",
    min_value=7,
    max_value=365,
    value=60,
    help="How many days of recent videos to analyze",
)

if st.button("Generate Report", type="primary", use_container_width=True):
    # Validate inputs
    if not channel.strip():
        st.error("Please enter your channel handle.")
        st.stop()

    competitors = [
        line.strip() for line in competitors_text.strip().splitlines() if line.strip()
    ]

    if len(competitors) < 4:
        st.error(f"Need at least 4 competitors, got {len(competitors)}.")
        st.stop()
    if len(competitors) > 7:
        st.error(f"Max 7 competitors, got {len(competitors)}.")
        st.stop()

    # Run pipeline
    with st.status("Running analysis...", expanded=True) as status:
        report_url = None
        error_occurred = False

        for event in run_pipeline(
            channel=channel.strip(),
            competitors=competitors,
            days=days,
            server_mode=True,
        ):
            if event["type"] == "progress":
                st.write(event["message"])
            elif event["type"] == "error":
                status.update(label="Error", state="error")
                st.error(event["message"])
                error_occurred = True
                break
            elif event["type"] == "result":
                report_url = event.get("report_url")
                summary = event.get("summary", {})

        if not error_occurred:
            status.update(label="Complete!", state="complete")

    if report_url:
        st.success("Report generated successfully!")
        st.markdown(f"### [Open Google Slides Report]({report_url})")
        st.caption(f"Channels analyzed: {summary.get('channels_fetched', '?')} | "
                   f"Videos: {summary.get('total_videos', '?')} | "
                   f"Quota: ~{summary.get('quota_estimate', '?')} units")
    elif not error_occurred:
        st.warning("Pipeline completed but no Slides report was generated. "
                   "Check that GOOGLE_SLIDES_TEMPLATE_ID is set.")
