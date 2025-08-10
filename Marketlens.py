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
