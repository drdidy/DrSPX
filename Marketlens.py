# spx_prophet.py
# SPX Prophet – Structural Channels + Stacked Rails + Bias + Contract Estimator
# Prior RTH pivots only. No EM. Contract factor model.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475        # pts per 30 min for underlying rails
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 "anchor" for 30m grid
CONTRACT_FACTOR_DEFAULT = 0.33           # contract move ≈ factor × SPX move
MIN_CHANNEL_HEIGHT = 60.0                # below this, structure is too tight
ASYM_RATIO_MAX = 1.30                    # >30% asymmetry = caution
MIN_CONTRACT_MOVE = 9.9                  # below this, not worth the risk


# ===============================
# STUNNING LIGHT UI
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

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
        padding-top: 3.0rem;
        padding-bottom: 4rem;
        max-width: 1400px;
    }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.08), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 2px solid rgba(99, 102, 241, 0.15);
        box-shadow:
            8px 0 40px rgba(99, 102, 241, 0.08),
            4px 0 20px rgba(0, 0, 0, 0.03);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #6366f1 0%, #3b82f6 50%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.2rem;
        letter-spacing: -0.04em;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.2rem 0;
        border: none;
        height: 2px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(99, 102, 241, 0.3) 20%,
            rgba(59, 130, 246, 0.5) 50%,
            rgba(99, 102, 241, 0.3) 80%,
            transparent 100%);
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
    }

    /* HERO */
    .hero-wrapper {
        display: flex;
        justify-content: center;
        margin-bottom: 1.5rem;
    }

    .hero-header {
        max-width: 900px;
        text-align: center;
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.12), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(59, 130, 246, 0.12), transparent 60%),
            linear-gradient(135deg, #ffffff, #fafbff);
        border-radius: 32px;
        padding: 32px 40px;
        border: 2px solid rgba(99, 102, 241, 0.2);
        box-shadow:
            0 24px 60px -12px rgba(99, 102, 241, 0.15),
            0 12px 30px -8px rgba(0, 0, 0, 0.08),
            inset 0 2px 4px rgba(255, 255, 255, 0.9),
            inset 0 -2px 4px rgba(99, 102, 241, 0.05);
        overflow: hidden;
        animation: heroGlow 6s ease-in-out infinite;
    }

    @keyframes heroGlow {
        0%, 100% { box-shadow: 0 24px 60px -12px rgba(99, 102, 241, 0.15), 0 12px 30px -8px rgba(0, 0, 0, 0.08); }
        50% { box-shadow: 0 24px 60px -12px rgba(99, 102, 241, 0.25), 0 12px 30px -8px rgba(99, 102, 241, 0.15); }
    }

    .hero-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #6366f1, #3b82f6, #06b6d4, #3b82f6, #6366f1);
        background-size: 200% 100%;
        animation: shimmer 4s linear infinite;
    }

    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    .hero-status {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        background:
            linear-gradient(135deg, rgba(16, 185, 129, 0.16), rgba(5, 150, 105, 0.12)),
            #ffffff;
        border: 2px solid rgba(16, 185, 129, 0.4);
        font-size: 0.8rem;
        font-weight: 700;
        color: #059669;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        margin-bottom: 10px;
        box-shadow:
            0 8px 24px rgba(16, 185, 129, 0.18),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
        animation: statusPulse 2s ease-in-out infinite;
    }

    .hero-status::before {
        content: '';
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #10b981;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.7);
    }

    @keyframes statusPulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.04); opacity: 0.9; }
    }

    .hero-title {
        font-size: 2.7rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 40%, #3b82f6 70%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0.2rem 0 0.1rem 0;
        letter-spacing: -0.06em;
        line-height: 1.05;
    }

    .hero-subtitle {
        font-size: 1.1rem;
        color: #64748b;
        margin-top: 6px;
        font-weight: 500;
        font-family: 'Poppins', sans-serif;
    }

    .hero-tagline {
        margin-top: 10px;
        font-size: 0.95rem;
        color: #475569;
        line-height: 1.6;
    }

    /* CARDS */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 8% 8%, rgba(99, 102, 241, 0.08), transparent 50%),
            radial-gradient(circle at 92% 92%, rgba(59, 130, 246, 0.08), transparent 50%),
            linear-gradient(135deg, #ffffff, #fefeff);
        border-radius: 28px;
        border: 2px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 22px 55px -12px rgba(148, 163, 184, 0.4),
            0 10px 30px -10px rgba(15, 23, 42, 0.35),
            inset 0 1px 3px rgba(255, 255, 255, 0.9);
        padding: 26px 30px;
        margin-bottom: 32px;
        transition: all 0.45s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }

    .spx-card:hover {
        transform: translateY(-6px) scale(1.01);
        border-color: rgba(99, 102, 241, 0.6);
        box-shadow:
            0 30px 70px -16px rgba(99, 102, 241, 0.35),
            0 14px 40px -10px rgba(15, 23, 42, 0.45);
    }

    .spx-card h4 {
        font-size: 1.7rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 8px 0;
        letter-spacing: -0.04em;
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        border: 2px solid rgba(99, 102, 241, 0.35);
        background:
            linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(59, 130, 246, 0.08)),
            #ffffff;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        color: #6366f1;
        text-transform: uppercase;
        box-shadow:
            0 6px 20px rgba(99, 102, 241, 0.2),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
        margin-bottom: 12px;
    }

    .spx-sub {
        color: #475569;
        font-size: 0.98rem;
        line-height: 1.7;
        font-weight: 400;
    }

    /* SECTION HEADERS */
    .section-header {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 2.2rem 0 1.1rem 0;
        padding-bottom: 0.6rem;
        border-bottom: 2px solid transparent;
        border-image: linear-gradient(90deg, #6366f1, #3b82f6, transparent) 1;
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
        box-shadow:
            0 0 18px rgba(99, 102, 241, 0.7),
            0 4px 12px rgba(99, 102, 241, 0.4);
    }

    /* METRICS */
    .spx-metric {
        position: relative;
        padding: 18px 18px;
        border-radius: 18px;
        background:
            radial-gradient(circle at top left, rgba(99, 102, 241, 0.12), transparent 70%),
            linear-gradient(135deg, #ffffff, #fefeff);
        border: 2px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            0 18px 40px rgba(148, 163, 184, 0.5),
            inset 0 1px 3px rgba(255, 255, 255, 0.9);
        transition: all 0.3s ease;
    }

    .spx-metric:hover {
        transform: translateY(-3px) scale(1.01);
        border-color: rgba(99, 102, 241, 0.7);
        box-shadow:
            0 24px 50px rgba(99, 102, 241, 0.45),
            inset 0 1px 3px rgba(255, 255, 255, 1);
    }

    .spx-metric-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 6px;
    }

    .spx-metric-value {
        font-size: 1.4rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
    }

    .spx-metric-note {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 4px;
    }

    /* ALERT BANNERS */
    .spx-banner-ok {
        padding: 14px 18px;
        border-radius: 16px;
        background:
            linear-gradient(135deg, rgba(22, 163, 74, 0.12), rgba(21, 128, 61, 0.06)),
            #ffffff;
        border: 2px solid rgba(22, 163, 74, 0.35);
        color: #166534;
        font-size: 0.95rem;
        box-shadow: 0 10px 26px rgba(22, 163, 74, 0.18);
    }

    .spx-banner-caution {
        padding: 14px 18px;
        border-radius: 16px;
        background:
            linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(217, 119, 6, 0.06)),
            #ffffff;
        border: 2px solid rgba(245, 158, 11, 0.4);
        color: #92400e;
        font-size: 0.95rem;
        box-shadow: 0 10px 26px rgba(245, 158, 11, 0.2);
    }

    .spx-banner-stop {
        padding: 16px 20px;
        border-radius: 18px;
        background:
            linear-gradient(135deg, rgba(239, 68, 68, 0.14), rgba(185, 28, 28, 0.06)),
            #ffffff;
        border: 2px solid rgba(239, 68, 68, 0.45);
        color: #991b1b;
        font-size: 1.0rem;
        font-weight: 600;
        box-shadow: 0 12px 28px rgba(239, 68, 68, 0.25);
    }

    /* INPUTS */
    .stNumberInput > div > div > input,
    .stTimeInput > div > div > input {
        background: #ffffff !important;
        border: 2px solid rgba(148, 163, 184, 0.7) !important;
        border-radius: 14px !important;
        color: #0f172a !important;
        padding: 10px 12px !important;
        font-size: 0.96rem !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stNumberInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus {
        border-color: #6366f1 !important;
        box-shadow:
            0 0 0 3px rgba(99, 102, 241, 0.2),
            0 8px 22px rgba(99, 102, 241, 0.25) !important;
    }

    /* RADIO & TABS */
    .stRadio > div {
        gap: 10px;
    }

    .stRadio > div > label {
        background: #ffffff;
        padding: 8px 14px;
        border-radius: 999px;
        border: 2px solid rgba(148, 163, 184, 0.8);
        font-size: 0.88rem;
        font-weight: 600;
        color: #475569;
        box-shadow: 0 3px 10px rgba(148, 163, 184, 0.5);
    }

    .stRadio > div > label:hover {
        border-color: rgba(99, 102, 241, 0.8);
        color: #4338ca;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background:
            linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.98));
        padding: 6px;
        border-radius: 999px;
        border: 2px solid rgba(148, 163, 184, 0.7);
        box-shadow: 0 12px 30px rgba(148, 163, 184, 0.6);
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 999px;
        color: #64748b;
        font-weight: 600;
        font-size: 0.9rem;
        padding: 6px 14px;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1, #3b82f6);
        color: #ffffff;
        box-shadow:
            0 6px 18px rgba(99, 102, 241, 0.4),
            inset 0 1px 2px rgba(255, 255, 255, 0.4);
    }

    /* DATAFRAME */
    .stDataFrame {
        border-radius: 18px;
        overflow: hidden;
        box-shadow:
            0 18px 45px rgba(148, 163, 184, 0.6),
            0 10px 26px rgba(15, 23, 42, 0.45);
        border: 2px solid rgba(148, 163, 184, 0.7);
    }

    .stDataFrame div[data-testid="StyledTable"] {
        font-variant-numeric: tabular-nums;
        font-size: 0.9rem;
        font-family: 'JetBrains Mono', monospace;
        background: #ffffff;
    }

    /* FOOTER */
    .app-footer {
        margin-top: 3rem;
        padding-top: 1.6rem;
        border-top: 2px solid rgba(148, 163, 184, 0.7);
        text-align: center;
        color: #64748b;
        font-size: 0.9rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown(
        """
        <div class="hero-wrapper">
          <div class="hero-header">
            <div class="hero-status">System Active</div>
            <h1 class="hero-title">SPX Prophet</h1>
            <p class="hero-subtitle">Where Structure Becomes Foresight.</p>
            <p class="hero-tagline">
              Prior-session pivots define your rails. Stacked channels frame your risk.
              You decide when to step in; the structure tells you when to step aside.
            </p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str, note: str = "") -> str:
    note_html = f"<div class='spx-metric-note'>{note}</div>" if note else ""
    return f"""
    <div class="spx-metric">
      <div class="spx-metric-label">{label}</div>
      <div class="spx-metric-value">{value}</div>
      {note_html}
    </div>
    """


def section_header(text: str):
    st.markdown(f"<h3 class='section-header'>{text}</h3>", unsafe_allow_html=True)


# ===============================
# TIME / GRID HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map a clock time into the synthetic grid.
    Times >= 15:00 are treated as BASE_DATE day.
    Times < 15:00 are treated as BASE_DATE + 1 day.
    """
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    """Align any datetime to nearest 30-minute block."""
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """
    RTH grid for projections: 08:30–14:30 CT, every 30 minutes.
    """
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
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
) -> Tuple[pd.DataFrame, float]:
    """
    Build a structural channel (ascending or descending) from prior RTH pivots
    using constant slope magnitude SLOPE_MAG.
    Returns DataFrame with Time, Main Top/Bottom, Stack ±1 and channel height.
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

    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        main_top = s * k + b_top
        main_bottom = s * k + b_bottom

        stack_up_top = main_top + channel_height
        stack_up_bottom = main_bottom + channel_height
        stack_down_top = main_top - channel_height
        stack_down_bottom = main_bottom - channel_height

        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Main Top": round(main_top, 2),
                "Main Bottom": round(main_bottom, 2),
                "Stack+1 Top": round(stack_up_top, 2),
                "Stack+1 Bottom": round(stack_up_bottom, 2),
                "Stack-1 Top": round(stack_down_top, 2),
                "Stack-1 Bottom": round(stack_down_bottom, 2),
            }
        )

    df = pd.DataFrame(rows)
    return df, round(channel_height, 2)


# ===============================
# STAY-ASIDE / DAY-TYPE LOGIC
# ===============================

def classify_day(
    primary_height: float,
    alt_height: float,
    contract_factor: float,
) -> Tuple[str, str, dict]:
    """
    Combine structural filters into a simple classification:
    - "STAND ASIDE"
    - "LIGHT SIZE / SCALP ONLY"
    - "NORMAL STRUCTURAL DAY"
    Returns (headline, explanation, flags_dict).
    """
    flags = {
        "narrow": False,
        "low_contract": False,
        "asym": False,
    }

    if primary_height <= 0:
        return "NO STRUCTURE", "Pivots not configured yet.", flags

    if primary_height < MIN_CHANNEL_HEIGHT:
        flags["narrow"] = True

    contract_move = primary_height * contract_factor
    if contract_move < MIN_CONTRACT_MOVE:
        flags["low_contract"] = True

    ratio = None
    if alt_height and alt_height > 0:
        big = max(primary_height, alt_height)
        small = min(primary_height, alt_height)
        ratio = big / small if small > 0 else None
        if ratio and ratio > ASYM_RATIO_MAX:
            flags["asym"] = True

    score = sum(flags.values())
    if score >= 2:
        headline = "STAND ASIDE"
        reason = []
        if flags["narrow"]:
            reason.append("rails are too tight to justify risk")
        if flags["low_contract"]:
            reason.append("projected contract move is too small")
        if flags["asym"]:
            reason.append("up vs down structure is unbalanced")
        explanation = (
            " and ".join(reason).capitalize()
            + ". Combine this with your timing rules: if the first clean rail touch "
              "happens before 09:00 CT, keep your powder dry."
        )
    elif score == 1:
        headline = "LIGHT SIZE / SCALP ONLY"
        parts = []
        if flags["narrow"]:
            parts.append("rails are on the tighter side")
        if flags["low_contract"]:
            parts.append("contract move is modest")
        if flags["asym"]:
            parts.append("structure is a bit unbalanced")
        explanation = (
            ", ".join(parts).capitalize()
            + ". You can trade, but treat it as a scalping environment. "
              "Respect your first touch rejection and get paid, don't marry it."
        )
    else:
        headline = "NORMAL STRUCTURAL DAY"
        explanation = (
            "Channel width and projected contract move are healthy, and the two scenarios "
            "are not excessively asymmetric. Your main focus is waiting for a clean touch "
            "and rejection near a rail inside the preferred timing window."
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
        st.caption("Underlying channels are projected on a fixed 30-minute grid.")

        contract_factor = st.number_input(
            "Contract factor (≈ move / SPX move)",
            min_value=0.10,
            max_value=1.00,
            value=CONTRACT_FACTOR_DEFAULT,
            step=0.01,
            help="Rough contract move per 1 point of SPX. 0.33 works well for many 0DTE near-the-money contracts.",
            key="contract_factor_input",
        )

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Underlying maintenance: 16:00–17:00 CT\n"
            "• Contracts maintenance: 16:00–19:00 CT\n"
            "• RTH grid: 08:30–14:30 CT (30m blocks)\n"
            "• Prior RTH structural pivots define the rails for the new day."
        )

    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # Session storage for channels
    if "asc_channel_df" not in st.session_state:
        st.session_state["asc_channel_df"] = None
    if "desc_channel_df" not in st.session_state:
        st.session_state["desc_channel_df"] = None
    if "asc_height" not in st.session_state:
        st.session_state["asc_height"] = None
    if "desc_height" not in st.session_state:
        st.session_state["desc_height"] = None

    # ======================
    # TAB 1 – RAILS SETUP
    # ======================
    with tabs[0]:
        card(
            "Rails + Stacks",
            "Use the structural high and low pivots from the previous regular session "
            "to build both ascending and descending rails. Stacked levels show where "
            "extensions tend to reverse.",
            badge="Structure Engine",
        )

        section_header("Underlying Pivots (Previous RTH)")
        st.markdown(
            """
            <div class="spx-sub">
            Pick the structural <strong>high</strong> and <strong>low</strong> pivots from the prior
            regular-hours session on your <strong>line chart</strong>. These are the main turning points of that day,
            not necessarily the absolute wicks. Times can be any valid CT times from that session
            (for example: 09:30, 11:00, 14:30).
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
                key="high_pivot_price",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(11, 0),
                step=1800,
                key="high_pivot_time",
            )

        with c2:
            st.markdown("**Low Pivot**")
            low_price = st.number_input(
                "Low pivot price (prior RTH)",
                value=5100.0,
                step=0.25,
                key="low_pivot_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(13, 0),
                step=1800,
                key="low_pivot_time",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("⚡ Build Structural Channels", use_container_width=True, key="build_struct_channels"):
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
                st.success("Channels built for both ascending and descending scenarios.")

        df_asc = st.session_state["asc_channel_df"]
        df_desc = st.session_state["desc_channel_df"]
        h_asc = st.session_state["asc_height"]
        h_desc = st.session_state["desc_height"]

        if df_asc is None or df_desc is None:
            section_header("Structural Projections • RTH 08:30–14:30 CT")
            st.info("Build channels to see the rails and stacked rails grid.")
        else:
            section_header("Ascending Channel (Structure)")
            a1, a2 = st.columns([3, 1])
            with a1:
                st.dataframe(df_asc, use_container_width=True, hide_index=True, height=360)
            with a2:
                st.markdown(
                    metric_card(
                        "Ascending Height",
                        f"{h_asc:.2f} pts",
                        "Full swing from main bottom rail to main top rail.",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Descending Channel (Structure)")
            d1, d2 = st.columns([3, 1])
            with d1:
                st.dataframe(df_desc, use_container_width=True, hide_index=True, height=360)
            with d2:
                st.markdown(
                    metric_card(
                        "Descending Height",
                        f"{h_desc:.2f} pts",
                        "Full swing from main top rail to main bottom rail.",
                    ),
                    unsafe_allow_html=True,
                )

        end_card()

    # =========================
    # TAB 2 – DAILY FORESIGHT
    # =========================
    with tabs[1]:
        card(
            "Daily Foresight",
            "Take the rails, add stacked channels, apply simple filters, and let the "
            "structure tell you: trade it, scalp it, or stand aside.",
            badge="Foresight Engine",
        )

        df_asc = st.session_state["asc_channel_df"]
        df_desc = st.session_state["desc_channel_df"]
        h_asc = st.session_state["asc_height"]
        h_desc = st.session_state["desc_height"]

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("No structural channels built yet. Configure pivots in the Rails Setup tab first.")
            end_card()
        else:
            section_header("Structural Summary")

            # Suggest default primary scenario based on which height is larger
            default_primary_index = 0 if h_asc >= h_desc else 1
            primary_choice = st.radio(
                "Primary structural scenario for today",
                ["Ascending", "Descending"],
                index=default_primary_index,
                horizontal=True,
                key="primary_choice_radio",
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
                        "Primary Scenario",
                        primary_choice,
                        "You can still glance at the alternate, but this is your main map.",
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                asym_note = (
                    f"Alt height: {alt_height:.2f} pts. "
                    "Big imbalance means structure is skewed."
                )
                st.markdown(
                    metric_card(
                        "Primary Channel Height",
                        f"{primary_height:.2f} pts",
                        asym_note,
                    ),
                    unsafe_allow_html=True,
                )
            with c3:
                ratio_text = "—"
                note = "Requires both channels to be valid."
                if primary_height and alt_height and alt_height > 0 and primary_height > 0:
                    big = max(primary_height, alt_height)
                    small = min(primary_height, alt_height)
                    ratio = big / small
                    ratio_text = f"{ratio:.2f}×"
                    note = "Above 1.30× is a structural imbalance filter."
                st.markdown(
                    metric_card(
                        "Asymmetry (max/min)",
                        ratio_text,
                        note,
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Contract Size Projection")

            contract_move = primary_height * contract_factor
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(
                    metric_card(
                        "Contract Factor",
                        f"{contract_factor:.2f}",
                        "Approx contract move per 1 SPX point.",
                    ),
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    metric_card(
                        "Projected Contract Move",
                        f"{contract_move:.2f} units",
                        "Full swing from one rail to the opposite rail.",
                    ),
                    unsafe_allow_html=True,
                )
            with m3:
                threshold_ratio = contract_move / MIN_CONTRACT_MOVE if MIN_CONTRACT_MOVE > 0 else 0.0
                note = f"Threshold: {MIN_CONTRACT_MOVE:.1f} units. Below 1.0× is a caution flag."
                st.markdown(
                    metric_card(
                        "Size vs Threshold",
                        f"{threshold_ratio:.2f}×",
                        note,
                    ),
                    unsafe_allow_html=True,
                )

            # Classification
            section_header("Day-Type Classification")
            headline, explanation, flags = classify_day(
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

            # Timing guidance
            section_header("Timing Windows")

            st.markdown(
                """
                <div class="spx-sub">
                  <ul style="margin-left:18px;">
                    <li><strong>08:30–09:00 CT:</strong> treated as noise and trap zone. Avoid entries here.</li>
                    <li><strong>09:00–09:30 CT:</strong> only touch if everything else lines up and structure looks clean.</li>
                    <li><strong>10:00–12:00 CT:</strong> preferred hours for first clean rail touch and rejection.</li>
                    <li><strong>After 13:00 CT:</strong> good for secondary tests, take profits faster.</li>
                  </ul>
                  <em>Rule of thumb:</em> if your very first clean structural touch happens before 09:00, treat the whole day as suspect
                  unless you have a very strong reason to engage.
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Direction Bias Planner
            section_header("Direction Bias Planner")

            st.markdown(
                """
                <div class="spx-sub">
                  Plug in the opening or current SPX price to see how it sits inside today's primary channel.
                  This does not predict the exact path; it tells you whether your first instinct should be
                  to fade from the top, fade from the bottom, or wait.
                </div>
                """,
                unsafe_allow_html=True,
            )

            bias_col1, bias_col2 = st.columns(2)
            with bias_col1:
                open_price = st.number_input(
                    "SPX opening / current price (optional)",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    help="If you know the open or a key early price, enter it here to see where it sits in the channel.",
                    key="open_price_input",
                )
            with bias_col2:
                slot_options = list(primary_df["Time"])
                # default to 09:30 if present, else first row
                default_idx = 0
                if "09:30" in slot_options:
                    default_idx = slot_options.index("09:30")
                open_slot = st.selectbox(
                    "Time slot for that price",
                    options=slot_options,
                    index=default_idx,
                    key="open_slot_select",
                )

            if open_price > 0.0:
                row = primary_df[primary_df["Time"] == open_slot].iloc[0]
                main_top = row["Main Top"]
                main_bottom = row["Main Bottom"]
                stack_up_top = row["Stack+1 Top"]
                stack_down_bottom = row["Stack-1 Bottom"]

                pos_text = ""
                suggestion = ""
                banner_class_bias = "spx-banner-ok"
                icon_bias = "✅"

                if main_bottom < main_top:
                    if main_bottom <= open_price <= main_top:
                        pos = (open_price - main_bottom) / (main_top - main_bottom)
                        if primary_choice == "Ascending":
                            if pos <= 0.3:
                                pos_text = "near the lower rail inside the main channel."
                                suggestion = (
                                    "Bias: look for long calls on clean bounces from the lower rail "
                                    "in the 10:00–12:00 CT window."
                                )
                            elif pos >= 0.7:
                                pos_text = "near the upper rail inside the main channel."
                                suggestion = (
                                    "Bias: day may be extended early. Favour short-term long puts "
                                    "from upper rail rejections, but take profits quickly."
                                )
                            else:
                                pos_text = "near the mid-zone between rails."
                                suggestion = (
                                    "Bias: neutral. Be patient and wait for a clean touch of either rail "
                                    "instead of forcing trades in the middle."
                                )
                        else:  # Descending
                            if pos <= 0.3:
                                pos_text = "near the lower rail inside the main channel."
                                suggestion = (
                                    "Bias: in a descending primary day, price starting low often bounces upward first. "
                                    "You can fade that bounce with long puts near the upper rail, not down here."
                                )
                            elif pos >= 0.7:
                                pos_text = "near the upper rail inside the main channel."
                                suggestion = (
                                    "Bias: look for long puts from upper rail rejections. The structure supports "
                                    "top-to-bottom plays."
                                )
                            else:
                                pos_text = "near the mid-zone between rails."
                                suggestion = (
                                    "Bias: neutral. Let price pick a side and touch a rail before committing."
                                )
                    else:
                        # Outside the main channel: use stacks
                        if open_price > main_top:
                            if open_price <= stack_up_top:
                                pos_text = "above the main channel but inside the first stacked band."
                                suggestion = (
                                    "Treat this as an extension. Watch for reversal signals near the stacked top, "
                                    "then favour trades back toward the main channel."
                                )
                                banner_class_bias = "spx-banner-caution"
                                icon_bias = "⚠️"
                            else:
                                pos_text = "well above both the main and first stacked channel."
                                suggestion = (
                                    "This is stretched. Expect mean-reversion style behaviour rather than chasing up here. "
                                    "If you cannot frame the risk tightly, stand aside."
                                )
                                banner_class_bias = "spx-banner-stop"
                                icon_bias = "🛑"
                        elif open_price < main_bottom:
                            if open_price >= stack_down_bottom:
                                pos_text = "below the main channel but inside the first stacked band."
                                suggestion = (
                                    "Treat this as an extension. Watch for reversal behaviour near the stacked bottom, "
                                    "then favour trades back toward the main channel."
                                )
                                banner_class_bias = "spx-banner-caution"
                                icon_bias = "⚠️"
                            else:
                                pos_text = "well below both the main and first stacked channel."
                                suggestion = (
                                    "This is washed out. Chasing further in the same direction is dangerous. "
                                    "If you cannot define risk clearly, stand aside."
                                )
                                banner_class_bias = "spx-banner-stop"
                                icon_bias = "🛑"
                else:
                    pos_text = "not well-defined because top and bottom are equal."
                    suggestion = "Check your pivots; structure is not valid here."

                st.markdown(
                    f"""
                    <div class="{banner_class_bias}" style="margin-top:10px;">
                      <strong>{icon_bias} Position inside structure</strong><br>
                      At {open_slot} CT, a price of <strong>{open_price:.2f}</strong> sits {pos_text}<br>
                      {suggestion}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Contract Trade Estimator
            section_header("Contract Trade Estimator")

            st.markdown(
                """
                <div class="spx-sub">
                  This takes your <strong>primary channel height</strong> and your <strong>contract factor</strong>
                  and turns it into a projected contract move for a structural swing.
                  It does not guess the exact minute. It tells you whether the move is worth building a plan around.
                </div>
                """,
                unsafe_allow_html=True,
            )

            tcol1, tcol2, tcol3 = st.columns(3)
            with tcol1:
                trade_side = st.radio(
                    "Planned structural play",
                    ["Long Call (bottom → top)", "Long Put (top → bottom)"],
                    index=0,
                    horizontal=False,
                    key="trade_side_radio",
                )
            with tcol2:
                rail_fraction = st.slider(
                    "Fraction of channel you intend to capture",
                    min_value=0.50,
                    max_value=1.00,
                    value=1.00,
                    step=0.05,
                    help="1.00 = full rail-to-rail. 0.70 = partial move for more conservative exits.",
                    key="rail_fraction_slider",
                )
            with tcol3:
                entry_contract_price = st.number_input(
                    "Planned contract entry price",
                    min_value=0.01,
                    value=5.00,
                    step=0.05,
                    help="The option price you expect to pay when price tags your rail.",
                    key="entry_contract_price_input",
                )

            # Compute projected move
            if primary_height > 0 and entry_contract_price > 0:
                underlying_move = primary_height * rail_fraction
                contract_proj_move = underlying_move * contract_factor
                exit_price_proj = entry_contract_price + contract_proj_move
                roi_pct = (contract_proj_move / entry_contract_price) * 100.0

                ecol1, ecol2, ecol3 = st.columns(3)
                with ecol1:
                    st.markdown(
                        metric_card(
                            "Underlying move planned",
                            f"{underlying_move:.2f} pts",
                            f"{rail_fraction:.0%} of primary channel height.",
                        ),
                        unsafe_allow_html=True,
                    )
                with ecol2:
                    st.markdown(
                        metric_card(
                            "Projected contract move",
                            f"+{contract_proj_move:.2f}",
                            f"Threshold: {MIN_CONTRACT_MOVE:.1f}. Below that, day is not worth it.",
                        ),
                        unsafe_allow_html=True,
                    )
                with ecol3:
                    st.markdown(
                        metric_card(
                            "Projected exit price",
                            f"{exit_price_proj:.2f}",
                            f"Approx ROI: {roi_pct:.1f} percent on this structural swing.",
                        ),
                        unsafe_allow_html=True,
                    )

                # Alignment / caution text
                aligned = (
                    (primary_choice == "Ascending" and trade_side.startswith("Long Call"))
                    or (primary_choice == "Descending" and trade_side.startswith("Long Put"))
                )

                if aligned:
                    align_text = (
                        "This trade is aligned with the primary structure. "
                        "You are trading in the direction that the main channel prefers."
                    )
                else:
                    align_text = (
                        "This trade is counter to the primary structure. "
                        "These can work, but they must be treated as fast scalps around extremes."
                    )

                # Contract-based no-trade flag
                if contract_proj_move < MIN_CONTRACT_MOVE:
                    banner_class_trade = "spx-banner-stop"
                    icon_trade = "🛑"
                    extra = (
                        "Projected contract move is below the minimum you set for a meaningful day. "
                        "Respect this. If the structure and size both whisper 'small', you do not need to trade."
                    )
                else:
                    if headline == "STAND ASIDE":
                        banner_class_trade = "spx-banner-stop"
                        icon_trade = "🛑"
                        extra = (
                            "Your structural filters already classify today as a stand-aside day. "
                            "Even if the math looks tempting, listen to the full picture, not the single number."
                        )
                    elif headline == "LIGHT SIZE / SCALP ONLY":
                        banner_class_trade = "spx-banner-caution"
                        icon_trade = "⚠️"
                        extra = (
                            "The day is tagged as a scalp day. Size down, take partial profits quickly, "
                            "and avoid averaging down if it hesitates at the rail."
                        )
                    else:
                        banner_class_trade = "spx-banner-ok"
                        icon_trade = "✅"
                        extra = (
                            "Structure, size, and direction are in a reasonable alignment. "
                            "Your remaining job is execution: wait for the clean touch, respect timing, "
                            "and exit when the structural move is paid."
                        )

                st.markdown(
                    f"""
                    <div class="{banner_class_trade}" style="margin-top:10px;">
                      <strong>{icon_trade} Trade context</strong><br>
                      {align_text}<br>
                      {extra}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Time-aligned map
            section_header("Time-Aligned Map (Primary Scenario)")

            st.caption(
                "Each row is a 30-minute RTH slot. Main rails show your inside-channel plays; "
                "Stack±1 rails show where extensions often reverse."
            )
            st.dataframe(primary_df, use_container_width=True, hide_index=True, height=420)

            st.markdown(
                """
                <div class="spx-sub" style="margin-top:10px;">
                  <strong>Reading it:</strong> you are not trying to guess which exact time will tag the rail.
                  You are asking: <em>if</em> price is near one of these rails in a healthy timing window,
                  how big is the structural move available to the opposite rail and how does that align with your contract factor.
                </div>
                """,
                unsafe_allow_html=True,
            )

        end_card()

    # ======================
    # TAB 3 – ABOUT
    # ======================
    with tabs[2]:
        card("About SPX Prophet", TAGLINE, badge="Structure-Only Edition")

        st.markdown(
            """
            <div class="spx-sub" style="font-size:0.98rem; line-height:1.8;">
              <p><strong>Design philosophy:</strong> keep the map simple, structural, and repeatable.</p>

              <ul style="margin-left:20px;">
                <li><strong>Two prior RTH pivots</strong> define the channel for the new day.</li>
                <li><strong>Constant slope</strong> of 0.475 points per 30 minutes carries that structure forward.</li>
                <li><strong>Both ascending and descending</strong> versions are built from the same pivots.</li>
                <li><strong>Stacked channels (±1 height)</strong> frame extension and snap-back behaviour.</li>
                <li><strong>Contract factor</strong> (default 0.33) turns SPX structure into an options move estimate.</li>
                <li><strong>Filters</strong> (channel width, asymmetry, contract move) tell you when to treat the day as a scalp day or a full stand-aside day.</li>
                <li><strong>Bias planner and trade estimator</strong> turn the map into a daily plan without pretending to be an oracle.</li>
              </ul>

              <p>The app does not guess volatility, skew, or news. It does one job:
              give you a clean, repeatable structural context so that you are not chasing candles in the dark.
              Your edge comes from <em>waiting</em> for the right touch, in the right zone, with the right structure.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="spx-sub" style="margin-top:14px;">
              <strong>Practical checklist before any trade:</strong>
              <ul style="margin-left:20px;">
                <li>Is today classified as <em>Normal</em>, <em>Scalp Only</em>, or <em>Stand Aside</em>?</li>
                <li>Is the touch happening near a main rail or a stacked rail?</li>
                <li>Is the time window at least 09:00 CT, preferably 10:00–12:00 CT?</li>
                <li>Is the projected contract move big enough to justify the risk?</li>
                <li>Is your planned trade aligned with the primary structure or fighting it?</li>
              </ul>
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