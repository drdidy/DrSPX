import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional, Dict, Any

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."

SLOPE_MAG = 0.475        # pts per 30m for rails
CONTRACT_FACTOR = 0.33   # 0.33 × channel move for contract expectation
BASE_DATE = datetime(2000, 1, 1, 15, 0)


# ===============================
# STUNNING LIGHT UI
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.06), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.06), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 40%, #eef2f7 70%, #f8fafc 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3.5rem;
        max-width: 1400px;
    }

    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.08), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.4);
        box-shadow:
            8px 0 30px rgba(15, 23, 42, 0.05),
            4px 0 16px rgba(15, 23, 42, 0.03);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.75rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 40%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.4rem;
        letter-spacing: -0.03em;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.7) 40%,
            rgba(148, 163, 184, 0.7) 60%,
            transparent 100%);
    }

    [data-testid="stSidebar"] h4 {
        color: #64748b;
        font-size: 0.9rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-top: 1.7rem;
        margin-bottom: 0.8rem;
    }

    .hero-shell {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 2.2rem;
    }

    .hero-header {
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(129, 140, 248, 0.12), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(59, 130, 246, 0.10), transparent 60%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 26px;
        padding: 26px 32px 22px 32px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 24px 60px -16px rgba(15, 23, 42, 0.18),
            0 10px 30px -18px rgba(15, 23, 42, 0.28),
            inset 0 1px 0 rgba(255, 255, 255, 0.8);
        max-width: 720px;
        text-align: center;
        overflow: hidden;
    }

    .hero-title {
        font-size: 2.4rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #1d4ed8 40%, #0ea5e9 80%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.06em;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        color: #64748b;
        margin-top: 4px;
        margin-bottom: 0;
        font-weight: 500;
    }

    .hero-chip-row {
        display: flex;
        gap: 10px;
        justify-content: center;
        margin-top: 16px;
        flex-wrap: wrap;
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 7px 15px;
        font-size: 0.78rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        border: 1px solid rgba(22, 163, 74, 0.5);
        background:
            linear-gradient(135deg, rgba(22, 163, 74, 0.12), rgba(34, 197, 94, 0.08)),
            #f0fdf4;
        color: #15803d;
        font-weight: 700;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 10px rgba(22, 163, 74, 0.7);
    }

    .soft-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 7px 15px;
        font-size: 0.78rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        border: 1px solid rgba(79, 70, 229, 0.3);
        background:
            linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(59, 130, 246, 0.04)),
            #eef2ff;
        color: #4f46e5;
        font-weight: 700;
    }

    .soft-pill span {
        font-size: 0.75rem;
    }

    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 10% 0%, rgba(129, 140, 248, 0.12), transparent 55%),
            radial-gradient(circle at 100% 100%, rgba(56, 189, 248, 0.08), transparent 60%),
            linear-gradient(145deg, #ffffff, #f9fafb);
        border-radius: 24px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 22px 50px -18px rgba(15, 23, 42, 0.22),
            0 10px 25px -18px rgba(15, 23, 42, 0.26),
            inset 0 1px 0 rgba(255, 255, 255, 0.8);
        padding: 26px 26px 22px 26px;
        margin-bottom: 26px;
        overflow: hidden;
    }

    .spx-card h4 {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #1d4ed8 60%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 6px 0;
    }

    .spx-sub {
        color: #475569;
        font-size: 0.98rem;
        line-height: 1.7;
        font-weight: 400;
    }

    .section-header {
        font-size: 1.2rem;
        font-weight: 700;
        font-family: 'Poppins', sans-serif;
        color: #0f172a;
        margin: 1.6rem 0 0.7rem 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .section-header::before {
        content: '';
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        box-shadow: 0 0 12px rgba(79, 70, 229, 0.8);
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 16px;
        margin: 12px 0 8px 0;
    }

    .spx-metric {
        position: relative;
        padding: 16px 16px 14px 16px;
        border-radius: 18px;
        background:
            linear-gradient(135deg, rgba(248, 250, 252, 1), rgba(241, 245, 249, 1));
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow:
            0 8px 22px rgba(15, 23, 42, 0.07),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
    }

    .spx-metric-label {
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .spx-metric-value {
        font-size: 1.4rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #0f172a;
    }

    .muted {
        color: #475569;
        font-size: 0.95rem;
        line-height: 1.7;
        padding: 14px 16px;
        background:
            linear-gradient(135deg, rgba(248, 250, 252, 1), rgba(241, 245, 249, 1));
        border-left: 3px solid #4f46e5;
        border-radius: 12px;
        margin: 14px 0 6px 0;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
    }

    .decision-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 7px 14px;
        font-size: 0.78rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        font-weight: 700;
    }

    .decision-good {
        background: #ecfdf3;
        color: #166534;
        border: 1px solid rgba(22, 163, 74, 0.45);
    }

    .decision-caution {
        background: #fffbeb;
        color: #92400e;
        border: 1px solid rgba(245, 158, 11, 0.55);
    }

    .decision-bad {
        background: #fef2f2;
        color: #b91c1c;
        border: 1px solid rgba(248, 113, 113, 0.7);
    }

    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 0.55rem 1.6rem;
        font-weight: 700;
        font-size: 0.86rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        box-shadow:
            0 10px 30px rgba(59, 130, 246, 0.35),
            inset 0 1px 0 rgba(255, 255, 255, 0.3);
        cursor: pointer;
        transition: all 0.25s ease;
    }

    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-1px);
        box-shadow:
            0 12px 32px rgba(59, 130, 246, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.4);
    }

    .stButton>button:active, .stDownloadButton>button:active {
        transform: translateY(0px) scale(0.99);
        box-shadow:
            0 8px 20px rgba(59, 130, 246, 0.35),
            inset 0 1px 0 rgba(255, 255, 255, 0.3);
    }

    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        border-radius: 14px !important;
        color: #0f172a !important;
        padding: 0.55rem 0.7rem !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    label {
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        color: #475569 !important;
        margin-bottom: 4px !important;
    }

    .app-footer {
        margin-top: 2.8rem;
        padding-top: 1.1rem;
        border-top: 1px solid rgba(148, 163, 184, 0.6);
        text-align: center;
        color: #64748b;
        font-size: 0.9rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown(
        f"""
        <div class="hero-shell">
          <div class="hero-header">
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">{TAGLINE}</p>
            <div class="hero-chip-row">
              <div class="status-pill">
                <div class="status-dot"></div>
                <span>SYSTEM ACTIVE</span>
              </div>
              <div class="soft-pill">
                <span>STRUCTURE FIRST</span>
                <span>EMOTION LAST</span>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, sub: Optional[str] = None):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str) -> str:
    return f"""
    <div class='spx-metric'>
      <div class='spx-metric-label'>{label}</div>
      <div class='spx-metric-value'>{value}</div>
    </div>
    """


def section_header(text: str):
    st.markdown(f"<div class='section-header'>{text}</div>", unsafe_allow_html=True)


# ===============================
# TIME / BLOCK HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
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


def add_stacked_levels(df: pd.DataFrame, height: float) -> pd.DataFrame:
    if df is None or height is None:
        return df
    df = df.copy()
    df["Top +1H"] = (df["Top Rail"] + height).round(2)
    df["Bottom +1H"] = (df["Bottom Rail"] + height).round(2)
    df["Top -1H"] = (df["Top Rail"] - height).round(2)
    df["Bottom -1H"] = (df["Bottom Rail"] - height).round(2)
    return df


# ===============================
# DAY CLASSIFICATION / STAND ASIDE
# ===============================

def classify_day(
    asc_height: Optional[float],
    desc_height: Optional[float],
    contract_factor: float = CONTRACT_FACTOR,
) -> Dict[str, Any]:
    result = {
        "status": "Insufficient",
        "label": "Not Ready",
        "reason_lines": ["Build both ascending and descending channels first."],
        "primary": None,
        "symmetry_pct": None,
        "primary_height": None,
        "secondary_height": None,
        "primary_name": None,
    }

    if asc_height is None or desc_height is None:
        return result

    primary_name = "Ascending" if asc_height >= desc_height else "Descending"
    primary_height = max(asc_height, desc_height)
    secondary_height = min(asc_height, desc_height)

    avg_width = (asc_height + desc_height) / 2.0 if (asc_height and desc_height) else primary_height
    diff = abs(asc_height - desc_height)
    symmetry_pct = (diff / avg_width * 100.0) if avg_width > 0 else 0.0

    est_contract_move = primary_height * contract_factor

    reasons = []

    # Hard stand-aside conditions
    hard_filters = []

    if avg_width < 55:
        hard_filters.append("Channel width is very small (< 55 pts). Likely a chop / scalp day.")

    if symmetry_pct > 22:
        hard_filters.append(
            f"Strong asymmetry between up / down channels ({symmetry_pct:.1f}% difference)."
        )

    if est_contract_move < 9.9:
        hard_filters.append(
            f"Estimated contract move for a full rail-to-rail swing is small ({est_contract_move:.1f} units)."
        )

    # Soft caution conditions
    soft_filters = []

    if 15 < symmetry_pct <= 22:
        soft_filters.append(
            f"Moderate asymmetry between channels ({symmetry_pct:.1f}% difference)."
        )

    if 55 <= avg_width < 65:
        soft_filters.append(
            f"Channel width is modest ({avg_width:.1f} pts). Expect tighter rotations."
        )

    status = "OK"
    label = "High Quality"

    if hard_filters:
        status = "StandAside"
        label = "Stand Aside"
        reasons.extend(hard_filters)
        if soft_filters:
            reasons.append("")
            reasons.append("Additional notes:")
            reasons.extend(soft_filters)
    elif soft_filters:
        status = "Caution"
        label = "Tradable but Cautious"
        reasons.extend(soft_filters)
    else:
        reasons.append(
            f"Channels are reasonably symmetric ({symmetry_pct:.1f}% difference) with healthy width ({avg_width:.1f} pts)."
        )

    result.update(
        {
            "status": status,
            "label": label,
            "reason_lines": reasons,
            "primary": primary_name,
            "symmetry_pct": symmetry_pct,
            "primary_height": primary_height,
            "secondary_height": secondary_height,
            "primary_name": primary_name,
        }
    )
    return result


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
            f"<div class='spx-sub' style='font-size:0.95rem;'>{TAGLINE}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG} pts / 30m**")
        st.write(f"Contract factor: **{CONTRACT_FACTOR:.2f} × SPX move**")
        st.caption("Underlying rails and contract expectations are projected on a 30-minute grid.")
        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Underlying maintenance: 16:00–17:00 CT\n"
            "• Contracts maintenance: 16:00–19:00 CT\n"
            "• RTH grid: 08:30–14:30 CT\n"
            "• You choose pivots from the prior RTH. The app carries the structure."
        )

    # Hero
    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "📐 Contract Estimator",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # ==========================
    # TAB 1: RAILS SETUP
    # ==========================
    with tabs[0]:
        card(
            "Rails + Stacks",
            "Define your key pivots from the prior regular session, build both ascending and descending channels, and see stacked rails for extension plays.",
        )

        section_header("Underlying Pivots (Previous RTH)")

        st.markdown(
            "<div class='spx-sub'>"
            "Pick the structural high and low pivots from the previous regular session on your line chart. "
            "These are the main turning points that framed the day. Times can be any valid CT times inside that prior session."
            "</div>",
            unsafe_allow_html=True,
        )

        use_same = st.checkbox(
            "Use same pivots for both ascending and descending channels",
            value=True,
            key="same_pivots_flag",
        )

        if use_same:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**High Pivot (Shared)**")
                sh_price = st.number_input(
                    "High pivot price",
                    value=6720.0,
                    step=0.25,
                    key="shared_high_price",
                )
                sh_time = st.time_input(
                    "High pivot time (CT)",
                    value=dtime(12, 0),
                    step=1800,
                    key="shared_high_time",
                )
            with c2:
                st.markdown("**Low Pivot (Shared)**")
                sl_price = st.number_input(
                    "Low pivot price",
                    value=6650.0,
                    step=0.25,
                    key="shared_low_price",
                )
                sl_time = st.time_input(
                    "Low pivot time (CT)",
                    value=dtime(14, 30),
                    step=1800,
                    key="shared_low_time",
                )

            asc_inputs = (sh_price, sh_time, sl_price, sl_time)
            desc_inputs = asc_inputs
        else:
            st.markdown("**Ascending Scenario Pivots**")
            a1, a2 = st.columns(2)
            with a1:
                a_hi_price = st.number_input(
                    "Ascending high pivot price",
                    value=6720.0,
                    step=0.25,
                    key="asc_high_price",
                )
                a_hi_time = st.time_input(
                    "Ascending high pivot time (CT)",
                    value=dtime(11, 0),
                    step=1800,
                    key="asc_high_time",
                )
            with a2:
                a_lo_price = st.number_input(
                    "Ascending low pivot price",
                    value=6650.0,
                    step=0.25,
                    key="asc_low_price",
                )
                a_lo_time = st.time_input(
                    "Ascending low pivot time (CT)",
                    value=dtime(13, 30),
                    step=1800,
                    key="asc_low_time",
                )

            st.markdown("**Descending Scenario Pivots**")
            d1, d2 = st.columns(2)
            with d1:
                d_hi_price = st.number_input(
                    "Descending high pivot price",
                    value=6720.0,
                    step=0.25,
                    key="desc_high_price",
                )
                d_hi_time = st.time_input(
                    "Descending high pivot time (CT)",
                    value=dtime(13, 0),
                    step=1800,
                    key="desc_high_time",
                )
            with d2:
                d_lo_price = st.number_input(
                    "Descending low pivot price",
                    value=6650.0,
                    step=0.25,
                    key="desc_low_price",
                )
                d_lo_time = st.time_input(
                    "Descending low pivot time (CT)",
                    value=dtime(11, 0),
                    step=1800,
                    key="desc_low_time",
                )

            asc_inputs = (a_hi_price, a_hi_time, a_lo_price, a_lo_time)
            desc_inputs = (d_hi_price, d_hi_time, d_lo_price, d_lo_time)

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("Build Channels", key="build_channels_btn", use_container_width=True):
                try:
                    # Ascending (+ slope)
                    df_asc, h_asc = build_channel(
                        high_price=asc_inputs[0],
                        high_time=asc_inputs[1],
                        low_price=asc_inputs[2],
                        low_time=asc_inputs[3],
                        slope_sign=+1,
                    )
                    df_asc = add_stacked_levels(df_asc, h_asc)
                    st.session_state["asc_df"] = df_asc
                    st.session_state["asc_height"] = h_asc

                    # Descending (– slope)
                    df_desc, h_desc = build_channel(
                        high_price=desc_inputs[0],
                        high_time=desc_inputs[1],
                        low_price=desc_inputs[2],
                        low_time=desc_inputs[3],
                        slope_sign=-1,
                    )
                    df_desc = add_stacked_levels(df_desc, h_desc)
                    st.session_state["desc_df"] = df_desc
                    st.session_state["desc_height"] = h_desc

                    st.success("Channels and stacked rails generated successfully. Check the tables and the Daily Foresight tab.")
                except Exception as e:
                    st.error(f"Error building channels: {e}")

        df_asc = st.session_state.get("asc_df")
        df_desc = st.session_state.get("desc_df")
        h_asc = st.session_state.get("asc_height")
        h_desc = st.session_state.get("desc_height")

        section_header("Underlying Rails • RTH 08:30–14:30 CT")

        if df_asc is None and df_desc is None:
            st.info("Build channels to see the RTH projection and stacked rails.")
        else:
            if df_asc is not None:
                st.markdown("**Ascending Channel (Structure)**")
                c_top = st.columns([3, 1])
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True, height=320)
                with c_top[1]:
                    st.markdown(metric_card("Ascending Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "Download Ascending CSV",
                        df_asc.to_csv(index=False).encode(),
                        "ascending_channel_with_stacks.csv",
                        "text/csv",
                        key="dl_asc",
                        use_container_width=True,
                    )

            if df_desc is not None:
                st.markdown("**Descending Channel (Structure)**")
                c_bot = st.columns([3, 1])
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True, height=320)
                with c_bot[1]:
                    st.markdown(metric_card("Descending Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "Download Descending CSV",
                        df_desc.to_csv(index=False).encode(),
                        "descending_channel_with_stacks.csv",
                        "text/csv",
                        key="dl_desc",
                        use_container_width=True,
                    )

        end_card()

    # ==========================
    # TAB 2: CONTRACT ESTIMATOR
    # ==========================
    with tabs[1]:
        card(
            "Contract Estimator",
            "Use the channel height and a simple contract factor to estimate realistic rail-to-rail moves for calls and puts.",
        )

        df_asc = st.session_state.get("asc_df")
        df_desc = st.session_state.get("desc_df")
        h_asc = st.session_state.get("asc_height")
        h_desc = st.session_state.get("desc_height")

        if h_asc is None or h_desc is None:
            st.warning("Build both ascending and descending channels first in the Rails Setup tab.")
            end_card()
        else:
            primary_name = "Ascending" if h_asc >= h_desc else "Descending"
            primary_height = max(h_asc, h_desc)
            secondary_height = min(h_asc, h_desc)

            section_header("Channel Summary")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(metric_card("Ascending Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Descending Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
            with c3:
                st.markdown(metric_card("Primary Scenario", primary_name), unsafe_allow_html=True)

            est_move_primary = primary_height * CONTRACT_FACTOR
            est_move_secondary = secondary_height * CONTRACT_FACTOR

            st.markdown("<br>", unsafe_allow_html=True)
            section_header("Rail-to-Rail Contract Change (Estimate)")
            c4, c5 = st.columns(2)
            with c4:
                st.markdown(
                    metric_card(
                        f"{primary_name} Contract Move",
                        f"{est_move_primary:.2f} units (rail-to-rail)",
                    ),
                    unsafe_allow_html=True,
                )
            with c5:
                st.markdown(
                    metric_card(
                        "Other Scenario Contract Move",
                        f"{est_move_secondary:.2f} units (rail-to-rail)",
                    ),
                    unsafe_allow_html=True,
                )

            st.markdown(
                "<div class='muted'>This is a structural estimate. It tells you how much the contract "
                "should move for a full trip from one rail to the opposite rail based on the current channel width.</div>",
                unsafe_allow_html=True,
            )

            section_header("Plan a Specific Contract Trade")

            col_side, col_entry, col_compare = st.columns([1, 1, 1])
            with col_side:
                side = st.selectbox(
                    "Direction",
                    ["Long Call (bottom to top)", "Long Put (top to bottom)"],
                    key="contract_side",
                )
            with col_entry:
                entry_price = st.number_input(
                    "Planned contract entry price",
                    value=5.0,
                    step=0.1,
                    key="contract_entry_price",
                )
            with col_compare:
                want_second = st.checkbox(
                    "Compare a second contract",
                    value=False,
                    key="second_contract_flag",
                )

            entry_price_2 = None
            if want_second:
                entry_price_2 = st.number_input(
                    "Second contract entry price",
                    value=8.0,
                    step=0.1,
                    key="contract_entry_price_2",
                )

            active_height = primary_height
            active_move = active_height * CONTRACT_FACTOR

            if side.startswith("Long Call"):
                exit_price = entry_price + active_move
                label_side = "Long Call"
            else:
                exit_price = entry_price + active_move
                label_side = "Long Put"

            c6, c7, c8 = st.columns(3)
            with c6:
                st.markdown(metric_card("Channel Height Used", f"{active_height:.2f} pts"), unsafe_allow_html=True)
            with c7:
                st.markdown(metric_card("Expected Change", f"+{active_move:.2f} units"), unsafe_allow_html=True)
            with c8:
                st.markdown(metric_card("Target Exit Price", f"{exit_price:.2f}"), unsafe_allow_html=True)

            if want_second and entry_price_2 is not None:
                exit_price_2 = entry_price_2 + active_move
                st.markdown("<br>", unsafe_allow_html=True)
                section_header("Second Contract Comparison")
                c9, c10 = st.columns(2)
                with c9:
                    st.markdown(
                        metric_card("Entry 2", f"{entry_price_2:.2f}"),
                        unsafe_allow_html=True,
                    )
                with c10:
                    st.markdown(
                        metric_card("Exit 2 Target", f"{exit_price_2:.2f}"),
                        unsafe_allow_html=True,
                    )

            st.markdown(
                "<div class='muted'><strong>How to use this:</strong> When price tags a rail, "
                "you line up your real contract price with this projected change. "
                "If the actual move is much larger than this structural estimate, that is your volatility bonus.</div>",
                unsafe_allow_html=True,
            )

        end_card()

    # ==========================
    # TAB 3: DAILY FORESIGHT
    # ==========================
    with tabs[2]:
        card(
            "Daily Foresight",
            "Channels, stacked rails, contract expectations and a simple decision card to tell you when to attack and when to stand aside.",
        )

        df_asc = st.session_state.get("asc_df")
        df_desc = st.session_state.get("desc_df")
        h_asc = st.session_state.get("asc_height")
        h_desc = st.session_state.get("desc_height")

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("Build both ascending and descending structural channels first in the Rails Setup tab.")
            end_card()
        else:
            info = classify_day(h_asc, h_desc, CONTRACT_FACTOR)

            section_header("Structure Summary")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(metric_card("Ascending Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Descending Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
            with c3:
                sym_txt = f"{info['symmetry_pct']:.1f}%" if info["symmetry_pct"] is not None else "—"
                st.markdown(metric_card("Symmetry Difference", sym_txt), unsafe_allow_html=True)
            with c4:
                st.markdown(metric_card("Contract Factor", f"{CONTRACT_FACTOR:.2f}×"), unsafe_allow_html=True)

            section_header("Day Quality / Stand-Aside Radar")

            if info["status"] == "StandAside":
                pill_class = "decision-bad"
            elif info["status"] == "Caution":
                pill_class = "decision-caution"
            else:
                pill_class = "decision-good"

            st.markdown(
                f"<div class='decision-pill {pill_class}'>{info['label']}</div>",
                unsafe_allow_html=True,
            )

            reason_html = "<br>".join(info["reason_lines"])
            st.markdown(
                f"<div class='muted'>{reason_html}</div>",
                unsafe_allow_html=True,
            )

            if info["status"] == "StandAside":
                st.markdown(
                    "<div class='muted'>On stand aside days, treat the structure as information only. "
                    "Use it to observe behavior, not to force trades.</div>",
                    unsafe_allow_html=True,
                )

            section_header("Primary Scenario and Contract Size")

            primary_name = info["primary_name"] or "Ascending"
            primary_height = info["primary_height"] or max(h_asc, h_desc)
            secondary_height = info["secondary_height"] or min(h_asc, h_desc)

            est_primary = primary_height * CONTRACT_FACTOR
            est_secondary = secondary_height * CONTRACT_FACTOR

            c5, c6, c7 = st.columns(3)
            with c5:
                st.markdown(metric_card("Primary Scenario", primary_name), unsafe_allow_html=True)
            with c6:
                st.markdown(
                    metric_card("Primary Height", f"{primary_height:.2f} pts"),
                    unsafe_allow_html=True,
                )
            with c7:
                st.markdown(
                    metric_card("Primary Contract Move", f"{est_primary:.2f} units"),
                    unsafe_allow_html=True,
                )

            st.markdown(
                "<div class='muted'>If you are choosing between calls and puts, bias your main trades in "
                f"the direction of the <strong>{primary_name}</strong> scenario. The other scenario still provides "
                "levels, but with slightly less structural edge.</div>",
                unsafe_allow_html=True,
            )

            section_header("Decision Windows (CT)")

            st.markdown(
                """
                <div class='muted'>
                <ul style="margin-left:18px; padding-left:0;">
                  <li><strong>08:30–09:00</strong> → Discovery / fakeout zone. Watch only unless structure is extremely clear.</li>
                  <li><strong>09:30–11:00</strong> → Primary window for rail-to-rail plays. Best time to engage 0DTE risk.</li>
                  <li><strong>11:00–12:00</strong> → Often a transition / pause. Good for managing open risk.</li>
                  <li><strong>12:00–13:30</strong> → Midday rotations. Smaller size and faster profit-taking.</li>
                  <li><strong>13:30–14:30</strong> → Late session. Use structure only if you have clear confluence and are not forcing trades.</li>
                </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Time-Aligned Map (Primary Scenario)")

            if primary_name == "Ascending":
                df_primary = df_asc
            else:
                df_primary = df_desc

            if df_primary is not None:
                st.caption(
                    "Each row is a 30-minute slot in RTH. Top / Bottom are the main rails, ±1H are stacked extension rails."
                )
                st.dataframe(df_primary, use_container_width=True, hide_index=True, height=420)
                st.markdown(
                    "<div class='muted'><strong>How to read this:</strong> "
                    "Treat the rails as magnets. When price stretches outside the main band, watch the stacked rails "
                    "for extension reversals rather than chasing candles in the middle of nowhere.</div>",
                    unsafe_allow_html=True,
                )

        end_card()

    # ==========================
    # TAB 4: ABOUT
    # ==========================
    with tabs[3]:
        card("About SPX Prophet", TAGLINE)
        st.markdown(
            """
            <div class='spx-sub'>
            <p>SPX Prophet is a structural map. It does not try to predict every tick. It gives you rails, stacked levels, and realistic contract expectations so your decisions are clean.</p>
            <ul style="margin-left:18px;">
              <li>Two pivots from the prior RTH create both ascending and descending channels.</li>
              <li>Stacked rails (+1 / -1 height) frame extension plays when price escapes the main band.</li>
              <li>A simple contract factor (0.33 × channel move) gives you a realistic rail-to-rail expectation.</li>
              <li>A day-quality engine tells you when the structure is strong, when to trade small, and when to stand aside.</li>
            </ul>
            <p>You still decide the trigger. The app keeps the structure in front of you so you are not trading from emotion.</p>
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