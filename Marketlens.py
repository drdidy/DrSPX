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

# ======================================================================
# ==========================  PART 4 — UI & NAV  ========================
# ======================================================================

# Equities slope-per-30m (ascending) — provided by you
STOCK_SLOPES = {
    "AAPL": 0.0750, "MSFT": 0.17,  "AMZN": 0.03, "GOOGL": 0.07,
    "META": 0.035,  "NVDA": 0.0485, "TSLA": 0.1508, "NFLX": 0.23,
}
STOCK_NAMES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "AMZN": "Amazon", "GOOGL": "Alphabet (Google)",
    "META": "Meta",  "NVDA": "NVIDIA",    "TSLA": "Tesla",  "NFLX": "Netflix",
}

def _flatten_yf(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance df to ['Dt','Open','High','Low','Close'] in CT."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    # Handle MultiIndex columns (yfinance often returns that)
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = ['_'.join([str(c) for c in col if c]) for col in out.columns]
    # Prefer these common names
    for c in ["Open","High","Low","Close"]:
        if c not in out.columns:
            # find candidate like 'AAPL Open' or 'Open_AAPL' or 'Open'
            candidates = [col for col in out.columns if col.lower().endswith(c.lower()) or col.split("_")[0].lower()==c.lower()]
            if candidates:
                out[c] = out[candidates[0]]
    if "Datetime" in out.columns:
        out.rename(columns={"Datetime": "Dt"}, inplace=True)
    if "Date" in out.columns and "Dt" not in out.columns:
        out.rename(columns={"Date": "Dt"}, inplace=True)
    if "Dt" not in out.columns:
        out = out.reset_index().rename(columns={"index": "Dt"})
    out["Dt"] = pd.to_datetime(out["Dt"], utc=True).dt.tz_convert(CT)
    out = out.dropna(subset=["Open","High","Low","Close"]).sort_values("Dt")
    return out[["Dt","Open","High","Low","Close"]]

@st.cache_data(ttl=300)
def stock_fetch_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Fetch 1m for any stock via yfinance and flatten."""
    import yfinance as yf
    # yfinance safety window
    start = start_dt.astimezone(CT) - timedelta(minutes=5)
    end   = end_dt.astimezone(CT) + timedelta(minutes=5)
    df = yf.download(
        symbol,
        start=start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None),
        end=end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None),
        interval="1m",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return _flatten_yf(df)

def stock_resample_30m_rth(df_1m: pd.DataFrame) -> pd.DataFrame:
    """30m OHLC restricted to RTH (08:30–14:30 CT)."""
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
    g = g[(g["Time"] >= RTH_START.strftime("%H:%M")) & (g["Time"] <= RTH_END.strftime("%H:%M"))].copy()
    return g

def stock_make_slots(start: time, end: time, step_min: int=30) -> list[str]:
    cur = datetime(2025,1,1,start.hour,start.minute)
    stop = datetime(2025,1,1,end.hour,end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

RTH_SLOTS = stock_make_slots(RTH_START, RTH_END)

def stock_blocks_between(t1: datetime, t2: datetime) -> int:
    if t2 < t1: t1, t2 = t2, t1
    blocks, cur = 0, t1
    while cur < t2:
        blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def stock_project_line(base_price: float, base_dt: datetime, target_dt: datetime, slope_per_block: float) -> float:
    return base_price + slope_per_block * stock_blocks_between(base_dt, target_dt)

@st.cache_data(ttl=600)
def stock_mon_tue_extremes(symbol: str, forecast: date):
    """Find Mon/Tue High & Low (RTH), then choose higher-high and lower-low as channel bases."""
    # Monday of this forecast week (if forecast is Wed+, still use same week)
    mon = forecast - timedelta(days=forecast.weekday())
    tue = mon + timedelta(days=1)

    # Pull 1m across Mon and Tue RTH windows
    for d in (mon, tue):
        pass
    start_dt = datetime.combine(mon, time(7,0), tzinfo=CT)
    end_dt   = datetime.combine(tue + timedelta(days=1), time(7,0), tzinfo=CT)
    raw = stock_fetch_1m(symbol, start_dt, end_dt)
    if raw.empty:
        return None

    raw["D"] = raw["Dt"].dt.date
    mon_df = stock_resample_30m_rth(raw[raw["D"]==mon])
    tue_df = stock_resample_30m_rth(raw[raw["D"]==tue])
    if mon_df.empty or tue_df.empty:
        return None

    midx_hi = mon_df["High"].idxmax(); midx_lo = mon_df["Low"].idxmin()
    MonHigh = float(mon_df.loc[midx_hi,"High"]); MonLow = float(mon_df.loc[midx_lo,"Low"])
    MonHigh_t = mon_df.loc[midx_hi,"Dt"].to_pydatetime(); MonLow_t = mon_df.loc[midx_lo,"Dt"].to_pydatetime()

    tidx_hi = tue_df["High"].idxmax(); tidx_lo = tue_df["Low"].idxmin()
    TueHigh = float(tue_df.loc[tidx_hi,"High"]); TueLow = float(tue_df.loc[tidx_lo,"Low"])
    TueHigh_t = tue_df.loc[tidx_hi,"Dt"].to_pydatetime(); TueLow_t = tue_df.loc[tidx_lo,"Dt"].to_pydatetime()

    if TueHigh >= MonHigh:
        upper_price, upper_time = TueHigh, TueHigh_t
    else:
        upper_price, upper_time = MonHigh, MonHigh_t

    if TueLow <= MonLow:
        lower_price, lower_time = TueLow, TueLow_t
    else:
        lower_price, lower_time = MonLow, MonLow_t

    return {
        "mon_date": mon, "tue_date": tue,
        "MonHigh": MonHigh, "MonLow": MonLow,
        "TueHigh": TueHigh, "TueLow": TueLow,
        "upper_base_price": upper_price, "upper_base_time": upper_time,
        "lower_base_price": lower_price, "lower_base_time": lower_time,
    }

def stock_channel_for_day(day: date, anchors: dict, slope: float) -> pd.DataFrame:
    rows = []
    for slot in RTH_SLOTS:
        h,m = map(int, slot.split(":"))
        tdt = datetime.combine(day, time(h,m), tzinfo=CT)
        up = stock_project_line(anchors["upper_base_price"], anchors["upper_base_time"], tdt, slope)
        lo = stock_project_line(anchors["lower_base_price"], anchors["lower_base_time"], tdt, slope)
        rows.append({"Time": slot, "UpperLine": round(up,2), "LowerLine": round(lo,2)})
    return pd.DataFrame(rows)

@st.cache_data(ttl=240)
def stock_open_price(symbol: str, d: date) -> float|None:
    start_dt = datetime.combine(d, time(7,0), tzinfo=CT)
    end_dt   = datetime.combine(d, time(15,0), tzinfo=CT)
    df = stock_fetch_1m(symbol, start_dt, end_dt)
    if df.empty:
        return None
    # first RTH minute at 08:30 CT
    bar = df.set_index("Dt").between_time("08:30","08:30")
    if bar.empty:
        return None
    return float(bar.iloc[0]["Open"])

def stock_weekdays(forecast: date) -> list[date]:
    mon = forecast - timedelta(days=forecast.weekday())
    return [mon + timedelta(days=i) for i in range(5)]

def stock_first_touch_close_above(symbol: str, day: date, anchors: dict, slope: float, tolerance: float):
    df1m = stock_fetch_1m(symbol, datetime.combine(day, time(7,0), tzinfo=CT), datetime.combine(day, time(16,0), tzinfo=CT))
    intr = stock_resample_30m_rth(df1m)
    if intr.empty:
        return {"Day": day, "Time":"—","Line":"—","Close":"—","Line Px":"—","Δ":"—"}
    ch = stock_channel_for_day(day, anchors, slope)
    merged = pd.merge(intr, ch, on="Time", how="inner")
    for _, r in merged.iterrows():
        lo_line, hi_line = r["LowerLine"], r["UpperLine"]
        lo, hi, close = r["Low"], r["High"], r["Close"]
        # Lower touch + close above
        if (lo - tolerance) <= lo_line <= (hi + tolerance) and close >= (lo_line - 1e-9):
            delta = round(float(close - lo_line), 2)
            return {"Day": day, "Time": r["Time"], "Line":"Lower", "Close": round(float(close),2), "Line Px": round(float(lo_line),2), "Δ": delta}
        # Upper touch + close above (break)
        if (lo - tolerance) <= hi_line <= (hi + tolerance) and close >= (hi_line - 1e-9):
            delta = round(float(close - hi_line), 2)
            return {"Day": day, "Time": r["Time"], "Line":"Upper", "Close": round(float(close),2), "Line Px": round(float(hi_line),2), "Δ": delta}
    return {"Day": day, "Time":"—","Line":"—","Close":"—","Line Px":"—","Δ":"—"}

def stock_signals_mon_fri(symbol: str, forecast: date, anchors: dict, slope: float, tolerance: float) -> pd.DataFrame:
    rows = [stock_first_touch_close_above(symbol, d, anchors, slope, tolerance) for d in stock_weekdays(forecast)]
    df = pd.DataFrame(rows)
    df["Day"] = df["Day"].apply(lambda d: d.strftime("%a %Y-%m-%d") if isinstance(d, date) else d)
    return df

def _badge_for_open(open_px: float|None, row0830: dict|None) -> tuple[str,str]:
    if open_px is None or row0830 is None:
        return ("neutral","Open: Neutral • No opening data")
    lo0830 = float(row0830["LowerLine"]); hi0830 = float(row0830["UpperLine"])
    if open_px < lo0830:
        return ("weak", f"Open: Weak • ${open_px:.2f} below channel (${lo0830:.2f})")
    if open_px > hi0830:
        return ("strong", f"Open: Strong • ${open_px:.2f} above channel (${hi0830:.2f})")
    return ("neutral", f"Open: Neutral • ${open_px:.2f} inside ${lo0830:.2f}–${hi0830:.2f}")

def render_equity_tab(symbol: str, forecast_date: date, tolerance: float):
    pretty = STOCK_NAMES.get(symbol, symbol)
    slope = STOCK_SLOPES[symbol]

    st.markdown(f'<div class="section-header">📈 {pretty} Weekly Channel</div>', unsafe_allow_html=True)

    anchors = stock_mon_tue_extremes(symbol, forecast_date)
    if not anchors:
        st.info(f"Could not compute Monday/Tuesday anchors for {symbol}. Try another date.")
        return

    ch = stock_channel_for_day(forecast_date, anchors, slope)
    opx = stock_open_price(symbol, forecast_date)
    row0830 = ch[ch["Time"] == "08:30"].iloc[0].to_dict() if "08:30" in set(ch["Time"]) and not ch.empty else None
    badge, desc = _badge_for_open(opx, row0830)

    # Status + next slot
    def _next_slot() -> str:
        now = datetime.now(tz=CT).strftime("%H:%M")
        for s in RTH_SLOTS:
            if s >= now:
                return s
        return RTH_SLOTS[0]
    nxt = _next_slot()
    nxt_info = None
    if nxt in set(ch["Time"]):
        r = ch[ch["Time"]==nxt].iloc[0]
        nxt_info = f'Next {nxt} → Lower ${r["LowerLine"]:.2f} • Upper ${r["UpperLine"]:.2f}'

    st.markdown(
        f"""
        <div class="premium-card">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;">
            <div><span class="status-badge {badge}">{desc}</span></div>
            <div class="next-slot">{nxt_info if nxt_info else ""}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Daily schedule
    st.markdown("### 📋 Daily Line Schedule")
    st.dataframe(
        ch[["Time","LowerLine","UpperLine"]],
        use_container_width=True, hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "LowerLine": st.column_config.NumberColumn("Lower ($)", format="$%.2f"),
            "UpperLine": st.column_config.NumberColumn("Upper ($)", format="$%.2f"),
        },
    )

    # Signals
    st.markdown('<div class="section-header">🎯 Signals (Mon–Fri)</div>', unsafe_allow_html=True)
    sig = stock_signals_mon_fri(symbol, forecast_date, anchors, slope, tolerance)
    st.dataframe(
        sig,
        use_container_width=True, hide_index=True,
        column_config={
            "Day": st.column_config.TextColumn("Day", width="medium"),
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Line": st.column_config.TextColumn("Line", width="small"),
            "Close": st.column_config.NumberColumn("Close ($)", format="$%.2f"),
            "Line Px": st.column_config.NumberColumn("Line ($)", format="$%.2f"),
            "Δ": st.column_config.NumberColumn("Delta ($)", format="$%.2f"),
        },
    )

# Top-level Equities section (tabs)
def render_equities_section(forecast_date: date, tolerance: float):
    st.markdown('<div class="section-header">🧺 Equities</div>', unsafe_allow_html=True)
    symbols = list(STOCK_SLOPES.keys())
    cols = st.columns(4)
    sel = st.session_state.get("equity_symbol", symbols[0])
    for i, sym in enumerate(symbols):
        label = STOCK_NAMES.get(sym, sym)
        if cols[i % 4].button(label, key=f"btn_{sym}"):
            st.session_state["equity_symbol"] = sym
            sel = sym
    st.markdown("<div style='margin:0.75rem 0;'></div>", unsafe_allow_html=True)
    render_equity_tab(sel, forecast_date, tolerance)


# ======================================================================
# ================  PART 5 — CONTRACT (SPX/ES) + SIGNALS  ===============
# ======================================================================

def render_contract_tab_es(forecast_date: date):
    st.markdown('<div class="section-header">📋 Contract Line (SPX via ES)</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        low1_t = st.time_input("Low #1 Time (CT)", value=time(2,0), step=300, key="c_low1_t")
        low1_p = st.number_input("Low #1 Price ($)", value=10.00, min_value=0.01, step=0.01, key="c_low1_p", format="%.2f")
    with c2:
        low2_t = st.time_input("Low #2 Time (CT)", value=time(3,30), step=300, key="c_low2_t")
        low2_p = st.number_input("Low #2 Price ($)", value=12.00, min_value=0.01, step=0.01, key="c_low2_p", format="%.2f")

    if low2_t <= low1_t:
        st.warning("Low #2 time must be after Low #1.")
        return {}

    t1 = datetime.combine(forecast_date, low1_t, tzinfo=CT)
    t2 = datetime.combine(forecast_date, low2_t, tzinfo=CT)
    blocks = stock_blocks_between(t1, t2)
    valid = blocks > 0
    slope = (low2_p - low1_p) / blocks if valid else 0.0

    st.markdown(
        f"""
        <div class="premium-card">
          <div style="display:flex;gap:1rem;flex-wrap:wrap;">
            <div class="kpi"><div class="v">{(slope if valid else 0.0):+.4f}</div><div class="l">Slope / 30m</div></div>
            <div class="kpi"><div class="v">{blocks if valid else 0}</div><div class="l">Blocks</div></div>
            <div class="kpi"><div class="v">${(low2_p - low1_p):+.2f}</div><div class="l">Change</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not valid:
        return {}

    # Build projection for all RTH slots
    rows = []
    for s in RTH_SLOTS:
        h,m = map(int, s.split(":"))
        t = datetime.combine(forecast_date, time(h,m), tzinfo=CT)
        proj = low1_p + slope * stock_blocks_between(t1, t)
        rows.append({"Time": s, "Projected": round(proj,2)})

    df = pd.DataFrame(rows)
    st.markdown("### 📊 Contract Projections")
    st.dataframe(
        df, use_container_width=True, hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Projected": st.column_config.NumberColumn("Projected ($)", format="$%.2f"),
        },
    )
    return {"table": df, "slope": slope, "t1": t1, "p1": low1_p}

def render_signals_tab_spx(forecast_date: date, tolerance: float, slope_up: float, slope_dn: float):
    st.markdown('<div class="section-header">🎯 SPX Signals (via ES)</div>', unsafe_allow_html=True)
    # Reuse your SPX/ES signals table from Parts 1–3 (assumes you exposed a function)
    # If you named it differently, tell me and I’ll rename this call.
    table, meta = project_spx_table(forecast_date)  # from Parts 1–3
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.info(f"Slope Up: {slope_up:+.4f} • Slope Down: {slope_dn:+.4f} • Tolerance ±${tolerance:.2f}")


# ======================================================================
# ================  PART 6 — FIBONACCI + EXPORT CENTER  =================
# ======================================================================

def fib_levels(low: float, high: float) -> dict:
    if high <= low: return {}
    r = high - low
    return {
        "0.236": high - 0.236*r,
        "0.382": high - 0.382*r,
        "0.500": high - 0.500*r,
        "0.618": high - 0.618*r,
        "0.786": high - 0.786*r,
        "1.000": low,
        "1.272": high + 0.272*r,
        "1.618": high + 0.618*r,
    }

def render_fibonacci_tab():
    st.markdown('<div class="section-header">🌀 Fibonacci (Bounce)</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        lo = st.number_input("Bounce Low ($)", value=0.00, min_value=0.0, step=0.01, format="%.2f")
    with c2:
        hi = st.number_input("Bounce High ($)", value=0.00, min_value=0.0, step=0.01, format="%.2f")
    with c3:
        show_ext = st.toggle("Show Extensions (1.272/1.618)", value=True)
    if hi <= lo or lo == 0:
        st.info("Enter a valid Low < High to compute Fibonacci levels.")
        return
    lv = fib_levels(lo, hi)
    rows = []
    for k in ["0.236","0.382","0.500","0.618","0.786","1.000"]:
        rows.append({"Level": k, "Price": f"${lv[k]:.2f}", "Note": "ALGO ENTRY" if k=="0.786" else ""})
    if show_ext:
        for k in ["1.272","1.618"]:
            rows.append({"Level": k, "Price": f"${lv[k]:.2f}", "Note": "Target"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def render_export_center_spx(forecast_date: date, tolerance: float):
    st.markdown('<div class="section-header">📤 Export Center</div>', unsafe_allow_html=True)
    # Minimal, professional: export SPX projections and signals from your Part 1–3 functions
    col1, col2 = st.columns(2)
    with col1:
        # Projections
        proj_tbl, _meta = project_spx_table(forecast_date)  # from Parts 1–3
        csv1 = proj_tbl.to_csv(index=False).encode()
        st.download_button("📥 SPX Projections (CSV)", data=csv1, file_name=f"SPX_Projections_{forecast_date}.csv", use_container_width=True)
    with col2:
        # Example: weekly signals already shown in render_signals_tab_spx; export same
        proj_tbl2, _meta2 = project_spx_table(forecast_date)
        csv2 = proj_tbl2.to_csv(index=False).encode()
        st.download_button("📥 SPX Signals (CSV)", data=csv2, file_name=f"SPX_Signals_{forecast_date}.csv", use_container_width=True)

def render_export_center_equity(symbol: str, forecast_date: date):
    anchors = stock_mon_tue_extremes(symbol, forecast_date)
    if not anchors:
        st.info("No anchors to export for this symbol/date.")
        return
    slope = STOCK_SLOPES[symbol]
    ch = stock_channel_for_day(forecast_date, anchors, slope)
    sig = stock_signals_mon_fri(symbol, forecast_date, anchors, slope, tolerance=0.05)

    st.markdown(f'<div class="section-header">📤 Export — {symbol}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📥 Channel Schedule (CSV)",
            data=ch.to_csv(index=False).encode(),
            file_name=f"{symbol}_Channel_{forecast_date}.csv",
            use_container_width=True
        )
    with c2:
        st.download_button(
            "📥 Signals (CSV)",
            data=sig.to_csv(index=False).encode(),
            file_name=f"{symbol}_Signals_{forecast_date}.csv",
            use_container_width=True
        )


# =======================  HOOK INTO MAIN NAV  ==========================
# Call these in your main view where appropriate (e.g., under tabs):
# - render_equities_section(forecast_date, tolerance)
# - render_signals_tab_spx(forecast_date, tolerance, slope_up, slope_dn)
# - render_contract_tab_es(forecast_date)
# - render_fibonacci_tab()
# - render_export_center_spx(forecast_date, tolerance)
# - render_export_center_equity(selected_symbol, forecast_date)

