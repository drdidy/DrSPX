# spx_prophet_v7_ultimate.py
# SPX Prophet v7.0 ULTIMATE PREMIUM EDITION
# Clean professional trading app for SPX channels and contracts

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet v7.0"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475  # underlying rail slope per 30m
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 CT baseline for time grid


# ===============================
# UI SYSTEM (LIGHT, MATURE)
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(circle at top left, rgba(120, 144, 156, 0.18), transparent 55%),
          radial-gradient(circle at bottom right, rgba(79, 195, 247, 0.18), transparent 55%),
          linear-gradient(180deg, #f7f9fc 0%, #edf1f7 40%, #f7f9fc 100%);
        background-attachment: fixed;
        color: #1b2635;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
    }
    
    .block-container {
        padding-top: 3rem;
        padding-bottom: 3rem;
        max-width: 1300px;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background:
            linear-gradient(180deg, #f4f6fb 0%, #e7ebf3 100%);
        border-right: 1px solid rgba(120, 144, 156, 0.25);
        box-shadow: 6px 0 24px rgba(15, 23, 42, 0.06);
    }
    
    [data-testid="stSidebar"] h3 {
        font-size: 1.6rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.25rem;
        letter-spacing: -0.03em;
    }
    
    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, rgba(148, 163, 184, 0.1), rgba(148, 163, 184, 0.6), rgba(148, 163, 184, 0.1));
    }
    
    /* Hero header */
    .hero-header {
        background:
            radial-gradient(circle at top left, rgba(79, 195, 247, 0.12), transparent 55%),
            radial-gradient(circle at bottom right, rgba(129, 199, 132, 0.12), transparent 55%),
            linear-gradient(135deg, #ffffff, #f4f6fb);
        border-radius: 24px;
        padding: 28px 32px;
        margin-bottom: 32px;
        border: 1px solid rgba(148, 163, 184, 0.4);
        box-shadow:
            0 16px 40px rgba(15, 23, 42, 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.7);
        position: relative;
        overflow: hidden;
    }
    
    .hero-title {
        font-size: 2.4rem;
        font-weight: 900;
        color: #0f172a;
        margin: 0;
        letter-spacing: -0.04em;
    }
    
    .hero-subtitle {
        font-size: 1.1rem;
        color: #6b7280;
        margin-top: 8px;
        font-weight: 400;
    }
    
    .status-indicator {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        background: #e8f5e9;
        border: 1px solid #a5d6a7;
        font-size: 0.8rem;
        font-weight: 600;
        color: #2e7d32;
        margin-bottom: 12px;
    }
    
    .status-indicator::before {
        content: '';
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #43a047;
    }
    
    /* Card */
    .spx-card {
        position: relative;
        background:
            linear-gradient(135deg, #ffffff, #f5f7fb);
        border-radius: 24px;
        border: 1px solid rgba(148, 163, 184, 0.45);
        box-shadow:
            0 18px 45px rgba(15, 23, 42, 0.06),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        padding: 28px 28px 24px 28px;
        margin-bottom: 28px;
    }
    
    .icon-large {
        font-size: 2.4rem;
        color: #1e88e5;
        margin-bottom: 8px;
        display: block;
    }
    
    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        border: 1px solid rgba(37, 99, 235, 0.3);
        background: rgba(219, 234, 254, 0.7);
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        color: #1d4ed8;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    
    .spx-card h4 {
        font-size: 1.4rem;
        font-weight: 800;
        color: #111827;
        margin: 0 0 8px 0;
        letter-spacing: -0.02em;
    }
    
    .spx-sub {
        color: #6b7280;
        font-size: 0.98rem;
        line-height: 1.6;
        font-weight: 400;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.35rem;
        font-weight: 800;
        color: #111827;
        margin: 1.8rem 0 1rem 0;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.6);
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .section-header::before {
        content: '';
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: #1e88e5;
    }
    
    /* Metric card */
    .spx-metric {
        position: relative;
        padding: 20px 18px;
        border-radius: 18px;
        background: #ffffff;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 12px 30px rgba(15, 23, 42, 0.05),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
    }
    
    .spx-metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #6b7280;
        font-weight: 600;
        margin-bottom: 6px;
    }
    
    .spx-metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #111827;
        letter-spacing: -0.03em;
    }
    
    /* Buttons */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #1e88e5, #1565c0);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 10px 22px;
        font-weight: 700;
        font-size: 0.95rem;
        letter-spacing: 0.06em;
        box-shadow:
            0 10px 20px rgba(37, 99, 235, 0.22);
        cursor: pointer;
        transition: all 0.2s ease;
        text-transform: uppercase;
    }
    
    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-1px);
        box-shadow:
            0 12px 28px rgba(37, 99, 235, 0.28);
    }
    
    .stButton>button:active, .stDownloadButton>button:active {
        transform: translateY(0px);
        box-shadow:
            0 8px 18px rgba(37, 99, 235, 0.22);
    }
    
    /* Inputs */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 1px solid rgba(148, 163, 184, 0.7) !important;
        border-radius: 12px !important;
        color: #111827 !important;
        padding: 10px 12px !important;
        font-size: 0.97rem !important;
        font-weight: 500 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: #1d4ed8 !important;
        box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.18) !important;
    }
    
    /* Radio */
    .stRadio>div {
        gap: 10px;
        flex-wrap: wrap;
    }
    
    .stRadio>div>label {
        background: #ffffff;
        padding: 8px 14px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.7);
        font-size: 0.9rem;
        font-weight: 500;
        color: #374151;
    }
    
    .stRadio>div>label[data-selected="true"] {
        border-color: #1e88e5;
        background: #e3f2fd;
        color: #1e3a8a;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: rgba(255, 255, 255, 0.9);
        padding: 6px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 999px;
        color: #6b7280;
        font-weight: 600;
        font-size: 0.92rem;
        padding: 8px 18px;
        border: none;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(226, 232, 240, 0.7);
        color: #111827;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #1e88e5;
        color: #ffffff;
    }
    
    /* Dataframe */
    .stDataFrame {
        border-radius: 16px;
        overflow: hidden;
        box-shadow:
            0 16px 36px rgba(15, 23, 42, 0.06);
        border: 1px solid rgba(148, 163, 184, 0.6);
    }
    
    .stDataFrame div[data-testid="StyledTable"] {
        font-variant-numeric: tabular-nums;
        font-size: 0.93rem;
        font-family: 'JetBrains Mono', monospace;
        background: #ffffff;
    }
    
    .stDataFrame thead tr th {
        background: #e5e9f2 !important;
        color: #374151 !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.75rem !important;
        padding: 10px 8px !important;
        border-bottom: 1px solid rgba(148, 163, 184, 0.8) !important;
    }
    
    .stDataFrame tbody tr td {
        padding: 8px !important;
        border-bottom: 1px solid rgba(229, 231, 235, 0.9) !important;
        color: #111827 !important;
        font-weight: 400 !important;
    }
    
    .stDataFrame tbody tr:hover {
        background: #f3f4f6 !important;
    }
    
    /* Messages */
    .stSuccess {
        background: #e8f5e9;
        border-radius: 16px;
        border: 1px solid #a5d6a7;
        padding: 16px 18px;
        color: #1b5e20;
        font-size: 0.95rem;
    }
    
    .stWarning {
        background: #fff8e1;
        border-radius: 16px;
        border: 1px solid #ffe082;
        padding: 16px 18px;
        color: #8d6e00;
        font-size: 0.95rem;
    }
    
    .stInfo {
        background: #e3f2fd;
        border-radius: 16px;
        border: 1px solid #90caf9;
        padding: 16px 18px;
        color: #0d47a1;
        font-size: 0.95rem;
    }
    
    .muted {
        color: #4b5563;
        font-size: 0.95rem;
        line-height: 1.6;
        padding: 14px 16px;
        background: #f9fafb;
        border-left: 3px solid #cbd5e1;
        border-radius: 8px;
        margin: 16px 0;
    }
    
    label {
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        color: #4b5563 !important;
        margin-bottom: 4px !important;
    }
    
    .app-footer {
        margin-top: 2.5rem;
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
    st.markdown("""
    <div class="hero-header">
        <div class="status-indicator">System active</div>
        <h1 class="hero-title">SPX Prophet v7.0</h1>
        <p class="hero-subtitle">Where Structure Becomes Foresight.</p>
    </div>
    """, unsafe_allow_html=True)


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


def metric_card(label: str, value: str, icon: str = "●"):
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
        rows.append({
            "Time": dt.strftime("%H:%M"),
            "Top Rail": round(top, 4),
            "Bottom Rail": round(bottom, 4),
        })
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
        rows.append({
            "Time": dt.strftime("%H:%M"),
            "Contract Price": round(price, 4),
        })
    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# DAILY FORESIGHT HELPERS
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

    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(f"<span class='spx-sub'>{TAGLINE}</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("#### Core slope")
        st.write(f"SPX rail slope magnitude: **{SLOPE_MAG} pts / 30 min**")
        st.caption("All calculations use a uniform 30 minute grid.")
        
        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "Underlying maintenance: 16:00 to 17:00 CT\n\n"
            "Contracts maintenance: 16:00 to 19:00 CT\n\n"
            "RTH projection window: 08:30 to 14:30 CT."
        )

    hero()

    tabs = st.tabs([
        "SPX Channel Setup",
        "Contract Slope Setup",
        "Daily Foresight Card",
        "About",
    ])

    # TAB 1
    with tabs[0]:
        card(
            "SPX Channel Setup",
            "Define your engulfing pivots, pick the channel direction, and project parallel rails across the session.",
            badge="Rails engine",
            icon="📊"
        )

        section_header("Pivots configuration")
        st.markdown(
            "<p class='spx-sub' style='margin-bottom:18px;'>"
            "Choose the highest and lowest engulfing reversals you trust between 15:00 and 07:30 CT."
            "</p>",
            unsafe_allow_html=True
        )
        
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### High pivot")
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
            st.markdown("#### Low pivot")
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

        section_header("Channel regime")
        mode = st.radio(
            "Select your channel mode",
            ["Ascending", "Descending", "Both"],
            index=0,
            key="channel_mode",
            horizontal=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("Build channel", key="build_channel_btn", use_container_width=True):
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

                st.success("Channel generated. Review the tables here and the Daily Foresight tab for the combined view.")

        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        section_header("Channel projections 08:30 to 14:30 CT")
        
        if df_asc is None and df_desc is None:
            st.info("Build at least one channel to view projections.")
        else:
            if df_asc is not None:
                st.markdown("<h4 style='font-size:1.15rem; margin:10px 0 10px;'>Ascending channel</h4>", unsafe_allow_html=True)
                c_top = st.columns([3, 1], gap="large")
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True, height=360)
                with c_top[1]:
                    st.markdown(metric_card("Channel height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
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
                st.markdown("<h4 style='font-size:1.15rem; margin:20px 0 10px;'>Descending channel</h4>", unsafe_allow_html=True)
                c_bot = st.columns([3, 1], gap="large")
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True, height=360)
                with c_bot[1]:
                    st.markdown(metric_card("Channel height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
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

    # TAB 2
    with tabs[1]:
        card(
            "Contract slope setup",
            "Use two contract prices to define a simple line on the same time grid as the rails.",
            badge="Contract engine",
            icon="📐"
        )

        ph_time: dtime = st.session_state.get("pivot_high_time", dtime(15, 0))
        pl_time: dtime = st.session_state.get("pivot_low_time", dtime(3, 0))

        section_header("Anchor A origin")
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
                f"<div class='muted'>Anchor A time set to high pivot time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT.</div>",
                unsafe_allow_html=True,
            )
        elif anchor_a_source == "Low pivot time":
            anchor_a_time = pl_time
            st.markdown(
                f"<div class='muted'>Anchor A time set to low pivot time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT.</div>",
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

        section_header("Anchor B second point")
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
            if st.button("Build contract projection", key="build_contract_btn", use_container_width=True):
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
                st.success("Contract projection generated. Review the table and the Daily Foresight tab for combined guidance.")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        section_header("Contract projection 08:30 to 14:30 CT")
        
        if df_contract is None:
            st.info("Build a contract projection to see projected prices.")
        else:
            c_top = st.columns([3, 1], gap="large")
            with c_top[0]:
                st.dataframe(df_contract, use_container_width=True, hide_index=True, height=360)
            with c_top[1]:
                st.markdown(metric_card("Contract slope", f"{slope_contract:+.4f} per 30 min"), unsafe_allow_html=True)
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

    # TAB 3
    with tabs[2]:
        card(
            "Daily foresight card",
            "Rails and contract line combined into a simple time based playbook.",
            badge="Foresight",
            icon="🧭"
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
            contract_move_per_channel = slope_contract * blocks_for_channel if blocks_for_channel != 0 else 0.0
            contract_gain_abs = abs(contract_move_per_channel)

            section_header("Structure summary")
            c1, c2, c3 = st.columns(3, gap="large")
            with c1:
                st.markdown(metric_card("Active channel", df_mode or "Not set"), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Channel height", f"{h_ch:.2f} pts"), unsafe_allow_html=True)
            with c3:
                st.markdown(
                    metric_card("Contract change for one channel", f"{contract_gain_abs:.2f} units"),
                    unsafe_allow_html=True
                )

            section_header("Inside channel play")
            st.markdown(f"""
            <div class='spx-sub' style='font-size:0.98rem;'>
              <p><strong>Long idea</strong> buy at the lower rail, exit at the upper rail.</p>
              <ul style='margin-left:18px;'>
                <li>Underlying move: about <strong>{h_ch:.2f} points</strong> in your favor.</li>
                <li>Typical contract change for a full swing: about <strong>{contract_gain_abs:.2f}</strong> units based on the current contract slope.</li>
              </ul>

              <p><strong>Short idea</strong> sell at the upper rail, exit at the lower rail.</p>
              <ul style='margin-left:18px;'>
                <li>Underlying move: about <strong>{h_ch:.2f} points</strong> in your favor, opposite direction.</li>
                <li>Same contract size of move in the opposite direction, from the same contract slope.</li>
              </ul>

              <p>This is a structural size of move, not a full options model. A real jump such as 5.20 to 50.68 will often be larger than this estimate because of volatility and time effects.</p>
            </div>
            """, unsafe_allow_html=True)

            section_header("Breakout and breakdown ideas")
            st.markdown(f"""
            <div class='spx-sub' style='font-size:0.98rem;'>
              <p><strong>Breakout above the upper rail</strong></p>
              <ul style='margin-left:18px;'>
                <li>Entry on a clean retest of the upper rail from above.</li>
                <li>Continuation target in price: roughly one additional channel height beyond the rail.</li>
                <li>Same channel size contract move estimate used as a guide, not a promise.</li>
              </ul>

              <p><strong>Breakdown below the lower rail</strong></p>
              <ul style='margin-left:18px;'>
                <li>Entry on a clean retest of the lower rail from below.</li>
                <li>Continuation target in price: roughly one additional channel height below that rail.</li>
              </ul>
            </div>
            """, unsafe_allow_html=True)

            section_header("Contract trade estimator")

            times = merged["Time"].tolist()
            if times:
                col_e, col_x = st.columns(2, gap="large")
                with col_e:
                    entry_time = st.selectbox(
                        "Entry time when the rail is touched",
                        times,
                        index=0,
                        key="foresight_entry_time",
                    )
                with col_x:
                    exit_time = st.selectbox(
                        "Exit time",
                        times,
                        index=min(len(times) - 1, 4),
                        key="foresight_exit_time",
                    )

                entry_row = merged[merged["Time"] == entry_time].iloc[0]
                exit_row = merged[merged["Time"] == exit_time].iloc[0]

                entry_contract = float(entry_row["Contract Price"])
                exit_contract = float(exit_row["Contract Price"])
                pnl_contract = exit_contract - entry_contract

                c1_est, c2_est, c3_est = st.columns(3, gap="large")
                with c1_est:
                    st.markdown(metric_card("Entry contract", f"{entry_contract:.2f}"), unsafe_allow_html=True)
                with c2_est:
                    st.markdown(metric_card("Exit contract", f"{exit_contract:.2f}"), unsafe_allow_html=True)
                with c3_est:
                    st.markdown(
                        metric_card("Projected PnL", f"{pnl_contract:+.2f} units"),
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    "<div class='muted'><strong>How to use this estimator.</strong> "
                    "Pick the time you expect the rail touch to happen as your entry, "
                    "pick your planned exit time, and compare this projected contract move with what the market actually gave you. "
                    "The difference is your volatility and skew bonus on that day.</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("No merged data yet. Build a channel and a contract projection first.")

            section_header("Time aligned map")
            st.caption("Every row is a 30 minute slot in RTH. If SPX tags a rail at that time, this is the structural contract level from your anchors.")
            st.dataframe(merged, use_container_width=True, hide_index=True, height=420)

            st.markdown(
                "<div class='muted'><strong>Reading the map.</strong> "
                "The grid does not tell you when the tag will happen. "
                "It tells you what your structure expects the contract to be worth if the tag happens at a given time.</div>",
                unsafe_allow_html=True,
            )

            end_card()

    # TAB 4
    with tabs[3]:
        card("About SPX Prophet v7.0", TAGLINE, badge="Version 7.0", icon="ℹ️")
        st.markdown(
            """
            <div class='spx-sub' style='font-size:1rem;'>
            <p>SPX Prophet is built on a simple idea.</p>

            <p><strong>Two pivots define the rails and the slope carries that structure into the session.</strong></p>

            <ul style='margin-left:18px;'>
                <li>Rails are projected with a uniform slope of ±0.475 points per 30 minutes.</li>
                <li>Pivots are engulfing reversals chosen by you between 15:00 and 07:30 CT.</li>
                <li>Channels can be viewed as ascending, descending, or inspected both ways.</li>
                <li>Contracts follow a straight line defined by two anchor prices on the same grid.</li>
            </ul>

            <p>The app does not claim to model full options behavior. It gives you a clean structural map so that when price returns to your rails, you are not reacting blindly. You already have a framework and a plan.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='muted'><strong>Maintenance windows.</strong> "
            "SPX 16:00 to 17:00 CT. Contracts 16:00 to 19:00 CT.</div>",
            unsafe_allow_html=True,
        )
        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet v7.0. Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()