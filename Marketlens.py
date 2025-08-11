# ==============================  PART 1 — CORE SHELL + LIVE SPX + ANCHOR INPUTS  ==============================
# Enterprise UI, always-open sidebar, SPX from Yahoo Finance, hidden slope engine, overnight inputs (price+time)
# --------------------------------------------------------------------------------------------------------------
# Drop this in your main file (e.g., MarketLens.py). It runs on its own — no other parts needed yet.

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

# ───────────────────────────────  GLOBAL CONFIG  ───────────────────────────────
APP_NAME   = "MarketLens Pro"
TAGLINE    = "Enterprise SPX & Equities Forecasting"
VERSION    = "5.0"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Market hours (SPX cash) in ET → converted in code as needed
RTH_START_ET, RTH_END_ET = time(9, 30), time(16, 0)
RTH_START_CT, RTH_END_CT = time(8, 30), time(15, 0)

# SPX core slopes (per 30-minute block) — WORKS IN BACKGROUND (not shown in UI)
# Previous-day anchors (descending from H/C/L; mirror ascending for TP)
SPX_SLOPES = {
    "prev_high_down": -0.2792,
    "prev_close_down": -0.2792,
    "prev_low_down": -0.2792,
    "tp_mirror_up": +0.2792,
}
# Overnight anchors (user inputs): low uses ascending; high uses descending
SPX_OVERNIGHT_SLOPES = {
    "overnight_low_up": +0.2792,
    "overnight_high_down": -0.2792,
}

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — SPX",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS (Clean, Bold, Product-Ready)  ───────────────────────────────
st.markdown("""
<style>
/* Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

/* App background */
.stApp { 
  background: radial-gradient(1200px 600px at 10% -10%, #f8fbff 0%, #ffffff 35%) no-repeat fixed;
}

/* Hide Streamlit chrome */
#MainMenu { display: none !important; }  /* header no longer hidden */

/* Brand Hero */
.hero {
  border-radius: 24px;
  padding: 22px 24px;
  border: 1px solid rgba(0,0,0,0.06);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 12px 30px rgba(99,102,241,0.25);
}
.hero .title { font-weight: 800; font-size: 26px; letter-spacing: -0.02em; }
.hero .sub { opacity: 0.95; font-weight: 500; }
.hero .meta { opacity: 0.8; font-size: 13px; margin-top: 4px; }

/* KPI strip */
.kpi {
  display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 14px;
}
.kpi .card {
  border-radius: 16px; padding: 14px 16px;
  background: white; border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 4px 16px rgba(2,6,23,0.05);
}
.kpi .label { color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.kpi .value { font-weight: 800; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }

/* Section */
.sec { margin-top: 18px; border-radius: 20px; padding: 18px; background: white; border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 8px 30px rgba(2,6,23,0.05); }
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 800; letter-spacing: -0.01em; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }

/* Sidebar polish */
section[data-testid="stSidebar"] {
  background: #0b1220 !important;
  color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] .css-1cypcdb { color: #e5e7eb !important; }
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 { color: #e5e7eb !important; }
.sidebar-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px 12px; margin: 10px 0;
}

/* Chips */
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(0,0,0,0.08); background:#f8fafc; font-size:12px; font-weight:700; color:#0f172a;
}
.chip.ok { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }

/* Table wrapper */
.table-wrap {
  border-radius: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 8px 24px rgba(2,6,23,0.05);
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS: YF FETCH + DATES  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_intraday_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ...