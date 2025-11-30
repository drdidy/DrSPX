# spx_prophet.py
# Offline SPX channel + stacked-rails planner for 0DTE structure trades

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Optional, Tuple

APP_NAME = "SPX Prophet"
TAGLINE = "Intraday Channel and Stacked-Rail Planner"

SLOPE_MAG = 0.475        # pts per 30m for underlying rails
CONTRACT_FACTOR = 0.33   # contract move as fraction of SPX move
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # reference for block math
NUM_STACKS = 6           # show ±6 stacks


# =========================================================
# ===============  STUNNING LIGHT UI LAYER  ===============
# =========================================================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.06), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.06), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 35%, #e5edf7 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    .block-container {
        padding-top: 2.8rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 0% 0%, rgba(129, 140, 248, 0.08), transparent 60%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.4);
        box-shadow:
            8px 0 30px rgba(15, 23, 42, 0.06),
            1px 0 0 rgba(148, 163, 184, 0.25);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.9rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        letter-spacing: -0.04em;
        margin-bottom: 0.2rem;
        background: linear-gradient(135deg, #1e293b 0%, #4f46e5 40%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.8), transparent);
    }

    [data-testid="stSidebar"] h4 {
        font-size: 0.9rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #64748b;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }

    /* Centered header */
    .app-hero {
        position: relative;
        border-radius: 28px;
        padding: 28px 32px 26px 32px;
        margin-bottom: 26px;
        background:
          radial-gradient(circle at 0% 0%, rgba(129, 140, 248, 0.16), transparent 55%),
          radial-gradient(circle at 100% 100%, rgba(56, 189, 248, 0.14), transparent 55%),
          linear-gradient(145deg, #ffffff 0%, #f9fafb 40%, #eef2ff 100%);
        border: 1px solid rgba(148, 163, 184, 0.55);
        box-shadow:
          0 24px 60px rgba(15, 23, 42, 0.13),
          inset 0 1px 0 rgba(255, 255, 255, 0.9);
        overflow: hidden;
    }

    .app-hero::before {
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(circle at 20% 0%, rgba(59, 130, 246, 0.12), transparent 50%);
        opacity: 0.7;
        pointer-events: none;
    }

    .app-hero-header {
        position: relative;
        text-align: center;
        z-index: 1;
    }

    .app-name {
        font-family: 'Poppins', sans-serif;
        font-size: 2.6rem;
        font-weight: 900;
        letter-spacing: -0.06em;
        margin: 0;
        background: linear-gradient(135deg, #020617 0%, #1d4ed8 40%, #0ea5e9 80%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .app-tagline {
        margin-top: 4px;
        font-size: 1.1rem;
        color: #64748b;
        font-weight: 500;
    }

    .app-status-row {
        margin-top: 18px;
        display: flex;
        justify-content: center;
        gap: 16px;
        flex-wrap: wrap;
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        background: rgba(22, 163, 74, 0.06);
        border: 1px solid rgba(34, 197, 94, 0.5);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-weight: 700;
        color: #15803d;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 10px rgba(34, 197, 94, 0.8);
    }

    .status-note {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        border-radius: 999px;
        background: rgba(59, 130, 246, 0.06);
        border: 1px solid rgba(59, 130, 246, 0.5);
        font-size: 0.78rem;
        letter-spacing: 0.12em;
        font-weight: 600;
        color: #1d4ed8;
        text-transform: uppercase;
    }

    /* Card */
    .spx-card {
        position: relative;
        background:
          radial-gradient(circle at 0% 0%, rgba(129, 140, 248, 0.10), transparent 55%),
          linear-gradient(135deg, #ffffff 0%, #f9fafb 100%);
        border-radius: 24px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
          0 18px 45px rgba(15, 23, 42, 0.12),
          inset 0 1px 0 rgba(255, 255, 255, 0.9);
        padding: 26px 26px 22px 26px;
        margin-bottom: 26px;
        overflow: hidden;
    }

    .spx-card h4 {
        margin: 0 0 10px 0;
        font-size: 1.4rem;
        font-family: 'Poppins', sans-serif;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #0f172a;
    }

    .spx-sub {
        font-size: 0.96rem;
        color: #4b5563;
        line-height: 1.7;
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        border: 1px solid rgba(129, 140, 248, 0.7);
        background: rgba(239, 246, 255, 0.9);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #4338ca;
        margin-bottom: 10px;
    }

    .section-header {
        font-size: 1.1rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #111827;
        margin: 1.8rem 0 0.9rem 0;
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
        box-shadow: 0 0 12px rgba(59, 130, 246, 0.9);
    }

    .spx-metric {
        border-radius: 18px;
        padding: 16px 18px 14px 18px;
        background:
          linear-gradient(135deg, #ffffff 0%, #eef2ff 100%);
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow:
          0 12px 28px rgba(15, 23, 42, 0.10),
          inset 0 1px 0 rgba(255, 255, 255, 0.95);
    }

    .spx-metric-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 6px;
    }

    .spx-metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.45rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #111827;
    }

    .muted {
        color: #4b5563;
        font-size: 0.95rem;
        line-height: 1.7;
        padding: 12px 14px;
        background: #f9fafb;
        border-left: 3px solid #4f46e5;
        border-radius: 10px;
        margin: 0.6rem 0 0.2rem 0;
    }

    .no-trade-ok {
        color: #166534;
        font-weight: 600;
    }
    .no-trade-warning {
        color: #b45309;
        font-weight: 600;
    }
    .no-trade-stop {
        color: #b91c1c;
        font-weight: 700;
    }

    .app-footer {
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(148, 163, 184, 0.4);
        text-align: center;
        font-size: 0.9rem;
        color: #6b7280;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(248, 250, 252, 0.9);
        padding: 8px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.7);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        padding: 8px 20px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #6b7280;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        color: #ffffff;
        box-shadow: 0 10px 24px rgba(37, 99, 235, 0.35);
    }

    .stDataFrame {
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.7);
        box-shadow: 0 14px 32px rgba(15, 23, 42, 0.10);
        overflow: hidden;
    }

    .stDataFrame thead tr th {
        background: rgba(239, 246, 255, 0.96) !important;
        color: #4338ca !important;
        font-weight: 800 !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.14em !important;
    }

    .stDataFrame tbody tr:hover {
        background: rgba(219, 234, 254, 0.55) !important;
    }

    .stButton>button {
        border-radius: 999px;
        border: none;
        padding: 10px 22px;
        font-size: 0.9rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        color: #ffffff;
        box-shadow: 0 14px 28px rgba(37, 99, 235, 0.35);
    }

    .stDownloadButton>button {
        border-radius: 999px;
        border: none;
        padding: 9px 18px;
        font-size: 0.85rem;
        font-weight: 600;
        background: #0f172a;
        color: #ffffff;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.40);
    }

    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        border-radius: 12px !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        background: #ffffff !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }

    label {
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        color: #374151 !important;
    }

    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown(
        f"""
        <div class="app-hero">
          <div class="app-hero-header">
            <div class="app-name">{APP_NAME}</div>
            <div class="app-tagline">{TAGLINE}</div>
            <div class="app-status-row">
              <div class="status-pill">
                <span class="status-dot"></span>
                SYSTEM ACTIVE
              </div>
              <div class="status-note">
                STRUCTURE FIRST • EMOTION LAST
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


def section_header(text: str):
    st.markdown(f"<div class='section-header'>{text}</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str) -> str:
    return f"""
    <div class="spx-metric">
      <div class="spx-metric-label">{label}</div>
      <div class="spx-metric-value">{value}</div>
    </div>
    """


def style_time_highlight(df: pd.DataFrame):
    """Highlight 09:30 and especially 10:00 rows."""
    def highlight(row):
        if "Time" not in row:
            return ['' for _ in row]
        t = row["Time"]
        if t == "10:00":
            return ['background-color: rgba(252, 211, 77, 0.45); font-weight: 700;' for _ in row]
        elif t == "09:30":
            return ['background-color: rgba(191, 219, 254, 0.55); font-weight: 600;' for _ in row]
        else:
            return ['' for _ in row]

    return df.style.apply(highlight, axis=1)


# =========================================================
# ===============  TIME / GRID HELPERS  ==================
# =========================================================

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map any CT time into a synthetic date anchored at BASE_DATE with 30m blocks.
    We only care about relative 30m spacing, not calendar day.
    """
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    """Snap to nearest 30-minute boundary."""
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """Return RTH grid 08:30–14:30 CT on the synthetic date."""
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


# =========================================================
# ===============  CHANNEL / STACK ENGINE  ===============
# =========================================================

def build_single_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
) -> Tuple[pd.DataFrame, float]:
    """
    Build a single structural channel (ascending or descending) using the
    manually chosen high and low pivots from the prior session.
    """
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))

    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

    # y = s*k + b => b = y - s*k
    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo
    channel_height = b_top - b_bottom

    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        top_main = s * k + b_top
        bottom_main = s * k + b_bottom
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Top_0": round(top_main, 2),
                "Bottom_0": round(bottom_main, 2),
            }
        )

    df = pd.DataFrame(rows)
    return df, float(round(channel_height, 2))


def add_stacks(df: pd.DataFrame, channel_height: float, num_stacks: int = NUM_STACKS) -> pd.DataFrame:
    """
    Add ±N stacks above and below the main channel.
    """
    df = df.copy()
    for n in range(1, num_stacks + 1):
        df[f"Top_+{n}"] = (df["Top_0"] + n * channel_height).round(2)
        df[f"Bottom_+{n}"] = (df["Bottom_0"] + n * channel_height).round(2)
        df[f"Top_-{n}"] = (df["Top_0"] - n * channel_height).round(2)
        df[f"Bottom_-{n}"] = (df["Bottom_0"] - n * channel_height).round(2)
    return df


def pick_primary_scenario(
    asc_height: Optional[float],
    desc_height: Optional[float],
) -> Tuple[str, str]:
    """
    Decide which scenario is primary based on channel height contrast.
    """
    if asc_height is None or desc_height is None:
        return "Ascending", "Both channels not available; defaulting to ascending."

    if asc_height <= 0 or desc_height <= 0:
        return "Ascending", "Invalid heights detected; defaulting to ascending."

    diff = abs(asc_height - desc_height)
    avg = (asc_height + desc_height) / 2.0
    if avg == 0:
        return "Ascending", "Zero heights; defaulting to ascending."

    rel = diff / avg

    if rel < 0.08:
        return "Neutral", "Heights are very similar; treat both scenarios as plausible."
    elif asc_height > desc_height:
        return "Ascending", "Ascending channel offers the larger structural move."
    else:
        return "Descending", "Descending channel offers the larger structural move."


def strict_no_trade_evaluation(
    primary_height: float,
    contract_move: float,
    asc_height: Optional[float],
    desc_height: Optional[float],
) -> Tuple[str, str]:
    """
    Combine structural filters into a simple pre-session recommendation.

    Looser than before: only hard "Stand aside" if structure is truly dead.
    Remember: if by 10:00 CT price is sitting at stack 4–6, that becomes a
    high-opportunity mean-reversion setup, even if this filter was cautious.
    """
    reasons = []

    # Filter 1: channel height
    if primary_height < 18:
        reasons.append("Primary channel height is under 18 points (very compressed).")
        height_flag = "fail"
    elif primary_height < 30:
        reasons.append("Primary channel height is between 18 and 30 points (compressed).")
        height_flag = "caution"
    elif primary_height < 40:
        reasons.append("Primary channel height is between 30 and 40 points (moderate).")
        height_flag = "ok_caution"
    else:
        reasons.append("Primary channel height is above 40 points (plenty of room to work).")
        height_flag = "ok"

    # Filter 2: contract move
    if contract_move < 7.0:
        reasons.append("Estimated contract move for a full rail-to-rail is under 7 units.")
        contract_flag = "fail"
    elif contract_move < 10.0:
        reasons.append("Estimated contract move is between 7 and 10 units (smaller payoff).")
        contract_flag = "caution"
    elif contract_move < 14.0:
        reasons.append("Estimated contract move is between 10 and 14 units (respectable).")
        contract_flag = "ok_caution"
    else:
        reasons.append("Estimated contract move is strong for a single structural swing.")
        contract_flag = "ok"

    # Filter 3: symmetry between ascending and descending
    symmetry_flag = "ok"
    if asc_height is not None and desc_height is not None and asc_height > 0 and desc_height > 0:
        diff = abs(asc_height - desc_height)
        avg = (asc_height + desc_height) / 2.0
        rel = diff / avg
        if rel < 0.06:
            reasons.append("Ascending and descending heights are extremely similar (structure may be indecisive).")
            symmetry_flag = "caution"
        else:
            reasons.append("Ascending and descending heights are separated enough to define a bias.")
            symmetry_flag = "ok"

    flags = [height_flag, contract_flag, symmetry_flag]

    # Hard stand aside: structure and contract both dead
    if height_flag == "fail" and contract_flag == "fail":
        status = "Stand aside. Structure offers almost nothing today."
        cls = "no-trade-stop"
    # Soft caution: some compression / small move but not completely dead
    elif "fail" in flags or flags.count("caution") + flags.count("ok_caution") >= 2:
        status = "Trade only if intraday tape is clean. Keep size small."
        cls = "no-trade-warning"
    else:
        status = "Day is structurally viable. Focus on discipline at the rails."
        cls = "no-trade-ok"

    html = (
        f"<span class='{cls}'>{status}</span><br/>"
        + "<br/>• " + "<br/>• ".join(reasons)
    )

    return status, html


# =========================================================
# ===================  MAIN APP  ==========================
# =========================================================

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
        st.markdown(f"<div class='spx-sub'>{TAGLINE}</div>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG} pts / 30m**")
        st.write(f"Contract factor: **{CONTRACT_FACTOR:.2f} × SPX move**")
        st.caption(
            "• Underlying: 16:00–17:00 CT maintenance\n"
            "• Contracts: 16:00–19:00 CT maintenance\n"
            "• RTH grid: 08:30–14:30 CT (30m blocks)\n"
            "• You choose pivots from prior session or early overnight; the app carries the structure forward."
        )

    hero()

    tabs = st.tabs(
        [
            "🧱 Rails + Stacks",
            "📐 Contract Factor",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # ============================================
    # TAB 1: Rails + Stacks
    # ============================================
    with tabs[0]:
        card(
            "Rails and Stacks",
            "Define your two key pivots from the prior session, build both ascending and descending channels, "
            "and stack them to see where reversals are likely.",
            badge="Structure Engine",
        )

        section_header("Underlying Pivots (Previous Session or Early Overnight)")
        st.markdown(
            """
            <div class="spx-sub">
            Choose the structural high and low pivots from the previous RTH session or early overnight (for example 17:00–21:00 CT).
            They do not need to be the absolute wick extremes. Use the first clean reversal high and low on your line chart that define the day’s structure.
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

        st.markdown("")
        build_col = st.columns([1, 3])[0]
        with build_col:
            build_clicked = st.button("Build Channels and Stacks", use_container_width=True)

        if build_clicked:
            asc_df, asc_h = build_single_channel(
                high_price=high_price,
                high_time=high_time,
                low_price=low_price,
                low_time=low_time,
                slope_sign=+1,
            )
            desc_df, desc_h = build_single_channel(
                high_price=high_price,
                high_time=high_time,
                low_price=low_price,
                low_time=low_time,
                slope_sign=-1,
            )
            asc_df = add_stacks(asc_df, asc_h, NUM_STACKS)
            desc_df = add_stacks(desc_df, desc_h, NUM_STACKS)

            st.session_state["asc_df"] = asc_df
            st.session_state["asc_h"] = asc_h
            st.session_state["desc_df"] = desc_df
            st.session_state["desc_h"] = desc_h

            st.success("Channels and stacked rails generated.")

        asc_df = st.session_state.get("asc_df")
        asc_h = st.session_state.get("asc_h")
        desc_df = st.session_state.get("desc_df")
        desc_h = st.session_state.get("desc_h")

        section_header("Channel Heights")
        c_h1, c_h2 = st.columns(2)
        with c_h1:
            if asc_h is not None:
                st.markdown(metric_card("Ascending Height", f"{asc_h:.2f} pts"), unsafe_allow_html=True)
            else:
                st.info("Build the channels to see ascending height.")
        with c_h2:
            if desc_h is not None:
                st.markdown(metric_card("Descending Height", f"{desc_h:.2f} pts"), unsafe_allow_html=True)
            else:
                st.info("Build the channels to see descending height.")

        section_header("Stacked Channels (±6)")
        st.markdown(
            """
            <div class="spx-sub">
            When price escapes the main channel, it often travels toward one of the stacked rails (±1, ±2, … ±6 heights) 
            before a decisive reversal. This map is designed to help you see those extension paths in advance.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if asc_df is None or desc_df is None:
            st.info("Build channels to see stacked structures.")
        else:
            auto_primary, auto_comment = pick_primary_scenario(asc_h, desc_h)
            st.markdown(
                f"<div class='muted'><strong>Primary scenario (auto):</strong> {auto_primary}. {auto_comment}</div>",
                unsafe_allow_html=True,
            )

            st.markdown("**Ascending Structure (Main + ±6 stacks)**")
            st.dataframe(style_time_highlight(asc_df), use_container_width=True, height=340)
            st.download_button(
                "Download Ascending Rails (CSV)",
                asc_df.to_csv(index=False).encode(),
                "ascending_rails_stacks.csv",
                "text/csv",
                use_container_width=True,
                key="dl_asc",
            )

            st.markdown("**Descending Structure (Main + ±6 stacks)**")
            st.dataframe(style_time_highlight(desc_df), use_container_width=True, height=340)
            st.download_button(
                "Download Descending Rails (CSV)",
                desc_df.to_csv(index=False).encode(),
                "descending_rails_stacks.csv",
                "text/csv",
                use_container_width=True,
                key="dl_desc",
            )

        end_card()

    # ============================================
    # TAB 2: Contract Factor
    # ============================================
    with tabs[1]:
        card(
            "Contract Factor View",
            "Use a simple factor between SPX move and contract move to estimate what one full rail-to-rail swing is worth.",
            badge="Contract Size Guide",
        )

        asc_df = st.session_state.get("asc_df")
        asc_h = st.session_state.get("asc_h")
        desc_df = st.session_state.get("desc_df")
        desc_h = st.session_state.get("desc_h")

        section_header("Factor Settings")
        cf = st.number_input(
            "Contract factor (contract move ÷ SPX move)",
            value=CONTRACT_FACTOR,
            step=0.01,
            min_value=0.01,
            max_value=2.0,
            key="contract_factor_input",
        )

        if asc_h is None or desc_h is None:
            st.info("Build the channels in the Rails tab before using the contract factor view.")
            end_card()
        else:
            asc_contract_move = asc_h * cf
            desc_contract_move = desc_h * cf

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(
                    metric_card("Ascending: full rail-to-rail", f"{asc_contract_move:.2f} units"),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card("Descending: full rail-to-rail", f"{desc_contract_move:.2f} units"),
                    unsafe_allow_html=True,
                )

            st.markdown(
                """
                <div class="muted">
                For a long call from lower rail to upper rail or a long put from upper rail to lower rail, 
                this value is the approximate structural contract move if the underlying completes one full channel swing.
                It does not attempt to model decay, volatility crush, or skew.
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("Quick Directional Guide")
            scenario = st.radio(
                "Which structural scenario are you planning to trade?",
                ["Ascending", "Descending"],
                index=0,
                horizontal=True,
                key="contract_scenario_choice",
            )

            play_type = st.radio(
                "Planned options structure",
                ["Long call (bottom → top)", "Long put (top → bottom)"],
                index=0,
                horizontal=True,
                key="contract_play_choice",
            )

            if scenario == "Ascending":
                cmove = asc_contract_move
                h_here = asc_h
            else:
                cmove = desc_contract_move
                h_here = desc_h

            st.markdown(
                metric_card(
                    "Underlying channel height in focus",
                    f"{h_here:.2f} pts",
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                metric_card(
                    "Estimated contract move for 1 full swing",
                    f"{cmove:.2f} units in your favor",
                ),
                unsafe_allow_html=True,
            )

            st.markdown(
                """
                <div class="muted">
                This estimator is intentionally simple. 
                Use it to frame expectations, not to force a trade. The discipline is to wait for clean reactions at your rails.
                </div>
                """,
                unsafe_allow_html=True,
            )

        end_card()

    # ============================================
    # TAB 3: Daily Foresight
    # ============================================
    with tabs[2]:
        card(
            "Daily Foresight",
            "Highlight the 09:30 and 10:00 CT decision points on the stacked structure and let the filters tell you when to stand aside.",
            badge="Session Playbook",
        )

        asc_df = st.session_state.get("asc_df")
        asc_h = st.session_state.get("asc_h")
        desc_df = st.session_state.get("desc_df")
        desc_h = st.session_state.get("desc_h")

        if asc_df is None or desc_df is None or asc_h is None or desc_h is None:
            st.warning("Build the channels in the Rails tab first.")
            end_card()
        else:
            auto_primary, auto_comment = pick_primary_scenario(asc_h, desc_h)
            primary_choice = st.radio(
                "Primary structural scenario for today",
                ["Ascending", "Descending"],
                index=0 if auto_primary in ["Ascending", "Neutral"] else 1,
                horizontal=True,
                key="primary_choice_radio",
            )

            if primary_choice == "Ascending":
                primary_df = asc_df
                primary_h = asc_h
                alt_df = desc_df
                alt_h = desc_h
            else:
                primary_df = desc_df
                primary_h = desc_h
                alt_df = asc_df
                alt_h = asc_h

            cf = st.session_state.get("contract_factor_input", CONTRACT_FACTOR)
            primary_contract_move = primary_h * cf

            section_header("Session Summary")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(metric_card("Primary Scenario", primary_choice), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Primary Channel Height", f"{primary_h:.2f} pts"), unsafe_allow_html=True)
            with c3:
                st.markdown(
                    metric_card("Contract Move (1 full swing)", f"{primary_contract_move:.2f} units"),
                    unsafe_allow_html=True,
                )

            _, html = strict_no_trade_evaluation(primary_h, primary_contract_move, asc_h, desc_h)
            st.markdown(
                f"<div class='muted'><strong>No-trade filter summary (pre-session):</strong><br/>{html}</div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                """
                <div class="spx-sub" style="margin-top:0.4rem;">
                • Before the open, this tells you how much structure the day is offering.<br/>
                • Around 09:30–10:00 CT, combine this with where price actually sits in the stacks:<br/>
                &nbsp;&nbsp;&nbsp;&nbsp;– Near main rails → standard channel swing plays.<br/>
                &nbsp;&nbsp;&nbsp;&nbsp;– Deep in stacks (±4 to ±6) → high-opportunity mean-reversion setups, even if the pre-session filter was cautious.
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 09:30 + 10:00 table (main + first 3 stacks)
            section_header("09:30 and 10:00 CT Map (Primary Scenario)")
            key_times = ["09:30", "10:00"]
            mask = primary_df["Time"].isin(key_times)
            focus_cols = ["Time", "Top_0", "Bottom_0"]
            for n in range(1, 4):
                focus_cols.extend(
                    [f"Top_+{n}", f"Bottom_+{n}", f"Top_-{n}", f"Bottom_-{n}"]
                )
            focus_cols = [c for c in focus_cols if c in primary_df.columns]
            focus_df = primary_df.loc[mask, focus_cols]

            st.dataframe(style_time_highlight(focus_df), use_container_width=True, height=160)

            # Dedicated 10:00 map with all stacks
            section_header("10:00 CT Stack Map (Primary Scenario)")
            ten_mask = primary_df["Time"] == "10:00"
            ten_df = primary_df.loc[ten_mask].copy()
            if ten_df.empty:
                st.info("No 10:00 row found in the grid (check pivot inputs).")
            else:
                st.dataframe(style_time_highlight(ten_df), use_container_width=True, height=140)
                st.download_button(
                    "Download 10:00 CT Stack Map (CSV)",
                    ten_df.to_csv(index=False).encode(),
                    "spx_10_00_stack_map.csv",
                    "text/csv",
                    use_container_width=True,
                    key="dl_10am",
                )
                st.markdown(
                    """
                    <div class="muted">
                    Mark these 10:00 CT values as horizontal levels on your chart:<br/>
                    • Main rails: <em>Top_0</em> and <em>Bottom_0</em>.<br/>
                    • Extension levels: <em>Top_±1…±6</em>, <em>Bottom_±1…±6</em> where available.<br/>
                    When price is sitting in stack 4–6 at 10:00, you are in the outer bands of the structure where sharp reversals back toward the main channel are common.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            section_header("Full Time-Aligned Map (Primary Scenario)")
            st.dataframe(style_time_highlight(primary_df), use_container_width=True, height=380)

            section_header("Alternate Scenario (For Context)")
            st.dataframe(style_time_highlight(alt_df), use_container_width=True, height=260)

        end_card()

    # ============================================
    # TAB 4: About
    # ============================================
    with tabs[3]:
        card("About the Planner", TAGLINE, badge="Reference")

        st.markdown(
            """
            <div class="spx-sub">
            <p>
            This tool is designed as an offline planner for SPX 0DTE structure trades. You choose the structural pivots from 
            the previous session or early overnight, and the app carries those rails forward on a uniform 30-minute grid.
            </p>

            <p>
            Both ascending and descending channels are always built from the same pivots. The difference in channel height 
            tells you how much room the market is offering in each scenario. Stacked rails at ±1 to ±6 channel heights give 
            you a map of where extension moves can exhaust before reversing.
            </p>

            <p>
            The goal is simple: arrive at the regular session with a clear, pre-defined structure, highlight the 09:30 and 
            10:00 CT rails, and let your execution follow the plan instead of the emotion of the moment.
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='muted'><strong>Reminder:</strong> This app does not stream live data, does not model options "
            "greeks, and does not guarantee outcomes. It gives you structure. What you do with that structure is where your edge lives.</div>",
            unsafe_allow_html=True,
        )

        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet • Offline structural planner for SPX 0DTE.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()