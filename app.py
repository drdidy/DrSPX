"""
🔮 SPX PROPHET — Next Gen
"Where Structure Becomes Foresight."

Premium 0DTE Trading Terminal
Built for precision. Designed for conviction.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time as dtime
import pytz
import json
import os

# Local modules
from data_fetcher import (
    fetch_es_1min, fetch_es_30min, fetch_spx_price,
    fetch_es_price, get_es_spx_offset,
    fetch_prior_day_afternoon, fetch_1min_for_afternoon
)
from channel_builder import (
    auto_build_channels, build_channels, AnchorPoint,
    get_channel_values_at_time, get_projection_table, count_blocks
)
from cross_detector import get_monitor_state, check_line_proximity
from trade_logic import (
    assess_position_ascending_day, assess_position_descending_day,
    assess_asian_session, convert_es_to_spx, get_session_mode,
    PropFirmRisk, round_strike, format_spxw_ticker
)

CT = pytz.timezone("America/Chicago")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SPX Prophet",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════════════════
# STATE FILE (persist inputs across sessions)
# ═══════════════════════════════════════════════════════════════════════════════
STATE_FILE = "spx_prophet_state.json"

def save_state(state_dict):
    """Save persistent state to file."""
    try:
        serializable = {}
        for k, v in state_dict.items():
            if isinstance(v, (date, datetime)):
                serializable[k] = v.isoformat()
            else:
                serializable[k] = v
        with open(STATE_FILE, "w") as f:
            json.dump(serializable, f)
    except Exception:
        pass

def load_state():
    """Load persistent state from file."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# ═══════════════════════════════════════════════════════════════════════════════
# PREMIUM CSS — INSTITUTIONAL TRADING TERMINAL
# ═══════════════════════════════════════════════════════════════════════════════
def inject_premium_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Outfit:wght@300;400;500;600;700;800;900&family=Sora:wght@300;400;500;600;700;800&display=swap');

    :root {
        --bg-primary: #050a14;
        --bg-secondary: #0a1628;
        --bg-card: rgba(12, 24, 48, 0.65);
        --bg-card-hover: rgba(16, 32, 64, 0.75);
        --border-subtle: rgba(0, 200, 255, 0.08);
        --border-active: rgba(0, 200, 255, 0.2);
        --text-primary: #e8f0ff;
        --text-secondary: #7a8baa;
        --text-muted: #4a5570;
        --cyan: #00c8ff;
        --cyan-glow: rgba(0, 200, 255, 0.15);
        --gold: #ffd700;
        --gold-glow: rgba(255, 215, 0, 0.12);
        --green: #00e88f;
        --green-glow: rgba(0, 232, 143, 0.12);
        --red: #ff4466;
        --red-glow: rgba(255, 68, 102, 0.12);
        --purple: #a78bfa;
        --orange: #ff8c42;
    }

    /* ══════ GLOBAL RESET ══════ */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        background: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        font-family: 'Outfit', sans-serif !important;
    }

    [data-testid="stAppViewContainer"]::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background:
            radial-gradient(ellipse 900px 600px at 10% 0%, rgba(0, 200, 255, 0.04), transparent),
            radial-gradient(ellipse 800px 500px at 90% 100%, rgba(255, 215, 0, 0.03), transparent),
            radial-gradient(circle 600px at 50% 50%, rgba(167, 139, 250, 0.02), transparent);
        pointer-events: none;
        z-index: 0;
    }

    [data-testid="stHeader"] {
        background: transparent !important;
    }

    [data-testid="stMainBlockContainer"] {
        max-width: 1400px;
        padding-top: 1rem !important;
    }

    /* ══════ SCROLLBAR ══════ */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-primary); }
    ::-webkit-scrollbar-thumb {
        background: rgba(0, 200, 255, 0.2);
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover { background: rgba(0, 200, 255, 0.35); }

    /* ══════ SIDEBAR ══════ */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #060e1e 0%, #0a1628 50%, #060e1e 100%) !important;
        border-right: 1px solid var(--border-subtle) !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdown"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdown"] label,
    [data-testid="stSidebar"] label {
        color: var(--text-secondary) !important;
        font-family: 'Outfit', sans-serif !important;
        font-size: 0.82rem !important;
    }

    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stNumberInput label,
    [data-testid="stSidebar"] .stDateInput label,
    [data-testid="stSidebar"] .stRadio label {
        color: var(--cyan) !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.72rem !important;
    }

    [data-testid="stSidebar"] .stSelectbox > div > div,
    [data-testid="stSidebar"] input {
        background: rgba(0, 200, 255, 0.04) !important;
        border: 1px solid var(--border-subtle) !important;
        color: var(--text-primary) !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    [data-testid="stSidebar"] .stSelectbox > div > div:focus-within,
    [data-testid="stSidebar"] input:focus {
        border-color: var(--cyan) !important;
        box-shadow: 0 0 12px var(--cyan-glow) !important;
    }

    /* Sidebar divider */
    [data-testid="stSidebar"] hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, var(--border-active), transparent) !important;
        margin: 1.2rem 0 !important;
    }

    /* ══════ BUTTONS ══════ */
    .stButton > button {
        background: linear-gradient(135deg, rgba(0, 200, 255, 0.12), rgba(0, 200, 255, 0.04)) !important;
        border: 1px solid rgba(0, 200, 255, 0.25) !important;
        color: var(--cyan) !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.04em !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(0, 200, 255, 0.22), rgba(0, 200, 255, 0.08)) !important;
        border-color: var(--cyan) !important;
        box-shadow: 0 0 20px var(--cyan-glow), 0 4px 15px rgba(0, 0, 0, 0.3) !important;
        transform: translateY(-1px) !important;
    }

    /* ══════ RADIO BUTTONS ══════ */
    .stRadio > div {
        gap: 0.5rem !important;
    }
    .stRadio > div > label {
        background: rgba(0, 200, 255, 0.04) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.8rem !important;
        transition: all 0.2s ease !important;
    }
    .stRadio > div > label:hover {
        border-color: var(--border-active) !important;
        background: rgba(0, 200, 255, 0.08) !important;
    }

    /* ══════ DATAFRAME / TABLE ══════ */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border-subtle) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }

    /* ══════ TABS ══════ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: rgba(0, 200, 255, 0.03);
        border-radius: 10px;
        padding: 4px;
        border: 1px solid var(--border-subtle);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: var(--text-secondary);
        font-family: 'Outfit', sans-serif;
        font-weight: 500;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(0, 200, 255, 0.1) !important;
        color: var(--cyan) !important;
    }

    /* ══════ EXPANDER ══════ */
    .streamlit-expanderHeader {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 10px !important;
        color: var(--text-primary) !important;
        font-family: 'Outfit', sans-serif !important;
    }

    /* ══════ METRIC ══════ */
    [data-testid="stMetric"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        color: var(--text-primary) !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        font-family: 'Outfit', sans-serif !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.72rem !important;
    }

    /* Hide default Streamlit elements */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stToolbar"] { display: none; }

    /* ══════ CUSTOM CARD SYSTEM ══════ */
    .prophet-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        backdrop-filter: blur(20px);
        transition: all 0.3s ease;
    }
    .prophet-card:hover {
        border-color: var(--border-active);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 1px var(--border-active);
    }

    .card-label {
        font-family: 'Outfit', sans-serif;
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--text-muted);
        margin-bottom: 0.4rem;
    }

    .card-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.1;
    }

    .card-sub {
        font-family: 'Outfit', sans-serif;
        font-size: 0.78rem;
        color: var(--text-secondary);
        margin-top: 0.3rem;
    }

    /* ══════ HERO BANNER ══════ */
    .hero-container {
        text-align: center;
        padding: 2rem 0 1.5rem 0;
        position: relative;
    }

    .hero-orb {
        width: 64px;
        height: 64px;
        margin: 0 auto 1rem;
        border-radius: 50%;
        background: radial-gradient(circle at 35% 35%,
            rgba(0, 200, 255, 0.6),
            rgba(0, 200, 255, 0.2) 40%,
            rgba(167, 139, 250, 0.15) 70%,
            transparent);
        box-shadow:
            0 0 40px rgba(0, 200, 255, 0.2),
            0 0 80px rgba(0, 200, 255, 0.08),
            inset 0 0 20px rgba(255, 255, 255, 0.05);
        animation: orbPulse 4s ease-in-out infinite;
    }

    @keyframes orbPulse {
        0%, 100% {
            transform: scale(1);
            box-shadow: 0 0 40px rgba(0, 200, 255, 0.2), 0 0 80px rgba(0, 200, 255, 0.08);
        }
        50% {
            transform: scale(1.05);
            box-shadow: 0 0 50px rgba(0, 200, 255, 0.3), 0 0 100px rgba(0, 200, 255, 0.12);
        }
    }

    .hero-title {
        font-family: 'Sora', sans-serif;
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #e8f0ff 0%, #00c8ff 50%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
        margin-bottom: 0.2rem;
    }

    .hero-tagline {
        font-family: 'Outfit', sans-serif;
        font-size: 0.85rem;
        font-weight: 400;
        color: var(--text-muted);
        letter-spacing: 0.15em;
        text-transform: uppercase;
    }

    /* ══════ STATUS BADGE ══════ */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.05em;
    }

    .status-live {
        background: rgba(0, 232, 143, 0.1);
        border: 1px solid rgba(0, 232, 143, 0.25);
        color: var(--green);
    }

    .status-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--green);
        animation: dotPulse 2s ease-in-out infinite;
    }

    @keyframes dotPulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }

    /* ══════ SIGNAL CARD ══════ */
    .signal-card {
        background: var(--bg-card);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin: 1rem 0;
        position: relative;
        overflow: hidden;
    }

    .signal-calls {
        border: 1px solid rgba(0, 232, 143, 0.2);
        box-shadow: 0 0 30px rgba(0, 232, 143, 0.05);
    }
    .signal-calls::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--green), transparent);
    }

    .signal-puts {
        border: 1px solid rgba(255, 68, 102, 0.2);
        box-shadow: 0 0 30px rgba(255, 68, 102, 0.05);
    }
    .signal-puts::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--red), transparent);
    }

    .signal-long {
        border: 1px solid rgba(0, 232, 143, 0.2);
        box-shadow: 0 0 30px rgba(0, 232, 143, 0.05);
    }
    .signal-long::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--green), transparent);
    }

    .signal-short {
        border: 1px solid rgba(255, 68, 102, 0.2);
        box-shadow: 0 0 30px rgba(255, 68, 102, 0.05);
    }
    .signal-short::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--red), transparent);
    }

    .signal-direction {
        font-family: 'Sora', sans-serif;
        font-size: 1.4rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }

    .signal-entry {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2rem;
        font-weight: 700;
    }

    .signal-meta {
        font-family: 'Outfit', sans-serif;
        font-size: 0.82rem;
        color: var(--text-secondary);
        margin-top: 0.5rem;
    }

    .signal-strike {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1rem;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
        margin-top: 0.5rem;
    }

    .strike-call {
        background: rgba(0, 232, 143, 0.1);
        color: var(--green);
        border: 1px solid rgba(0, 232, 143, 0.2);
    }

    .strike-put {
        background: rgba(255, 68, 102, 0.1);
        color: var(--red);
        border: 1px solid rgba(255, 68, 102, 0.2);
    }

    /* ══════ CROSS MONITOR ══════ */
    .cross-monitor {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        padding: 1.5rem;
    }

    .cross-status-ready {
        color: var(--gold);
    }

    .cross-status-watching {
        color: var(--text-secondary);
    }

    .cross-status-valid {
        color: var(--green);
        animation: crossFlash 1s ease-in-out 3;
    }

    .cross-status-invalid {
        color: var(--red);
    }

    @keyframes crossFlash {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* ══════ ZONE INDICATOR ══════ */
    .zone-bar {
        width: 100%;
        height: 140px;
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        position: relative;
        overflow: hidden;
        margin: 1rem 0;
    }

    .zone-section {
        position: absolute;
        left: 0; right: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .zone-asc {
        background: rgba(0, 232, 143, 0.06);
        color: rgba(0, 232, 143, 0.6);
        border-bottom: 1px solid rgba(0, 232, 143, 0.15);
    }

    .zone-between {
        background: rgba(255, 215, 0, 0.04);
        color: rgba(255, 215, 0, 0.5);
    }

    .zone-desc {
        background: rgba(255, 68, 102, 0.06);
        color: rgba(255, 68, 102, 0.6);
        border-top: 1px solid rgba(255, 68, 102, 0.15);
    }

    .zone-marker {
        position: absolute;
        left: 50%;
        transform: translateX(-50%);
        width: 8px;
        height: 8px;
        background: var(--cyan);
        border-radius: 50%;
        box-shadow: 0 0 10px rgba(0, 200, 255, 0.5);
        z-index: 10;
    }

    /* ══════ PROP FIRM RISK ══════ */
    .risk-bar {
        width: 100%;
        height: 8px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 4px;
        overflow: hidden;
        margin-top: 0.5rem;
    }

    .risk-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.5s ease;
    }

    .risk-clear { background: var(--green); }
    .risk-active { background: var(--cyan); }
    .risk-caution { background: var(--orange); }
    .risk-danger { background: var(--red); }

    /* ══════ STRENGTH BADGE ══════ */
    .strength-strong {
        background: rgba(0, 232, 143, 0.1);
        color: var(--green);
        border: 1px solid rgba(0, 232, 143, 0.2);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }
    .strength-standard {
        background: rgba(0, 200, 255, 0.1);
        color: var(--cyan);
        border: 1px solid rgba(0, 200, 255, 0.2);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }
    .strength-caution {
        background: rgba(255, 140, 66, 0.1);
        color: var(--orange);
        border: 1px solid rgba(255, 140, 66, 0.2);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }

    /* ══════ DAY TYPE TOGGLE ══════ */
    .day-asc {
        background: linear-gradient(135deg, rgba(0, 232, 143, 0.08), rgba(0, 232, 143, 0.02));
        border: 1px solid rgba(0, 232, 143, 0.2);
        padding: 0.6rem 1.2rem;
        border-radius: 10px;
        text-align: center;
    }
    .day-desc {
        background: linear-gradient(135deg, rgba(255, 68, 102, 0.08), rgba(255, 68, 102, 0.02));
        border: 1px solid rgba(255, 68, 102, 0.2);
        padding: 0.6rem 1.2rem;
        border-radius: 10px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def render_hero():
    """Render the animated hero banner."""
    st.markdown("""
    <div class="hero-container">
        <div class="hero-orb"></div>
        <div class="hero-title">SPX PROPHET</div>
        <div class="hero-tagline">Where Structure Becomes Foresight</div>
    </div>
    """, unsafe_allow_html=True)


def render_live_bar(es_price, spx_price, offset, session_mode):
    """Render the live price bar with session indicator."""
    session_labels = {
        "asian": "ASIAN SESSION",
        "pre_rth": "PRE-MARKET",
        "rth": "RTH ACTIVE",
        "afternoon": "AFTERNOON",
        "off": "MARKET CLOSED"
    }
    session_label = session_labels.get(session_mode, "—")
    now_ct = datetime.now(CT)

    st.markdown(f"""
    <div class="prophet-card" style="padding: 1rem 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.8rem;">
            <div>
                <span class="status-badge status-live"><span class="status-dot"></span>{session_label}</span>
            </div>
            <div style="display: flex; gap: 2rem; align-items: center;">
                <div>
                    <div class="card-label">ES FUTURES</div>
                    <div class="card-value" style="font-size: 1.3rem; color: var(--cyan);">{es_price:,.2f}</div>
                </div>
                <div>
                    <div class="card-label">SPX INDEX</div>
                    <div class="card-value" style="font-size: 1.3rem; color: var(--text-primary);">{spx_price:,.2f}</div>
                </div>
                <div>
                    <div class="card-label">ES-SPX OFFSET</div>
                    <div class="card-value" style="font-size: 1.3rem; color: var(--purple);">{offset:+.2f}</div>
                </div>
                <div>
                    <div class="card-label">TIME (CT)</div>
                    <div class="card-value" style="font-size: 1.3rem; color: var(--text-secondary);">{now_ct.strftime("%I:%M %p")}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_day_type_indicator(day_type):
    """Render the current day type indicator."""
    if day_type == "ascending":
        st.markdown("""
        <div class="day-asc">
            <div class="card-label" style="color: rgba(0, 232, 143, 0.6);">TODAY'S CHANNEL</div>
            <div style="font-family: 'Sora', sans-serif; font-size: 1.3rem; font-weight: 800; color: var(--green);">
                ▲ ASCENDING DAY
            </div>
            <div class="card-sub">Active channel: Ascending | Ascending floor = primary buy zone</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="day-desc">
            <div class="card-label" style="color: rgba(255, 68, 102, 0.6);">TODAY'S CHANNEL</div>
            <div style="font-family: 'Sora', sans-serif; font-size: 1.3rem; font-weight: 800; color: var(--red);">
                ▼ DESCENDING DAY
            </div>
            <div class="card-sub">Active channel: Descending | Descending ceiling = primary sell zone</div>
        </div>
        """, unsafe_allow_html=True)


def render_channel_values(channel_vals, is_es=True):
    """Render current channel projected values."""
    unit = "ES" if is_es else "SPX"
    asc_ext = f"{channel_vals['asc_extreme']:,.2f}" if channel_vals.get('asc_extreme') else "—"
    asc_ceil = f"{channel_vals['asc_ceiling']:,.2f}"
    asc_flr = f"{channel_vals['asc_floor']:,.2f}"
    desc_ceil = f"{channel_vals['desc_ceiling']:,.2f}"
    desc_flr = f"{channel_vals['desc_floor']:,.2f}"
    desc_ext = f"{channel_vals['desc_extreme']:,.2f}" if channel_vals.get('desc_extreme') else "—"

    st.markdown(f"""
    <div class="prophet-card">
        <div class="card-label">CHANNEL PROJECTIONS — {unit} VALUES</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 0.8rem;">
            <div style="border-left: 3px solid var(--green); padding-left: 1rem;">
                <div class="card-label" style="color: var(--green);">ASCENDING CHANNEL</div>
                <div style="display: flex; justify-content: space-between; margin-top: 0.4rem;">
                    <span class="card-sub">Extreme</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: rgba(0, 232, 143, 0.5); font-size: 0.9rem;">
                        {asc_ext}
                    </span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span class="card-sub">Ceiling</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: var(--green); font-size: 0.9rem; font-weight: 600;">
                        {asc_ceil}
                    </span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span class="card-sub">Floor</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: var(--green); font-size: 0.9rem; font-weight: 600;">
                        {asc_flr}
                    </span>
                </div>
            </div>
            <div style="border-left: 3px solid var(--red); padding-left: 1rem;">
                <div class="card-label" style="color: var(--red);">DESCENDING CHANNEL</div>
                <div style="display: flex; justify-content: space-between; margin-top: 0.4rem;">
                    <span class="card-sub">Ceiling</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: var(--red); font-size: 0.9rem; font-weight: 600;">
                        {desc_ceil}
                    </span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span class="card-sub">Floor</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: var(--red); font-size: 0.9rem; font-weight: 600;">
                        {desc_flr}
                    </span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span class="card-sub">Extreme</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: rgba(255, 68, 102, 0.5); font-size: 0.9rem;">
                        {desc_ext}
                    </span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_scenario_card(scenario, trading_date=None):
    """Render a trade scenario card with full trade management details."""
    from trade_logic import format_spxw_ticker
    is_bullish = scenario.direction in ("CALLS", "LONG ES")

    if is_bullish:
        signal_class = "signal-calls" if scenario.direction == "CALLS" else "signal-long"
        dir_color = "var(--green)"
        strike_class = "strike-call"
    else:
        signal_class = "signal-puts" if scenario.direction == "PUTS" else "signal-short"
        dir_color = "var(--red)"
        strike_class = "strike-put"

    strength_class = f"strength-{scenario.strength.lower()}"
    primary_label = "PRIMARY" if scenario.is_primary else "ALTERNATE"

    # Build target HTML
    target_html = ""
    if scenario.target_level:
        target_html = (
            f'<div style="margin-top: 0.5rem;">'
            f'<span class="card-sub">Target: </span>'
            f'<span style="font-family: JetBrains Mono, monospace; color: {dir_color};">{scenario.target_level:,.2f}</span>'
            f'<span class="card-sub"> ({scenario.target_label})</span>'
            f'</div>'
        )

    # Build stop loss HTML
    sl_html = ""
    sl = getattr(scenario, 'stop_loss', None)
    if sl:
        sl_html = (
            f'<div style="margin-top: 0.3rem;">'
            f'<span class="card-sub">Stop Loss: </span>'
            f'<span style="font-family: JetBrains Mono, monospace; color: var(--red); font-weight: 600;">{sl:,.2f}</span>'
            f'</div>'
        )

    # Build take profit HTML
    tp_html = ""
    tp1 = getattr(scenario, 'take_profit_1', None)
    tp2 = getattr(scenario, 'take_profit_2', None)
    tp3 = getattr(scenario, 'take_profit_3', None)
    if tp1:
        tp_html = (
            f'<div style="display: flex; gap: 1rem; margin-top: 0.3rem; flex-wrap: wrap;">'
            f'<div><span class="card-sub">TP1 (25%): </span>'
            f'<span style="font-family: JetBrains Mono, monospace; color: var(--gold); font-size: 0.85rem;">{tp1:,.2f}</span></div>'
            f'<div><span class="card-sub">TP2 (50%): </span>'
            f'<span style="font-family: JetBrains Mono, monospace; color: var(--gold); font-size: 0.85rem;">{tp2:,.2f}</span></div>'
            f'<div><span class="card-sub">TP3 (75%): </span>'
            f'<span style="font-family: JetBrains Mono, monospace; color: var(--gold); font-size: 0.85rem;">{tp3:,.2f}</span></div>'
            f'</div>'
        )

    # Build strike + contract HTML
    strike_html = ""
    if scenario.strike and scenario.direction in ("CALLS", "PUTS"):
        is_call = scenario.direction == "CALLS"
        if trading_date is None:
            trading_date = date.today()
        ticker = format_spxw_ticker(scenario.strike, trading_date, is_call)
        strike_html = (
            f'<div style="margin-top: 0.8rem; padding-top: 0.8rem; border-top: 1px solid var(--border-subtle);">'
            f'<div style="display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap;">'
            f'<div><span class="card-sub">Strike: </span>'
            f'<span class="signal-strike {strike_class}">{scenario.strike}</span></div>'
            f'<div><span class="card-sub">Contract: </span>'
            f'<span style="font-family: JetBrains Mono, monospace; color: var(--cyan); font-size: 0.8rem;">{ticker}</span></div>'
            f'</div></div>'
        )

    st.markdown(
        f'<div class="signal-card {signal_class}">'
        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
        f'<div><span class="{strength_class}">{scenario.strength}</span>'
        f'<span style="margin-left: 8px; font-size: 0.7rem; color: var(--text-muted);">{primary_label}</span></div></div>'
        f'<div style="margin-top: 0.8rem;">'
        f'<span class="signal-direction" style="color: {dir_color};">{scenario.direction}</span>'
        f'<span style="color: var(--text-muted); font-size: 0.85rem; margin-left: 0.5rem;">at</span></div>'
        f'<div class="signal-entry" style="color: {dir_color}; margin-top: 0.3rem;">{scenario.entry_level:,.2f}</div>'
        f'<div class="card-sub">{scenario.entry_label}</div>'
        f'<div class="signal-meta">{scenario.rationale}</div>'
        f'{target_html}'
        f'{sl_html}'
        f'{tp_html}'
        f'{strike_html}'
        f'</div>',
        unsafe_allow_html=True
    )


def render_cross_monitor(state):
    """Render the 8/50 EMA cross monitor."""
    if "VALID" in state.status:
        status_class = "cross-status-valid"
    elif state.status == "READY":
        status_class = "cross-status-ready"
    elif "INVALID" in state.status:
        status_class = "cross-status-invalid"
    else:
        status_class = "cross-status-watching"

    spread_color = "var(--green)" if state.current_spread > 0 else "var(--red)"
    div_pct = min(100, (state.max_divergence_since_last_cross / 10.0) * 100)

    st.markdown(f"""
    <div class="cross-monitor">
        <div class="card-label">8 / 50 EMA CROSS MONITOR — ES 1-MIN</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-top: 1rem;">
            <div>
                <div class="card-sub">Spread (8 - 50)</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 700; color: {spread_color};">
                    {state.current_spread:+.1f}
                </div>
            </div>
            <div>
                <div class="card-sub">Max Divergence</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 700; color: {'var(--gold)' if state.is_diverged_enough else 'var(--text-muted)'};">
                    {state.max_divergence_since_last_cross:.1f}
                </div>
                <div class="risk-bar" style="margin-top: 0.3rem;">
                    <div class="risk-fill {'risk-clear' if state.is_diverged_enough else 'risk-active'}" style="width: {div_pct}%;"></div>
                </div>
                <div class="card-sub" style="font-size: 0.65rem;">{'✓ THRESHOLD MET' if state.is_diverged_enough else f'Need 10+ pts'}</div>
            </div>
            <div>
                <div class="card-sub">Status</div>
                <div class="{status_class}" style="font-family: 'Sora', sans-serif; font-size: 1rem; font-weight: 700;">
                    {state.status}
                </div>
            </div>
        </div>
        <div style="margin-top: 1rem; padding-top: 0.8rem; border-top: 1px solid var(--border-subtle);">
            <div class="card-sub">{state.status_detail}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_prop_firm_panel(risk: PropFirmRisk):
    """Render prop firm risk management panel."""
    risk_color_map = {
        "CLEAR": "risk-clear",
        "ACTIVE": "risk-active",
        "CAUTION": "risk-caution",
        "DANGER": "risk-danger",
        "LIMIT HIT": "risk-danger"
    }
    risk_class = risk_color_map.get(risk.risk_status, "risk-active")

    st.markdown(f"""
    <div class="prophet-card">
        <div class="card-label">THE FUTURES DESK — RISK MANAGEMENT</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-top: 0.8rem;">
            <div>
                <div class="card-sub">Max Contracts</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1rem; color: var(--text-primary);">
                    {risk.max_es_contracts} ES / {risk.max_mes_contracts} MES
                </div>
            </div>
            <div>
                <div class="card-sub">Daily Loss Limit</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1rem; color: var(--red);">
                    ${risk.daily_loss_limit:,.0f}
                </div>
            </div>
            <div>
                <div class="card-sub">Risk Used</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1rem; color: {'var(--green)' if risk.risk_pct < 50 else 'var(--red)'};">
                    {risk.risk_pct:.0f}%
                </div>
                <div class="risk-bar">
                    <div class="risk-fill {risk_class}" style="width: {risk.risk_pct}%;"></div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    inject_premium_css()
    render_hero()

    # ─── SIDEBAR ───
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 1rem;">
            <div style="font-family: 'Sora', sans-serif; font-size: 1.1rem; font-weight: 700;
                 background: linear-gradient(135deg, #00c8ff, #a78bfa);
                 -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                COMMAND CENTER
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Trading date — this is the day you're TRADING (today)
        trading_date = st.date_input(
            "TRADING DATE (today)",
            value=date.today(),
            help="The day you are trading. The app will automatically use the prior trading day's 12-3 PM data for channel construction. Weekends are skipped (Monday uses Friday)."
        )

        # Show which prior day will be used
        prior = trading_date - timedelta(days=1)
        while prior.weekday() >= 5:  # Skip Sat/Sun
            prior -= timedelta(days=1)
        st.markdown(f"""
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: var(--text-muted);
             padding: 0.3rem 0;">
            Channel source: {prior.strftime('%A, %b %d')} 12-3 PM
        </div>
        """, unsafe_allow_html=True)

        # Day type toggle
        st.markdown("---")
        day_type = st.radio(
            "TODAY'S DAY TYPE",
            options=["ASCENDING", "DESCENDING"],
            index=0,
            horizontal=True
        )
        day_type_lower = day_type.lower()

        st.markdown("---")

        # Manual overrides
        st.markdown("#### MANUAL OVERRIDES")

        use_manual_anchors = st.checkbox("Manual Channel Anchors", value=False)

        if use_manual_anchors:
            st.markdown("##### Anchor Points (ES values)")
            man_lowest_bounce = st.number_input("Lowest Bounce (12-3 PM)", value=0.0, format="%.2f", key="lb")
            man_lb_hour = st.number_input("└ Hour (CT)", min_value=12, max_value=15, value=13, key="lb_h")
            man_lb_min = st.number_input("└ Minute", min_value=0, max_value=59, value=30, key="lb_m")

            man_highest_rej = st.number_input("Highest Rejection (12-3 PM)", value=0.0, format="%.2f", key="hr")
            man_hr_hour = st.number_input("└ Hour (CT)", min_value=12, max_value=15, value=14, key="hr_h")
            man_hr_min = st.number_input("└ Minute", min_value=0, max_value=59, value=0, key="hr_m")

            man_highest_wick = st.number_input("Highest Wick (12-3 PM)", value=0.0, format="%.2f", key="hw")
            man_hw_hour = st.number_input("└ Hour (CT)", min_value=12, max_value=15, value=13, key="hw_h")
            man_hw_min = st.number_input("└ Minute", min_value=0, max_value=59, value=0, key="hw_m")

            man_lowest_wick = st.number_input("Lowest Wick (12-3 PM)", value=0.0, format="%.2f", key="lw")
            man_lw_hour = st.number_input("└ Hour (CT)", min_value=12, max_value=15, value=14, key="lw_h")
            man_lw_min = st.number_input("└ Minute", min_value=0, max_value=59, value=30, key="lw_m")

        st.markdown("---")

        # ES-SPX offset override
        auto_offset = st.checkbox("Auto-detect ES-SPX offset", value=True)
        if not auto_offset:
            manual_offset = st.number_input("Manual ES-SPX Offset", value=10.0, format="%.2f")

        st.markdown("---")

        # Refresh button
        if st.button("🔄 REFRESH DATA", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        # Auto refresh toggle
        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

    # ─── FETCH DATA ───
    with st.spinner("Loading market data..."):
        es_price = fetch_es_price()
        spx_price = fetch_spx_price()

        if auto_offset:
            offset = get_es_spx_offset()
        else:
            offset = manual_offset

        session_mode = get_session_mode()
        es_1min = fetch_es_1min()

    # ─── LIVE BAR ───
    render_live_bar(es_price, spx_price, offset, session_mode)

    # ─── BUILD CHANNELS ───
    channels = None

    if use_manual_anchors and man_lowest_bounce > 0 and man_highest_rej > 0:
        # Use manual anchors
        prior_date = trading_date - timedelta(days=1)
        try:
            lb_anchor = AnchorPoint(
                price=man_lowest_bounce,
                timestamp=CT.localize(datetime.combine(prior_date, dtime(man_lb_hour, man_lb_min))),
                label="Lowest Bounce"
            )
            hr_anchor = AnchorPoint(
                price=man_highest_rej,
                timestamp=CT.localize(datetime.combine(prior_date, dtime(man_hr_hour, man_hr_min))),
                label="Highest Rejection"
            )
            hw_anchor = AnchorPoint(
                price=man_highest_wick if man_highest_wick > 0 else man_highest_rej,
                timestamp=CT.localize(datetime.combine(prior_date, dtime(man_hw_hour, man_hw_min))),
                label="Highest Wick"
            )
            lw_anchor = AnchorPoint(
                price=man_lowest_wick if man_lowest_wick > 0 else man_lowest_bounce,
                timestamp=CT.localize(datetime.combine(prior_date, dtime(man_lw_hour, man_lw_min))),
                label="Lowest Wick"
            )
            channels = build_channels(lb_anchor, hr_anchor, hw_anchor, lw_anchor)
        except Exception as e:
            st.error(f"Error building channels from manual inputs: {e}")
    else:
        # Auto-detect from yfinance data
        with st.spinner("Detecting channel anchors from prior day..."):
            df_1min = fetch_1min_for_afternoon(trading_date)
            df_30min = fetch_prior_day_afternoon(trading_date)
            if not df_1min.empty:
                channels = auto_build_channels(df_1min, df_30min)

    if channels is None:
        st.markdown("""
        <div class="prophet-card" style="text-align: center; padding: 2rem;">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">⚠️</div>
            <div style="font-family: 'Outfit', sans-serif; color: var(--gold); font-size: 1rem; font-weight: 600;">
                NO CHANNEL DATA DETECTED
            </div>
            <div class="card-sub" style="margin-top: 0.5rem;">
                Enable "Manual Channel Anchors" in the sidebar to input prior day's 12-3 PM levels,
                or wait for market data to become available.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ─── DAY TYPE INDICATOR ───
    render_day_type_indicator(day_type_lower)

    # ─── GET CURRENT CHANNEL VALUES ───
    now_ct = datetime.now(CT)
    es_channel_vals = get_channel_values_at_time(channels, now_ct)

    # ─── SESSION-BASED DISPLAY ───
    tab_asian, tab_rth, tab_projection = st.tabs(["🌏 ASIAN SESSION", "📈 RTH SESSION", "📊 PROJECTIONS"])

    # ═══ ASIAN SESSION TAB ═══
    with tab_asian:
        st.markdown("")
        render_channel_values(es_channel_vals, is_es=True)

        # Asian session position assessment
        if es_price > 0:
            asian_assessment = assess_asian_session(es_price, es_channel_vals)

            # Zone indicator
            st.markdown(f"""
            <div class="prophet-card">
                <div class="card-label">POSITION — ES @ {es_price:,.2f}</div>
                <div style="font-family: 'Sora', sans-serif; font-size: 1.1rem; font-weight: 700;
                     color: var(--cyan); margin-top: 0.5rem;">
                    {asian_assessment.zone_label}
                </div>
                <div class="card-sub">
                    Nearest line: {asian_assessment.nearest_line} ({asian_assessment.nearest_distance:.2f} pts away)
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Scenarios
            for scenario in asian_assessment.scenarios:
                render_scenario_card(scenario)

            # Prop firm risk panel
            prop_risk = PropFirmRisk()
            render_prop_firm_panel(prop_risk)

    # ═══ RTH SESSION TAB ═══
    with tab_rth:
        st.markdown("")

        # Convert to SPX values
        spx_channel_vals = convert_es_to_spx(es_channel_vals, offset)
        render_channel_values(spx_channel_vals, is_es=False)

        # RTH position assessment
        price_for_rth = spx_price if spx_price > 0 else (es_price - offset if es_price > 0 else 0)

        if price_for_rth > 0:
            if day_type_lower == "ascending":
                rth_assessment = assess_position_ascending_day(price_for_rth, spx_channel_vals)
            else:
                rth_assessment = assess_position_descending_day(price_for_rth, spx_channel_vals)

            st.markdown(f"""
            <div class="prophet-card">
                <div class="card-label">POSITION — SPX @ {price_for_rth:,.2f}</div>
                <div style="font-family: 'Sora', sans-serif; font-size: 1.1rem; font-weight: 700;
                     color: var(--cyan); margin-top: 0.5rem;">
                    {rth_assessment.zone_label}
                </div>
                <div class="card-sub">
                    Nearest line: {rth_assessment.nearest_line} ({rth_assessment.nearest_distance:.2f} pts away)
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Scenarios with SPX strikes
            for scenario in rth_assessment.scenarios:
                render_scenario_card(scenario, trading_date=trading_date)

    # ═══ PROJECTIONS TAB ═══
    with tab_projection:
        st.markdown("")
        st.markdown("""
        <div class="card-label" style="margin-bottom: 0.5rem;">CHANNEL PROJECTION TABLE — ES VALUES</div>
        """, unsafe_allow_html=True)

        # Determine projection window
        if session_mode in ("asian", "off"):
            # Project from 6 PM to next day 11:30 AM
            start_proj = CT.localize(datetime.combine(trading_date, dtime(18, 0)))
            end_proj = CT.localize(datetime.combine(trading_date + timedelta(days=1), dtime(11, 30)))
        else:
            # Project from 8:30 AM to 3 PM today
            start_proj = CT.localize(datetime.combine(trading_date, dtime(8, 30)))
            end_proj = CT.localize(datetime.combine(trading_date, dtime(15, 0)))

        proj_table = get_projection_table(channels, start_proj, end_proj, interval_minutes=30)
        st.dataframe(
            proj_table,
            use_container_width=True,
            hide_index=True,
            height=500
        )

        # SPX conversion table
        if offset != 0:
            st.markdown("""
            <div class="card-label" style="margin: 1rem 0 0.5rem;">CHANNEL PROJECTION TABLE — SPX VALUES (offset applied)</div>
            """, unsafe_allow_html=True)

            spx_proj = proj_table.copy()
            for col in ["Asc Extreme", "Asc Ceiling", "Asc Floor", "Desc Ceiling", "Desc Floor", "Desc Extreme"]:
                spx_proj[col] = spx_proj[col].apply(
                    lambda x: round(float(x) - offset, 2) if x != "—" and x != "-" else x
                )
            st.dataframe(
                spx_proj,
                use_container_width=True,
                hide_index=True,
                height=500
            )

    # ─── CROSS MONITOR (always visible) ───
    st.markdown("")
    st.markdown("""
    <div class="card-label" style="margin: 1.5rem 0 0.5rem; font-size: 0.75rem;">ENTRY CONFIRMATION</div>
    """, unsafe_allow_html=True)

    if not es_1min.empty:
        cross_state = get_monitor_state(es_1min)

        # Check line proximity for cross validation
        if es_price > 0:
            nearby_line = check_line_proximity(es_price, es_channel_vals, proximity_threshold=5.0)
            if nearby_line and "CROSS" in cross_state.status:
                cross_state.status_detail += f" | Price near {nearby_line} — LINE TOUCH CONFIRMED ✓"

        render_cross_monitor(cross_state)

        # Recent crosses log
        if cross_state.recent_crosses:
            with st.expander("📋 Recent Cross History"):
                for cx in reversed(cross_state.recent_crosses):
                    validity = "✅ VALID" if cx.is_valid else "❌ INVALID"
                    st.markdown(f"""
                    <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle);
                         font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;">
                        <span style="color: {'var(--green)' if cx.cross_type == 'bullish' else 'var(--red)'};">
                            {'▲ BULL' if cx.cross_type == 'bullish' else '▼ BEAR'}
                        </span>
                        &nbsp;{cx.timestamp.strftime('%I:%M %p')} &nbsp;|&nbsp;
                        Div: {cx.divergence:.1f} &nbsp;|&nbsp;
                        Near: {cx.nearest_hour} &nbsp;|&nbsp;
                        {validity}
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="cross-monitor">
            <div class="card-label">8 / 50 EMA CROSS MONITOR</div>
            <div class="card-sub" style="margin-top: 0.5rem;">Waiting for ES 1-min data...</div>
        </div>
        """, unsafe_allow_html=True)

    # ─── ANCHOR POINTS DEBUG ───
    with st.expander("🔧 Channel Anchor Points"):
        for ap in channels.anchor_points:
            st.markdown(f"""
            <div style="padding: 0.4rem 0; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;">
                <span style="color: var(--cyan);">{ap.label}</span> &nbsp;|&nbsp;
                <span style="color: var(--text-primary);">{ap.price:,.2f}</span> &nbsp;|&nbsp;
                <span style="color: var(--text-muted);">{ap.timestamp.strftime('%b %d, %I:%M %p CT')}</span>
            </div>
            """, unsafe_allow_html=True)

    # ─── FOOTER ───
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 1rem; margin-top: 2rem;
         border-top: 1px solid var(--border-subtle);">
        <div style="font-family: 'Sora', sans-serif; font-size: 0.75rem; color: var(--text-muted);
             letter-spacing: 0.1em;">
            SPX PROPHET — NEXT GEN &nbsp;|&nbsp; BUILT FOR PRECISION
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ─── AUTO REFRESH ───
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()


if __name__ == "__main__":
    main()
