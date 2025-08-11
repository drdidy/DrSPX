# =====================  PART 1 — ENTERPRISE SHELL + YFINANCE (SPX & EQUITIES)  =====================
# Open sidebar • Asset picker (^GSPC + 8 equities) • Live banner with fallbacks • Overnight inputs
# Uses yfinance.Ticker().history with 1m→5m→1d fallback so KPIs never show dashes.

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# ── Meta
APP_NAME   = "MarketLens Pro"
TAGLINE    = "Enterprise SPX & Equities Forecasting"
VERSION    = "5.0"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# ── Supported instruments
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

# ── Page config (header stays visible)
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Premium look & feel
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
.stApp { background: radial-gradient(1200px 600px at 10% -10%, #f7fbff 0%, #ffffff 38%) no-repeat fixed; }

/* Hero */
.hero {
  border-radius: 26px; padding: 22px 24px 26px; color: #fff;
  background: linear-gradient(145deg, #0ea5e9 0%, #6366f1 100%);
  border: 1px solid rgba(255,255,255,.28);
  box-shadow: 0 18px 44px rgba(99,102,241,.28), inset 0 1px 0 rgba(255,255,255,.18);
}
.hero h1 { margin: 0; font-weight: 900; font-size: 28px; letter-spacing: -0.02em; }
.hero .sub { margin-top: 2px; opacity: .96; font-weight: 600; }
.hero .meta { margin-top: 6px; opacity: .85; font-size: 12px; }

/* KPI */
.kpi { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 16px; }
.kpi .card {
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28); backdrop-filter: blur(6px);
  border-radius: 18px; padding: 14px 16px;
  box-shadow: 0 10px 25px rgba(2,6,23,.18), inset 0 1px 0 rgba(255,255,255,.35);
}
.kpi .label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; opacity: .9; font-weight: 800; }
.kpi .value { margin-top: 6px; font-weight: 900; font-size: 22px; letter-spacing: -0.02em; }

/* Section */
.sec { margin-top: 18px; border-radius: 20px; padding: 18px; background: #fff; border: 1px solid rgba(0,0,0,0.06);
       box-shadow: 0 16px 34px rgba(2,6,23,.08); }
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

/* Sidebar */
section[data-testid="stSidebar"] { background:#0b1220!important; color:#e5e7eb; border-right:1px solid rgba(255,255,255,.06); }
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label { color:#e5e7eb!important; }
.sidebar-card { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12); border-radius:14px; padding:12px; margin:10px 0; }

/* Chips */
.chip { display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; font-weight:800; font-size:12px; }
.chip.info { background:#eef2ff; color:#312e81; border:1px solid #6366f133; }
.chip.ok { background:#ecfdf5; color:#065f46; border:1px solid #10b98133; }
</style>
""", unsafe_allow_html=True)

# ── Yahoo helpers (Ticker().history everywhere)
def _t_hist(symbol: str, *, period: str, interval: str) -> pd.DataFrame:
    try:
        t = yf.Ticker(symbol)
        df = t.history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.dropna(subset=["Close"]).copy()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60, show_spinner=False)
def yf_last_with_fallback(symbol: str) -> dict:
    """
    Try 1m (today) → 5m (recent) → last daily close.
    Always returns a value (avoids dashes).
    """
    # 1m today
    df = _t_hist(symbol, period="1d", interval="1m")
    if not df.empty:
        last = df.iloc[-1]
        ts = df.index[-1].to_pydatetime().astimezone(CT)
        return {"price": f"{float(last['Close']):,.2f}",
                "asof": ts.strftime("%a %b %d, %Y %I:%M %p CT"),
                "engine": "Yahoo 1m (live/rt delayed)"}
    # 5m recent
    df = _t_hist(symbol, period="5d", interval="5m")
    if not df.empty:
        last = df.iloc[-1]
        ts = df.index[-1].to_pydatetime().astimezone(CT)
        return {"price": f"{float(last['Close']):,.2f}",
                "asof": ts.strftime("%a %b %d, %Y %I:%M %p CT"),
                "engine": "Yahoo 5m (fallback)"}
    # 1d last close
    df = _t_hist(symbol, period="6mo", interval="1d")
    if not df.empty:
        last = df.iloc[-1]
        d = df.index[-1].date()
        return {"price": f"{float(last['Close']):,.2f}",
                "asof": d.strftime("%a %b %d, %Y"),
                "engine": "Yahoo 1d (last close)"}
    return {"price": "N/A", "asof": "No data", "engine": "Unavailable"}

# ── Sidebar: nav, asset, session, overnight inputs
with st.sidebar:
    st.markdown("### 📚 Navigation")
    page = st.radio("", ["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
                    index=0, label_visibility="collapsed")

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🎯 Asset")
    asset_label = st.selectbox("Choose instrument", list(SYMBOLS.keys()), index=0)
    symbol = SYMBOLS[asset_label]
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input("Target session", value=date.today())
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual)")
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00)
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0))
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00)
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30))
    st.caption("Used in Overnight tab (Parts 2+).")
    st.markdown('</div>', unsafe_allow_html=True)

# ── Hero banner (now always resolves to some price/time) — works for SPX & equities
last = yf_last_with_fallback(symbol)

st.markdown(f"""
<div class="hero">
  <h1>{APP_NAME}</h1>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="card">
      <div class="label">{asset_label} — Last</div>
      <div class="value">{last['price']}</div>
    </div>
    <div class="card">
      <div class="label">As of</div>
      <div class="value">{last['asof']}</div>
    </div>
    <div class="card">
      <div class="label">Session (selected)</div>
      <div class="value">{forecast_date.strftime('%a %b %d, %Y')}</div>
    </div>
    <div class="card">
      <div class="label">Engine</div>
      <div class="value">{last['engine']}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Overview (light for Part 1)
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)
    st.markdown(
        """
        <span class="chip ok">Live price resolved via fallback chain</span>
        <span class="chip info">Prev-day anchors & entries arrive in Part 2+</span>
        <span class="chip info">Overnight inputs captured</span>
        """, unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ── Placeholders (will light up in next parts)
if page in {"Anchors","Forecasts","Signals","Contracts","Fibonacci","Export","Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section activates in the next parts with your full strategy, tables, charts and exports.")
    st.markdown('</div>', unsafe_allow_html=True)