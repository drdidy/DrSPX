# spx_prophet.py
# SPX Prophet — Structure-Driven 0DTE Planner

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."

# Core structural constants
SLOPE_MAG = 0.475          # underlying rails slope per 30 min
CONTRACT_FACTOR = 0.33     # contract move per SPX point (approx)
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 CT anchor for 30m grid


# ===============================
# STUNNING LIGHT MODE UI
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.06), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.06), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 30%, #f1f5f9 60%, #f8fafc 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.06), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.35);
        box-shadow:
            8px 0 30px rgba(15, 23, 42, 0.04);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.8rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1f2937 0%, #6366f1 35%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        letter-spacing: -0.04em;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.8) 30%,
            rgba(148, 163, 184, 0.8) 70%,
            transparent 100%);
    }

    .hero-wrapper {
        display: flex;
        justify-content: center;
        margin-bottom: 2.5rem;
    }

    .hero-header {
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.10), transparent 55%),
            radial-gradient(ellipse at bottom right, rgba(56, 189, 248, 0.12), transparent 60%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 28px;
        padding: 28px 36px 26px 36px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 20px 60px rgba(15, 23, 42, 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        text-align: center;
        overflow: hidden;
    }

    .hero-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: -40%;
        width: 180%;
        height: 3px;
        background: linear-gradient(90deg, #6366f1, #0ea5e9, #22c55e, #6366f1);
        opacity: 0.8;
        animation: heroShimmer 9s linear infinite;
    }

    @keyframes heroShimmer {
        0% { transform: translateX(0); }
        100% { transform: translateX(30%); }
    }

    .hero-status {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        background: rgba(22, 163, 74, 0.05);
        border: 1px solid rgba(22, 163, 74, 0.35);
        color: #166534;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 10px;
    }

    .hero-status-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 12px rgba(34, 197, 94, 0.8);
    }

    .hero-title {
        font-size: 2.4rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #020617 0%, #1f2933 25%, #4f46e5 65%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.06em;
        margin: 0;
    }

    .hero-tagline {
        margin-top: 4px;
        font-size: 1.05rem;
        color: #6b7280;
        font-weight: 500;
    }

    .hero-subline {
        margin-top: 10px;
        font-size: 0.95rem;
        color: #94a3b8;
    }

    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 5% 0%, rgba(129, 140, 248, 0.10), transparent 50%),
            radial-gradient(circle at 100% 100%, rgba(56, 189, 248, 0.10), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 24px;
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            0 16px 40px rgba(15, 23, 42, 0.06),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        padding: 26px 26px 22px 26px;
        margin-bottom: 24px;
        transition: all 0.3s ease;
        overflow: hidden;
    }

    .spx-card:hover {
        transform: translateY(-4px);
        box-shadow:
            0 22px 55px rgba(15, 23, 42, 0.10),
            inset 0 1px 0 rgba(255, 255, 255, 1);
        border-color: rgba(129, 140, 248, 0.9);
    }

    .spx-card h4 {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        margin: 0 0 6px 0;
        color: #111827;
        letter-spacing: -0.03em;
    }

    .spx-card-sub {
        color: #6b7280;
        font-size: 0.97rem;
        line-height: 1.6;
    }

    .section-header {
        font-size: 1.3rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        color: #111827;
        margin: 1.6rem 0 1rem 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .section-header-dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: linear-gradient(135deg, #6366f1, #0ea5e9);
        box-shadow: 0 0 12px rgba(129, 140, 248, 0.9);
    }

    .spx-metric {
        position: relative;
        padding: 18px 18px 16px 18px;
        border-radius: 18px;
        background:
            radial-gradient(circle at 0% 0%, rgba(129, 140, 248, 0.12), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border: 1px solid rgba(148, 163, 184, 0.8);
        box-shadow:
            0 12px 30px rgba(15, 23, 42, 0.06),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        overflow: hidden;
    }

    .spx-metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: #6b7280;
        font-weight: 600;
        margin-bottom: 6px;
    }

    .spx-metric-value {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #111827;
    }

    .spx-metric-note {
        font-size: 0.83rem;
        color: #9ca3af;
        margin-top: 3px;
    }

    .muted {
        color: #6b7280;
        font-size: 0.95rem;
        line-height: 1.7;
        padding: 14px 18px;
        background:
            linear-gradient(135deg, rgba(148, 163, 184, 0.10), rgba(226, 232, 240, 0.7));
        border-radius: 14px;
        border-left: 3px solid #6366f1;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);
        margin: 10px 0;
    }

    .no-trade-strong {
        font-weight: 700;
        color: #b91c1c;
    }

    .timing-tag {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .timing-prime {
        background: rgba(22, 163, 74, 0.08);
        color: #166534;
        border: 1px solid rgba(22, 163, 74, 0.25);
    }

    .timing-caution {
        background: rgba(234, 179, 8, 0.08);
        color: #92400e;
        border: 1px solid rgba(234, 179, 8, 0.35);
    }

    .timing-late {
        background: rgba(59, 130, 246, 0.08);
        color: #1d4ed8;
        border: 1px solid rgba(59, 130, 246, 0.35);
    }

    .stButton>button {
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        color: #ffffff;
        border-radius: 999px;
        border: none;
        padding: 0.6rem 1.6rem;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        box-shadow:
            0 12px 24px rgba(79, 70, 229, 0.35);
        cursor: pointer;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow:
            0 18px 32px rgba(79, 70, 229, 0.45);
    }

    .stButton>button:active {
        transform: translateY(0);
        box-shadow:
            0 12px 24px rgba(79, 70, 229, 0.35);
    }

    .stSelectbox>div>div,
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        border-radius: 14px !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        background-color: #ffffff !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06) !important;
    }

    label {
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        color: #475569 !important;
    }

    .stDataFrame {
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow: 0 14px 30px rgba(15, 23, 42, 0.06);
    }

    .app-footer {
        margin-top: 2.5rem;
        padding-top: 1.4rem;
        border-top: 1px solid rgba(148, 163, 184, 0.6);
        text-align: center;
        color: #9ca3af;
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
            <div class="hero-status">
              <span class="hero-status-dot"></span>
              SYSTEM ACTIVE
            </div>
            <div class="hero-title">{APP_NAME}</div>
            <div class="hero-tagline">{TAGLINE}</div>
            <div class="hero-subline">
              Structure from your pivots. Clear levels. Disciplined timing.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(text: str):
    st.markdown(
        f"""
        <div class="section-header">
          <div class="section-header-dot"></div>
          <span>{text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, note: Optional[str] = None) -> str:
    html = f"""
    <div class="spx-metric">
      <div class="spx-metric-label">{label}</div>
      <div class="spx-metric-value">{value}</div>
    """
    if note:
        html += f"""<div class="spx-metric-note">{note}</div>"""
    html += "</div>"
    return html


# ===============================
# TIME / GRID HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map a CT time to the fixed date grid.
    Any time between 00:00 and 23:59 is allowed.
    """
    dt = BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    return dt


def align_30min(dt: datetime) -> datetime:
    """Round to nearest 30m slot (15-min rule)."""
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """30-minute RTH grid: 08:30–14:30 CT."""
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


def time_label_for_dt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def classify_timing_label(time_str: str) -> str:
    """Return one of: prime / caution / late for timing band."""
    h, m = map(int, time_str.split(":"))
    total = h * 60 + m

    # 08:30–09:29: caution
    if 8 * 60 + 30 <= total < 9 * 60 + 30:
        return "caution"
    # 09:30–10:29: prime (channel touch + decision zone)
    if 9 * 60 + 30 <= total < 10 * 60 + 30:
        return "prime"
    # 10:30–12:29: prime continuation
    if 10 * 60 + 30 <= total < 12 * 60 + 30:
        return "prime"
    # 12:30–13:29: caution (midday digestion)
    if 12 * 60 + 30 <= total < 13 * 60 + 30:
        return "caution"
    # 13:30–14:30: late
    if 13 * 60 + 30 <= total <= 14 * 60 + 30:
        return "late"
    return "caution"


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
    Build a structural ascending/descending channel from two pivots.
    slope_sign = +1 for ascending, -1 for descending.
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
                "Time": time_label_for_dt(dt),
                "Top Rail": round(top, 2),
                "Bottom Rail": round(bottom, 2),
            }
        )
    df = pd.DataFrame(rows)
    return df, round(channel_height, 2)


def build_stacked_channel(df_main: pd.DataFrame, height: float) -> pd.DataFrame:
    """
    Given a main channel, build one stacked channel above and one below (±1 height).
    Adds columns:
        Top Stack Up, Bottom Stack Up, Top Stack Down, Bottom Stack Down
    """
    df = df_main.copy()
    df["Top Stack Up"] = (df["Top Rail"] + height).round(2)
    df["Bottom Stack Up"] = (df["Bottom Rail"] + height).round(2)
    df["Top Stack Down"] = (df["Top Rail"] - height).round(2)
    df["Bottom Stack Down"] = (df["Bottom Rail"] - height).round(2)
    return df


def guess_primary_scenario(
    h_asc: Optional[float],
    h_desc: Optional[float],
    close_price: Optional[float],
    close_time: Optional[dtime],
    df_asc: Optional[pd.DataFrame],
    df_desc: Optional[pd.DataFrame],
) -> str:
    """
    Heuristic: compare where the close sits relative to each channel.
    Whichever channel has the close nearer to the midline wins.
    Fallback: if one height is much larger, we assume that is primary.
    """
    if h_asc is None or h_desc is None or df_asc is None or df_desc is None:
        return "Ascending"

    if close_price is not None and close_time is not None:
        t_label = align_30min(make_dt_from_time(close_time)).strftime("%H:%M")
        try:
            row_a = df_asc[df_asc["Time"] == t_label].iloc[0]
            row_d = df_desc[df_desc["Time"] == t_label].iloc[0]
            mid_a = (row_a["Top Rail"] + row_a["Bottom Rail"]) / 2.0
            mid_d = (row_d["Top Rail"] + row_d["Bottom Rail"]) / 2.0
            dist_a = abs(close_price - mid_a)
            dist_d = abs(close_price - mid_d)
            return "Ascending" if dist_a <= dist_d else "Descending"
        except IndexError:
            pass

    # Fallback: whichever has taller structure tends to dominate
    if h_asc >= h_desc:
        return "Ascending"
    return "Descending"


# ===============================
# CONTRACT / PNL ENGINE
# ===============================

def estimate_contract_move(
    underlying_move: float,
    direction: str,
) -> float:
    """
    Positive result = profit for that long options direction.
    direction: "Long Call" or "Long Put"
    """
    if direction == "Long Call":
        # Calls profit when underlying rises
        return CONTRACT_FACTOR * underlying_move
    else:
        # Long Put: profit when underlying falls
        return CONTRACT_FACTOR * (-underlying_move)


# ===============================
# NO-TRADE FILTERS
# ===============================

def evaluate_no_trade(
    height_primary: float,
    height_alternate: float,
    contract_move_full: float,
) -> Tuple[str, str]:
    """
    Combine a few simple filters:
      1) Very narrow primary channel
      2) Big disagreement between ascending and descending heights
      3) Contract move too small relative to full rail-to-rail
    Returns: (status, explanation)
      status in {"OK", "CAUTION", "NO-TRADE"}
    """
    issues = []

    # 1) Narrow structure -> low edge
    if height_primary < 40:
        issues.append("Primary channel height is under 40 points (narrow structure).")

    # 2) Big disagreement between up/down channels
    if abs(height_primary - height_alternate) > 20:
        issues.append(
            "Ascending vs descending channel heights differ by more than 20 points (structure disagreement)."
        )

    # 3) Small contract move relative to full swing
    if contract_move_full < 9.9:
        issues.append(
            "Expected contract move from rail-to-rail is under 9.9 units (limited reward)."
        )

    if len(issues) == 0:
        return "OK", "All structure filters clear. You still manage risk, but the map is supportive."
    if len(issues) == 1:
        return "CAUTION", issues[0]
    # 2 or more issues: stand aside
    joined = " ".join(issues)
    return "NO-TRADE", joined


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

    # Sidebar info
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.caption(TAGLINE)
        st.markdown("---")
        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG} pts / 30m**")
        st.write(f"Contract factor: **{CONTRACT_FACTOR:.2f} × SPX move**")
        st.caption("Underlying channels are projected on a fixed 30-minute grid.")
        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "• Underlying maintenance: 16:00–17:00 CT\n"
            "• Contracts maintenance: 16:00–19:00 CT\n"
            "• RTH grid: 08:30–14:30 CT (30m blocks)\n"
            "• You choose pivots; the app carries the structure.",
        )

    hero()

    tabs = st.tabs(
        [
            "🧱 Rails & Stacks",
            "📐 Contract Planner",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # Ensure storage keys exist
    if "asc_df" not in st.session_state:
        st.session_state["asc_df"] = None
    if "desc_df" not in st.session_state:
        st.session_state["desc_df"] = None
    if "asc_h" not in st.session_state:
        st.session_state["asc_h"] = None
    if "desc_h" not in st.session_state:
        st.session_state["desc_h"] = None
    if "primary_guess" not in st.session_state:
        st.session_state["primary_guess"] = "Ascending"

    # TAB 1: RAILS & STACKS
    with tabs[0]:
        st.markdown(
            """
            <div class="spx-card">
              <h4>Rails + Stacks</h4>
              <div class="spx-card-sub">
                Define your two key pivots, build both ascending and descending channels,
                and stack them to understand how far extensions are likely to travel before reversing.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        section_header("Underlying Pivots (Previous Structure)")
        st.markdown(
            """
            <div class="spx-card-sub" style="margin-bottom:1rem;">
            Use the structural high and low pivots from the previous regular session, or from the first
            hours of overnight (for example 17:00–21:00). Focus on the clean turning points on your line chart.
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**High Pivot**")
            high_price = st.number_input(
                "High pivot price",
                value=6600.0,
                step=0.25,
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
                value=6500.0,
                step=0.25,
                key="low_pivot_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(14, 30),
                step=1800,
                key="low_pivot_time",
            )

        st.markdown("")
        close_col1, close_col2 = st.columns(2)
        with close_col1:
            close_price = st.number_input(
                "Previous close price (for bias detection)",
                value=6550.0,
                step=0.25,
                key="prev_close_price",
            )
        with close_col2:
            close_time = st.time_input(
                "Previous close time (CT)",
                value=dtime(15, 0),
                step=1800,
                key="prev_close_time",
            )

        st.markdown("")
        build_col = st.columns([1, 3])[0]
        with build_col:
            if st.button("Build Rails", use_container_width=True, key="build_rails_btn"):
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

                df_asc = build_stacked_channel(df_asc, h_asc)
                df_desc = build_stacked_channel(df_desc, h_desc)

                st.session_state["asc_df"] = df_asc
                st.session_state["desc_df"] = df_desc
                st.session_state["asc_h"] = h_asc
                st.session_state["desc_h"] = h_desc

                primary_guess = guess_primary_scenario(
                    h_asc,
                    h_desc,
                    close_price,
                    close_time,
                    df_asc,
                    df_desc,
                )
                st.session_state["primary_guess"] = primary_guess

                st.success("Rails and stacked channels generated from your pivots.")

        df_asc = st.session_state.get("asc_df")
        df_desc = st.session_state.get("desc_df")
        h_asc = st.session_state.get("asc_h")
        h_desc = st.session_state.get("desc_h")

        if df_asc is None or df_desc is None:
            st.info("Build the rails to see the structure tables.")
        else:
            section_header("Channel Structure Summary")
            m1, m2 = st.columns(2)
            with m1:
                st.markdown(
                    metric_card(
                        "Ascending Channel Height",
                        f"{h_asc:.2f} pts",
                        note="Slope +0.475 pts / 30m",
                    ),
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    metric_card(
                        "Descending Channel Height",
                        f"{h_desc:.2f} pts",
                        note="Slope -0.475 pts / 30m",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Primary Structural Scenario")
            primary_choice = st.radio(
                "Choose which channel to treat as primary for planning (you can override the suggestion).",
                ["Ascending", "Descending"],
                index=0 if st.session_state.get("primary_guess", "Ascending") == "Ascending" else 1,
                horizontal=True,
                key="primary_scenario",
            )

            st.markdown(
                f"""
                <div class="muted">
                <strong>Soft bias:</strong> The app's structural guess is
                <strong>{st.session_state.get("primary_guess")}</strong>. You have selected
                <strong>{primary_choice}</strong> as the active map for the day.
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Ascending Channel + Stacks")
            st.caption("Main rails, plus one channel-height above and one below.")
            st.dataframe(df_asc, use_container_width=True, hide_index=True, height=260)

            section_header("Descending Channel + Stacks")
            st.caption("Same pivots, opposite slope, plus stacked extension rails.")
            st.dataframe(df_desc, use_container_width=True, hide_index=True, height=260)

    # TAB 2: CONTRACT PLANNER
    with tabs[1]:
        st.markdown(
            """
            <div class="spx-card">
              <h4>Contract Planner</h4>
              <div class="spx-card-sub">
                Use the structural channel width and a simple contract factor to estimate
                the size of moves for calls and puts when trading from rail to rail, or
                from the main channel to a stacked extension.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        df_asc = st.session_state.get("asc_df")
        df_desc = st.session_state.get("desc_df")
        h_asc = st.session_state.get("asc_h")
        h_desc = st.session_state.get("desc_h")
        primary_choice = st.session_state.get("primary_scenario", "Ascending")

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("No channel found. Build the rails in the first tab before planning contracts.")
        else:
            # Select active DF & heights
            if primary_choice == "Ascending":
                df_main = df_asc
                h_primary = h_asc
                h_alt = h_desc
            else:
                df_main = df_desc
                h_primary = h_desc
                h_alt = h_asc

            section_header("Rail-to-Rail Estimates")
            c1, c2, c3 = st.columns(3)
            full_contract_move = CONTRACT_FACTOR * h_primary
            with c1:
                st.markdown(
                    metric_card(
                        "Primary Channel Height",
                        f"{h_primary:.2f} pts",
                        note="Main structural move from lower rail to upper rail.",
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card(
                        "Full Swing Contract Move",
                        f"{full_contract_move:.2f} units",
                        note=f"Approx. {CONTRACT_FACTOR:.2f} × SPX move.",
                    ),
                    unsafe_allow_html=True,
                )
            with c3:
                stack_move = CONTRACT_FACTOR * (2 * h_primary)
                st.markdown(
                    metric_card(
                        "Stack Extension Move",
                        f"{stack_move:.2f} units",
                        note="If price travels one full extra channel beyond the main rails.",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Scenario Estimator (Call / Put)")

            times = df_main["Time"].tolist()
            if not times:
                st.info("No time grid available.")
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    direction = st.selectbox(
                        "Position direction",
                        ["Long Call", "Long Put"],
                        key="contract_direction",
                    )
                with col2:
                    rail_side = st.selectbox(
                        "Entry rail",
                        ["Lower rail to upper rail", "Upper rail to lower rail"],
                        key="contract_rail_side",
                    )
                with col3:
                    stack_target = st.selectbox(
                        "Target scope",
                        [
                            "Main channel only",
                            "Main channel + one stack in direction of trade",
                        ],
                        key="contract_target_scope",
                    )

                # Timing: entry and exit
                section_header("Timing for This Trade Plan")
                tcol1, tcol2 = st.columns(2)
                with tcol1:
                    entry_time = st.selectbox(
                        "Planned entry time",
                        times,
                        index=min(len(times) - 1, 2),  # often 09:30
                        key="contract_entry_time",
                    )
                with tcol2:
                    # default exit a few slots later
                    default_exit_index = min(len(times) - 1, times.index(entry_time) + 2)
                    exit_time = st.selectbox(
                        "Planned exit time",
                        times,
                        index=default_exit_index,
                        key="contract_exit_time",
                    )

                # Underlying prices at entry & exit on selected rail(s)
                entry_row = df_main[df_main["Time"] == entry_time].iloc[0]
                exit_row = df_main[df_main["Time"] == exit_time].iloc[0]

                # Determine underlying move based on chosen rail logic
                if rail_side == "Lower rail to upper rail":
                    entry_underlying = entry_row["Bottom Rail"]
                    if stack_target == "Main channel only":
                        exit_underlying = exit_row["Top Rail"]
                    else:
                        # main + one stack in direction of move
                        exit_underlying = exit_row["Top Stack Up"]
                else:  # Upper to lower
                    entry_underlying = entry_row["Top Rail"]
                    if stack_target == "Main channel only":
                        exit_underlying = exit_row["Bottom Rail"]
                    else:
                        exit_underlying = exit_row["Bottom Stack Down"]

                underlying_move = exit_underlying - entry_underlying
                contract_pnl = estimate_contract_move(underlying_move, direction)

                cA, cB, cC = st.columns(3)
                with cA:
                    st.markdown(
                        metric_card(
                            "Underlying Entry → Exit",
                            f"{underlying_move:+.2f} pts",
                            note=f"From {entry_underlying:.2f} to {exit_underlying:.2f}.",
                        ),
                        unsafe_allow_html=True,
                    )
                with cB:
                    st.markdown(
                        metric_card(
                            "Projected Contract P&L",
                            f"{contract_pnl:+.2f} units",
                            note=f"{direction}, structural move only.",
                        ),
                        unsafe_allow_html=True,
                    )
                with cC:
                    effective_span = abs(underlying_move) / h_primary if h_primary != 0 else 0
                    st.markdown(
                        metric_card(
                            "Channel Span Used",
                            f"{effective_span*100:.1f} %",
                            note="Percentage of the full primary channel used by this plan.",
                        ),
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    """
                    <div class="muted">
                    <strong>How to read this:</strong> the planner assumes your entry is at the chosen rail
                    at the selected time, and your exit is at the target rail (main or stacked) at the later
                    time. It only reflects the structural move from your pivots; implied volatility,
                    theta, and skew are not modeled here.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # TAB 3: DAILY FORESIGHT
    with tabs[2]:
        st.markdown(
            """
            <div class="spx-card">
              <h4>Daily Foresight</h4>
              <div class="spx-card-sub">
                One card that combines your primary channel, stacked levels, no-trade filters,
                timing bands, and a simple directional bias for calls or puts.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        df_asc = st.session_state.get("asc_df")
        df_desc = st.session_state.get("desc_df")
        h_asc = st.session_state.get("asc_h")
        h_desc = st.session_state.get("desc_h")
        primary_choice = st.session_state.get("primary_scenario", "Ascending")

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("No channel found. Build your rails in the first tab to unlock the Foresight card.")
        else:
            if primary_choice == "Ascending":
                df_primary = df_asc
                h_primary = h_asc
                h_alt = h_desc
            else:
                df_primary = df_desc
                h_primary = h_desc
                h_alt = h_asc

            full_contract_move = CONTRACT_FACTOR * h_primary
            status, explanation = evaluate_no_trade(h_primary, h_alt, full_contract_move)

            section_header("Structure Snapshot")
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(
                    metric_card(
                        "Primary Scenario",
                        primary_choice,
                        note="Active channel used for the map.",
                    ),
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    metric_card(
                        "Primary Height",
                        f"{h_primary:.2f} pts",
                        note="Full move from lower to upper rail.",
                    ),
                    unsafe_allow_html=True,
                )
            with m3:
                st.markdown(
                    metric_card(
                        "Rail-to-Rail Contract Move",
                        f"{full_contract_move:.2f} units",
                        note=f"Approx. {CONTRACT_FACTOR:.2f} × SPX move.",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("Tradeability Filter")
            if status == "NO-TRADE":
                color_line = "<span class='no-trade-strong'>NO-TRADE DAY (STRUCTURE ONLY)</span>"
            elif status == "CAUTION":
                color_line = "<span style='color:#b45309;font-weight:700;'>CAUTION</span>"
            else:
                color_line = "<span style='color:#15803d;font-weight:700;'>STRUCTURE OK</span>"

            st.markdown(
                f"""
                <div class="muted">
                  <strong>Status:</strong> {color_line}<br>
                  <strong>Reasoning:</strong> {explanation}
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Directional Bias (Structure Only)")

            # Simple structural bias: for ascending primary, core trade is long call from lower rail.
            # For descending primary, core trade is long put from upper rail.
            if primary_choice == "Ascending":
                bias_html = """
                <p><strong>Core idea:</strong> treat the lower rail as the buy zone for calls
                and the upper rail as the fade zone for puts once the first 30–60 minutes have printed.</p>
                <ul>
                  <li>Look for clean rejection of the lower rail between <strong>09:30–10:30 CT</strong> for long calls.</li>
                  <li>Use 10:00–11:00 CT as the decision window for follow-through vs fake-out.</li>
                  <li>If price escapes the upper rail, watch the upper stacked rail as the extension target.</li>
                </ul>
                """
            else:
                bias_html = """
                <p><strong>Core idea:</strong> treat the upper rail as the sell zone for puts
                and the lower rail as the cover/bounce zone once the first 30–60 minutes have printed.</p>
                <ul>
                  <li>Look for clean rejection of the upper rail between <strong>09:30–10:30 CT</strong> for long puts.</li>
                  <li>Use 10:00–11:00 CT as the decision window for continuation vs short-trap.</li>
                  <li>If price breaks below the main channel, the lower stacked rail becomes the likely extension magnet.</li>
                </ul>
                """

            st.markdown(
                f"""
                <div class="spx-card-sub" style="background:transparent;margin-top:0.25rem;">
                {bias_html}
                <p style="margin-top:6px;color:#9ca3af;font-size:0.9rem;">
                This is structural context only. You still decide size, risk and whether today deserves your capital.
                </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Timing Bands (CT, 30m Slots)")
            st.markdown(
                """
                <div class="spx-card-sub">
                <ul>
                  <li><span class="timing-tag timing-caution">08:30–09:29</span> Opening imbalance and noise. Observe structure; rarely commit size.</li>
                  <li><span class="timing-tag timing-prime">09:30–10:29</span> First serious tests of your rails. Many key reversals or breaks form here.</li>
                  <li><span class="timing-tag timing-prime">10:30–12:29</span> Continuation or clean reversal away from the rails if the 09:30–10:00 tests held.</li>
                  <li><span class="timing-tag timing-caution">12:30–13:29</span> Midday digestion. Often choppy; be selective.</li>
                  <li><span class="timing-tag timing-late">13:30–14:30</span> Late-day pushes, squeezes, and mean-reversion. Good for partials, not fresh risk.</li>
                </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Time-Aligned Map (Primary + First Stack)")
            # Build table with timing labels
            map_df = df_primary.copy()
            map_df["Timing Band"] = map_df["Time"].apply(classify_timing_label)
            map_df["Timing Band"] = map_df["Timing Band"].map(
                {"prime": "Prime", "caution": "Caution", "late": "Late"}
            )
            st.caption(
                "Main rails and the first stacked rails, all on the same 30-minute grid, "
                "with a timing band label for context."
            )
            st.dataframe(
                map_df[
                    [
                        "Time",
                        "Top Rail",
                        "Bottom Rail",
                        "Top Stack Up",
                        "Bottom Stack Up",
                        "Top Stack Down",
                        "Bottom Stack Down",
                        "Timing Band",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                height=360,
            )

            st.markdown(
                """
                <div class="muted">
                <strong>Reading the map:</strong> the rails tell you where structure expects reactions.
                The timing band tells you when reactions are more likely to turn into trades worth taking.
                You combine both and pass only the cleanest tests.
                </div>
                """,
                unsafe_allow_html=True,
            )

    # TAB 4: ABOUT
    with tabs[3]:
        st.markdown(
            """
            <div class="spx-card">
              <h4>About SPX Prophet</h4>
              <div class="spx-card-sub">
                SPX Prophet is a structure-only planner. It does not pull live market data, it does not
                model full options greeks, and it does not promise certainty. It gives you a disciplined
                map built from two pivots, a fixed slope, and clean timing rules.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        section_header("What the App Does")
        st.markdown(
            """
            <div class="spx-card-sub">
            <ul>
              <li>Builds both ascending and descending channels from your chosen pivots.</li>
              <li>Stacks channels one height above and below the main structure to frame extensions.</li>
              <li>Highlights a primary scenario while still giving you the alternate.</li>
              <li>Estimates contract moves from rail-to-rail using a simple factor of the SPX move.</li>
              <li>Offers structural no-trade filters when conditions are not worth the risk.</li>
              <li>Marks timing bands so you are not blindly trading outside your best windows.</li>
            </ul>
            <p>Everything else is up to your discipline, your sizing, and your ability to wait.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        section_header("What the App Does Not Do")
        st.markdown(
            """
            <div class="spx-card-sub">
            <ul>
              <li>No automatic data feed, no delayed surprises from external APIs.</li>
              <li>No volatility surface, no skew or gamma curves.</li>
              <li>No promises that every day is tradable. Some days the answer will be “stand aside”.</li>
            </ul>
            <p>
            The edge is not in prediction. The edge is in showing up on the right days, at the right rails,
            at the right times, and passing on everything else.
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()