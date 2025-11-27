# spx_prophet.py
# SPX Prophet – Lanes, options, game plan, and signal scanner.
# Offline edition: prior RTH pivots plus overnight up to 03:00. No external APIs.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime

APP_NAME = "SPX Prophet"
TAGLINE = "Quantitative structure for intraday SPX planning."
SLOPE_MAG = 0.475          # points per 30 min for underlying lanes

# Synthetic calendar anchor
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 anchor for 30 minute grid

# Risk / sizing parameters
CONTRACT_FACTOR_DEFAULT = 0.33       # option move ≈ factor × SPX move
MIN_CHANNEL_HEIGHT = 60.0            # below this is structural compression
ASYM_RATIO_MAX = 1.30                # ratio for structural imbalance
MIN_CONTRACT_MOVE = 9.9              # below this, option move may not be worth it
MAX_STACK_DEPTH = 3                  # up to 3 extra outer lanes


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
              Yesterday's key swings draw today's lanes. A steady slope carries the map forward.
              You decide when to lean on the lane and when to ride the breakout.
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

def pivot_dt_from_time(t: dtime, is_night: bool = False) -> datetime:
    """
    Map a pivot time onto either:
      BASE_DATE for prior RTH
      BASE_DATE plus one day for moves between midnight and 03:00.
    """
    base_day = BASE_DATE.date()

    if is_night and t.hour < 3:
        pivot_date = base_day + timedelta(days=1)
    else:
        pivot_date = base_day

    return datetime(
        pivot_date.year,
        pivot_date.month,
        pivot_date.day,
        t.hour,
        t.minute,
        0,
        0,
    )


def align_30min_dt(dt: datetime) -> datetime:
    """Align any datetime to the nearest 30 minute block."""
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """
    RTH grid for the new session:
    Day 1 is BASE_DATE date plus one day
    08:30 to 14:30 CT at 30 minute steps.
    """
    day1 = BASE_DATE.date() + timedelta(days=1)
    start = datetime(day1.year, day1.month, day1.day, 8, 30)
    end = datetime(day1.year, day1.month, day1.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


# ===============================
# CHANNEL BUILDER AND STACKED LANES
# ===============================

def build_structural_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
    high_is_night: bool = False,
    low_is_night: bool = False,
) -> tuple[pd.DataFrame, float]:
    """
    Build either an up view or down view structural channel from chosen pivots.
    Pivots can be from prior RTH or from overnight up to 03:00.
    """
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min_dt(pivot_dt_from_time(high_time, is_night=high_is_night))
    dt_lo = align_30min_dt(pivot_dt_from_time(low_time, is_night=low_is_night))

    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

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


def extend_stacks(df: pd.DataFrame, channel_height: float, max_depth: int = MAX_STACK_DEPTH) -> pd.DataFrame:
    """
    Add Stack+2, Stack+3, Stack-2, Stack-3 lanes based on main channel height.
    Stack+1 and Stack-1 are left as they are.
    """
    if channel_height <= 0:
        return df

    for level in range(2, max_depth + 1):
        plus_top_col = f"Stack+{level} Top"
        plus_bottom_col = f"Stack+{level} Bottom"
        minus_top_col = f"Stack-{level} Top"
        minus_bottom_col = f"Stack-{level} Bottom"

        if plus_top_col not in df.columns:
            df[plus_top_col] = df["Main Top"] + channel_height * level
        if plus_bottom_col not in df.columns:
            df[plus_bottom_col] = df["Main Bottom"] + channel_height * level
        if minus_top_col not in df.columns:
            df[minus_top_col] = df["Main Top"] - channel_height * level
        if minus_bottom_col not in df.columns:
            df[minus_bottom_col] = df["Main Bottom"] - channel_height * level

        df[plus_top_col] = df[plus_top_col].round(2)
        df[plus_bottom_col] = df[plus_bottom_col].round(2)
        df[minus_top_col] = df[minus_top_col].round(2)
        df[minus_bottom_col] = df[minus_bottom_col].round(2)

    return df


# ===============================
# DAY TYPE, CONFIDENCE SCORE, FLAGS
# ===============================

def classify_day(
    primary_height: float,
    alt_height: float,
    contract_factor: float,
) -> tuple[str, str, dict]:
    """
    Use simple structural rules to describe the day:
      NORMAL STRUCTURAL DAY
      LIGHT SIZE / SCALP ONLY
      COMPRESSION / BREAKOUT WATCH
      STAND ASIDE
    """
    flags = {"compression": False, "low_contract": False, "asym": False}

    if primary_height <= 0:
        return "NO STRUCTURE", "Pivots are not configured yet.", flags

    if primary_height < MIN_CHANNEL_HEIGHT:
        flags["compression"] = True

    contract_move = primary_height * contract_factor
    if contract_move < MIN_CONTRACT_MOVE:
        flags["low_contract"] = True

    if alt_height and alt_height > 0:
        big = max(primary_height, alt_height)
        small = min(primary_height, alt_height)
        if small > 0:
            ratio = big / small
            if ratio > ASYM_RATIO_MAX:
                flags["asym"] = True

    # Now convert flags into a headline
    if flags["low_contract"] and flags["asym"]:
        headline = "STAND ASIDE"
        explanation = (
            "Projected option move is small and the two views are far apart. Preserve capital here and let other traders fight."
        )
    elif flags["low_contract"] and not flags["asym"]:
        headline = "LIGHT SIZE / SCALP ONLY"
        explanation = (
            "Projected option move is on the small side. It can still work, but think smaller size and faster exits."
        )
    elif flags["asym"] and not flags["low_contract"]:
        headline = "LIGHT SIZE / SCALP ONLY"
        explanation = (
            "The up view and down view are not aligned. Price can whip between stories, so keep risk tight."
        )
    elif flags["compression"]:
        headline = "COMPRESSION / BREAKOUT WATCH"
        explanation = (
            "Lane height is tight. The rail to rail move is smaller, but a clean break beyond the main lane plus the first outer lane "
            "can turn into a sharp run. Best results come from letting the break prove itself before you commit."
        )
    else:
        headline = "NORMAL STRUCTURAL DAY"
        explanation = (
            "There is enough room for a meaningful option move and the views are close enough. Your job is to wait for a clean touch "
            "in the right time window and follow your rules."
        )

    return headline, explanation, flags


def compute_confidence_score(
    primary_height: float,
    alt_height: float,
    contract_factor: float,
    overnight_high: float,
    overnight_low: float,
) -> float:
    """
    Return a 0-100 confidence score based on:
      1. Lane height times option sensitivity
      2. Symmetry between up and down views
      3. Overnight range compared to lane height
    """
    if primary_height <= 0 or contract_factor <= 0:
        return 0.0

    # 1. Structural room for the option
    contract_span = primary_height * contract_factor
    base_ratio = contract_span / MIN_CONTRACT_MOVE if MIN_CONTRACT_MOVE > 0 else 0.0
    base_ratio_clamped = max(0.0, min(base_ratio, 2.0))
    base_score = 40.0 * min(base_ratio_clamped, 1.0) + 20.0 * max(base_ratio_clamped - 1.0, 0.0)

    # 2. Symmetry between views
    symmetry_score = 20.0
    if alt_height and alt_height > 0:
        big = max(primary_height, alt_height)
        small = min(primary_height, alt_height)
        if small > 0:
            ratio = big / small
            if ratio <= 1.0:
                symmetry_score = 20.0
            elif ratio >= ASYM_RATIO_MAX:
                symmetry_score = 5.0
            else:
                span = ASYM_RATIO_MAX - 1.0
                penalty = (ratio - 1.0) / span
                symmetry_score = 20.0 - 15.0 * penalty

    # 3. Overnight range vs lane height
    overnight_score = 20.0
    if overnight_high > overnight_low and primary_height > 0:
        night_range = overnight_high - overnight_low
        ratio_night = night_range / primary_height
        if 0.5 <= ratio_night <= 1.5:
            overnight_score = 20.0
        elif 0.3 <= ratio_night <= 2.0:
            overnight_score = 12.0
        else:
            overnight_score = 6.0

    score = base_score + symmetry_score + overnight_score
    return max(0.0, min(score, 100.0))


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

    # Session state containers
    if "asc_channel_df" not in st.session_state:
        st.session_state["asc_channel_df"] = None
    if "desc_channel_df" not in st.session_state:
        st.session_state["desc_channel_df"] = None
    if "asc_height" not in st.session_state:
        st.session_state["asc_height"] = None
    if "desc_height" not in st.session_state:
        st.session_state["desc_height"] = None
    if "stack_depth_suggestion" not in st.session_state:
        st.session_state["stack_depth_suggestion"] = 1
    if "stack_label" not in st.session_state:
        st.session_state["stack_label"] = ""
    if "flip_levels" not in st.session_state:
        st.session_state["flip_levels"] = []

    # Sidebar
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.caption(TAGLINE)
        st.markdown("---")

        st.markdown("#### Core Settings")
        st.write(f"Lane slope: **{SLOPE_MAG:.3f} pts / 30 min**")

        contract_factor = st.number_input(
            "Option sensitivity (approx move per 1 SPX point)",
            min_value=0.10,
            max_value=1.00,
            value=CONTRACT_FACTOR_DEFAULT,
            step=0.01,
            help="For many 0DTE near the money contracts, around 0.33 is common.",
            key="contract_factor",
        )

        st.markdown("---")
        st.markdown("#### Overnight feel (optional)")

        overnight_low = st.number_input(
            "Overnight low",
            value=0.0,
            step=0.5,
            help="Futures or SPX overnight low for this session.",
            key="ov_low",
        )
        overnight_high = st.number_input(
            "Overnight high",
            value=0.0,
            step=0.5,
            help="Futures or SPX overnight high for this session.",
            key="ov_high",
        )

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Lanes are built from yesterday's key swing high and low.\n"
            "• Pivots can include overnight action up to 03:00.\n"
            "• A fixed slope carries those lanes through today's RTH."
        )

    hero()

    tabs = st.tabs(
        [
            "🗺 Map of the Day",
            "🎯 Option Move Planner",
            "📓 Game Plan",
            "ℹ️ Behind the Scenes",
        ]
    )

    # ============= TAB 1 – MAP OF THE DAY =============
    with tabs[0]:
        card(
            "Map of the Day",
            "Pick yesterday's key swing high and low. The app draws today's lanes (up and down), "
            "plus outer lanes suggested by how the night traded.",
            badge="Lanes and Outer Lanes",
        )

        section_header("Yesterday's Key Swings")

        st.markdown(
            """
            <div class="spx-sub">
              Choose the main <strong>high swing</strong> and <strong>low swing</strong> from the previous regular-hours
              session or from the overnight stretch up to 03:00. Times are in CT.
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**High Swing**")
            high_price = st.number_input(
                "High price (prior RTH or up to 03:00)",
                value=5200.0,
                step=0.25,
                key="high_pivot",
            )
            high_time = st.time_input(
                "High time (CT)",
                value=dtime(11, 0),
                step=1800,
                key="high_time",
            )
            high_is_night = st.checkbox(
                "High was between midnight and 03:00",
                value=False,
                key="high_is_night",
            )

        with c2:
            st.markdown("**Low Swing**")
            low_price = st.number_input(
                "Low price (prior RTH or up to 03:00)",
                value=5100.0,
                step=0.25,
                key="low_pivot",
            )
            low_time = st.time_input(
                "Low time (CT)",
                value=dtime(13, 0),
                step=1800,
                key="low_time",
            )
            low_is_night = st.checkbox(
                "Low was between midnight and 03:00",
                value=False,
                key="low_is_night",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        build_col = st.columns([1, 3])[0]
        with build_col:
            if st.button("Draw today's lanes", use_container_width=True, key="build_channels_btn"):
                df_asc, h_asc = build_structural_channel(
                    high_price=high_price,
                    high_time=high_time,
                    low_price=low_price,
                    low_time=low_time,
                    slope_sign=+1,
                    high_is_night=high_is_night,
                    low_is_night=low_is_night,
                )
                df_desc, h_desc = build_structural_channel(
                    high_price=high_price,
                    high_time=high_time,
                    low_price=low_price,
                    low_time=low_time,
                    slope_sign=-1,
                    high_is_night=high_is_night,
                    low_is_night=low_is_night,
                )

                df_asc = extend_stacks(df_asc, h_asc, MAX_STACK_DEPTH)
                df_desc = extend_stacks(df_desc, h_desc, MAX_STACK_DEPTH)

                st.session_state["asc_channel_df"] = df_asc
                st.session_state["desc_channel_df"] = df_desc
                st.session_state["asc_height"] = h_asc
                st.session_state["desc_height"] = h_desc

                depth_suggest, label = suggest_stack_depth(
                    channel_height=max(h_asc, h_desc),
                    overnight_high=overnight_high,
                    overnight_low=overnight_low,
                )
                st.session_state["stack_depth_suggestion"] = depth_suggest
                st.session_state["stack_label"] = label

                st.success("Lanes drawn for both the up view and the down view.")

        df_asc = st.session_state["asc_channel_df"]
        df_desc = st.session_state["desc_channel_df"]
        h_asc = st.session_state["asc_height"]
        h_desc = st.session_state["desc_height"]

        if df_asc is None or df_desc is None:
            section_header("Today's RTH Grid")
            st.info("After you draw the lanes, you will see a full time by price grid with main and outer lanes.")
        else:
            view_choice = st.radio(
                "Which view do you want to see right now?",
                ["Up view only", "Down view only", "Show both"],
                index=2,
                horizontal=True,
                key="map_view_choice",
            )

            section_header("Quick Summary")

            depth_suggest = st.session_state.get("stack_depth_suggestion", 1)
            stack_label = st.session_state.get("stack_label", "")

            s1, s2, s3 = st.columns(3)
            with s1:
                st.markdown(
                    metric_card(
                        "Up view lane height",
                        f"{h_asc:.2f} pts",
                        "Bottom lane to top lane.",
                    ),
                    unsafe_allow_html=True,
                )
            with s2:
                st.markdown(
                    metric_card(
                        "Down view lane height",
                        f"{h_desc:.2f} pts",
                        "Top lane to bottom lane.",
                    ),
                    unsafe_allow_html=True,
                )
            with s3:
                st.markdown(
                    metric_card(
                        "Suggested outer lanes",
                        f"{depth_suggest} each side",
                        stack_label,
                    ),
                    unsafe_allow_html=True,
                )

            if view_choice in ["Up view only", "Show both"]:
                section_header("Up View (Rising Lanes)")
                a1, a2 = st.columns([3, 1])
                with a1:
                    cols_to_show = ["Time", "Main Top", "Main Bottom"]
                    for lvl in range(1, depth_suggest + 1):
                        cols_to_show.extend(
                            [f"Stack+{lvl} Top", f"Stack+{lvl} Bottom", f"Stack-{lvl} Top", f"Stack-{lvl} Bottom"]
                        )
                    cols_to_show = [c for c in cols_to_show if c in df_asc.columns]
                    st.dataframe(df_asc[cols_to_show], use_container_width=True, hide_index=True, height=340)
                with a2:
                    st.markdown(
                        metric_card(
                            "Max outer lane shown",
                            f"+/- {depth_suggest}",
                            "You can scroll in the table to see all lanes if needed.",
                        ),
                        unsafe_allow_html=True,
                    )

            if view_choice in ["Down view only", "Show both"]:
                section_header("Down View (Falling Lanes)")
                d1, d2 = st.columns([3, 1])
                with d1:
                    cols_to_show_d = ["Time", "Main Top", "Main Bottom"]
                    for lvl in range(1, depth_suggest + 1):
                        cols_to_show_d.extend(
                            [f"Stack+{lvl} Top", f"Stack+{lvl} Bottom", f"Stack-{lvl} Top", f"Stack-{lvl} Bottom"]
                        )
                    cols_to_show_d = [c for c in cols_to_show_d if c in df_desc.columns]
                    st.dataframe(df_desc[cols_to_show_d], use_container_width=True, hide_index=True, height=340)
                with d2:
                    st.markdown(
                        metric_card(
                            "Same outer lanes",
                            f"+/- {depth_suggest}",
                            "Both views use the same outer lane depth.",
                        ),
                        unsafe_allow_html=True,
                    )

        end_card()

    # ============= TAB 2 – OPTION MOVE PLANNER =============
    with tabs[1]:
        card(
            "Option Move Planner",
            "Take the distance between lanes, apply your option sensitivity, and build a simple rail to rail template "
            "for calls or puts.",
            badge="Options Layer",
        )

        df_asc = st.session_state["asc_channel_df"]
        df_desc = st.session_state["desc_channel_df"]
        h_asc = st.session_state["asc_height"]
        h_desc = st.session_state["desc_height"]

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("No lanes yet. Draw today's lanes first in Map of the Day.")
            end_card()
        else:
            section_header("Which version are you leaning toward?")

            default_primary_index = 0 if h_asc >= h_desc else 1
            primary_choice = st.radio(
                "Today's main story",
                ["Up Day View", "Down Day View"],
                index=default_primary_index,
                horizontal=True,
                key="primary_scenario_contract_tab",
            )

            if primary_choice == "Up Day View":
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
                        "Main story",
                        primary_choice,
                        "The version of the map you are planning to lean on.",
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card(
                        "Room from rail to rail",
                        f"{primary_height:.2f} pts",
                        "Full distance from one main lane to the opposite lane.",
                    ),
                    unsafe_allow_html=True,
                )
            with c3:
                asym_text = "N/A"
                note = "Uses both views."
                if primary_height and alt_height and alt_height > 0 and primary_height > 0:
                    big = max(primary_height, alt_height)
                    small = min(primary_height, alt_height)
                    ratio = big / small
                    asym_text = f"{ratio:.2f}x"
                    note = "Above 1.30x means one side of the story dominates."
                st.markdown(
                    metric_card(
                        "Difference between views",
                        asym_text,
                        note,
                    ),
                    unsafe_allow_html=True,
                )

            section_header("How big a bite are you aiming for?")

            underlying_full_span = primary_height
            contract_full_span = underlying_full_span * contract_factor
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(
                    metric_card(
                        "Full rail to rail move",
                        f"{underlying_full_span:.2f} pts",
                        "If price travels the whole lane.",
                    ),
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    metric_card(
                        "Option move on full span",
                        f"{contract_full_span:.2f} units",
                        f"Using sensitivity {contract_factor:.2f}.",
                    ),
                    unsafe_allow_html=True,
                )
            with m3:
                ratio_vs_min = contract_full_span / MIN_CONTRACT_MOVE if MIN_CONTRACT_MOVE > 0 else 0.0
                st.markdown(
                    metric_card(
                        "Power vs minimum move",
                        f"{ratio_vs_min:.2f}x",
                        f"Below 1.0x is more of a small win day.",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Your planned play")

            t1, t2, t3 = st.columns(3)
            with t1:
                trade_side = st.radio(
                    "Which way are you planning to ride the lane?",
                    ["Long Call (bottom to top)", "Long Put (top to bottom)"],
                    index=0,
                    key="trade_side",
                )
            with t2:
                rail_fraction = st.slider(
                    "How much of the lane do you expect to catch?",
                    min_value=0.50,
                    max_value=1.00,
                    value=1.00,
                    step=0.05,
                    key="rail_fraction",
                    help="1.00 = full lane, 0.70 = take profits earlier and let the rest go.",
                )
            with t3:
                entry_contract_price = st.number_input(
                    "Rough option entry price at the lane",
                    min_value=0.01,
                    value=5.00,
                    step=0.05,
                    key="entry_contract_price",
                    help="Your ballpark option price when the lane touch happens.",
                )

            underlying_plan = primary_height * rail_fraction
            contract_plan_move = underlying_plan * contract_factor
            exit_price = entry_contract_price + contract_plan_move if entry_contract_price > 0 else 0.0
            roi_pct = (contract_plan_move / entry_contract_price * 100.0) if entry_contract_price > 0 else 0.0

            # Store for Game Plan bridging
            st.session_state["primary_height_for_play"] = primary_height
            st.session_state["primary_choice_for_play"] = primary_choice
            st.session_state["rail_fraction_for_play"] = rail_fraction
            st.session_state["entry_contract_price_for_play"] = entry_contract_price
            st.session_state["contract_plan_move_for_play"] = contract_plan_move
            st.session_state["roi_pct_for_play"] = roi_pct

            c4, c5, c6 = st.columns(3)
            with c4:
                st.markdown(
                    metric_card(
                        "Planned underlying move",
                        f"{underlying_plan:.2f} pts",
                        f"{rail_fraction:.0%} of your lane.",
                    ),
                    unsafe_allow_html=True,
                )
            with c5:
                st.markdown(
                    metric_card(
                        "Planned option move",
                        f"+{contract_plan_move:.2f}",
                        f"Needs at least {MIN_CONTRACT_MOVE:.1f} to feel worth it.",
                    ),
                    unsafe_allow_html=True,
                )
            with c6:
                st.markdown(
                    metric_card(
                        "Planned exit price",
                        f"{exit_price:.2f}",
                        f"Rough return: {roi_pct:.1f} percent.",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Time by price view with option overlay")

            st.caption(
                "Each row is a 30 minute slot on your main view. Lanes show location. "
                "The option columns show what a full lane move could pay."
            )

            map_df = primary_df.copy()
            map_df["Lane Span"] = round(primary_height, 2)
            map_df["Option Δ (full lane)"] = round(primary_height * contract_factor, 2)
            if entry_contract_price > 0:
                map_df["Rough Exit @ full lane"] = round(entry_contract_price + primary_height * contract_factor, 2)
            else:
                map_df["Rough Exit @ full lane"] = None

            st.dataframe(map_df, use_container_width=True, hide_index=True, height=420)

            st.markdown(
                """
                <div class="spx-sub" style="margin-top:8px;">
                  The table does not try to guess where the touch will happen. It gives a clean grid:
                  time on one axis, lanes on the other, and what a full move might hand your option.
                </div>
                """,
                unsafe_allow_html=True,
            )

        end_card()

    # ============= TAB 3 – GAME PLAN (with Signal Scanner) =============
    with tabs[2]:
        card(
            "Game Plan",
            "Turn the map into a label for the day, combine it with where we open, scan your latest 30 minute candle "
            "against the lanes, and see if your planned option move is worth pressing.",
            badge="Execution Layer",
        )

        df_asc = st.session_state["asc_channel_df"]
        df_desc = st.session_state["desc_channel_df"]
        h_asc = st.session_state["asc_height"]
        h_desc = st.session_state["desc_height"]

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("No lanes yet. Draw today's lanes first in Map of the Day.")
            end_card()
        else:
            section_header("Which version are you watching today?")

            default_primary_index = 0 if h_asc >= h_desc else 1
            primary_choice = st.radio(
                "Main view for today",
                ["Up Day View", "Down Day View"],
                index=default_primary_index,
                horizontal=True,
                key="primary_scenario_playbook",
            )

            if primary_choice == "Up Day View":
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
                        "Main view",
                        primary_choice,
                        "Based on your chosen swings.",
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card(
                        "Room from rail to rail",
                        f"{primary_height:.2f} pts",
                        "This is your playground for the day.",
                    ),
                    unsafe_allow_html=True,
                )
            with c3:
                asym_text = "N/A"
                note = "Looks at both views."
                if primary_height and alt_height and alt_height > 0 and primary_height > 0:
                    big = max(primary_height, alt_height)
                    small = min(primary_height, alt_height)
                    ratio = big / small
                    asym_text = f"{ratio:.2f}x"
                    note = "Above 1.30x means one side of the story is louder."
                st.markdown(
                    metric_card(
                        "Difference between views",
                        asym_text,
                        note,
                    ),
                    unsafe_allow_html=True,
                )

            # Day label and confidence score
            section_header("Big picture and confidence score")

            headline, explanation, flags = classify_day(
                primary_height=primary_height,
                alt_height=alt_height,
                contract_factor=contract_factor,
            )
            confidence_score = compute_confidence_score(
                primary_height=primary_height,
                alt_height=alt_height,
                contract_factor=contract_factor,
                overnight_high=overnight_high,
                overnight_low=overnight_low,
            )

            if headline == "STAND ASIDE":
                banner_class = "spx-banner-stop"
                icon = "🛑"
                friendly = "No Trade Zone"
            elif headline == "LIGHT SIZE / SCALP ONLY":
                banner_class = "spx-banner-caution"
                icon = "⚠️"
                friendly = "Small Chips Only"
            elif headline == "COMPRESSION / BREAKOUT WATCH":
                banner_class = "spx-banner-caution"
                icon = "📏"
                friendly = "Compression Breakout Watch"
            elif headline == "NORMAL STRUCTURAL DAY":
                banner_class = "spx-banner-ok"
                icon = "✅"
                friendly = "All Systems Go (with discipline)"
            else:
                banner_class = "spx-banner-caution"
                icon = "ℹ️"
                friendly = headline

            d1, d2 = st.columns(2)
            with d1:
                st.markdown(
                    f"""
                    <div class="{banner_class}">
                      <strong>{icon} {friendly}</strong><br>
                      {explanation}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with d2:
                st.markdown(
                    metric_card(
                        "Daily confidence score",
                        f"{confidence_score:.0f} / 100",
                        "Higher scores mean better alignment between lane size, option power, and overnight action.",
                    ),
                    unsafe_allow_html=True,
                )

            # Open location
            section_header("Where do we open inside the lanes?")

            b1, b2 = st.columns(2)
            with b1:
                open_price = st.number_input(
                    "SPX opening or early reference price",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    help="For example: the official open, or the price at 09:00 CT.",
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
                stack_up_top = row.get("Stack+1 Top", main_top)
                stack_down_bottom = row.get("Stack-1 Bottom", main_bottom)

                # Surprise logic
                true_day_label = ""
                true_banner_class = None
                true_icon = ""

                if primary_choice == "Up Day View" and open_price < main_bottom:
                    true_day_label = "Bear Surprise Day"
                    true_banner_class = "spx-banner-stop"
                    true_icon = "🐻"
                elif primary_choice == "Down Day View" and open_price > main_top:
                    true_day_label = "Bull Takeover Day"
                    true_banner_class = "spx-banner-stop"
                    true_icon = "🐂"

                if true_day_label:
                    st.markdown(
                        f"""
                        <div class="{true_banner_class}" style="margin-top:4px; margin-bottom:6px;">
                          <strong>{true_icon} {true_day_label}</strong><br>
                          Open is beyond the main lane in the opposite direction of your main view. Expect fake outs and sharp snaps.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                banner_class_bias = "spx-banner-ok"
                icon_bias = "✅"
                pos_text = ""
                suggestion = ""

                if main_bottom < main_top:
                    if main_bottom <= open_price <= main_top:
                        pos = (open_price - main_bottom) / (main_top - main_bottom)
                        if primary_choice == "Up Day View":
                            if pos <= 0.3:
                                pos_text = "near the lower lane inside the main channel."
                                suggestion = (
                                    "Bias: you have room above. Best ideas often come from patient bounces here, "
                                    "especially after the first hour."
                                )
                            elif pos >= 0.7:
                                pos_text = "near the upper lane inside the main channel."
                                suggestion = (
                                    "Bias: upside is already stretched. Treat fresh calls carefully here and be open "
                                    "to quick puts if you see a clean rejection."
                                )
                            else:
                                pos_text = "around the middle of the channel."
                                suggestion = (
                                    "Bias: middle of the playground. Let price choose a lane before you commit."
                                )
                        else:
                            if pos <= 0.3:
                                pos_text = "near the lower lane inside the main channel."
                                suggestion = (
                                    "Bias: in a falling day, this is where bounces often run out of steam. "
                                    "Watch how price behaves as it climbs back toward the upper lane."
                                )
                            elif pos >= 0.7:
                                pos_text = "near the upper lane inside the main channel."
                                suggestion = (
                                    "Bias: main short ideas usually live here on down days, once the rejection is clear."
                                )
                            else:
                                pos_text = "around the middle of the channel."
                                suggestion = (
                                    "Bias: neutral. Wait for price to hug a lane instead of guessing in the center."
                                )
                    else:
                        if open_price > main_top:
                            if open_price <= stack_up_top:
                                pos_text = "above the main channel but inside the first upper outer lane."
                                suggestion = (
                                    "Bias: this is an extension zone. It can still snap back into the main lanes. "
                                    "Wait for price to slow down before stepping in."
                                )
                                banner_class_bias = "spx-banner-caution"
                                icon_bias = "⚠️"
                            else:
                                pos_text = "well above both the main lane and the first upper outer lane."
                                suggestion = (
                                    "Bias: very stretched. Chasing in the same direction here usually ends badly."
                                )
                                banner_class_bias = "spx-banner-stop"
                                icon_bias = "🛑"
                        elif open_price < main_bottom:
                            if open_price >= stack_down_bottom:
                                pos_text = "below the main channel but inside the first lower outer lane."
                                suggestion = (
                                    "Bias: extension to the downside. Watch for exhaustion; often the best moves are "
                                    "back into the main lanes from here."
                                )
                                banner_class_bias = "spx-banner-caution"
                                icon_bias = "⚠️"
                            else:
                                pos_text = "well below both the main lane and the first lower outer lane."
                                suggestion = (
                                    "Bias: washed out levels. Let other traders chase; you protect your firepower."
                                )
                                banner_class_bias = "spx-banner-stop"
                                icon_bias = "🛑"
                else:
                    pos_text = "not well defined because the lanes are flat."
                    suggestion = "Check your chosen swings; top and bottom should not be the same."

                st.markdown(
                    f"""
                    <div class="{banner_class_bias}" style="margin-top:8px;">
                      <strong>{icon_bias} Where that price sits</strong><br>
                      At {open_slot} CT, a price of <strong>{open_price:.2f}</strong> sits {pos_text}<br>
                      {suggestion}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Signal Scanner
            section_header("Signal Scanner on latest 30 minute candle")

            st.markdown(
                """
                <div class="spx-sub">
                  Enter the latest 30 minute candle and let the app check it against your lanes using your rule set:
                  bearish candles pressing support on an up day for longs, bullish candles pressing resistance on a down day for shorts,
                  and clear closes through lanes turning them into flip levels.
                </div>
                """,
                unsafe_allow_html=True,
            )

            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                candle_type = st.radio(
                    "Candle type",
                    ["Bearish", "Bullish"],
                    index=0,
                    horizontal=True,
                    key="candle_type",
                )
            with cc2:
                candle_high = st.number_input(
                    "Candle high",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key="candle_high",
                )
            with cc3:
                candle_low = st.number_input(
                    "Candle low",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key="candle_low",
                )

            c_close, c_slot, c_tol = st.columns(3)
            with c_close:
                candle_close = st.number_input(
                    "Candle close",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key="candle_close",
                )
            with c_slot:
                slot_options_sig = list(primary_df["Time"])
                default_idx_sig = len(slot_options_sig) - 1
                candle_slot = st.selectbox(
                    "Candle time slot",
                    options=slot_options_sig,
                    index=default_idx_sig,
                    key="candle_slot",
                )
            with c_tol:
                tolerance_points = st.number_input(
                    "Touch tolerance (points)",
                    min_value=1.0,
                    max_value=10.0,
                    value=5.0,
                    step=0.5,
                    key="tolerance_points",
                    help="Close must be within this many points of the lane to count as a tight touch.",
                )

            if st.button("Check this candle against the lanes", key="check_signal_btn"):
                signal_messages = []
                flip_messages = []
                noise_messages = []

                if candle_high <= 0.0 or candle_low <= 0.0 or candle_close <= 0.0:
                    st.markdown(
                        """
                        <div class="spx-banner-caution">
                          Enter valid high, low, and close values to scan this candle.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    row_c = primary_df[primary_df["Time"] == candle_slot].iloc[0]
                    rails = [("Top rail", "Main Top"), ("Bottom rail", "Main Bottom")]

                    for rail_name, rail_col in rails:
                        rail_price = row_c[rail_col]
                        touched = (candle_high >= rail_price >= candle_low)
                        dist = abs(candle_close - rail_price)

                        if not touched:
                            continue

                        # Up day logic
                        if primary_choice == "Up Day View":
                            if candle_type == "Bearish" and candle_close > rail_price and dist <= tolerance_points:
                                signal_messages.append(
                                    f"Long from {rail_name} around {rail_price:.2f} "
                                    f"(bear candle touch, close above, within {dist:.1f} pts)."
                                )
                            elif candle_close < rail_price - tolerance_points:
                                flip_messages.append(
                                    f"{rail_name} around {rail_price:.2f} becomes a flip level. "
                                    "Next time price buys into it from below, bias is to sell away from it."
                                )
                                st.session_state["flip_levels"].append(
                                    {
                                        "view": "Up",
                                        "rail": rail_name,
                                        "price": round(rail_price, 2),
                                        "time": candle_slot,
                                    }
                                )
                            elif dist > tolerance_points:
                                noise_messages.append(
                                    f"{rail_name} was touched but the close was {dist:.1f} pts away. "
                                    "Treat this as noise, not a clean structural signal."
                                )

                        # Down day logic
                        else:
                            if candle_type == "Bullish" and candle_close < rail_price and dist <= tolerance_points:
                                signal_messages.append(
                                    f"Short from {rail_name} around {rail_price:.2f} "
                                    f"(bull candle touch, close below, within {dist:.1f} pts)."
                                )
                            elif candle_close > rail_price + tolerance_points:
                                flip_messages.append(
                                    f"{rail_name} around {rail_price:.2f} becomes a flip level. "
                                    "Next time price sells into it from above, bias is to buy away from it."
                                )
                                st.session_state["flip_levels"].append(
                                    {
                                        "view": "Down",
                                        "rail": rail_name,
                                        "price": round(rail_price, 2),
                                        "time": candle_slot,
                                    }
                                )
                            elif dist > tolerance_points:
                                noise_messages.append(
                                    f"{rail_name} was touched but the close was {dist:.1f} pts away. "
                                    "Treat this as noise, not a clean structural signal."
                                )

                    # Display results
                    if signal_messages:
                        st.markdown(
                            "<div class='spx-banner-ok'><strong>✅ Structural signal detected</strong><br>"
                            + "<br>".join(signal_messages)
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                    if flip_messages:
                        st.markdown(
                            "<div class='spx-banner-caution'><strong>⚠️ Flip level created</strong><br>"
                            + "<br>".join(flip_messages)
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                    if noise_messages and not signal_messages and not flip_messages:
                        st.markdown(
                            "<div class='spx-banner-caution'><strong>ℹ️ Touch but not tight</strong><br>"
                            + "<br>".join(noise_messages)
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                    if not signal_messages and not flip_messages and not noise_messages:
                        st.markdown(
                            """
                            <div class="spx-banner-caution">
                              No main rail was touched by this candle. This one is outside your structural rule set.
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

            # Active flip levels
            if st.session_state["flip_levels"]:
                section_header("Active flip levels")

                fl_df = pd.DataFrame(st.session_state["flip_levels"])
                fl_df = fl_df[["view", "rail", "price", "time"]]
                fl_df.columns = ["View", "Rail", "Price", "Time"]
                st.dataframe(fl_df, use_container_width=True, hide_index=True, height=200)
            else:
                st.caption("No flip levels recorded yet for this session.")

            # Play of the Day (based on planner)
            section_header("Play of the Day (based on your planner)")

            primary_height_for_play = st.session_state.get("primary_height_for_play", primary_height)
            rail_fraction_for_play = st.session_state.get("rail_fraction_for_play", 1.0)
            entry_contract_price_for_play = st.session_state.get("entry_contract_price_for_play", 5.0)
            contract_plan_move_for_play = st.session_state.get(
                "contract_plan_move_for_play",
                primary_height_for_play * contract_factor * rail_fraction_for_play,
            )
            roi_pct_for_play = st.session_state.get("roi_pct_for_play", 0.0)

            if contract_plan_move_for_play >= MIN_CONTRACT_MOVE * 1.5 and roi_pct_for_play >= 100:
                play_label = "Green Light Setup"
                play_banner = "spx-banner-ok"
                play_icon = "🚀"
                play_text = "The lane gives your option plenty of room. If your entry rules line up, this deserves your full focus."
            elif contract_plan_move_for_play >= MIN_CONTRACT_MOVE:
                play_label = "Decent Opportunity"
                play_banner = "spx-banner-caution"
                play_icon = "✨"
                play_text = "This can still be a solid trade. Think in terms of singles and doubles, not home runs."
            else:
                play_label = "Save Your Bullets"
                play_banner = "spx-banner-stop"
                play_icon = "🧊"
                play_text = "The planned option move is small. Today might be better for watching and recording notes."

            st.markdown(
                f"""
                <div class="{play_banner}">
                  <strong>{play_icon} {play_label}</strong><br>
                  Planned option move: <strong>{contract_plan_move_for_play:.2f}</strong> from an entry around <strong>{entry_contract_price_for_play:.2f}</strong>.<br>
                  Rough return if the plan plays out: <strong>{roi_pct_for_play:.1f}%</strong>.<br>
                  {play_text}
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Execution checklist")

            st.markdown(
                """
                <div class="spx-sub">
                  <ul style="margin-left:18px;">
                    <li>Your day label and confidence score both say it is worth playing.</li>
                    <li>The first clean touch at a lane appears after the opening chaos, not inside it.</li>
                    <li>Signal scanner agrees with your eyes on the candle.</li>
                    <li>You know in advance what price means "I am wrong" and where you will exit.</li>
                    <li>You respect your max loss for the day, no matter how good the next candle looks.</li>
                  </ul>
                  The app gives structure, names, and numbers. Your edge is how consistently you follow your rules on top of that.
                </div>
                """,
                unsafe_allow_html=True,
            )

        end_card()

    # ============= TAB 4 – BEHIND THE SCENES =============
    with tabs[3]:
        card("Behind the Scenes", TAGLINE, badge="Design Notes")

        st.markdown(
            """
            <div class="spx-sub" style="font-size:0.95rem; line-height:1.7;">
              <p><strong>What this tool does quietly:</strong></p>
              <ul style="margin-left:18px;">
                <li>Takes yesterday's chosen high swing and low swing as the rails for today.</li>
                <li>Lets those swings come from prior RTH or from overnight up to 03:00.</li>
                <li>Uses a fixed slope of 0.475 points per 30 minutes to carry those rails forward.</li>
                <li>Builds an up day view and a down day view from the same swings.</li>
                <li>Adds outer lanes above and below so you can see stretch and snap back zones.</li>
                <li>Turns the distance between rails into an option move using your sensitivity number.</li>
                <li>Gives the day a simple label and a confidence score so you know whether to press, scalp, or sit out.</li>
                <li>Lets you scan each 30 minute candle against the lanes using your own touch rules and flip levels.</li>
              </ul>

              <p><strong>What it does not try to do:</strong></p>
              <ul style="margin-left:18px;">
                <li>Predict news, volatility spikes, or sudden waves of buyers or sellers.</li>
                <li>Replace your own entry pattern, stop placement, or review process.</li>
                <li>Guarantee wins. It makes the map and the math easier to see and repeat.</li>
              </ul>

              <p>The goal is clear lanes, honest math, and a clean bridge from structure to options to actual signals.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet · Lanes, option map, signals, and game plan in one screen.</div>",
        unsafe_allow_html=True,
    )


def suggest_stack_depth(channel_height: float, overnight_high: float, overnight_low: float) -> tuple[int, str]:
    """
    Suggest how many extra lanes to pay attention to based on
    how the night range compares to the main channel height.
    """
    if channel_height <= 0 or overnight_high <= overnight_low:
        return 1, "Night range unknown or flat. Defaulting to one extra lane each side."

    night_range = overnight_high - overnight_low
    ratio = night_range / channel_height

    if ratio <= 0.75:
        depth = 1
        label = "Calm night. Main lane plus one outer lane is usually enough."
    elif ratio <= 1.5:
        depth = 2
        label = "Busy night. Two outer lanes give a clearer view of stretch zones."
    else:
        depth = 3
        label = "Wild night. Price has shown it can step out far, so three outer lanes may be helpful."

    return depth, label


if __name__ == "__main__":
    main()