# ==============================================================
#  PART 1/10 — CORE SHELL + ES DATA + ANCHORS + FORECAST TABLE
#  MarketLens Pro — Clean restart (ES=F via yfinance)
#  Shows: Overview, Anchors, Forecasts (works standalone)
# ==============================================================

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

# ------------------ GLOBAL CONFIG ------------------

APP_NAME = "MarketLens Pro"
VERSION = "5.0.0"
COMPANY = "Quantum Trading Systems"

# Timezones
ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Instruments
ES_SYMBOL = "ES=F"   # S&P 500 E-mini futures (continuous front)

# Slopes per 30-min block (your strategy)
SLOPES = {
    "SPX_PREV_HIGH": -0.2792,
    "SPX_PREV_CLOSE": -0.2792,
    "SPX_PREV_LOW": -0.2792,
    "SPX_ON_HIGH": +0.3171,   # Overnight high line ascends
    "SPX_ON_LOW": -0.3171,    # Overnight low line descends
}

# RTH display window (we project to US equities RTH in CT)
RTH_START_CT = time(8, 30)   # 8:30 CT
RTH_END_CT   = time(14, 30)  # 2:30 CT

# ------------------ CSS (lean, professional) ------------------

CSS = """
<style>
#MainMenu, header[data-testid="stHeader"], footer {display:none!important;}
:root {
  --primary:#0A84FF; --surface:#ffffff; --bg:#F5F7FB; --border:rgba(0,0,0,0.08);
  --muted:#6B7280; --ok:#34C759; --warn:#FF9500; --err:#FF3B30;
}
.stApp {background: linear-gradient(180deg, var(--bg), #ffffff 40%);}
.card {
  background:var(--surface); border:1px solid var(--border);
  border-radius:16px; padding:20px; box-shadow:0 6px 16px rgba(0,0,0,0.06);
}
.h1 {font-weight:800; font-size:1.8rem; letter-spacing:-0.01em;}
.h2 {font-weight:700; font-size:1.2rem; border-bottom:2px solid var(--primary); padding-bottom:6px;}
.kpis {display:flex; gap:16px; flex-wrap:wrap; margin:8px 0;}
.kpi {flex:1; min-width:160px; background:#FBFCFE; border:1px solid var(--border); border-radius:14px; padding:14px;}
.kpi .v {font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-weight:800; font-size:1.2rem;}
.kpi .l {color:var(--muted); font-size:0.8rem;}
.badge {display:inline-block; padding:6px 10px; border-radius:999px; font-weight:600; font-size:0.8rem;}
.badge.ok {background:rgba(52,199,89,0.12); color:var(--ok); border:1px solid rgba(52,199,89,0.3);}
.badge.warn {background:rgba(255,149,0,0.12); color:var(--warn); border:1px solid rgba(255,149,0,0.3);}
.badge.err {background:rgba(255,59,48,0.12); color:var(--err); border:1px solid rgba(255,59,48,0.3);}
.tbl {border-radius:12px; overflow:hidden; border:1px solid var(--border);}
</style>
"""
st.set_page_config(page_title=f"{APP_NAME} — ES/SPX Core", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

# ------------------ UTILITIES ------------------

def _as_et(dt_utc: pd.Timestamp | datetime) -> datetime:
    if isinstance(dt_utc, pd.Timestamp):
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.tz_localize("UTC")
        return dt_utc.tz_convert(ET).to_pydatetime()
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    return dt_utc.astimezone(ET)

def blocks_between_30m(t1: datetime, t2: datetime) -> int:
    """Count 30m steps from t1 → t2 (signed). Uses exact 30m increments."""
    step = timedelta(minutes=30)
    # normalize to 0/30 minute marks
    def snap(dt): 
        m = 30 if dt.minute >= 30 else 0
        return dt.replace(minute=m, second=0, microsecond=0)
    a, b = snap(t1), snap(t2)
    diff = (b - a).total_seconds() / 1800.0
    return int(np.round(diff))

def make_ct_slots(start_ct: time, end_ct: time) -> list[datetime]:
    slots = []
    cur = datetime.now(tz=CT).replace(hour=start_ct.hour, minute=start_ct.minute, second=0, microsecond=0)
    end = cur.replace(hour=end_ct.hour, minute=end_ct.minute)
    # Walk forward on an arbitrary day; we will replace date later
    while cur <= end:
        slots.append(cur)
        cur = cur + timedelta(minutes=30)
    return slots

def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun

# ------------------ YFINANCE FETCH LAYER (ES=F) ------------------

@st.cache_data(ttl=180)
def yf_fetch_1m(symbol: str, start_et: datetime, end_et: datetime) -> pd.DataFrame:
    """
    Robust 1m fetch. Returns columns: Dt(ET tz-aware), Open, High, Low, Close
    """
    try:
        # yfinance expects naive UTC times or tz-aware; easiest: use UTC range
        start_utc = start_et.astimezone(ZoneInfo("UTC"))
        end_utc = end_et.astimezone(ZoneInfo("UTC"))
        df = yf.download(
            symbol, start=start_utc, end=end_utc, interval="1m", auto_adjust=False, progress=False
        )
        if df is None or df.empty:
            return pd.DataFrame()
        # index is UTC tz-aware DatetimeIndex
        df = df.rename(columns=str.title)  # Open, High, Low, Close, Volume
        df = df[["Open","High","Low","Close"]].copy()
        df = df.dropna(subset=["Open","High","Low","Close"])
        df["Dt"] = df.index.tz_convert(ET)
        df = df.reset_index(drop=True).sort_values("Dt")
        return df[["Dt","Open","High","Low","Close"]]
    except Exception:
        return pd.DataFrame()

def resample_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Right-closed 30m resample in ET."""
    if df_1m.empty: 
        return pd.DataFrame()
    g = (
        df_1m.set_index("Dt")[["Open","High","Low","Close"]]
        .resample("30min", label="right", closed="right")
        .agg({"Open":"first","High":"max","Low":"min","Close":"last"})
        .dropna(subset=["Open","High","Low","Close"])
        .reset_index()
    )
    return g

# ------------------ ANCHOR COMPUTATIONS (ES for SPX lines) ------------------

def prev_trading_day(d: date) -> date:
    # simple back-step to previous weekday
    dt = d - timedelta(days=1)
    while is_weekend(dt):
        dt -= timedelta(days=1)
    return dt

def es_prevday_hlc(forecast_d: date) -> dict | None:
    """
    Previous day ES RTH: 9:30–16:00 ET.
    Returns dict with prices AND their ET timestamps.
    """
    prev_d = prev_trading_day(forecast_d)
    rth_start = datetime.combine(prev_d, time(9,30), tzinfo=ET)
    rth_end   = datetime.combine(prev_d, time(16,0), tzinfo=ET)
    buf_start = rth_start - timedelta(minutes=15)
    buf_end   = rth_end + timedelta(minutes=15)
    d1 = yf_fetch_1m(ES_SYMBOL, buf_start, buf_end)
    if d1.empty:
        return None
    rth = d1[(d1["Dt"]>=rth_start) & (d1["Dt"]<=rth_end)].copy()
    if rth.empty:
        return None
    # H/L and close
    idx_hi = rth["High"].idxmax()
    idx_lo = rth["Low"].idxmin()
    prev_high = float(rth.loc[idx_hi,"High"]); t_high = rth.loc[idx_hi,"Dt"].to_pydatetime()
    prev_low  = float(rth.loc[idx_lo,"Low"]);  t_low  = rth.loc[idx_lo,"Dt"].to_pydatetime()
    prev_close = float(rth.iloc[-1]["Close"]); t_close = rth.iloc[-1]["Dt"].to_pydatetime()
    return {
        "day": prev_d,
        "high": prev_high, "t_high": t_high,
        "low": prev_low,   "t_low":  t_low,
        "close": prev_close,"t_close":t_close,
    }

def es_overnight_hl(forecast_d: date) -> dict | None:
    """
    Overnight ES window: 6:00 PM → 2:00 AM ET spanning prev day → forecast day.
    """
    prev_d = prev_trading_day(forecast_d)
    start_et = datetime.combine(prev_d, time(18,0), tzinfo=ET)  # 6pm ET prev day
    end_et   = datetime.combine(forecast_d, time(2,0), tzinfo=ET)  # 2am ET forecast
    d1 = yf_fetch_1m(ES_SYMBOL, start_et - timedelta(minutes=10), end_et + timedelta(minutes=10))
    if d1.empty:
        return None
    seg = d1[(d1["Dt"]>=start_et) & (d1["Dt"]<=end_et)].copy()
    if seg.empty:
        return None
    idx_hi = seg["High"].idxmax()
    idx_lo = seg["Low"].idxmin()
    on_high = float(seg.loc[idx_hi,"High"]); t_on_high = seg.loc[idx_hi,"Dt"].to_pydatetime()
    on_low  = float(seg.loc[idx_lo,"Low"]);  t_on_low  = seg.loc[idx_lo,"Dt"].to_pydatetime()
    return {
        "start": start_et, "end": end_et,
        "high": on_high, "t_high": t_on_high,
        "low":  on_low,  "t_low":  t_on_low,
    }

# ------------------ LINE PROJECTION (to CT RTH slots) ------------------

def project_line(base_price: float, base_time: datetime, slope_per_block: float, target_time: datetime) -> float:
    blocks = blocks_between_30m(base_time, target_time)
    return base_price + slope_per_block * blocks

def project_spx_table(forecast_d: date) -> tuple[pd.DataFrame, dict]:
    """
    Builds a 30m table for CT RTH showing:
      - Prev-day High/Close/Low projected lines
      - Overnight High/Low projected lines
    Returns (table, meta) or (empty, reason)
    """
    if is_weekend(forecast_d):
        return pd.DataFrame(), {"msg":"Weekend selected; choose a weekday."}

    prev = es_prevday_hlc(forecast_d)
    ono  = es_overnight_hl(forecast_d)
    if not prev or not ono:
        return pd.DataFrame(), {"msg":"Could not compute anchors (ES data missing)."}

    # Build CT slots on the SELECTED forecast date
    slots_ct = []
    cur = datetime.combine(forecast_d, RTH_START_CT, tzinfo=CT)
    end = datetime.combine(forecast_d, RTH_END_CT, tzinfo=CT)
    while cur <= end:
        slots_ct.append(cur)
        cur += timedelta(minutes=30)

    rows = []
    for ct_ts in slots_ct:
        # Convert target to ET for consistent blocks math
        target_et = ct_ts.astimezone(ET)

        p_high = project_line(prev["high"],  prev["t_high"],  SLOPES["SPX_PREV_HIGH"],  target_et)
        p_close= project_line(prev["close"], prev["t_close"], SLOPES["SPX_PREV_CLOSE"], target_et)
        p_low  = project_line(prev["low"],   prev["t_low"],   SLOPES["SPX_PREV_LOW"],   target_et)
        on_hi  = project_line(ono["high"],   ono["t_high"],   SLOPES["SPX_ON_HIGH"],    target_et)
        on_lo  = project_line(ono["low"],    ono["t_low"],    SLOPES["SPX_ON_LOW"],     target_et)

        rows.append({
            "Time (CT)": ct_ts.strftime("%H:%M"),
            "Prev High": round(p_high,2),
            "Prev Close": round(p_close,2),
            "Prev Low": round(p_low,2),
            "ON High": round(on_hi,2),
            "ON Low": round(on_lo,2),
        })

    tbl = pd.DataFrame(rows)
    meta = {
        "prev_day": prev["day"].strftime("%Y-%m-%d"),
        "prev_high": prev["high"], "t_prev_high": prev["t_high"].strftime("%Y-%m-%d %H:%M ET"),
        "prev_low":  prev["low"],  "t_prev_low":  prev["t_low"].strftime("%Y-%m-%d %H:%M ET"),
        "prev_close":prev["close"],"t_prev_close":prev["t_close"].strftime("%Y-%m-%d %H:%M ET"),
        "on_window": f"{ono['start'].strftime('%Y-%m-%d %H:%M')} → {ono['end'].strftime('%Y-%m-%d %H:%M')} ET",
        "on_high": ono["high"], "t_on_high": ono["t_high"].strftime("%Y-%m-%d %H:%M ET"),
        "on_low":  ono["low"],  "t_on_low":  ono["t_low"].strftime("%Y-%m-%d %H:%M ET"),
    }
    return tbl, meta

# ------------------ SIDEBAR ------------------

with st.sidebar:
    st.markdown(f"<div class='h2'>Session</div>", unsafe_allow_html=True)
    default_d = date.today()
    # If market is closed today, you might prefer next weekday—keeping simple here
    forecast_date = st.date_input("Forecast Date", value=default_d, help="Projects lines to CT RTH for this session.")
    st.caption("Overnight window: 6:00 PM → 2:00 AM ET (prior → forecast)")
    st.markdown("---")
    st.markdown(f"<span class='badge ok'>ES data via Yahoo</span>", unsafe_allow_html=True)

# ------------------ OVERVIEW ------------------

st.markdown(f"<div class='card'><div class='h1'>{APP_NAME}</div>"
            f"<div style='color:#6B7280'>Professional SPX (via ES) line projections • v{VERSION} • {COMPANY}</div></div>", 
            unsafe_allow_html=True)

# ------------------ ANCHORS SECTION ------------------

st.markdown("<div class='h2'>⚓ Anchors</div>", unsafe_allow_html=True)
prev_info = es_prevday_hlc(forecast_date)
on_info   = es_overnight_hl(forecast_date)

if not prev_info or not on_info:
    st.warning("Could not compute anchors (no ES data in one of the windows). Try another recent weekday.")
else:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Previous Day (RTH 9:30–16:00 ET)**")
        st.markdown(f"<div class='kpis'>"
                    f"<div class='kpi'><div class='v'>{prev_info['high']:.2f}</div><div class='l'>High</div></div>"
                    f"<div class='kpi'><div class='v'>{prev_info['low']:.2f}</div><div class='l'>Low</div></div>"
                    f"<div class='kpi'><div class='v'>{prev_info['close']:.2f}</div><div class='l'>Close</div></div>"
                    f"</div>", unsafe_allow_html=True)
        st.caption(f"Prev Day: {prev_info['day'].strftime('%Y-%m-%d')}")
        st.caption(f"High @ {prev_info['t_high'].strftime('%Y-%m-%d %H:%M ET')}")
        st.caption(f"Low  @ {prev_info['t_low'].strftime('%Y-%m-%d %H:%M ET')}")
        st.caption(f"Close@ {prev_info['t_close'].strftime('%Y-%m-%d %H:%M ET')}")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Overnight (6:00 PM → 2:00 AM ET)**")
        st.markdown(f"<div class='kpis'>"
                    f"<div class='kpi'><div class='v'>{on_info['high']:.2f}</div><div class='l'>ON High</div></div>"
                    f"<div class='kpi'><div class='v'>{on_info['low']:.2f}</div><div class='l'>ON Low</div></div>"
                    f"</div>", unsafe_allow_html=True)
        st.caption(f"Window: {on_info['t_high'].strftime('%Y-%m-%d %H:%M ET')} ↔ {on_info['t_low'].strftime('%Y-%m-%d %H:%M ET')}")
        st.markdown("</div>", unsafe_allow_html=True)

# ------------------ FORECAST TABLE ------------------

st.markdown("<div class='h2'>📋 Forecast Lines (CT RTH)</div>", unsafe_allow_html=True)
table, meta = project_spx_table(forecast_date)

if table is None or table.empty:
    st.info(meta.get("msg", "No projection available."))
else:
    # KPI ribbon
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("**Reference Summary**")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(f"<div class='kpi'><div class='v'>{meta['prev_high']:.2f}</div><div class='l'>Prev High</div></div>", unsafe_allow_html=True)
    with k2:
        st.markdown(f"<div class='kpi'><div class='v'>{meta['prev_close']:.2f}</div><div class='l'>Prev Close</div></div>", unsafe_allow_html=True)
    with k3:
        st.markdown(f"<div class='kpi'><div class='v'>{meta['prev_low']:.2f}</div><div class='l'>Prev Low</div></div>", unsafe_allow_html=True)
    with k4:
        st.markdown(f"<div class='kpi'><div class='v'>{meta['on_high']:.2f}</div><div class='l'>ON High</div></div>", unsafe_allow_html=True)
    with k5:
        st.markdown(f"<div class='kpi'><div class='v'>{meta['on_low']:.2f}</div><div class='l'>ON Low</div></div>", unsafe_allow_html=True)
    st.caption(f"Prev Day: {meta['prev_day']} • Overnight: {meta['on_window']}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='tbl'>", unsafe_allow_html=True)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time (CT)": st.column_config.TextColumn("Time (CT)", width="small"),
            "Prev High": st.column_config.NumberColumn("Prev High", format="%.2f"),
            "Prev Close": st.column_config.NumberColumn("Prev Close", format="%.2f"),
            "Prev Low": st.column_config.NumberColumn("Prev Low", format="%.2f"),
            "ON High": st.column_config.NumberColumn("Overnight High", format="%.2f"),
            "ON Low": st.column_config.NumberColumn("Overnight Low", format="%.2f"),
        }
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------ FOOTER ------------------

st.markdown(
    f"<div style='opacity:0.8;margin-top:18px;color:#6B7280'>"
    f"{APP_NAME} • v{VERSION} • {COMPANY}</div>",
    unsafe_allow_html=True
)