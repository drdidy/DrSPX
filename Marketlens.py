# =============================== PART 1 — APP CONFIG & DESIGN ===============================
from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import yfinance as yf
import streamlit as st

# ---- App meta
APP_NAME = "MarketLens Pro"
PAGE = "SPX via ES (Pro)"
VERSION = "4.1.0"
COMPANY = "Quantum Trading Systems"

# ---- Timezones
CT = ZoneInfo("America/Chicago")   # Your local (Chicago)
ET = ZoneInfo("America/New_York")  # Eastern

# ---- Trading session (SPX cash hours in CT)
RTH_START_CT = time(8, 30)
RTH_END_CT   = time(15, 0)
SLOT_MINUTES = 30

# ---- Slopes (per 30-minute block)
# Previous-day anchors (High/Close/Low) — all descending lines
SPX_SLOPES_PREV_30M = {
    "HIGH":  -0.2792,
    "CLOSE": -0.2792,
    "LOW":   -0.2792,
}
# Overnight (5:00pm–2:00am CT) anchors
SPX_SLOPE_OVERNIGHT_HIGH_30M = +0.3171   # line drawn upward from overnight high
SPX_SLOPE_OVERNIGHT_LOW_30M  = -0.3171   # line drawn downward from overnight low

# ---- Equities (weekly channels) — per 30m upward drift
CHANNEL_SLOPES_30M = {
    "TSLA": 0.1508, "NVDA": 0.0485, "AAPL": 0.0750, "MSFT": 0.1700,
    "AMZN": 0.0300, "GOOGL": 0.0700, "META": 0.0350, "NFLX": 0.2300,
}
def get_channel_slope(symbol: str) -> float:
    return float(CHANNEL_SLOPES_30M.get(symbol.upper(), 0.0))

# ---- UI colors (Apple-ish)
COLORS = {
    "primary": "#007AFF",
    "secondary": "#5AC8FA",
    "success": "#34C759",
    "warning": "#FF9500",
    "error":   "#FF3B30",
    "neutral": "#8B5CF6",
    "text":    "#0B0F1A",
    "muted":   "#6B7280",
    "surface": "#FFFFFF",
    "border":  "rgba(0,0,0,.08)",
}

# ---- Page config
st.set_page_config(
    page_title=f"{APP_NAME} — {PAGE}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---- Minimal polished CSS
st.markdown(f"""
<style>
html, body, .stApp {{
  font-family: -apple-system, BlinkMacSystemFont, Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
}}
#MainMenu, footer {{ display:none !important; }}
.section {{ background:{COLORS['surface']}; border:1px solid {COLORS['border']}; border-radius:16px; padding:18px 18px; box-shadow:0 6px 14px rgba(0,0,0,.04); }}
.hdr {{
  font-weight:800; font-size:1.25rem; color:{COLORS['text']}; margin-bottom:8px;
  border-bottom:2px solid {COLORS['primary']}; padding-bottom:6px;
}}
.kpi {{ display:flex; gap:14px; flex-wrap:wrap; }}
.kpi .item {{ background:#F7F8FA; border:1px solid {COLORS['border']}; border-radius:12px; padding:10px 12px; min-width:150px; }}
.kpi .v {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "JetBrains Mono", "Courier New", monospace; font-weight:800; }}
.badge {{ display:inline-block; padding:6px 10px; border-radius:999px; font-weight:700; font-size:.875rem }}
.badge.ok {{ background:rgba(52,199,89,.12); color:{COLORS['success']}; border:1px solid rgba(52,199,89,.3) }}
.badge.warn {{ background:rgba(255,149,0,.12); color:{COLORS['warning']}; border:1px solid rgba(255,149,0,.3) }}
.badge.err {{ background:rgba(255,59,48,.12); color:{COLORS['error']}; border:1px solid rgba(255,59,48,.3) }}
.tbl .stDataFrame {{ border-radius:12px; overflow:hidden; }}
</style>
""", unsafe_allow_html=True)

# ---- Small helpers
def make_slots(start: time, end: time, step_min: int = SLOT_MINUTES) -> list[str]:
    cur = datetime(2025, 1, 1, start.hour, start.minute)
    stop = datetime(2025, 1, 1, end.hour, end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

SLOTS_RTH = make_slots(RTH_START_CT, RTH_END_CT, SLOT_MINUTES)

def blocks_between(t1: datetime, t2: datetime) -> int:
    """Number of 30m blocks moving forward from t1 to t2 (right-closed bars)."""
    if t2 < t1:
        t1, t2 = t2, t1
    blocks, cur = 0, t1
    while cur < t2:
        blocks += 1
        cur += timedelta(minutes=SLOT_MINUTES)
    return blocks

def project_line(base_price: float, base_time: datetime, slope_per_30m: float, target_dt: datetime) -> float:
    return base_price + slope_per_30m * blocks_between(base_time, target_dt)
# ============================ END PART 1 — APP CONFIG & DESIGN ============================

# =============================== PART 2 — DATA ENGINE (ES via yfinance) ===================
# ES continuous futures (RTH & overnight) pulled from Yahoo
ES_SYMBOL = "ES=F"

@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_1m(symbol: str, start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """Fetch 1-minute bars in CT; returns columns: Dt(Open/High/Low/Close)."""
    # yfinance wants UTC or naive; we pass UTC window.
    start_utc = start_dt_ct.astimezone(ZoneInfo("UTC"))
    end_utc   = end_dt_ct.astimezone(ZoneInfo("UTC"))

    df = yf.download(
        symbol,
        start=start_utc,
        end=end_utc,
        interval="1m",
        auto_adjust=False,
        progress=False,
        prepost=True,
        threads=True,
    )

    if df is None or df.empty:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

    # yfinance returns UTC index
    df = df.rename(columns=str.title).reset_index().rename(columns={"Datetime": "Dt"})
    # Normalize columns (sometimes Adj Close etc sneaks in—ignore)
    keep = ["Dt","Open","High","Low","Close"]
    df = df[keep]
    # Convert to CT tz-aware
    df["Dt"] = pd.to_datetime(df["Dt"], utc=True).dt.tz_convert(CT)
    # Clean
    df = df.dropna(subset=["Open","High","Low","Close"]).sort_values("Dt")
    return df

def resample_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Right-closed 30m bars in CT."""
    if df_1m.empty:
        return df_1m
    g = (
        df_1m.set_index("Dt")[["Open","High","Low","Close"]]
        .resample("30min", label="right", closed="right")
        .agg({"Open":"first","High":"max","Low":"min","Close":"last"})
        .dropna(subset=["Open","High","Low","Close"])
        .reset_index()
    )
    g["Time"] = g["Dt"].dt.strftime("%H:%M")
    return g

def prev_business_day(d: date) -> date:
    wd = d.weekday()
    if wd == 0:  # Monday -> previous Friday
        return d - timedelta(days=3)
    elif wd == 6:  # Sunday -> previous Friday
        return d - timedelta(days=2)
    else:
        return d - timedelta(days=1)

def rth_window_ct(d: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(d, RTH_START_CT, tzinfo=CT),
        datetime.combine(d, RTH_END_CT, tzinfo=CT),
    )

def overnight_window_ct(forecast_d: date) -> tuple[datetime, datetime]:
    """5:00pm (prev calendar day) → 2:00am (forecast day) in CT."""
    start_dt = datetime.combine(forecast_d - timedelta(days=1), time(17, 0), tzinfo=CT)
    end_dt   = datetime.combine(forecast_d, time(2, 0), tzinfo=CT)
    return start_dt, end_dt

@st.cache_data(ttl=300, show_spinner=False)
def es_prevday_hlc(forecast_d: date) -> dict | None:
    """Get prev-day High/Low and Close (at or near 15:00 CT) from ES RTH."""
    prev_d = prev_business_day(forecast_d)
    rth_start, rth_end = rth_window_ct(prev_d)
    m1 = yf_fetch_1m(ES_SYMBOL, rth_start - timedelta(minutes=5), rth_end + timedelta(minutes=5))
    if m1.empty:
        return None

    # H/L over full RTH
    rth = m1[(m1["Dt"] >= rth_start) & (m1["Dt"] <= rth_end)].copy()
    if rth.empty:
        return None

    # High
    idx_hi = rth["High"].idxmax()
    prev_high = float(rth.loc[idx_hi, "High"])
    prev_high_t = rth.loc[idx_hi, "Dt"].to_pydatetime()

    # Low
    idx_lo = rth["Low"].idxmin()
    prev_low = float(rth.loc[idx_lo, "Low"])
    prev_low_t = rth.loc[idx_lo, "Dt"].to_pydatetime()

    # Close (take the last 1m bar <= 15:00)
    close_row = rth[rth["Dt"] <= rth_end].iloc[-1]
    prev_close = float(close_row["Close"])
    prev_close_t = close_row["Dt"].to_pydatetime()

    return {
        "prev_day": prev_d,
        "high": prev_high, "high_t": prev_high_t,
        "low":  prev_low,  "low_t":  prev_low_t,
        "close": prev_close, "close_t": prev_close_t,
    }

@st.cache_data(ttl=300, show_spinner=False)
def es_overnight_extremes(forecast_d: date) -> dict | None:
    """Overnight High/Low in [17:00 prev day, 02:00 forecast day] CT."""
    ow_start, ow_end = overnight_window_ct(forecast_d)
    m1 = yf_fetch_1m(ES_SYMBOL, ow_start - timedelta(minutes=2), ow_end + timedelta(minutes=2))
    if m1.empty:
        return None

    ow = m1[(m1["Dt"] >= ow_start) & (m1["Dt"] <= ow_end)].copy()
    if ow.empty:
        return None

    idx_hi = ow["High"].idxmax()
    on_high = float(ow.loc[idx_hi, "High"])
    on_high_t = ow.loc[idx_hi, "Dt"].to_pydatetime()

    idx_lo = ow["Low"].idxmin()
    on_low = float(ow.loc[idx_lo, "Low"])
    on_low_t = ow.loc[idx_lo, "Dt"].to_pydatetime()

    return {
        "start": ow_start, "end": ow_end,
        "overnight_high": on_high, "overnight_high_t": on_high_t,
        "overnight_low":  on_low,  "overnight_low_t":  on_low_t,
    }

def project_spx_table(forecast_d: date,
                      slope_up_overnight_high: float = SPX_SLOPE_OVERNIGHT_HIGH_30M,
                      slope_dn_overnight_low: float  = SPX_SLOPE_OVERNIGHT_LOW_30M,
                      slopes_prev: dict = SPX_SLOPES_PREV_30M) -> tuple[pd.DataFrame, dict]:
    """Build RTH projections table for forecast date using ES anchors."""
    prev = es_prevday_hlc(forecast_d)
    onx  = es_overnight_extremes(forecast_d)
    rth_start, rth_end = rth_window_ct(forecast_d)

    meta = {"ok": bool(prev and onx)}
    if not (prev and onx):
        return pd.DataFrame(), meta

    # Prepare slots
    slots = []
    cur = rth_start
    while cur <= rth_end:
        slots.append(cur)
        cur += timedelta(minutes=SLOT_MINUTES)

    rows = []
    for dt_slot in slots:
        rows.append({
            "Time": dt_slot.strftime("%H:%M"),
            # Previous-day anchors (all use same -0.2792 slope)
            "Prev High Line":  round(project_line(prev["high"],  prev["high_t"],  slopes_prev["HIGH"],  dt_slot), 2),
            "Prev Close Line": round(project_line(prev["close"], prev["close_t"], slopes_prev["CLOSE"], dt_slot), 2),
            "Prev Low Line":   round(project_line(prev["low"],   prev["low_t"],   slopes_prev["LOW"],   dt_slot), 2),
            # Overnight anchors
            "ON High Line":    round(project_line(onx["overnight_high"], onx["overnight_high_t"], slope_up_overnight_high, dt_slot), 2),
            "ON Low Line":     round(project_line(onx["overnight_low"],  onx["overnight_low_t"],  slope_dn_overnight_low,  dt_slot), 2),
        })

    df = pd.DataFrame(rows)
    meta.update({
        "prev_high": prev["high"], "prev_high_t": prev["high_t"],
        "prev_low":  prev["low"],  "prev_low_t":  prev["low_t"],
        "prev_close": prev["close"], "prev_close_t": prev["close_t"],
        "on_high": onx["overnight_high"], "on_high_t": onx["overnight_high_t"],
        "on_low":  onx["overnight_low"],  "on_low_t":  onx["overnight_low_t"],
        "forecast": forecast_d,
    })
    return df, meta
# ============================ END PART 2 — DATA ENGINE (ES via yfinance) ===================

# =============================== PART 3 — UI: OVERVIEW + ANCHORS + FORECAST ================
st.markdown(f"""
<div class="section">
  <div class="hdr">📈 {APP_NAME} — {PAGE}</div>
  <div style="color:{COLORS['muted']}">v{VERSION} • {COMPANY}</div>
</div>
""", unsafe_allow_html=True)

# ---- Sidebar controls
with st.sidebar:
    st.markdown(f'<div class="hdr">⚙️ Session</div>', unsafe_allow_html=True)
    forecast_date = st.date_input("Forecast Session (RTH)", value=date.today())
    st.caption("RTH: 8:30–15:00 CT • Overnight anchors: 5:00pm–2:00am CT (previous → forecast)")

    st.markdown(f'<div class="hdr">🎚 Slopes</div>', unsafe_allow_html=True)
    # Show (read-only) to reduce accidental edits; you can toggle if needed.
    c1, c2 = st.columns(2)
    with c1:
        st.number_input("Prev Anchors Slope (per 30m)", value=SPX_SLOPES_PREV_30M["HIGH"], step=0.0001, disabled=True, help="Applied to previous-day High/Close/Low lines (all same).")
    with c2:
        st.number_input("ON High Slope (per 30m)", value=SPX_SLOPE_OVERNIGHT_HIGH_30M, step=0.0001, disabled=True, help="Line drawn UP from overnight high.")
    c3, _ = st.columns(2)
    with c3:
        st.number_input("ON Low Slope (per 30m)", value=SPX_SLOPE_OVERNIGHT_LOW_30M, step=0.0001, disabled=True, help="Line drawn DOWN from overnight low.")

# ---- Anchors compute
table, meta = project_spx_table(forecast_date)

st.markdown(f"""<div class="section"><div class="hdr">⚓ ES Anchors (Driving SPX Entry)</div>""", unsafe_allow_html=True)

if not meta.get("ok"):
    st.markdown(
        f"""<div class="badge err">Data not available</div>
        <div style="margin-top:8px;color:{COLORS['muted']}">
        Couldn’t compute prev-day or overnight anchors. Try a recent trading date (yfinance 1m covers ~7 days).
        </div></div>""",
        unsafe_allow_html=True
    )
    st.stop()

# ---- KPI tiles
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        f"""<div class="kpi">
            <div class="item"><div class="v">${meta['prev_high']:.2f}</div><div>Prev Day High</div></div>
            <div class="item"><div class="v">${meta['prev_low']:.2f}</div><div>Prev Day Low</div></div>
        </div>""", unsafe_allow_html=True
    )
with c2:
    st.markdown(
        f"""<div class="kpi">
            <div class="item"><div class="v">${meta['prev_close']:.2f}</div><div>Prev Close</div></div>
            <div class="item"><div class="v">{meta['prev_close_t'].strftime('%H:%M')}</div><div>Close Time (CT)</div></div>
        </div>""", unsafe_allow_html=True
    )
with c3:
    st.markdown(
        f"""<div class="kpi">
            <div class="item"><div class="v">${meta['on_high']:.2f}</div><div>Overnight High (5pm–2am)</div></div>
            <div class="item"><div class="v">${meta['on_low']:.2f}</div><div>Overnight Low (5pm–2am)</div></div>
        </div>""", unsafe_allow_html=True
    )

# times row
c4, c5, c6 = st.columns(3)
with c4:
    st.markdown(
        f"""<div class="kpi">
            <div class="item"><div class="v">{meta['prev_high_t'].strftime('%a %H:%M')}</div><div>Prev High Time (CT)</div></div>
        </div>""", unsafe_allow_html=True
    )
with c5:
    st.markdown(
        f"""<div class="kpi">
            <div class="item"><div class="v">{meta['prev_low_t'].strftime('%a %H:%M')}</div><div>Prev Low Time (CT)</div></div>
        </div>""", unsafe_allow_html=True
    )
with c6:
    st.markdown(
        f"""<div class="kpi">
            <div class="item"><div class="v">{meta['on_high_t'].strftime('%a %H:%M')}</div><div>ON High Time (CT)</div></div>
        </div>""", unsafe_allow_html=True
    )
st.markdown("</div>", unsafe_allow_html=True)

# ---- Forecast lines table
st.markdown(f"""<div class="section"><div class="hdr">📋 SPX Forecast Lines (Projected on ES)</div>""", unsafe_allow_html=True)

if table.empty:
    st.markdown(f"""<div class="badge warn">No projections</div>
        <div style="margin-top:8px;color:{COLORS['muted']}">Missing inputs.</div></div>""",
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f"""<div style="color:{COLORS['muted']}; margin-bottom:10px;">
             Projected lines for {forecast_date.strftime('%A, %B %d, %Y')} RTH (CT).
            </div>""",
        unsafe_allow_html=True
    )
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Prev High Line":  st.column_config.NumberColumn("Prev High Line ($)",  format="$%.2f"),
            "Prev Close Line": st.column_config.NumberColumn("Prev Close Line ($)", format="$%.2f"),
            "Prev Low Line":   st.column_config.NumberColumn("Prev Low Line ($)",   format="$%.2f"),
            "ON High Line":    st.column_config.NumberColumn("ON High Line ($)",    format="$%.2f"),
            "ON Low Line":     st.column_config.NumberColumn("ON Low Line ($)",     format="$%.2f"),
        },
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ---- Subtle footer
st.caption("Data: Yahoo Finance (ES=F). Times in CT. SPX entries are derived from ES anchors (conversion hidden).")
# ============================ END PART 3 — UI: OVERVIEW + ANCHORS + FORECAST ===============