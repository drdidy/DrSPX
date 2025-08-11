# ==============================  PART 1 — CORE SHELL + PREMIUM UI + YF FALLBACK  ==============================
# Bold, enterprise styling • Always-open sidebar • SPX + 8 stocks • Live banner with 1m→daily fallback
# --------------------------------------------------------------------------------------------------------------
# Drop this in your main file (e.g., MarketLens.py). It runs by itself.

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

# Instrument universe (you can add later)
INSTRUMENTS = {
    "SPX (S&P 500 Index)": "^GSPC",
    "AAPL — Apple": "AAPL",
    "MSFT — Microsoft": "MSFT",
    "AMZN — Amazon": "AMZN",
    "GOOGL — Alphabet": "GOOGL",
    "META — Meta": "META",
    "NVDA — NVIDIA": "NVDA",
    "TSLA — Tesla": "TSLA",
    "NFLX — Netflix": "NFLX",
}

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS (Bold, 3D, Uniform Fonts)  ───────────────────────────────
st.markdown(r"""
<style>
/* Typography */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

/* App background */
.stApp {
  background: radial-gradient(1200px 700px at 10% -10%, #f5f8ff 0%, #ffffff 40%) fixed;
}

/* Keep native Streamlit header visible (you asked to keep it) */

/* Hero (3D card) */
.hero {
  border-radius: 22px;
  padding: 20px 22px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow:
    0 14px 30px rgba(99, 102, 241, 0.28),
    inset 0 1px 0 rgba(255,255,255,0.25);
}
.hero .title { font-weight: 900; font-size: 26px; letter-spacing: -0.02em; }
.hero .sub { opacity: 0.95; font-weight: 600; }
.hero .meta { opacity: 0.85; font-size: 13px; margin-top: 4px; }

/* KPI cards — glossy, 3D */
.kpi {
  display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 14px;
}
.kpi .card {
  border-radius: 16px; padding: 14px 16px;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0.9) 100%),
    #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow:
    0 10px 24px rgba(2,6,23,0.08),
    inset 0 1px 0 rgba(255,255,255,0.6);
  backdrop-filter: blur(6px);
}
.kpi .label { color: #64748b; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
.kpi .value { font-weight: 900; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }

/* Sections */
.sec {
  margin-top: 18px; border-radius: 18px; padding: 18px;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.6) 0%, rgba(255,255,255,0.95) 100%),
    #ffffff;
  border: 1px solid rgba(15,23,42,0.08);
  box-shadow: 0 12px 28px rgba(2,6,23,0.08), inset 0 1px 0 rgba(255,255,255,0.6);
}
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

/* Sidebar (sleek dark) */
section[data-testid="stSidebar"] {
  background: #0b1220 !important;
  color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
.sidebar-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px 12px; margin: 10px 0;
}
.sidebar-card h4 { margin: 0 0 6px 0; font-weight: 800; color: #f3f4f6; }

/* Chips */
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(15, 23, 42, 0.08); background:#f8fafc; font-size:12px; font-weight:800; color:#0f172a;
}
.chip.ok { background:#ecfdf5; border-color:#10b98130; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f130; color:#312e81; }

/* Table wrapper */
.table-wrap {
  border-radius: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 10px 26px rgba(2,6,23,0.08);
}

/* Buttons */
.stButton > button, .stDownloadButton > button {
  border-radius: 14px !important;
  border: 1px solid rgba(15,23,42,0.1) !important;
  background: linear-gradient(180deg, #0ea5e9 0%, #6366f1 100%) !important;
  color: #fff !important; font-weight: 800 !important;
  box-shadow: 0 10px 20px rgba(99,102,241,0.25), inset 0 1px 0 rgba(255,255,255,0.3) !important;
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS: YF FETCH + FALLBACK  ───────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def yf_fetch_intraday_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Pull up to last 7 days 1-minute bars from Yahoo and filter locally by time range.
    Returns columns: Dt (tz-aware CT), Open/High/Low/Close.
    """
    try:
        df = yf.download(
            symbol,
            interval="1m",
            period="7d",
            auto_adjust=False,
            progress=False,
            prepost=True,
            threads=True,
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        df = df.reset_index()
        # Normalize datetime column
        if "Datetime" in df.columns:
            df.rename(columns={"Datetime":"Dt"}, inplace=True)
        elif "index" in df.columns:
            df.rename(columns={"index":"Dt"}, inplace=True)
        else:
            # yfinance sometimes returns plain index as datetime
            df.rename(columns={df.columns[0]:"Dt"}, inplace=True)

        df["Dt"] = pd.to_datetime(df["Dt"], utc=True).dt.tz_convert(ET).dt.tz_convert(CT)
        cols = [c for c in ["Open","High","Low","Close"] if c in df.columns]
        out = df[["Dt"] + cols].dropna(subset=cols)
        mask = (out["Dt"] >= start_dt) & (out["Dt"] <= end_dt)
        return out.loc[mask].sort_values("Dt").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

@st.cache_data(ttl=600, show_spinner=False)
def yf_fetch_recent_daily_close(symbol: str) -> tuple[str,str] | None:
    """
    Fallback: pull up to 14 days of daily candles and return last close + date.
    Returns (price_str, date_str) or None.
    """
    try:
        df = yf.download(symbol, interval="1d", period="14d", auto_adjust=False, progress=False, threads=True)
        if df is None or df.empty:
            return None
        last = df.dropna(subset=["Close"]).iloc[-1]
        px = f"{float(last['Close']):,.2f}"
        dt = last.name
        if not isinstance(dt, pd.Timestamp):
            return (px, "—")
        dt = pd.to_datetime(dt).tz_localize("UTC").tz_convert(ET)
        ds = dt.strftime("%a %b %d")
        return (px, f"{ds} (Daily Close)")
    except Exception:
        return None

def get_last_with_fallback(symbol: str) -> dict:
    """
    Try intraday 1m last; if empty, fall back to most recent daily close.
    Returns {"px": str, "ts": str, "source": "1m"|"1d"}.
    """
    try:
        end_ct = datetime.now(tz=CT)
        start_ct = end_ct - timedelta(hours=8)
        m1 = yf_fetch_intraday_1m(symbol, start_ct, end_ct)
        if not m1.empty:
            last = m1.iloc[-1]
            return {"px": f"{float(last['Close']):,.2f}", "ts": last["Dt"].strftime("%-I:%M %p CT"), "source": "1m"}
        # fallback: daily close
        daily = yf_fetch_recent_daily_close(symbol)
        if daily:
            px, ds = daily
            return {"px": px, "ts": ds, "source": "1d"}
        return {"px": "—", "ts": "—", "source": "none"}
    except Exception:
        return {"px": "—", "ts": "—", "source": "error"}

# ───────────────────────────────  SIDEBAR — NAV + SESSION + OVERNIGHT INPUTS  ───────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-card"><h4>📚 Navigation</h4>', unsafe_allow_html=True)
    page = st.radio(
        label="",
        options=["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
        index=0,
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><h4>📊 Instrument</h4>', unsafe_allow_html=True)
    chosen_label = st.selectbox("Select", list(INSTRUMENTS.keys()), index=0, label_visibility="collapsed")
    SYMBOL = INSTRUMENTS[chosen_label]
    st.caption(f"Data source: Yahoo Finance • {chosen_label}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><h4>📅 Session</h4>', unsafe_allow_html=True)
    forecast_date = st.date_input("Target session", value=date.today())
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><h4>🌙 Overnight Anchors (Manual)</h4>', unsafe_allow_html=True)
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Enter the overnight swing LOW price.")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Time between 5:00 PM and 7:00 AM ET.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Enter the overnight swing HIGH price.")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Time between 5:00 PM and 7:00 AM ET.")
    st.caption("Tip: Overnight entries light up later; inputs are saved immediately.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE BANNER  ───────────────────────────────
last = get_last_with_fallback(SYMBOL)
source_chip = '<span class="chip ok">Yahoo • 1m</span>' if last["source"] == "1m" else (
              '<span class="chip info">Yahoo • Daily Close</span>' if last["source"] == "1d" else
              '<span class="chip info">Awaiting data</span>')

st.markdown(f"""
<div class="hero">
  <div class="title">{APP_NAME}</div>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="card">
      <div class="label">{chosen_label} — Last</div>
      <div class="value">{last['px']}</div>
    </div>
    <div class="card">
      <div class="label">As of</div>
      <div class="value">{last['ts']}</div>
    </div>
    <div class="card">
      <div class="label">Session</div>
      <div class="value">{forecast_date.strftime('%a %b %d, %Y')}</div>
    </div>
    <div class="card">
      <div class="label">Engine</div>
      <div class="value">{source_chip}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────  OVERVIEW (CLEAN; HEAVY LOGIC COMES IN PART 2+)  ───────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
            <span class="chip ok">Live price ready</span>
            <span class="chip info">Prev-day anchors & entries load in Part 2+</span>
            <span class="chip info">Overnight inputs captured</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDER PAGES (TO BE FILLED IN PARTS 2+)  ───────────────────────────────
if page in {"Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section lights up in the next parts with your full strategy, premium tables, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)