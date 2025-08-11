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