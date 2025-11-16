# spx_prophet_app.py
# SPX Prophet — Light Mode Edition

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475          # SPX rail slope per 30 minutes
PROFIT_FACTOR = 0.30       # Contract TP factor per SPX point
BASE_DATE = datetime(2000, 1, 1, 15, 0)


# ===============================
# STUNNING LIGHT MODE UI
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
    
    /* === FOUNDATION === */
    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.08), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.08), transparent 60%),
          radial-gradient(circle 1200px at 50% 50%, rgba(167, 139, 250, 0.05), transparent),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 30%, #f1f5f9 60%, #f8fafc 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    .block-container {
        padding-top: 3.5rem;
        padding-bottom: 4rem;
        max-width: 1400px;
    }
    
    /* === STUNNING SIDEBAR === */
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.08), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 2px solid rgba(99, 102, 241, 0.15);
        box-shadow:
            8px 0 40px rgba(99, 102, 241, 0.08),
            4px 0 20px rgba(0, 0, 0, 0.03);
    }
    
    [data-testid="stSidebar"] h4 {
        color: #6366f1;
        font-size: 0.95rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    
    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 2px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.6) 20%,
            rgba(148, 163, 184, 0.9) 50%,
            rgba(148, 163, 184, 0.6) 80%,
            transparent 100%);
    }
    
    /* === EPIC HERO HEADER (CENTERED) === */
    .hero-header {
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.12), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(59, 130, 246, 0.12), transparent 60%),
            linear-gradient(135deg, #ffffff, #fafbff);
        border-radius: 32px;
        padding: 40px 48px;
        margin-bottom: 40px;
        border: 2px solid rgba(148, 163, 184, 0.4);
        box-shadow:
            0 24px 70px -18px rgba(15, 23, 42, 0.28),
            0 12px 30px -10px rgba(15, 23, 42, 0.12),
            inset 0 2px 4px rgba(255, 255, 255, 0.9);
        overflow: hidden;
        text-align: center;
    }
    
    .hero-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 20%;
        right: 20%;
        height: 3px;
        border-radius: 999px;
        background: linear-gradient(90deg, #6366f1, #3b82f6, #06b6d4);
        opacity: 0.9;
    }
    
    .hero-title {
        font-size: 2.7rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #4f46e5 40%, #3b82f6 70%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.05em;
        line-height: 1.1;
    }
    
    .hero-subtitle {
        font-size: 1.2rem;
        color: #64748b;
        margin-top: 10px;
        font-weight: 500;
        font-family: 'Poppins', sans-serif;
    }
    
    .hero-status {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 8px 18px;
        border-radius: 999px;
        background: #ecfdf5;
        border: 1px solid rgba(22, 163, 74, 0.25);
        font-size: 0.8rem;
        font-weight: 600;
        color: #166534;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        margin-bottom: 16px;
    }
    
    .hero-status::before {
        content: '';
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: #16a34a;
        box-shadow: 0 0 8px rgba(34, 197, 94, 0.8);
    }
    
    /* === CARDS === */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 8% 8%, rgba(148, 163, 184, 0.16), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 28px;
        border: 1px solid rgba(148, 163, 184, 0.4);
        box-shadow:
            0 18px 45px -18px rgba(15, 23, 42, 0.25),
            inset 0 1px 3px rgba(255, 255, 255, 0.9);
        padding: 28px 30px;
        margin-bottom: 28px;
        transition: all 0.3s ease;
    }
    
    .spx-card:hover {
        transform: translateY(-4px);
        box-shadow:
            0 24px 60px -18px rgba(15, 23, 42, 0.3),
            inset 0 1px 3px rgba(255, 255, 255, 1);
        border-color: rgba(99, 102, 241, 0.45);
    }
    
    .spx-card h4 {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        color: #0f172a;
        margin: 0 0 10px 0;
        letter-spacing: -0.03em;
    }
    
    .icon-large {
        font-size: 2.4rem;
        margin-bottom: 8px;
    }
    
    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 16px;
        border-radius: 999px;
        border: 1px solid rgba(99, 102, 241, 0.25);
        background: #eef2ff;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        color: #4f46e5;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    
    .spx-pill::before {
        content: '◆';
        font-size: 0.7rem;
    }
    
    .spx-sub {
        color: #475569;
        font-size: 0.98rem;
        line-height: 1.7;
        font-weight: 400;
    }
    
    /* === SECTION HEADERS === */
    .section-header {
        font-size: 1.4rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        color: #0f172a;
        margin: 2.5rem 0 1.1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.7);
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .section-header::before {
        content: '';
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: linear-gradient(135deg, #6366f1, #3b82f6);
        box-shadow: 0 0 10px rgba(99, 102, 241, 0.6);
    }
    
    /* === METRIC CARDS === */
    .spx-metric {
        position: relative;
        padding: 20px 18px;
        border-radius: 20px;
        background: #ffffff;
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            0 16px 40px -18px rgba(15, 23, 42, 0.15),
            inset 0 1px 2px rgba(255, 255, 255, 0.9);
        transition: all 0.25s ease;
    }
    
    .spx-metric:hover {
        transform: translateY(-3px);
        box-shadow:
            0 18px 45px -18px rgba(15, 23, 42, 0.22),
            inset 0 1px 3px rgba(255, 255, 255, 1);
        border-color: rgba(99, 102, 241, 0.5);
    }
    
    .spx-metric-label {
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: #6b7280;
        font-weight: 600;
        margin-bottom: 6px;
    }
    
    .spx-metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #111827;
    }
    
    /* === BUTTONS === */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #4f46e5, #3b82f6);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 12px 28px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.12em;
        box-shadow:
            0 14px 32px rgba(79, 70, 229, 0.3),
            0 8px 18px rgba(15, 23, 42, 0.2);
        cursor: pointer;
        transition: all 0.25s ease;
        text-transform: uppercase;
    }
    
    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-2px);
        box-shadow:
            0 18px 42px rgba(79, 70, 229, 0.35),
            0 10px 24px rgba(15, 23, 42, 0.25);
    }
    
    .stButton>button:active, .stDownloadButton>button:active {
        transform: translateY(0px) scale(0.99);
    }
    
    /* === INPUTS === */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        border-radius: 16px !important;
        color: #0f172a !important;
        padding: 10px 14px !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
        box-shadow:
            0 4px 10px rgba(148, 163, 184, 0.25),
            inset 0 1px 2px rgba(255, 255, 255, 0.9) !important;
    }
    
    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: #4f46e5 !important;
        box-shadow:
            0 0 0 2px rgba(129, 140, 248, 0.35),
            0 6px 16px rgba(79, 70, 229, 0.25) !important;
        background: #f9fafb !important;
    }
    
    /* === RADIO === */
    .stRadio>div {
        gap: 12px;
    }
    
    .stRadio>div>label {
        background: #ffffff;
        padding: 9px 18px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.8);
        font-size: 0.9rem;
        font-weight: 600;
        color: #475569;
        box-shadow: 0 4px 10px rgba(148, 163, 184, 0.35);
        transition: all 0.2s ease;
    }
    
    .stRadio>div>label:hover {
        border-color: #4f46e5;
        color: #111827;
    }
    
    .stRadio>div>label[data-selected="true"] {
        background: #eef2ff;
        border-color: #4f46e5;
        color: #4f46e5;
    }
    
    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: #e5e7eb;
        padding: 6px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.8);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 999px;
        color: #6b7280;
        font-weight: 600;
        font-size: 0.9rem;
        padding: 8px 18px;
        border: none;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.85);
        color: #111827;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #ffffff;
        color: #111827;
        box-shadow:
            0 8px 18px rgba(148, 163, 184, 0.6),
            inset 0 1px 2px rgba(255, 255, 255, 0.9);
    }
    
    /* === DATAFRAME === */
    .stDataFrame {
        border-radius: 20px;
        overflow: hidden;
        box-shadow:
            0 18px 40px rgba(148, 163, 184, 0.35),
            0 10px 24px rgba(15, 23, 42, 0.2);
        border: 1px solid rgba(148, 163, 184, 0.9);
    }
    
    .stDataFrame div[data-testid="StyledTable"] {
        font-variant-numeric: tabular-nums;
        font-size: 0.9rem;
        font-family: 'JetBrains Mono', monospace;
        background: #ffffff;
    }
    
    .stDataFrame thead tr th {
        background: #eef2ff !important;
        color: #4f46e5 !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12em !important;
        font-size: 0.75rem !important;
        padding: 12px 10px !important;
        border-bottom: 1px solid rgba(148, 163, 184, 0.9) !important;
    }
    
    .stDataFrame tbody tr:hover {
        background: #f3f4ff !important;
    }
    
    .stDataFrame tbody tr td {
        padding: 10px 10px !important;
        border-bottom: 1px solid rgba(226, 232, 240, 0.9) !important;
        color: #111827 !important;
    }
    
    /* === MESSAGES === */
    .stSuccess, .stWarning, .stInfo {
        border-radius: 16px;
        border-width: 1px !important;
        font-size: 0.9rem;
    }
    
    .muted {
        color: #475569;
        font-size: 0.9rem;
        line-height: 1.7;
        padding: 16px 18px;
        background: #f8fafc;
        border-left: 3px solid #4f46e5;
        border-radius: 10px;
        margin: 16px 0;
        box-shadow: 0 6px 18px rgba(148, 163, 184, 0.3);
    }
    
    /* === SELECTBOX === */
    .stSelectbox>div>div {
        background: #ffffff;
        border: 1px solid rgba(148, 163, 184, 0.9);
        border-radius: 16px;
        box-shadow: 0 4px 14px rgba(148, 163, 184, 0.3);
        font-size: 0.95rem;
    }
    
    /* === LABELS === */
    label {
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        color: #4b5563 !important;
        margin-bottom: 4px !important;
    }
    
    /* === FOOTER === */
    .app-footer {
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(148, 163, 184, 0.7);
        text-align: center;
        color: #6b7280;
        font-size: 0.9rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown(
        f"""
        <div class="hero-header">
            <div class="hero-status">Running • Live Session Map</div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">{TAGLINE}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None, icon: str = ""):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if icon:
        st.markdown(f"<span class='icon-large'>{icon}</span>", unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str):
    return f"""
    <div class='spx-metric'>
        <div class='spx-metric-label'>{label}</div>
        <div class='spx-metric-value'>{value}</div>
    </div>
    """


def section_header(text: str):
    st.markdown(f"<h3 class='section-header'>{text}</h3>", unsafe_allow_html=True)


# ===============================
# TIME / BLOCK HELPERS
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
# CHANNEL ENGINE
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
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Top Rail": round(top, 4),
                "Bottom Rail": round(bottom, 4),
            }
        )
    df = pd.DataFrame(rows)
    return df, round(channel_height, 4)


# ===============================
# CONTRACT ENGINE
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
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Contract Price": round(price, 4),
            }
        )
    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# DAILY FORESIGHT HELPER
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

    # Sidebar
    with st.sidebar:
        st.markdown("#### Session Info")
        st.caption("This sidebar is just for quick reference. All core controls live in the main view.")
        st.markdown("---")

        st.markdown("#### Core Slope")
        st.write(f"SPX rail slope: **{SLOPE_MAG} pts / 30 min**")
        st.caption("Uniform 30 minute grid. All rails are straight lines from your pivots.")

        st.markdown("#### Options Factor")
        st.write(f"Contract TP factor: **{PROFIT_FACTOR} per SPX point**")
        st.caption("Rough contract target size for a full channel move.")

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Underlying maintenance: 16:00–17:00 CT\n\n"
            "• Contracts maintenance: 16:00–19:00 CT\n\n"
            "• RTH projection window: 08:30–14:30 CT."
        )

    hero()

    tabs = st.tabs(
        [
            "🧱 SPX Channel Setup",
            "📐 Contract Slope Setup",
            "🔮 Daily Foresight Card",
            "ℹ️ About",
        ]
    )

    # ==========================
    # TAB 1 — CHANNEL SETUP
    # ==========================
    with tabs[0]:
        card(
            "SPX Channel Setup",
            "Choose your engulfing pivots between 15:00 and 07:30 CT, pick the regime, and project the rails into RTH.",
            badge="Rails Engine",
            icon="🧱",
        )

        section_header("Pivots Configuration")
        st.markdown(
            "<div class='spx-sub'>Use the highest and lowest engulfing reversals you trust. "
            "All calculations run on a 30 minute grid.</div>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### High Pivot")
            high_price = st.number_input(
                "High pivot price",
                value=5200.0,
                step=0.25,
                key="pivot_high_price",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(19, 30),
                step=1800,
                key="pivot_high_time",
            )
        with c2:
            st.markdown("#### Low Pivot")
            low_price = st.number_input(
                "Low pivot price",
                value=5100.0,
                step=0.25,
                key="pivot_low_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(3, 0),
                step=1800,
                key="pivot_low_time",
            )

        section_header("Channel Regime")
        mode = st.radio(
            "Channel mode",
            ["Ascending", "Descending", "Both"],
            index=0,
            key="channel_mode",
            horizontal=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("Build Channel", key="build_channel_btn", use_container_width=True):
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

                st.success("Channel generated. Scroll down or open the Foresight tab to use it.")

        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        section_header("Channel Projections • RTH 08:30–14:30 CT")

        if df_asc is None and df_desc is None:
            st.info("Build at least one channel to view the projections.")
        else:
            if df_asc is not None:
                st.markdown(
                    "<h4 style='font-size:1.1rem; margin:16px 0;'>Ascending Channel</h4>",
                    unsafe_allow_html=True,
                )
                c_top = st.columns([3, 1], gap="large")
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True, height=360)
                with c_top[1]:
                    st.markdown(
                        metric_card("Channel height", f"{h_asc:.2f} pts"),
                        unsafe_allow_html=True,
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "Download CSV",
                        df_asc.to_csv(index=False).encode(),
                        "spx_ascending_rails.csv",
                        "text/csv",
                        key="dl_asc_channel",
                        use_container_width=True,
                    )

            if df_desc is not None:
                st.markdown(
                    "<h4 style='font-size:1.1rem; margin:20px 0 16px;'>Descending Channel</h4>",
                    unsafe_allow_html=True,
                )
                c_bot = st.columns([3, 1], gap="large")
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True, height=360)
                with c_bot[1]:
                    st.markdown(
                        metric_card("Channel height", f"{h_desc:.2f} pts"),
                        unsafe_allow_html=True,
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "Download CSV",
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
            "Use two contract prices to define a straight line on the same 30 minute grid as your rails.",
            badge="Contract Engine",
            icon="📐",
        )

        ph_time: dtime = st.session_state.get("pivot_high_time", dtime(15, 0))
        pl_time: dtime = st.session_state.get("pivot_low_time", dtime(3, 0))

        section_header("Anchor A — Contract Origin")
        anchor_a_source = st.radio(
            "Use which time for Anchor A",
            ["High pivot time", "Low pivot time", "Custom time"],
            index=0,
            key="contract_anchor_a_source",
            horizontal=True,
        )

        if anchor_a_source == "High pivot time":
            anchor_a_time = ph_time
            st.markdown(
                f"<div class='muted'>Anchor A time is locked to high pivot time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT.</div>",
                unsafe_allow_html=True,
            )
        elif anchor_a_source == "Low pivot time":
            anchor_a_time = pl_time
            st.markdown(
                f"<div class='muted'>Anchor A time is locked to low pivot time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT.</div>",
                unsafe_allow_html=True,
            )
        else:
            anchor_a_time = st.time_input(
                "Custom Anchor A time (CT)",
                value=dtime(1, 0),
                step=1800,
                key="contract_anchor_a_time_custom",
            )

        anchor_a_price = st.number_input(
            "Contract price at Anchor A time",
            value=10.0,
            step=0.1,
            key="contract_anchor_a_price",
        )

        section_header("Anchor B — Second Contract Point")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            anchor_b_time = st.time_input(
                "Anchor B time (CT)",
                value=dtime(7, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
        with c2:
            anchor_b_price = st.number_input(
                "Contract price at Anchor B time",
                value=8.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("Build Contract", key="build_contract_btn", use_container_width=True):
                try:
                    df_contract, slope_contract = build_contract_projection(
                        anchor_a_time=anchor_a_time,
                        anchor_a_price=anchor_a_price,
                        anchor_b_time=anchor_b_time,
                        anchor_b_price=anchor_b_price,
                    )
                    st.session_state["contract_df"] = df_contract
                    st.session_state["contract_slope"] = slope_contract
                    st.success("Contract projection generated. You can now use it in the Foresight tab.")
                except Exception as e:
                    st.error(f"Error generating contract projection: {e}")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        section_header("Contract Projection • RTH 08:30–14:30 CT")

        if df_contract is None:
            st.info("Build a contract projection to see projected prices.")
        else:
            c_top = st.columns([3, 1], gap="large")
            with c_top[0]:
                st.dataframe(df_contract, use_container_width=True, hide_index=True, height=360)
            with c_top[1]:
                st.markdown(
                    metric_card("Contract slope", f"{slope_contract:+.4f} / 30m"),
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "Download CSV",
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
            "Channel structure and contract line combined into a simple time-based playbook.",
            badge="Foresight",
            icon="🔮",
        )

        df_mode, df_ch, h_ch = get_active_channel()
        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        if df_ch is None or h_ch is None:
            st.warning("No active channel found. Build a channel in the SPX Channel Setup tab first.")
            end_card()
        elif df_contract is None or slope_contract is None:
            st.warning("No contract projection found. Build one in the Contract Slope Setup tab first.")
            end_card()
        else:
            merged = df_ch.merge(df_contract, on="Time", how="left")
            blocks_for_channel = h_ch / SLOPE_MAG if SLOPE_MAG != 0 else 0.0
            structural_contract_move = slope_contract * blocks_for_channel if blocks_for_channel != 0 else 0.0
            factor_tp_size = h_ch * PROFIT_FACTOR

            section_header("Structure Summary")
            c1, c2, c3 = st.columns(3, gap="large")
            with c1:
                st.markdown(
                    metric_card("Active channel", df_mode or "Not set"),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card("Channel height", f"{h_ch:.2f} pts"),
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    metric_card("Contract TP size", f"{factor_tp_size:.2f} units"),
                    unsafe_allow_html=True,
                )

            section_header("Inside Channel Play")
            st.markdown(
                f"""
                <div class='spx-sub'>
                  <p><strong>Long idea</strong> — Buy at the lower rail, exit at the upper rail.</p>
                  <ul>
                    <li>SPX structural move: about <strong>{h_ch:.2f} points</strong> in your favor</li>
                    <li>Anchor-based contract line size (per full channel): about <strong>{structural_contract_move:+.2f} units</strong></li>
                    <li>Conservative take profit using factor {PROFIT_FACTOR}: about <strong>{factor_tp_size:.2f} units</strong> per contract</li>
                  </ul>
                  <p><strong>Short idea</strong> — Sell at the upper rail, cover at the lower rail.</p>
                  <ul>
                    <li>Same SPX distance, opposite direction</li>
                    <li>Same contract size, mirrored in sign</li>
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Breakout and Breakdown Ideas")
            st.markdown(
                f"""
                <div class='spx-sub'>
                  <p><strong>Breakout above upper rail</strong></p>
                  <ul>
                    <li>Entry on clean retest of the upper rail from above</li>
                    <li>First continuation target ≈ one more channel height of SPX</li>
                    <li>Use the same contract TP size (~{factor_tp_size:.2f} units) as a guide</li>
                  </ul>
                  <p><strong>Breakdown below lower rail</strong></p>
                  <ul>
                    <li>Entry on clean retest of the lower rail from below</li>
                    <li>First continuation target ≈ one more channel height beneath</li>
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Contract Trade Estimator")

            times = merged["Time"].tolist()
            if times:
                col_e, col_x = st.columns(2, gap="large")
                with col_e:
                    entry_time = st.selectbox(
                        "Planned rail touch (entry time)",
                        times,
                        index=0,
                        key="foresight_entry_time",
                    )
                with col_x:
                    exit_time = st.selectbox(
                        "Planned exit time (for line estimate)",
                        times,
                        index=min(len(times) - 1, 4),
                        key="foresight_exit_time",
                    )

                entry_row = merged[merged["Time"] == entry_time].iloc[0]
                exit_row = merged[merged["Time"] == exit_time].iloc[0]
                entry_contract = float(entry_row["Contract Price"])
                exit_contract = float(exit_row["Contract Price"])
                pnl_contract_line = exit_contract - entry_contract

                # Factor based TP levels for long / short idea
                tp_long = entry_contract + factor_tp_size
                tp_short = entry_contract - factor_tp_size

                c1_est, c2_est, c3_est = st.columns(3, gap="large")
                with c1_est:
                    st.markdown(
                        metric_card("Entry contract (line)", f"{entry_contract:.2f}"),
                        unsafe_allow_html=True,
                    )
                with c2_est:
                    st.markdown(
                        metric_card(f"Line at {exit_time}", f"{exit_contract:.2f}"),
                        unsafe_allow_html=True,
                    )
                with c3_est:
                    st.markdown(
                        metric_card("Line P&L", f"{pnl_contract_line:+.2f} units"),
                        unsafe_allow_html=True,
                    )

                c4_est, c5_est = st.columns(2, gap="large")
                with c4_est:
                    st.markdown(
                        metric_card("Factor TP (long idea)", f"{tp_long:.2f}"),
                        unsafe_allow_html=True,
                    )
                with c5_est:
                    st.markdown(
                        metric_card("Factor TP (short idea)", f"{tp_short:.2f}"),
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    "<div class='muted'><strong>How to read this:</strong> "
                    "The contract line values show the structural price from your two anchors at different times. "
                    "The factor-based targets use your SPX channel height and a fixed factor "
                    f"({PROFIT_FACTOR}) to give a more realistic TP zone for options compared to what you observed in real trades.</div>",
                    unsafe_allow_html=True,
                )

            section_header("Time Aligned Map")
            st.caption(
                "Each row is a 30 minute slot in RTH. If SPX tags a rail at that time, "
                "this is the structural contract level implied by your two anchors."
            )
            st.dataframe(merged, use_container_width=True, hide_index=True, height=420)

            st.markdown(
                "<div class='muted'><strong>Reminder:</strong> "
                "This map does not know volatility or IV crush. "
                "It gives you a clean structural canvas so you can compare what your anchors expected "
                "with what the contract actually did on that day.</div>",
                unsafe_allow_html=True,
            )

            end_card()

    # ==========================
    # TAB 4 — ABOUT
    # ==========================
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Overview", icon="ℹ️")
        st.markdown(
            f"""
            <div class='spx-sub'>
            <p><strong>{APP_NAME}</strong> is built around your idea:</p>
            <p><em>“I want to trade bounces and rejections off two parallel lines that represent where price should be, based on two anchors and a uniform slope.”</em></p>
            <ul>
                <li>Rails are projected with a fixed slope of <strong>{SLOPE_MAG} points per 30 minutes</strong></li>
                <li>Pivots are engulfing reversals you select between 15:00 and 07:30 CT</li>
                <li>Channels can be viewed as ascending, descending, or inspected both ways</li>
                <li>Contracts follow a straight line defined by two anchor prices on the same grid</li>
                <li>A simple factor of <strong>{PROFIT_FACTOR}</strong> per SPX point gives you a practical options TP size for a full channel move</li>
            </ul>
            <p>The goal is not to be a full options pricing model. It is to give you a clean, repeatable structure so that when price returns to your rails, you are not reacting emotionally — you already know what the structure expects.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='muted'><strong>Maintenance windows:</strong> SPX 16:00–17:00 CT. "
            "Contracts 16:00–19:00 CT.</div>",
            unsafe_allow_html=True,
        )
        end_card()

    st.markdown(
        f"<div class='app-footer'>© 2025 {APP_NAME} • {TAGLINE}</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()