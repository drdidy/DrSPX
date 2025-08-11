# ==============================  PART 1 — CORE SHELL (DAILY-ONLY)  ==============================
# Enterprise UI • Always-open sidebar • Asset picker (SPX + 8 stocks)
# Yahoo Finance daily candles with robust SPX alias fallback (^GSPC → ^INX → ^SPX)
# Hidden slope engine (not shown) + Overnight (price+time) inputs captured for later parts
# -----------------------------------------------------------------------------------------------

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# ─────────────────────────────  GLOBAL CONFIG  ─────────────────────────────
APP_NAME = "MarketLens Pro"
TAGLINE  = "Enterprise SPX & Equities Forecasting"
VERSION  = "5.0"
COMPANY  = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Cash session (used for labeling only in Part 1)
RTH_START_ET, RTH_END_ET = time(9, 30), time(16, 0)

# Previous-day anchor engine (hidden; shown here so it works in later parts)
SLOPES = {
    "SPX_prev_down": -0.2792,  # high/close/low (descending)
    "SPX_tp_up":     +0.2792,  # mirrored TP (ascending)
    "ON_low_up":     +0.2792,  # overnight low (ascending)
    "ON_high_down":  -0.2792,  # overnight high (descending)
}

# Asset universe (SPX is a virtual key resolved via aliases)
ASSETS = {
    "SPX (S&P 500 Index)": "SPX_INDEX",
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
    "Amazon (AMZN)": "AMZN",
    "Alphabet (GOOGL)": "GOOGL",
    "Meta (META)": "META",
    "NVIDIA (NVDA)": "NVDA",
    "Tesla (TSLA)": "TSLA",
    "Netflix (NFLX)": "NFLX",
}
SPX_ALIASES = ["^GSPC", "^INX", "^SPX"]  # daily-only fallback order

# ─────────────────────────────  PAGE SETUP  ─────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — Daily Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────  PREMIUM CSS  ─────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
.stApp { background: radial-gradient(1200px 600px at 8% -10%, #f6f9ff 0%, #ffffff 38%) fixed; }

/* Hero */
.hero {
  border-radius: 22px;
  padding: 22px 24px;
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: #fff;
  border: 1px solid rgba(255,255,255,.18);
  box-shadow: 0 18px 40px rgba(99,102,241,.28);
}
.hero .title { font-weight: 900; font-size: 28px; letter-spacing: -0.02em; }
.hero .sub   { opacity: .95; font-weight: 600; margin-top: 2px; }
.hero .meta  { opacity: .85; font-size: 12px; margin-top: 8px; }
.kpi { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-top:16px; }
.kpi .card {
  border-radius: 16px; padding: 14px 16px; background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.25);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.25), 0 8px 24px rgba(15,23,42,.22);
  backdrop-filter: blur(6px);
}
.kpi .label { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; opacity: .9; }
.kpi .value { font-weight: 900; font-size: 22px; letter-spacing: -0.02em; }

/* Sections */
.sec {
  margin-top: 18px; padding: 18px; border-radius: 20px; background: #fff;
  border: 1px solid rgba(2,6,23,.06); box-shadow: 0 10px 34px rgba(2,6,23,.07);
}
.sec h3 { margin:0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -.01em; }

/* Sidebar */
section[data-testid="stSidebar"] {
  background:#0b1220 !important; color:#e5e7eb;
  border-right:1px solid rgba(255,255,255,.06);
}
.sidebar-card {
  background: rgba(255,255,255,.06);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 14px; padding: 12px; margin: 12px 0;
}
.sidebar-card .hdr { font-weight:800; margin-bottom:6px; }

/* Chips */
.chips { display:flex; flex-wrap:wrap; gap:8px; }
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  font-size:12px; font-weight:800; letter-spacing:.02em;
  border:1px solid rgba(0,0,0,.08); background:#f8fafc; color:#0f172a;
}
.chip.ok   { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }

/* Table wrapper (for later parts) */
.table-wrap{border-radius:16px;overflow:hidden;border:1px solid rgba(0,0,0,.06);box-shadow:0 8px 24px rgba(2,6,23,.05);}
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────  YF HELPERS (DAILY-ONLY)  ─────────────────────────────
def _clean_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
    df = df.copy().reset_index()
    # yfinance daily often uses "Date" or "index"
    for c in ("Date", "Datetime", "index"):
        if c in df.columns and "Dt" not in df.columns:
            df.rename(columns={c:"Dt"}, inplace=True)
    if "Dt" not in df.columns:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
    df["Dt"] = pd.to_datetime(df["Dt"], utc=True, errors="coerce").dt.tz_localize("UTC").dt.tz_convert(ET)
    keep = [c for c in ["Open","High","Low","Close"] if c in df.columns]
    return df[["Dt"]+keep].dropna(subset=keep).sort_values("Dt").reset_index(drop=True)

@st.cache_data(ttl=600, show_spinner=False)
def yf_download_daily(symbol: str, period: str = "5y") -> pd.DataFrame:
    try:
        raw = yf.download(symbol, interval="1d", period=period, auto_adjust=False, progress=False, threads=True)
        return _clean_daily(raw)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

def get_spx_daily(period: str = "5y") -> pd.DataFrame:
    """Try ^GSPC → ^INX → ^SPX, return first non-empty daily frame."""
    for tkr in SPX_ALIASES:
        df = yf_download_daily(tkr, period=period)
        if not df.empty:
            return df
    return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

# Banner: last close + date (daily-only)
@st.cache_data(ttl=300, show_spinner=False)
def fetch_last_banner(symbol_or_virtual: str) -> dict:
    try:
        df = get_spx_daily() if symbol_or_virtual == "SPX_INDEX" else yf_download_daily(symbol_or_virtual)
        if df.empty:
            return {"px":"—","ts":"—","engine":"Awaiting data"}
        last = df.iloc[-1]
        ts = last["Dt"].strftime("Close %a %b %d, %Y")
        return {"px": f"{float(last['Close']):,.2f}", "ts": ts, "engine": "Yahoo • 1d"}
    except Exception:
        return {"px":"—","ts":"—","engine":"Awaiting data"}

# Previous trading day (helper)
def previous_trading_day(ref_d: date) -> date:
    d = ref_d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

# Prev-day H/L/C from daily (close = prior day close; high/low from that day)
@st.cache_data(ttl=600, show_spinner=False)
def prev_day_hlc_daily(symbol_or_virtual: str, ref_session: date) -> dict | None:
    df = get_spx_daily() if symbol_or_virtual == "SPX_INDEX" else yf_download_daily(symbol_or_virtual)
    if df.empty: 
        return None
    prev_d = previous_trading_day(ref_session)
    # match by ET date only
    df["D_ET"] = df["Dt"].dt.tz_convert(ET).dt.date
    row = df[df["D_ET"] == prev_d]
    if row.empty:
        # fallback: use last available prior date
        row = df[df["D_ET"] < ref_session].tail(1)
        if row.empty:
            return None
    r = row.iloc[-1]
    return {
        "prev_day": prev_d,
        "high": float(r["High"]),
        "low": float(r["Low"]),
        "close": float(r["Close"]),
    }

# ─────────────────────────────  SIDEBAR (NAV + INPUTS)  ─────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-card"><div class="hdr">📚 Navigation</div>', unsafe_allow_html=True)
    page = st.radio(
        label="",
        options=["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
        index=0, label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><div class="hdr">🎯 Instrument</div>', unsafe_allow_html=True)
    asset_label = st.selectbox("Asset", list(ASSETS.keys()), index=0)
    symbol = ASSETS[asset_label]
    st.caption("Tip: SPX uses a resilient daily fallback (^GSPC → ^INX → ^SPX).")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><div class="hdr">📅 Session</div>', unsafe_allow_html=True)
    forecast_date = st.date_input(
        "Target session (ET)",
        value=date.today(),
        help="The cash session you’re analyzing (09:30–16:00 ET)."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><div class="hdr">🌙 Overnight Anchors (Manual)</div>', unsafe_allow_html=True)
    on_low_price  = st.number_input("Overnight Low — Price", min_value=0.0, step=0.25, value=0.00)
    on_low_time   = st.time_input("Overnight Low — Time (ET)", value=time(21, 0))
    on_high_price = st.number_input("Overnight High — Price", min_value=0.0, step=0.25, value=0.00)
    on_high_time  = st.time_input("Overnight High — Time (ET)", value=time(22, 30))
    st.caption("Window reference: 5:00 PM → 7:00 AM ET. Used in later parts to project entries.")
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────  HERO  ─────────────────────────────
last = fetch_last_banner(symbol)
st.markdown(f"""
<div class="hero">
  <div class="title">{APP_NAME}</div>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="card">
      <div class="label">{asset_label} — Last</div>
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

# ─────────────────────────────  OVERVIEW  ─────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)
    anchors = prev_day_hlc_daily(symbol, forecast_date)
    chip1 = '<span class="chip ok">Daily price ready</span>' if last["px"] != "—" else '<span class="chip info">Waiting on Yahoo data…</span>'
    chip2 = '<span class="chip ok">Prev-day anchors ready</span>' if anchors else '<span class="chip info">Prev-day anchors will load when available</span>'
    chip3 = '<span class="chip info">Overnight inputs captured</span>'
    st.markdown(f'<div class="chips">{chip1}{chip2}{chip3}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────  ANCHORS (DAILY PREVIEW)  ─────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Previous Day Anchors</h3>", unsafe_allow_html=True)
    anchors = prev_day_hlc_daily(symbol, forecast_date)
    if not anchors:
        st.info("Could not compute previous-day anchors from daily data yet. Try another recent weekday.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Prev Day High", f"{anchors['high']:.2f}")
        with c2:
            st.metric("Prev Day Close", f"{anchors['close']:.2f}")
        with c3:
            st.metric("Prev Day Low", f"{anchors['low']:.2f}")
        st.caption(f"Date used: {anchors['prev_day'].strftime('%a %b %d, %Y')} • Daily candles (Yahoo Finance)")
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────  PLACEHOLDERS (filled in Parts 2+)  ─────────────────────────────
if page in {"Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section will light up in the next parts with professional tables, signal logic, contract helper, Fibonacci toolkit, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)