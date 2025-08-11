# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                           MARKETLENS PRO (PARTS 1–3)                    ║
# ║              ES-driven SPX Shell • Robust yfinance • CT timezone        ║
# ╚══════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# ────────────────────────────────────────────────────────────────────────────
# **PART 1 — APP SHELL, CONSTANTS, THEME**
# ────────────────────────────────────────────────────────────────────────────

APP_NAME   = "MarketLens Pro"
PAGE_NAME  = "SPX via ES (Foundations)"
COMPANY    = "Quantum Trading Systems"
VERSION    = "4.1.0"

# Timezones
CT = ZoneInfo("America/Chicago")
UTC = ZoneInfo("UTC")

# Symbols
ES_SYMBOL  = "ES=F"    # E-mini S&P 500 futures (continuous front)
SPX_LABEL  = "SPX"     # Just a label; we use ES data beneath

# Sessions (CT)
RTH_START = time(8, 30)   # 08:30 CT
RTH_END   = time(14, 30)  # 14:30 CT (kept per your previous app)
ON_START  = time(17, 0)   # 17:00 CT
ON_END    = time(2, 0)    # 02:00 CT (crosses midnight)

# Slopes per 30-min block (yours)
SPX_SLOPES = {
    "SPX_HIGH":  -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW":   -0.2792,
}

# UI lists
NAV_SECTIONS = ["Overview", "Anchors", "Forecasts"]

# Streamlit Page Config
st.set_page_config(
    page_title=f"{APP_NAME} — {PAGE_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal premium CSS (no volume UI)
CSS = """
<style>
/* Base */
html, body, .stApp { font-family: ui-sans-serif, system-ui, -apple-system; }
.stApp { background: linear-gradient(135deg,#ffffff 0%,#f6f8fb 100%); }

/* Hide default header/footer */
#MainMenu, footer, header[data-testid="stHeader"] { display:none !important; }

/* Hero */
.hero {
  background: linear-gradient(135deg,#0f172a 0%, #1e293b 100%);
  color: white; padding: 28px 24px; border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 12px 30px rgba(0,0,0,0.12);
}
.hero h1 { margin:0; font-size: 28px; font-weight:800; letter-spacing:-0.02em; }
.hero p  { margin:6px 0 0; opacity:0.85; }

/* Card */
.card {
  background: #fff; border:1px solid rgba(0,0,0,0.06); border-radius:16px;
  padding: 18px; box-shadow: 0 6px 18px rgba(0,0,0,0.06);
}

/* Section Title */
.h2 {
  font-size: 20px; font-weight: 800; margin: 8px 0 12px; color: #0f172a;
  padding-bottom:8px; border-bottom: 2px solid #3b82f6;
}
.kpi { display:flex; gap:18px; flex-wrap:wrap; }
.kpi .v { font-weight:800; font-size:20px; }
.kpi .l { font-size:12px; color:#6b7280; margin-top:-2px; }

/* Dataframe chrome */
.stDataFrame { border-radius: 14px; overflow:hidden; box-shadow: 0 8px 22px rgba(0,0,0,0.06); }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Hero
st.markdown(
    f"""
    <div class="hero">
      <h1>{APP_NAME} — {SPX_LABEL} (via ES)</h1>
      <p>Foundational shell with robust ES data, CT sessions, and SPX slope projections • v{VERSION}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar — global controls
with st.sidebar:
    st.markdown("### Instrument")
    st.markdown(f"**{SPX_LABEL}** *(data: {ES_SYMBOL})*")

    st.markdown("### Navigation")
    section = st.radio("", NAV_SECTIONS, index=0)

    st.markdown("---")
    st.markdown("### Session")
    forecast_date = st.date_input("Target Session (CT)", value=date.today())
    tolerance = st.slider("Touch Tolerance ($)", 0.01, 0.60, 0.05, 0.01)

# Utility: make 30m slots between times (inclusive)
def make_slots(start: time, end: time) -> list[str]:
    cur = datetime(2025, 1, 1, start.hour, start.minute)
    stop = datetime(2025, 1, 1, end.hour, end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=30)
    return out

SLOTS_RTH = make_slots(RTH_START, RTH_END)

# ────────────────────────────────────────────────────────────────────────────
# **PART 2 — ROBUST DATA FETCH & RESAMPLING (yfinance)**
# ────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_1m(symbol: str, start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """
    Robust 1-minute fetch. Always returns columns: Dt,Open,High,Low,Close (tz-aware CT) or empty frame.
    Handles MultiIndex columns and odd shapes from yfinance safely.
    """
    start_utc = start_dt_ct.astimezone(UTC)
    end_utc   = end_dt_ct.astimezone(UTC)

    df = yf.download(
        symbol,
        start=start_utc,
        end=end_utc,
        interval="1m",
        auto_adjust=False,
        progress=False,
        prepost=True,
        group_by="column",
        threads=True,
    )
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

    # Flatten MultiIndex if present
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(symbol, axis=1, level=0)
        except Exception:
            df.columns = [t[-1] for t in df.columns.to_flat_index()]

    # Standardize OHLC names
    rename_map = {c: c.title() for c in df.columns}
    df = df.rename(columns=rename_map)

    # Ensure DatetimeIndex -> column
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce", utc=True)

    df = df.reset_index()
    # Normalise datetime column name
    if "Datetime" not in df.columns:
        if "Date" in df.columns:
            df = df.rename(columns={"Date": "Datetime"})
        else:
            df = df.rename(columns={df.columns[0]: "Datetime"})

    needed = ["Datetime","Open","High","Low","Close"]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

    # Convert to CT tz-aware and filter
    dt = pd.to_datetime(df["Datetime"], utc=True, errors="coerce")
    df["Dt"] = dt.dt.tz_convert(CT)
    df = df[["Dt","Open","High","Low","Close"]].dropna().sort_values("Dt")

    # Guard: clip to requested CT window
    mask = (df["Dt"] >= start_dt_ct) & (df["Dt"] <= end_dt_ct)
    df = df.loc[mask].copy()

    if df.empty:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
    return df

def resample_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    1m -> 30m OHLC (right-labeled, right-closed).
    Returns columns: Dt,Open,High,Low,Close, Time(HH:MM)
    """
    if df_1m.empty:
        return df_1m

    g = (
        df_1m.set_index("Dt")[["Open","High","Low","Close"]]
        .resample("30min", label="right", closed="right")
        .agg({"Open":"first","High":"max","Low":"min","Close":"last"})
        .dropna()
        .reset_index()
    )
    g["Time"] = g["Dt"].dt.strftime("%H:%M")
    return g

# ────────────────────────────────────────────────────────────────────────────
# **PART 3 — ANCHORS, PROJECTIONS, UI SECTIONS**
# ────────────────────────────────────────────────────────────────────────────

def ct_range(d: date, t1: time, t2: time) -> tuple[datetime, datetime]:
    """Build CT datetimes for a same-day range."""
    return (
        datetime.combine(d, t1, tzinfo=CT),
        datetime.combine(d, t2, tzinfo=CT),
    )

def ct_range_overnight(d: date, start_t: time, end_t: time) -> tuple[datetime, datetime]:
    """
    Overnight range that crosses midnight if end_t < start_t.
    For (17:00 -> 02:00) CT, this returns [d@17:00, (d+1)@02:00].
    """
    start_dt = datetime.combine(d, start_t, tzinfo=CT)
    end_dt = datetime.combine(d, end_t, tzinfo=CT)
    if end_t <= start_t:
        end_dt = end_dt + timedelta(days=1)
    return (start_dt, end_dt)

@st.cache_data(ttl=300, show_spinner=False)
def es_prevday_hlc(forecast_d: date) -> dict | None:
    """
    Previous RTH (08:30–14:30 CT) High/Low/Close for ES=F and their times.
    """
    prev = forecast_d - timedelta(days=1)
    rth_start, rth_end = ct_range(prev, RTH_START, RTH_END)
    # widen a bit to ensure edges exist
    m1 = yf_fetch_1m(ES_SYMBOL, rth_start - timedelta(minutes=5), rth_end + timedelta(minutes=5))
    if m1.empty:
        return None
    # keep only within RTH
    m1 = m1[(m1["Dt"].dt.time >= RTH_START) & (m1["Dt"].dt.time <= RTH_END)].copy()
    if m1.empty:
        return None

    # High/Low times
    idx_hi = m1["High"].idxmax()
    idx_lo = m1["Low"].idxmin()
    prev_high = float(m1.loc[idx_hi, "High"])
    prev_low  = float(m1.loc[idx_lo, "Low"])
    prev_close = float(m1.iloc[-1]["Close"])
    t_high = m1.loc[idx_hi, "Dt"].to_pydatetime()
    t_low  = m1.loc[idx_lo, "Dt"].to_pydatetime()
    t_close = m1.iloc[-1]["Dt"].to_pydatetime()
    return {
        "day": prev,
        "prev_high": prev_high, "t_high": t_high,
        "prev_low":  prev_low,  "t_low":  t_low,
        "prev_close": prev_close, "t_close": t_close,
    }

@st.cache_data(ttl=300, show_spinner=False)
def es_overnight_extremes(forecast_d: date) -> dict | None:
    """
    Overnight extremes for the *night before* the forecast day: 17:00–02:00 CT window.
    Example: for Tue forecast, we inspect Mon 17:00 -> Tue 02:00.
    """
    start_dt, end_dt = ct_range_overnight(forecast_d - timedelta(days=1), ON_START, ON_END)
    raw = yf_fetch_1m(ES_SYMBOL, start_dt - timedelta(minutes=5), end_dt + timedelta(minutes=5))
    if raw.empty:
        return None
    raw = raw[(raw["Dt"] >= start_dt) & (raw["Dt"] <= end_dt)].copy()
    if raw.empty:
        return None

    idx_hi = raw["High"].idxmax()
    idx_lo = raw["Low"].idxmin()
    on_high = float(raw.loc[idx_hi, "High"]); t_on_high = raw.loc[idx_hi, "Dt"].to_pydatetime()
    on_low  = float(raw.loc[idx_lo, "Low"]);  t_on_low  = raw.loc[idx_lo, "Dt"].to_pydatetime()

    return {"on_high": on_high, "t_on_high": t_on_high, "on_low": on_low, "t_on_low": t_on_low}

def blocks_between(dt1: datetime, dt2: datetime) -> int:
    """30-min block count between two tz-aware datetimes (order agnostic)."""
    if dt2 < dt1:
        dt1, dt2 = dt2, dt1
    blocks, cur = 0, dt1
    while cur < dt2:
        blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def project_line(base_price: float, base_time: datetime, target_time: datetime, slope_per_block: float) -> float:
    return base_price + slope_per_block * blocks_between(base_time, target_time)

def project_spx_table(forecast_d: date) -> tuple[pd.DataFrame, dict] | tuple[pd.DataFrame, dict]:
    """
    Build a table of projected lines for the forecast RTH day using:
      - Previous day H/L/C as bases, each with your SPX slope (-0.2792 per 30m).
      - Overnight High/Low (17:00–02:00 CT) as additional optional context (display only).
    """
    prev = es_prevday_hlc(forecast_d)
    if not prev:
        return pd.DataFrame(), {}

    # Meta (also include overnight extremes for display)
    overnight = es_overnight_extremes(forecast_d)

    # Create rows for each 30m slot of forecast day
    rows = []
    for hhmm in SLOTS_RTH:
        h, m = map(int, hhmm.split(":"))
        tgt = datetime.combine(forecast_d, time(h, m), tzinfo=CT)

        ph = project_line(prev["prev_high"], prev["t_high"], tgt, SPX_SLOPES["SPX_HIGH"])
        pc = project_line(prev["prev_close"], prev["t_close"], tgt, SPX_SLOPES["SPX_CLOSE"])
        pl = project_line(prev["prev_low"],  prev["t_low"],  tgt, SPX_SLOPES["SPX_LOW"])

        rows.append({
            "Time": hhmm,
            "PrevHigh_Line": round(ph, 2),
            "PrevClose_Line": round(pc, 2),
            "PrevLow_Line": round(pl, 2),
        })

    table = pd.DataFrame(rows)
    meta  = {
        "prev_day": prev["day"],
        "prev_high": prev["prev_high"], "t_prev_high": prev["t_high"],
        "prev_low":  prev["prev_low"],  "t_prev_low":  prev["t_low"],
        "prev_close": prev["prev_close"], "t_prev_close": prev["t_close"],
        "overnight": overnight or {},
        "slope_high":  SPX_SLOPES["SPX_HIGH"],
        "slope_close": SPX_SLOPES["SPX_CLOSE"],
        "slope_low":   SPX_SLOPES["SPX_LOW"],
    }
    return table, meta

# ---------------- UI Sections ----------------

def render_overview():
    st.markdown('<div class="h2">Overview</div>', unsafe_allow_html=True)
    colA, colB, colC = st.columns(3)
    with colA:
        st.markdown('<div class="card"><div class="kpi"><div class="v">ES=F</div><div class="l">Data Source</div></div></div>', unsafe_allow_html=True)
    with colB:
        st.markdown(f'<div class="card"><div class="kpi"><div class="v">{forecast_date}</div><div class="l">Forecast Session (CT)</div></div></div>', unsafe_allow_html=True)
    with colC:
        st.markdown(f'<div class="card"><div class="kpi"><div class="v">±${tolerance:.2f}</div><div class="l">Touch Tolerance</div></div></div>', unsafe_allow_html=True)

def render_anchors():
    st.markdown('<div class="h2">⚓ Previous RTH Anchors & Overnight</div>', unsafe_allow_html=True)
    prev = es_prevday_hlc(forecast_date)
    on   = es_overnight_extremes(forecast_date)
    if not prev:
        st.info("Previous-day RTH anchors unavailable for this date.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="card"><div class="kpi"><div class="v">${prev["prev_high"]:.2f}</div><div class="l">Prev RTH High @ {prev["t_high"].strftime("%H:%M")}</div></div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="card"><div class="kpi"><div class="v">${prev["prev_close"]:.2f}</div><div class="l">Prev RTH Close @ {prev["t_close"].strftime("%H:%M")}</div></div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="card"><div class="kpi"><div class="v">${prev["prev_low"]:.2f}</div><div class="l">Prev RTH Low @ {prev["t_low"].strftime("%H:%M")}</div></div></div>',
            unsafe_allow_html=True,
        )

    if on:
        oc1, oc2 = st.columns(2)
        with oc1:
            st.markdown(
                f'<div class="card"><div class="kpi"><div class="v">${on["on_high"]:.2f}</div><div class="l">Overnight High (17:00→02:00) @ {on["t_on_high"].strftime("%m-%d %H:%M")}</div></div></div>',
                unsafe_allow_html=True,
            )
        with oc2:
            st.markdown(
                f'<div class="card"><div class="kpi"><div class="v">${on["on_low"]:.2f}</div><div class="l">Overnight Low (17:00→02:00) @ {on["t_on_low"].strftime("%m-%d %H:%M")}</div></div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No overnight extremes found for 17:00→02:00 CT window.")

def render_forecasts():
    st.markdown('<div class="h2">📋 Forecast Projections (SPX via ES)</div>', unsafe_allow_html=True)
    table, meta = project_spx_table(forecast_date)
    if table.empty:
        st.info("No projections available yet. Try another session date.")
        return
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "PrevHigh_Line":  st.column_config.NumberColumn("Prev High Line ($)",  format='$%.2f'),
            "PrevClose_Line": st.column_config.NumberColumn("Prev Close Line ($)", format='$%.2f'),
            "PrevLow_Line":   st.column_config.NumberColumn("Prev Low Line ($)",   format='$%.2f'),
        },
    )

    # Meta footer
    prev_day = meta.get("prev_day")
    st.markdown(
        f"""
        <div class="card">
          <div class="kpi">
            <div>
              <div class="v">{prev_day.strftime("%a %Y-%m-%d") if prev_day else "—"}</div>
              <div class="l">Previous RTH Anchors Day</div>
            </div>
            <div>
              <div class="v">{meta["slope_high"]:+.4f}</div>
              <div class="l">Slope (Prev High)</div>
            </div>
            <div>
              <div class="v">{meta["slope_close"]:+.4f}</div>
              <div class="l">Slope (Prev Close)</div>
            </div>
            <div>
              <div class="v">{meta["slope_low"]:+.4f}</div>
              <div class="l">Slope (Prev Low)</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Route
if section == "Overview":
    render_overview()
elif section == "Anchors":
    render_anchors()
elif section == "Forecasts":
    render_forecasts()