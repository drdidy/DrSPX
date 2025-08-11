# ==============================  **PART 1 / 10 — APP SHELL & NAVIGATION**  ==============================
# MarketLens Pro (Rebuild)
# Goal of Part 1:
# - Minimal, production-clean Streamlit shell
# - Fixed sidebar (expanded) with 8 tickers incl. SPX
# - Simple theme + typography (no heavy CSS yet)
# - Page router scaffold (placeholders only; real logic starts Part 2)
# - Safe to run even without network access

from __future__ import annotations
import os
from datetime import datetime
import streamlit as st

# --- Meta & Config ---
APP_NAME = "MarketLens Pro"
APP_VERSION = "5.0.0"
APP_TAGLINE = "Professional Forecasting & Analytics"
TICKERS = [
    ("^GSPC", "SPX (S&P 500)"),
    ("AMZN",  "AMZN"),
    ("TSLA",  "TSLA"),
    ("GOOGL", "GOOGL"),
    ("AAPL",  "AAPL"),
    ("MSFT",  "MSFT"),
    ("META",  "META"),
    ("NVDA",  "NVDA"),
]

st.set_page_config(
    page_title=f"{APP_NAME} — {APP_TAGLINE}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Minimal, tasteful styling (kept light; full design system comes later) ---
st.markdown("""
<style>
/* Base */
html, body, .stApp { font-family: Inter, -apple-system, Segoe UI, Roboto, sans-serif; }
h1,h2,h3 { letter-spacing:-0.02em; }
.small { color: rgba(0,0,0,0.55); font-size:0.9rem; }
[data-testid="stSidebar"] { border-right: 1px solid rgba(0,0,0,0.06); }

/* Metric card feel */
.block { border:1px solid rgba(0,0,0,0.08); border-radius:14px; padding:16px; background: #fff; }

/* Dark mode tweaks */
:root [data-theme="dark"] .block { background: #1f1f1f; border-color: rgba(255,255,255,0.08); }
:root [data-theme="dark"] .small { color: rgba(255,255,255,0.65); }
</style>
""", unsafe_allow_html=True)

# --- Session bootstrap ---
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "^GSPC"  # default to SPX
if "selected_name" not in st.session_state:
    st.session_state.selected_name = "SPX (S&P 500)"

# --- Sidebar (Navigation) ---
with st.sidebar:
    st.markdown(f"### {APP_NAME}")
    st.caption(APP_TAGLINE)

    # Stock selector (single source of truth)
    labels = {sym: label for sym, label in TICKERS}
    symbol = st.selectbox(
        "Symbol",
        options=[sym for sym, _ in TICKERS],
        index=0,
        format_func=lambda s: labels[s],
        help="Choose the instrument page",
    )
    st.session_state.selected_symbol = symbol
    st.session_state.selected_name = labels[symbol]

    st.divider()
    st.markdown("**Pages**")
    page = st.radio(
        label="",
        options=["Overview", "Anchors & Forecast", "Signals", "Contract Line", "Fibonacci", "Export"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown(
        f"""
        <div class="small">
            v{APP_VERSION}<br/>
            {datetime.now().strftime("%Y-%m-%d %H:%M")}
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Header / Hero (lightweight; expanded later) ---
col1, col2 = st.columns([0.7, 0.3])
with col1:
    st.markdown(f"## {st.session_state.selected_name}")
    st.caption("Clean. Fast. Professional.")
with col2:
    with st.container(border=True):
        st.markdown("**Status**")
        st.markdown(
            "<span class='small'>Live data via Yahoo Finance (enabled in Part 2).</span>",
            unsafe_allow_html=True,
        )

# --- Router scaffold (placeholders only in Part 1) ---
def render_overview():
    st.markdown("### Overview")
    st.markdown(
        """
        <div class="block">
        This is the streamlined shell. In **Part 2+**, we’ll wire:
        <ul>
            <li>Live SPX & equities fetch via <code>yfinance</code></li>
            <li>Professional anchor inputs & validation</li>
            <li>Forecast fan tables (Entry → TP1 → TP2)</li>
            <li>Signal detection, Contract line, Fibonacci tools</li>
            <li>Export center</li>
        </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_anchors_forecast():
    st.markdown("### Anchors & Forecast")
    st.info("Coming in Part 2–4: anchor inputs, locking, fan generation.")

def render_signals():
    st.markdown("### Signals")
    st.info("Coming in Part 5–6: detection table, confidence, monitoring.")

def render_contract():
    st.markdown("### Contract Line")
    st.info("Coming in Part 7: two-point slope → projected curve & lookup.")

def render_fibonacci():
    st.markdown("### Fibonacci")
    st.info("Coming in Part 8: 0.786 focus + confluence with contract line.")

def render_export():
    st.markdown("### Export")
    st.info("Coming in Part 9–10: CSV bundles, summary sheets, downloads.")

ROUTES = {
    "Overview": render_overview,
    "Anchors & Forecast": render_anchors_forecast,
    "Signals": render_signals,
    "Contract Line": render_contract,
    "Fibonacci": render_fibonacci,
    "Export": render_export,
}

# --- Render selected page ---
ROUTES.get(page, render_overview)()

# --- Footer (minimal, no clutter) ---
st.markdown("---")
st.caption("© MarketLens Pro — For educational analysis only.")

# ==============================  **PART 2 / 10 — DATA LAYER & LIVE SNAPSHOT**  ==============================
# What this adds:
# - yfinance-powered fetchers (snapshot, intraday, daily)
# - Previous-day anchors (High/Close/Low)
# - Small, professional "Live Snapshot" card (shown on Overview only)
# - Caching + graceful error handling
#
# Paste directly below Part 1 in the same file.

from datetime import time, timedelta
from typing import Dict, Optional
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st

# --- Trading session (RTH) ---
RTH_START = time(9, 30)   # NYSE open
RTH_END   = time(16, 0)   # NYSE close

def _now_ts():
    return pd.Timestamp.now(tz="America/New_York")

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

# --------------------  Fetchers (cached)  --------------------

@st.cache_data(ttl=60, show_spinner=False)
def fetch_snapshot(symbol: str) -> Dict:
    """
    Return a compact snapshot using 1m intraday + recent daily for prev close.
    """
    try:
        tk = yf.Ticker(symbol)
        intraday = tk.history(period="1d", interval="1m")
        daily = tk.history(period="6d", interval="1d")

        if intraday is None or intraday.empty:
            return {"status": "error", "message": "No intraday data"}

        last = intraday.iloc[-1]
        price = _safe_float(last.get("Close"))
        volume = int(_safe_float(last.get("Volume"), 0))

        # Use previous daily close for change
        if daily is None or len(daily) < 2:
            prev_close = price
        else:
            prev_close = _safe_float(daily.iloc[-2].get("Close"), price)

        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        today = daily.iloc[-1] if daily is not None and not daily.empty else None
        today_high = _safe_float(today.get("High")) if today is not None else price
        today_low  = _safe_float(today.get("Low"))  if today is not None else price

        return {
            "status": "success",
            "symbol": symbol,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "high": round(today_high, 2),
            "low": round(today_low, 2),
            "prev_close": round(prev_close, 2),
            "volume": volume,
            "last_update": _now_ts(),
        }
    except Exception as e:
        return {"status": "error", "message": f"snapshot failed: {e}"}

@st.cache_data(ttl=120, show_spinner=False)
def fetch_daily(symbol: str, period: str = "1mo") -> pd.DataFrame:
    """
    Daily bars. Used across multiple pages (anchors, analytics).
    """
    try:
        df = yf.Ticker(symbol).history(period=period, interval="1d")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index().rename(columns={"Date": "dt"})
        # Normalize time zone for comparisons
        df["dt"] = pd.to_datetime(df["dt"]).dt.tz_localize(None)
        df["date"] = df["dt"].dt.date
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=120, show_spinner=False)
def fetch_intraday(symbol: str, target_date: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """
    Intraday 1m bars for target_date (US/Eastern). If target_date is None, use today's session.
    """
    try:
        if target_date is None:
            target_date = _now_ts().tz_localize(None).normalize()

        start = (pd.Timestamp(target_date) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        end   = (pd.Timestamp(target_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        df = yf.Ticker(symbol).history(start=start, end=end, interval="1m")
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.reset_index().rename(columns={"Datetime": "dt"})
        if "dt" not in df.columns:
            # Some regions label first column differently; fallback
            df.rename(columns={df.columns[0]: "dt"}, inplace=True)

        df["dt"] = pd.to_datetime(df["dt"]).dt.tz_localize(None)
        df["date"] = df["dt"].dt.date
        df["time"] = df["dt"].dt.strftime("%H:%M")
        # Keep only target date rows
        df = df[df["date"] == pd.to_datetime(target_date).date()].copy()
        return df
    except Exception:
        return pd.DataFrame()

# --------------------  Anchors (Previous Day High/Close/Low)  --------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_previous_day_anchors(symbol: str) -> Optional[Dict]:
    """
    Returns previous trading day's High/Close/Low for given symbol.
    """
    daily = fetch_daily(symbol, period="1mo")
    if daily.empty:
        return None
    # Previous trading day is the last row excluding the last date if it's today
    today_date = pd.Timestamp.today().normalize().date()
    candidates = daily[daily["date"] < today_date]
    if candidates.empty:
        # If market hasn't closed yet, last available may still be 'previous'
        candidates = daily.iloc[:-1] if len(daily) > 1 else daily
    if candidates.empty:
        return None

    prev = candidates.iloc[-1]
    return {
        "date": prev["date"],
        "high": round(_safe_float(prev["High"]), 2),
        "close": round(_safe_float(prev["Close"]), 2),
        "low": round(_safe_float(prev["Low"]), 2),
        "volume": int(_safe_float(prev.get("Volume"), 0)),
    }

# --------------------  UI — Live Snapshot (compact, professional)  --------------------

def render_live_snapshot(symbol: str, label: str):
    snap = fetch_snapshot(symbol)
    with st.container(border=True):
        st.markdown(f"**Live Snapshot — {label}**")
        if snap.get("status") != "success":
            st.caption(f"Data unavailable ({snap.get('message','error')})")
            return

        price = snap["price"]
        ch = snap["change"]
        chp = snap["change_pct"]
        hi = snap["high"]
        lo = snap["low"]
        vol = snap["volume"]
        when = snap["last_update"].strftime("%H:%M:%S %Z") if hasattr(snap["last_update"], "strftime") else str(snap["last_update"])

        colA, colB, colC, colD = st.columns([1.2, 1, 1, 1.2])
        with colA:
            st.metric("Price", f"${price:,.2f}", f"{ch:+.2f} ({chp:+.2f}%)")
        with colB:
            st.metric("High", f"${hi:,.2f}")
        with colC:
            st.metric("Low", f"${lo:,.2f}")
        with colD:
            st.metric("Volume", f"{vol:,}")

        st.caption(f"Updated: {when}")

# --------------------  Part 2: minimal activation (Overview only)  --------------------

# If the Part 1 variable `page` exists and we are on Overview, show the snapshot card
try:
    if "page" in globals() and page == "Overview":
        # Use the selection from Part 1 session state
        render_live_snapshot(st.session_state.selected_symbol, st.session_state.selected_name)

        # (Optional) show anchors succinctly to confirm function works
        anchors = get_previous_day_anchors(st.session_state.selected_symbol)
        if anchors:
            a_col1, a_col2, a_col3, a_col4 = st.columns(4)
            with a_col1:
                st.metric("Prev High", f"${anchors['high']:,.2f}")
            with a_col2:
                st.metric("Prev Close", f"${anchors['close']:,.2f}")
            with a_col3:
                st.metric("Prev Low", f"${anchors['low']:,.2f}")
            with a_col4:
                st.caption(f"Session: {anchors['date']}")
        else:
            st.caption("Previous-day anchors not available yet.")
except Exception:
    # Never break the page if remote fetch fails
    st.caption("Live data temporarily unavailable.")