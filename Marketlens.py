# ==============================  PART 1 — CORE SHELL (SPX + YF 15m + OVERNIGHT INPUTS)  ==============================
# Enterprise UI, always-open sidebar, SPX from Yahoo Finance (15m), hidden slope engine, overnight inputs (price+time)
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

# SPX regular trading hours (cash index times) in ET
RTH_START_ET, RTH_END_ET = time(9, 30), time(16, 0)

# Core slopes (per 30-minute block) — run entirely in the background
SPX_SLOPES = {
    "prev_high_down": -0.2792,
    "prev_close_down": -0.2792,
    "prev_low_down":  -0.2792,
    "tp_mirror_up":   +0.2792,
}
# Overnight anchors (manual inputs): low ascends, high descends
SPX_OVERNIGHT_SLOPES = {
    "overnight_low_up":  +0.2792,
    "overnight_high_down": -0.2792,
}

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — SPX",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS  ───────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

.stApp { 
  background: radial-gradient(1200px 600px at 10% -10%, #f7fbff 0%, #ffffff 35%) fixed;
}

/* Keep Streamlit header visible (do NOT hide) */
#MainMenu { display:none !important; }

/* Hero */
.hero {
  border-radius: 22px;
  padding: 22px 24px;
  border: 1px solid rgba(0,0,0,0.06);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 24px 48px rgba(99,102,241,0.35);
}
.hero .title { font-weight: 900; font-size: 28px; letter-spacing: -0.02em; }
.hero .sub { opacity: .95; font-weight: 600; margin-top: 2px; }
.hero .meta { opacity: .9; font-size: 12px; margin-top: 6px; }

.kpi { display:grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap:14px; margin-top: 14px; }
.kpi .card {
  border-radius: 14px; padding: 14px 16px;
  background: rgba(255,255,255,.16);
  border: 1px solid rgba(255,255,255,.25);
  backdrop-filter: blur(6px);
  box-shadow: 0 10px 30px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,.4);
}
.kpi .label { opacity:.9; font-size:12px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; }
.kpi .value { font-weight: 900; font-size: 22px; letter-spacing: -0.02em; }

/* Sections */
.sec {
  margin-top: 18px; border-radius: 20px; padding: 18px;
  background: white; border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 18px 36px rgba(2,6,23,0.06);
}
.sec h3 { margin:0 0 8px 0; font-size:18px; font-weight:900; letter-spacing:-.01em; }

/* Sidebar (dark premium) */
section[data-testid="stSidebar"] {
  background: #0b1220 !important; color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] * { color: #e5e7eb !important; }
.sidebar-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px 12px; margin: 10px 0;
}
.help { color:#c7d2fe !important; opacity:.9; font-size:12px; }

/* Chips */
.chips { display:flex; flex-wrap:wrap; gap:8px; }
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(0,0,0,0.08); background:#f8fafc; font-size:12px; font-weight:800; color:#0f172a;
  box-shadow: 0 1px 0 rgba(255,255,255,0.8) inset;
}
.chip.ok { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }

/* Table wrapper */
.table-wrap {
  border-radius: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 12px 30px rgba(2,6,23,0.06);
}

/* Mono */
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS: YF FETCH + FALLBACKS (15m)  ───────────────────────────────
def _clean_index_to_dt(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
    df = df.copy().reset_index()
    # yfinance can label time column "Datetime" or simply use index name
    if "Datetime" in df.columns:
        df.rename(columns={"Datetime":"Dt"}, inplace=True)
    elif "Date" in df.columns:
        df.rename(columns={"Date":"Dt"}, inplace=True)
    elif "index" in df.columns:
        df.rename(columns={"index":"Dt"}, inplace=True)
    if "Dt" not in df.columns:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
    # YF timestamps are UTC → convert to ET then CT for display
    s = pd.to_datetime(df["Dt"], utc=True, errors="coerce")
    df["Dt"] = s.dt.tz_convert(ET).dt.tz_convert(CT)
    keep = [c for c in ["Open","High","Low","Close"] if c in df.columns]
    return df[["Dt"] + keep].dropna(subset=keep).sort_values("Dt")

@st.cache_data(ttl=180, show_spinner=False)
def yf_fetch_intraday_15m(symbol: str, start_ct: datetime, end_ct: datetime) -> pd.DataFrame:
    """
    Fetch 15m bars (preferred) for up to ~60 days. If window ends outside available range,
    we still return all rows and let the caller filter locally.
    """
    try:
        df = yf.download(symbol, interval="15m", period="60d", auto_adjust=False, progress=False, prepost=True, threads=True)
        df = _clean_index_to_dt(df)
        if df.empty: 
            return df
        mask = (df["Dt"] >= start_ct) & (df["Dt"] <= end_ct)
        return df.loc[mask].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

@st.cache_data(ttl=120, show_spinner=False)
def fetch_spx_last_banner() -> dict:
    """
    Returns a dict {px, ts, engine}:
      1) Try last 15m bar within last 7 days
      2) Fallback to last daily close (1d)
    Never returns dashes unless literally nothing is available.
    """
    try:
        now_ct = datetime.now(tz=CT)
        df = yf_fetch_intraday_15m("^GSPC", now_ct - timedelta(days=7), now_ct + timedelta(minutes=1))
        if not df.empty:
            last = df.iloc[-1]
            return {"px": f"{float(last['Close']):,.2f}", "ts": last["Dt"].strftime("%-I:%M %p CT"), "engine": "Yahoo • 15m"}
        # Fallback: last daily close
        d1 = yf.download("^GSPC", interval="1d", period="10d", auto_adjust=False, progress=False)
        d1 = _clean_index_to_dt(d1)
        if not d1.empty:
            last = d1.iloc[-1]
            return {"px": f"{float(last['Close']):,.2f}", "ts": last["Dt"].strftime("Close %a %-m/%-d"), "engine": "Yahoo • 1d fallback"}
        return {"px": "—", "ts": "—", "engine": "Awaiting data"}
    except Exception:
        return {"px": "—", "ts": "—", "engine": "Awaiting data"}

# Previous trading day helper (Mon–Fri)
def previous_trading_day(ref_d: date) -> date:
    d = ref_d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

# ───────────────────────────────  PREV-DAY H/L/C (computed silently, 15m)  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def prev_day_hlc_spx(ref_session: date) -> dict | None:
    """
    Compute Previous-Day High/Low/Close for SPX with 15m bars restricted to cash RTH.
    """
    try:
        prev_d = previous_trading_day(ref_session)
        start_ct = datetime.combine(prev_d, time(8, 0), tzinfo=CT)
        end_ct   = datetime.combine(prev_d, time(16, 30), tzinfo=CT)
        df = yf_fetch_intraday_15m("^GSPC", start_ct, end_ct)
        if df.empty or not {"High","Low","Close"}.issubset(set(df.columns)): 
            return None

        # Convert to ET to enforce cash hours precisely
        dft = df.copy()
        dft["Dt_ET"] = dft["Dt"].dt.tz_convert(ET)
        mask = (dft["Dt_ET"].dt.time >= RTH_START_ET) & (dft["Dt_ET"].dt.time <= RTH_END_ET)
        rth = dft.loc[mask]
        if rth.empty: 
            return None

        hi_idx = rth["High"].idxmax()
        lo_idx = rth["Low"].idxmin()
        return {
            "prev_day": prev_d,
            "high": float(rth.loc[hi_idx, "High"]),
            "low":  float(rth.loc[lo_idx, "Low"]),
            "close": float(rth["Close"].iloc[-1]),
            "high_time_et": rth.loc[hi_idx, "Dt_ET"].to_pydatetime(),
            "low_time_et":  rth.loc[lo_idx, "Dt_ET"].to_pydatetime(),
            "close_time_et": rth["Dt_ET"].iloc[-1].to_pydatetime(),
        }
    except Exception:
        return None

# ───────────────────────────────  SIDEBAR — NAV, DATE, OVERNIGHT INPUTS  ───────────────────────────────
with st.sidebar:
    st.markdown("### 📚 Navigation")
    page = st.radio(
        label="",
        options=["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input(
        "Target session",
        value=date.today(),
        help="SPX cash session to analyze (09:30–16:00 ET)."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual)")
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Low between 5:00 PM and 7:00 AM ET.")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Select a time in the overnight window.", key="on_low_t")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="High between 5:00 PM and 7:00 AM ET.")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Select a time in the overnight window.", key="on_high_t")
    st.caption("Tip: You can leave these blank — they’ll be used when you open the Overnight/Forecasts pages.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE BANNER  ───────────────────────────────
last = fetch_spx_last_banner()
st.markdown(f"""
<div class="hero">
  <div class="title">{APP_NAME}</div>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="card">
      <div class="label">SPX (S&P 500 Index) — Last</div>
      <div class="value mono">{last['px']}</div>
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
      <div class="value">{last['engine']}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────  OVERVIEW  ───────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)

    anchors = prev_day_hlc_spx(forecast_date)
    ready_chip = '<span class="chip ok">Prev-day H/L/C ready</span>' if anchors else '<span class="chip info">Waiting on Yahoo data…</span>'

    st.markdown(f'<div class="chips">{ready_chip}<span class="chip info">Overnight inputs captured</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  ANCHORS (DISPLAY PREVIEW)  ───────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Previous Day Anchors (SPX)</h3>", unsafe_allow_html=True)

    anchors = prev_day_hlc_spx(forecast_date)
    if not anchors:
        st.info("Could not compute anchors yet. Try a recent weekday (Yahoo 15-minute availability can vary).")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Prev Day High", f"{anchors['high']:.2f}")
            st.caption(f"Time ET: {anchors['high_time_et'].strftime('%-I:%M %p')}")
        with c2:
            st.metric("Prev Day Close", f"{anchors['close']:.2f}")
            st.caption(f"Time ET: {anchors['close_time_et'].strftime('%-I:%M %p')}")
        with c3:
            st.metric("Prev Day Low", f"{anchors['low']:.2f}")
            st.caption(f"Time ET: {anchors['low_time_et'].strftime('%-I:%M %p')}")

        st.markdown(
            """
            <div class="table-wrap" style="margin-top:12px;">
              <div style="padding:12px 14px;color:#6b7280;font-size:12px;">
                These anchors power your internal projections (descending from H/C/L with mirrored TP lines).
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDERS (Parts 2+)  ───────────────────────────────
if page in {"Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section will light up in the next parts with full professional tables, detection, contracts, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)