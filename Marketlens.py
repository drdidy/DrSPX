# ==============================  **PART 1 / 10 — APP SHELL & NAVIGATION (CLEAN)**  ==============================
# What this provides (minimal, professional):
# - Streamlit page config
# - Light, clean design tokens (colors, spacing, fonts)
# - Sidebar navigation + symbol picker with your 8 symbols + SPX
# - Page router stubs (no placeholder paragraphs)
# - A lean Overview stub (Part 2 will populate its content)

import streamlit as st
from dataclasses import dataclass

# ---------- App Meta ----------
APP_NAME = "MarketLens Pro"
APP_VERSION = "4.1.0"
APP_TAGLINE = "Professional SPX & Equities Analytics"

st.set_page_config(
    page_title=f"{APP_NAME} — {APP_TAGLINE}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Design Tokens (lean) ----------
COLORS = {
    "primary": "#0A84FF",
    "success": "#34C759",
    "warning": "#FF9500",
    "danger":  "#FF3B30",
    "text":    "#111827",
    "muted":   "#6B7280",
    "surface": "#FFFFFF",
    "panel":   "#F8FAFC",
    "border":  "rgba(0,0,0,0.08)",
}

BASE_CSS = f"""
<style>
html, body, .stApp {{
  font-family: ui-sans-serif, -apple-system, "SF Pro Text", Inter, Segoe UI, Roboto, sans-serif;
  color: {COLORS["text"]};
}}
.block {{
  background: {COLORS["panel"]};
  border: 1px solid {COLORS["border"]};
  border-radius: 14px;
  padding: 14px 16px;
}}
h1,h2,h3 {{ letter-spacing: -0.01em; }}
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

# ---------- Symbol Set ----------
@dataclass(frozen=True)
class Ticker:
    symbol: str
    name: str

SYMBOLS = [
    Ticker("^GSPC", "S&P 500 (SPX)"),
    Ticker("AAPL",  "Apple"),
    Ticker("MSFT",  "Microsoft"),
    Ticker("NVDA",  "NVIDIA"),
    Ticker("META",  "Meta"),
    Ticker("GOOGL", "Alphabet"),
    Ticker("TSLA",  "Tesla"),
    Ticker("NFLX",  "Netflix"),
    Ticker("AMZN",  "Amazon"),
]

# ---------- Session Defaults ----------
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = SYMBOLS[0].symbol
if "selected_name" not in st.session_state:
    st.session_state.selected_name = SYMBOLS[0].name
if "page" not in st.session_state:
    st.session_state.page = "Overview"

# ---------- Sidebar: Navigation ----------
with st.sidebar:
    st.markdown(f"### {APP_NAME}")
    st.caption(APP_TAGLINE)

    # Symbol picker
    names = [f"{t.name} — {t.symbol}" for t in SYMBOLS]
    default_index = next((i for i,t in enumerate(SYMBOLS) if t.symbol == st.session_state.selected_symbol), 0)
    sel = st.selectbox("Instrument", names, index=default_index)
    sel_idx = names.index(sel)
    st.session_state.selected_symbol = SYMBOLS[sel_idx].symbol
    st.session_state.selected_name = SYMBOLS[sel_idx].name

    st.divider()

    pages = [
        "Overview",
        "Anchors",
        "Forecasts",
        "Signals",
        "Contract",
        "Fibonacci",
        "Export",
        "Settings / About",
    ]
    page = st.radio("Navigation", pages, index=pages.index(st.session_state.page))
    st.session_state.page = page

# ---------- Page Stubs (no placeholder copy) ----------
def render_overview():
    st.markdown("### Overview")
    # Part 2 will inject live snapshot & anchors here.

def render_anchors():
    st.markdown("### Anchors")

def render_forecasts():
    st.markdown("### Forecasts")

def render_signals():
    st.markdown("### Signals")

def render_contract():
    st.markdown("### Contract")

def render_fibonacci():
    st.markdown("### Fibonacci")

def render_export():
    st.markdown("### Export")

def render_settings():
    st.markdown("### Settings / About")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**App:** {APP_NAME}")
        st.write(f"**Version:** {APP_VERSION}")
    with col2:
        st.write("**Design:** Minimal, professional UI")
        st.write("**Data:** yfinance (cached)")

# ---------- Router ----------
ROUTES = {
    "Overview": render_overview,
    "Anchors": render_anchors,
    "Forecasts": render_forecasts,
    "Signals": render_signals,
    "Contract": render_contract,
    "Fibonacci": render_fibonacci,
    "Export": render_export,
    "Settings / About": render_settings,
}

ROUTES[page]()  # render current page

# ==============================  **PART 2 / 10 — LIVE SNAPSHOT & PREVIOUS-DAY ANCHORS (NO VOLUME)**  ==============================
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st

# --- Utility: fetch live snapshot from Yahoo Finance ---
@st.cache_data(ttl=60, show_spinner=False)
def get_live_snapshot(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m")
        if df.empty:
            return None
        last_bar = df.iloc[-1]
        prev_bar = df.iloc[-2] if len(df) > 1 else last_bar

        cur = float(last_bar["Close"])
        prev_close = float(prev_bar["Close"])
        chg = cur - prev_close
        pct = (chg / prev_close) * 100 if prev_close else 0
        hi = float(df["High"].max())
        lo = float(df["Low"].min())

        return {
            "price": cur,
            "change": chg,
            "change_pct": pct,
            "high": hi,
            "low": lo,
            "time": last_bar.name.to_pydatetime(),
        }
    except Exception:
        return None

# --- Utility: fetch previous day's OHLC (anchors) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_prev_day_anchors(symbol: str):
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=5)
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if df.empty:
            return None
        prev_day = df.iloc[-1]
        return {
            "date": prev_day.name.date(),
            "high": float(prev_day["High"]),
            "close": float(prev_day["Close"]),
            "low": float(prev_day["Low"]),
        }
    except Exception:
        return None

# --- Render Overview page content ---
def render_overview():
    st.markdown(f"### {st.session_state.selected_name}")

    # Live snapshot
    snapshot = get_live_snapshot(st.session_state.selected_symbol)
    if snapshot:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Price",
                f"{snapshot['price']:.2f}",
                f"{snapshot['change']:+.2f} ({snapshot['change_pct']:+.2f}%)"
            )
        with col2:
            st.metric("High", f"{snapshot['high']:.2f}")
        with col3:
            st.metric("Low", f"{snapshot['low']:.2f}")
        st.caption(f"Last update: {snapshot['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.error("No live data available.")

    st.divider()

    # Previous-day anchors
    anchors = get_prev_day_anchors(st.session_state.selected_symbol)
    if anchors:
        st.markdown("#### Previous Day Anchors")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High", f"{anchors['high']:.2f}")
        with col2:
            st.metric("Close", f"{anchors['close']:.2f}")
        with col3:
            st.metric("Low", f"{anchors['low']:.2f}")
        st.caption(f"From: {anchors['date']}")
    else:
        st.error("No anchor data available.")

# --- Hook into router ---
if st.session_state.page == "Overview":
    render_overview()

# ========================== PART 3 — DATA LAYER (SPX via Yahoo, 5 PM Anchors) ==========================
# Clean, Yahoo-only data utilities for SPX:
# - 1m fetch (cached)
# - 30m RTH resample
# - 5:00–5:29 PM CT evening candle extraction (high & low)
# - 30-min block math + line projection (±0.3171 per block)
# - No volume, no Alpaca

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# ---- Time & Session ----
CT = ZoneInfo("America/Chicago")
RTH_START, RTH_END = time(8, 30), time(14, 30)        # CT window used across the app
EVENING_ANCHOR_START = time(17, 0)                     # 5:00 PM CT
EVENING_ANCHOR_END   = time(17, 29)                    # 5:29 PM CT

# ---- SPX Parameters ----
SPX_SYMBOL = "^GSPC"                                   # Yahoo’s S&P 500 index
SPX_SLOPE_UP_PER_BLOCK   =  +0.3171                    # from 5pm LOW, 30-min blocks
SPX_SLOPE_DOWN_PER_BLOCK =  -0.3171                    # from 5pm HIGH, 30-min blocks

# -------------------------------------------------------------------------------------
# Core helpers
# -------------------------------------------------------------------------------------
def _ensure_ct_index(df: pd.DataFrame) -> pd.DataFrame:
    """Make index tz-aware in CT; name it 'dt' and sort."""
    if df.empty:
        return df
    idx = df.index
    if idx.tz is None:
        # yfinance intraday is UTC-naive in some environments; treat as UTC then convert
        df.index = pd.to_datetime(idx).tz_localize("UTC").tz_convert(CT)
    else:
        df.index = pd.to_datetime(idx).tz_convert(CT)
    df.index.name = "dt"
    return df.sort_index()

def _time_str(dt_: datetime) -> str:
    return dt_.strftime("%H:%M")

def _in_time_range(dt_: datetime, start_t: time, end_t: time) -> bool:
    t = dt_.timetz()
    return (t >= start_t) and (t <= end_t)

# -------------------------------------------------------------------------------------
# Yahoo fetchers (cached)
# -------------------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_spx_1m(start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """
    Fetch 1m SPX (Yahoo) between CT datetimes. Includes pre/post to capture 5pm window.
    Returns columns: Open, High, Low, Close (no Volume), index 'dt' in CT.
    """
    if start_dt_ct.tzinfo is None:
        start_dt_ct = start_dt_ct.replace(tzinfo=CT)
    if end_dt_ct.tzinfo is None:
        end_dt_ct = end_dt_ct.replace(tzinfo=CT)

    # yfinance wants naive timestamps in local or UTC-aware index; give strings
    df = yf.download(
        SPX_SYMBOL,
        start=start_dt_ct.astimezone(CT).strftime("%Y-%m-%d %H:%M:%S"),
        end=end_dt_ct.astimezone(CT).strftime("%Y-%m-%d %H:%M:%S"),
        interval="1m",
        auto_adjust=False,
        prepost=True,
        progress=False,
        threads=True,
    )

    if df is None or df.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close"])

    df = df[["Open", "High", "Low", "Close"]].copy()
    df = _ensure_ct_index(df)
    return df

@st.cache_data(ttl=300, show_spinner=False)
def to_30m_rth(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Resample 1m to 30m (right-closed) and filter to CT RTH window.
    Returns: dt (index), Open, High, Low, Close, plus 'Time' HH:MM column.
    """
    if df_1m.empty:
        return df_1m

    ohlc = (
        df_1m.resample("30min", label="right", closed="right")
             .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
             .dropna(subset=["Open", "High", "Low", "Close"])
    )

    # Keep only bars whose RIGHT edge falls inside RTH
    ohlc = ohlc[_time_between_series(ohlc.index, RTH_START, RTH_END)]
    ohlc["Time"] = ohlc.index.strftime("%H:%M")
    return ohlc

def _time_between_series(idx: pd.DatetimeIndex, start_t: time, end_t: time) -> pd.Series:
    """Vectorized mask for right-edge time window (CT)."""
    # idx already CT
    times = idx.time
    return pd.Series([(t >= start_t) and (t <= end_t) for t in times], index=idx)

# -------------------------------------------------------------------------------------
# 5 PM candle extraction (CT) for evening anchors
# -------------------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def spx_5pm_candle(forecast: date) -> dict | None:
    """
    Find the most recent 5:00–5:29 PM CT candle BEFORE the forecast session begins.
    By convention, that is 5 PM on the PRIOR calendar day (forecast - 1 day).
    Returns dict: {'base_end_time', 'high', 'low'} where base_end_time ≈ 17:29 CT.
    """
    anchor_day = forecast - timedelta(days=1)
    start_ct = datetime.combine(anchor_day, EVENING_ANCHOR_START, tzinfo=CT)
    end_ct   = datetime.combine(anchor_day, (EVENING_ANCHOR_END.replace(second=59)), tzinfo=CT)

    df_1m = fetch_spx_1m(start_ct - timedelta(minutes=5), end_ct + timedelta(minutes=5))
    if df_1m.empty:
        return None

    window = df_1m[(df_1m.index.time >= EVENING_ANCHOR_START) & (df_1m.index.time <= EVENING_ANCHOR_END)]
    if window.empty:
        return None

    high_px = float(window["High"].max())
    low_px  = float(window["Low"].min())

    # Use the RIGHT edge of the 5:00–5:29 window as the base time (consistent with right-closed bars)
    base_end_time = datetime.combine(anchor_day, time(17, 29), tzinfo=CT)
    return {"base_end_time": base_end_time, "high": high_px, "low": low_px}

# -------------------------------------------------------------------------------------
# Block math & projections
# -------------------------------------------------------------------------------------
def blocks_between_30m(t1: datetime, t2: datetime) -> int:
    """
    Count 30-min right-closed buckets between t1 and t2 (CT). Order-agnostic.
    We simply step in 30-min hops; this matches how your tables advance.
    """
    if t1.tzinfo is None: t1 = t1.replace(tzinfo=CT)
    if t2.tzinfo is None: t2 = t2.replace(tzinfo=CT)
    if t2 < t1:
        t1, t2 = t2, t1

    cur, blocks = t1, 0
    while cur < t2:
        blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def project_from_evening_high(base_high: float, base_dt: datetime, target_dt: datetime) -> float:
    """
    Down-sloping line from 5pm HIGH using −0.3171 per 30-min block.
    """
    b = blocks_between_30m(base_dt, target_dt)
    return round(base_high + SPX_SLOPE_DOWN_PER_BLOCK * b, 2)

def project_from_evening_low(base_low: float, base_dt: datetime, target_dt: datetime) -> float:
    """
    Up-sloping line from 5pm LOW using +0.3171 per 30-min block.
    """
    b = blocks_between_30m(base_dt, target_dt)
    return round(base_low + SPX_SLOPE_UP_PER_BLOCK * b, 2)

# -------------------------------------------------------------------------------------
# Day schedule for SPX (two lines): from 5pm HIGH and from 5pm LOW
# -------------------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def spx_schedule_for_day(forecast: date) -> pd.DataFrame | None:
    """
    Build the daily schedule (RTH 30m slots) with both evening-anchor lines:
    - FromHigh: starts at 5pm HIGH, slope −0.3171 per block
    - FromLow : starts at 5pm LOW , slope +0.3171 per block
    """
    anchors = spx_5pm_candle(forecast)
    if not anchors:
        return None

    # Generate the RTH slot endpoints for the forecast day (right-closed)
    slots = _make_slots(RTH_START, RTH_END)
    rows = []
    for hhmm in slots:
        hh, mm = map(int, hhmm.split(":"))
        tdt = datetime.combine(forecast, time(hh, mm), tzinfo=CT)
        from_high = project_from_evening_high(anchors["high"], anchors["base_end_time"], tdt)
        from_low  = project_from_evening_low(anchors["low"],  anchors["base_end_time"], tdt)
        rows.append({"Time": hhmm, "FromHigh": from_high, "FromLow": from_low})

    df = pd.DataFrame(rows)
    df.attrs.update({
        "evening_high": anchors["high"],
        "evening_low": anchors["low"],
        "evening_base_time": anchors["base_end_time"],
        "slope_up_per_block": SPX_SLOPE_UP_PER_BLOCK,
        "slope_down_per_block": SPX_SLOPE_DOWN_PER_BLOCK,
    })
    return df

def _make_slots(start_t: time, end_t: time, step_min: int = 30) -> list[str]:
    cur = datetime(2025, 1, 1, start_t.hour, start_t.minute)
    stop = datetime(2025, 1, 1, end_t.hour, end_t.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

# ========================== END PART 3 =================================================================

# ============================================
# **PART 4 — SPX FORECASTS & DAILY SCHEDULE**
# ============================================
# Renders the Forecasts page: projects Upper/Lower lines from the PRIOR-day 5:00–5:29 PM anchors
# using your slope(s), and displays a clean daily schedule for the selected forecast date.

# ---- Helpers (use the anchors & slots from Part 3) ----

def _spx_project_line(base_price: float, base_time: datetime, target_dt: datetime, slope_per_block: float) -> float:
    """Project a price from base_time → target_dt using slope_per_block per 30-min block."""
    blocks = spx_blocks_between(base_time, target_dt)
    return round(base_price + (slope_per_block * blocks), 2)

def spx_build_daily_schedule(anchors: dict, forecast: date) -> pd.DataFrame:
    """
    Build the daily schedule (LowerLine, UpperLine) across all 30-min slots for the forecast date.
    Uses your slope setup from Part 3:
      - Upper line is projected from the prior-day 5PM High anchor
      - Lower line is projected from the prior-day 5PM Low  anchor
      - If a distinct lower slope is defined, it is used; otherwise the upper slope is reused.
    """
    if not anchors:
        return pd.DataFrame()

    # Prefer explicit per-line slopes if you defined them in Part 3; otherwise fall back to one slope.
    slope_up   = globals().get("SPX_SLOPE_UP",   globals().get("SPX_SLOPE_PER_BLOCK", 0.3171))
    slope_low  = globals().get("SPX_SLOPE_LOW",  slope_up)   # fallback to same slope if not provided

    rows = []
    for slot in spx_make_slots(SPX_RTH_START, SPX_RTH_END, step_min=30):
        hh, mm = map(int, slot.split(":"))
        target_dt = datetime.combine(forecast, time(hh, mm), tzinfo=CT)

        upper_val = _spx_project_line(
            anchors["hi_anchor_price"], anchors["hi_anchor_time"], target_dt, slope_up
        )
        lower_val = _spx_project_line(
            anchors["lo_anchor_price"], anchors["lo_anchor_time"], target_dt, slope_low
        )

        rows.append({"Time": slot, "LowerLine": lower_val, "UpperLine": upper_val})

    df = pd.DataFrame(rows)
    return df[["Time", "LowerLine", "UpperLine"]]

# ---- Page Renderer ----

def render_spx_forecasts():
    st.markdown('<div class="section-header">📋 SPX Daily Forecast Schedule</div>', unsafe_allow_html=True)

    # 1) Get anchors (from Part 3, fixed to use "dt" everywhere)
    anchors = spx_get_5pm_candle(st.session_state["forecast_date"])
    if not anchors:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">⚠️</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">Could not derive the prior-day 5:00–5:29 PM anchors</div>
                <div style="color:var(--text-tertiary);">Try another date or check your network/data source</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    # 2) Build the schedule
    schedule_df = spx_build_daily_schedule(anchors, st.session_state["forecast_date"])
    if schedule_df.empty:
        st.warning("No schedule generated.")
        return

    # 3) Top metrics
    rng = schedule_df["UpperLine"].max() - schedule_df["LowerLine"].min()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📈 Upper @ Open", f"${float(schedule_df.loc[schedule_df['Time']=='08:30','UpperLine'].iloc[0]):.2f}")
    with col2:
        st.metric("📉 Lower @ Open", f"${float(schedule_df.loc[schedule_df['Time']=='08:30','LowerLine'].iloc[0]):.2f}")
    with col3:
        st.metric("📏 Channel Range", f"${rng:.2f}")

    # 4) Display table
    st.dataframe(
        schedule_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "LowerLine": st.column_config.NumberColumn("Lower Line ($)", format="$%.2f"),
            "UpperLine": st.column_config.NumberColumn("Upper Line ($)", format="$%.2f"),
        },
    )

    # 5) Context card
    hi_t = anchors["hi_anchor_time"].astimezone(CT).strftime("%Y-%m-%d %H:%M")
    lo_t = anchors["lo_anchor_time"].astimezone(CT).strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
        <div class="premium-card" style="margin-top:var(--space-4);">
            <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:var(--space-4);">
                <div>
                    <div style="font-weight:700;color:var(--primary);">Anchor Source (CT)</div>
                    <div style="color:var(--text-secondary);font-size:var(--text-sm);">
                        High: ${anchors['hi_anchor_price']:.2f} @ {hi_t}<br>
                        Low:&nbsp; ${anchors['lo_anchor_price']:.2f} @ {lo_t}
                    </div>
                </div>
                <div>
                    <div style="font-weight:700;color:var(--primary);">Slope(s) per 30-min</div>
                    <div style="color:var(--text-secondary);font-size:var(--text-sm);">
                        Upper: {globals().get("SPX_SLOPE_UP", globals().get("SPX_SLOPE_PER_BLOCK", 0.3171)):+.4f}<br>
                        Lower: {globals().get("SPX_SLOPE_LOW", globals().get("SPX_SLOPE_UP", globals().get("SPX_SLOPE_PER_BLOCK", 0.3171))):+.4f}
                    </div>
                </div>
                <div>
                    <div style="font-weight:700;color:var(--primary);">Session</div>
                    <div style="color:var(--text-secondary);font-size:var(--text-sm);">
                        {st.session_state["forecast_date"].strftime('%A, %B %d, %Y')}<br>
                        {SPX_RTH_START.strftime('%H:%M')}–{SPX_RTH_END.strftime('%H:%M')} CT
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---- Hook into the main nav ----
if st.session_state.get("nav") == "Forecasts":
    render_spx_forecasts()