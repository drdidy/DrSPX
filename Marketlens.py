# ==============================  PART 1 — CORE SHELL (DAILY, FALLBACK-SAFE)  ==============================
# Beautiful enterprise shell • Open sidebar • Yahoo Finance daily candles
# Live banner shows today's daily if available, else last completed session (no dashes)
# Overnight (manual) inputs captured now — used by Parts 2+

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# ───────────────────────────────  GLOBAL CONFIG  ───────────────────────────────
APP_NAME   = "MarketLens Pro"
TAGLINE    = "Enterprise SPX & Equities Forecasting"
VERSION    = "5.0"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Symbols (you can expand later)
SYMBOLS = {
    "SPX (S&P 500 Index)": "^GSPC",
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "NVDA": "NVDA",
    "AMZN": "AMZN",
    "GOOGL": "GOOGL",
    "META": "META",
    "NFLX": "NFLX",
    "TSLA": "TSLA",
}

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — Daily",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS  ───────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
.stApp { background: radial-gradient(1200px 600px at 10% -10%, #f8fbff 0%, #ffffff 35%) no-repeat fixed; }

/* Hero */
.hero {
  border-radius: 26px;
  padding: 22px 24px 26px 24px;
  border: 1px solid rgba(0,0,0,0.06);
  background: linear-gradient(145deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 18px 44px rgba(99,102,241,.28), inset 0 1px 0 rgba(255,255,255,.18);
}
.hero h1 { margin: 0; font-weight: 900; font-size: 28px; letter-spacing: -0.02em; }
.hero .sub { margin-top: 2px; opacity: .96; font-weight: 600; }
.hero .meta { margin-top: 6px; opacity: .85; font-size: 12px; }

/* 3D KPI cards */
.kpi { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 16px; }
.kpi .card {
  background: rgba(255,255,255,.14);
  border: 1px solid rgba(255,255,255,.28);
  backdrop-filter: blur(6px);
  border-radius: 18px;
  padding: 14px 16px;
  box-shadow:
    0 10px 25px rgba(2,6,23,.18),
    inset 0 1px 0 rgba(255,255,255,.35);
}
.kpi .label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; opacity: .9; font-weight: 800; }
.kpi .value { margin-top: 6px; font-weight: 900; font-size: 22px; letter-spacing: -0.02em; }

/* Section */
.sec { margin-top: 18px; border-radius: 20px; padding: 18px; background: #fff; border: 1px solid rgba(0,0,0,0.06);
       box-shadow: 0 16px 34px rgba(2,6,23,.08); }
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

/* Sidebar */
section[data-testid="stSidebar"] {
  background: #0b1220 !important; color: #e5e7eb; border-right: 1px solid rgba(255,255,255,.06);
}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label { color: #e5e7eb !important; }
.sidebar-card { background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12); border-radius: 14px; padding: 12px; margin: 10px 0; }

/* Chips */
.chip { display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; font-weight:800; font-size:12px; }
.chip.info { background:#eef2ff; color:#312e81; border:1px solid #6366f133; }
.chip.ok { background:#ecfdf5; color:#065f46; border:1px solid #10b98133; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  YF DAILY FETCH (FALLBACK SAFE)  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_daily_last(symbol: str) -> dict:
    """
    Return last *available* daily candle for symbol (close & date).
    If today's candle isn't present, falls back to the most recent completed session.
    """
    try:
        df = yf.download(symbol, period="3mo", interval="1d", auto_adjust=False, progress=False, threads=True)
        if df is None or df.empty or "Close" not in df.columns:
            return {"px": "—", "as_of": "—", "note": "No data"}
        df = df.dropna(subset=["Close"])
        if df.empty:
            return {"px": "—", "as_of": "—", "note": "No data"}

        # Prefer today if present; otherwise take the last index
        idx = df.index
        last_idx = idx[-1]
        last_date = (last_idx.tz_localize(None).date() if hasattr(last_idx, "tz") else pd.to_datetime(last_idx).date())
        last_close = float(df["Close"].iloc[-1])

        # If Yahoo has a partial "today" row but it's NaN it would be dropped already. So we just use the last.
        return {
            "px": f"{last_close:,.2f}",
            "as_of": last_date.strftime("%a %b %d, %Y"),
            "note": "Last available daily",
        }
    except Exception:
        return {"px": "—", "as_of": "—", "note": "Error"}

# ───────────────────────────────  SIDEBAR — NAV, ASSET, OVERNIGHT INPUTS  ───────────────────────────────
with st.sidebar:
    st.markdown("### 📚 Navigation")
    page = st.radio("", ["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"], index=0, label_visibility="collapsed")

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🎯 Asset")
    asset_label = st.selectbox("Choose instrument", list(SYMBOLS.keys()), index=0)
    symbol = SYMBOLS[asset_label]
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input("Target session (for later analytics)", value=date.today())
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual)")
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Price between 5:00 PM and 7:00 AM ET.")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0))
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00)
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30))
    st.caption("These feed the Overnight logic in later parts.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + KPI  ───────────────────────────────
last = yf_fetch_daily_last(symbol)

st.markdown(f"""
<div class="hero">
  <h1>{APP_NAME}</h1>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="card">
      <div class="label">{asset_label} — Last Daily Close</div>
      <div class="value">{last['px']}</div>
    </div>
    <div class="card">
      <div class="label">As of</div>
      <div class="value">{last['as_of']}</div>
    </div>
    <div class="card">
      <div class="label">Session (selected)</div>
      <div class="value">{forecast_date.strftime('%a %b %d, %Y')}</div>
    </div>
    <div class="card">
      <div class="label">Engine</div>
      <div class="value">Yahoo Finance • Daily</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────  OVERVIEW  ───────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)
    st.markdown(
        """
        <span class="chip ok">Daily price ready</span>
        <span class="chip info">Prev-day anchors & entry tables arrive in Part 2+</span>
        <span class="chip info">Overnight inputs captured</span>
        """,
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDERS (WILL LIGHT UP LATER)  ───────────────────────────────
if page in {"Anchors","Forecasts","Signals","Contracts","Fibonacci","Export","Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section activates in the next parts with your full intraday strategy, tables and charts.")
    st.markdown('</div>', unsafe_allow_html=True)