# spx_prophet_app.py
# SPX Prophet — Where Structure Becomes Foresight.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Optional, Tuple

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."

# Core structural slope (SPX rails)
SLOPE_MAG = 0.475  # pts per 30 min

# Base date for 30m block indexing (just a fixed reference)
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 (3pm) CT


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
        padding-top: 2.5rem;
        padding-bottom: 4rem;
        max-width: 1400px;
    }

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
        margin-bottom: 0.4rem;
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

    /* HERO CENTERED */
    .hero-header {
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.12), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(59, 130, 246, 0.12), transparent 60%),
            linear-gradient(135deg, #ffffff, #fafbff);
        border-radius: 32px;
        padding: 32px 40px 36px 40px;
        margin-bottom: 32px;
        border: 2px solid rgba(99, 102, 241, 0.2);
        box-shadow:
            0 24px 60px -12px rgba(99, 102, 241, 0.15),
            0 16px 40px -8px rgba(0, 0, 0, 0.08),
            inset 0 2px 4px rgba(255, 255, 255, 0.9),
            inset 0 -2px 4px rgba(99, 102, 241, 0.05);
        overflow: hidden;
        animation: heroGlow 6s ease-in-out infinite;
        text-align: center;
    }

    @keyframes heroGlow {
        0%, 100% { box-shadow: 0 24px 60px -12px rgba(99, 102, 241, 0.15), 0 16px 40px -8px rgba(0, 0, 0, 0.08); }
        50% { box-shadow: 0 24px 60px -12px rgba(99, 102, 241, 0.25), 0 16px 40px -8px rgba(99, 102, 241, 0.12); }
    }

    .hero-title {
        font-size: 2.6rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 40%, #3b82f6 70%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.06em;
        line-height: 1.1;
        animation: titleFloat 3s ease-in-out infinite;
    }

    @keyframes titleFloat {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-3px); }
    }

    .hero-subtitle {
        font-size: 1.1rem;
        color: #64748b;
        margin-top: 8px;
        font-weight: 500;
        font-family: 'Poppins', sans-serif;
    }

    .hero-tagline {
        margin-top: 18px;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 10px 18px;
        border-radius: 999px;
        background:
            linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.12)),
            #ffffff;
        border: 2px solid rgba(16, 185, 129, 0.3);
        font-size: 0.83rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #047857;
        font-weight: 700;
    }

    .hero-tagline-dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: #10b981;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
        animation: pulse 1.8s ease-in-out infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(0.85); }
    }

    /* CARDS */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 8% 8%, rgba(99, 102, 241, 0.08), transparent 55%),
            radial-gradient(circle at 92% 92%, rgba(59, 130, 246, 0.08), transparent 55%),
            linear-gradient(135deg, #ffffff, #fefeff);
        border-radius: 28px;
        border: 2px solid rgba(148, 163, 184, 0.45);
        box-shadow:
            0 22px 55px -12px rgba(148, 163, 184, 0.5),
            0 10px 25px -8px rgba(15, 23, 42, 0.15),
            inset 0 1px 3px rgba(255, 255, 255, 0.9);
        padding: 28px 30px 30px 30px;
        margin-bottom: 32px;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }

    .spx-card:hover {
        transform: translateY(-4px);
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow:
            0 28px 70px -12px rgba(99, 102, 241, 0.25),
            0 14px 35px -10px rgba(15, 23, 42, 0.25);
    }

    .spx-card h4 {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 10px 0;
        letter-spacing: -0.03em;
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 8px 18px;
        border-radius: 999px;
        border: 1.5px solid rgba(99, 102, 241, 0.35);
        background:
            linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(59, 130, 246, 0.10)),
            #ffffff;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        color: #4f46e5;
        text-transform: uppercase;
        margin-bottom: 12px;
    }

    .spx-sub {
        color: #475569;
        font-size: 1rem;
        line-height: 1.7;
        font-weight: 400;
    }

    .section-header {
        font-size: 1.4rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 1.8rem 0 1rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid rgba(148, 163, 184, 0.5);
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .section-header::before {
        content: '';
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: linear-gradient(135deg, #6366f1, #22c55e);
        box-shadow:
            0 0 16px rgba(99, 102, 241, 0.7),
            0 3px 8px rgba(148, 163, 184, 0.9);
    }

    .spx-metric {
        position: relative;
        padding: 20px 20px;
        border-radius: 22px;
        background:
            radial-gradient(circle at top left, rgba(99, 102, 241, 0.12), transparent 70%),
            linear-gradient(135deg, #ffffff, #fefeff);
        border: 2px solid rgba(148, 163, 184, 0.7);
        box-shadow:
            0 18px 40px rgba(148, 163, 184, 0.35),
            inset 0 1px 2px rgba(255, 255, 255, 0.9);
        transition: all 0.25s ease;
    }

    .spx-metric:hover {
        transform: translateY(-3px);
        border-color: rgba(79, 70, 229, 0.8);
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
        font-size: 1.7rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #0f172a 0%, #4f46e5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(248,250,252,0.95));
        padding: 8px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.8);
        box-shadow:
            0 12px 35px rgba(148, 163, 184, 0.4),
            inset 0 1px 2px rgba(255, 255, 255, 0.9);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 8px 18px;
        color: #6b7280;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #4f46e5, #2563eb);
        color: #ffffff;
        box-shadow:
            0 10px 24px rgba(79, 70, 229, 0.4);
    }

    .muted {
        color: #475569;
        font-size: 0.95rem;
        line-height: 1.7;
        padding: 16px 18px;
        background:
            linear-gradient(135deg, rgba(148, 163, 184, 0.08), rgba(100, 116, 139, 0.06)),
            #ffffff;
        border-left: 3px solid #4f46e5;
        border-radius: 12px;
        margin: 16px 0;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.03);
    }

    .trade-stance-good {
        border-left-color: #16a34a !important;
    }
    .trade-stance-caution {
        border-left-color: #f59e0b !important;
    }
    .trade-stance-avoid {
        border-left-color: #ef4444 !important;
    }

    .app-footer {
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(148, 163, 184, 0.7);
        text-align: center;
        color: #6b7280;
        font-size: 0.9rem;
    }

    .stDataFrame {
        border-radius: 18px;
        overflow: hidden;
        box-shadow:
            0 18px 40px rgba(148, 163, 184, 0.5),
            0 10px 25px rgba(15, 23, 42, 0.25);
        border: 1px solid rgba(148, 163, 184, 0.8);
    }

    .stDataFrame div[data-testid="StyledTable"] {
        font-variant-numeric: tabular-nums;
        font-size: 0.9rem;
        font-family: 'JetBrains Mono', monospace;
        background: #ffffff;
    }

    .stDataFrame thead tr th {
        background: linear-gradient(135deg, rgba(79, 70, 229, 0.16), rgba(59, 130, 246, 0.16)) !important;
        color: #111827 !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12em !important;
        font-size: 0.7rem !important;
        padding: 10px 8px !important;
    }

    .stDataFrame tbody tr:hover {
        background: rgba(129, 140, 248, 0.06) !important;
    }

    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 1.5px solid rgba(148, 163, 184, 0.9) !important;
        border-radius: 12px !important;
        color: #111827 !important;
        padding: 10px 12px !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: #4f46e5 !important;
        box-shadow:
            0 0 0 2px rgba(129, 140, 248, 0.35) !important;
    }

    .stButton>button {
        background: linear-gradient(135deg, #4f46e5, #2563eb);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 10px 22px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.12em;
        box-shadow:
            0 10px 26px rgba(79, 70, 229, 0.4),
            0 4px 10px rgba(15, 23, 42, 0.25);
        text-transform: uppercase;
    }

    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow:
            0 14px 30px rgba(79, 70, 229, 0.5);
    }

    label {
        font-size: 0.85rem !important;
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
            <div class="hero-tagline">
                <div class="hero-tagline-dot"></div>
                SYSTEM ACTIVE • STRUCTURE FIRST
            </div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">{TAGLINE}</p>
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


# ===============================
# TIME / BLOCK HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map a clock time (CT) to a datetime on or after BASE_DATE.
    You will feed it previous-day RTH times (e.g., 09:30, 11:00, 14:30).
    """
    base_day = BASE_DATE.date()
    return datetime(base_day.year, base_day.month, base_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    """
    Lock a datetime to the nearest 30-min block using 15/45 thresholds.
    """
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """
    Generate RTH slots 08:30–14:30 CT on the NEXT day after BASE_DATE.
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
    Build rails using two pivots on a 30-minute grid.
    slope_sign: +1 for ascending, -1 for descending.
    """
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))

    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

    # b = y - s*k at the pivot
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
    return df, float(round(channel_height, 2))


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

    # ---- SIDEBAR ----
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(
            f"<span class='spx-sub' style='font-size:0.95rem;'>{TAGLINE}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG:.3f} pts / 30m**")
        contract_factor = st.number_input(
            "Contract factor (contract move per 1 SPX point)",
            min_value=0.05,
            max_value=1.0,
            step=0.05,
            value=0.30,
            format="%.2f",
            key="contract_factor",
            help="If SPX moves 100 pts, this factor × 100 is your expected contract move.",
        )
        min_channel_height = st.number_input(
            "Min channel height to trade (H, pts)",
            min_value=10.0,
            max_value=200.0,
            step=5.0,
            value=40.0,
            format="%.1f",
            key="min_channel_height",
            help="Below this H, the day is treated as structurally small / likely choppy.",
        )

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Underlying maintenance: 16:00–17:00 CT  \n"
            "• Contracts maintenance: 16:00–19:00 CT  \n"
            "• RTH grid: 08:30–14:30 CT (30m blocks)  \n"
            "• You choose pivots. The app carries the structure."
        )

    # ---- HERO ----
    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "📐 Contract Factor",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # =========================================
    # TAB 1: RAILS SETUP
    # =========================================
    with tabs[0]:
        card(
            "Rails + Stacks",
            "Define your two key pivots from the previous RTH session, build both ascending and "
            "descending rails, and stack them to see where reversals are likely.",
            badge="Structure Engine",
        )

        section_header("Underlying Pivots (Previous RTH)")
        st.markdown(
            """
            <div class="spx-sub">
            Pick the <strong>structural high and low pivots</strong> from the previous regular session on your line chart.
            These do not have to be the absolute wicks. They are the main turning points that framed the day.
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**High Pivot**")
            high_price = st.number_input(
                "High pivot price",
                value=6800.0,
                step=0.5,
                key="high_pivot_price",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(12, 0),
                step=1800,
                key="high_pivot_time",
            )
        with c2:
            st.markdown("**Low Pivot**")
            low_price = st.number_input(
                "Low pivot price",
                value=6725.0,
                step=0.5,
                key="low_pivot_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(14, 30),
                step=1800,
                key="low_pivot_time",
            )

        st.markdown("")
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("⚡ Build Rails", use_container_width=True, key="build_rails_btn"):
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
                st.session_state["asc_df"] = df_asc
                st.session_state["asc_h"] = h_asc
                st.session_state["desc_df"] = df_desc
                st.session_state["desc_h"] = h_desc
                st.success("Rails generated successfully. Review below and open Daily Foresight.")

        df_asc = st.session_state.get("asc_df")
        df_desc = st.session_state.get("desc_df")
        h_asc = st.session_state.get("asc_h")
        h_desc = st.session_state.get("desc_h")

        section_header("Underlying Rails • RTH 08:30–14:30 CT")

        if df_asc is None or df_desc is None:
            st.info("Build rails first to see projections.")
        else:
            st.markdown("### Ascending Channel (Structure)")
            c_top = st.columns([3, 1])
            with c_top[0]:
                st.dataframe(df_asc, use_container_width=True, hide_index=True, height=280)
            with c_top[1]:
                st.markdown(
                    metric_card("Channel Height", f"{h_asc:.2f} pts"),
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "📥 Download Ascending CSV",
                    df_asc.to_csv(index=False).encode(),
                    "spx_ascending_rails.csv",
                    "text/csv",
                    key="dl_asc",
                    use_container_width=True,
                )

            st.markdown("### Descending Channel (Structure)")
            c_bot = st.columns([3, 1])
            with c_bot[0]:
                st.dataframe(df_desc, use_container_width=True, hide_index=True, height=280)
            with c_bot[1]:
                st.markdown(
                    metric_card("Channel Height", f"{h_desc:.2f} pts"),
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "📥 Download Descending CSV",
                    df_desc.to_csv(index=False).encode(),
                    "spx_descending_rails.csv",
                    "text/csv",
                    key="dl_desc",
                    use_container_width=True,
                )

        st.markdown(
            """
            <div class="muted">
            <strong>Reminder:</strong> the same pivots generate both ascending and descending grids.
            You decide which one is primary in the Daily Foresight tab. The other becomes the alternate frame.
            Stacked rails (±1H) will be displayed there.
            </div>
            """,
            unsafe_allow_html=True,
        )

        end_card()

    # =========================================
    # TAB 2: CONTRACT FACTOR (EXPLANATION)
    # =========================================
    with tabs[1]:
        card(
            "Contract Factor",
            "One simple knob to map structural SPX moves into contract targets.",
            badge="Contract Engine",
        )

        section_header("How the Contract Factor Works")
        st.markdown(
            f"""
            <div class="spx-sub">
            <p>
            Let <code>H</code> be your channel height in SPX points and <code>f</code> your contract factor.
            A full rail-to-rail swing is then:
            </p>
            <ul>
              <li>Underlying move ≈ <strong>H</strong> points</li>
              <li>Expected contract move ≈ <strong>f × H</strong> points</li>
            </ul>
            <p>
            For example, if <strong>H = 80</strong> and <strong>f = {st.session_state.get("contract_factor", 0.30):.2f}</strong>,
            a clean bottom-to-top move suggests about <strong>{st.session_state.get("contract_factor", 0.30) * 80:.1f} pts</strong> of contract change.
            The rail-based estimator in the Daily Foresight tab uses exactly this logic.
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        section_header("Quick Calculator")
        calc_h = st.number_input(
            "Hypothetical channel height H (pts)",
            min_value=10.0,
            max_value=250.0,
            step=5.0,
            value=80.0,
            format="%.1f",
            key="calc_h",
        )
        cf = st.session_state.get("contract_factor", 0.30)
        move_1h = cf * calc_h
        move_2h = cf * 2 * calc_h

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(metric_card("H (Rail-to-Rail)", f"{calc_h:.1f} pts"), unsafe_allow_html=True)
        with c2:
            st.markdown(
                metric_card("Contract Move (1H)", f"{move_1h:.1f} pts"),
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                metric_card("Contract Move (2H)", f"{move_2h:.1f} pts"),
                unsafe_allow_html=True,
            )

        st.markdown(
            """
            <div class="muted">
            <strong>Note:</strong> the factor does not try to model IV, theta, or skew.
            It gives you a conservative structural target. The tape can always pay more than the structure.
            </div>
            """,
            unsafe_allow_html=True,
        )
        end_card()

    # =========================================
    # TAB 3: DAILY FORESIGHT
    # =========================================
    with tabs[2]:
        card(
            "Daily Foresight",
            "Rails, stacks, stance, and rail-based contract exits — all on one page.",
            badge="Playbook",
        )

        df_asc = st.session_state.get("asc_df")
        df_desc = st.session_state.get("desc_df")
        h_asc = st.session_state.get("asc_h")
        h_desc = st.session_state.get("desc_h")

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("No rails found. Go to 'Rails Setup' first and build the structure.")
            end_card()
        else:
            # Choose primary scenario (no writing to session_state to avoid widget conflict)
            section_header("Primary Structural Scenario")
            # Simple default: pick the larger channel as primary
            default_index = 0 if h_asc >= h_desc else 1
            primary_choice = st.radio(
                "Which channel are you treating as primary today?",
                ["Ascending", "Descending"],
                index=default_index,
                horizontal=True,
                key="primary_choice",
            )

            if primary_choice == "Ascending":
                df_primary = df_asc.copy()
                primary_h = h_asc
                df_alt = df_desc.copy()
                alt_h = h_desc
            else:
                df_primary = df_desc.copy()
                primary_h = h_desc
                df_alt = df_asc.copy()
                alt_h = h_asc

            # Build stacked rails for primary
            df_primary["Top +1H"] = df_primary["Top Rail"] + primary_h
            df_primary["Bottom -1H"] = df_primary["Bottom Rail"] - primary_h

            # Attach alt rails (for context only, not used in estimator)
            df_primary["Alt Top"] = df_alt["Top Rail"]
            df_primary["Alt Bottom"] = df_alt["Bottom Rail"]

            contract_factor = st.session_state.get("contract_factor", 0.30)
            min_channel_height = st.session_state.get("min_channel_height", 40.0)

            # ----- Trade stance (simple traffic light based on structure) -----
            section_header("Structure Summary")

            # Basic stance rules
            if primary_h < min_channel_height:
                stance = "Stand Aside"
                stance_class = "trade-stance-avoid"
                stance_msg = (
                    "Primary channel height is smaller than your minimum threshold. "
                    "Structurally this is a narrow day — treat it as likely chop."
                )
            else:
                # If alt height is very different from primary, mark as caution
                if alt_h > 0 and abs(primary_h - alt_h) / primary_h > 0.5:
                    stance = "Caution"
                    stance_class = "trade-stance-caution"
                    stance_msg = (
                        "Ascending and descending structures disagree strongly. "
                        "Expect a higher chance of fake breaks and mixed flow."
                    )
                else:
                    stance = "OK"
                    stance_class = "trade-stance-good"
                    stance_msg = (
                        "Channel height is healthy and both structures are in a similar range. "
                        "Good environment to look for clean rail-to-rail plays."
                    )

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(
                    metric_card("Primary Scenario", primary_choice),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card("Primary H", f"{primary_h:.2f} pts"),
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    metric_card("Alt H", f"{alt_h:.2f} pts"),
                    unsafe_allow_html=True,
                )
            with c4:
                st.markdown(
                    metric_card("Contract Factor", f"{contract_factor:.2f}"),
                    unsafe_allow_html=True,
                )

            st.markdown(
                f"""
                <div class="muted {stance_class}">
                <strong>Trade stance: {stance}</strong> — {stance_msg}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ----- Explicit Stacked Channels section -----
            section_header("Stacked Channels (±1H)")

            first_row = df_primary.iloc[0]  # 08:30 row
            top_main_0830 = first_row["Top Rail"]
            bottom_main_0830 = first_row["Bottom Rail"]
            top_stack_0830 = first_row["Top +1H"]
            bottom_stack_0830 = first_row["Bottom -1H"]

            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.markdown(
                    metric_card("Main Top @ 08:30", f"{top_main_0830:.2f}"),
                    unsafe_allow_html=True,
                )
            with sc2:
                st.markdown(
                    metric_card("Stacked Top (+1H)", f"{top_stack_0830:.2f}"),
                    unsafe_allow_html=True,
                )
            with sc3:
                st.markdown(
                    metric_card("Stacked Bottom (−1H)", f"{bottom_stack_0830:.2f}"),
                    unsafe_allow_html=True,
                )

            st.markdown(
                """
                <div class="muted">
                <strong>How to read this:</strong>
                The main top/bottom rails define your core channel.
                When price escapes, the stacked rails (+1H above, −1H below) mark the typical zones where
                large players start fading the move and steering it back toward the body of the channel.
                These stacked rails also appear in the time-aligned map as <code>Top +1H</code> and <code>Bottom -1H</code>.
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ----- Rail Playbook -----
            section_header("Rail Playbook")

            if primary_choice == "Ascending":
                bias_text = (
                    "<strong>Bias:</strong> price tends to respect rising rails. "
                    "Calls from the lower rail toward the upper, puts from the upper into the body."
                )
            else:
                bias_text = (
                    "<strong>Bias:</strong> price tends to respect falling rails. "
                    "Puts from the upper rail toward the lower, calls from the lower into the body."
                )

            st.markdown(
                f"""
                <div class="spx-sub">
                <p>{bias_text}</p>
                <ul>
                  <li>Primary swing: inside the main channel, rail-to-rail (1H).</li>
                  <li>Extension play: when price escapes, look to the stacked rail (Top +1H or Bottom -1H) for a potential reversal (2H total move).</li>
                </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ----- Rail-based Contract Estimator -----
            section_header("Rail-based Contract Estimator")

            if primary_h <= 0:
                st.info("Channel height is zero or invalid. Rebuild rails.")
            else:
                side = st.radio(
                    "Planned trade",
                    ["Long Call (bottom → top)", "Long Put (top → bottom)"],
                    index=0,
                    key="rail_trade_side",
                    horizontal=True,
                )

                swing_type = st.radio(
                    "Move size",
                    ["Full channel (1H)", "Extension to stacked rail (2H)"],
                    index=0,
                    key="rail_swing_type",
                    horizontal=True,
                )

                entry_contract = st.number_input(
                    "Your planned / actual entry contract price at rail touch",
                    value=10.0,
                    step=0.1,
                    key="rail_entry_price",
                )

                multiplier = 2.0 if "2H" in swing_type else 1.0
                dir_sign = +1 if "Long Call" in side else -1

                projected_change = dir_sign * contract_factor * primary_h * multiplier
                projected_exit = entry_contract + projected_change

                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    st.markdown(
                        metric_card("Entry Contract", f"{entry_contract:.2f}"),
                        unsafe_allow_html=True,
                    )
                with cc2:
                    st.markdown(
                        metric_card("Projected Exit", f"{projected_exit:.2f}"),
                        unsafe_allow_html=True,
                    )
                with cc3:
                    st.markdown(
                        metric_card("Projected P&L", f"{projected_change:+.2f} pts"),
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    """
                    <div class="muted">
                    <strong>How to use this:</strong>
                    Enter the contract price where you expect to buy at the rail touch.
                    The estimator multiplies your channel height by your contract factor to give you a conservative
                    exit target for a full rail-to-rail swing (1H) or a stacked extension (2H).
                    Real moves can pay more if volatility expands in your favour.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # ----- Time-aligned Map -----
            section_header("Time-Aligned Map (Rails + Stacks)")

            display_df = df_primary[[
                "Time",
                "Top Rail",
                "Bottom Rail",
                "Top +1H",
                "Bottom -1H",
                "Alt Top",
                "Alt Bottom",
            ]].copy()

            st.caption(
                "Every row is a 30-minute RTH slot. Primary rails define your core swing. "
                "Stacked rails (+1H / −1H) mark likely reversal zones when price escapes the main channel. "
                "Alt rails show the opposing structural frame."
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=420)

            st.markdown(
                """
                <div class="muted">
                <strong>Reading this grid:</strong>
                It does not tell you when price will touch a rail.
                It tells you what your structure expects the rails to be worth if the tag happens at a given time.
                You bring the tape reading and patience. The app brings the map.
                </div>
                """,
                unsafe_allow_html=True,
            )

        end_card()

    # =========================================
    # TAB 4: ABOUT
    # =========================================
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Overview")

        st.markdown(
            """
            <div class="spx-sub">
            <p>SPX Prophet is built around one simple conviction:</p>
            <p style="font-size:1.05rem; color:#4f46e5; font-weight:600; margin:12px 0;">
            Two pivots define your rails. The slope carries that structure into the next day.
            Contracts follow the structure, not your emotions.
            </p>
            <ul>
              <li>Rails are projected with a fixed structural slope of ±0.475 points per 30 minutes.</li>
              <li>You pick the structural high and low pivots from the previous RTH session.</li>
              <li>The app builds both ascending and descending channels, plus stacked rails at ±1H.</li>
              <li>A single contract factor converts SPX rail-to-rail moves into realistic contract targets.</li>
            </ul>
            <p>
            This is not a full options model with greeks and IV curves.
            It is a clean structural map so that when price returns to your rails, you are not guessing.
            You already know the lane, the distance, and a conservative target for your contracts.
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        end_card()

    st.markdown(
        '<div class="app-footer">© 2025 SPX Prophet • Where Structure Becomes Foresight.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()