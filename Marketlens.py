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

# ===========================
# PART 4 — SPX Anchors & Slope Engine
#  - Pulls ^GSPC 1m from Yahoo
#  - Extracts prior day's 5:00–5:29 PM (CT) candle high/low
#  - Builds ascending/descending lines for forecast RTH (08:30–14:30 CT)
#  - No volume. No extraneous UI.
# ===========================
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# --- Timezones & session window (must match earlier parts) ---
CT = ZoneInfo("America/Chicago")
RTH_START, RTH_END = time(8, 30), time(14, 30)   # Regular Trading Hours

# --- SPX settings ---
SPX_SYMBOL = "^GSPC"
SPX_TICK = 0.01
# Your strategy: use 5pm candle anchors with equal-magnitude, opposite slopes
SPX_SLOPE_UP_PER_30M = +0.3171   # from 5pm HIGH, ascends each 30-min block
SPX_SLOPE_DN_PER_30M = -0.3171   # from 5pm LOW, descends each 30-min block

# ---------- Helpers ----------
def _round_tick(x: float, tick: float = SPX_TICK) -> float:
    return round(round(x / tick) * tick, 2)

def _make_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    cur = datetime(2025, 1, 1, start.hour, start.minute)
    stop = datetime(2025, 1, 1, end.hour, end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

SPX_SLOTS = _make_slots(RTH_START, RTH_END)

def _blocks_between(t1: datetime, t2: datetime) -> int:
    """Count 30m blocks (right-closed) between t1 and t2 within same-day math."""
    if t2 < t1:
        t1, t2 = t2, t1
    blocks, cur = 0, t1
    while cur < t2:
        blocks += 1
        cur += timedelta(minutes=30)
    return blocks

# ---------- Yahoo minute data ----------
@st.cache_data(ttl=300)
def spx_fetch_1m(start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """
    Fetch ^GSPC 1m bars from Yahoo within [start, end] CT.
    Yahoo returns UTC; we convert to CT.
    """
    # yfinance expects naive UTC or timezone-aware UTC; we’ll ask for a wide window via period/interval
    # For precise windowing, use timezone convert after download.
    # We’ll pull 2 days to be safe, then trim.
    period = "5d"
    df = yf.download(
        SPX_SYMBOL,
        interval="1m",
        period=period,
        progress=False,
        auto_adjust=False,
        prepost=True,
        threads=True
    )
    if df is None or df.empty:
        return pd.DataFrame()

    # Normalize columns
    df = df.rename(columns=str.title)
    # Ensure tz-aware UTC then convert to CT
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(CT)

    df = df.reset_index().rename(columns={"Datetime": "dt"})
    # Trim to requested window
    mask = (df["Dt"] >= start_dt_ct) & (df["Dt"] <= end_dt_ct)
    out = df.loc[mask, ["Dt", "Open", "High", "Low", "Close"]].copy()
    return out.sort_values("Dt").reset_index(drop=True)

# ---------- 5:00–5:29 PM candle extraction ----------
def spx_get_5pm_candle(forecast: date) -> dict | None:
    """
    Use the PRIOR CALENDAR DAY 5:00–5:29 PM (CT) 1m window.
    - Anchor High = max high in that 30-min window
    - Anchor Low  = min low  in that 30-min window
    """
    prior_day = forecast - timedelta(days=1)
    start_5pm = datetime.combine(prior_day, time(17, 0), tzinfo=CT)
    end_5pm = datetime.combine(prior_day, time(17, 29), tzinfo=CT)

    # Pull a modest window to ensure we capture the band
    start_pull = start_5pm - timedelta(minutes=5)
    end_pull = end_5pm + timedelta(minutes=5)
    data = spx_fetch_1m(start_pull, end_pull)
    if data.empty:
        return None

    # Keep only 17:00–17:29
    band = data[(data["Dt"] >= start_5pm) & (data["Dt"] <= end_5pm)].copy()
    if band.empty:
        return None

    idx_hi = band["High"].idxmax()
    idx_lo = band["Low"].idxmin()
    hi_px = float(band.loc[idx_hi, "High"])
    hi_t  = band.loc[idx_hi, "Dt"].to_pydatetime()
    lo_px = float(band.loc[idx_lo, "Low"])
    lo_t  = band.loc[idx_lo, "Dt"].to_pydatetime()

    return {
        "prior_day": prior_day,
        "hi_anchor_price": hi_px,
        "hi_anchor_time": hi_t,
        "lo_anchor_price": lo_px,
        "lo_anchor_time": lo_t,
    }

# ---------- Line projection for the forecast session ----------
def _project_from_anchor(base_price: float, base_time: datetime, target_dt: datetime, slope_per_30m: float) -> float:
    blocks = _blocks_between(base_time, target_dt)
    return _round_tick(base_price + slope_per_30m * blocks, SPX_TICK)

def spx_project_day_lines(forecast: date, anchors: dict) -> pd.DataFrame:
    """
    Build ascending line from 5pm HIGH (+0.3171/30m)
    and descending line from 5pm LOW (−0.3171/30m)
    for all 30m RTH slots of the forecast date.
    """
    rows = []
    for slot in SPX_SLOTS:
        h, m = map(int, slot.split(":"))
        tdt = datetime.combine(forecast, time(h, m), tzinfo=CT)

        up_line = _project_from_anchor(
            anchors["hi_anchor_price"], anchors["hi_anchor_time"], tdt, SPX_SLOPE_UP_PER_30M
        )
        dn_line = _project_from_anchor(
            anchors["lo_anchor_price"], anchors["lo_anchor_time"], tdt, SPX_SLOPE_DN_PER_30M
        )
        rows.append({"Time": slot, "AscFrom5pmHigh": up_line, "DescFrom5pmLow": dn_line})

    df = pd.DataFrame(rows)
    return df

# ---------- Minimal UI glue ----------
def render_spx_anchors_and_lines(forecast: date | None = None):
    """Small, clean section: compute anchors + show two tiles + build the line schedule."""
    if forecast is None:
        forecast = date.today() + timedelta(days=1)

    st.markdown("### ⚓ SPX 5:00 Candle Anchors")

    anchors = spx_get_5pm_candle(forecast)
    if not anchors:
        st.info("Could not find the prior day's 5:00–5:29 PM candle for SPX. Try another forecast date.")
        return

    colA, colB = st.columns(2)
    with colA:
        st.markdown(
            f"""
            <div class="anchor-tile">
              <div class="anchor-icon" style="color:#34C759;">⬆️</div>
              <div class="anchor-label">5:00 PM HIGH (CT)</div>
              <div class="anchor-value" style="color:#34C759;">{anchors['hi_anchor_price']:.2f}</div>
              <div class="anchor-meta">
                {anchors['hi_anchor_time'].strftime('%b %d, %Y • %H:%M')}<br>
                Slope: +{SPX_SLOPE_UP_PER_30M:.4f} / 30m
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with colB:
        st.markdown(
            f"""
            <div class="anchor-tile">
              <div class="anchor-icon" style="color:#FF3B30;">⬇️</div>
              <div class="anchor-label">5:00 PM LOW (CT)</div>
              <div class="anchor-value" style="color:#FF3B30;">{anchors['lo_anchor_price']:.2f}</div>
              <div class="anchor-meta">
                {anchors['lo_anchor_time'].strftime('%b %d, %Y • %H:%M')}<br>
                Slope: {SPX_SLOPE_DN_PER_30M:.4f} / 30m
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Build schedule
    lines_df = spx_project_day_lines(forecast, anchors)

    # Store for later parts (detections, exports, etc.)
    st.session_state["spx_anchors"] = anchors
    st.session_state["spx_lines_df"] = lines_df

    st.markdown("### 📋 SPX Daily Line Schedule")
    st.dataframe(
        lines_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "AscFrom5pmHigh": st.column_config.NumberColumn("Asc from 5pm High ($)", format="$%.2f"),
            "DescFrom5pmLow": st.column_config.NumberColumn("Desc from 5pm Low ($)", format="$%.2f"),
        },
    )

# --- Lightweight call (expects forecast_date set in Part 1 sidebar; falls back gracefully) ---
_render_forecast = st.session_state.get("forecast_date", None)
render_spx_anchors_and_lines(_render_forecast)