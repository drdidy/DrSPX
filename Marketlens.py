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
# STUNNING LIGHT UI
# =========================================

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
        padding-bottom: 3.0rem;
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
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #6366f1 0%, #3b82f6 50%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
        letter-spacing: -0.04em;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
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
        margin-bottom: 2.5rem;
    }

    .hero-header {
        position: relative;
        max-width: 900px;
        width: 100%;
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
        text-align: center;
        animation: heroGlow 6s ease-in-out infinite;
    }

    @keyframes heroGlow {
        0%, 100% {
            box-shadow: 0 24px 60px -12px rgba(99, 102, 241, 0.15),
                        0 12px 30px -8px rgba(0, 0, 0, 0.08);
        }
        50% {
            box-shadow: 0 24px 60px -12px rgba(99, 102, 241, 0.25),
                        0 12px 30px -8px rgba(99, 102, 241, 0.12);
        }
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

    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 8px 18px;
        border-radius: 999px;
        background:
            linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.12)),
            #ffffff;
        border: 2px solid rgba(16, 185, 129, 0.3);
        font-size: 0.8rem;
        font-weight: 700;
        color: #059669;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 12px;
        box-shadow:
            0 8px 24px rgba(16, 185, 129, 0.15),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
        animation: statusPulse 2s ease-in-out infinite;
    }

    .hero-badge::before {
        content: '';
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: #10b981;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
        animation: pulseDot 2s ease-in-out infinite;
    }

    @keyframes statusPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }

    @keyframes pulseDot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(0.85); }
    }

    .hero-title {
        font-size: 2.8rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 40%, #3b82f6 70%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 4px 0;
        letter-spacing: -0.06em;
    }

    .hero-subtitle {
        font-size: 1.1rem;
        color: #64748b;
        margin-top: 6px;
        font-weight: 500;
        font-family: 'Poppins', sans-serif;
    }

    .hero-meta {
        margin-top: 10px;
        font-size: 0.95rem;
        color: #94a3b8;
    }

    /* CARD */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 8% 8%, rgba(99, 102, 241, 0.08), transparent 50%),
            radial-gradient(circle at 92% 92%, rgba(59, 130, 246, 0.08), transparent 50%),
            linear-gradient(135deg, #ffffff, #fefeff);
        border-radius: 28px;
        border: 2px solid rgba(148, 163, 184, 0.35);
        box-shadow:
            0 24px 60px -12px rgba(148, 163, 184, 0.35),
            0 12px 30px -8px rgba(0, 0, 0, 0.04),
            inset 0 2px 4px rgba(255, 255, 255, 0.9),
            inset 0 -2px 4px rgba(148, 163, 184, 0.08);
        padding: 28px 30px;
        margin-bottom: 28px;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }

    .spx-card:hover {
        transform: translateY(-6px);
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow:
            0 32px 80px -16px rgba(99, 102, 241, 0.25),
            0 16px 40px -8px rgba(148, 163, 184, 0.45);
    }

    .spx-card h4 {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 6px 0;
        letter-spacing: -0.03em;
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 16px;
        border-radius: 999px;
        border: 1px solid rgba(99, 102, 241, 0.4);
        background:
            linear-gradient(135deg, rgba(148, 163, 184, 0.12), rgba(148, 163, 184, 0.08)),
            #ffffff;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        color: #4b5563;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .spx-sub {
        color: #475569;
        font-size: 0.98rem;
        line-height: 1.7;
        font-weight: 400;
    }

    /* SECTION HEADER */
    .section-header {
        font-size: 1.3rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
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
        background: linear-gradient(135deg, #6366f1, #3b82f6);
        box-shadow:
            0 0 14px rgba(99, 102, 241, 0.7),
            0 3px 8px rgba(99, 102, 241, 0.35);
    }

    /* METRIC */
    .spx-metric {
        position: relative;
        padding: 18px 18px;
        border-radius: 20px;
        background:
            radial-gradient(circle at top left, rgba(148, 163, 184, 0.15), transparent 70%),
            linear-gradient(135deg, #ffffff, #f8fafc);
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            0 16px 40px rgba(148, 163, 184, 0.25),
            inset 0 1px 3px rgba(255, 255, 255, 0.9);
        overflow: hidden;
    }

    .spx-metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .spx-metric-value {
        font-size: 1.5rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #1f2933 0%, #4f46e5 100%);
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
        font-size: 0.95rem !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: #6366f1 !important;
        box-shadow:
            0 0 0 3px rgba(129, 140, 248, 0.3) !important;
    }

    .stSelectbox>div>div {
        background: #ffffff;
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.9);
        box-shadow: 0 6px 16px rgba(148, 163, 184, 0.25);
    }

    .stRadio>div {
        gap: 10px;
    }

    .stRadio>div>label {
        background: #ffffff;
        padding: 8px 16px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.9);
        font-size: 0.9rem;
        font-weight: 600;
        color: #4b5563;
    }

    .stRadio>div>label[data-selected="true"] {
        background: linear-gradient(135deg, rgba(129, 140, 248, 0.15), rgba(129, 140, 248, 0.08));
        border-color: #6366f1;
        color: #4338ca;
    }

    /* BUTTONS */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 50%, #0ea5e9 100%);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 10px 24px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        box-shadow:
            0 14px 30px rgba(79, 70, 229, 0.35),
            0 6px 14px rgba(15, 23, 42, 0.2);
    }

    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-2px);
        box-shadow:
            0 18px 40px rgba(79, 70, 229, 0.45),
            0 8px 18px rgba(15, 23, 42, 0.25);
    }

    /* DATAFRAME */
    .stDataFrame {
        border-radius: 20px;
        overflow: hidden;
        box-shadow:
            0 20px 50px rgba(148, 163, 184, 0.4),
            0 10px 20px rgba(15, 23, 42, 0.12);
    }

    label {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #4b5563 !important;
    }

    .muted {
        color: #475569;
        font-size: 0.95rem;
        line-height: 1.7;
        padding: 14px 16px;
        background:
            linear-gradient(135deg, rgba(148, 163, 184, 0.08), rgba(148, 163, 184, 0.04)),
            #ffffff;
        border-left: 4px solid #6366f1;
        border-radius: 10px;
        margin: 16px 0;
        box-shadow: 0 8px 20px rgba(148, 163, 184, 0.3);
    }

    .app-footer {
        margin-top: 2.5rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(148, 163, 184, 0.7);
        text-align: center;
        color: #94a3b8;
        font-size: 0.9rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown(
        f"""
        <div class="hero-wrapper">
            <div class="hero-header">
                <div class="hero-badge">System Active · Structure First</div>
                <h1 class="hero-title">{APP_NAME}</h1>
                <p class="hero-subtitle">{TAGLINE}</p>
                <div class="hero-meta">
                    Slope: {SLOPE_MAG:.3f} pts / 30m · Contract factor: {st.session_state.get("contract_factor", DEFAULT_CONTRACT_FACTOR):.2f}
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

    This is the fix: all underlying pivots (RTH pivots from yesterday)
    live on the day of BASE_DATE.
    """
    return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def make_dt_mixed(t: dtime) -> datetime:
    """
    For things like contract anchors that might be overnight:
    - times >= 15:00 are treated as previous session
    - times < 15:00 are treated as next session
    """
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


# =========================================
# CHANNEL ENGINES
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

    # Pivots live on previous session day (fix)
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


def build_em_channel(
    em_value: float,
    anchor_price: float,
    anchor_time: dtime,
    orientation_sign: int,
) -> Tuple[pd.DataFrame, float]:
    """
    EM channel with the SAME slope magnitude as the rails.

    em_value ~ one-side EM in points.
    We build a mid-line and shift +/- em_value to get top/bottom.
    """
    s = orientation_sign * SLOPE_MAG

    # EM anchor is also thought of as previous-session reference (e.g., 17:00)
    dt_anchor = align_30min(make_dt_prev_session(anchor_time))
    k_anchor = blocks_from_base(dt_anchor)

    # Mid-line through the anchor
    b_mid = anchor_price - s * k_anchor

    rows = []
    for dt in rth_slots():
        k = blocks_from_base(dt)
        mid = s * k + b_mid
        top = mid + em_value
        bottom = mid - em_value
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "EM Mid": round(mid, 4),
                "EM Top": round(top, 4),
                "EM Bottom": round(bottom, 4),
            }
        )

    df = pd.DataFrame(rows)
    em_height = 2 * em_value
    return df, float(abs(round(em_height, 4)))


# =========================================
# CONTRACT FACTOR HELPER
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
            f"<span class='spx-sub' style='font-size:0.95rem;'>{TAGLINE}</span>",
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
            "🧱 Rails & EM Setup",
            "📐 Contract Factor Helper",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # =======================
    # TAB 1: RAILS & EM
    # =======================
    with tabs[0]:
        card(
            "Structure Engine",
            "Define your previous RTH pivots, project structural rails into the new day, "
            "and optionally overlay an Expected Move channel.",
            badge="Rails & EM",
        )

        section_header("Underlying Pivots (Previous RTH Day)")
        st.markdown(
            "<div class='spx-sub'>Use the key swing high and low from the previous "
            "RTH session (engulfing pivots on your line chart). Times are for the "
            "<b>previous</b> RTH day; the app extends them into the new session.</div>",
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

        # ---------- EM CHANNEL ----------
        section_header("Expected Move Channel (Optional)")
        st.markdown(
            "<div class='spx-sub'>If you have the market's daily expected move, you can build a "
            "matching-slope channel to frame the day. If not, you can skip this section.</div>",
            unsafe_allow_html=True,
        )

        c1_em, c2_em, c3_em = st.columns(3)
        with c1_em:
            em_value = st.number_input(
                "Expected move (points, one side)",
                value=80.0,
                step=1.0,
                key="em_value_input",
            )
        with c2_em:
            em_anchor_price = st.number_input(
                "EM anchor price",
                value=5200.0,
                step=1.0,
                key="em_anchor_price",
            )
        with c3_em:
            em_anchor_time = st.time_input(
                "EM anchor time (previous session, CT)",
                value=dtime(17, 0),
                step=1800,
                key="em_anchor_time",
            )

        em_orientation = st.radio(
            "EM orientation",
            ["Up", "Down"],
            index=0,
            key="em_orientation",
            horizontal=True,
        )

        build_em_col = st.columns([1, 3])[0]
        with build_em_col:
            if st.button("Build EM Channel", key="build_em_btn", use_container_width=True):
                if em_value <= 0:
                    st.warning("Expected move must be positive to build a channel.")
                else:
                    sign = +1 if em_orientation == "Up" else -1
                    df_em, em_height = build_em_channel(
                        em_value=em_value,
                        anchor_price=em_anchor_price,
                        anchor_time=em_anchor_time,
                        orientation_sign=sign,
                    )
                    st.session_state["em_df"] = df_em
                    st.session_state["em_height"] = em_height
                    st.success("EM channel generated. It will also appear in the Daily Foresight map.")

        df_em = st.session_state.get("em_df")
        em_height = st.session_state.get("em_height")

        if df_em is not None:
            st.markdown("**EM Channel • RTH 08:30–14:30 CT**")
            em_cols = st.columns([3, 1])
            with em_cols[0]:
                st.dataframe(df_em, use_container_width=True, hide_index=True, height=320)
            with em_cols[1]:
                st.markdown(metric_card("EM Width (top-bottom)", f"{em_height:.2f} pts"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "Download EM CSV",
                    df_em.to_csv(index=False).encode(),
                    "spx_em_channel.csv",
                    "text/csv",
                    key="dl_em_channel",
                    use_container_width=True,
                )

        end_card()

    # =======================
    # TAB 2: CONTRACT FACTOR
    # =======================
    with tabs[1]:
        card(
            "Contract Factor Helper",
            "Use real trades to calibrate how far your option typically moves for a given SPX move. "
            "This factor feeds into your Daily Foresight targets.",
            badge="Options Mapping",
        )

        section_header("Current Factor")
        cf = st.session_state["contract_factor"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(metric_card("Active Contract Factor", f"{cf:.3f} × SPX"), unsafe_allow_html=True)
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
            "Use the SPX start/end and the option start/end to back out the factor.</div>",
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

        end_card()

    # =======================
    # TAB 3: DAILY FORESIGHT
    # =======================
    with tabs[2]:
        card(
            "Daily Foresight",
            "One page that ties together your structural rails, EM (if used), and contract factor "
            "into a simple playbook.",
            badge="Playbook",
        )

        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_height")
        h_desc = st.session_state.get("rails_desc_height")
        df_em = st.session_state.get("em_df")
        em_height = st.session_state.get("em_height")
        cf = st.session_state.get("contract_factor", DEFAULT_CONTRACT_FACTOR)

        if df_asc is None and df_desc is None:
            st.warning("No structural rails found. Build them first in the Rails & EM Setup tab.")
            end_card()
        else:
            section_header("Structure Summary")
            c1, c2, c3 = st.columns(3)
            with c1:
                scenario = "Ascending" if df_asc is not None else "Descending"
                st.markdown(metric_card("Default Scenario", scenario), unsafe_allow_html=True)

            with c2:
                ch_text = "—"
                if h_asc is not None and h_desc is not None:
                    ch_text = f"Asc: {h_asc:.1f} · Desc: {h_desc:.1f}"
                elif h_asc is not None:
                    ch_text = f"{h_asc:.1f} pts (Asc)"
                elif h_desc is not None:
                    ch_text = f"{h_desc:.1f} pts (Desc)"
                st.markdown(metric_card("Channel Heights", ch_text), unsafe_allow_html=True)

            with c3:
                if h_asc is not None:
                    ex_move = cf * h_asc
                elif h_desc is not None:
                    ex_move = cf * h_desc
                else:
                    ex_move = 0.0
                st.markdown(
                    metric_card("Option Target per Full Swing", f"{ex_move:.2f} units"),
                    unsafe_allow_html=True,
                )

            section_header("Choose Active Scenario")
            active_choice = st.radio(
                "Which channel are you trading today?",
                [opt for opt in ["Ascending", "Descending"] if
                 (opt == "Ascending" and df_asc is not None) or (opt == "Descending" and df_desc is not None)],
                horizontal=True,
                key="foresight_scenario_choice",
            )

            if active_choice == "Ascending":
                df_ch = df_asc
                h_ch = h_asc
            else:
                df_ch = df_desc
                h_ch = h_desc

            if df_ch is None or h_ch is None:
                st.warning("Selected scenario has no rails. Build that channel in the setup tab.")
                end_card()
            else:
                contract_move_full = cf * h_ch

                section_header("Inside-Channel Play")
                st.markdown(
                    f"""
                    <div class='spx-sub'>
                        <p><b>Long idea:</b> Buy calls near the lower rail, exit near the upper rail.</p>
                        <ul style="margin-left:20px;">
                            <li>Underlying move: about <b>{h_ch:.1f}</b> points in your favor.</li>
                            <li>Option target (structural): about <b>{contract_move_full:.1f}</b> units
                            using factor {cf:.2f}.</li>
                        </ul>
                        <p><b>Short idea:</b> Buy puts near the upper rail, exit near the lower rail.</p>
                        <ul style="margin-left:20px;">
                            <li>Same channel height in your favor, opposite direction.</li>
                            <li>Same size option move in the opposite sign.</li>
                        </ul>
                        <p><i>This is a structural benchmark, not a full Greeks model. Real options can move
                        more due to IV expansion or time decay.</i></p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Time-aligned map
                section_header("Time-Aligned Map")

                if df_em is not None:
                    merged = df_ch.merge(df_em, on="Time", how="left")
                else:
                    merged = df_ch.copy()

                merged["Full-Channel SPX Move"] = round(float(h_ch), 2)
                merged["Option Target per Full Swing"] = round(float(contract_move_full), 2)

                st.caption(
                    "Every row is a 30-minute RTH slot. Rails and EM (if present) give you the "
                    "structure. The option columns show the structural target size for a full "
                    "lower-to-upper or upper-to-lower swing."
                )
                st.dataframe(merged, use_container_width=True, hide_index=True, height=460)

                st.markdown(
                    "<div class='muted'><b>How to read this:</b> "
                    "Use the diagonal rails to time entries and the full-channel option target as your "
                    "benchmark. If the option pays you more than the structural target, that extra is "
                    "your volatility bonus for the day.</div>",
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
            <p>SPX Prophet is built on a simple structure:</p>
            <ul style="margin-left:20px;">
              <li>Previous RTH high and low pivots define your core structural channel.</li>
              <li>A fixed slope of <b>0.475 points per 30 minutes</b> projects that structure into the new day.</li>
              <li>An optional Expected Move channel lets you frame the market maker’s range with the same geometry.</li>
              <li>A simple contract factor maps SPX moves into option targets, without overcomplicating things with Greeks.</li>
            </ul>
            <p>The goal is clarity. When price tags your rails, you already know what a full swing is worth on the underlying
            and roughly what that tends to mean for your contracts.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        end_card()

    # Footer
    st.markdown(
        f"<div class='app-footer'>© 2025 {APP_NAME} • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()