import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime, date as ddate
from typing import Tuple, Optional

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475
CONTRACT_FACTOR_DEFAULT = 0.30
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # anchor for 30m blocks


# ===============================
# UI THEME
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(79, 70, 229, 0.05), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(37, 99, 235, 0.05), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 40%, #eef2f7 100%);
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

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 10% 0%, rgba(79, 70, 229, 0.08), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            8px 0 30px rgba(15, 23, 42, 0.08);
    }

    [data-testid="stSidebar"] h3 {
        font-size: 1.6rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #111827 0%, #4f46e5 40%, #2563eb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
        letter-spacing: -0.04em;
    }

    [data-testid="stSidebar"] hr {
        margin: 1.5rem 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(148, 163, 184, 0.8) 40%,
            rgba(148, 163, 184, 0.4) 60%,
            transparent 100%);
    }

    /* CENTERED HERO */
    .hero-wrap {
        text-align: center;
        margin-bottom: 2.5rem;
    }

    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 16px;
        border-radius: 999px;
        background: rgba(22, 163, 74, 0.06);
        border: 1px solid rgba(22, 163, 74, 0.3);
        color: #166534;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 10px;
    }

    .hero-title {
        font-size: 2.6rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        letter-spacing: -0.06em;
        margin-bottom: 0.35rem;
        background: linear-gradient(135deg, #020617 0%, #1d4ed8 45%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        color: #64748b;
        max-width: 540px;
        margin: 0 auto;
    }

    .hero-chip-row {
        display: flex;
        justify-content: center;
        gap: 10px;
        margin-top: 14px;
        flex-wrap: wrap;
    }

    .hero-chip {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: #4b5563;
        background: #ffffff;
        border-radius: 999px;
        padding: 6px 14px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
    }

    /* CARD SHELL */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 0% 0%, rgba(79, 70, 229, 0.06), transparent 55%),
            radial-gradient(circle at 100% 100%, rgba(37, 99, 235, 0.05), transparent 55%),
            linear-gradient(135deg, #ffffff, #f9fafb);
        border-radius: 28px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        box-shadow:
            0 20px 50px rgba(15, 23, 42, 0.07),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
        padding: 28px 30px;
        margin-bottom: 26px;
        overflow: hidden;
        transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
    }

    .spx-card:hover {
        transform: translateY(-4px);
        border-color: rgba(79, 70, 229, 0.5);
        box-shadow:
            0 26px 70px rgba(15, 23, 42, 0.13);
    }

    .spx-card h4 {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        margin: 0 0 4px 0;
        color: #0f172a;
        letter-spacing: -0.04em;
    }

    .spx-sub {
        color: #6b7280;
        font-size: 0.98rem;
        line-height: 1.7;
    }

    .icon-large {
        font-size: 2.4rem;
        display: inline-block;
        margin-bottom: 8px;
        filter: drop-shadow(0 8px 16px rgba(15, 23, 42, 0.2));
    }

    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 999px;
        background: #eff6ff;
        border: 1px solid rgba(59, 130, 246, 0.4);
        color: #1d4ed8;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 10px;
    }

    .spx-pill::before {
        content: "";
        width: 6px;
        height: 6px;
        border-radius: 999px;
        background: #22c55e;
    }

    .section-header {
        font-size: 1.35rem;
        font-weight: 800;
        font-family: 'Poppins',sans-serif;
        color: #0f172a;
        margin: 1.8rem 0 1.1rem 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .section-header::before {
        content: "";
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: linear-gradient(135deg, #4f46e5, #0ea5e9);
        box-shadow: 0 0 0 4px rgba(129, 140, 248, 0.35);
    }

    /* METRICS */
    .spx-metric {
        padding: 18px 18px;
        border-radius: 18px;
        background: linear-gradient(135deg, #ffffff, #f3f4ff);
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow:
            0 14px 30px rgba(15, 23, 42, 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.9);
    }

    .spx-metric-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: #6b7280;
        margin-bottom: 6px;
    }

    .spx-metric-value {
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #111827;
        letter-spacing: -0.03em;
    }

    /* INPUTS */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 1px solid rgba(148, 163, 184, 0.9) !important;
        border-radius: 14px !important;
        color: #0f172a !important;
        padding: 10px 12px !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: #4f46e5 !important;
        box-shadow: 0 0 0 1px rgba(79, 70, 229, 0.3) !important;
    }

    .stSelectbox>div>div {
        background: #ffffff;
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.9);
    }

    label {
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        color: #4b5563 !important;
        margin-bottom: 4px !important;
    }

    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: #e5e7eb;
        padding: 4px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.7);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        font-size: 0.9rem;
        font-weight: 600;
        padding: 6px 16px;
        color: #4b5563;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #ffffff;
        color: #111827;
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.12);
    }

    /* TABLE */
    .stDataFrame {
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
        border: 1px solid rgba(148, 163, 184, 0.7);
    }

    .muted {
        color: #4b5563;
        font-size: 0.92rem;
        line-height: 1.7;
        padding: 14px 16px;
        background: #f9fafb;
        border-left: 3px solid #4f46e5;
        border-radius: 10px;
        margin: 10px 0 0 0;
    }

    .app-footer {
        margin-top: 2.5rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(148, 163, 184, 0.6);
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
        <div class="hero-wrap">
            <div class="hero-badge">System Active · Structure First</div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">{TAGLINE}</p>
            <div class="hero-chip-row">
                <div class="hero-chip">Slope 0.475 pts / 30m</div>
                <div class="hero-chip">Contract Factor 0.30</div>
                <div class="hero-chip">RTH Grid 08:30–14:30 CT</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None, icon: str = ""):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    if icon:
        st.markdown(f"<div class='icon-large'>{icon}</div>", unsafe_allow_html=True)
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
    """Map a time-of-day into the BASE_DATE grid (previous or next day handling)."""
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    """Snap arbitrary dt to nearest half-hour block."""
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """RTH grid 08:30–14:30 on the 'next' day relative to BASE_DATE."""
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


# ===============================
# PIVOT SUGGESTION (YFINANCE) – MULTIINDEX-SAFE
# ===============================

def suggest_pivots_from_yahoo(ticker: str, session_date: ddate):
    """
    Try to suggest previous session high/low pivots from Yahoo Finance.
    Uses 30m candles around the given session_date.
    Safely returns None on any problem, instead of crashing.
    """
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        st.warning("yfinance is not installed in this environment. Please enter pivots manually.")
        return None

    try:
        # Request 2 days around the session date to be safe.
        start = session_date - timedelta(days=1)
        end = session_date + timedelta(days=1)

        data = yf.download(
            ticker,
            start=start,
            end=end,
            interval="30m",
            progress=False,
        )

        if data is None or data.empty:
            st.warning("No intraday data returned from Yahoo. Please enter pivots manually.")
            return None

        # Flatten possible MultiIndex columns to simple strings
        if isinstance(data.columns, pd.MultiIndex):
            flat_cols = []
            for col in data.columns:
                # take the first level name if available
                if isinstance(col, tuple) and len(col) > 0:
                    flat_cols.append(str(col[0]))
                else:
                    flat_cols.append(str(col))
            data.columns = flat_cols
        else:
            data.columns = [str(c) for c in data.columns]

        # Make sure we have High/Low columns present
        cols_lower = [c.lower() for c in data.columns]
        if not any("high" == c or " high" in c or "high " in c for c in cols_lower) or \
           not any("low" == c or " low" in c or "low " in c for c in cols_lower):
            st.warning("Downloaded data does not contain recognizable High/Low columns.")
            return None

        # Normalize column names exactly to 'High' and 'Low'
        rename_map = {}
        for c in data.columns:
            lc = c.lower()
            if "high" == lc or lc.endswith(" high") or lc.startswith("high "):
                rename_map[c] = "High"
            if "low" == lc or lc.endswith(" low") or lc.startswith("low "):
                rename_map[c] = "Low"
        if rename_map:
            data = data.rename(columns=rename_map)

        if "High" not in data.columns or "Low" not in data.columns:
            st.warning("After normalization, High/Low still not found. Please enter pivots manually.")
            return None

        # Timezone handling
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC").tz_convert("US/Central")
        else:
            data.index = data.index.tz_convert("US/Central")

        # Select candles for the requested session_date during 08:30–15:00 CT
        mask = (
            (data.index.date == session_date)
            & (data.index.time >= dtime(8, 30))
            & (data.index.time <= dtime(15, 0))
        )
        day_data = data.loc[mask]

        if day_data.empty:
            st.warning("No RTH data for that date. Please enter pivots manually.")
            return None

        hi_ser = day_data["High"]
        lo_ser = day_data["Low"]

        if hi_ser.isna().all() or lo_ser.isna().all():
            st.warning("High/Low data for that day is all NaN. Please enter pivots manually.")
            return None

        hi_price = float(hi_ser.max())
        lo_price = float(lo_ser.min())

        hi_idx = hi_ser.idxmax()
        lo_idx = lo_ser.idxmin()

        # Extract local time-of-day
        try:
            hi_time = hi_idx.to_pydatetime().astimezone().time()
        except Exception:
            hi_time = hi_idx.to_pydatetime().time()

        try:
            lo_time = lo_idx.to_pydatetime().astimezone().time()
        except Exception:
            lo_time = lo_idx.to_pydatetime().time()

        return hi_price, hi_time, lo_price, lo_time

    except Exception as e:
        st.warning(f"Could not fetch pivot suggestion from Yahoo Finance. Reason: {e}")
        return None


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
    channel_height = b_top - b_bottom  # may be negative depending on sign

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
    return df, float(abs(round(channel_height, 4)))


# ===============================
# CONTRACT ENGINE
# ===============================

def build_contract_projection_from_anchors(
    anchor_a_time: dtime,
    anchor_a_price: float,
    anchor_b_time: dtime,
    anchor_b_price: float,
) -> Tuple[pd.DataFrame, float]:
    """Linear contract path from two anchor prices on same time grid."""
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
        rows.append({"Time": dt.strftime("%H:%M"), "Contract Price": round(price, 4)})
    df = pd.DataFrame(rows)
    return df, float(round(slope, 6))


def estimate_contract_full_swing_from_factor(
    channel_height: float, factor: float
) -> float:
    """Simple factor mapping of underlying move to contract move."""
    return float(round(channel_height * factor, 2))


# ===============================
# DAILY FORESIGHT HELPERS
# ===============================

def get_active_channel() -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[float]]:
    mode = st.session_state.get("channel_mode")
    df_asc = st.session_state.get("channel_asc_df")
    df_desc = st.session_state.get("channel_desc_df")
    h_asc = st.session_state.get("channel_asc_height")
    h_desc = st.session_state.get("channel_desc_height")

    if mode == "Ascending":
        return "Ascending", df_asc, h_asc
    if mode == "Descending":
        return "Descending", df_desc, h_desc
    if mode == "Both":
        scenario = st.selectbox(
            "Which structural scenario are you following today?",
            ["Ascending", "Descending"],
            index=0,
            key="foresight_scenario",
        )
        if scenario == "Ascending":
            return "Ascending", df_asc, h_asc
        else:
            return "Descending", df_desc, h_desc
    return None, None, None


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

    # SIDEBAR
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.caption(TAGLINE)
        st.markdown("---")

        st.markdown("#### Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG} pts / 30m**")
        st.write(f"Contract factor: **{CONTRACT_FACTOR_DEFAULT:.2f} × SPX move**")

        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "Underlying: 16:00–17:00 CT maintenance\n\n"
            "Contracts: 16:00–19:00 CT maintenance\n\n"
            "RTH projection grid: 08:30–14:30 CT (30m blocks)."
        )

    hero()

    tabs = st.tabs(
        [
            "🧱 Rails Setup",
            "📐 Contract Setup",
            "🔮 Daily Foresight",
            "ℹ️ About",
        ]
    )

    # TAB 1: RAILS
    with tabs[0]:
        card(
            "Structure Engine",
            "Build ascending and descending channels from your chosen pivots. "
            "Optionally, let Yahoo suggest yesterday’s pivots, then you refine.",
            badge="Rails",
            icon="🧱",
        )

        section_header("⚙️ Underlying Pivots (Previous Session)")
        st.markdown(
            "<div class='spx-sub'>Use the key swing high and low from the previous RTH session. "
            "Times are the actual 30-minute pivot times on your chart.</div>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### High Pivot")
            high_price = st.number_input(
                "High pivot price",
                value=5200.0,
                step=0.25,
                key="pivot_high_price",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(13, 0),
                step=1800,
                key="pivot_high_time",
            )
        with c2:
            st.markdown("##### Low Pivot")
            low_price = st.number_input(
                "Low pivot price",
                value=5100.0,
                step=0.25,
                key="pivot_low_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(10, 0),
                step=1800,
                key="pivot_low_time",
            )

        with st.expander("🔍 Optional: Let Yahoo suggest yesterday’s pivots"):
            ticker = st.text_input("Ticker (Yahoo symbol)", value="^SPX", key="yahoo_ticker")
            session_date = st.date_input(
                "Session date for pivots",
                value=ddate.today() - timedelta(days=1),
                key="yahoo_session_date",
            )
            if st.button("Fetch suggested pivots", key="btn_fetch_pivots"):
                suggestion = suggest_pivots_from_yahoo(ticker.strip(), session_date)
                if suggestion is not None:
                    hi_price, hi_time_s, lo_price, lo_time_s = suggestion
                    st.success(
                        f"Suggested high pivot: {hi_price:.2f} at {hi_time_s.strftime('%H:%M')} CT\n\n"
                        f"Suggested low pivot: {lo_price:.2f} at {lo_time_s.strftime('%H:%M')} CT\n\n"
                        "You can now manually enter or adjust these in the pivot inputs above.",
                    )

        section_header("📊 Channel Regime")
        mode = st.radio(
            "Channel mode",
            ["Ascending", "Descending", "Both"],
            index=2,
            key="channel_mode",
            horizontal=True,
        )

        build_btn_col = st.columns([1, 3])[0]
        with build_btn_col:
            if st.button("Build Rails", key="btn_build_rails", use_container_width=True):
                # Ascending rails
                df_asc, h_asc = build_channel(
                    high_price=high_price,
                    high_time=high_time,
                    low_price=low_price,
                    low_time=low_time,
                    slope_sign=+1,
                )
                st.session_state["channel_asc_df"] = df_asc
                st.session_state["channel_asc_height"] = h_asc

                # Descending rails
                df_desc, h_desc = build_channel(
                    high_price=high_price,
                    high_time=high_time,
                    low_price=low_price,
                    low_time=low_time,
                    slope_sign=-1,
                )
                st.session_state["channel_desc_df"] = df_desc
                st.session_state["channel_desc_height"] = h_desc

                st.success("Rails generated for both ascending and descending structures.")

        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        section_header("📊 Underlying Rails • RTH 08:30–14:30 CT")

        if df_asc is None or df_desc is None:
            st.info("Build rails to view the channel projections.")
        else:
            st.markdown("##### Ascending Channel")
            asc_cols = st.columns([3, 1])
            with asc_cols[0]:
                st.dataframe(df_asc, use_container_width=True, hide_index=True, height=320)
            with asc_cols[1]:
                st.markdown(metric_card("Channel Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)

            st.markdown("##### Descending Channel")
            desc_cols = st.columns([3, 1])
            with desc_cols[0]:
                st.dataframe(df_desc, use_container_width=True, hide_index=True, height=320)
            with desc_cols[1]:
                st.markdown(metric_card("Channel Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)

        end_card()

    # TAB 2: CONTRACT
    with tabs[1]:
        card(
            "Contract Line Setup",
            "Project a simple contract line using two anchor prices, and optionally apply a "
            "contract factor to relate full-channel SPX moves to contract targets.",
            badge="Contracts",
            icon="📐",
        )

        section_header("⚓ Contract Anchors (Linear Path)")
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
                value=dtime(10, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
            anchor_b_price = st.number_input(
                "Contract price at Anchor B",
                value=6.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        st.markdown(
            "<div class='muted'>These two anchors define a straight contract line on the same 30-minute grid "
            "as your rails. It will never fully capture gamma spikes, but it gives you a structural expectation "
            "for contract value at each potential rail tag.</div>",
            unsafe_allow_html=True,
        )

        section_header("📏 Contract Factor")
        factor = st.number_input(
            "Contract factor (× underlying full-channel move)",
            value=CONTRACT_FACTOR_DEFAULT,
            step=0.05,
            min_value=0.0,
            max_value=5.0,
            key="contract_factor",
        )

        build_btn_col2 = st.columns([1, 3])[0]
        with build_btn_col2:
            if st.button("Build Contract Line", key="btn_build_contract", use_container_width=True):
                df_contract, slope_contract = build_contract_projection_from_anchors(
                    anchor_a_time=anchor_a_time,
                    anchor_a_price=anchor_a_price,
                    anchor_b_time=anchor_b_time,
                    anchor_b_price=anchor_b_price,
                )
                st.session_state["contract_df"] = df_contract
                st.session_state["contract_slope"] = slope_contract
                st.success("Contract projection generated on the RTH grid.")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        section_header("📊 Contract Projection • RTH 08:30–14:30 CT")
        if df_contract is None:
            st.info("Build a contract line to see the projection.")
        else:
            cols = st.columns([3, 1])
            with cols[0]:
                st.dataframe(df_contract, use_container_width=True, hide_index=True, height=340)
            with cols[1]:
                st.markdown(metric_card("Contract Slope", f"{slope_contract:+.4f} / 30m"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "Download contract CSV",
                    df_contract.to_csv(index=False).encode(),
                    "contract_projection.csv",
                    "text/csv",
                    key="dl_contract_csv",
                    use_container_width=True,
                )

        end_card()

    # TAB 3: FORESIGHT
    with tabs[2]:
        card(
            "Daily Foresight",
            "Blend rails and contract line into a simple action map: direction, structure, "
            "and time-aligned expectations.",
            badge="Playbook",
            icon="🔮",
        )

        df_mode, df_ch, h_ch = get_active_channel()
        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")
        factor = st.session_state.get("contract_factor", CONTRACT_FACTOR_DEFAULT)

        if df_ch is None or h_ch is None:
            st.warning("Build rails on the Rails Setup tab first.")
            end_card()
        elif df_contract is None or slope_contract is None:
            st.warning("Build a contract line on the Contract Setup tab first.")
            end_card()
        else:
            merged = df_ch.merge(df_contract, on="Time", how="left")

            # Full-channel stats
            blocks_full = h_ch / SLOPE_MAG if SLOPE_MAG != 0 else 0.0
            contract_full_factor = estimate_contract_full_swing_from_factor(h_ch, factor)
            contract_full_linear = float(round(abs(slope_contract * blocks_full), 2))

            section_header("📊 Structure Snapshot")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(metric_card("Active Channel", df_mode or "Not set"), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Channel Height", f"{h_ch:.2f} pts"), unsafe_allow_html=True)
            with c3:
                st.markdown(
                    metric_card(
                        "Full-Swing Contract",
                        f"~{contract_full_factor:.1f} (factor) / {contract_full_linear:.1f} (line)",
                    ),
                    unsafe_allow_html=True,
                )

            section_header("🎯 Trade Idea Size")
            st.markdown(
                f"""
                <div class='spx-sub'>
                <p><strong>Inside-channel swing:</strong> a full move from one rail to the other is about 
                <strong>{h_ch:.1f} SPX points</strong>.</p>
                <ul>
                    <li>Factor model: aim for ≈ <strong>{contract_full_factor:.1f}</strong> contract move for a clean rail-to-rail swing.</li>
                    <li>Linear model: your anchor-based slope implies ≈ <strong>{contract_full_linear:.1f}</strong> contract move.</li>
                </ul>
                <p>Use the lower of the two for conservative targets when you want high win-rate days.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("🧮 Contract Estimator (Time-Based)")
            times = merged["Time"].tolist()
            if times:
                col_e, col_x = st.columns(2)
                with col_e:
                    entry_time = st.selectbox(
                        "Entry time (rail touch or bounce)",
                        times,
                        index=0,
                        key="fs_entry_time",
                    )
                with col_x:
                    exit_time = st.selectbox(
                        "Exit time",
                        times,
                        index=min(len(times) - 1, 4),
                        key="fs_exit_time",
                    )

                entry_row = merged[merged["Time"] == entry_time].iloc[0]
                exit_row = merged[merged["Time"] == exit_time].iloc[0]

                entry_contract = float(entry_row["Contract Price"])
                exit_contract = float(exit_row["Contract Price"])
                pnl_contract = exit_contract - entry_contract

                c1e, c2e, c3e = st.columns(3)
                with c1e:
                    st.markdown(metric_card("Entry Contract", f"{entry_contract:.2f}"), unsafe_allow_html=True)
                    st.markdown(
                        "<div class='muted'>Use this as the structural contract value if price is tagging your chosen rail at this time.</div>",
                        unsafe_allow_html=True,
                    )
                with c2e:
                    st.markdown(metric_card("Exit Contract", f"{exit_contract:.2f}"), unsafe_allow_html=True)
                with c3e:
                    st.markdown(metric_card("Projected Δ", f"{pnl_contract:+.2f} units"), unsafe_allow_html=True)

                st.markdown(
                    "<div class='muted'><strong>How to read this:</strong> choose the time you expect to enter on a rail touch, "
                    "choose your planned exit time, and compare the projected move to what the contract actually did. "
                    "The gap is your volatility bonus or decay cost for that day.</div>",
                    unsafe_allow_html=True,
                )

            section_header("🗺️ Time-Aligned Map")
            st.caption(
                "Every row is a 30-minute block in RTH. If SPX is on a rail at that time, this is the underlying and contract structure."
            )

            st.dataframe(merged, use_container_width=True, hide_index=True, height=460)

            st.markdown(
                "<div class='muted'><strong>Reading the map:</strong> the table does not tell you when the tag will happen. "
                "It tells you what your structure expects the SPX rails and contract value to be if a tag happens at a given time. "
                "You bring the trigger and discretion; the app gives you the geometry.</div>",
                unsafe_allow_html=True,
            )

        end_card()

    # TAB 4: ABOUT
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Overview", icon="ℹ️")
        st.markdown(
            """
            <div class='spx-sub'>
            <p><strong>SPX Prophet</strong> is built around one idea: institutions care about <em>geometry</em>, not random candles.</p>
            <ul>
                <li>Two pivots from the previous session define parallel rails.</li>
                <li>The session runs on a 30-minute grid with a fixed slope of 0.475 pts / block.</li>
                <li>Your contract line is a simple, honest line between two prices on that same grid.</li>
                <li>The full swing between rails is sized into a contract move through a factor you control.</li>
            </ul>
            <p>The app does not predict news, gamma squeezes, or IV crush. It keeps you anchored to structure so that 
            when price returns to your rails, you already know what “normal” looks like.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet · Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()