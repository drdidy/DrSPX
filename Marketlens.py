# spx_prophet.py
# SPX Prophet – Structural Channels + Stacked Rails + Contract Planner + Daily Playbook
# Offline edition: prior RTH pivots only. No external APIs.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime

APP_NAME = "SPX Prophet"
TAGLINE = "Quantitative structure for intraday SPX planning."
SLOPE_MAG = 0.475          # pts per 30 min for underlying rails
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 anchor for synthetic 30m grid

# Risk / sizing parameters
CONTRACT_FACTOR_DEFAULT = 0.33       # contract move ≈ factor × SPX move
MIN_CHANNEL_HEIGHT = 60.0            # below this, structure is too tight
ASYM_RATIO_MAX = 1.30                # >30% asymmetry = structural imbalance
MIN_CONTRACT_MOVE = 9.9              # below this, contract move is not worth it


# ===============================
# UI / STYLING
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.06), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.06), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 40%, #eef2ff 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    .block-container {
        padding-top: 2.6rem;
        padding-bottom: 3.4rem;
        max-width: 1420px;
    }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(79, 70, 229, 0.12), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            6px 0 30px rgba(99, 102, 241, 0.16),
            3px 0 12px rgba(15, 23, 42, 0.15);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #4f46e5 0%, #2563eb 50%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.04em;
        margin-bottom: 0.2rem;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.0rem 0 0.8rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            rgba(148, 163, 184, 0.0),
            rgba(129, 140, 248, 0.7),
            rgba(148, 163, 184, 0.0));
    }

    /* HERO */
    .hero-wrapper {
        display: flex;
        justify-content: center;
        margin-bottom: 1.6rem;
    }

    .hero-header {
        max-width: 920px;
        text-align: center;
        position: relative;
        background:
            radial-gradient(circle at 12% 0%, rgba(79, 70, 229, 0.10), transparent 65%),
            radial-gradient(circle at 88% 100%, rgba(37, 99, 235, 0.12), transparent 65%),
            linear-gradient(135deg, #ffffff, #f8fafc);
        border-radius: 28px;
        padding: 26px 34px 24px 34px;
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow:
            0 20px 55px -18px rgba(37, 99, 235, 0.45),
            0 10px 30px -18px rgba(15, 23, 42, 0.35),
            inset 0 1px 0 rgba(255, 255, 255, 0.75);
        overflow: hidden;
    }

    .hero-header::before {
        content: '';
        position: absolute;
        inset: 0;
        background:
            linear-gradient(135deg, rgba(129, 140, 248, 0.4), transparent 60%);
        opacity: 0.12;
        pointer-events: none;
    }

    .hero-title {
        position: relative;
        font-size: 2.4rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        letter-spacing: -0.06em;
        margin: 0.1rem 0 0.25rem 0;
        background: linear-gradient(135deg, #020617 0%, #4f46e5 45%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-tagline {
        position: relative;
        font-size: 1.0rem;
        color: #475569;
        margin-bottom: 0.4rem;
        font-weight: 500;
    }

    .hero-subline {
        position: relative;
        font-size: 0.92rem;
        color: #64748b;
        line-height: 1.7;
    }

    .hero-pill {
        position: relative;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 999px;
        background:
            linear-gradient(135deg, rgba(22, 163, 74, 0.10), rgba(22, 163, 74, 0.04)),
            #ffffff;
        border: 1px solid rgba(22, 163, 74, 0.45);
        color: #166534;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }

    .hero-pill-dot {
        width: 7px;
        height: 7px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 0 5px rgba(22, 163, 74, 0.32);
    }

    /* CARDS */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 8% 0%, rgba(129, 140, 248, 0.10), transparent 55%),
            radial-gradient(circle at 92% 100%, rgba(56, 189, 248, 0.10), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 24px;
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow:
            0 18px 45px -16px rgba(148, 163, 184, 0.7),
            0 8px 20px -14px rgba(15, 23, 42, 0.55),
            inset 0 1px 0 rgba(255, 255, 255, 0.85);
        padding: 22px 24px 22px 24px;
        margin-bottom: 26px;
    }

    .spx-card h4 {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        margin: 0 0 6px 0;
        letter-spacing: -0.04em;
        background: linear-gradient(135deg, #020617 0%, #4f46e5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        border: 1px solid rgba(129, 140, 248, 0.7);
        background:
            linear-gradient(135deg, rgba(129, 140, 248, 0.12), rgba(59, 130, 246, 0.06)),
            #ffffff;
        font-size: 0.74rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #4338ca;
        margin-bottom: 8px;
    }

    .spx-sub {
        color: #475569;
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* SECTION HEADER */
    .section-header {
        font-size: 1.35rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #4f46e5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 1.6rem 0 0.6rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.7);
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .section-header::before {
        content: '';
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        box-shadow: 0 0 0 4px rgba(129, 140, 248, 0.35);
    }

    /* METRICS */
    .spx-metric {
        position: relative;
        padding: 14px 16px;
        border-radius: 18px;
        background:
            radial-gradient(circle at top left, rgba(129, 140, 248, 0.09), transparent 60%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border: 1px solid rgba(148, 163, 184, 0.8);
        box-shadow:
            0 14px 36px -16px rgba(148, 163, 184, 0.9),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
    }

    .spx-metric-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .spx-metric-value {
        font-size: 1.25rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #020617 0%, #4f46e5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .spx-metric-note {
        font-size: 0.76rem;
        color: #6b7280;
        margin-top: 3px;
    }

    /* ALERT BANNERS */
    .spx-banner-ok,
    .spx-banner-caution,
    .spx-banner-stop {
        border-radius: 16px;
        padding: 12px 14px;
        font-size: 0.94rem;
    }

    .spx-banner-ok {
        background:
            linear-gradient(135deg, rgba(22, 163, 74, 0.09), rgba(22, 163, 74, 0.03)),
            #ffffff;
        border: 1px solid rgba(22, 163, 74, 0.4);
        color: #166534;
        box-shadow: 0 10px 26px -16px rgba(22, 163, 74, 0.7);
    }

    .spx-banner-caution {
        background:
            linear-gradient(135deg, rgba(245, 158, 11, 0.11), rgba(245, 158, 11, 0.03)),
            #ffffff;
        border: 1px solid rgba(245, 158, 11, 0.6);
        color: #92400e;
        box-shadow: 0 10px 26px -16px rgba(245, 158, 11, 0.8);
    }

    .spx-banner-stop {
        background:
            linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(239, 68, 68, 0.03)),
            #ffffff;
        border: 1px solid rgba(239, 68, 68, 0.65);
        color: #991b1b;
        box-shadow: 0 10px 26px -16px rgba(239, 68, 68, 0.8);
    }

    /* INPUTS */
    .stNumberInput > div > div > input,
    .stTimeInput > div > div > input {
        background: #ffffff !important;
        border-radius: 12px !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        padding: 8px 10px !important;
        color: #0f172a !important;
    }

    .stNumberInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus {
        border-color: #4f46e5 !important;
        box-shadow:
            0 0 0 2px rgba(79, 70, 229, 0.25),
            0 0 0 1px rgba(79, 70, 229, 0.4) !important;
    }

    /* RADIO / SLIDER / TABS */
    .stRadio > div {
        gap: 6px;
    }

    .stRadio > div > label {
        background: #ffffff;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.9);
        padding: 6px 10px;
        font-size: 0.83rem;
        font-weight: 600;
        color: #4b5563;
        box-shadow: 0 4px 10px -6px rgba(148, 163, 184, 0.9);
    }

    .stRadio > div > label:hover {
        border-color: rgba(79, 70, 229, 0.9);
        color: #4f46e5;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background:
            linear-gradient(135deg, rgba(248, 250, 252, 0.95), rgba(239, 246, 255, 0.98));
        padding: 4px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.9);
        box-shadow: 0 14px 30px -18px rgba(148, 163, 184, 0.9);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        font-size: 0.88rem;
        font-weight: 600;
        padding: 4px 14px;
        color: #6b7280;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #4f46e5, #2563eb);
        color: #ffffff;
        box-shadow:
            0 8px 18px -10px rgba(79, 70, 229, 0.9),
            inset 0 1px 0 rgba(255, 255, 255, 0.4);
    }

    /* DATAFRAME */
    .stDataFrame {
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.95);
        box-shadow:
            0 14px 40px -18px rgba(148, 163, 184, 0.95),
            0 8px 20px -16px rgba(15, 23, 42, 0.8);
        overflow: hidden;
    }

    .stDataFrame div[data-testid="StyledTable"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
    }

    /* FOOTER */
    .app-footer {
        margin-top: 2.4rem;
        padding-top: 1.2rem;
        border-top: 1px solid rgba(148, 163, 184, 0.7);
        text-align: center;
        color: #6b7280;
        font-size: 0.85rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown(
        f"""
        <div class="hero-wrapper">
          <div class="hero-header">
            <div class="hero-pill">
              <div class="hero-pill-dot"></div>
              SYSTEM ACTIVE
            </div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <div class="hero-tagline">{TAGLINE}</div>
            <div class="hero-subline">
              Prior-session structure defines the rails. A fixed slope carries the channel into today.
              Filters and timing rules turn that map into an intraday plan.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, sub: str = "", badge: str = ""):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def section_header(text: str):
    st.markdown(f"<h3 class='section-header'>{text}</h3>", unsafe_allow_html=True)


def metric_card(label: str, value: str, note: str = "") -> str:
    note_html = f"<div class='spx-metric-note'>{note}</div>" if note else ""
    return f"""
    <div class="spx-metric">
      <div class="spx-metric-label">{label}</div>
      <div class="spx-metric-value">{value}</div>
      {note_html}
    </div>
    """


# ===============================
# TIME / GRID HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map a CT clock time into synthetic grid:
    - times >= 15:00 belong to BASE_DATE
    - times < 15:00 belong to BASE_DATE + 1 day
    """
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    next_day = BASE_DATE.date() + timedelta(days=1)
    return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    """Align any datetime to the nearest 30-minute block."""
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """RTH grid: 08:30–14:30 CT at 30-minute steps (synthetic next-day mapping)."""
    day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(day.year, day.month, day.day, 8, 30)
    end = datetime(day.year, day.month, day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


# ===============================
# CHANNEL BUILDER + STACKED RAILS
# ===============================

def build_structural_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
) -> tuple[pd.DataFrame, float]:
    """
    Build either an ascending or descending structural channel from prior RTH pivots.
    Uses fixed slope magnitude SLOPE_MAG.

    Returns:
      - DataFrame with Time, Main rails, and stacked rails
      - Channel height (top - bottom intercepts)
    """
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))

    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

    # Intercepts
    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo

    channel_height = b_top - b_bottom

    rows = []
    for dt in rth_slots():
        k = blocks_from_base(dt)
        main_top = s * k + b_top
        main_bottom = s * k + b_bottom
        stack_plus_top = main_top + channel_height
        stack_plus_bottom = main_bottom + channel_height
        stack_minus_top = main_top - channel_height
        stack_minus_bottom = main_bottom - channel_height

        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Main Top": round(main_top, 2),
                "Main Bottom": round(main_bottom, 2),
                "Stack+1 Top": round(stack_plus_top, 2),
                "Stack+1 Bottom": round(stack_plus_bottom, 2),
                "Stack-1 Top": round(stack_minus_top, 2),
                "Stack-1 Bottom": round(stack_minus_bottom, 2),
            }
        )

    df = pd.DataFrame(rows)
    return df, round(channel_height, 2)


# ===============================
# DAY TYPE / FILTERS
# ===============================

def classify_day(
    primary_height: float,
    alt_height: float,
    contract_factor: float,
) -> tuple[str, str, dict]:
    """
    Combine simple structural rules into:
      - NORMAL STRUCTURAL DAY
      - LIGHT SIZE / SCALP ONLY
      - STAND ASIDE
    """
    flags = {"narrow": False, "low_contract": False, "asym": False}

    if primary_height <= 0:
        return "NO STRUCTURE", "Pivots are not configured yet.", flags

    if primary_height < MIN_CHANNEL_HEIGHT:
        flags["narrow"] = True

    contract_move = primary_height * contract_factor
    if contract_move < MIN_CONTRACT_MOVE:
        flags["low_contract"] = True

    ratio = None
    if alt_height and alt_height > 0:
        big = max(primary_height, alt_height)
        small = min(primary_height, alt_height)
        if small > 0:
            ratio = big / small
            if ratio > ASYM_RATIO_MAX:
                flags["asym"] = True

    score = sum(flags.values())

    if score >= 2:
        headline = "STAND ASIDE"
        reasons = []
        if flags["narrow"]:
            reasons.append("channel height is small")
        if flags["low_contract"]:
            reasons.append("projected contract move is small")
        if flags["asym"]:
            reasons.append("up vs down structure is unbalanced")
        explanation = (
            " and ".join(reasons).capitalize()
            + ". Combined with timing, this is a good day to preserve capital."
        )
    elif score == 1:
        headline = "LIGHT SIZE / SCALP ONLY"
        reasons = []
        if flags["narrow"]:
            reasons.append("channel is relatively tight")
        if flags["low_contract"]:
            reasons.append("contract move is modest")
        if flags["asym"]:
            reasons.append("structure is skewed")
        explanation = (
            ", ".join(reasons).capitalize()
            + ". You can trade, but keep size small and treat moves as scalps."
        )
    else:
        headline = "NORMAL STRUCTURAL DAY"
        explanation = (
            "Channel height and projected contract move are healthy, and the two scenarios are "
            "not excessively asymmetric. Your job is to wait for clean touches in the right windows."
        )

    return headline, explanation, flags


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
        st.caption(TAGLINE)
        st.markdown("---")

        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG:.3f} pts / 30m**")

        contract_factor = st.number_input(
            "Contract factor (≈ contract move / SPX move)",
            min_value=0.10,
            max_value=1.00,
            value=CONTRACT_FACTOR_DEFAULT,
            step=0.01,
            help="Approximate option move for each 1-point SPX move. 0.33 is a good starting point for many 0DTE near-the-money contracts.",
            key="contract_factor",
        )

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Underlying rails use a synthetic 30-minute grid.\n"
            "• Prior RTH structural pivots define today's channel.\n"
            "• RTH grid: 08:30–14:30 CT.\n"
            "• This app does not use live data or volatility feeds."
        )

    # Session structure containers (initialized before widgets)
    if "asc_channel_df" not in st.session_state:
        st.session_state["asc_channel_df"] = None
    if "desc_channel_df" not in st.session_state:
        st.session_state["desc_channel_df"] = None
    if "asc_height" not in st.session_state:
        st.session_state["asc_height"] = None
    if "desc_height" not in st.session_state:
        st.session_state["desc_height"] = None

    hero()

    tabs = st.tabs(
        [
            "🧱 Market Structure",
            "📐 Contract Planner",
            "📊 Daily Playbook",
            "ℹ️ About",
        ]
    )

    # ============= TAB 1 – STRUCTURE =============
    with tabs[0]:
        card(
            "Market Structure",
            "Define structural rails for the new session using the prior RTH high and low pivots. "
            "The same pivots generate both ascending and descending channels, plus stacked bands.",
            badge="Rails + Stacked Channels",
        )

        section_header("Prior RTH Pivots (Line Chart)")

        st.markdown(
            """
            <div class="spx-sub">
              Select the structural <strong>high</strong> and <strong>low</strong> pivots from the previous
              regular-hours session on a line chart. These are the main intraday turning points, not necessarily
              the absolute wicks. Times should be valid CT times from that session
              (for example 09:30, 11:00, 14:30).
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**High Pivot**")
            high_price = st.number_input(
                "High pivot price (prior RTH)",
                value=5200.0,
                step=0.25,
                key="high_pivot",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(11, 0),
                step=1800,
                key="high_time",
            )
        with c2:
            st.markdown("**Low Pivot**")
            low_price = st.number_input(
                "Low pivot price (prior RTH)",
                value=5100.0,
                step=0.25,
                key="low_pivot",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(13, 0),
                step=1800,
                key="low_time",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        build_col = st.columns([1, 3])[0]
        with build_col:
            if st.button("Build structural channels", use_container_width=True, key="build_channels_btn"):
                df_asc, h_asc = build_structural_channel(
                    high_price=high_price,
                    high_time=high_time,
                    low_price=low_price,
                    low_time=low_time,
                    slope_sign=+1,
                )
                df_desc, h_desc = build_structural_channel(
                    high_price=high_price,
                    high_time=high_time,
                    low_price=low_price,
                    low_time=low_time,
                    slope_sign=-1,
                )
                st.session_state["asc_channel_df"] = df_asc
                st.session_state["desc_channel_df"] = df_desc
                st.session_state["asc_height"] = h_asc
                st.session_state["desc_height"] = h_desc
                st.success("Ascending and descending structural channels built successfully.")

        df_asc = st.session_state["asc_channel_df"]
        df_desc = st.session_state["desc_channel_df"]
        h_asc = st.session_state["asc_height"]
        h_desc = st.session_state["desc_height"]

        if df_asc is None or df_desc is None:
            section_header("RTH Structural Grid")
            st.info("Build channels to see the full RTH rail map with stacked bands.")
        else:
            section_header("Ascending Scenario (Structure)")
            a1, a2 = st.columns([3, 1])
            with a1:
                st.dataframe(df_asc, use_container_width=True, hide_index=True, height=340)
            with a2:
                st.markdown(
                    metric_card(
                        "Ascending channel height",
                        f"{h_asc:.2f} pts",
                        "Main bottom to main top.",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Descending Scenario (Structure)")
            d1, d2 = st.columns([3, 1])
            with d1:
                st.dataframe(df_desc, use_container_width=True, hide_index=True, height=340)
            with d2:
                st.markdown(
                    metric_card(
                        "Descending channel height",
                        f"{h_desc:.2f} pts",
                        "Main top to main bottom.",
                    ),
                    unsafe_allow_html=True,
                )

        end_card()

    # ============= TAB 2 – CONTRACT PLANNER =============
    with tabs[1]:
        card(
            "Contract Planner",
            "Translate the structural channel into an options move: channel height, contract factor, "
            "and a simple rail-to-rail template for calls and puts.",
            badge="Options Layer",
        )

        df_asc = st.session_state["asc_channel_df"]
        df_desc = st.session_state["desc_channel_df"]
        h_asc = st.session_state["asc_height"]
        h_desc = st.session_state["desc_height"]

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("No structural channels available. Configure pivots and build channels in the Market Structure tab first.")
            end_card()
        else:
            section_header("Scenario Selection")

            default_primary_index = 0 if h_asc >= h_desc else 1
            primary_choice = st.radio(
                "Primary structural scenario for today",
                ["Ascending", "Descending"],
                index=default_primary_index,
                horizontal=True,
                key="primary_scenario_contract_tab",
            )

            if primary_choice == "Ascending":
                primary_df = df_asc
                primary_height = h_asc
                alt_height = h_desc
            else:
                primary_df = df_desc
                primary_height = h_desc
                alt_height = h_asc

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    metric_card(
                        "Primary scenario",
                        primary_choice,
                        "The main structural view you intend to trade around.",
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card(
                        "Primary channel height",
                        f"{primary_height:.2f} pts",
                        "Full distance between main rails.",
                    ),
                    unsafe_allow_html=True,
                )
            with c3:
                asym_text = "—"
                note = "Requires both channels to have valid heights."
                if primary_height and alt_height and alt_height > 0 and primary_height > 0:
                    big = max(primary_height, alt_height)
                    small = min(primary_height, alt_height)
                    ratio = big / small
                    asym_text = f"{ratio:.2f}×"
                    note = "Above 1.30× indicates structural imbalance."
                st.markdown(
                    metric_card(
                        "Height asymmetry (max/min)",
                        asym_text,
                        note,
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Contract Move Template")

            underlying_full_span = primary_height
            contract_full_span = underlying_full_span * contract_factor
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(
                    metric_card(
                        "Underlying span (full rail-to-rail)",
                        f"{underlying_full_span:.2f} pts",
                        "From one main rail to the opposite rail.",
                    ),
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    metric_card(
                        "Contract move (full span)",
                        f"{contract_full_span:.2f} units",
                        f"Using factor {contract_factor:.2f}.",
                    ),
                    unsafe_allow_html=True,
                )
            with m3:
                ratio_vs_min = contract_full_span / MIN_CONTRACT_MOVE if MIN_CONTRACT_MOVE > 0 else 0.0
                st.markdown(
                    metric_card(
                        "Move vs minimum threshold",
                        f"{ratio_vs_min:.2f}×",
                        f"Threshold: {MIN_CONTRACT_MOVE:.1f}. Below 1.0× is weak.",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Trade Template")

            t1, t2, t3 = st.columns(3)
            with t1:
                trade_side = st.radio(
                    "Planned structural play",
                    ["Long Call (bottom → top)", "Long Put (top → bottom)"],
                    index=0,
                    key="trade_side",
                )
            with t2:
                rail_fraction = st.slider(
                    "Fraction of channel you intend to capture",
                    min_value=0.50,
                    max_value=1.00,
                    value=1.00,
                    step=0.05,
                    key="rail_fraction",
                    help="1.00 = full rail-to-rail. 0.70 = partial move for faster exits.",
                )
            with t3:
                entry_contract_price = st.number_input(
                    "Planned contract entry price",
                    min_value=0.01,
                    value=5.00,
                    step=0.05,
                    key="entry_contract_price",
                    help="Approximate option price when the rail touch occurs.",
                )

            underlying_plan = primary_height * rail_fraction
            contract_plan_move = underlying_plan * contract_factor
            exit_price = entry_contract_price + contract_plan_move if entry_contract_price > 0 else 0.0
            roi_pct = (contract_plan_move / entry_contract_price * 100.0) if entry_contract_price > 0 else 0.0

            c4, c5, c6 = st.columns(3)
            with c4:
                st.markdown(
                    metric_card(
                        "Underlying move (planned)",
                        f"{underlying_plan:.2f} pts",
                        f"{rail_fraction:.0%} of primary channel height.",
                    ),
                    unsafe_allow_html=True,
                )
            with c5:
                st.markdown(
                    metric_card(
                        "Projected contract move",
                        f"+{contract_plan_move:.2f}",
                        f"Requires ≥ {MIN_CONTRACT_MOVE:.1f} for a strong day.",
                    ),
                    unsafe_allow_html=True,
                )
            with c6:
                st.markdown(
                    metric_card(
                        "Projected exit price",
                        f"{exit_price:.2f}",
                        f"Approximate ROI: {roi_pct:.1f} percent.",
                    ),
                    unsafe_allow_html=True,
                )

            # Time-aligned map with contract columns
            section_header("Time-Aligned Map (Primary Scenario)")

            st.caption(
                "Each row is a 30-minute RTH slot in the primary scenario. Structural rails and stacked bands "
                "give you location. Contract columns show what a full structural move would mean for your option."
            )

            map_df = primary_df.copy()
            map_df["Struct Span"] = round(primary_height, 2)
            map_df["Contract Δ (full span)"] = round(primary_height * contract_factor, 2)
            if entry_contract_price > 0:
                map_df["Proj Exit @ full span"] = round(entry_contract_price + primary_height * contract_factor, 2)
            else:
                map_df["Proj Exit @ full span"] = None

            st.dataframe(map_df, use_container_width=True, hide_index=True, height=420)

            st.markdown(
                """
                <div class="spx-sub" style="margin-top:8px;">
                  The table does not tell you which specific time will be the touch. It gives you a consistent
                  price grid so you can match your own timing rules, see where price is in the channel, and know
                  what a structural move would pay on your contract.
                </div>
                """,
                unsafe_allow_html=True,
            )

        end_card()

    # ============= TAB 3 – DAILY PLAYBOOK =============
    with tabs[2]:
        card(
            "Daily Playbook",
            "Combine structure, contract size, and timing into a simple label: trade, scalp, or stand aside. "
            "Then refine that with open location and direction bias.",
            badge="Execution Layer",
        )

        df_asc = st.session_state["asc_channel_df"]
        df_desc = st.session_state["desc_channel_df"]
        h_asc = st.session_state["asc_height"]
        h_desc = st.session_state["desc_height"]

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("No structural channels available. Configure pivots and build channels in the Market Structure tab first.")
            end_card()
        else:
            section_header("Scenario and Filters")

            default_primary_index = 0 if h_asc >= h_desc else 1
            primary_choice = st.radio(
                "Primary structural scenario for today",
                ["Ascending", "Descending"],
                index=default_primary_index,
                horizontal=True,
                key="primary_scenario_playbook",
            )

            if primary_choice == "Ascending":
                primary_df = df_asc
                primary_height = h_asc
                alt_height = h_desc
            else:
                primary_df = df_desc
                primary_height = h_desc
                alt_height = h_asc

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    metric_card(
                        "Primary scenario",
                        primary_choice,
                        "Based on prior RTH structure.",
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card(
                        "Primary channel height",
                        f"{primary_height:.2f} pts",
                        "Main rail to opposite rail.",
                    ),
                    unsafe_allow_html=True,
                )
            with c3:
                asym_text = "—"
                note = "Requires both heights."
                if primary_height and alt_height and alt_height > 0 and primary_height > 0:
                    big = max(primary_height, alt_height)
                    small = min(primary_height, alt_height)
                    ratio = big / small
                    asym_text = f"{ratio:.2f}×"
                    note = "Above 1.30× is structurally unbalanced."
                st.markdown(
                    metric_card(
                        "Height asymmetry (max/min)",
                        asym_text,
                        note,
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Day Classification")

            headline, explanation, _flags = classify_day(
                primary_height=primary_height,
                alt_height=alt_height,
                contract_factor=contract_factor,
            )

            if headline == "STAND ASIDE":
                banner_class = "spx-banner-stop"
                icon = "🛑"
            elif headline == "LIGHT SIZE / SCALP ONLY":
                banner_class = "spx-banner-caution"
                icon = "⚠️"
            elif headline == "NORMAL STRUCTURAL DAY":
                banner_class = "spx-banner-ok"
                icon = "✅"
            else:
                banner_class = "spx-banner-caution"
                icon = "ℹ️"

            st.markdown(
                f"""
                <div class="{banner_class}">
                  <strong>{icon} {headline}</strong><br>
                  {explanation}
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Timing Framework")

            st.markdown(
                """
                <div class="spx-sub">
                  <ul style="margin-left:18px;">
                    <li><strong>08:30–09:00 CT:</strong> opening noise. No new entries here.</li>
                    <li><strong>09:00–09:30 CT:</strong> only if the touch is clean and structure is clear.</li>
                    <li><strong>10:00–12:00 CT:</strong> preferred window for the first structural touch and rejection.</li>
                    <li><strong>After 13:00 CT:</strong> suitable for secondary tests, but exits should be faster.</li>
                  </ul>
                  If the <strong>first clean structural touch</strong> occurs before 09:00 CT,
                  treat the session with extra caution and keep size minimal or stand aside.
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Open Location and Direction Bias")

            b1, b2 = st.columns(2)
            with b1:
                open_price = st.number_input(
                    "SPX opening or early reference price",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    help="For example: the open, or the price at 09:00 CT.",
                    key="open_price_playbook",
                )
            with b2:
                slot_options = list(primary_df["Time"])
                default_idx = 0
                if "09:30" in slot_options:
                    default_idx = slot_options.index("09:30")
                open_slot = st.selectbox(
                    "Time slot for that price",
                    options=slot_options,
                    index=default_idx,
                    key="open_slot_playbook",
                )

            if open_price > 0.0:
                row = primary_df[primary_df["Time"] == open_slot].iloc[0]
                main_top = row["Main Top"]
                main_bottom = row["Main Bottom"]
                stack_up_top = row["Stack+1 Top"]
                stack_down_bottom = row["Stack-1 Bottom"]

                banner_class_bias = "spx-banner-ok"
                icon_bias = "✅"
                pos_text = ""
                suggestion = ""

                if main_bottom < main_top:
                    if main_bottom <= open_price <= main_top:
                        # inside main channel
                        pos = (open_price - main_bottom) / (main_top - main_bottom)
                        if primary_choice == "Ascending":
                            if pos <= 0.3:
                                pos_text = "near the lower rail inside the main channel."
                                suggestion = (
                                    "Bias: prefer long calls from clean bounces at the lower rail, "
                                    "especially in the 10:00–12:00 CT window."
                                )
                            elif pos >= 0.7:
                                pos_text = "near the upper rail inside the main channel."
                                suggestion = (
                                    "Bias: upside is already stretched. Treat short-duration long puts "
                                    "from upper rail rejections as your main idea."
                                )
                            else:
                                pos_text = "near the middle of the channel."
                                suggestion = (
                                    "Bias: neutral. Wait for a clear touch at a rail instead of forcing a trade in the middle."
                                )
                        else:  # Descending day
                            if pos <= 0.3:
                                pos_text = "near the lower rail inside the main channel."
                                suggestion = (
                                    "Bias: descending sessions often bounce up before resuming lower. "
                                    "Look to fade that bounce with long puts near the upper rail."
                                )
                            elif pos >= 0.7:
                                pos_text = "near the upper rail inside the main channel."
                                suggestion = (
                                    "Bias: prefer long puts from upper rail rejections; the structure supports top-to-bottom moves."
                                )
                            else:
                                pos_text = "near the middle of the channel."
                                suggestion = (
                                    "Bias: neutral. Let price choose a rail before you commit."
                                )
                    else:
                        # outside the main channel
                        if open_price > main_top:
                            if open_price <= stack_up_top:
                                pos_text = "above the main channel but inside the first upper stack."
                                suggestion = (
                                    "Bias: treat this as an extension zone. Watch for reversal behaviour near the stacked top, "
                                    "then favour trades back toward the main channel."
                                )
                                banner_class_bias = "spx-banner-caution"
                                icon_bias = "⚠️"
                            else:
                                pos_text = "well above both the main and first stacked channel."
                                suggestion = (
                                    "Bias: risk/reward is poor for chasing higher here. If risk cannot be defined cleanly, stand aside."
                                )
                                banner_class_bias = "spx-banner-stop"
                                icon_bias = "🛑"
                        elif open_price < main_bottom:
                            if open_price >= stack_down_bottom:
                                pos_text = "below the main channel but inside the first lower stack."
                                suggestion = (
                                    "Bias: extension to the downside. Watch for exhaustion and reversals near the stacked bottom, "
                                    "then favour trades back toward the main band."
                                )
                                banner_class_bias = "spx-banner-caution"
                                icon_bias = "⚠️"
                            else:
                                pos_text = "well below both the main and first stacked channel."
                                suggestion = (
                                    "Bias: washed-out levels. Chasing further in the same direction carries poor reward relative to risk."
                                )
                                banner_class_bias = "spx-banner-stop"
                                icon_bias = "🛑"
                else:
                    pos_text = "not well-defined because the rails are flat."
                    suggestion = "Check pivot selection; top and bottom rails should not be identical."

                st.markdown(
                    f"""
                    <div class="{banner_class_bias}" style="margin-top:8px;">
                      <strong>{icon_bias} Position inside structure</strong><br>
                      At {open_slot} CT, a price of <strong>{open_price:.2f}</strong> sits {pos_text}<br>
                      {suggestion}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            section_header("Execution Checklist")

            st.markdown(
                """
                <div class="spx-sub">
                  <ul style="margin-left:18px;">
                    <li>Day type: <em>Normal</em>, <em>Scalp only</em>, or <em>Stand aside</em>.</li>
                    <li>First clean structural touch happens at or after 09:00 CT, ideally 10:00–12:00 CT.</li>
                    <li>Trade is aligned with the primary scenario, or treated strictly as a scalp if counter-trend.</li>
                    <li>Projected contract move is large enough to justify the risk.</li>
                    <li>Risk per trade and daily loss limit are defined before the session starts.</li>
                  </ul>
                  The tool gives you a consistent structural framework. The discipline around entries, exits,
                  and risk size is what turns that framework into a track record.
                </div>
                """,
                unsafe_allow_html=True,
            )

        end_card()

    # ============= TAB 4 – ABOUT =============
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Design Notes")

        st.markdown(
            """
            <div class="spx-sub" style="font-size:0.95rem; line-height:1.7;">
              <p><strong>What this app does:</strong></p>
              <ul style="margin-left:18px;">
                <li>Uses two prior RTH pivots (high and low) to define a structural channel for the new day.</li>
                <li>Applies a fixed slope of 0.475 points per 30 minutes to carry that channel forward.</li>
                <li>Builds both ascending and descending versions from the same pivots.</li>
                <li>Adds one stacked channel above and below to frame extensions and reversals.</li>
                <li>Translates channel height into an options move using a simple contract factor.</li>
                <li>Combines channel width, asymmetry, and contract size into a simple day label.</li>
                <li>Uses timing guidance and open location to refine direction bias and trade stance.</li>
              </ul>

              <p><strong>What this app does not attempt to do:</strong></p>
              <ul style="margin-left:18px;">
                <li>Predict intraday news, volatility spikes, or order-flow shifts.</li>
                <li>Replace your own execution rules, risk limits, or review process.</li>
                <li>Guarantee profitability or remove the need for discretion.</li>
              </ul>

              <p>The goal is a clear, repeatable structural framework you can use
              with your own reading of price, order flow, and volatility. The logic is offline and transparent
              so it can be inspected, modified, or extended without dependency on external APIs.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet · Structural map, contract layer, and intraday playbook.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()