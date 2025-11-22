# spx_prophet_legend.py
# SPX Prophet — Where Structure Becomes Foresight.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475  # pts per 30m for rails
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # synthetic 15:00 anchor for time math


# ===============================
# STUNNING LIGHT MODE UI
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
      
    /* === FOUNDATION === */
    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.05), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.05), transparent 60%),
          radial-gradient(circle 1200px at 50% 50%, rgba(148, 163, 184, 0.04), transparent),
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
      
    /* === SIDEBAR === */
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.05), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.4);
        box-shadow:
            8px 0 40px rgba(148, 163, 184, 0.15),
            4px 0 14px rgba(15, 23, 42, 0.06);
    }
      
    [data-testid="stSidebar"] h3 {
        font-size: 1.8rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #4f46e5 50%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        letter-spacing: -0.03em;
    }
      
    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.7) 20%,
            rgba(148, 163, 184, 0.9) 50%,
            rgba(148, 163, 184, 0.7) 80%,
            transparent 100%);
    }
      
    [data-testid="stSidebar"] h4 {
        color: #475569;
        font-size: 0.95rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-top: 1.5rem;
        margin-bottom: 0.6rem;
    }
      
    /* === HERO HEADER (CENTERED) === */
    .hero-header {
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(79, 70, 229, 0.10), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(56, 189, 248, 0.10), transparent 60%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 32px;
        padding: 32px 40px;
        margin-bottom: 32px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 24px 60px -18px rgba(15, 23, 42, 0.25),
            0 10px 30px -18px rgba(15, 23, 42, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        overflow: hidden;
    }
      
    .hero-inner {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        gap: 12px;
    }
      
    .status-indicator {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        background:
            linear-gradient(135deg, rgba(22, 163, 74, 0.12), rgba(22, 163, 74, 0.08)),
            #ffffff;
        border: 1px solid rgba(22, 163, 74, 0.5);
        font-size: 0.8rem;
        font-weight: 600;
        color: #15803d;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }
      
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 10px rgba(34, 197, 94, 0.9);
    }
      
    .hero-title {
        font-size: 2.6rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #1d4ed8 40%, #0369a1 80%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.06em;
        line-height: 1.1;
    }
      
    .hero-subtitle {
        font-size: 1.05rem;
        color: #64748b;
        max-width: 620px;
    }
      
    .hero-meta {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 12px;
        margin-top: 8px;
        font-size: 0.85rem;
        color: #6b7280;
    }
      
    .hero-meta span {
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.10);
        border: 1px solid rgba(148, 163, 184, 0.6);
    }
      
    /* === CARD === */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 10% 0%, rgba(79, 70, 229, 0.08), transparent 55%),
            radial-gradient(circle at 90% 100%, rgba(56, 189, 248, 0.08), transparent 55%),
            linear-gradient(135deg, #ffffff, #fdfdfd);
        border-radius: 28px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 20px 55px rgba(15, 23, 42, 0.16),
            0 8px 18px rgba(15, 23, 42, 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.95);
        padding: 28px 30px;
        margin-bottom: 26px;
        overflow: hidden;
    }
      
    .spx-card h4 {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #1d4ed8 70%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 8px 0;
        letter-spacing: -0.04em;
    }
      
    .icon-large {
        font-size: 2.8rem;
        margin-bottom: 6px;
    }
      
    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 16px;
        border-radius: 999px;
        border: 1px solid rgba(59, 130, 246, 0.4);
        background:
            linear-gradient(135deg, rgba(59, 130, 246, 0.10), rgba(37, 99, 235, 0.06)),
            #ffffff;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        color: #1d4ed8;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
      
    .spx-sub {
        color: #4b5563;
        font-size: 0.98rem;
        line-height: 1.7;
    }
      
    /* === SECTION HEADERS === */
    .section-header {
        font-size: 1.35rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #1d4ed8 70%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 1.8rem 0 0.8rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.7);
        display: flex;
        align-items: center;
        gap: 10px;
    }
      
    .section-header::before {
        content: '';
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: linear-gradient(135deg, #22c55e, #16a34a);
        box-shadow: 0 0 14px rgba(34, 197, 94, 0.9);
    }
      
    /* === METRIC CARD === */
    .spx-metric {
        position: relative;
        padding: 18px 18px 16px 18px;
        border-radius: 20px;
        background:
            radial-gradient(circle at 0% 0%, rgba(79, 70, 229, 0.06), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow:
            0 14px 32px rgba(15, 23, 42, 0.18),
            0 4px 10px rgba(15, 23, 42, 0.08);
    }
      
    .spx-metric-label {
        font-size: 0.70rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 6px;
    }
      
    .spx-metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #020617;
    }
      
    /* === BUTTONS === */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 60%, #0284c7 100%);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 10px 20px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        box-shadow:
            0 14px 28px rgba(37, 99, 235, 0.35),
            0 4px 12px rgba(15, 23, 42, 0.3);
        cursor: pointer;
    }
      
    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-1px);
        box-shadow:
            0 18px 34px rgba(37, 99, 235, 0.4),
            0 6px 14px rgba(15, 23, 42, 0.35);
    }
      
    /* === INPUTS === */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 1px solid rgba(148, 163, 184, 0.8) !important;
        border-radius: 14px !important;
        color: #020617 !important;
        padding: 10px 12px !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
      
    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: #2563eb !important;
        box-shadow:
            0 0 0 1px rgba(37, 99, 235, 0.3),
            0 0 0 4px rgba(191, 219, 254, 0.9) !important;
        background: #f9fafb !important;
    }
      
    .stSelectbox>div>div {
        background: #ffffff;
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.8);
    }
      
    label {
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        color: #4b5563 !important;
    }
      
    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: rgba(248, 250, 252, 0.9);
        padding: 6px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.7);
    }
      
    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        font-weight: 600;
        font-size: 0.9rem;
        padding: 8px 16px;
        color: #6b7280;
    }
      
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #1d4ed8, #2563eb);
        color: #ffffff;
    }
      
    /* === DATAFRAME === */
    .stDataFrame {
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow:
            0 16px 34px rgba(15, 23, 42, 0.16),
            0 4px 10px rgba(15, 23, 42, 0.08);
    }
      
    .muted {
        color: #4b5563;
        font-size: 0.95rem;
        line-height: 1.7;
        padding: 12px 14px;
        background:
            linear-gradient(135deg, rgba(148, 163, 184, 0.10), rgba(226, 232, 240, 0.4)),
            #ffffff;
        border-left: 3px solid #1d4ed8;
        border-radius: 10px;
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
          <div class="hero-inner">
            <div class="status-indicator">
              <span class="status-dot"></span>
              SYSTEM ACTIVE
            </div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">{TAGLINE}</p>
            <div class="hero-meta">
              <span>Structure First. Emotion Last.</span>
              <span>Rails slope: {SLOPE_MAG:.3f} pts / 30m</span>
            </div>
          </div>
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
    Same mapping you used before:
    If hour >= 15, treat as BASE_DATE day (synthetic).
    Else treat as next calendar day.
    This keeps your overnight / RTH grid consistent with your old app.
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
    """
    RTH grid for 'today': 08:30–14:30 CT on the next day after BASE_DATE.
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
    Build a single channel (ascending or descending) using your fixed slope magnitude.
    """
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))
    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

    # Intercepts for top & bottom rails
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


def build_stacked_from_channel(df: pd.DataFrame, channel_height: float) -> pd.DataFrame:
    """
    Build a stacked channel: main rails plus ±1 channel-height rails.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in df.iterrows():
        time_str = row["Time"]
        top = float(row["Top Rail"])
        bottom = float(row["Bottom Rail"])
        rows.append(
            {
                "Time": time_str,
                "Main Top": round(top, 4),
                "Main Bottom": round(bottom, 4),
                "Top +1H": round(top + channel_height, 4),
                "Bottom -1H": round(bottom - channel_height, 4),
            }
        )
    return pd.DataFrame(rows)


# ===============================
# CONTRACT ENGINE (LINE PROJECTION)
# ===============================

def build_contract_projection(
    anchor_a_time: dtime,
    anchor_a_price: float,
    anchor_b_time: dtime,
    anchor_b_price: float,
) -> Tuple[pd.DataFrame, float]:
    """
    Simple structural contract line on the same 30m grid, defined by two anchor prices.
    No Greeks, no decay model: just a clean slope baseline.
    """
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
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Contract Price": round(price, 4),
            }
        )

    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# CHOP DETECTOR
# ===============================

def detect_chop(
    primary_height: Optional[float],
    alt_height: Optional[float],
    min_height_for_trend: float,
    max_height_ratio_for_clean_trend: float,
):
    """
    Very simple structural chop detector.

    • If both channels are small -> likely chop.
    • If heights are similar (alt / primary high) -> competing structures -> more chop.
    • Otherwise -> cleaner trending environment.
    """
    if primary_height is None or alt_height is None:
        return "Unknown", "Need both ascending and descending rails to assess chop."

    h_p = float(primary_height)
    h_a = float(alt_height)

    if h_p < min_height_for_trend and h_a < min_height_for_trend:
        return (
            "High",
            f"Both channels are small (primary {h_p:.1f} pts, alternate {h_a:.1f} pts). Structural moves are tight. Expect chop unless the tape proves otherwise.",
        )

    ratio = min(h_p, h_a) / max(h_p, h_a) if max(h_p, h_a) > 0 else 1.0

    if ratio > max_height_ratio_for_clean_trend:
        return (
            "Moderate",
            f"Channel heights are similar (ratio ≈ {ratio:.2f}). Structure is not clearly dominated by one direction. Expect more back-and-forth.",
        )

    return (
        "Low",
        f"One scenario dominates (primary {h_p:.1f} pts vs alternate {h_a:.1f} pts). You likely have a cleaner structural bias.",
    )


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

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(
            f"<span class='spx-sub' style='font-size:0.95rem;'>{TAGLINE}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG:.3f} pts / 30m**")
        current_factor = st.session_state.get("contract_factor", 0.30)
        st.write(f"Contract factor: **{current_factor:.2f} × SPX move**")
        st.caption("Underlying channels are projected on a uniform 30-minute grid.")

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Underlying maintenance: 16:00–17:00 CT\n"
            "• Contracts maintenance: 16:00–19:00 CT\n"
            "• RTH grid: 08:30–14:30 CT (30m blocks)\n"
            "• You choose pivots. The app carries the structure."
        )

    # --- HERO ---
    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "📐 Contract Line Setup",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # ============================
    # TAB 1: RAILS + STACKS
    # ============================
    with tabs[0]:
        card(
            "Rails + Stacks",
            "Define your two key pivots from the previous regular session, build both ascending and descending rails, and stack them to see where reversals are likely.",
            badge="Structure Engine",
            icon="🧱",
        )

        section_header("Underlying Pivots (Previous RTH)")
        st.markdown(
            """
            <div class="spx-sub">
            Pick the <strong>structural high and low pivots</strong> from the previous regular session on your line chart.
            These do not have to be the absolute wick extremes, but the main turning points that defined the day.
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
                key="pivot_high_price",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(12, 0),
                step=1800,
                key="pivot_high_time",
            )
        with c2:
            st.markdown("**Low Pivot**")
            low_price = st.number_input(
                "Low pivot price",
                value=6600.0,
                step=0.25,
                key="pivot_low_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(14, 30),
                step=1800,
                key="pivot_low_time",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        build_col, _ = st.columns([1, 3])
        with build_col:
            if st.button("⚡ Build Rails", key="build_rails_btn", use_container_width=True):
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
                st.session_state["rails_asc_h"] = h_asc
                st.session_state["rails_desc_h"] = h_desc

                # Auto primary scenario: whichever has larger height
                primary_auto = "Ascending" if h_asc >= h_desc else "Descending"
                st.session_state["primary_mode_auto"] = primary_auto

                st.success("Rails generated. Scroll down to inspect channels and stacks.")

        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_h")
        h_desc = st.session_state.get("rails_desc_h")

        section_header("Underlying Rails • RTH 08:30–14:30 CT")

        if df_asc is None or df_desc is None:
            st.info("Build rails to see the ascending and descending projections.")
        else:
            st.markdown("### Ascending Channel (Structure)")
            col_a1, col_a2 = st.columns([3, 1])
            with col_a1:
                st.dataframe(df_asc, use_container_width=True, hide_index=True, height=300)
            with col_a2:
                st.markdown(metric_card("Channel Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)

            st.markdown("### Descending Channel (Structure)")
            col_d1, col_d2 = st.columns([3, 1])
            with col_d1:
                st.dataframe(df_desc, use_container_width=True, hide_index=True, height=300)
            with col_d2:
                st.markdown(metric_card("Channel Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)

            section_header("Stacked Channels (±1 Height)")
            primary_auto = st.session_state.get("primary_mode_auto", "Ascending")
            st.markdown(
                f"""
                <div class="muted">
                Auto-detected dominant structure from your pivots: <strong>{primary_auto}</strong>.<br>
                You can override which scenario you treat as primary for the day.
                </div>
                """,
                unsafe_allow_html=True,
            )

            primary_choice = st.radio(
                "Primary structural scenario",
                ["Ascending", "Descending"],
                index=0 if primary_auto == "Ascending" else 1,
                key="primary_struct_choice",
            )

            if primary_choice == "Ascending":
                base_df = df_asc
                base_h = h_asc
                alt_h = h_desc
            else:
                base_df = df_desc
                base_h = h_desc
                alt_h = h_asc

            stacked_df = build_stacked_from_channel(base_df, base_h)
            st.dataframe(stacked_df, use_container_width=True, hide_index=True, height=320)

            # Store only derived data – DO NOT overwrite widget keys
            st.session_state["stacked_df_primary"] = stacked_df
            st.session_state["primary_channel_height"] = base_h
            st.session_state["primary_mode"] = primary_choice
            st.session_state["alt_channel_height"] = alt_h

        end_card()

    # ============================
    # TAB 2: CONTRACT LINE
    # ============================
    with tabs[1]:
        card(
            "Contract Line Setup",
            "Use two contract prices to define a simple structural line on the same time grid as the rails, and set a global contract factor that tells you how much the option tends to move per SPX point.",
            badge="Contract Engine",
            icon="📐",
        )

        section_header("Global Contract Factor")
        st.markdown(
            """
            <div class="spx-sub">
            This is your rule-of-thumb mapping from SPX points to contract points.
            For example, <strong>0.30</strong> means “a full channel of 100 SPX points tends to give me about 30 points in this contract.”
            You can calibrate this from your own trade history.
            </div>
            """,
            unsafe_allow_html=True,
        )

        default_cf = st.session_state.get("contract_factor", 0.30)
        cf = st.slider(
            "Contract factor (× SPX move)",
            min_value=0.05,
            max_value=1.00,
            value=float(default_cf),
            step=0.05,
            key="contract_factor_widget",
        )
        st.session_state["contract_factor"] = cf

        section_header("Contract Line (Optional Structural Baseline)")
        st.markdown(
            """
            <div class="spx-sub">
            This line is <em>not</em> a full options model. It is a simple linear baseline defined by two prices of the same contract
            at two times. It gives you a structural reference so that you can compare what the market actually paid you versus
            what the “calm” line would have done.
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
                value=dtime(7, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
            anchor_b_price = st.number_input(
                "Contract price at Anchor B",
                value=8.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        build_c_col, _ = st.columns([1, 3])
        with build_c_col:
            if st.button("⚡ Build Contract Line", key="build_contract_btn", use_container_width=True):
                df_contract, slope_contract = build_contract_projection(
                    anchor_a_time=anchor_a_time,
                    anchor_a_price=anchor_a_price,
                    anchor_b_time=anchor_b_time,
                    anchor_b_price=anchor_b_price,
                )
                st.session_state["contract_df"] = df_contract
                st.session_state["contract_slope"] = slope_contract
                st.success("Contract line generated. Check the Daily Foresight tab for estimators.")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        section_header("Contract Projection • RTH 08:30–14:30 CT")
        if df_contract is None:
            st.info("Build a contract line to see projected contract prices on the RTH grid.")
        else:
            c_top, c_side = st.columns([3, 1])
            with c_top:
                st.dataframe(df_contract, use_container_width=True, hide_index=True, height=320)
            with c_side:
                st.markdown(
                    metric_card("Contract Slope", f"{slope_contract:+.4f} / 30m"),
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "📥 Download contract CSV",
                    df_contract.to_csv(index=False).encode(),
                    "contract_projection.csv",
                    "text/csv",
                    key="dl_contract",
                    use_container_width=True,
                )

        end_card()

    # ============================
    # TAB 3: DAILY FORESIGHT
    # ============================
    with tabs[2]:
        card(
            "Daily Foresight",
            "Primary rails, stacked channels, contract factor and contract line pulled together into one simple playbook.",
            badge="Foresight Engine",
            icon="🔮",
        )

        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_h")
        h_desc = st.session_state.get("rails_desc_h")
        primary_mode = st.session_state.get("primary_mode")
        stacked_df_primary = st.session_state.get("stacked_df_primary")
        primary_h = st.session_state.get("primary_channel_height")
        alt_h = st.session_state.get("alt_channel_height")
        df_contract = st.session_state.get("contract_df")
        contract_factor = st.session_state.get("contract_factor", 0.30)

        if df_asc is None or df_desc is None or stacked_df_primary is None or primary_mode is None:
            st.warning("Build your rails and stacked channels first in the Rails Setup tab.")
            end_card()
        else:
            # Structure Summary
            section_header("Structure Summary")
            if primary_mode == "Ascending":
                primary_label = "Ascending (trend-up structure)"
            else:
                primary_label = "Descending (trend-down structure)"

            alt_label = "Descending" if primary_mode == "Ascending" else "Ascending"

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    metric_card("Primary Scenario", primary_label),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card("Primary Height", f"{primary_h:.2f} pts" if primary_h is not None else "—"),
                    unsafe_allow_html=True,
                )
            with c3:
                if alt_h is not None:
                    st.markdown(
                        metric_card(f"{alt_label} Height", f"{alt_h:.2f} pts"),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        metric_card(f"{alt_label} Height", "N/A"),
                        unsafe_allow_html=True,
                    )

            # Chop Detector
            section_header("Chop Detector (Structure-Only View)")
            col_l, col_r = st.columns(2)
            with col_l:
                min_height_for_trend = st.slider(
                    "Minimum channel height for trend (pts)",
                    min_value=20.0,
                    max_value=200.0,
                    value=60.0,
                    step=5.0,
                    key="chop_min_height",
                )
            with col_r:
                max_height_ratio_for_clean_trend = st.slider(
                    "Max height ratio for clean trend (alt / primary)",
                    min_value=0.50,
                    max_value=1.00,
                    value=0.80,
                    step=0.05,
                    key="chop_height_ratio",
                )

            chop_level, chop_reason = detect_chop(
                primary_h, alt_h, min_height_for_trend, max_height_ratio_for_clean_trend
            )

            if chop_level == "High":
                st.warning(chop_reason)
            elif chop_level == "Moderate":
                st.info(chop_reason)
            elif chop_level == "Low":
                st.success(chop_reason)
            else:
                st.info(chop_reason)

            # Contract move summary
            section_header("Contract Move Estimate (Channel-Based)")
            if primary_h is not None:
                full_move = primary_h * contract_factor
                stack_move = 2 * primary_h * contract_factor
            else:
                full_move = 0.0
                stack_move = 0.0

            c1c, c2c, c3c = st.columns(3)
            with c1c:
                st.markdown(
                    metric_card("Contract Factor", f"{contract_factor:.2f} × SPX"),
                    unsafe_allow_html=True,
                )
            with c2c:
                st.markdown(
                    metric_card("Full Channel Δ", f"{full_move:.2f} pts"),
                    unsafe_allow_html=True,
                )
            with c3c:
                st.markdown(
                    metric_card("Stacked Δ (2H)", f"{stack_move:.2f} pts"),
                    unsafe_allow_html=True,
                )

            st.markdown(
                """
                <div class="muted">
                <strong>How to read this:</strong> If SPX gives you a clean full move from the lower rail to the upper rail
                in the primary structure, your working assumption is roughly this contract change.
                If price escapes the main channel and tags a stacked rail (±1H), use the 2H estimate as a guide.
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Bias & Plan
            section_header("Bias & Daily Plan (Structure-Only Rules)")
            if chop_level == "High":
                plan_text = (
                    "Structural chop risk is high. Treat the day as a candidate for standing aside "
                    "or trading only ultra-clean tests with very small size."
                )
            elif primary_mode == "Ascending":
                plan_text = (
                    "Primary structure is ascending. Core idea: look for long call ideas on bounces from the main lower rail "
                    "or the lower stacked rail, targeting the main upper rail or stacked upper rails. Only consider puts at clear "
                    "rejections near the upper or stacked upper rails if the tape confirms."
                )
            else:
                plan_text = (
                    "Primary structure is descending. Core idea: look for long put ideas on pushes into the main upper rail "
                    "or the upper stacked rail, targeting the main lower rail or stacked lower rails. Only consider calls at clear "
                    "rejections near the lower or stacked lower rails if the tape confirms."
                )

            st.markdown(f"<div class='muted'>{plan_text}</div>", unsafe_allow_html=True)

            # Time-Aligned Map + Contract Estimator
            section_header("Time-Aligned Map")
            if stacked_df_primary is None or stacked_df_primary.empty:
                st.info("Stacked rails not found. Build them first in Rails Setup.")
            else:
                df_struct = stacked_df_primary.copy()

                if df_contract is not None:
                    merged = df_struct.merge(df_contract, on="Time", how="left")
                else:
                    merged = df_struct.copy()
                    merged["Contract Price"] = float("nan")

                st.caption(
                    "Every row is a 30-minute RTH slot. Main Top/Main Bottom are your primary rails. "
                    "Top +1H / Bottom -1H are the stacked rails. Contract Price is the structural contract line if you built it."
                )
                st.dataframe(merged, use_container_width=True, hide_index=True, height=420)

                if df_contract is not None:
                    section_header("Contract Trade Estimator (Structural Line)")
                    times = merged["Time"].tolist()
                    if times:
                        col_e, col_x = st.columns(2)
                        with col_e:
                            entry_time = st.selectbox(
                                "Entry time (when you expect the rail touch)",
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

                        c1e, c2e, c3e = st.columns(3)
                        with c1e:
                            st.markdown(
                                metric_card("Entry Contract", f"{entry_contract:.2f}"),
                                unsafe_allow_html=True,
                            )
                        with c2e:
                            st.markdown(
                                metric_card("Exit Contract", f"{exit_contract:.2f}"),
                                unsafe_allow_html=True,
                            )
                        with c3e:
                            st.markdown(
                                metric_card("Projected P&L", f"{pnl_contract:+.2f} pts"),
                                unsafe_allow_html=True,
                            )

                        st.markdown(
                            """
                            <div class="muted">
                            <strong>How to use this:</strong> treat the line as the calm baseline. Your real fills will often
                            beat this line when volatility expands in your favour. When they do not, you know the day is stingy
                            and you can tighten expectations.
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

        end_card()

    # ============================
    # TAB 4: ABOUT
    # ============================
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Framework", icon="ℹ️")
        st.markdown(
            """
            <div class="spx-sub" style="font-size:0.98rem; line-height:1.8;">
            <p><strong>SPX Prophet</strong> is built around a simple conviction:</p>

            <p style="margin-top:8px;">
            <em>Price is not random. Institutions trade around structure. Your job is to see the structure clearly and
            let the tape tell you when it is active or when it is breaking.</em>
            </p>

            <ul style="margin-left:22px; margin-top:10px;">
              <li>Two pivots from the previous regular session define your <strong>structural rails</strong>.</li>
              <li>The same slope is projected as both <strong>ascending</strong> and <strong>descending</strong> channels.</li>
              <li>Stacked rails (±1 channel-height) show you where extension reversals are likely to form.</li>
              <li>A simple <strong>contract factor</strong> gives you a clean mapping from SPX points to contract points.</li>
              <li>An optional <strong>contract line</strong> lets you compare real fills to a calm, linear baseline.</li>
              <li>A basic <strong>chop detector</strong> warns you when structure is too tight or too balanced to push hard.</li>
            </ul>

            <p style="margin-top:10px;">
            None of this replaces your discretion. It takes the geometry you are already using in your head and pins it
            down on a 30-minute grid so you can plan with less noise and less emotion.
            </p>
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