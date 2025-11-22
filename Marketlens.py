# spx_prophet.py
# SPX Prophet — Where Structure Becomes Foresight.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

# ===============================
# CORE CONSTANTS
# ===============================

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475         # Rails slope (points per 30m)
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 anchor for blocks
DEFAULT_CONTRACT_FACTOR = 0.30           # Contract move ≈ factor × SPX move


# ===============================
# UI: STUNNING LIGHT MODE
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.06), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.06), transparent 60%),
          radial-gradient(circle 1200px at 50% 50%, rgba(148, 163, 184, 0.07), transparent),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 30%, #f1f5f9 60%, #f8fafc 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    .block-container {
        padding-top: 2.8rem;
        padding-bottom: 4rem;
        max-width: 1400px;
    }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.08), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            6px 0 24px rgba(15, 23, 42, 0.05),
            2px 0 12px rgba(15, 23, 42, 0.03);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.4rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 40%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
        letter-spacing: -0.03em;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.6rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.8) 40%,
            rgba(148, 163, 184, 0.4) 60%,
            transparent 100%);
    }

    [data-testid="stSidebar"] h4 {
        color: #4b5563;
        font-size: 0.9rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.11em;
        margin-top: 1.8rem;
        margin-bottom: 0.7rem;
    }

    /* HERO HEADER CENTERED */
    .hero-header {
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.10), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(56, 189, 248, 0.10), transparent 60%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 32px;
        padding: 36px 40px 40px 40px;
        margin: 0 auto 36px auto;
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            0 24px 60px -18px rgba(15, 23, 42, 0.25),
            0 12px 30px -12px rgba(15, 23, 42, 0.14);
        overflow: hidden;
        text-align: center;
    }

    .hero-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: -40%;
        width: 180%;
        height: 3px;
        background: linear-gradient(90deg, #6366f1, #0ea5e9, #22c55e, #6366f1);
        background-size: 200% 100%;
        opacity: 0.9;
        animation: shimmer 6s linear infinite;
    }

    @keyframes shimmer {
        0% { transform: translateX(0%); }
        100% { transform: translateX(30%); }
    }

    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 14px;
        padding: 8px 18px;
        border-radius: 999px;
        background: rgba(34, 197, 94, 0.06);
        border: 1px solid rgba(34, 197, 94, 0.35);
        color: #15803d;
        font-size: 0.8rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        font-weight: 700;
    }

    .hero-badge-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 10px rgba(34, 197, 94, 0.9);
        animation: pulseDot 2s ease-in-out infinite;
    }

    @keyframes pulseDot {
        0%, 100% { transform: scale(1); opacity: 1; }
        50%      { transform: scale(0.9); opacity: 0.8; }
    }

    .hero-title {
        font-size: 3.2rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 40%, #0ea5e9 70%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.05em;
    }

    .hero-subtitle {
        font-size: 1.2rem;
        color: #475569;
        margin-top: 8px;
        font-weight: 500;
        font-family: 'Poppins', sans-serif;
    }

    .hero-tagline {
        margin-top: 16px;
        font-size: 0.95rem;
        color: #6b7280;
    }

    /* CARDS */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 8% 8%, rgba(99, 102, 241, 0.06), transparent 55%),
            radial-gradient(circle at 92% 92%, rgba(56, 189, 248, 0.06), transparent 50%),
            linear-gradient(135deg, #ffffff, #fefefe);
        border-radius: 28px;
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            0 22px 50px -18px rgba(15, 23, 42, 0.18),
            0 10px 24px -12px rgba(15, 23, 42, 0.12);
        padding: 28px 32px 32px 32px;
        margin-bottom: 32px;
        overflow: hidden;
    }

    .spx-card h4 {
        font-size: 1.7rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 10px 0;
        letter-spacing: -0.03em;
    }

    .icon-large {
        font-size: 3rem;
        background: linear-gradient(135deg, #6366f1, #0ea5e9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 10px;
        display: block;
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        border: 1px solid rgba(129, 140, 248, 0.7);
        background:
            linear-gradient(135deg, rgba(129, 140, 248, 0.14), rgba(59, 130, 246, 0.10)),
            #ffffff;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        color: #4338ca;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .spx-sub {
        color: #4b5563;
        font-size: 0.98rem;
        line-height: 1.7;
        font-weight: 400;
    }

    /* SECTION HEADERS */
    .section-header {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 2.4rem 0 1.2rem 0;
        padding-bottom: 0.6rem;
        border-bottom: 2px solid rgba(148, 163, 184, 0.6);
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .section-header::before {
        content: '';
        width: 12px;
        height: 12px;
        border-radius: 999px;
        background: linear-gradient(135deg, #1d4ed8, #0ea5e9);
        box-shadow:
            0 0 16px rgba(37, 99, 235, 0.9),
            0 3px 8px rgba(15, 23, 42, 0.4);
    }

    /* METRICS */
    .spx-metric {
        position: relative;
        padding: 22px 20px;
        border-radius: 20px;
        background:
            radial-gradient(circle at top left, rgba(129, 140, 248, 0.10), transparent 70%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border: 1px solid rgba(191, 219, 254, 0.9);
        box-shadow:
            0 12px 32px rgba(148, 163, 184, 0.35),
            0 6px 16px rgba(15, 23, 42, 0.10);
    }

    .spx-metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 6px;
    }

    .spx-metric-value {
        font-size: 1.7rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
    }

    /* BUTTONS */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #1d4ed8 0%, #0ea5e9 50%, #22c55e 100%);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 12px 26px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.12em;
        box-shadow:
            0 16px 35px rgba(37, 99, 235, 0.35),
            0 8px 18px rgba(15, 23, 42, 0.18);
        cursor: pointer;
        text-transform: uppercase;
    }

    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-2px);
        box-shadow:
            0 20px 40px rgba(37, 99, 235, 0.45),
            0 10px 22px rgba(15, 23, 42, 0.22);
    }

    /* INPUTS */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        border-radius: 14px !important;
        color: #0f172a !important;
        padding: 10px 14px !important;
        font-size: 0.98rem !important;
        font-weight: 500 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background:
            linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.98));
        padding: 6px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.7);
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

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #1d4ed8, #0ea5e9);
        color: #ffffff;
        box-shadow:
            0 10px 24px rgba(37, 99, 235, 0.35),
            0 4px 10px rgba(15, 23, 42, 0.18);
    }

    /* DATAFRAME */
    .stDataFrame {
        border-radius: 20px;
        overflow: hidden;
        box-shadow:
            0 16px 38px rgba(148, 163, 184, 0.45),
            0 8px 18px rgba(15, 23, 42, 0.20);
        border: 1px solid rgba(148, 163, 184, 0.8);
    }

    .muted {
        color: #4b5563;
        font-size: 0.95rem;
        line-height: 1.7;
        padding: 16px 18px;
        background:
            linear-gradient(135deg, rgba(148, 163, 184, 0.10), rgba(226, 232, 240, 0.70));
        border-left: 3px solid #1d4ed8;
        border-radius: 12px;
        margin: 16px 0;
    }

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
            <div class="hero-badge">
                <div class="hero-badge-dot"></div>
                SYSTEM ACTIVE • STRUCTURE MODE
            </div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">{TAGLINE}</p>
            <p class="hero-tagline">
                Two pivots define your rails. Expected move frames your day. 
                Contracts follow the structure, not the noise.
            </p>
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


def metric_card(label: str, value: str) -> str:
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
    # If time >= 15:00, treat as "today" BASE_DATE date; else next day
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    # Align a datetime to the nearest 30m block (15 threshold)
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    # RTH grid 08:30–14:30 CT on "next day"
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


# ===============================
# STRUCTURAL CHANNEL ENGINE
# ===============================

def build_structural_channel(
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

    # Two lines: top and bottom
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
# EXPECTED MOVE CHANNEL ENGINE
# ===============================

def build_em_channel(
    em_points: float,
    anchor_price: float,
    anchor_time: dtime,
    orientation: str,
) -> pd.DataFrame:
    """
    EM channel uses the same slope magnitude as the rails.
    Anchor price is treated as the LOWER rail for 'Up', and LOWER rail for 'Down' as well,
    but the slope sign flips. The vertical distance between rails is em_points.
    """
    s = +SLOPE_MAG if orientation == "Up" else -SLOPE_MAG

    dt_anchor = align_30min(make_dt_from_time(anchor_time))
    k_anchor = blocks_from_base(dt_anchor)

    # Anchor is lower rail at anchor time
    b_bottom = anchor_price - s * k_anchor
    b_top = b_bottom + em_points

    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        bottom = s * k + b_bottom
        top = s * k + b_top
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "EM Bottom": round(bottom, 4),
                "EM Top": round(top, 4),
            }
        )
    return pd.DataFrame(rows)


# ===============================
# DAILY FORESIGHT HELPERS
# ===============================

def get_active_structural_channel() -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[float]]:
    mode = st.session_state.get("channel_mode_struct")
    df_asc = st.session_state.get("struct_asc_df")
    df_desc = st.session_state.get("struct_desc_df")
    h_asc = st.session_state.get("struct_asc_height")
    h_desc = st.session_state.get("struct_desc_height")

    if mode == "Ascending":
        return "Ascending", df_asc, h_asc
    if mode == "Descending":
        return "Descending", df_desc, h_desc
    if mode == "Both":
        scenario = st.selectbox(
            "Active structural scenario",
            ["Ascending", "Descending"],
            index=0,
            key="foresight_struct_scenario",
        )
        if scenario == "Ascending":
            return "Ascending", df_asc, h_asc
        else:
            return "Descending", df_desc, h_desc
    return None, None, None


def get_contract_factor() -> float:
    # If user calibrated from a real trade, use that; otherwise use sidebar value
    calibrated = st.session_state.get("contract_factor_calibrated")
    if calibrated is not None:
        return calibrated
    else:
        return st.session_state.get("contract_factor_input", DEFAULT_CONTRACT_FACTOR)


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

    # SIDEBAR
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.caption(TAGLINE)
        st.markdown("---")

        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG} pts / 30m**")

        contract_factor_input = st.number_input(
            "Contract factor (× SPX move)",
            min_value=0.05,
            max_value=1.00,
            value=DEFAULT_CONTRACT_FACTOR,
            step=0.05,
            key="contract_factor_input",
            help="Approx contract move per 1 point of SPX move (e.g. 0.30 means 30% of SPX move).",
        )

        st.markdown(
            f"<p class='spx-sub' style='margin-top:4px;'><b>Current factor in use:</b> "
            f"{get_contract_factor():.2f}</p>",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Underlying: 16:00–17:00 CT maintenance\n\n"
            "• Contracts: 16:00–19:00 CT maintenance\n\n"
            "• RTH projection grid: 08:30–14:30 CT (30m blocks)."
        )

    # HERO
    hero()

    # TABS
    tabs = st.tabs(
        [
            "🧱 Rails & EM Setup",
            "📐 Contract Factor & Calibration",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # ==========================
    # TAB 1: RAILS & EM SETUP
    # ==========================
    with tabs[0]:
        card(
            "Structure Engine",
            "Build your structural rails from previous RTH pivot shelves and overlay the expected move channel.",
            badge="Rails + EM",
            icon="🧱",
        )

        # Structural pivots
        section_header("⚙️ Previous RTH Pivots (Channel)")
        st.markdown(
            """
            <div class='spx-sub'>
            Use the <b>dominant pivot high and low from the previous RTH</b> as seen on your 30m line chart.
            Not the absolute wick extremes, but the shelves where price actually turned.
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Pivot High")
            high_price = st.number_input(
                "Pivot high price",
                value=5200.0,
                step=0.25,
                key="pivot_high_price_struct",
            )
            high_time = st.time_input(
                "Pivot high time (CT)",
                value=dtime(11, 0),
                step=1800,
                key="pivot_high_time_struct",
            )
        with c2:
            st.markdown("#### Pivot Low")
            low_price = st.number_input(
                "Pivot low price",
                value=5100.0,
                step=0.25,
                key="pivot_low_price_struct",
            )
            low_time = st.time_input(
                "Pivot low time (CT)",
                value=dtime(13, 30),
                step=1800,
                key="pivot_low_time_struct",
            )

        section_header("📊 Channel Regime")
        mode = st.radio(
            "Select structural channel mode",
            ["Ascending", "Descending", "Both"],
            index=0,
            key="channel_mode_struct",
            horizontal=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("⚡ Build Structural Rails", key="build_struct_channel_btn", use_container_width=True):
                if mode in ("Ascending", "Both"):
                    df_asc, h_asc = build_structural_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=+1,
                    )
                    st.session_state["struct_asc_df"] = df_asc
                    st.session_state["struct_asc_height"] = h_asc
                else:
                    st.session_state["struct_asc_df"] = None
                    st.session_state["struct_asc_height"] = None

                if mode in ("Descending", "Both"):
                    df_desc, h_desc = build_structural_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=-1,
                    )
                    st.session_state["struct_desc_df"] = df_desc
                    st.session_state["struct_desc_height"] = h_desc
                else:
                    st.session_state["struct_desc_df"] = None
                    st.session_state["struct_desc_height"] = None

                st.success("Structural rails generated. Check the tables below and the Daily Foresight tab.")

        df_asc = st.session_state.get("struct_asc_df")
        df_desc = st.session_state.get("struct_desc_df")
        h_asc = st.session_state.get("struct_asc_height")
        h_desc = st.session_state.get("struct_desc_height")

        section_header("📊 Structural Rails • RTH 08:30–14:30 CT")

        if df_asc is None and df_desc is None:
            st.info("Build at least one structural channel to view projections.")
        else:
            if df_asc is not None:
                st.markdown(
                    "<h4 style='font-size:1.2rem; margin:10px 0;'>📈 Ascending Channel</h4>",
                    unsafe_allow_html=True,
                )
                c_top = st.columns([3, 1])
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True, height=320)
                with c_top[1]:
                    st.markdown(metric_card("Channel Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download CSV",
                        df_asc.to_csv(index=False).encode(),
                        "spx_struct_ascending.csv",
                        "text/csv",
                        key="dl_struct_asc",
                        use_container_width=True,
                    )

            if df_desc is not None:
                st.markdown(
                    "<h4 style='font-size:1.2rem; margin:22px 0 10px;'>📉 Descending Channel</h4>",
                    unsafe_allow_html=True,
                )
                c_bot = st.columns([3, 1])
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True, height=320)
                with c_bot[1]:
                    st.markdown(metric_card("Channel Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download CSV",
                        df_desc.to_csv(index=False).encode(),
                        "spx_struct_descending.csv",
                        "text/csv",
                        key="dl_struct_desc",
                        use_container_width=True,
                    )

        # EM CHANNEL
        section_header("📊 EM Channel")
        st.markdown(
            """
            <div class='spx-sub'>
            Use the daily expected move as a <b>sloped channel</b> on the same 0.475 grid. 
            Anchor it to the level you believe they are defending (often a key RTH pivot or 17:00 print).
            </div>
            """,
            unsafe_allow_html=True,
        )

        c_em1, c_em2, c_em3 = st.columns(3)
        with c_em1:
            em_points_input = st.number_input(
                "Expected Move (points)",
                value=80.0,
                step=0.5,
                key="em_points_input",
            )
        with c_em2:
            em_anchor_price_input = st.number_input(
                "EM anchor price",
                value=6700.0,
                step=0.5,
                key="em_anchor_price_input",
            )
        with c_em3:
            em_anchor_time_input = st.time_input(
                "EM anchor time (CT)",
                value=dtime(17, 0),
                step=1800,
                key="em_anchor_time_input",
            )

        em_orientation = st.radio(
            "EM orientation",
            ["Up", "Down"],
            index=0,
            key="em_orientation",
            horizontal=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn2 = st.columns([1, 3])[0]
        with col_btn2:
            if st.button("⚡ Build EM Channel", key="build_em_channel_btn", use_container_width=True):
                df_em = build_em_channel(
                    em_points=em_points_input,
                    anchor_price=em_anchor_price_input,
                    anchor_time=em_anchor_time_input,
                    orientation=em_orientation,
                )
                st.session_state["em_df"] = df_em
                st.session_state["em_points_value"] = float(em_points_input)
                st.session_state["em_orientation_value"] = em_orientation
                st.success("EM channel generated. Check the table below and the Daily Foresight tab.")

        df_em = st.session_state.get("em_df")
        em_points_value = st.session_state.get("em_points_value")

        if df_em is None:
            st.info("Build the EM channel to view its projections.")
        else:
            st.markdown(
                "<h4 style='font-size:1.2rem; margin:18px 0 10px;'>📈 EM Projection</h4>",
                unsafe_allow_html=True,
            )
            c_em_top = st.columns([3, 1])
            with c_em_top[0]:
                st.dataframe(df_em, use_container_width=True, hide_index=True, height=320)
            with c_em_top[1]:
                st.markdown(metric_card("EM Range", f"{em_points_value:.2f} pts"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "📥 Download CSV",
                    df_em.to_csv(index=False).encode(),
                    "spx_em_channel.csv",
                    "text/csv",
                    key="dl_em_channel",
                    use_container_width=True,
                )

        end_card()

    # ==========================
    # TAB 2: CONTRACT FACTOR
    # ==========================
    with tabs[1]:
        card(
            "Contract Factor & Calibration",
            "Tie your options to the structure: use a factor of SPX move or calibrate it from real trades.",
            badge="Contracts",
            icon="📐",
        )

        section_header("📏 Factor in Use")

        cf = get_contract_factor()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(metric_card("Contract Factor", f"{cf:.2f} × SPX"), unsafe_allow_html=True)
        with c2:
            st.markdown(
                """
                <div class='muted'>
                This factor is your <b“personal gamma multiplier</b>.
                If SPX moves 100 points and your factor is 0.30, you plan around a ~30 unit move on your contracts
                for a full structural swing.
                </div>
                """,
                unsafe_allow_html=True,
            )

        section_header("🎯 Quick Calibration From a Real Trade")

        st.markdown(
            """
            <div class='spx-sub'>
            If you have a real example (e.g. SPX moved 124 points and the contract went from 5.22 to 50.68),
            plug it in here and let the app compute the factor for you.
            </div>
            """,
            unsafe_allow_html=True,
        )

        c3, c4, c5 = st.columns(3)
        with c3:
            calib_spx_move = st.number_input(
                "SPX move (points)",
                value=0.0,
                step=1.0,
                key="calib_spx_move",
            )
        with c4:
            calib_contract_entry = st.number_input(
                "Contract entry price",
                value=0.0,
                step=0.1,
                key="calib_contract_entry",
            )
        with c5:
            calib_contract_exit = st.number_input(
                "Contract exit price",
                value=0.0,
                step=0.1,
                key="calib_contract_exit",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn_calib = st.columns([1, 3])[0]
        with col_btn_calib:
            if st.button("⚡ Calibrate Factor", key="calibrate_factor_btn", use_container_width=True):
                if calib_spx_move == 0:
                    st.warning("SPX move cannot be zero for calibration.")
                else:
                    contract_move = calib_contract_exit - calib_contract_entry
                    factor = contract_move / calib_spx_move
                    st.session_state["contract_factor_calibrated"] = factor
                    st.success(f"Calibrated factor set to {factor:.3f}. This now overrides the sidebar value.")

        end_card()

    # ==========================
    # TAB 3: DAILY FORESIGHT
    # ==========================
    with tabs[2]:
        card(
            "Daily Foresight",
            "Structural rails, EM channel, and contract factor combined into a clean action map.",
            badge="Foresight",
            icon="🔮",
        )

        df_mode, df_struct, h_struct = get_active_structural_channel()
        df_em = st.session_state.get("em_df")
        em_points_value = st.session_state.get("em_points_value")
        em_orientation_value = st.session_state.get("em_orientation_value")
        cf = get_contract_factor()

        if df_struct is None or h_struct is None:
            st.warning("No active structural channel found. Build one in the Rails & EM Setup tab first.")
            end_card()
        else:
            # Merge structural + EM if EM exists
            merged = df_struct.copy()
            if df_em is not None:
                merged = merged.merge(df_em, on="Time", how="left")
            else:
                merged["EM Bottom"] = None
                merged["EM Top"] = None

            # Midpoints
            merged["Rail Mid"] = (merged["Top Rail"] + merged["Bottom Rail"]) / 2.0
            if df_em is not None:
                merged["EM Mid"] = (merged["EM Top"] + merged["EM Bottom"]) / 2.0

            # Contract targets per full swing
            contract_target_struct = cf * h_struct
            contract_target_em = cf * em_points_value if (df_em is not None and em_points_value is not None) else None

            # Structure summary
            section_header("📊 Structure Summary")

            csum1, csum2, csum3 = st.columns(3)
            with csum1:
                st.markdown(metric_card("Active Structural", df_mode or "Not set"), unsafe_allow_html=True)
            with csum2:
                st.markdown(metric_card("Channel Height", f"{h_struct:.2f} pts"), unsafe_allow_html=True)
            with csum3:
                if df_em is not None and em_points_value is not None:
                    st.markdown(metric_card("EM Range", f"{em_points_value:.2f} pts"), unsafe_allow_html=True)
                else:
                    st.markdown(metric_card("EM Range", "Not set"), unsafe_allow_html=True)

            section_header("💹 Contract Size of Move")

            ccts1, ccts2 = st.columns(2)
            with ccts1:
                st.markdown(
                    metric_card(
                        "Full Structural Swing",
                        f"{contract_target_struct:+.2f} units",
                    ),
                    unsafe_allow_html=True,
                )
            with ccts2:
                if contract_target_em is not None:
                    st.markdown(
                        metric_card(
                            "Full EM Excursion",
                            f"{contract_target_em:+.2f} units",
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        metric_card(
                            "Full EM Excursion",
                            "EM not set",
                        ),
                        unsafe_allow_html=True,
                    )

            st.markdown(
                """
                <div class='muted'>
                <b>How to read this:</b> if price travels <b>one full structural channel</b> 
                from lower rail to upper rail, you build your contract expectations around 
                the number above. The same logic applies if the day stretches a full expected move.
                </div>
                """,
                unsafe_allow_html=True,
            )

            # PLAYBOOK
            section_header("📜 Playbook for the Day")

            em_text = ""
            if df_em is not None and em_points_value is not None:
                em_text = (
                    f"The EM channel is <b>{em_orientation_value.lower()}</b>-oriented with a range of "
                    f"<b>{em_points_value:.1f} points</b>. This frames your outer boundary."
                )
            else:
                em_text = "EM channel not set. You are trading purely off the structural rails today."

            st.markdown(
                f"""
                <div class='spx-sub' style='line-height:1.8;'>
                  <p><b>1. Structural bias:</b> The active channel is <b>{df_mode}</b>. 
                  That means your baseline expectation is that price respects this sloped zone until proven otherwise.</p>

                  <p><b>2. EM frame:</b> {em_text}</p>

                  <p><b>3. Long Call Template:</b></p>
                  <ul style='margin-left:22px;'>
                    <li>Wait for price to <b>push down into or slightly through the lower structural rail</b>.</li>
                    <li>Prefer entries where the lower rail and EM bottom are reasonably close.</li>
                    <li>Frame your take profit around <b>½ to 1×</b> the full structural contract target 
                        (<b>{contract_target_struct/2:.2f} to {contract_target_struct:.2f} units</b>).</li>
                  </ul>

                  <p><b>4. Long Put Template:</b></p>
                  <ul style='margin-left:22px;'>
                    <li>Wait for price to <b>push up into or slightly through the upper structural rail</b>.</li>
                    <li>Prefer entries near the upper EM band when it lines up with the structural top.</li>
                    <li>Same contract sizing logic: <b>½ to 1×</b> the structural target, in the opposite direction.</li>
                  </ul>

                  <p><b>5. No-Trade Conditions:</b></p>
                  <ul style='margin-left:22px;'>
                    <li>Price chopping around the <b>mid of the channel</b> with no clean tests of the rails.</li>
                    <li>Price pinned between <b>EM mid</b> and <b>Rail mid</b> with overlapping candles and no clean trend.</li>
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # TIME-ALIGNED MAP
            section_header("🗺️ Time-Aligned Map")

            st.caption(
                "Every row is a 30-minute slot in RTH. Use it as a structural map: "
                "where are the rails and EM at any given time?"
            )

            display_cols = ["Time", "Top Rail", "Bottom Rail", "Rail Mid"]
            if df_em is not None:
                display_cols += ["EM Top", "EM Bottom", "EM Mid"]

            st.dataframe(
                merged[display_cols],
                use_container_width=True,
                hide_index=True,
                height=480,
            )

            st.markdown(
                """
                <div class='muted'>
                <b>Reading the map:</b> the grid does not tell you when the tag will happen. 
                It tells you what your structure expects the rails (and EM bands) to be worth if that tag happens at a given time.
                You bring your tape reading, order flow, and experience on top of this.
                </div>
                """,
                unsafe_allow_html=True,
            )

        end_card()

    # ==========================
    # TAB 4: ABOUT
    # ==========================
    with tabs[3]:
        card(
            "About SPX Prophet",
            TAGLINE,
            badge="Version: Structure Engine",
            icon="ℹ️",
        )
        st.markdown(
            """
            <div class='spx-sub' style='font-size:1.02rem; line-height:1.8;'>
            <p>SPX Prophet is built around a simple idea:</p>

            <p style='font-size:1.05rem; color:#1d4ed8; font-weight:600; margin:16px 0;'>
            <b>Previous RTH pivot shelves define your rails. The expected move defines your outer frame. 
            Contracts ride on top of that structure with a stable factor.</b>
            </p>

            <ul style='margin-left:24px;'>
                <li>Structural rails use a <b>uniform slope of ±0.475 points per 30 minutes</b>.</li>
                <li>Pivots are <b>dominant shelves</b> from the previous RTH, not just wick extremes.</li>
                <li>EM is applied as a <b>sloped channel</b> on the same grid, with its own anchor and direction.</li>
                <li>Contracts are summarized by a <b>factor</b> (e.g. 0.30 × SPX) derived from your real trades.</li>
            </ul>

            <p style='margin-top:20px;'>
            The goal is not to predict every tick. The goal is to start each day with a <b>clear structural script</b>,
            so that when price returns to your zones, you are calm, prepared, and sized appropriately.
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        end_card()

    # FOOTER
    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()