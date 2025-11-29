# spx_prophet.py
# Offline SPX structure + contract planner
# No EM channels, no APIs

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional, Dict, List

# ===============================
# CORE CONSTANTS
# ===============================

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."

# Underlying rails slope in pts / 30 min
SLOPE_MAG = 0.475

# Contract factor relative to SPX full-channel move
CONTRACT_FACTOR = 0.33  # your chosen factor

# No-trade filters (structure-only)
MIN_CHANNEL_HEIGHT = 45.0      # pts
MIN_CONTRACT_MOVE = 9.9        # units (0.33 * 30 pts ≈ 9.9)
MAX_HEIGHT_MISMATCH_RATIO = 0.4  # 40 percent mismatch between asc/desc

# Internal base reference (any fixed date/time in CT)
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 CT anchor


# ===============================
# LIGHT UI STYLING
# ===============================

def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 10% 0%, rgba(79, 70, 229, 0.06), transparent 55%),
                radial-gradient(circle at 90% 100%, rgba(37, 99, 235, 0.06), transparent 55%),
                linear-gradient(180deg, #ffffff 0%, #f8fafc 50%, #eff6ff 100%);
            background-attachment: fixed;
            color: #0f172a;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        }

        .block-container {
            padding-top: 3.0rem;
            padding-bottom: 3.5rem;
            max-width: 1350px;
        }

        [data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 0% 0%, rgba(79, 70, 229, 0.08), transparent 70%),
                linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.4);
            box-shadow: 6px 0 26px rgba(15, 23, 42, 0.08);
        }

        [data-testid="stSidebar"] h3 {
            font-family: 'Poppins', sans-serif;
            font-weight: 800;
            letter-spacing: -0.04em;
            font-size: 1.5rem;
            margin-bottom: 0.25rem;
            background: linear-gradient(135deg, #1e293b, #4f46e5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .sidebar-tagline {
            font-size: 0.9rem;
            color: #64748b;
            margin-bottom: 0.75rem;
        }

        .sidebar-chip {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(79, 70, 229, 0.06);
            border: 1px solid rgba(79, 70, 229, 0.2);
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #4f46e5;
            margin-top: 0.25rem;
        }

        .hero-shell {
            text-align: center;
            margin-bottom: 2.2rem;
        }

        .hero-card {
            display: inline-block;
            padding: 28px 40px 30px 40px;
            border-radius: 26px;
            background:
                radial-gradient(circle at 0% 0%, rgba(79, 70, 229, 0.09), transparent 60%),
                radial-gradient(circle at 100% 100%, rgba(59, 130, 246, 0.09), transparent 60%),
                linear-gradient(135deg, #ffffff, #f9fafb);
            border: 1px solid rgba(148, 163, 184, 0.5);
            box-shadow:
                0 26px 60px rgba(15, 23, 42, 0.16),
                0 1px 0 rgba(255, 255, 255, 0.7) inset;
        }

        .hero-title {
            font-family: 'Poppins', sans-serif;
            font-weight: 900;
            font-size: 2.4rem;
            letter-spacing: -0.06em;
            margin: 0;
            background: linear-gradient(120deg, #020617, #4f46e5, #2563eb);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-tagline {
            font-size: 1rem;
            color: #6b7280;
            margin-top: 0.4rem;
            margin-bottom: 0.9rem;
        }

        .hero-status {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 5px 14px;
            border-radius: 999px;
            background: rgba(22, 163, 74, 0.06);
            border: 1px solid rgba(22, 163, 74, 0.5);
            color: #15803d;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
        }

        .hero-status-dot {
            width: 8px;
            height: 8px;
            border-radius: 999px;
            background: #22c55e;
            box-shadow: 0 0 10px rgba(34, 197, 94, 0.9);
        }

        .hero-subnote {
            margin-top: 0.8rem;
            font-size: 0.9rem;
            color: #64748b;
        }

        .spx-card {
            border-radius: 22px;
            padding: 24px 26px;
            background: linear-gradient(135deg, #ffffff, #f9fafb);
            border: 1px solid rgba(148, 163, 184, 0.45);
            box-shadow:
                0 18px 45px rgba(15, 23, 42, 0.12),
                0 1px 0 rgba(255, 255, 255, 0.7) inset;
            margin-bottom: 1.5rem;
        }

        .spx-card h4 {
            font-family: 'Poppins', sans-serif;
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 0.25rem;
        }

        .spx-card-sub {
            font-size: 0.92rem;
            color: #6b7280;
        }

        .spx-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 999px;
            background: rgba(79, 70, 229, 0.06);
            border: 1px solid rgba(79, 70, 229, 0.25);
            color: #4f46e5;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            margin-bottom: 0.6rem;
        }

        .section-header {
            font-family: 'Poppins', sans-serif;
            font-size: 1.05rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #4b5563;
            padding-bottom: 0.45rem;
            margin-top: 1.3rem;
            margin-bottom: 0.6rem;
            border-bottom: 1px solid rgba(148, 163, 184, 0.6);
        }

        .muted-box {
            font-size: 0.9rem;
            color: #6b7280;
            background: rgba(148, 163, 184, 0.12);
            border-radius: 14px;
            padding: 10px 12px;
            border-left: 3px solid #4f46e5;
            margin-top: 0.4rem;
        }

        .metric-shell {
            border-radius: 18px;
            padding: 14px 16px;
            background: linear-gradient(135deg, #ffffff, #eff6ff);
            border: 1px solid rgba(148, 163, 184, 0.5);
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.12);
        }

        .metric-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: #6b7280;
            margin-bottom: 0.15rem;
        }

        .metric-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1.25rem;
            color: #111827;
        }

        .metric-note {
            font-size: 0.8rem;
            color: #6b7280;
            margin-top: 0.3rem;
        }

        .status-pill-good {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(22, 163, 74, 0.06);
            border: 1px solid rgba(22, 163, 74, 0.5);
            color: #15803d;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
        }

        .status-pill-warn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(248, 113, 113, 0.06);
            border: 1px solid rgba(248, 113, 113, 0.6);
            color: #b91c1c;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
        }

        .app-footer {
            margin-top: 2.4rem;
            padding-top: 1.2rem;
            border-top: 1px solid rgba(148, 163, 184, 0.6);
            font-size: 0.85rem;
            color: #9ca3af;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero():
    st.markdown(
        f"""
        <div class="hero-shell">
          <div class="hero-card">
            <div class="hero-status">
                <div class="hero-status-dot"></div>
                SYSTEM ACTIVE
            </div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <div class="hero-tagline">{TAGLINE}</div>
            <div class="hero-subnote">
                Two pivots define your rails. Stacked structure frames your risk.
                Contracts follow the structure, not your emotions.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def open_card(title: str, subtitle: str = "", badge: Optional[str] = None):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if badge:
        st.markdown(f'<div class="spx-pill">{badge}</div>', unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="spx-card-sub">{subtitle}</div>', unsafe_allow_html=True)


def close_card():
    st.markdown("</div>", unsafe_allow_html=True)


def section_header(text: str):
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def metric_card(label: str, value: str, note: Optional[str] = None):
    html = f"""
    <div class="metric-shell">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
    """
    if note:
        html += f'<div class="metric-note">{note}</div>'
    html += "</div>"
    return html


# ===============================
# TIME / BLOCK HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map a CT time into a 30-minute grid relative to BASE_DATE.
    Times >= 15:00 are treated as the 'prior' day,
    times < 15:00 as the 'next' day (overnight into RTH).
    """
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    """
    Snap a datetime to the nearest 30-minute block.
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
    RTH grid for the 'new' day: 08:30–14:30 CT in 30-minute blocks.
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
    Build ascending or descending channel from two pivots.
    Returns dataframe with main rails + stacked rails, and channel height.
    """
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))

    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

    # top and bottom intercepts
    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo

    channel_height = b_top - b_bottom  # can be negative depending on sign; we normalize later
    slots = rth_slots()

    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        top = s * k + b_top
        bottom = s * k + b_bottom
        # stack rails +/- 1 height
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Top Rail": round(top, 4),
                "Bottom Rail": round(bottom, 4),
                "Top +1H": round(top + channel_height, 4),
                "Bottom -1H": round(bottom - channel_height, 4),
            }
        )

    df = pd.DataFrame(rows)
    # absolute height for metrics
    return df, round(abs(channel_height), 4)


# ===============================
# CONTRACT LINE ENGINE (OPTIONAL)
# ===============================

def build_contract_line(
    anchor_a_time: dtime,
    anchor_a_price: float,
    anchor_b_time: dtime,
    anchor_b_price: float,
) -> Tuple[pd.DataFrame, float]:
    """
    Simple linear contract line on same 30m grid.
    Purely structural, not a full options model.
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

    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        price = slope * k + b
        rows.append({"Time": dt.strftime("%H:%M"), "Contract Line": round(price, 4)})

    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# PRIMARY SCENARIO SUGGESTION
# ===============================

def score_scenario_for_close(
    df: pd.DataFrame, height: float, close_price: float, close_time: dtime
) -> float:
    """
    Heuristic score:
    - Prefer scenarios where prior close sits inside the rails.
    - Prefer close near midline rather than far outside.
    """
    if df is None or df.empty or height <= 0:
        return -999.0

    # Align time to grid
    dt_close = align_30min(make_dt_from_time(close_time))
    t_str = dt_close.strftime("%H:%M")

    if t_str in df["Time"].values:
        row = df[df["Time"] == t_str].iloc[0]
    else:
        # nearest neighbor if off-grid
        times = pd.to_datetime(df["Time"], format="%H:%M")
        diffs = (times - dt_close).abs()
        idx = diffs.idxmin()
        row = df.loc[idx]

    top = float(row["Top Rail"])
    bottom = float(row["Bottom Rail"])
    lo, hi = sorted([bottom, top])

    inside = lo <= close_price <= hi
    mid = (lo + hi) / 2.0
    dist_mid = abs(close_price - mid)

    # normalize distance by height
    norm_dist = dist_mid / height if height > 0 else 1e9

    score = 0.0
    if inside:
        score += 2.0
    # penalize being far from mid
    score -= norm_dist
    return score


def suggest_primary_scenario(
    df_asc: Optional[pd.DataFrame],
    h_asc: Optional[float],
    df_desc: Optional[pd.DataFrame],
    h_desc: Optional[float],
    close_price: float,
    close_time: dtime,
) -> str:
    if df_asc is None or h_asc is None or df_desc is None or h_desc is None:
        return "Ascending"  # default

    score_asc = score_scenario_for_close(df_asc, h_asc, close_price, close_time)
    score_desc = score_scenario_for_close(df_desc, h_desc, close_price, close_time)

    return "Ascending" if score_asc >= score_desc else "Descending"


# ===============================
# NO-TRADE FILTERS
# ===============================

def evaluate_no_trade(
    primary_height: float,
    contract_move_struct: float,
    h_asc: Optional[float],
    h_desc: Optional[float],
) -> Tuple[bool, List[str]]:
    flags: List[str] = []

    if primary_height < MIN_CHANNEL_HEIGHT:
        flags.append(
            f"Primary channel height is shallow ({primary_height:.1f} pts < {MIN_CHANNEL_HEIGHT:.0f} pts)."
        )

    if contract_move_struct < MIN_CONTRACT_MOVE:
        flags.append(
            f"Expected contract move at 0.33 factor is small ({contract_move_struct:.1f} < {MIN_CONTRACT_MOVE:.1f})."
        )

    if h_asc is not None and h_desc is not None and max(h_asc, h_desc) > 0:
        mismatch_ratio = abs(h_asc - h_desc) / max(h_asc, h_desc)
        if mismatch_ratio > MAX_HEIGHT_MISMATCH_RATIO:
            flags.append(
                f"Ascending vs descending channel heights disagree by more than {MAX_HEIGHT_MISMATCH_RATIO*100:.0f}%."
            )

    no_trade = len(flags) > 0
    return no_trade, flags


# ===============================
# ACTIVE SCENARIO HELPERS
# ===============================

def get_primary_df(
    primary_label: str,
    df_asc: Optional[pd.DataFrame],
    h_asc: Optional[float],
    df_desc: Optional[pd.DataFrame],
    h_desc: Optional[float],
) -> Tuple[Optional[pd.DataFrame], Optional[float]]:
    if primary_label == "Ascending":
        return df_asc, h_asc
    else:
        return df_desc, h_desc


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

    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(f'<div class="sidebar-tagline">{TAGLINE}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-chip">Structure First • Emotion Last</div>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG} pts / 30m**")
        st.write(f"Contract factor: **{CONTRACT_FACTOR:.2f} × SPX channel move**")
        st.caption(
            "• Underlying maintenance: 16:00–17:00 CT\n"
            "• Contracts maintenance: 16:00–19:00 CT\n"
            "• RTH grid: 08:30–14:30 CT (30m blocks)\n"
            "• You select pivots. The app carries the structure."
        )

    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "📐 Contract Plan",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # ----------------------------------
    # TAB 1: RAILS SETUP
    # ----------------------------------
    with tabs[0]:
        open_card(
            "Rails + Stacks",
            "Define your two key pivots, build both ascending and descending channels, "
            "and see stacked rails for extension reversals.",
            badge="Structure Engine",
        )

        section_header("Underlying Pivots (Prior Structure)")

        st.markdown(
            """
            Use the **structural high and low pivots** from the prior regular session or the early Globex window (17:00–21:00 CT).
            Work from your line chart. These are the main turning points that defined the day, not necessarily wick extremes.
            All times you enter here are CT.
            """,
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

        section_header("Prior Close (For Scenario Scoring)")
        c3, c4 = st.columns(2)
        with c3:
            close_price = st.number_input(
                "Prior session close price",
                value=6650.0,
                step=0.25,
                key="prior_close_price",
            )
        with c4:
            close_time = st.time_input(
                "Prior session close time (CT)",
                value=dtime(15, 0),
                step=1800,
                key="prior_close_time",
            )

        st.markdown("")
        build_col = st.columns([1, 3])[0]
        with build_col:
            clicked_build = st.button("Build Channels", use_container_width=True)

        if clicked_build:
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
            st.session_state["df_asc"] = df_asc
            st.session_state["h_asc"] = h_asc
            st.session_state["df_desc"] = df_desc
            st.session_state["h_desc"] = h_desc
            st.session_state["close_price_internal"] = close_price
            st.session_state["close_time_internal"] = close_time
            st.success("Channels built. Inspect the structure and then move to Daily Foresight for the plan.")

        df_asc = st.session_state.get("df_asc")
        h_asc = st.session_state.get("h_asc")
        df_desc = st.session_state.get("df_desc")
        h_desc = st.session_state.get("h_desc")

        if df_asc is None or df_desc is None:
            st.info("Build channels to see ascending / descending structures and stacked rails.")
            close_card()
        else:
            section_header("Ascending Channel (Structure)")
            c_top = st.columns([3, 1])
            with c_top[0]:
                st.dataframe(df_asc, use_container_width=True, hide_index=True, height=330)
            with c_top[1]:
                st.markdown(
                    metric_card(
                        "Height (Ascending)",
                        f"{h_asc:.2f} pts",
                        note="Top / bottom rails projected on 30m CT grid.",
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown("")
                st.download_button(
                    "Download ascending rails CSV",
                    df_asc.to_csv(index=False).encode(),
                    "spx_ascending_rails.csv",
                    "text/csv",
                    use_container_width=True,
                )

            section_header("Descending Channel (Structure)")
            c_bot = st.columns([3, 1])
            with c_bot[0]:
                st.dataframe(df_desc, use_container_width=True, hide_index=True, height=330)
            with c_bot[1]:
                st.markdown(
                    metric_card(
                        "Height (Descending)",
                        f"{h_desc:.2f} pts",
                        note="Same pivots, opposite slope direction.",
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown("")
                st.download_button(
                    "Download descending rails CSV",
                    df_desc.to_csv(index=False).encode(),
                    "spx_descending_rails.csv",
                    "text/csv",
                    use_container_width=True,
                )

            section_header("Primary Structural Scenario")

            # Suggested primary from prior close
            cp = st.session_state.get("close_price_internal", close_price)
            ct = st.session_state.get("close_time_internal", close_time)
            suggested = suggest_primary_scenario(df_asc, h_asc, df_desc, h_desc, cp, ct)

            options = ["Ascending", "Descending"]
            default_index = 0 if suggested == "Ascending" else 1

            primary_choice = st.radio(
                "Suggested primary scenario (you can override):",
                options,
                index=default_index,
                horizontal=True,
                key="primary_choice_radio",
            )

            # Highlight suggestion
            if primary_choice == suggested:
                st.markdown(
                    '<div class="status-pill-good">Using suggested scenario based on prior close.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="status-pill-warn">Manual override: using non-suggested scenario.</div>',
                    unsafe_allow_html=True,
                )

            st.session_state["primary_scenario_label"] = primary_choice
            close_card()

    # ----------------------------------
    # TAB 2: CONTRACT PLAN
    # ----------------------------------
    with tabs[1]:
        open_card(
            "Contract Plan",
            "Use a simple structural line for your contract and pair it with a 0.33×channel move target.",
            badge="Contract Engine",
        )

        st.markdown(
            """
            This tab is optional. You can:
            * Anchor a simple **contract line** with two prices and times, just to see time alignment.
            * Use the **0.33 factor** on the Daily Foresight tab to size your exit target.
            """
        )

        section_header("Anchor Points (Contract Line)")

        c1, c2 = st.columns(2)
        with c1:
            anchor_a_time = st.time_input(
                "Anchor A time (CT)",
                value=dtime(15, 0),
                step=1800,
                key="contract_anchor_a_time",
            )
            anchor_a_price = st.number_input(
                "Contract price at Anchor A time",
                value=10.0,
                step=0.1,
                key="contract_anchor_a_price",
            )
        with c2:
            anchor_b_time = st.time_input(
                "Anchor B time (CT)",
                value=dtime(9, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
            anchor_b_price = st.number_input(
                "Contract price at Anchor B time",
                value=7.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        st.markdown("")
        build_contract_clicked = st.button("Build Contract Line", use_container_width=True)

        if build_contract_clicked:
            df_contract, slope_contract = build_contract_line(
                anchor_a_time=anchor_a_time,
                anchor_a_price=anchor_a_price,
                anchor_b_time=anchor_b_time,
                anchor_b_price=anchor_b_price,
            )
            st.session_state["df_contract"] = df_contract
            st.session_state["slope_contract"] = slope_contract
            st.success("Contract line projected on the same 30-minute grid as the rails.")

        df_contract = st.session_state.get("df_contract")
        slope_contract = st.session_state.get("slope_contract")

        if df_contract is None:
            st.info("Build a contract line if you want to see its time alignment against the rails.")
        else:
            c3, c4 = st.columns([3, 1])
            with c3:
                st.dataframe(df_contract, use_container_width=True, hide_index=True, height=330)
            with c4:
                st.markdown(
                    metric_card(
                        "Contract Line Slope",
                        f"{slope_contract:+.4f} / 30m",
                        note="Purely structural line between your two anchors.",
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown("")
                st.download_button(
                    "Download contract line CSV",
                    df_contract.to_csv(index=False).encode(),
                    "contract_line.csv",
                    "text/csv",
                    use_container_width=True,
                )

        close_card()

    # ----------------------------------
    # TAB 3: DAILY FORESIGHT
    # ----------------------------------
    with tabs[2]:
        open_card(
            "Daily Foresight",
            "One page that combines primary rails, stacked channels, no-trade filters, "
            "and a contract target using the 0.33 factor.",
            badge="Foresight Map",
        )

        df_asc = st.session_state.get("df_asc")
        h_asc = st.session_state.get("h_asc")
        df_desc = st.session_state.get("df_desc")
        h_desc = st.session_state.get("h_desc")
        primary_label = st.session_state.get("primary_scenario_label", "Ascending")
        df_contract = st.session_state.get("df_contract")

        if df_asc is None or df_desc is None or h_asc is None or h_desc is None:
            st.warning("Build channels on the Rails Setup tab first.")
            close_card()
        else:
            # choose primary dataframe
            df_primary, h_primary = get_primary_df(primary_label, df_asc, h_asc, df_desc, h_desc)
            if df_primary is None or h_primary is None:
                st.warning("Primary scenario not available. Rebuild channels on Rails Setup.")
                close_card()
            else:
                # Structural contract move
                contract_move_struct = h_primary * CONTRACT_FACTOR

                # No-trade evaluation
                no_trade, flags = evaluate_no_trade(h_primary, contract_move_struct, h_asc, h_desc)

                # STRUCTURE SUMMARY
                section_header("Structure Summary")

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(
                        metric_card(
                            "Primary Scenario",
                            primary_label,
                            note="Suggested from prior close; you can override on Rails tab.",
                        ),
                        unsafe_allow_html=True,
                    )
                with c2:
                    st.markdown(
                        metric_card(
                            "Channel Height",
                            f"{h_primary:.2f} pts",
                            note="Distance from bottom rail to top rail on RTH grid.",
                        ),
                        unsafe_allow_html=True,
                    )
                with c3:
                    st.markdown(
                        metric_card(
                            "Contract Move (0.33×Height)",
                            f"{contract_move_struct:.2f} units",
                            note="This is your structural target size for a full rail-to-rail move.",
                        ),
                        unsafe_allow_html=True,
                    )

                st.markdown("")
                if no_trade:
                    st.markdown(
                        '<div class="status-pill-warn">STRUCTURAL NO-TRADE / SCALP-ONLY DAY</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="status-pill-good">STRUCTURE IS TRADE-ABLE</div>',
                        unsafe_allow_html=True,
                    )

                if flags:
                    st.markdown("<br/>**Reasons:**", unsafe_allow_html=True)
                    for f in flags:
                        st.markdown(f"- {f}")

                # CONTRACT TRADE PLAN (FACTOR-BASED)
                section_header("Contract Trade Plan (Factor-Based)")

                st.markdown(
                    """
                    The app does **not** try to model full options behavior.  
                    It simply tells you: *“If SPX traverses the full primary channel, a contract sized at 0.33×SPX move should
                    give roughly this magnitude of change.”*
                    """
                )

                cdir, centry = st.columns(2)
                with cdir:
                    trade_dir = st.radio(
                        "Planned trade",
                        ["Long Call (bottom → top)", "Long Put (top → bottom)"],
                        index=0,
                        horizontal=True,
                        key="foresight_trade_direction",
                    )
                with centry:
                    entry_contract_price = st.number_input(
                        "Your planned contract entry price",
                        value=5.00,
                        step=0.1,
                        key="foresight_entry_contract_price",
                    )

                target_exit = entry_contract_price + contract_move_struct
                pnl_size = contract_move_struct

                c4, c5, c6 = st.columns(3)
                with c4:
                    st.markdown(
                        metric_card(
                            "Planned Entry",
                            f"{entry_contract_price:.2f}",
                            note="Your chosen fill when the rail interaction appears.",
                        ),
                        unsafe_allow_html=True,
                    )
                with c5:
                    st.markdown(
                        metric_card(
                            "Target Exit (Size-Based)",
                            f"{target_exit:.2f}",
                            note="Entry + 0.33×channel height.",
                        ),
                        unsafe_allow_html=True,
                    )
                with c6:
                    st.markdown(
                        metric_card(
                            "Projected Contract Move Size",
                            f"{pnl_size:.2f}",
                            note="Magnitude only. Direction is defined by your trade (call or put).",
                        ),
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    """
                    <div class="muted-box">
                    <strong>How to read this:</strong> If price travels from one rail to the opposite rail in your primary channel,
                    this is the sort of contract move you are structurally targeting.  
                    The **timing of the touch** and the **shape of the move** will add or subtract extra edge.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # TIME / RAIL MAP
                section_header("Time-Aligned Map (Primary Scenario)")

                if df_contract is not None:
                    merged = df_primary.merge(df_contract, on="Time", how="left")
                else:
                    merged = df_primary.copy()
                    merged["Contract Line"] = None

                st.caption(
                    "Each row is a 30-minute slot in the RTH session (CT). "
                    "Top / bottom show the main channel. Top +1H / Bottom -1H are one full channel-height stacked rails."
                )
                st.dataframe(merged, use_container_width=True, hide_index=True, height=420)

                st.markdown(
                    """
                    <div class="muted-box">
                    <strong>Reading this table:</strong>  
                    • You do not know <em>when</em> SPX will tag a rail.  
                    • The table tells you: “If it tags at this time, this is the structural level.”  
                    Use your own tape reading, timing rules (09:30–11:00 CT focus), and contract factor to decide if the day is worth trading.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # TIMING GUIDANCE
                section_header("Timing Notes (CT Focus)")

                st.markdown(
                    """
                    * Most of the **clean, tradable reversals** cluster between **09:30 and 11:00 CT**.  
                    * The most important slots to watch around your rails are usually **09:30**, **10:00**, and **10:30 CT**.  
                    * Entries **before 09:00 CT** are rare “gift” days. Treat them as advanced plays, not your default.  
                    * If there has been **no meaningful interaction with your rails by 11:00 CT**, treat the day as lower quality or scalp-only, even if the structure passes the filters.
                    """
                )

                close_card()

    # ----------------------------------
    # TAB 4: ABOUT
    # ----------------------------------
    with tabs[3]:
        open_card("About SPX Prophet", TAGLINE, badge="Offline Structure Tool")

        st.markdown(
            """
            This app is intentionally **offline** and **structure-only**:

            * You **choose the pivots** from your own charts (prior RTH, early Globex, or both).
            * The app projects **ascending and descending channels** using a fixed slope of **0.475 pts / 30 min**.
            * It uses those channels to compute **stacked rails**, giving you a map for extension reversals.
            * It suggests a **primary structural scenario** based on where the prior close sits relative to each channel.
            * It applies **no-trade filters** using only:
              - Channel height  
              - Ascending vs descending agreement  
              - Expected contract move using your **0.33 factor**  

            The goal is not to predict the future.  
            The goal is to make sure that when you sit down to trade, the **structure is already drawn**,  
            your **risk is already framed**, and your **contract exits are sized** before the first 30-minute candle prints.
            """
        )

        st.markdown(
            """
            <div class="muted-box">
            <strong>Design principle:</strong> The rails do the heavy lifting.  
            Your job is to wait, listen, and only move when price and time agree with your map.
            </div>
            """,
            unsafe_allow_html=True,
        )

        close_card()

    st.markdown(
        f'<div class="app-footer">© 2025 {APP_NAME}. Built for manual pivots, clean structure, and disciplined execution.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()