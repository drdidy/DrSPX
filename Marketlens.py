# marketlens_legendary.py
# SPX Prophet — Where Structure Becomes Foresight.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Optional, Tuple, List, Dict

# ========= CORE CONSTANTS =========

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475  # underlying rails slope per 30 min
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 CT reference


# ========= UI / THEME =========

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.05), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.05), transparent 60%),
          radial-gradient(circle 1200px at 50% 50%, rgba(148, 163, 184, 0.12), transparent),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 30%, #f1f5f9 60%, #f8fafc 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 4rem;
        max-width: 1400px;
    }

    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.06), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 2px solid rgba(148, 163, 184, 0.35);
        box-shadow:
            8px 0 32px rgba(148, 163, 184, 0.18),
            4px 0 16px rgba(15, 23, 42, 0.05);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.9rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #6366f1 40%, #0ea5e9 80%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.04em;
        margin-bottom: 0.3rem;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.7) 20%,
            rgba(148, 163, 184, 0.7) 80%,
            transparent 100%);
    }

    [data-testid="stSidebar"] h4 {
        color: #475569;
        font-size: 0.9rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-top: 1.3rem;
        margin-bottom: 0.5rem;
    }

    /* HERO */
    .hero-header {
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.10), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(56, 189, 248, 0.10), transparent 60%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 28px;
        padding: 32px 28px 30px 28px;
        margin-bottom: 32px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 18px 40px rgba(15, 23, 42, 0.08),
            0 0 0 1px rgba(255, 255, 255, 0.8);
        text-align: center;
        overflow: hidden;
    }

    .hero-header::before {
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(circle at 0 0, rgba(129, 140, 248, 0.18), transparent 60%);
        opacity: 0.7;
        pointer-events: none;
    }

    .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        background: rgba(22, 163, 74, 0.06);
        border: 1px solid rgba(22, 163, 74, 0.4);
        font-size: 0.8rem;
        font-weight: 600;
        color: #15803d;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .hero-pill-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 8px rgba(34, 197, 94, 0.7);
        animation: dotPulse 1.8s ease-in-out infinite;
    }

    @keyframes dotPulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(0.8); opacity: 0.8; }
    }

    .hero-title {
        position: relative;
        font-size: 2.8rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #0f172a 30%, #6366f1 70%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.06em;
        margin: 0.2rem 0 0.4rem 0;
    }

    .hero-subtitle {
        position: relative;
        font-size: 1.0rem;
        color: #64748b;
        max-width: 520px;
        margin: 0 auto;
    }

    /* CARDS */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 10% 0%, rgba(129, 140, 248, 0.10), transparent 55%),
            radial-gradient(circle at 100% 100%, rgba(56, 189, 248, 0.12), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 24px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 18px 40px rgba(15, 23, 42, 0.06),
            0 0 0 1px rgba(255, 255, 255, 0.8);
        padding: 28px 26px 24px 26px;
        margin-bottom: 24px;
        overflow: hidden;
    }

    .spx-card h4 {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        color: #0f172a;
        margin-bottom: 6px;
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        border: 1px solid rgba(99, 102, 241, 0.3);
        background: rgba(248, 250, 252, 0.8);
        font-size: 0.75rem;
        font-weight: 600;
        color: #4f46e5;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }

    .icon-large {
        font-size: 2.4rem;
        margin-bottom: 6px;
    }

    .spx-sub {
        color: #64748b;
        font-size: 0.98rem;
        line-height: 1.7;
    }

    .section-header {
        font-size: 1.3rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        color: #0f172a;
        margin: 1.8rem 0 0.8rem 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .section-header::before {
        content: '';
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        box-shadow: 0 0 10px rgba(79, 70, 229, 0.7);
    }

    .spx-metric {
        padding: 18px 18px 14px 18px;
        border-radius: 18px;
        background:
            linear-gradient(135deg, #ffffff, #f9fafb);
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow: 0 12px 24px rgba(15, 23, 42, 0.05);
    }

    .spx-metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #94a3b8;
        font-weight: 700;
        margin-bottom: 6px;
    }

    .spx-metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #0f172a;
    }

    .muted {
        color: #64748b;
        font-size: 0.94rem;
        line-height: 1.7;
        padding: 14px 16px;
        background: #f8fafc;
        border-left: 3px solid #6366f1;
        border-radius: 10px;
        margin: 10px 0 4px 0;
    }

    .decision-banner {
        padding: 16px 18px;
        border-radius: 16px;
        font-size: 0.96rem;
        font-weight: 600;
        margin-bottom: 10px;
    }

    .decision-good {
        background: rgba(34, 197, 94, 0.08);
        border: 1px solid rgba(34, 197, 94, 0.5);
        color: #166534;
    }

    .decision-warning {
        background: rgba(234, 179, 8, 0.08);
        border: 1px solid rgba(234, 179, 8, 0.5);
        color: #854d0e;
    }

    .decision-bad {
        background: rgba(248, 113, 113, 0.10);
        border: 1px solid rgba(248, 113, 113, 0.6);
        color: #b91c1c;
    }

    .spx-decision-title {
        font-weight: 800;
        margin-bottom: 4px;
    }

    .spx-decision-body {
        font-weight: 500;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: #e5e7eb33;
        padding: 4px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.7);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        padding: 6px 16px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #4b5563;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #ffffff;
        color: #111827;
        box-shadow: 0 6px 14px rgba(15, 23, 42, 0.12);
    }

    .stButton>button {
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 10px 22px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        box-shadow: 0 10px 22px rgba(79, 70, 229, 0.35);
        cursor: pointer;
    }

    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 12px 26px rgba(79, 70, 229, 0.4);
    }

    .stDataFrame {
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 16px 32px rgba(15, 23, 42, 0.06);
        border: 1px solid rgba(148, 163, 184, 0.7);
    }

    .app-footer {
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(148, 163, 184, 0.6);
        text-align: center;
        color: #94a3b8;
        font-size: 0.9rem;
    }

    label {
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        color: #4b5563 !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown(
        f"""
        <div class="hero-header">
            <div class="hero-pill">
                <div class="hero-pill-dot"></div>
                SYSTEM ACTIVE
            </div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">
                {TAGLINE}<br/>
                Two pivots define your rails. Stacked channels frame your risk. Contracts follow the structure, not your emotions.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None, icon: str = ""):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if icon:
        st.markdown(f"<div class='icon-large'>{icon}</div>", unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def metric_html(label: str, value: str) -> str:
    return f"""
    <div class="spx-metric">
        <div class="spx-metric-label">{label}</div>
        <div class="spx-metric-value">{value}</div>
    </div>
    """


def section_header(text: str):
    st.markdown(f"<h3 class='section-header'>{text}</h3>", unsafe_allow_html=True)


# ========= TIME HELPERS =========

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map a clock time (CT) to a BASE_DATE-relative datetime.
    If hour >= 15, treat as 'previous day evening'. Else next day.
    """
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


# ========= RAILS / CHANNELS =========

def build_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
) -> Tuple[pd.DataFrame, float]:
    """
    Build ascending or descending rails using fixed slope magnitude and 2 pivots.
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
                "Top Rail": round(top, 2),
                "Bottom Rail": round(bottom, 2),
            }
        )

    df = pd.DataFrame(rows)
    return df, round(channel_height, 2)


def build_stacked_from_channel(df: pd.DataFrame, height: float) -> pd.DataFrame:
    """
    Given a base channel df (Time, Top Rail, Bottom Rail) and channel height,
    build +1 and -1 stacked rails.
    """
    df = df.copy()
    df["Top +1"] = df["Top Rail"] + height
    df["Bottom +1"] = df["Bottom Rail"] + height
    df["Top -1"] = df["Top Rail"] - height
    df["Bottom -1"] = df["Bottom Rail"] - height
    return df


# ========= CONTRACT LINE =========

def build_contract_projection_from_anchors(
    anchor_a_time: dtime,
    anchor_a_price: float,
    anchor_b_time: dtime,
    anchor_b_price: float,
) -> Tuple[pd.DataFrame, float]:
    """
    Use 2 contract anchors on the same BASE_DATE-relative grid to fit a straight line.
    Returns df(Time, Contract Price) and slope per 30m.
    """
    dt_a = align_30min(make_dt_from_time(anchor_a_time))
    dt_b = align_30min(make_dt_from_time(anchor_b_time))

    k_a = blocks_from_base(dt_a)
    k_b = blocks_from_base(dt_b)

    if k_a == k_b:
        slope = 0.0
    else:
        slope = (anchor_b_price - anchor_a_price) / (k_b - k_a)

    b = anchor_a_price - slope * k_a

    rows = []
    for dt in rth_slots():
        k = blocks_from_base(dt)
        price = slope * k + b
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Contract Price": round(price, 2),
            }
        )

    df = pd.DataFrame(rows)
    return df, round(slope, 4)


def build_contract_projection_from_factor(
    base_contract_price: float,
    reference_time: dtime,
    contract_factor: float,
    underlying_slope_sign: int,
    channel_height: Optional[float] = None,
) -> Tuple[pd.DataFrame, float]:
    """
    Simpler model:
    - Use SPX slope sign (+/- 0.475)
    - Convert to a contract slope via factor (e.g. 0.30 of SPX move per channel)
    - Normalize roughly so that across one 'channel-height' move, contract changes ~factor*channel_height.
      If channel_height is not provided, just scale directly with slope.
    """
    dt_ref = align_30min(make_dt_from_time(reference_time))
    k_ref = blocks_from_base(dt_ref)

    spx_slope = underlying_slope_sign * SLOPE_MAG
    if channel_height is not None and channel_height != 0:
        # contract change for full channel move = factor * channel_height
        blocks_for_channel = channel_height / abs(spx_slope) if spx_slope != 0 else 0
        slope = (contract_factor * channel_height / blocks_for_channel) if blocks_for_channel != 0 else 0.0
    else:
        # fallback: proportional to SPX slope
        slope = contract_factor * spx_slope

    b = base_contract_price - slope * k_ref

    rows = []
    for dt in rth_slots():
        k = blocks_from_base(dt)
        price = slope * k + b
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Contract Price": round(price, 2),
            }
        )
    df = pd.DataFrame(rows)
    return df, round(slope, 4)


# ========= PRIMARY / ALT SCENARIO =========

def choose_primary_scenario_from_pivots(
    high_time: dtime,
    low_time: dtime,
) -> str:
    """
    Simple, transparent rule:
    - If low happens first then high -> net up move -> Ascending primary.
    - If high happens first then low -> net down move -> Descending primary.
    """
    if high_time > low_time:
        return "Ascending"
    elif high_time < low_time:
        return "Descending"
    else:
        # Same time -> default to Ascending
        return "Ascending"


# ========= CHOP DETECTION =========

def compute_chop_score(
    channel_height: float,
    rails_df: pd.DataFrame,
    open_price_830: Optional[float],
    em_value: Optional[float],
    em_bias: str,
    contract_factor: Optional[float],
    primary_slope_sign: int,
) -> Tuple[int, List[str], str]:
    """
    Multi-factor CHOP engine.
    Only uses what we have (no external feeds).
    Returns (score, reasons, decision_class).
    """
    score = 0
    reasons: List[str] = []

    # 1) Micro-channel width
    if channel_height < 40:
        score += 1
        reasons.append("Channel height < 40 pts (compressed structure).")

    # 2) 8:30 position
    if open_price_830 is not None:
        row_830 = rails_df[rails_df["Time"] == "08:30"]
        if not row_830.empty:
            bottom_830 = float(row_830.iloc[0]["Bottom Rail"])
            top_830 = float(row_830.iloc[0]["Top Rail"])
            if channel_height > 0:
                pos = (open_price_830 - bottom_830) / channel_height  # 0=bottom,1=top
                if 0.4 <= pos <= 0.6:
                    score += 1
                    reasons.append("8:30 open sits in the middle of the channel (no edge).")

    # 3) EM vs channel
    if em_value is not None and channel_height > 0:
        if em_value < 0.5 * channel_height:
            score += 1
            reasons.append("Expected move < 50% of channel height (tight expansion).")

    # 4) Contract factor
    if contract_factor is not None:
        if contract_factor < 0.18:
            score += 1
            reasons.append("Contract factor < 0.18 (weak option responsiveness).")

    # 5) Slope disagreement between EM bias and structure
    if em_value is not None and em_value > 0:
        if em_bias == "Up" and primary_slope_sign < 0:
            score += 1
            reasons.append("EM bias up, structural primary descending (compression).")
        elif em_bias == "Down" and primary_slope_sign > 0:
            score += 1
            reasons.append("EM bias down, structural primary ascending (compression).")

    # Decision band
    if score >= 4:
        decision_class = "stand_aside"
    elif score >= 2:
        decision_class = "high_risk"
    else:
        decision_class = "normal"

    return score, reasons, decision_class


# ========= DAILY DIRECTIONAL SUGGESTION =========

def suggest_direction(
    primary_mode: str,
    rails_df: pd.DataFrame,
    open_price_830: Optional[float],
    proximity_threshold: float,
) -> Tuple[str, str]:
    """
    Suggest calls / puts / neutral based on 8:30 location vs rails.
    Returns (direction_label, explanation).
    """
    if open_price_830 is None:
        return "Neutral", "No 8:30 open provided. Treat day as structural only; wait for clear tests of rails."

    row_830 = rails_df[rails_df["Time"] == "08:30"]
    if row_830.empty:
        return "Neutral", "Rails for 08:30 are missing. Use the map visually to decide."

    bottom_830 = float(row_830.iloc[0]["Bottom Rail"])
    top_830 = float(row_830.iloc[0]["Top Rail"])

    dist_to_lower = open_price_830 - bottom_830
    dist_to_upper = top_830 - open_price_830

    # inside channel
    if bottom_830 <= open_price_830 <= top_830:
        # nearer to lower rail
        if dist_to_lower <= dist_to_upper and dist_to_lower <= proximity_threshold:
            if primary_mode == "Ascending":
                return "Calls", "8:30 is sitting near the lower rail of an ascending primary channel. Buy-the-dip calls toward mid/upper rail have the edge."
            else:
                return "Neutral", "8:30 is near the lower rail but primary structure is descending. Safer to wait for cleaner confirmation before calls."
        # nearer to upper rail
        if dist_to_upper < dist_to_lower and dist_to_upper <= proximity_threshold:
            if primary_mode == "Descending":
                return "Puts", "8:30 is sitting near the upper rail of a descending primary channel. Fading with puts toward mid/lower rail has the edge."
            else:
                return "Neutral", "8:30 is near the upper rail but primary structure is ascending. Wait for breakout and retest before leaning into puts."

        return "Neutral", "8:30 is not close enough to either rail. Wait for price to approach a rail or stacked rail before taking a directional stance."

    # above upper rail
    if open_price_830 > top_830:
        return "Puts", "8:30 opened above the upper rail (over-extension). Look for failure/rejection patterns for put entries back toward the channel or stacked rails."

    # below lower rail
    if open_price_830 < bottom_830:
        return "Calls", "8:30 opened below the lower rail (flush). Look for exhaustion / reclaim patterns for call entries back toward the channel or stacked rails."

    return "Neutral", "No clear structural bias at 8:30."


# ========= MAIN APP =========

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
        st.markdown(
            f"<div class='spx-sub' style='font-size:0.96rem;'>{TAGLINE}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG:.3f} pts / 30m**")
        st.caption("Underlying channels are projected on a 30-minute grid.")

        st.markdown("#### Notes")
        st.caption(
            "• Underlying maintenance: 16:00–17:00 CT\n"
            "• Contracts maintenance: 16:00–19:00 CT\n"
            "• RTH grid: 08:30–14:30 CT (30m blocks)\n"
            "• You choose pivots. The app carries the structure."
        )

    # HEADER
    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "📐 Contract Line Setup",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # ===== TAB 1: RAILS SETUP =====
    with tabs[0]:
        card(
            "Structure Engine",
            "Define your two key pivots from the prior RTH session, build both ascending and descending rails, and stack them to see where reversals are likely.",
            badge="Rails + Stacks",
            icon="🧱",
        )

        section_header("Underlying Pivots (Previous RTH)")
        st.markdown(
            """
            <div class="spx-sub">
            Pick the **structural high and low pivots** from the previous regular session on your line chart.
            These do not have to be the absolute wick extremes, but the main turning points that define the day.
            Times can be any valid CT times from the previous session (e.g. 09:30, 11:00, 14:30).
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**High Pivot**")
            high_price = st.number_input(
                "High pivot price",
                value=6700.0,
                step=0.25,
                key="high_pivot_price",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(13, 0),
                step=1800,
                key="high_pivot_time",
            )

        with c2:
            st.markdown("**Low Pivot**")
            low_price = st.number_input(
                "Low pivot price",
                value=6600.0,
                step=0.25,
                key="low_pivot_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(10, 30),
                step=1800,
                key="low_pivot_time",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        build_btn_col = st.columns([1, 3])[0]
        with build_btn_col:
            if st.button("Build Rails and Stacks", key="build_rails"):
                # Build both ascending and descending
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

                st.session_state["rails_asc_df"] = df_asc
                st.session_state["rails_desc_df"] = df_desc
                st.session_state["rails_asc_height"] = h_asc
                st.session_state["rails_desc_height"] = h_desc
                st.session_state["primary_mode"] = choose_primary_scenario_from_pivots(
                    high_time, low_time
                )
                st.success("Rails generated. Check both views and then go to Daily Foresight.")

        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_height")
        h_desc = st.session_state.get("rails_desc_height")
        primary_mode = st.session_state.get("primary_mode", "Ascending")

        if df_asc is None or df_desc is None:
            st.info("Build rails to see the structural and stacked projections.")
            end_card()
        else:
            section_header("Ascending Channel (Structure)")
            c_top = st.columns([3, 1])
            with c_top[0]:
                st.dataframe(df_asc, use_container_width=True, hide_index=True, height=320)
            with c_top[1]:
                st.markdown(metric_html("Channel Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "Download Ascending Rails CSV",
                    df_asc.to_csv(index=False).encode(),
                    "spx_ascending_rails.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            section_header("Descending Channel (Structure)")
            c_bot = st.columns([3, 1])
            with c_bot[0]:
                st.dataframe(df_desc, use_container_width=True, hide_index=True, height=320)
            with c_bot[1]:
                st.markdown(metric_html("Channel Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "Download Descending Rails CSV",
                    df_desc.to_csv(index=False).encode(),
                    "spx_descending_rails.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            section_header("Stacked Channels (±1 Height)")
            st.markdown(
                """
                <div class="spx-sub">
                When price escapes the main channel, a common behavior is to travel toward the next stacked rail
                (one full channel-height above or below) and reverse there. This gives you the map for those extension plays.
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Show stacked for primary scenario only (to avoid clutter)
            primary_choice = st.selectbox(
                "Primary structural scenario",
                ["Ascending", "Descending"],
                index=0 if primary_mode == "Ascending" else 1,
                key="primary_choice",
                help="This scenario will be used as the default for Daily Foresight and chop detection.",
            )

            if primary_choice == "Ascending":
                base_df = df_asc
                base_h = h_asc
            else:
                base_df = df_desc
                base_h = h_desc

            stacked_df = build_stacked_from_channel(base_df, base_h)
            st.dataframe(stacked_df, use_container_width=True, hide_index=True, height=320)

            st.session_state["primary_choice"] = primary_choice
            st.session_state["stacked_df_primary"] = stacked_df
            st.session_state["primary_channel_height"] = base_h

            end_card()

    # ===== TAB 2: CONTRACT LINE =====
    with tabs[1]:
        card(
            "Contract Line Setup",
            "Map your option contract to the same time grid using either two real anchors or a factor of the SPX move.",
            badge="Contract Engine",
            icon="📐",
        )

        df_primary_stack = st.session_state.get("stacked_df_primary")
        primary_choice = st.session_state.get("primary_choice", "Ascending")
        primary_height = st.session_state.get("primary_channel_height")

        if df_primary_stack is None or primary_height is None:
            st.warning("Build rails and stacks first in the Rails Setup tab.")
            end_card()
        else:
            section_header("Slope Source")
            slope_mode = st.radio(
                "How should the contract line slope be determined?",
                [
                    "Use two contract anchors (recommended)",
                    "Use contract factor × SPX structural slope",
                ],
                index=0,
                horizontal=False,
                key="contract_slope_mode",
            )

            contract_df = None
            contract_slope = None

            if slope_mode == "Use two contract anchors (recommended)":
                section_header("Contract Anchors")
                st.markdown(
                    """
                    <div class="spx-sub">
                    Use two observed prices for the same contract (e.g. 6850c) on the same session:
                    one earlier and one later in the overnight/RTH window.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns(2)
                with c1:
                    anchor_a_time = st.time_input(
                        "Anchor A time (CT)",
                        value=dtime(15, 0),
                        step=1800,
                        key="contract_anchor_a_time",
                    )
                    anchor_a_price = st.number_input(
                        "Contract price at Anchor A",
                        value=10.0,
                        step=0.1,
                        key="contract_anchor_a_price",
                    )
                with c2:
                    anchor_b_time = st.time_input(
                        "Anchor B time (CT)",
                        value=dtime(22, 30),
                        step=1800,
                        key="contract_anchor_b_time",
                    )
                    anchor_b_price = st.number_input(
                        "Contract price at Anchor B",
                        value=7.0,
                        step=0.1,
                        key="contract_anchor_b_price",
                    )

                build_contract_btn = st.button(
                    "Build Contract Line from Anchors",
                    key="build_contract_anchors",
                )
                if build_contract_btn:
                    contract_df, contract_slope = build_contract_projection_from_anchors(
                        anchor_a_time=anchor_a_time,
                        anchor_a_price=anchor_a_price,
                        anchor_b_time=anchor_b_time,
                        anchor_b_price=anchor_b_price,
                    )
                    st.session_state["contract_df"] = contract_df
                    st.session_state["contract_slope"] = contract_slope
                    st.success("Contract projection built from anchors.")

            else:
                section_header("Contract Factor Mode")
                st.markdown(
                    """
                    <div class="spx-sub">
                    Here the contract changes roughly as a fixed fraction of the SPX channel move.
                    For example, factor = 0.30 means a full channel swing in SPX maps to about 30% of that in the contract.
                    You still need one observed contract price and its time to anchor the line.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c1, c2 = st.columns(2)
                with c1:
                    contract_factor = st.number_input(
                        "Contract factor (fraction of SPX move)",
                        value=0.30,
                        step=0.01,
                        min_value=0.0,
                        max_value=5.0,
                        key="contract_factor_input",
                    )
                    st.session_state["contract_factor"] = contract_factor
                with c2:
                    ref_time = st.time_input(
                        "Reference time for observed contract price",
                        value=dtime(8, 30),
                        step=1800,
                        key="contract_factor_ref_time",
                    )
                    ref_price = st.number_input(
                        "Contract price at reference time",
                        value=5.0,
                        step=0.1,
                        key="contract_factor_ref_price",
                    )

                build_contract_btn = st.button(
                    "Build Contract Line from Factor",
                    key="build_contract_factor",
                )

                if build_contract_btn:
                    underlying_slope_sign = +1 if primary_choice == "Ascending" else -1
                    contract_df, contract_slope = build_contract_projection_from_factor(
                        base_contract_price=ref_price,
                        reference_time=ref_time,
                        contract_factor=contract_factor,
                        underlying_slope_sign=underlying_slope_sign,
                        channel_height=primary_height,
                    )
                    st.session_state["contract_df"] = contract_df
                    st.session_state["contract_slope"] = contract_slope
                    st.success("Contract projection built from factor mode.")

            contract_df = st.session_state.get("contract_df")
            contract_slope = st.session_state.get("contract_slope")

            if contract_df is not None:
                section_header("Contract Projection • RTH 08:30–14:30 CT")
                c_top = st.columns([3, 1])
                with c_top[0]:
                    st.dataframe(contract_df, use_container_width=True, hide_index=True, height=320)
                with c_top[1]:
                    st.markdown(
                        metric_html("Contract Slope", f"{contract_slope:+.4f} per 30m"),
                        unsafe_allow_html=True,
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "Download Contract CSV",
                        contract_df.to_csv(index=False).encode(),
                        "contract_projection.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

            end_card()

    # ===== TAB 3: DAILY FORESIGHT =====
    with tabs[2]:
        card(
            "Daily Foresight",
            "Combine rails, stacks, and contract line into a simple decision card: trade, bias, and map.",
            badge="Foresight + Chop Engine",
            icon="🔮",
        )

        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_height")
        h_desc = st.session_state.get("rails_desc_height")
        stacked_df_primary = st.session_state.get("stacked_df_primary")
        primary_choice = st.session_state.get("primary_choice", "Ascending")
        primary_height = st.session_state.get("primary_channel_height")
        contract_df = st.session_state.get("contract_df")
        stored_contract_factor = st.session_state.get("contract_factor", None)

        if (
            df_asc is None
            or df_desc is None
            or stacked_df_primary is None
            or primary_height is None
        ):
            st.warning("You need to build rails and stacks first in the Rails Setup tab.")
            end_card()
        else:
            section_header("Session Inputs (Today)")
            c1, c2, c3 = st.columns(3)
            with c1:
                open_830 = st.number_input(
                    "SPX 08:30 open (today)",
                    value=6675.0,
                    step=0.5,
                    key="open_830_today",
                )
            with c2:
                em_value = st.number_input(
                    "Daily expected move (points, optional)",
                    value=80.0,
                    step=0.5,
                    key="em_value_today",
                )
                if em_value <= 0:
                    em_value = None
            with c3:
                em_bias = st.selectbox(
                    "Expected move bias",
                    ["Neutral", "Up", "Down"],
                    index=0,
                    key="em_bias_today",
                    help="If EM skew is clearly to one side, select it; otherwise leave Neutral.",
                )

            c4, c5 = st.columns(2)
            with c4:
                proximity_threshold = st.number_input(
                    "Rail proximity threshold (pts)",
                    value=6.0,
                    step=0.5,
                    key="proximity_threshold",
                    help="How close 8:30 must be to a rail to treat it as 'near' that rail.",
                )
            with c5:
                contract_factor = st.number_input(
                    "Contract factor for chop check (optional)",
                    value=float(stored_contract_factor) if stored_contract_factor is not None else 0.30,
                    step=0.01,
                    key="contract_factor_chop",
                )
                if contract_factor <= 0:
                    contract_factor = None

            # Choose which scenario to treat as primary in Foresight
            section_header("Scenario for Foresight")
            foresight_mode = st.selectbox(
                "Active structural scenario",
                ["Ascending", "Descending"],
                index=0 if primary_choice == "Ascending" else 1,
                key="foresight_mode",
            )
            if foresight_mode == "Ascending":
                rails_df = df_asc
                ch_height = h_asc
                primary_slope_sign = +1
            else:
                rails_df = df_desc
                ch_height = h_desc
                primary_slope_sign = -1

            # CHOP DETECTION
            if ch_height is None:
                st.warning("Channel height missing; rebuild rails.")
                end_card()
            else:
                chop_score, chop_reasons, decision_class = compute_chop_score(
                    channel_height=ch_height,
                    rails_df=rails_df,
                    open_price_830=open_830,
                    em_value=em_value,
                    em_bias=em_bias,
                    contract_factor=contract_factor,
                    primary_slope_sign=primary_slope_sign,
                )

                section_header("Chop Detection")
                if decision_class == "stand_aside":
                    st.markdown(
                        f"""
                        <div class="decision-banner decision-bad">
                            <div class="spx-decision-title">❌ CHOP DAY – STAND ASIDE</div>
                            <div class="spx-decision-body">
                                Chop score: <strong>{chop_score}</strong>. Too many compression signals.
                                Preserve capital and wait for a cleaner day.
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif decision_class == "high_risk":
                    st.markdown(
                        f"""
                        <div class="decision-banner decision-warning">
                            <div class="spx-decision-title">⚠ HIGH-RISK STRUCTURE</div>
                            <div class="spx-decision-body">
                                Chop score: <strong>{chop_score}</strong>. Trade light, focus only on extreme rail or stacked touches with clear rejection/confirmation.
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"""
                        <div class="decision-banner decision-good">
                            <div class="spx-decision-title">✅ STRUCTURE OK TO TRADE</div>
                            <div class="spx-decision-body">
                                Chop score: <strong>{chop_score}</strong>. Structure is supportive of directional plays if your entries are disciplined.
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if chop_reasons:
                    st.markdown(
                        "<div class='muted'><strong>Chop diagnostics:</strong><br/>"
                        + "<br/>".join(f"• {r}" for r in chop_reasons)
                        + "</div>",
                        unsafe_allow_html=True,
                    )

                # Direction suggestion (only meaningful if not stand aside)
                section_header("Directional Bias at 08:30")
                direction_label, direction_expl = suggest_direction(
                    primary_mode=foresight_mode,
                    rails_df=rails_df,
                    open_price_830=open_830,
                    proximity_threshold=proximity_threshold,
                )
                st.markdown(
                    f"""
                    <div class="muted">
                        <strong>Bias:</strong> {direction_label}<br/>{direction_expl}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Time-Aligned Map
                section_header("Time-Aligned Map (Rails, Stacks, Contract)")
                if contract_df is not None:
                    merged = stacked_df_primary.merge(contract_df, on="Time", how="left")
                else:
                    merged = stacked_df_primary.copy()
                    merged["Contract Price"] = None

                st.caption(
                    "Every row is a 30-minute RTH slot. Use this as a panoramic map of rails, stacked rails, and your contract line."
                )
                st.dataframe(merged, use_container_width=True, hide_index=True, height=420)

                st.markdown(
                    """
                    <div class="muted">
                    <strong>How to read this:</strong><br/>
                    • Rails show where SPX structure expects reversals or continuation zones.<br/>
                    • Stacked rails (+1 / -1) are extension targets once price escapes the main channel.<br/>
                    • If you calibrated the contract line, the Contract Price column is the structural value if the touch happens at that time.<br/>
                    Use this to pre-plan entries/exits instead of reacting candle by candle.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                end_card()

    # ===== TAB 4: ABOUT =====
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Legendary Structure Map", icon="ℹ️")
        st.markdown(
            """
            <div class="spx-sub">
            <p><strong>What this app does:</strong></p>
            <ul>
                <li>Takes <strong>your chosen pivots</strong> from the previous RTH session.</li>
                <li>Builds <strong>ascending and descending rails</strong> with a fixed slope of 0.475 pts / 30m.</li>
                <li>Stacks extra channels above and below to frame extension and reversal zones.</li>
                <li>Lets you map an <strong>option contract</strong> onto the same time grid, either from two anchors or a factor of SPX move.</li>
                <li>Runs a <strong>chop detection engine</strong> to tell you when to trade, when to size down, and when to simply stand aside.</li>
            </ul>

            <p>Your edge is not predicting every tick. Your edge is having a clear, repeatable structure, 
            and only playing when structure, time, and options all agree.</p>
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