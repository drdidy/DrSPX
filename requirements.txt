# spx_prophet.py
# SPX Prophet - Light Mode Legendary Edition

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."

SLOPE_MAG = 0.475          # points per 30 minutes for rails
CONTRACT_FACTOR_DEFAULT = 0.33  # contract move per 1 point SPX move
MIN_CONTRACT_MOVE = 9.9    # below this, likely not worth trading the channel

# Base reference: previous session "afternoon anchor"
BASE_DATE = datetime(2000, 1, 1, 15, 0)


# ===============================
# STUNNING LIGHT MODE UI
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.07), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.07), transparent 60%),
          radial-gradient(circle 1200px at 50% 50%, rgba(148, 163, 184, 0.05), transparent),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 30%, #f1f5f9 60%, #f8fafc 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.08), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.35);
        box-shadow:
            8px 0 40px rgba(148, 163, 184, 0.20),
            4px 0 16px rgba(15, 23, 42, 0.05);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        text-align: left;
        margin-bottom: 0.25rem;
        letter-spacing: -0.03em;
        color: #111827;
    }

    .sidebar-tagline {
        font-size: 0.9rem;
        color: #6b7280;
        font-weight: 500;
        margin-bottom: 0.75rem;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.8) 20%,
            rgba(148, 163, 184, 0.8) 80%,
            transparent 100%);
    }

    /* Hero */
    .hero-header {
        position: relative;
        border-radius: 32px;
        padding: 32px 40px;
        margin-bottom: 32px;
        background:
            radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.13), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(56, 189, 248, 0.16), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 24px 60px rgba(148, 163, 184, 0.28),
            0 12px 24px rgba(15, 23, 42, 0.10),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        overflow: hidden;
    }

    .hero-title {
        font-size: 2.7rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        text-align: center;
        margin: 0;
        letter-spacing: -0.05em;
        background: linear-gradient(120deg, #0f172a, #1d4ed8, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        text-align: center;
        margin-top: 0.35rem;
        color: #6b7280;
        font-weight: 500;
    }

    .hero-status-row {
        display: flex;
        justify-content: center;
        gap: 12px;
        margin-top: 18px;
        flex-wrap: wrap;
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        background: #ecfdf3;
        color: #15803d;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border: 1px solid rgba(34, 197, 94, 0.5);
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 8px rgba(34, 197, 94, 0.7);
    }

    .status-pill-soft {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        background: #eff6ff;
        color: #1d4ed8;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border: 1px solid rgba(59, 130, 246, 0.45);
    }

    /* Cards */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 0% 0%, rgba(129, 140, 248, 0.12), transparent 55%),
            radial-gradient(circle at 100% 100%, rgba(56, 189, 248, 0.12), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 28px;
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            0 20px 50px rgba(148, 163, 184, 0.25),
            0 10px 20px rgba(15, 23, 42, 0.10),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        padding: 28px 30px;
        margin-bottom: 28px;
    }

    .spx-card h4 {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        margin: 0 0 8px 0;
        letter-spacing: -0.03em;
        color: #0f172a;
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        border: 1px solid rgba(129, 140, 248, 0.7);
        background: rgba(239, 246, 255, 0.8);
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: #4f46e5;
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    .spx-pill::before {
        content: "";
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: radial-gradient(circle, #4f46e5, #22d3ee);
    }

    .spx-sub {
        color: #4b5563;
        font-size: 0.98rem;
        line-height: 1.7;
        font-weight: 400;
    }

    .icon-large {
        font-size: 2rem;
        margin-bottom: 6px;
    }

    /* Section header */
    .section-header {
        font-size: 1.4rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        color: #111827;
        margin: 1.6rem 0 0.9rem 0;
        display: flex;
        align-items: center;
        gap: 10px;
        border-bottom: 1px solid rgba(209, 213, 219, 0.9);
        padding-bottom: 6px;
    }

    .section-header::before {
        content: "";
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: radial-gradient(circle, #4f46e5, #22d3ee);
        box-shadow: 0 0 12px rgba(79, 70, 229, 0.8);
    }

    /* Metric card (html chunk) */
    .spx-metric {
        padding: 18px 18px;
        border-radius: 18px;
        background:
            radial-gradient(circle at 0% 0%, rgba(129, 140, 248, 0.13), transparent 60%),
            linear-gradient(135deg, #ffffff, #f3f4f6);
        border: 1px solid rgba(148, 163, 184, 0.9);
        box-shadow:
            0 10px 28px rgba(148, 163, 184, 0.35),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
    }

    .spx-metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 6px;
    }

    .spx-metric-value {
        font-size: 1.5rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        color: #0f172a;
    }

    .muted {
        color: #4b5563;
        font-size: 0.95rem;
        line-height: 1.7;
        padding: 14px 16px;
        background:
            linear-gradient(135deg, rgba(229, 231, 235, 0.9), #ffffff);
        border-left: 3px solid #4f46e5;
        border-radius: 10px;
        margin: 10px 0;
        box-shadow: 0 10px 22px rgba(148, 163, 184, 0.25);
    }

    .risk-badge {
        display: inline-flex;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .risk-good {
        background: #ecfdf3;
        color: #15803d;
        border: 1px solid rgba(34, 197, 94, 0.6);
    }

    .risk-warning {
        background: #fffbeb;
        color: #92400e;
        border: 1px solid rgba(245, 158, 11, 0.8);
    }

    .risk-bad {
        background: #fef2f2;
        color: #b91c1c;
        border: 1px solid rgba(239, 68, 68, 0.85);
    }

    /* Inputs */
    .stNumberInput > div > div > input,
    .stTimeInput > div > div > input {
        background: #ffffff !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        border-radius: 12px !important;
        color: #0f172a !important;
        padding: 8px 10px !important;
        font-size: 0.95rem !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stSelectbox > div > div {
        background: #ffffff;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.9);
    }

    .stRadio > div {
        gap: 8px;
    }

    .stRadio > div > label {
        background: #ffffff;
        padding: 6px 12px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.9);
        font-size: 0.9rem;
        color: #4b5563;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: rgba(249, 250, 251, 0.92);
        padding: 6px;
        border-radius: 999px;
        border: 1px solid rgba(209, 213, 219, 0.9);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        padding: 6px 14px;
        font-size: 0.9rem;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #4f46e5, #22d3ee);
        color: #ffffff;
        font-weight: 700;
    }

    .stDataFrame {
        border-radius: 16px;
        overflow: hidden;
        box-shadow:
            0 12px 30px rgba(148, 163, 184, 0.35),
            0 6px 14px rgba(15, 23, 42, 0.12);
        border: 1px solid rgba(148, 163, 184, 0.9);
    }

    .app-footer {
        margin-top: 2.5rem;
        padding-top: 1.2rem;
        border-top: 1px solid rgba(209, 213, 219, 0.9);
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
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">{TAGLINE}</p>
            <div class="hero-status-row">
                <div class="status-pill">
                    <span class="status-dot"></span>
                    SYSTEM ACTIVE
                </div>
                <div class="status-pill-soft">
                    STRUCTURE FIRST · EMOTION LAST
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None, icon: str = ""):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    if icon:
        st.markdown(f"<div class='icon-large'>{icon}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str) -> str:
    return f"""
    <div class="spx-metric">
        <div class="spx-metric-label">{label}</div>
        <div class="spx-metric-value">{value}</div>
    </div>
    """


def section_header(text: str):
    st.markdown(f"<h3 class='section-header'>{text}</h3>", unsafe_allow_html=True)


# ===============================
# TIME / BLOCK HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map a clock time into the two-session structure around BASE_DATE:

    - Times from 08:30 to 23:59 are treated as belonging to the
      PREVIOUS SESSION DAY (previous RTH or late-day swings).
    - Times from 00:00 up to 08:00 are treated as the CURRENT DAY
      OVERNIGHT leading into the RTH open.

    BASE_DATE itself is 15:00 on the previous session day.
    """
    # Minutes since midnight
    minutes = t.hour * 60 + t.minute
    # 08:30 cutoff
    cutoff_830 = 8 * 60 + 30

    if minutes < cutoff_830:
        # Overnight of the "current" day
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)
    else:
        # Previous session day (RTH and late day)
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def align_30min(dt: datetime) -> datetime:
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """
    RTH grid for the main trading day: 08:30 to 14:30 CT on the day after BASE_DATE.
    """
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
    """
    Build a single channel (ascending or descending) projected across RTH slots.
    """
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
# TIMING CLASSIFIER
# ===============================

def classify_time_window(time_str: str) -> str:
    """
    Classify a 30 minute slot into timing windows:
    - Prime (Open Drive): 08:30 to <10:00
    - Prime (Mid Morning): 10:00 to <=11:30
    - Late: 12:00 to <=13:30
    - Dead zone: everything else in the RTH grid
    """
    try:
        h, m = time_str.split(":")
        h = int(h)
        m = int(m)
    except Exception:
        return "Unknown"

    minutes = h * 60 + m

    open_830 = 8 * 60 + 30
    ten = 10 * 60
    eleven30 = 11 * 60 + 30
    twelve = 12 * 60
    thirteen30 = 13 * 60 + 30

    if open_830 <= minutes < ten:
        return "Prime (Open Drive)"
    if ten <= minutes <= eleven30:
        return "Prime (Mid Morning)"
    if twelve <= minutes <= thirteen30:
        return "Late (Fade Only)"
    return "Dead Zone / Be Very Selective"


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
        st.markdown(f"### {APP_NAME}")
        st.markdown(
            f"<div class='sidebar-tagline'>{TAGLINE}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG} pts / 30m**")
        st.write(f"Contract factor: **{CONTRACT_FACTOR_DEFAULT:.2f} × SPX move**")
        st.caption(
            "Underlying: 16:00–17:00 CT maintenance\n\n"
            "Contracts: 16:00–19:00 CT maintenance\n\n"
            "RTH grid: 08:30–14:30 CT (30m blocks).\n\n"
            "You choose the previous-session pivots. The app carries the structure."
        )

    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "📐 Contract Setup",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # ===============================
    # TAB 1 - RAILS
    # ===============================
    with tabs[0]:
        card(
            "Rails + Stacks",
            "Define your underlying channel from your key previous-session pivots and project both ascending and "
            "descending rails into today's RTH. Stack them by one channel height to see common extension reversal zones.",
            badge="Structure Engine",
            icon="🧱",
        )

        section_header("Underlying Pivots (Previous Session Structure)")
        st.markdown(
            "<div class='spx-sub'>"
            "Pick the <strong>structural high and low pivots</strong> from the previous session on your line chart. "
            "These can come from the previous RTH (for example 09:30, 11:00, 14:30) "
            "or from the overnight action leading into today (for example 18:00, 23:00, 03:00, 07:30). "
            "<br><br>The app maps any time from <strong>08:30–23:59</strong> as part of the previous session day, and "
            "any time from <strong>00:00–08:00</strong> as overnight for the current day."
            "</div>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**High Pivot**")
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
            st.markdown("**Low Pivot**")
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

        st.markdown("")
        build_col = st.columns([1, 3])[0]
        with build_col:
            if st.button("Build Rails", use_container_width=True, key="build_rails_btn"):
                df_asc, h_asc = build_channel(
                    high_price=high_price,
                    high_time=high_time,
                    low_price=low_price,
                    low_time=low_time,
                    slope_sign=+1,
                )
                df_desc, h_desc = build_channel(
                    high_price=high_price,
                    high_time=high_time,
                    low_price=low_price,
                    low_time=low_time,
                    slope_sign=-1,
                )
                st.session_state["channel_asc_df"] = df_asc
                st.session_state["channel_asc_height"] = h_asc
                st.session_state["channel_desc_df"] = df_desc
                st.session_state["channel_desc_height"] = h_desc
                st.success("Rails generated for both ascending and descending scenarios.")

        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        section_header("Underlying Rails - Today’s RTH 08:30–14:30 CT")

        if df_asc is None or df_desc is None:
            st.info("Build the rails to see projections.")
        else:
            st.markdown("**Ascending Channel (Price respecting higher lows)**")
            c_top = st.columns([3, 1])
            with c_top[0]:
                st.dataframe(df_asc, use_container_width=True, hide_index=True, height=280)
            with c_top[1]:
                if h_asc is not None:
                    st.markdown(
                        metric_card("Channel Height", f"{h_asc:.2f} pts"),
                        unsafe_allow_html=True,
                    )

            st.markdown("**Descending Channel (Price respecting lower highs)**")
            c_bot = st.columns([3, 1])
            with c_bot[0]:
                st.dataframe(df_desc, use_container_width=True, hide_index=True, height=280)
            with c_bot[1]:
                if h_desc is not None:
                    st.markdown(
                        metric_card("Channel Height", f"{h_desc:.2f} pts"),
                        unsafe_allow_html=True,
                    )

        end_card()

    # ===============================
    # TAB 2 - CONTRACT
    # ===============================
    with tabs[1]:
        card(
            "Contract Setup",
            "Tell the app roughly how your chosen contract moves relative to SPX. "
            "This lets the Foresight card translate a rail to rail move into a realistic options target.",
            badge="Contract Engine",
            icon="📐",
        )

        section_header("Contract Behavior Approximation")

        contract_factor = st.number_input(
            "Contract factor (contract change per 1 point SPX move)",
            value=CONTRACT_FACTOR_DEFAULT,
            step=0.01,
            min_value=0.01,
            max_value=2.0,
            key="contract_factor",
        )

        direction = st.radio(
            "Planned directional bias for the main channel move",
            ["Long Call (Bottom to Top)", "Long Put (Top to Bottom)"],
            index=0,
            key="contract_direction",
            horizontal=True,
        )

        entry_contract_price = st.number_input(
            "Planned entry contract price at rail touch",
            value=10.0,
            step=0.1,
            min_value=0.0,
            key="contract_entry_price",
        )

        st.markdown(
            "<div class='muted'><strong>How to use this:</strong> "
            "Pick the contract you intend to trade, enter the approximate price you expect to pay when your rail is touched, "
            "and use a contract factor that reflects how that contract moves relative to SPX. "
            "Further out-of-the-money contracts usually have a higher factor; closer to the money a bit lower.</div>",
            unsafe_allow_html=True,
        )

        end_card()

    # ===============================
    # TAB 3 - DAILY FORESIGHT
    # ===============================
    with tabs[2]:
        card(
            "Daily Foresight",
            "Rails, stacked extensions, contract behavior, and timing windows combined into a simple playbook.",
            badge="Foresight Card",
            icon="🔮",
        )

        df_asc = st.session_state.get("channel_asc_df")
        h_asc = st.session_state.get("channel_asc_height")
        df_desc = st.session_state.get("channel_desc_df")
        h_desc = st.session_state.get("channel_desc_height")

        if df_asc is None or h_asc is None or df_desc is None or h_desc is None:
            st.warning("No rails available. Build the rails in the Rails Setup tab first.")
            end_card()
        else:
            section_header("Primary Scenario Selection")

            scenario_choice = st.radio(
                "Choose which structure you are treating as primary for today",
                [
                    "Ascending primary (Descending alternate)",
                    "Descending primary (Ascending alternate)",
                ],
                index=0,
                key="primary_scenario_choice",
            )

            if "Ascending primary" in scenario_choice:
                primary_name = "Ascending"
                primary_df = df_asc.copy()
                primary_h = h_asc
                alt_name = "Descending"
                alt_df = df_desc.copy()
                alt_h = h_desc
            else:
                primary_name = "Descending"
                primary_df = df_desc.copy()
                primary_h = h_desc
                alt_name = "Ascending"
                alt_df = df_asc.copy()
                alt_h = h_asc

            # Stacked channels for primary
            map_df = primary_df.copy()
            map_df["Top +1H"] = map_df["Top Rail"] + primary_h
            map_df["Bottom -1H"] = map_df["Bottom Rail"] - primary_h
            map_df["Timing Window"] = map_df["Time"].apply(classify_time_window)

            # Contract behavior for a full rail to rail move
            cf = st.session_state.get("contract_factor", CONTRACT_FACTOR_DEFAULT)
            approx_contract_move = cf * primary_h

            # Summary metrics
            section_header("Structure Summary")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    metric_card("Primary Scenario", primary_name),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card("Channel Height", f"{primary_h:.2f} pts"),
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    metric_card("Contract Move per Channel", f"{approx_contract_move:.2f} units"),
                    unsafe_allow_html=True,
                )

            # Stand aside logic based on contract juice
            if approx_contract_move < MIN_CONTRACT_MOVE:
                st.markdown(
                    "<div class='muted'>"
                    "<span class='risk-badge risk-bad'>Low Juice Day</span> "
                    "The structural channel is not offering much options movement today based on your contract factor. "
                    "This is a good candidate day to stand aside or trade very small."
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<div class='muted'>"
                    "<span class='risk-badge risk-good'>Tradable Channel</span> "
                    "The expected contract move from a full rail-to-rail swing is large enough to justify taking the setup, "
                    "if price and timing cooperate."
                    "</div>",
                    unsafe_allow_html=True,
                )

            # Contract trade estimator
            section_header("Contract Trade Estimator")

            times = map_df["Time"].tolist()
            if not times:
                st.info("No RTH slots found.")
            else:
                entry_time = st.selectbox(
                    "Planned entry time (when you expect the rail to be tagged)",
                    times,
                    index=0,
                    key="foresight_entry_time",
                )

                timing_label = classify_time_window(entry_time)

                planned_direction = st.session_state.get(
                    "contract_direction", "Long Call (Bottom to Top)"
                )
                entry_price = st.session_state.get("contract_entry_price", 0.0)

                # For a full rail-to-rail move, we use the absolute move.
                # Long Call: bottom to top, SPX up, contract up.
                # Long Put: top to bottom, SPX down, contract up in value.
                # Projected PnL is positive when price travels the full channel in the trade direction.
                projected_move = approx_contract_move
                target_price = entry_price + projected_move

                c1e, c2e, c3e = st.columns(3)
                with c1e:
                    st.markdown(
                        metric_card("Entry Contract", f"{entry_price:.2f}"),
                        unsafe_allow_html=True,
                    )
                with c2e:
                    st.markdown(
                        metric_card("Target Contract", f"{target_price:.2f}"),
                        unsafe_allow_html=True,
                    )
                with c3e:
                    st.markdown(
                        metric_card("Projected PnL", f"+{projected_move:.2f} units"),
                        unsafe_allow_html=True,
                    )

                # Timing guidance text
                if timing_label.startswith("Prime"):
                    timing_badge = "<span class='risk-badge risk-good'>Prime Window</span>"
                    comment = (
                        "You are planning to enter inside one of the prime windows "
                        "(08:30 to 11:30 CT). This is where the cleanest rail-to-rail "
                        "moves tend to complete."
                    )
                elif "Late" in timing_label:
                    timing_badge = "<span class='risk-badge risk-warning'>Late Session</span>"
                    comment = (
                        "You are planning to enter in the afternoon. Expect more chop and "
                        "shorter continuation. Tighten your stop and be faster to take profits."
                    )
                else:
                    timing_badge = "<span class='risk-badge risk-bad'>Dead Zone</span>"
                    comment = (
                        "You are planning to enter outside the ideal windows. "
                        "Historical behavior suggests more noise and failed follow-through in this zone."
                    )

                st.markdown(
                    f"<div class='muted'>{timing_badge} "
                    f"<br><strong>Timing classification for {entry_time} CT:</strong> {timing_label}. "
                    f"<br>{comment}</div>",
                    unsafe_allow_html=True,
                )

            # Time aligned map
            section_header("Time Aligned Map")

            st.caption(
                "Primary scenario rails with stacked extensions and timing windows. "
                "Use this as a panoramic map: where are the main rails, the extension rails, "
                "and which times of day align with the cleanest moves."
            )

            st.dataframe(map_df, use_container_width=True, hide_index=True, height=420)

            st.markdown(
                "<div class='muted'>"
                "<strong>Reading this grid:</strong> "
                "Top Rail and Bottom Rail form the main channel for your primary scenario. "
                "Top +1H and Bottom -1H are the stacked rails one channel height above and below. "
                "Timing Window shows how friendly that 30 minute slot tends to be for clean moves. "
                "You still wait for price action at the rail, but now you have structure, contracts, "
                "and time working together in a clear plan."
                "</div>",
                unsafe_allow_html=True,
            )

        end_card()

    # ===============================
    # TAB 4 - ABOUT
    # ===============================
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Overview", icon="ℹ️")
        st.markdown(
            """
            <div class='spx-sub'>
            <p><strong>Core idea:</strong> two previous-session pivots define your rails, the slope carries that structure into today's RTH, and your contract factor connects SPX movement to an options target.</p>

            <ul style="margin-left:20px;">
                <li>Rails use a fixed slope of <strong>±0.475 points per 30 minutes</strong> on a 30 minute grid.</li>
                <li>You define the high and low engulfing pivots from the <strong>previous session structure</strong> – either previous RTH or overnight up to 07:30 CT.</li>
                <li>The app builds <strong>both</strong> ascending and descending channels and lets you pick the primary scenario for the day.</li>
                <li>Stacked rails one channel height above and below highlight common extension reversal zones.</li>
                <li>A simple <strong>contract factor</strong> turns a rail-to-rail SPX move into an expected contract move.</li>
                <li>Timing windows label each 30 minute slot as prime, late, or dead zone to help you avoid forcing trades at the wrong time of day.</li>
            </ul>

            <p>This is not a full options model. It is a structural map designed to make your discretionary decisions clearer:
            where to focus, which way to lean, when the contract has enough juice, and when the clock is working for or against you.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()