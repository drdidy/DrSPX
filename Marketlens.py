# ==============================  PART 1 — CORE SHELL + LIVE SPX + SAFE DATA DEFAULTS  ==============================
# Enterprise UI, always-open sidebar, SPX from Yahoo Finance, hidden slope engine, overnight inputs (price+time)
# Auto-resolves to a recent trading day with data so the page never looks empty.

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

# SPX cash RTH (ET)
RTH_START_ET, RTH_END_ET = time(9, 30), time(16, 0)

# SPX slopes (per 30-min) — work in background
SPX_SLOPES = {
    "prev_high_down": -0.2792,
    "prev_close_down": -0.2792,
    "prev_low_down":  -0.2792,
    "tp_mirror_up":   +0.2792,
}
SPX_OVERNIGHT_SLOPES = {
    "overnight_low_up":   +0.2792,
    "overnight_high_down":-0.2792,
}

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — SPX",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS (Header visible)  ───────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

/* App background */
.stApp { background: radial-gradient(1200px 600px at 10% -10%, #f8fbff 0%, #ffffff 35%) no-repeat fixed; }

/* Keep Streamlit header visible; only hide MainMenu */
#MainMenu { display: none !important; }

/* Brand Hero */
.hero {
  border-radius: 24px;
  padding: 20px 22px;
  border: 1px solid rgba(0,0,0,0.06);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 12px 30px rgba(99,102,241,0.25);
  margin-top: 8px;
}
.hero .title { font-weight: 800; font-size: 26px; letter-spacing: -0.02em; }
.hero .sub { opacity: 0.95; font-weight: 500; }
.hero .meta { opacity: 0.8; font-size: 13px; margin-top: 4px; }

/* KPI strip */
.kpi { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 12px; }
.kpi .card {
  border-radius: 16px; padding: 14px 16px;
  background: white; border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 4px 16px rgba(2,6,23,0.05);
}
.kpi .label { color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.kpi .value { font-weight: 800; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }

/* Section */
.sec { margin-top: 18px; border-radius: 20px; padding: 18px; background: white; border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 8px 30px rgba(2,6,23,0.05); }
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 800; letter-spacing: -0.01em; }

/* Sidebar */
section[data-testid="stSidebar"] {
  background: #0b1220 !important;
  color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
.sidebar-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px 12px; margin: 10px 0;
}
.sidebar-card h4 { margin: 0 0 8px 0; }

/* Chips */
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(0,0,0,0.08); background:#f8fafc; font-size:12px; font-weight:700; color:#0f172a;
}
.chip.ok { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS: YF FETCH + DAY RESOLUTION  ───────────────────────────────
def _weekday_backwards(d: date):
    cur = d
    while True:
        if cur.weekday() < 5:  # Mon–Fri
            yield cur
        cur -= timedelta(days=1)

@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_intraday_1m(symbol: str) -> pd.DataFrame:
    """
    Pull last 7 days of 1m data from Yahoo. Returns tz-aware CT timestamps + OHLC.
    We filter per-session locally elsewhere.
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
        # Normalize timestamp column
        ts_col = "Datetime" if "Datetime" in df.columns else ("index" if "index" in df.columns else None)
        if ts_col is None:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        df["Dt"] = pd.to_datetime(df[ts_col], utc=True).dt.tz_convert(CT)
        keep = [c for c in ["Open","High","Low","Close"] if c in df.columns]
        return df[["Dt"] + keep].dropna(subset=keep).sort_values("Dt").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

def session_mask_et(df: pd.DataFrame, d: date) -> pd.Series:
    """Mask rows that fall inside ET RTH of the given date."""
    if df.empty: 
        return pd.Series([], dtype=bool)
    dt_et = df["Dt"].dt.tz_convert(ET)
    in_day = dt_et.dt.date == d
    in_rth = (dt_et.dt.time >= RTH_START_ET) & (dt_et.dt.time <= RTH_END_ET)
    return in_day & in_rth

@st.cache_data(ttl=300, show_spinner=False)
def resolve_latest_trading_day_with_data(desired_session: date) -> tuple[date, str]:
    """
    Given a desired RTH session date, find the most recent session (<= desired) that
    actually has SPX 1m data available. Returns (resolved_date, note).
    """
    df = yf_fetch_intraday_1m("^GSPC")
    if df.empty:
        # No Yahoo data at all right now
        return desired_session, "No Yahoo intraday data available (last 7d)."
    # Walk backwards through weekdays to find a session with RTH rows
    for d in _weekday_backwards(desired_session):
        m = session_mask_et(df, d)
        if m.any():
            note = "Using your selected session." if d == desired_session else f"Auto-switched to {d.strftime('%a %b %d, %Y')} (most recent with data)."
            return d, note
    # Shouldn’t happen: we had data but none maps to any weekday window
    first_dt = df["Dt"].iloc[-1].tz_convert(ET).date()
    return first_dt, "Fallback to last data day."

@st.cache_data(ttl=300, show_spinner=False)
def prev_day_hlc_spx(session_d: date) -> dict | None:
    """
    Compute Prev Day H/L/C for the resolved session date.
    """
    try:
        df = yf_fetch_intraday_1m("^GSPC")
        if df.empty: 
            return None
        # Previous weekday
        prev = session_d - timedelta(days=1)
        while prev.weekday() >= 5:
            prev -= timedelta(days=1)
        # Mask prev day RTH (in ET)
        dt_et = df["Dt"].dt.tz_convert(ET)
        in_day = dt_et.dt.date == prev
        in_rth = (dt_et.dt.time >= RTH_START_ET) & (dt_et.dt.time <= RTH_END_ET)
        rth = df.loc[in_day & in_rth].copy()
        if rth.empty or not {"High","Low","Close"}.issubset(rth.columns):
            return None

        # Build ET times for anchors
        rth["Dt_ET"] = rth["Dt"].dt.tz_convert(ET)
        hi_idx = rth["High"].idxmax()
        lo_idx = rth["Low"].idxmin()

        return {
            "prev_day": prev,
            "high":  float(rth.loc[hi_idx,"High"]),
            "low":   float(rth.loc[lo_idx,"Low"]),
            "close": float(rth["Close"].iloc[-1]),
            "high_time_et":  rth.loc[hi_idx,"Dt_ET"].to_pydatetime(),
            "low_time_et":   rth.loc[lo_idx,"Dt_ET"].to_pydatetime(),
            "close_time_et": rth["Dt_ET"].iloc[-1].to_pydatetime(),
        }
    except Exception:
        return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_last_banner() -> dict:
    """Last SPX price/time for the banner, with robust fallback."""
    try:
        df = yf_fetch_intraday_1m("^GSPC")
        if not df.empty:
            last = df.iloc[-1]
            return {"px": f"{float(last['Close']):,.2f}", "ts": last["Dt"].strftime("%-I:%M %p %Z")}
        # Fallback to recent daily close
        daily = yf.Ticker("^GSPC").history(period="5d", auto_adjust=False)
        if not daily.empty:
            px = float(daily["Close"].iloc[-1])
            ts = daily.index[-1].tz_localize("UTC").tz_convert(CT).strftime("%-I:%M %p %Z")
            return {"px": f"{px:,.2f}", "ts": ts}
        return {"px":"—","ts":"—"}
    except Exception:
        return {"px":"—","ts":"—"}

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
    st.markdown("<h4>📅 Session</h4>", unsafe_allow_html=True)
    user_pick = st.date_input(
        "Target session (RTH)",
        value=date.today(),
        help="We’ll auto-switch to the latest weekday that has Yahoo 1-minute data so your page never looks empty."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("<h4>🌙 Overnight Anchors (Manual)</h4>", unsafe_allow_html=True)
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing LOW (5:00 PM–7:00 AM ET).")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Pick a time between 5:00 PM and 7:00 AM ET.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing HIGH (5:00 PM–7:00 AM ET).")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Pick a time between 5:00 PM and 7:00 AM ET.")
    st.caption("You’ll use these on the Overnight/Forecast tabs in later parts.")
    st.markdown('</div>', unsafe_allow_html=True)

# Resolve a session day that truly has data
resolved_session, session_note = resolve_latest_trading_day_with_data(user_pick)

# ───────────────────────────────  HERO + LIVE BANNER  ───────────────────────────────
last = fetch_spx_last_banner()
st.markdown(f"""
<div class="hero">
  <div class="title">{APP_NAME}</div>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>
  <div class="kpi">
    <div class="card">
      <div class="label">SPX — Last</div>
      <div class="value mono">{last['px']}</div>
    </div>
    <div class="card">
      <div class="label">As of</div>
      <div class="value">{last['ts']}</div>
    </div>
    <div class="card">
      <div class="label">Session</div>
      <div class="value">{resolved_session.strftime('%a %b %d, %Y')}</div>
    </div>
    <div class="card">
      <div class="label">Engine</div>
      <div class="value"><span class="chip ok">Yahoo Finance • 1m</span></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# If we auto-switched, tell the user (subtle)
if session_note and "Auto-switched" in session_note:
    st.info(session_note)

# ───────────────────────────────  OVERVIEW  ───────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)
    anchors = prev_day_hlc_spx(resolved_session)
    chip = '<span class="chip ok">Prev-Day H/L/C Ready</span>' if anchors else '<span class="chip info">Waiting for Yahoo intraday…</span>'
    st.markdown(f"<div style='display:flex;gap:8px;flex-wrap:wrap;'>{chip}<span class='chip info'>Overnight inputs captured</span></div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  ANCHORS  ───────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Previous Day Anchors (SPX)</h3>", unsafe_allow_html=True)
    anchors = prev_day_hlc_spx(resolved_session)
    if not anchors:
        st.error("Could not compute SPX prev-day anchors. Yahoo may be rate-limited or this week has no 1-minute data. Try another recent weekday.")
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
        st.caption(f"Prev day: {anchors['prev_day'].strftime('%a %b %d, %Y')} (ET RTH)")

    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDERS (filled in next parts)  ───────────────────────────────
if page in {"Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section lights up in Part 2+ with the full professional tables, detection, contract logic, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)