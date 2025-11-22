import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

# =========================================
# CORE CONSTANTS
# =========================================

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."

# Underlying rail slope (points per 30-minute block)
SLOPE_MAG = 0.475

# Default contract factor (option move as fraction of SPX move)
DEFAULT_CONTRACT_FACTOR = 0.30

# Base date used to build a consistent time grid
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 = previous session reference


# =========================================
# STUNNING LIGHT UI (MATURE, ELEGANT)
# =========================================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1400px 900px at 15% 0%, rgba(79, 70, 229, 0.06), transparent 60%),
          radial-gradient(ellipse 1600px 1000px at 85% 100%, rgba(59, 130, 246, 0.06), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 40%, #e5e7eb 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 2.5rem;
        max-width: 1380px;
    }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 30% 0%, rgba(79, 70, 229, 0.08), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            8px 0 32px rgba(148, 163, 184, 0.25);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #111827 0%, #4f46e5 50%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.2rem;
        letter-spacing: -0.05em;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.3rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.7) 20%,
            rgba(148, 163, 184, 0.9) 50%,
            rgba(148, 163, 184, 0.7) 80%,
            transparent 100%);
    }

    /* HERO */
    .hero-wrapper {
        display: flex;
        justify-content: center;
        margin-bottom: 2.2rem;
    }

    .hero-header {
        position: relative;
        max-width: 880px;
        width: 100%;
        background:
            radial-gradient(circle at 0% 0%, rgba(79, 70, 229, 0.08), transparent 55%),
            radial-gradient(circle at 100% 100%, rgba(59, 130, 246, 0.08), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 32px;
        padding: 26px 34px 24px;
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow:
            0 24px 60px rgba(148, 163, 184, 0.6),
            0 10px 24px rgba(15, 23, 42, 0.18);
        overflow: hidden;
        text-align: center;
        backdrop-filter: blur(12px);
        animation: heroFloat 14s ease-in-out infinite;
    }

    @keyframes heroFloat {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-3px); }
    }

    .hero-inner {
        position: relative;
        z-index: 1;
    }

    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 6px 16px;
        border-radius: 999px;
        background:
            linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(5, 150, 105, 0.1)),
            #ffffff;
        border: 1px solid rgba(16, 185, 129, 0.6);
        font-size: 0.75rem;
        font-weight: 700;
        color: #047857;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 8px;
    }

    .hero-dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 14px rgba(34, 197, 94, 0.9);
        animation: dotPulse 1.8s ease-in-out infinite;
    }

    @keyframes dotPulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(0.85); opacity: 0.7; }
    }

    .hero-title {
        font-size: 2.6rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #1f2937 30%, #4f46e5 70%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 4px 0 2px;
        letter-spacing: -0.06em;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        color: #4b5563;
        margin-top: 4px;
        font-weight: 500;
        font-family: 'Poppins', sans-serif;
    }

    .hero-meta {
        margin-top: 10px;
        font-size: 0.9rem;
        color: #9ca3af;
    }

    /* CARD */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 0% 0%, rgba(79, 70, 229, 0.07), transparent 55%),
            radial-gradient(circle at 100% 100%, rgba(148, 163, 184, 0.15), transparent 60%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 26px;
        border: 1px solid rgba(148, 163, 184, 0.8);
        box-shadow:
            0 20px 56px rgba(148, 163, 184, 0.7),
            0 8px 20px rgba(15, 23, 42, 0.2);
        padding: 22px 24px 24px;
        margin-bottom: 26px;
        transition: all 0.35s ease;
        overflow: hidden;
    }

    .spx-card:hover {
        transform: translateY(-4px);
        box-shadow:
            0 28px 70px rgba(148, 163, 184, 0.85),
            0 10px 26px rgba(15, 23, 42, 0.26);
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 999px;
        border: 1px solid rgba(79, 70, 229, 0.5);
        background:
            linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(37, 99, 235, 0.04)),
            #ffffff;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        color: #4338ca;
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    .spx-pill::before {
        content: '';
        width: 7px;
        height: 7px;
        border-radius: 999px;
        background: #4f46e5;
    }

    .spx-card h4 {
        font-size: 1.4rem;
        font-weight: 800;
        font-family: 'Poppins',sans-serif;
        background: linear-gradient(135deg, #020617 0%, #111827 35%, #4f46e5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 6px 0;
        letter-spacing: -0.04em;
    }

    .spx-sub {
        color: #4b5563;
        font-size: 0.96rem;
        line-height: 1.7;
        font-weight: 400;
    }

    /* SECTION HEADER */
    .section-header {
        font-size: 1.2rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #4b5563 40%, #4f46e5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 1.6rem 0 0.7rem 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .section-header::before {
        content: '';
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        box-shadow:
            0 0 12px rgba(79, 70, 229, 0.9),
            0 3px 7px rgba(15, 23, 42, 0.4);
    }

    /* METRIC */
    .spx-metric {
        position: relative;
        padding: 16px 16px;
        border-radius: 20px;
        background:
            radial-gradient(circle at 0% 0%, rgba(148, 163, 184, 0.2), transparent 65%),
            linear-gradient(135deg, #ffffff, #f3f4f6);
        border: 1px solid rgba(148, 163, 184, 0.9);
        box-shadow:
            0 18px 46px rgba(148, 163, 184, 0.8),
            0 6px 16px rgba(15, 23, 42, 0.22);
    }

    .spx-metric-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.2em;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .spx-metric-value {
        font-size: 1.4rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #020617 0%, #111827 35%, #4f46e5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
    }

    /* INPUTS */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        border-radius: 14px !important;
        color: #111827 !important;
        padding: 10px 14px !important;
        font-size: 0.92rem !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: #4f46e5 !important;
        box-shadow:
            0 0 0 2px rgba(129, 140, 248, 0.35) !important;
    }

    .stSelectbox>div>div {
        background: #ffffff;
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.9);
        box-shadow:
            0 10px 26px rgba(148, 163, 184, 0.4),
            0 4px 10px rgba(15, 23, 42, 0.18);
    }

    .stRadio>div {
        gap: 8px;
        flex-wrap: wrap;
    }

    .stRadio>div>label {
        background: #ffffff;
        padding: 6px 14px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.9);
        font-size: 0.86rem;
        font-weight: 600;
        color: #4b5563;
    }

    .stRadio>div>label[data-selected="true"] {
        background: linear-gradient(135deg, rgba(129, 140, 248, 0.15), rgba(129, 140, 248, 0.08));
        border-color: #4f46e5;
        color: #4338ca;
    }

    /* BUTTONS */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #4f46e5 0%, #2563eb 50%, #0ea5e9 100%);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 9px 20px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        box-shadow:
            0 16px 40px rgba(79, 70, 229, 0.55),
            0 8px 18px rgba(15, 23, 42, 0.28);
    }

    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-2px);
        box-shadow:
            0 20px 56px rgba(79, 70, 229, 0.7),
            0 10px 24px rgba(15, 23, 42, 0.32);
    }

    /* DATAFRAME */
    .stDataFrame {
        border-radius: 18px;
        overflow: hidden;
        box-shadow:
            0 22px 60px rgba(148, 163, 184, 0.9),
            0 10px 24px rgba(15, 23, 42, 0.3);
    }

    label {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: #4b5563 !important;
    }

    .muted {
        color: #4b5563;
        font-size: 0.94rem;
        line-height: 1.7;
        padding: 12px 14px;
        background:
            linear-gradient(135deg, rgba(148, 163, 184, 0.1), rgba(148, 163, 184, 0.05)),
            #ffffff;
        border-left: 4px solid #4f46e5;
        border-radius: 10px;
        margin: 14px 0;
        box-shadow:
            0 14px 38px rgba(148, 163, 184, 0.7),
            0 6px 14px rgba(15, 23, 42, 0.22);
    }

    .decision-card {
        color: #111827;
        font-size: 0.96rem;
        line-height: 1.7;
        padding: 14px 16px;
        background:
            radial-gradient(circle at 0% 0%, rgba(34, 197, 94, 0.12), transparent 55%),
            linear-gradient(135deg, #ecfdf3, #ffffff);
        border-radius: 14px;
        border: 1px solid rgba(22, 163, 74, 0.6);
        box-shadow:
            0 18px 46px rgba(34, 197, 94, 0.45),
            0 6px 16px rgba(15, 23, 42, 0.22);
        margin-bottom: 12px;
    }

    .decision-title {
        font-weight: 800;
        font-size: 1.02rem;
        margin-bottom: 4px;
    }

    .decision-sub {
        font-size: 0.9rem;
        color: #16a34a;
        font-weight: 600;
        margin-bottom: 4px;
    }

    .decision-note {
        font-size: 0.86rem;
        color: #4b5563;
    }

    .app-footer {
        margin-top: 2.2rem;
        padding-top: 1.2rem;
        border-top: 1px solid rgba(148, 163, 184, 0.8);
        text-align: center;
        color: #9ca3af;
        font-size: 0.88rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    cf = st.session_state.get("contract_factor", DEFAULT_CONTRACT_FACTOR)
    st.markdown(
        f"""
        <div class="hero-wrapper">
          <div class="hero-header">
            <div class="hero-inner">
              <div class="hero-badge">
                <span class="hero-dot"></span>
                SYSTEM ACTIVE · STRUCTURE FIRST
              </div>
              <h1 class="hero-title">{APP_NAME}</h1>
              <p class="hero-subtitle">{TAGLINE}</p>
              <div class="hero-meta">
                Slope: {SLOPE_MAG:.3f} pts / 30m · Contract factor: {cf:.2f}
              </div>
            </div>
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


def metric_card(label: str, value: str) -> str:
    return f"""
    <div class="spx-metric">
        <div class="spx-metric-label">{label}</div>
        <div class="spx-metric-value">{value}</div>
    </div>
    """


def section_header(text: str):
    st.markdown(f"<h3 class='section-header'>{text}</h3>", unsafe_allow_html=True)


# =========================================
# TIME / GRID HELPERS
# =========================================

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
    RTH grid for the *new* session day: 08:30–14:30.
    """
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


def make_dt_prev_session(t: dtime) -> datetime:
    """
    Map a pivot time into the *previous* session day.
    All underlying pivots live on the day of BASE_DATE.
    """
    return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def make_dt_from_time(t: dtime) -> datetime:
    """
    24h band around the maintenance window:
    - times >= 15:00 → BASE_DATE day
    - times < 15:00 → BASE_DATE+1 day
    Used for contract anchors that can span 15:00 → next day.
    """
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


# =========================================
# CHANNEL ENGINE (STRUCTURAL RAILS ONLY)
# =========================================

def build_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
) -> Tuple[pd.DataFrame, float]:
    """
    Build a structural channel from previous-session pivots,
    projected onto next-day RTH grid.
    """
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min(make_dt_prev_session(high_time))
    dt_lo = align_30min(make_dt_prev_session(low_time))

    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo

    channel_height = b_top - b_bottom

    rows = []
    for dt in rth_slots():
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
    return df, float(abs(round(channel_height, 4)))


# =========================================
# CONTRACT ENGINE
# =========================================

def compute_contract_factor(
    spx_start: float,
    spx_end: float,
    opt_start: float,
    opt_end: float,
) -> Optional[float]:
    spx_move = spx_end - spx_start
    opt_move = opt_end - opt_start
    if spx_move == 0:
        return None
    return abs(opt_move) / abs(spx_move)


def build_contract_line(
    anchor_a_time: dtime,
    anchor_a_price: float,
    anchor_b_time: dtime,
    anchor_b_price: float,
) -> Tuple[pd.DataFrame, float]:
    """
    Simple linear baseline for a specific contract,
    using two anchors (like 15:00 previous day and 10:30 next day).
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
                "Contract Baseline": round(price, 4),
            }
        )

    df = pd.DataFrame(rows)
    return df, float(round(slope, 6))


# =========================================
# MAIN APP
# =========================================

def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize contract factor
    if "contract_factor" not in st.session_state:
        st.session_state["contract_factor"] = DEFAULT_CONTRACT_FACTOR

    inject_css()

    # -------- SIDEBAR --------
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(
            f"<span class='spx-sub' style='font-size:0.9rem;'>{TAGLINE}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG:.3f} pts / 30m**")
        st.write(f"Contract factor: **{st.session_state['contract_factor']:.2f} × SPX move**")

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "Underlying: 16:00–17:00 CT maintenance\n\n"
            "Contracts: 16:00–19:00 CT maintenance\n\n"
            "RTH projection grid: 08:30–14:30 CT (30m blocks)."
        )

    # -------- HERO --------
    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "📐 Contracts",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # =======================
    # TAB 1: RAILS SETUP
    # =======================
    with tabs[0]:
        card(
            "Structure Engine",
            "Use the previous RTH high and low pivots to define your structural channels. "
            "The app projects them into the new RTH session on a clean 30-minute grid.",
            badge="Rails",
        )

        section_header("Underlying Pivots (Previous RTH Day)")
        st.markdown(
            "<div class='muted'>"
            "Pick the <b>previous RTH</b> high and low pivots from your line chart. "
            "Times are on the prior session; SPX Prophet extends that structure into the new day."
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
                key="rails_high_price",
            )
            high_time = st.time_input(
                "High pivot time (previous RTH, CT)",
                value=dtime(13, 0),
                step=1800,
                key="rails_high_time",
            )
        with c2:
            st.markdown("**Low Pivot**")
            low_price = st.number_input(
                "Low pivot price",
                value=5100.0,
                step=0.25,
                key="rails_low_price",
            )
            low_time = st.time_input(
                "Low pivot time (previous RTH, CT)",
                value=dtime(10, 0),
                step=1800,
                key="rails_low_time",
            )

        section_header("Channel Regime")
        mode = st.radio(
            "Select your channel mode",
            ["Ascending", "Descending", "Both"],
            index=2,
            key="rails_mode",
            horizontal=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        build_col = st.columns([1, 3])[0]
        with build_col:
            if st.button("Build Structural Rails", key="build_rails_btn", use_container_width=True):
                # Ascending channel
                if mode in ("Ascending", "Both"):
                    df_asc, h_asc = build_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=+1,
                    )
                    st.session_state["rails_asc_df"] = df_asc
                    st.session_state["rails_asc_height"] = h_asc
                else:
                    st.session_state["rails_asc_df"] = None
                    st.session_state["rails_asc_height"] = None

                # Descending channel
                if mode in ("Descending", "Both"):
                    df_desc, h_desc = build_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=-1,
                    )
                    st.session_state["rails_desc_df"] = df_desc
                    st.session_state["rails_desc_height"] = h_desc
                else:
                    st.session_state["rails_desc_df"] = None
                    st.session_state["rails_desc_height"] = None

                st.success("Structural rails generated. Check the tables below and the Daily Foresight tab.")

        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_height")
        h_desc = st.session_state.get("rails_desc_height")

        section_header("Underlying Rails • RTH 08:30–14:30 CT")

        if df_asc is None and df_desc is None:
            st.info("Build at least one structural channel to view projections.")
        else:
            if df_asc is not None:
                st.markdown("**Ascending Channel**")
                c_top = st.columns([3, 1])
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True, height=320)
                with c_top[1]:
                    st.markdown(metric_card("Channel Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "Download Ascending CSV",
                        df_asc.to_csv(index=False).encode(),
                        "spx_ascending_rails.csv",
                        "text/csv",
                        key="dl_asc_rails",
                        use_container_width=True,
                    )

            if df_desc is not None:
                st.markdown("**Descending Channel**")
                c_bot = st.columns([3, 1])
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True, height=320)
                with c_bot[1]:
                    st.markdown(metric_card("Channel Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "Download Descending CSV",
                        df_desc.to_csv(index=False).encode(),
                        "spx_descending_rails.csv",
                        "text/csv",
                        key="dl_desc_rails",
                        use_container_width=True,
                    )

        end_card()

    # =======================
    # TAB 2: CONTRACTS
    # =======================
    with tabs[1]:
        card(
            "Contract Engine",
            "Map SPX rail moves into option targets, and optionally build a baseline line "
            "for a specific contract from two anchors.",
            badge="Options",
        )

        # ---------- Factor section ----------
        section_header("Contract Factor")
        cf = st.session_state["contract_factor"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                metric_card("Active Contract Factor", f"{cf:.3f} × SPX"),
                unsafe_allow_html=True,
            )
        with c2:
            new_cf = st.number_input(
                "Manual factor override",
                value=float(cf),
                step=0.05,
                key="manual_cf_input",
            )
            if st.button("Update Factor", key="update_cf_btn"):
                st.session_state["contract_factor"] = new_cf
                st.success(f"Contract factor updated to {new_cf:.3f} × SPX move.")

        section_header("Calibrate From a Real Move")
        st.markdown(
            "<div class='spx-sub'>Take a clean move you already traded. "
            "Use SPX start/end and option start/end to back out the factor.</div>",
            unsafe_allow_html=True,
        )

        c_spx, c_opt = st.columns(2)
        with c_spx:
            spx_start = st.number_input(
                "SPX price at start",
                value=6800.0,
                step=1.0,
                key="cf_spx_start",
            )
            spx_end = st.number_input(
                "SPX price at end",
                value=6820.0,
                step=1.0,
                key="cf_spx_end",
            )
        with c_opt:
            opt_start = st.number_input(
                "Option price at start",
                value=10.0,
                step=0.1,
                key="cf_opt_start",
            )
            opt_end = st.number_input(
                "Option price at end",
                value=15.0,
                step=0.1,
                key="cf_opt_end",
            )

        if st.button("Compute Suggested Factor", key="compute_factor_btn"):
            factor = compute_contract_factor(spx_start, spx_end, opt_start, opt_end)
            if factor is None:
                st.warning("SPX move is zero. Use a case where SPX actually moved.")
            else:
                spx_move = spx_end - spx_start
                opt_move = opt_end - opt_start
                st.markdown(
                    metric_card(
                        "Suggested Factor",
                        f"{factor:.3f} × SPX (from {spx_move:+.1f} pts → {opt_move:+.2f} option)",
                    ),
                    unsafe_allow_html=True,
                )
                if st.button("Apply Suggested Factor", key="apply_factor_btn"):
                    st.session_state["contract_factor"] = factor
                    st.success(f"Contract factor updated to {factor:.3f} × SPX move.")

        # ---------- Manual contract line ----------
        section_header("Manual Contract Line (Optional)")
        st.markdown(
            "<div class='spx-sub'>"
            "Pick two anchors for a specific contract (for example 15:00 previous day and 10:30 in RTH). "
            "The app builds a simple baseline line for that contract on the same 30-minute grid."
            "</div>",
            unsafe_allow_html=True,
        )

        c_a, c_b = st.columns(2)
        with c_a:
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
        with c_b:
            anchor_b_time = st.time_input(
                "Anchor B time (CT)",
                value=dtime(10, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
            anchor_b_price = st.number_input(
                "Contract price at Anchor B",
                value=5.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        if st.button("Build Contract Baseline", key="build_contract_line_btn"):
            df_line, slope_line = build_contract_line(
                anchor_a_time=anchor_a_time,
                anchor_a_price=anchor_a_price,
                anchor_b_time=anchor_b_time,
                anchor_b_price=anchor_b_price,
            )
            st.session_state["contract_line_df"] = df_line
            st.session_state["contract_line_slope"] = slope_line
            st.success(f"Contract baseline built. Slope: {slope_line:+.4f} per 30m.")
        else:
            df_line = st.session_state.get("contract_line_df")
            slope_line = st.session_state.get("contract_line_slope")

        if df_line is not None:
            c_line = st.columns([3, 1])
            with c_line[0]:
                st.dataframe(df_line, use_container_width=True, hide_index=True, height=260)
            with c_line[1]:
                st.markdown(
                    metric_card("Baseline Slope", f"{slope_line:+.4f} / 30m"),
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "Download Baseline CSV",
                    df_line.to_csv(index=False).encode(),
                    "contract_baseline.csv",
                    "text/csv",
                    key="dl_contract_baseline",
                    use_container_width=True,
                )

        end_card()

    # =======================
    # TAB 3: DAILY FORESIGHT
    # =======================
    with tabs[2]:
        card(
            "Daily Foresight",
            "One page that ties together your structural rails, contract factor, "
            "manual contract baseline, and a simple bias decision.",
            badge="Playbook",
        )

        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_height")
        h_desc = st.session_state.get("rails_desc_height")
        cf = st.session_state.get("contract_factor", DEFAULT_CONTRACT_FACTOR)
        df_line = st.session_state.get("contract_line_df")

        if df_asc is None and df_desc is None:
            st.warning("No structural rails found. Build them first in the Rails Setup tab.")
            end_card()
        else:
            # Choose active scenario
            available_choices = []
            if df_asc is not None:
                available_choices.append("Ascending")
            if df_desc is not None:
                available_choices.append("Descending")

            section_header("Choose Active Scenario")
            active_choice = st.radio(
                "Which structural channel are you trading today?",
                available_choices,
                horizontal=True,
                key="foresight_scenario_choice",
            )

            if active_choice == "Ascending":
                df_ch = df_asc
                h_ch = h_asc
            else:
                df_ch = df_desc
                h_ch = h_desc

            # ---- Decision Card: calls / puts / stand aside ----
            section_header("Decision Card")

            times = df_ch["Time"].tolist()
            col_t, col_p = st.columns(2)
            with col_t:
                entry_time = st.selectbox(
                    "Planned entry time (CT, 30m grid)",
                    times,
                    index=0,
                    key="decision_entry_time",
                )
            with col_p:
                entry_spx = st.number_input(
                    "Planned SPX price at that time",
                    value=6800.0,
                    step=0.5,
                    key="decision_entry_spx",
                )

            col_thr, col_em = st.columns(2)
            with col_thr:
                rail_threshold = st.slider(
                    "Rail proximity threshold (points)",
                    min_value=1.0,
                    max_value=10.0,
                    value=3.0,
                    step=0.5,
                    key="rail_threshold",
                )
            with col_em:
                daily_em = st.number_input(
                    "Daily expected move (optional, points)",
                    value=80.0,
                    step=1.0,
                    key="decision_em",
                )

            row = df_ch[df_ch["Time"] == entry_time].iloc[0]
            top = float(row["Top Rail"])
            bottom = float(row["Bottom Rail"])

            dist_lower = abs(entry_spx - bottom)
            dist_upper = abs(top - entry_spx)

            # Simple bias logic
            if dist_lower <= rail_threshold and dist_upper > rail_threshold:
                bias = "Call bias (buying dips into structure)"
                bias_short = "Calls"
                note = "Price is leaning into the lower rail. This is your structural support zone."
            elif dist_upper <= rail_threshold and dist_lower > rail_threshold:
                bias = "Put bias (selling rips into structure)"
                bias_short = "Puts"
                note = "Price is leaning into the upper rail. This is your structural resistance zone."
            elif dist_lower <= rail_threshold and dist_upper <= rail_threshold:
                bias = "Very tight channel — extreme compression"
                bias_short = "Cautious / small size"
                note = "Price is within threshold of both rails. This can be squeeze/chop territory."
            else:
                bias = "Stand aside / middle of channel"
                bias_short = "No clean edge"
                note = "Price is not near either rail. Wait for a lean into structure or only scalp very small."

            # EM risk notes
            risk_notes = []
            if h_ch is not None and daily_em is not None and daily_em > 0:
                if h_ch < 0.5 * daily_em:
                    risk_notes.append(
                        "Channel height is much smaller than expected move. "
                        "Chop / fakeouts above and below rails are more likely."
                    )
                elif h_ch > 1.5 * daily_em:
                    risk_notes.append(
                        "Channel height is larger than expected move. "
                        "Full rail-to-rail swings may be ambitious; partial targets can be safer."
                    )

            em_text = " · ".join(risk_notes) if risk_notes else "Channel vs EM looks normal."

            st.markdown(
                f"""
                <div class="decision-card">
                  <div class="decision-title">{bias_short}</div>
                  <div class="decision-sub">{bias}</div>
                  <div class="decision-note">
                    {note}<br>
                    <b>Distance to lower rail:</b> {dist_lower:.1f} pts ·
                    <b>Distance to upper rail:</b> {dist_upper:.1f} pts<br>
                    <b>Channel height:</b> {h_ch:.1f} pts · <b>EM:</b> {daily_em:.1f} pts<br>
                    {em_text}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ---- Structure Summary ----
            section_header("Structure Summary")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(metric_card("Active Scenario", active_choice), unsafe_allow_html=True)

            with c2:
                st.markdown(
                    metric_card("Channel Height", f"{h_ch:.1f} pts"),
                    unsafe_allow_html=True,
                )

            with c3:
                full_opt_move = cf * h_ch
                st.markdown(
                    metric_card("Option Target / Full Swing", f"{full_opt_move:.2f} units"),
                    unsafe_allow_html=True,
                )

            # ---- Inside-Channel Play ----
            section_header("Inside-Channel Play")
            st.markdown(
                f"""
                <div class='spx-sub'>
                    <p><b>Long calls:</b> Buy near the lower rail, target the upper rail.</p>
                    <ul style="margin-left:20px;">
                        <li>Underlying move: about <b>{h_ch:.1f}</b> points in your favor.</li>
                        <li>Structural option target: about <b>{full_opt_move:.1f}</b> units using factor {cf:.2f}.</li>
                    </ul>
                    <p><b>Long puts:</b> Sell near the upper rail, target the lower rail.</p>
                    <ul style="margin-left:20px;">
                        <li>Same channel height in your favor, opposite direction.</li>
                        <li>Same size option move in the opposite sign.</li>
                    </ul>
                    <p><i>This is your baseline map. Anything the contract gives you beyond this target
                    is volatility and skew working in your favor.</i></p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ---- Option Planner ----
            section_header("Option Planner")

            col_side, col_entry = st.columns(2)
            with col_side:
                position_type = st.radio(
                    "Position type",
                    ["Long Call", "Long Put"],
                    horizontal=True,
                    key="planner_pos_type",
                )
            with col_entry:
                entry_contract = st.number_input(
                    "Planned contract entry price",
                    value=5.0,
                    step=0.1,
                    key="planner_entry_contract",
                )

            col_frac, col_dummy = st.columns(2)
            with col_frac:
                tp_fraction = st.slider(
                    "Take profit fraction of full channel move",
                    min_value=0.1,
                    max_value=1.0,
                    value=0.5,
                    step=0.05,
                    key="planner_tp_fraction",
                )

            full_move_units = cf * h_ch
            target_move = full_move_units * tp_fraction

            if position_type == "Long Call":
                target_contract = entry_contract + target_move
                side_sign = +1
            else:
                target_contract = entry_contract - target_move
                side_sign = -1

            c_opt1, c_opt2, c_opt3 = st.columns(3)
            with c_opt1:
                st.markdown(
                    metric_card("Entry Contract", f"{entry_contract:.2f}"),
                    unsafe_allow_html=True,
                )
            with c_opt2:
                st.markdown(
                    metric_card("Target Move (structural)", f"{side_sign*target_move:+.2f} units"),
                    unsafe_allow_html=True,
                )
            with c_opt3:
                st.markdown(
                    metric_card("Target Exit Price", f"{target_contract:.2f}"),
                    unsafe_allow_html=True,
                )

            # If manual contract line exists, show baseline at entry time
            if df_line is not None:
                row_line = df_line[df_line["Time"] == entry_time]
                if not row_line.empty:
                    baseline_price = float(row_line.iloc[0]["Contract Baseline"])
                    st.markdown(
                        f"""
                        <div class='muted'>
                        <b>Baseline check:</b> At {entry_time}, your contract baseline is around
                        <b>{baseline_price:.2f}</b>. Compare your planned entry ({entry_contract:.2f}) and
                        target ({target_contract:.2f}) to see if you're paying rich/cheap vs your own anchors.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            # ---- Time-Aligned Map ----
            section_header("Time-Aligned Map")

            merged = df_ch.copy()
            merged["Full-Channel SPX Move"] = round(float(h_ch), 2)
            merged["Option Target per Full Swing"] = round(float(full_move_units), 2)

            if df_line is not None:
                merged = merged.merge(df_line, on="Time", how="left")

            st.caption(
                "Each row is a 30-minute RTH slot. The rails give you the structure. "
                "The option columns show what a full lower→upper or upper→lower swing is worth "
                "to your contracts using your current factor. "
                "If you built a contract baseline, it appears as an extra column."
            )
            st.dataframe(merged, use_container_width=True, hide_index=True, height=460)

            st.markdown(
                "<div class='muted'><b>How to use this:</b> "
                "Wait for price to lean into a rail, use the Decision Card for direction, "
                "and the Option Planner for contract targets. The map below is just the grid that "
                "ties time and rails together.</div>",
                unsafe_allow_html=True,
            )

            end_card()

    # =======================
    # TAB 4: ABOUT
    # =======================
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Overview")
        st.markdown(
            """
            <div class='spx-sub'>
            <p>SPX Prophet centers everything around one idea:</p>
            <p style="margin-left:14px; margin-top:6px;">
            <b>Previous RTH pivots define today's rails.</b>
            </p>
            <ul style="margin-left:20px; margin-top:10px;">
              <li>Previous RTH high and low pivots form your structural channel.</li>
              <li>A fixed slope of <b>0.475 points per 30 minutes</b> projects that structure into the new session.</li>
              <li>You choose whether you treat the day as an ascending or descending regime (or keep both in view).</li>
              <li>A simple contract factor maps SPX channel moves into realistic option targets.</li>
              <li>An optional manual contract line lets you track the behavior of a specific contract.</li>
              <li>The Daily Foresight tab compresses this into a <b>Direction</b> (calls/puts/stand aside)
                  and a <b>Target</b> (contract exit zone).</li>
            </ul>
            <p>The goal is not prediction magic. The goal is to remove guesswork at the rail so that when price returns
            to your structure, you already know which side you're leaning to and what a sensible exit looks like.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        end_card()

    # Footer
    st.markdown(
        f"<div class='app-footer'>© 2025 {APP_NAME} · Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()