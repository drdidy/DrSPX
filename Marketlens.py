# ==============================  **PART 1 / 10 — APP SHELL & NAVIGATION (CLEAN)**  ==============================
# What this provides (minimal, professional):
# - Streamlit page config
# - Light, clean design tokens (colors, spacing, fonts)
# - Sidebar navigation + symbol picker with your 8 symbols + SPX
# - Page router stubs (no placeholder paragraphs)
# - A lean Overview stub (Part 2 will populate its content)

import streamlit as st
from dataclasses import dataclass

# ---------- App Meta ----------
APP_NAME = "MarketLens Pro"
APP_VERSION = "4.1.0"
APP_TAGLINE = "Professional SPX & Equities Analytics"

st.set_page_config(
    page_title=f"{APP_NAME} — {APP_TAGLINE}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Design Tokens (lean) ----------
COLORS = {
    "primary": "#0A84FF",
    "success": "#34C759",
    "warning": "#FF9500",
    "danger":  "#FF3B30",
    "text":    "#111827",
    "muted":   "#6B7280",
    "surface": "#FFFFFF",
    "panel":   "#F8FAFC",
    "border":  "rgba(0,0,0,0.08)",
}

BASE_CSS = f"""
<style>
html, body, .stApp {{
  font-family: ui-sans-serif, -apple-system, "SF Pro Text", Inter, Segoe UI, Roboto, sans-serif;
  color: {COLORS["text"]};
}}
.block {{
  background: {COLORS["panel"]};
  border: 1px solid {COLORS["border"]};
  border-radius: 14px;
  padding: 14px 16px;
}}
h1,h2,h3 {{ letter-spacing: -0.01em; }}
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

# ---------- Symbol Set ----------
@dataclass(frozen=True)
class Ticker:
    symbol: str
    name: str

SYMBOLS = [
    Ticker("^GSPC", "S&P 500 (SPX)"),
    Ticker("AAPL",  "Apple"),
    Ticker("MSFT",  "Microsoft"),
    Ticker("NVDA",  "NVIDIA"),
    Ticker("META",  "Meta"),
    Ticker("GOOGL", "Alphabet"),
    Ticker("TSLA",  "Tesla"),
    Ticker("NFLX",  "Netflix"),
    Ticker("AMZN",  "Amazon"),
]

# ---------- Session Defaults ----------
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = SYMBOLS[0].symbol
if "selected_name" not in st.session_state:
    st.session_state.selected_name = SYMBOLS[0].name
if "page" not in st.session_state:
    st.session_state.page = "Overview"

# ---------- Sidebar: Navigation ----------
with st.sidebar:
    st.markdown(f"### {APP_NAME}")
    st.caption(APP_TAGLINE)

    # Symbol picker
    names = [f"{t.name} — {t.symbol}" for t in SYMBOLS]
    default_index = next((i for i,t in enumerate(SYMBOLS) if t.symbol == st.session_state.selected_symbol), 0)
    sel = st.selectbox("Instrument", names, index=default_index)
    sel_idx = names.index(sel)
    st.session_state.selected_symbol = SYMBOLS[sel_idx].symbol
    st.session_state.selected_name = SYMBOLS[sel_idx].name

    st.divider()

    pages = [
        "Overview",
        "Anchors",
        "Forecasts",
        "Signals",
        "Contract",
        "Fibonacci",
        "Export",
        "Settings / About",
    ]
    page = st.radio("Navigation", pages, index=pages.index(st.session_state.page))
    st.session_state.page = page

# ---------- Page Stubs (no placeholder copy) ----------
def render_overview():
    st.markdown("### Overview")
    # Part 2 will inject live snapshot & anchors here.

def render_anchors():
    st.markdown("### Anchors")

def render_forecasts():
    st.markdown("### Forecasts")

def render_signals():
    st.markdown("### Signals")

def render_contract():
    st.markdown("### Contract")

def render_fibonacci():
    st.markdown("### Fibonacci")

def render_export():
    st.markdown("### Export")

def render_settings():
    st.markdown("### Settings / About")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**App:** {APP_NAME}")
        st.write(f"**Version:** {APP_VERSION}")
    with col2:
        st.write("**Design:** Minimal, professional UI")
        st.write("**Data:** yfinance (cached)")

# ---------- Router ----------
ROUTES = {
    "Overview": render_overview,
    "Anchors": render_anchors,
    "Forecasts": render_forecasts,
    "Signals": render_signals,
    "Contract": render_contract,
    "Fibonacci": render_fibonacci,
    "Export": render_export,
    "Settings / About": render_settings,
}

ROUTES[page]()  # render current page

# ==============================  **PART 2 / 10 — LIVE SNAPSHOT & PREVIOUS-DAY ANCHORS (NO VOLUME)**  ==============================
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st

# --- Utility: fetch live snapshot from Yahoo Finance ---
@st.cache_data(ttl=60, show_spinner=False)
def get_live_snapshot(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m")
        if df.empty:
            return None
        last_bar = df.iloc[-1]
        prev_bar = df.iloc[-2] if len(df) > 1 else last_bar

        cur = float(last_bar["Close"])
        prev_close = float(prev_bar["Close"])
        chg = cur - prev_close
        pct = (chg / prev_close) * 100 if prev_close else 0
        hi = float(df["High"].max())
        lo = float(df["Low"].min())

        return {
            "price": cur,
            "change": chg,
            "change_pct": pct,
            "high": hi,
            "low": lo,
            "time": last_bar.name.to_pydatetime(),
        }
    except Exception:
        return None

# --- Utility: fetch previous day's OHLC (anchors) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_prev_day_anchors(symbol: str):
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=5)
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if df.empty:
            return None
        prev_day = df.iloc[-1]
        return {
            "date": prev_day.name.date(),
            "high": float(prev_day["High"]),
            "close": float(prev_day["Close"]),
            "low": float(prev_day["Low"]),
        }
    except Exception:
        return None

# --- Render Overview page content ---
def render_overview():
    st.markdown(f"### {st.session_state.selected_name}")

    # Live snapshot
    snapshot = get_live_snapshot(st.session_state.selected_symbol)
    if snapshot:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Price",
                f"{snapshot['price']:.2f}",
                f"{snapshot['change']:+.2f} ({snapshot['change_pct']:+.2f}%)"
            )
        with col2:
            st.metric("High", f"{snapshot['high']:.2f}")
        with col3:
            st.metric("Low", f"{snapshot['low']:.2f}")
        st.caption(f"Last update: {snapshot['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.error("No live data available.")

    st.divider()

    # Previous-day anchors
    anchors = get_prev_day_anchors(st.session_state.selected_symbol)
    if anchors:
        st.markdown("#### Previous Day Anchors")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High", f"{anchors['high']:.2f}")
        with col2:
            st.metric("Close", f"{anchors['close']:.2f}")
        with col3:
            st.metric("Low", f"{anchors['low']:.2f}")
        st.caption(f"From: {anchors['date']}")
    else:
        st.error("No anchor data available.")

# --- Hook into router ---
if st.session_state.page == "Overview":
    render_overview()

# ===========================================
# ============= PART 3 (DATA) ===============
# ===== SPX & EQUITIES DATA + ANCHORS ======
# ===========================================

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Optional, Tuple
import pandas as pd
import yfinance as yf
import streamlit as st

# ---- Shared constants (must match Part 1) ----
ET = ZoneInfo("America/New_York")
SPX_SYMBOL = "^GSPC"
RTH_START = time(8, 30)  # ET
RTH_END   = time(15, 30) # ET

# Keep your slope logic + new 5PM anchors
SPX_SLOPES_DOWN = {"HIGH": -0.2792, "CLOSE": -0.2792, "LOW": -0.2792, "5PM_LOW": -0.3171}
SPX_SLOPES_UP   = {"HIGH": +0.3171, "CLOSE": +0.3171, "LOW": +0.3171, "5PM_HIGH": +0.3171}

# Minimal equity universe (you can edit later)
EQUITY_UNIVERSE = ["AAPL", "MSFT", "NVDA", "META", "TSLA", "AMZN", "GOOGL", "SPY"]

# ---------- Core Yahoo helpers ----------

@st.cache_data(ttl=90, show_spinner=False)
def yf_intraday_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    1-minute bars from Yahoo within [start_dt, end_dt] (ET).
    Returns a tz-naive ET-indexed DataFrame with columns: Open, High, Low, Close, Volume, dt, Time, Date.
    """
    tkr = yf.Ticker(symbol)
    # Pull a slightly wider window to be safe
    start_pad = (start_dt - timedelta(days=1)).astimezone(ET)
    end_pad = (end_dt + timedelta(days=1)).astimezone(ET)
    df = tkr.history(start=start_pad, end=end_pad, interval="1m")
    if df is None or df.empty:
        return pd.DataFrame()

    # Normalize timezone to ET and slice exact window
    df = df.tz_convert(ET) if df.index.tzinfo else df.tz_localize(ET)
    df = df.loc[(df.index >= start_dt.astimezone(ET)) & (df.index <= end_dt.astimezone(ET))].copy()
    if df.empty:
        return pd.DataFrame()

    # Add helpers
    df["dt"] = df.index.tz_convert(ET).tz_localize(None)
    df["Time"] = df["dt"].dt.strftime("%H:%M")
    df["Date"] = df["dt"].dt.date
    return df

@st.cache_data(ttl=300, show_spinner=False)
def yf_daily(symbol: str, lookback_days: int = 30) -> pd.DataFrame:
    """
    Daily bars (1d) for lookback window. Returns tz-naive ET date index named 'Date'.
    """
    tkr = yf.Ticker(symbol)
    df = tkr.history(period=f"{max(lookback_days, 7)}d", interval="1d")
    if df is None or df.empty:
        return pd.DataFrame()
    # Normalize 'Date' column (naive ET date)
    out = df.copy()
    out = out.reset_index()
    date_col = "Date" if "Date" in out.columns else out.columns[0]
    out.rename(columns={date_col: "Date"}, inplace=True)
    out["Date"] = pd.to_datetime(out["Date"]).dt.tz_localize(None)
    out["DateOnly"] = out["Date"].dt.date
    return out

def _previous_trading_date(symbol: str, before_date: date) -> Optional[date]:
    daily = yf_daily(symbol, lookback_days=45)
    if daily.empty:
        return None
    prev = daily.loc[daily["DateOnly"] < before_date]
    if prev.empty:
        return None
    return prev.iloc[-1]["DateOnly"]

# --------- Anchor extraction (Prev Day OHLC) ----------

@st.cache_data(ttl=300, show_spinner=False)
def get_prev_day_ohlc_anchor(
    symbol: str,
    forecast_session: date,
    which: str  # "HIGH" | "CLOSE" | "LOW"
) -> Optional[Dict]:
    """
    Returns dict: {'date': prev_day, 'price': float, 'time': time, 'label': which}
    Time is a best-effort typical time (HIGH/LOW unknown intraday minute -> leave None).
    For CLOSE we use 16:00 as the canonical 'close' time.
    """
    prev_day = _previous_trading_date(symbol, forecast_session)
    if not prev_day:
        return None
    daily = yf_daily(symbol, lookback_days=45)
    row = daily.loc[daily["DateOnly"] == prev_day]
    if row.empty:
        return None

    price = None
    t_hint = None
    if which == "HIGH":
        price = float(row.iloc[0]["High"])
        # unknown intraday minute -> keep time None
    elif which == "LOW":
        price = float(row.iloc[0]["Low"])
    elif which == "CLOSE":
        price = float(row.iloc[0]["Close"])
        t_hint = time(16, 0)
    else:
        return None

    return {
        "date": prev_day,
        "price": round(float(price), 2),
        "time": t_hint,  # None for High/Low (unknown minute)
        "label": which
    }

# --------- Anchor extraction (5:00–5:29 PM candle) ----------

@st.cache_data(ttl=300, show_spinner=False)
def get_5pm_candle_anchor(
    symbol: str,
    forecast_session: date,
    candle_pick: str  # "5PM_HIGH" | "5PM_LOW"
) -> Optional[Dict]:
    """
    Uses previous trading day 5:00–5:29 PM ET window:
      - '5PM_HIGH' -> highest price in that 30-min window
      - '5PM_LOW'  -> lowest  price in that 30-min window
    Anchor time returned as 17:00.
    """
    prev_day = _previous_trading_date(symbol, forecast_session)
    if not prev_day:
        return None

    start_dt = datetime.combine(prev_day, time(17, 0), ET)
    end_dt   = datetime.combine(prev_day, time(17, 29, 59), ET)
    df_1m = yf_intraday_1m(symbol, start_dt, end_dt)
    if df_1m.empty:
        return None

    if candle_pick == "5PM_HIGH":
        px = float(df_1m["High"].max())
    elif candle_pick == "5PM_LOW":
        px = float(df_1m["Low"].min())
    else:
        return None

    return {
        "date": prev_day,
        "price": round(px, 2),
        "time": time(17, 0),
        "label": candle_pick
    }

# ---------- Unified anchor selector (SPX-focused) ----------

def select_spx_anchor(forecast_session: date) -> Optional[Dict]:
    """
    Minimal UI in sidebar to pick SPX anchor source & variant.
    Returns anchor dict or None. No extra markup.
    """
    with st.sidebar:
        src = st.selectbox(
            "Anchor source",
            ["Prev Day (High/Close/Low)", "5:00 PM Candle (High/Low)"],
            index=0,
            key="spx_anchor_src"
        )
        if src.startswith("Prev Day"):
            pick = st.selectbox("Which anchor", ["HIGH", "CLOSE", "LOW"], index=1, key="spx_anchor_pick")
            anchor = get_prev_day_ohlc_anchor(SPX_SYMBOL, forecast_session, pick)
        else:
            pick = st.selectbox("Which 5 PM anchor", ["5PM_HIGH", "5PM_LOW"], index=0, key="spx_5pm_pick")
            anchor = get_5pm_candle_anchor(SPX_SYMBOL, forecast_session, pick)

    # Persist to session (for Parts 4/5)
    if anchor:
        st.session_state["spx_anchor"] = anchor
        st.session_state["spx_anchor_source"] = src
    return anchor

# ---------- Convenience fetchers for other pages ----------

@st.cache_data(ttl=90, show_spinner=False)
def get_live_quote(symbol: str) -> Optional[Dict]:
    """
    Lightweight last bar snapshot (today). Returns dict with price and daily H/L/C if available.
    """
    tkr = yf.Ticker(symbol)
    intraday = tkr.history(period="1d", interval="1m")
    daily = tkr.history(period="6d", interval="1d")

    if intraday is None or intraday.empty:
        return None

    last = intraday.iloc[-1]
    price = float(last["Close"])
    out = {"symbol": symbol, "price": round(price, 2)}
    if daily is not None and not daily.empty:
        out.update({
            "today_high": round(float(daily.iloc[-1]["High"]), 2),
            "today_low": round(float(daily.iloc[-1]["Low"]), 2),
            "prev_close": round(float(daily.iloc[-2]["Close"]), 2) if len(daily) >= 2 else round(price, 2)
        })
    return out

# ---------- Part 3 minimal integration point ----------

def part3_bind_data_layer(forecast_session: date):
    """
    Call this once during page build (e.g., in Overview) to
    1) let user choose SPX anchor
    2) store anchor + source in session for later parts
    """
    _ = select_spx_anchor(forecast_session)