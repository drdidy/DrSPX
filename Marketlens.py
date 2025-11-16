# spx_prophet_v7_premium.py
# SPX Prophet v7.0 — "Where Structure Becomes Foresight."
# Premium UI Edition - Enterprise-grade design, unchanged strategy

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet v7.0"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475
BASE_DATE = datetime(2000, 1, 1, 15, 0)


# ===============================
# WORLD-CLASS UI SYSTEM
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* === CORE FOUNDATION === */
    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1400px 900px at 15% 0%, rgba(0, 255, 255, 0.08), transparent 50%),
          radial-gradient(ellipse 1200px 1000px at 85% 100%, rgba(0, 255, 135, 0.06), transparent 50%),
          radial-gradient(circle 800px at 50% 50%, rgba(138, 43, 226, 0.03), transparent),
          linear-gradient(165deg, #010208 0%, #020515 25%, #030a1a 50%, #020515 75%, #010208 100%);
        background-attachment: fixed;
        color: #E8F0FF;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
        font-weight: 400;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    /* === REFINED SIDEBAR === */
    [data-testid="stSidebar"] {
        background: 
            linear-gradient(175deg, rgba(3,8,25,0.97) 0%, rgba(8,15,35,0.98) 50%, rgba(5,10,28,0.97) 100%);
        border-right: 1px solid rgba(0,255,200,0.12);
        backdrop-filter: blur(28px) saturate(180%);
        box-shadow: 
            4px 0 40px rgba(0,0,0,0.5),
            inset -1px 0 1px rgba(0,255,255,0.08);
    }
    
    [data-testid="stSidebar"] h3 {
        font-size: 1.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #00FFE5 0%, #00FF9D 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    
    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,255,200,0.3), transparent);
    }
    
    [data-testid="stSidebar"] h4 {
        color: #00FFE5;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    
    [data-testid="stSidebar"] .stMarkdown p {
        font-size: 0.95rem;
        line-height: 1.6;
        color: #B8C5E0;
    }
    
    [data-testid="stSidebar"] .stMarkdown strong {
        color: #00FFE5;
        font-weight: 600;
    }
    
    /* === TYPOGRAPHY SYSTEM === */
    h1, h2, h3, h4, h5, h6 {
        color: #E8F0FF;
        font-weight: 700;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }
    
    h1 { font-size: 2.5rem; }
    h2 { font-size: 2rem; }
    h3 { font-size: 1.5rem; }
    h4 { font-size: 1.25rem; }
    
    label, p, span, div {
        color: #D1DFFF;
        line-height: 1.6;
    }
    
    /* === PREMIUM CARD SYSTEM === */
    .spx-card {
        position: relative;
        background: 
            radial-gradient(circle at 5% 5%, rgba(0,255,255,0.08), transparent 40%),
            radial-gradient(circle at 95% 95%, rgba(0,255,135,0.06), transparent 40%),
            linear-gradient(135deg, rgba(15,20,45,0.95), rgba(8,12,30,0.92));
        border-radius: 24px;
        border: 1px solid rgba(0,255,200,0.15);
        box-shadow:
          0 20px 60px -12px rgba(0,0,0,0.8),
          0 8px 24px -8px rgba(0,0,0,0.6),
          inset 0 1px 0 rgba(255,255,255,0.03),
          0 0 0 1px rgba(0,255,255,0.05);
        padding: 28px 32px;
        margin-bottom: 24px;
        backdrop-filter: blur(24px) saturate(180%);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }
    
    .spx-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, 
            transparent, 
            rgba(0,255,255,0.4) 30%, 
            rgba(0,255,135,0.4) 70%, 
            transparent);
        opacity: 0;
        transition: opacity 0.4s ease;
    }
    
    .spx-card:hover {
        transform: translateY(-4px);
        border-color: rgba(0,255,255,0.35);
        box-shadow:
          0 32px 80px -12px rgba(0,0,0,0.9),
          0 16px 40px -8px rgba(0,255,255,0.15),
          inset 0 1px 0 rgba(255,255,255,0.06),
          0 0 0 1px rgba(0,255,255,0.15),
          0 0 80px rgba(0,255,255,0.1);
    }
    
    .spx-card:hover::before {
        opacity: 1;
    }
    
    .spx-card h4 {
        margin: 0 0 8px 0;
        font-size: 1.35rem;
        font-weight: 700;
        background: linear-gradient(135deg, #E8F0FF 0%, #B8D5FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* === PREMIUM BADGE SYSTEM === */
    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 16px;
        border-radius: 100px;
        border: 1px solid rgba(0,255,200,0.3);
        background: 
            linear-gradient(135deg, rgba(0,255,200,0.15), rgba(0,255,135,0.12)),
            rgba(0,30,30,0.4);
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #00FFE5;
        box-shadow: 
            0 4px 12px rgba(0,255,255,0.15),
            inset 0 1px 0 rgba(255,255,255,0.1);
        margin-bottom: 12px;
        transition: all 0.3s ease;
    }
    
    .spx-pill:hover {
        transform: scale(1.05);
        box-shadow: 
            0 6px 20px rgba(0,255,255,0.25),
            inset 0 1px 0 rgba(255,255,255,0.15);
    }
    
    .spx-pill::before {
        content: '◆';
        font-size: 0.5rem;
        color: #00FFE5;
    }
    
    /* === SUBTITLE STYLING === */
    .spx-sub {
        color: #8FA8D0;
        font-size: 0.95rem;
        line-height: 1.5;
        font-weight: 400;
    }
    
    .muted {
        color: #7A92B8;
        font-size: 0.88rem;
        line-height: 1.6;
        padding: 12px 16px;
        background: rgba(0,100,150,0.08);
        border-left: 2px solid rgba(0,255,200,0.25);
        border-radius: 8px;
        margin: 12px 0;
    }
    
    /* === PREMIUM METRICS SYSTEM === */
    .spx-metric {
        position: relative;
        padding: 20px 24px;
        border-radius: 16px;
        background: 
            radial-gradient(circle at top left, rgba(0,255,255,0.12), transparent 60%),
            linear-gradient(135deg, rgba(20,30,60,0.6), rgba(10,20,45,0.8));
        border: 1px solid rgba(0,255,255,0.2);
        box-shadow: 
            0 8px 24px rgba(0,0,0,0.4),
            inset 0 1px 0 rgba(255,255,255,0.05);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }
    
    .spx-metric::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, #00FFE5, #00FF9D);
        transform: scaleX(0);
        transform-origin: left;
        transition: transform 0.4s ease;
    }
    
    .spx-metric:hover {
        transform: translateY(-2px);
        border-color: rgba(0,255,255,0.4);
        box-shadow: 
            0 12px 32px rgba(0,0,0,0.5),
            0 0 40px rgba(0,255,255,0.1),
            inset 0 1px 0 rgba(255,255,255,0.08);
    }
    
    .spx-metric:hover::before {
        transform: scaleX(1);
    }
    
    .spx-metric-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #8FA8D0;
        font-weight: 600;
        margin-bottom: 8px;
        display: block;
    }
    
    .spx-metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #E8F0FF;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #E8F0FF 0%, #00FFE5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* === WORLD-CLASS BUTTONS === */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #00E5FF 0%, #00FF9D 100%);
        color: #001a1a;
        border-radius: 12px;
        border: none;
        padding: 12px 28px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.02em;
        box-shadow: 
            0 8px 24px rgba(0,230,255,0.25),
            0 4px 12px rgba(0,0,0,0.3),
            inset 0 1px 0 rgba(255,255,255,0.3);
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    
    .stButton>button::before, .stDownloadButton>button::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(255,255,255,0.3);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
    }
    
    .stButton>button:hover::before, .stDownloadButton>button:hover::before {
        width: 300px;
        height: 300px;
    }
    
    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 
            0 12px 32px rgba(0,230,255,0.35),
            0 6px 16px rgba(0,0,0,0.4),
            inset 0 1px 0 rgba(255,255,255,0.4);
    }
    
    .stButton>button:active, .stDownloadButton>button:active {
        transform: translateY(0);
        box-shadow: 
            0 4px 12px rgba(0,230,255,0.2),
            0 2px 6px rgba(0,0,0,0.3);
    }
    
    /* === REFINED INPUTS === */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input,
    .stTextInput>div>div>input {
        background: rgba(15,25,50,0.6) !important;
        border: 1px solid rgba(0,255,200,0.2) !important;
        border-radius: 10px !important;
        color: #E8F0FF !important;
        padding: 10px 14px !important;
        font-size: 0.95rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus,
    .stTextInput>div>div>input:focus {
        border-color: rgba(0,255,255,0.5) !important;
        box-shadow: 
            0 0 0 3px rgba(0,255,255,0.1),
            0 4px 12px rgba(0,255,255,0.15) !important;
        background: rgba(20,30,60,0.7) !important;
    }
    
    /* === PREMIUM RADIO BUTTONS === */
    .stRadio>div {
        gap: 12px;
    }
    
    .stRadio>div>label {
        background: rgba(15,25,50,0.5);
        padding: 10px 20px;
        border-radius: 10px;
        border: 1px solid rgba(0,255,200,0.15);
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .stRadio>div>label:hover {
        background: rgba(20,30,60,0.7);
        border-color: rgba(0,255,200,0.3);
        transform: translateY(-1px);
    }
    
    .stRadio>div>label[data-selected="true"] {
        background: linear-gradient(135deg, rgba(0,255,255,0.15), rgba(0,255,135,0.12));
        border-color: rgba(0,255,200,0.5);
        box-shadow: 0 4px 16px rgba(0,255,255,0.2);
    }
    
    /* === ELEGANT TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(5,10,25,0.6);
        padding: 8px;
        border-radius: 16px;
        border: 1px solid rgba(0,255,200,0.1);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 10px;
        color: #8FA8D0;
        font-weight: 600;
        padding: 12px 24px;
        transition: all 0.3s ease;
        border: 1px solid transparent;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(0,255,200,0.08);
        color: #00FFE5;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, rgba(0,255,255,0.15), rgba(0,255,135,0.12));
        color: #00FFE5;
        border-color: rgba(0,255,200,0.3);
        box-shadow: 0 4px 16px rgba(0,255,255,0.15);
    }
    
    /* === PREMIUM DATAFRAMES === */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }
    
    .stDataFrame div[data-testid="StyledTable"] {
        font-variant-numeric: tabular-nums;
        font-size: 0.88rem;
        background: rgba(10,15,35,0.7);
    }
    
    .stDataFrame thead tr th {
        background: linear-gradient(135deg, rgba(0,255,255,0.15), rgba(0,255,135,0.12)) !important;
        color: #00FFE5 !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.75rem !important;
        padding: 14px 12px !important;
        border-bottom: 2px solid rgba(0,255,200,0.3) !important;
    }
    
    .stDataFrame tbody tr {
        transition: all 0.2s ease;
    }
    
    .stDataFrame tbody tr:hover {
        background: rgba(0,255,255,0.05) !important;
    }
    
    .stDataFrame tbody tr td {
        padding: 12px !important;
        border-bottom: 1px solid rgba(0,255,200,0.08) !important;
        color: #D1DFFF !important;
    }
    
    /* === SUCCESS/WARNING/INFO MESSAGES === */
    .stSuccess, .stWarning, .stInfo {
        border-radius: 12px;
        border-left-width: 4px;
        padding: 16px 20px;
        backdrop-filter: blur(10px);
    }
    
    .stSuccess {
        background: linear-gradient(135deg, rgba(0,255,135,0.15), rgba(0,255,200,0.1));
        border-left-color: #00FF9D;
    }
    
    .stWarning {
        background: linear-gradient(135deg, rgba(255,200,0,0.15), rgba(255,150,0,0.1));
        border-left-color: #FFC800;
    }
    
    .stInfo {
        background: linear-gradient(135deg, rgba(0,200,255,0.15), rgba(0,150,255,0.1));
        border-left-color: #00C8FF;
    }
    
    /* === SELECTBOX === */
    .stSelectbox>div>div {
        background: rgba(15,25,50,0.6);
        border: 1px solid rgba(0,255,200,0.2);
        border-radius: 10px;
        transition: all 0.3s ease;
    }
    
    .stSelectbox>div>div:hover {
        border-color: rgba(0,255,200,0.4);
        background: rgba(20,30,60,0.7);
    }
    
    /* === SCROLLBAR === */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(5,10,25,0.5);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, rgba(0,255,255,0.3), rgba(0,255,135,0.3));
        border-radius: 10px;
        border: 2px solid rgba(5,10,25,0.5);
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, rgba(0,255,255,0.5), rgba(0,255,135,0.5));
    }
    
    /* === ENHANCED SPACING === */
    .block-container {
        padding-top: 3rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }
    
    /* === SECTION HEADERS === */
    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #E8F0FF;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid rgba(0,255,200,0.2);
        background: linear-gradient(135deg, #E8F0FF 0%, #00FFE5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* === FOOTER === */
    .app-footer {
        margin-top: 3rem;
        padding-top: 2rem;
        border-top: 1px solid rgba(0,255,200,0.1);
        text-align: center;
        color: #6A7A98;
        font-size: 0.85rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str):
    """Premium metric display"""
    return f"""
    <div class='spx-metric'>
        <div class='spx-metric-label'>{label}</div>
        <div class='spx-metric-value'>{value}</div>
    </div>
    """


# ===============================
# TIME / BLOCK HELPERS (UNCHANGED)
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


# ===============================
# CHANNEL ENGINE (UNCHANGED)
# ===============================

def build_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
) -> Tuple[pd.DataFrame, float]:
    s = slope_sign * SLOPE_MAG
    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))
    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)
    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo
    channel_height = b_top - b_bottom
    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        top = s * k + b_top
        bottom = s * k + b_bottom
        rows.append({
            "Time": dt.strftime("%H:%M"),
            "Top Rail": round(top, 4),
            "Bottom Rail": round(bottom, 4),
        })
    df = pd.DataFrame(rows)
    return df, round(channel_height, 4)


# ===============================
# CONTRACT ENGINE (UNCHANGED)
# ===============================

def build_contract_projection(
    anchor_a_time: dtime,
    anchor_a_price: float,
    anchor_b_time: dtime,
    anchor_b_price: float,
) -> Tuple[pd.DataFrame, float]:
    dt_a = align_30min(make_dt_from_time(anchor_a_time))
    dt_b = align_30min(make_dt_from_time(anchor_b_time))
    k_a = blocks_from_base(dt_a)
    k_b = blocks_from_base(dt_b)
    if k_a == k_b:
        slope = 0.0
    else:
        slope = (anchor_b_price - anchor_a_price) / (k_b - k_a)
    b_contract = anchor_a_price - slope * k_a
    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        price = slope * k + b_contract
        rows.append({
            "Time": dt.strftime("%H:%M"),
            "Contract Price": round(price, 4),
        })
    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# DAILY FORESIGHT CARD LOGIC (UNCHANGED)
# ===============================

def get_active_channel() -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[float]]:
    mode = st.session_state.get("channel_mode")
    df_asc = st.session_state.get("channel_asc_df")
    df_desc = st.session_state.get("channel_desc_df")
    h_asc = st.session_state.get("channel_asc_height")
    h_desc = st.session_state.get("channel_desc_height")

    if mode == "Ascending":
        return "Ascending", df_asc, h_asc
    if mode == "Descending":
        return "Descending", df_desc, h_desc
    if mode == "Both":
        scenario = st.selectbox(
            "Active scenario for Foresight",
            ["Ascending", "Descending"],
            index=0,
            key="foresight_scenario",
        )
        if scenario == "Ascending":
            return "Ascending", df_asc, h_asc
        else:
            return "Descending", df_desc, h_desc
    return None, None, None


# ===============================
# MAIN APP
# ===============================

def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    # Premium Sidebar
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(f"<span class='spx-sub'>{TAGLINE}</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("#### Core Slope")
        st.write(f"SPX rail slope magnitude: **{SLOPE_MAG} pts / 30 min**")
        st.caption("All calculations use a uniform per-block slope. Time grid = 30-minute candles.")
        
        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "Underlying maintenance: 16:00–17:00 CT\n\n"
            "Contracts maintenance: 16:00–19:00 CT\n\n"
            "RTH projection window: 08:30–14:30 CT."
        )

    tabs = st.tabs([
        "🧱 SPX Channel Setup",
        "📐 Contract Slope Setup",
        "🔮 Daily Foresight Card",
        "ℹ️ About",
    ])

    # ==========================
    # TAB 1 — CHANNEL SETUP
    # ==========================
    with tabs[0]:
        card(
            "SPX Channel Setup",
            "Define your high and low pivots, choose the channel regime, and project parallel rails across RTH.",
            badge="Rails Engine",
        )

        st.markdown("<h5 class='section-header'>Pivots (3:00 PM to 7:30 AM, manual)</h5>", unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="large")
        with c1:
            high_price = st.number_input(
                "High Pivot Price",
                value=5200.0,
                step=0.25,
                key="pivot_high_price",
            )
            high_time = st.time_input(
                "High Pivot Time (CT)",
                value=dtime(15, 0),
                step=1800,
                key="pivot_high_time",
            )
        with c2:
            low_price = st.number_input(
                "Low Pivot Price",
                value=5100.0,
                step=0.25,
                key="pivot_low_price",
            )
            low_time = st.time_input(
                "Low Pivot Time (CT)",
                value=dtime(3, 0),
                step=1800,
                key="pivot_low_time",
            )

        st.markdown("<h5 class='section-header'>Channel Regime</h5>", unsafe_allow_html=True)
        mode = st.radio(
            "Channel Mode",
            ["Ascending", "Descending", "Both"],
            index=0,
            key="channel_mode",
            horizontal=True,
        )

        col_btn = st.columns([1, 2])[0]
        with col_btn:
            if st.button("⚡ Build Channel", key="build_channel_btn", use_container_width=True):
                if mode in ("Ascending", "Both"):
                    df_asc, h_asc = build_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=+1,
                    )
                    st.session_state["channel_asc_df"] = df_asc
                    st.session_state["channel_asc_height"] = h_asc
                else:
                    st.session_state["channel_asc_df"] = None
                    st.session_state["channel_asc_height"] = None

                if mode in ("Descending", "Both"):
                    df_desc, h_desc = build_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=-1,
                    )
                    st.session_state["channel_desc_df"] = df_desc
                    st.session_state["channel_desc_height"] = h_desc
                else:
                    st.session_state["channel_desc_df"] = None
                    st.session_state["channel_desc_height"] = None

                st.success("✨ Channel(s) generated successfully! Check tables below and the Daily Foresight Card tab.")

        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        st.markdown("<h5 class='section-header'>Channel Projections (RTH 08:30–14:30 CT)</h5>", unsafe_allow_html=True)
        if df_asc is None and df_desc is None:
            st.info("📊 Build a channel to view projections.")
        else:
            if df_asc is not None:
                st.markdown("#### Ascending Channel")
                c_top = st.columns([2, 1], gap="large")
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True)
                with c_top[1]:
                    st.markdown(metric_card("Channel Height (Ascending)", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download Ascending Rails CSV",
                        df_asc.to_csv(index=False).encode(),
                        "spx_ascending_rails.csv",
                        "text/csv",
                        key="dl_asc_channel",
                        use_container_width=True,
                    )

            if df_desc is not None:
                st.markdown("#### Descending Channel")
                c_bot = st.columns([2, 1], gap="large")
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True)
                with c_bot[1]:
                    st.markdown(metric_card("Channel Height (Descending)", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download Descending Rails CSV",
                        df_desc.to_csv(index=False).encode(),
                        "spx_descending_rails.csv",
                        "text/csv",
                        key="dl_desc_channel",
                        use_container_width=True,
                    )

        end_card()

    # ==========================
    # TAB 2 — CONTRACT SLOPE
    # ==========================
    with tabs[1]:
        card(
            "Contract Slope Setup",
            "Anchor your contract line to a pivot or custom time, define a second point, and project value across RTH.",
            badge="Contract Engine",
        )

        ph_time: dtime = st.session_state.get("pivot_high_time", dtime(15, 0))
        pl_time: dtime = st.session_state.get("pivot_low_time", dtime(3, 0))

        st.markdown("<h5 class='section-header'>Anchor A — Contract Origin</h5>", unsafe_allow_html=True)
        anchor_a_source = st.radio(
            "Use which time for Anchor A?",
            ["High Pivot Time", "Low Pivot Time", "Custom Time"],
            index=0,
            key="contract_anchor_a_source",
            horizontal=True,
        )

        if anchor_a_source == "High Pivot Time":
            anchor_a_time = ph_time
            st.markdown(
                f"<div class='muted'>✓ Anchor A time set to High Pivot Time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT</div>",
                unsafe_allow_html=True,
            )
        elif anchor_a_source == "Low Pivot Time":
            anchor_a_time = pl_time
            st.markdown(
                f"<div class='muted'>✓ Anchor A time set to Low Pivot Time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT</div>",
                unsafe_allow_html=True,
            )
        else:
            anchor_a_time = st.time_input(
                "Custom Anchor A Time (CT)",
                value=dtime(1, 0),
                step=1800,
                key="contract_anchor_a_time_custom",
            )

        anchor_a_price = st.number_input(
            "Contract Price at Anchor A Time",
            value=10.0,
            step=0.1,
            key="contract_anchor_a_price",
        )

        st.markdown("<h5 class='section-header'>Anchor B — Second Contract Point</h5>", unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="large")
        with c1:
            anchor_b_time = st.time_input(
                "Anchor B Time (CT)",
                value=dtime(7, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
        with c2:
            anchor_b_price = st.number_input(
                "Contract Price at Anchor B Time",
                value=8.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        col_btn = st.columns([1, 2])[0]
        with col_btn:
            if st.button("⚡ Build Contract Projection", key="build_contract_btn", use_container_width=True):
                df_contract, slope_contract = build_contract_projection(
                    anchor_a_time=anchor_a_time,
                    anchor_a_price=anchor_a_price,
                    anchor_b_time=anchor_b_time,
                    anchor_b_price=anchor_b_price,
                )
                st.session_state["contract_df"] = df_contract
                st.session_state["contract_slope"] = slope_contract
                st.session_state["contract_anchor_a_time"] = anchor_a_time
                st.session_state["contract_anchor_a_price"] = anchor_a_price
                st.session_state["contract_anchor_b_time"] = anchor_b_time
                st.session_state["contract_anchor_b_price"] = anchor_b_price
                st.success("✨ Contract projection generated successfully! Check the table below and the Daily Foresight Card tab.")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        st.markdown("<h5 class='section-header'>Contract Projection (RTH 08:30–14:30 CT)</h5>", unsafe_allow_html=True)
        if df_contract is None:
            st.info("📊 Build a contract projection to view projected contract prices.")
        else:
            c_top = st.columns([2, 1], gap="large")
            with c_top[0]:
                st.dataframe(df_contract, use_container_width=True, hide_index=True)
            with c_top[1]:
                st.markdown(metric_card("Contract Slope", f"{slope_contract:+.4f} / 30m"), unsafe_allow_html=True)
                st.download_button(
                    "📥 Download Contract Projection CSV",
                    df_contract.to_csv(index=False).encode(),
                    "contract_projection.csv",
                    "text/csv",
                    key="dl_contract",
                    use_container_width=True,
                )

        end_card()

    # ==========================
    # TAB 3 — DAILY FORESIGHT
    # ==========================
    with tabs[2]:
        card(
            "Daily Foresight Card",
            "Channel structure + contract slope combined into a simple playbook for the session.",
            badge="Foresight",
        )

        mode = st.session_state.get("channel_mode")
        df_mode, df_ch, h_ch = get_active_channel()
        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        if df_ch is None or h_ch is None:
            st.warning("⚠️ No active channel found. Build a channel in the SPX Channel Setup tab first.")
            end_card()
        elif df_contract is None or slope_contract is None:
            st.warning("⚠️ No contract projection found. Build one in the Contract Slope Setup tab first.")
            end_card()
        else:
            merged = df_ch.merge(df_contract, on="Time", how="left")
            blocks_for_channel = h_ch / SLOPE_MAG if SLOPE_MAG != 0 else 0
            contract_move_per_channel = slope_contract * blocks_for_channel if blocks_for_channel != 0 else 0

            st.markdown("<h5 class='section-header'>Structure Summary</h5>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3, gap="large")
            with c1:
                st.markdown(metric_card("Active Channel", df_mode), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Channel Height", f"{h_ch:.2f} pts"), unsafe_allow_html=True)
            with c3:
                st.markdown(metric_card("Contract Move per Channel", f"{contract_move_per_channel:+.2f} units"), unsafe_allow_html=True)

            st.markdown("<h5 class='section-header'>Inside-Channel Play (If Price Stays Between Rails)</h5>", unsafe_allow_html=True)
            st.markdown(
                f"""
                - **Long Play**: Buy at bottom rail, exit at top rail  
                  - Underlying reward ≈ **+{h_ch:.2f} pts**  
                  - Contract expectation ≈ **{contract_move_per_channel:+.2f}** units  
                - **Short Play**: Sell at top rail, exit at bottom rail  
                  - Underlying reward ≈ **-{h_ch:.2f} pts**  
                  - Contract expectation ≈ **{(-contract_move_per_channel):+.2f}** units  
                """.strip()
            )

            st.markdown("<h5 class='section-header'>Breakout / Breakdown Play (If Price Leaves the Channel)</h5>", unsafe_allow_html=True)
            st.markdown(
                f"""
                - **Bullish Breakout**:  
                  - Entry on retest of top rail from above  
                  - Underlying continuation target ≈ **Top Rail + {h_ch:.2f} pts**  
                  - Contract expectation per full channel move ≈ **{contract_move_per_channel:+.2f}** units  
                - **Bearish Breakdown**:  
                  - Entry on retest of bottom rail from below  
                  - Underlying continuation target ≈ **Bottom Rail − {h_ch:.2f} pts**  
                  - Contract expectation per full channel move ≈ **{contract_move_per_channel:+.2f}** units  
                """.strip()
            )

            st.markdown("<h5 class='section-header'>Time-Aligned Map (Rails + Contract)</h5>", unsafe_allow_html=True)
            st.caption("Each row is a 30-minute slot in RTH. Use this as a conditional map: if price tags a rail at that time, this is the expected contract level.")
            st.dataframe(merged, use_container_width=True, hide_index=True)

            st.markdown(
                "<div class='muted'><strong>Interpretation:</strong> "
                "The map does not predict exactly <em>when</em> SPX will hit a rail. "
                "It tells you what the contract should roughly be worth <em>if</em> that touch happens at a given time.</div>",
                unsafe_allow_html=True,
            )

            end_card()

    # ==========================
    # TAB 4 — ABOUT
    # ==========================
    with tabs[3]:
        card("About SPX Prophet v7.0", TAGLINE, badge="Version 7.0")
        st.markdown(
            """
            **SPX Prophet v7.0** is built around a single idea:

            > Two pivots define the rails. The slope defines the future.

            - Rails are projected using a **uniform slope** of **±0.475 pts per 30 minutes**  
            - Pivots are **engulfing reversals** chosen between **15:00 and 07:30 CT**  
            - Channels can be **ascending, descending, or inspected both ways**  
            - Contracts are projected from **two anchor prices** on the same 30-minute grid  

            The app does not guess volatility, gamma, or implied pricing.  
            It respects one thing: **structure**.

            When the market returns to your rails, you are no longer surprised.  
            You are prepared.
            """.strip()
        )
        st.markdown("<div class='muted'><strong>Maintenance windows:</strong> SPX 16:00–17:00 CT, contracts 16:00–19:00 CT.</div>", unsafe_allow_html=True)
        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet v7.0 • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()