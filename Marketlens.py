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
            radial-gradient(circle at 0% 0%, rgba(79, 70, 229, 0.08), transparent 50%),
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

    .hero-header::before {
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(circle at 0% 0%, rgba(255, 255, 255, 0.4), transparent 55%);
        opacity: 0.75;
        pointer-events: none;
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
        font-family: 'Poppins', sans-serif;
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
            "📐 Contract Factor",
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

        end_card()

    # =======================
    # TAB 3: DAILY FORESIGHT
    # =======================
    with tabs[2]:
        card(
            "Daily Foresight",
            "One page that ties together your structural rails and contract factor "
            "into a simple playbook for the session.",
            badge="Playbook",
        )

        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_height")
        h_desc = st.session_state.get("rails_desc_height")
        cf = st.session_state.get("contract_factor", DEFAULT_CONTRACT_FACTOR)

        if df_asc is None and df_desc is None:
            st.warning("No structural rails found. Build them first in the Rails Setup tab.")
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
                    metric_card("Option Target / Full Swing", f"{ex_move:.2f} units"),
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
                        <p><b>Long calls:</b> Buy near the lower rail, target the upper rail.</p>
                        <ul style="margin-left:20px;">
                            <li>Underlying move: about <b>{h_ch:.1f}</b> points in your favor.</li>
                            <li>Structural option target: about <b>{contract_move_full:.1f}</b> units
                            using factor {cf:.2f}.</li>
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

                # Time-aligned map
                section_header("Time-Aligned Map")

                merged = df_ch.copy()
                merged["Full-Channel SPX Move"] = round(float(h_ch), 2)
                merged["Option Target per Full Swing"] = round(float(contract_move_full), 2)

                st.caption(
                    "Each row is a 30-minute RTH slot. The rails give you the structure. "
                    "The option columns show what a full lower→upper or upper→lower swing is worth "
                    "to your contracts using your current factor."
                )
                st.dataframe(merged, use_container_width=True, hide_index=True, height=460)

                st.markdown(
                    "<div class='muted'><b>How to use this:</b> "
                    "Wait for price to lean into a rail, decide whether you're playing the bounce or the break, "
                    "and use the full-channel option target as your reference for sizing, risk, and exits.</div>",
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
            </ul>
            <p>The result is a clean map. When SPX tags a rail, you already know what a full swing is structurally worth —
            both on the index and on your contracts.</p>
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