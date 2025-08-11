# =============================== PART 1 — APP SHELL / STYLES / CONSTANTS (ES) ===============================
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

APP_NAME = "MarketLens Pro"
COMPANY = "Quantum Trading Systems"
VERSION = "4.1.0"

# === Core instrument (ES futures via Yahoo) ===
ES_YF_SYMBOL = "ES=F"

# === Timezones & trading window (CT / RTH) ===
CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")
RTH_START, RTH_END = time(8, 30), time(14, 30)  # 08:30–14:30 CT

# === 30-min slope per block (same slope for upper/lower; simple, stable) ===
# If you later want the lower line to descend, we can split this into UP/DOWN.
SLOPE_PER_BLOCK = 0.3171  # points per 30-min block

# === Minimal, professional CSS (no banners, no volume, no fetch-time) ===
BASE_CSS = """
<style>
:root{
  --primary:#007AFF; --secondary:#5AC8FA; --success:#34C759; --warning:#FF9500; --error:#FF3B30;
  --bg:#FFFFFF; --panel:#FFFFFF; --muted:#F2F2F7; --border:rgba(0,0,0,.08);
  --text:#111; --sub:#3C3C43; --ter:#8E8E93;
  --r-sm:.375rem; --r-md:.5rem; --r-lg:.75rem; --r-xl:1rem;
  --s1:.25rem; --s2:.5rem; --s3:.75rem; --s4:1rem; --s6:1.5rem; --s8:2rem;
}
#MainMenu, footer, header[data-testid="stHeader"]{display:none!important;}
html, body, .stApp{background:linear-gradient(135deg,#fff 0%,#f7f7fb 100%);}
.card{
  background:var(--panel); border:1px solid var(--border); border-radius:var(--r-xl);
  padding:var(--s6); box-shadow:0 8px 20px rgba(0,0,0,.06);
}
.h1{font-weight:800; font-size:1.6rem; letter-spacing:-.02em;}
.h2{font-weight:700; font-size:1.2rem; border-bottom:2px solid var(--primary); padding-bottom:.4rem; margin-bottom:.75rem;}
.badge{
  display:inline-block; padding:.35rem .7rem; border-radius:999px; font-weight:600; font-size:.9rem;
  border:1px solid var(--border); background:#fafafa;
}
.grid3{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:var(--s6);}
.grid2{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:var(--s6);}
.kpi{
  background:linear-gradient(180deg,#fff, #fafafa); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:var(--s6); text-align:center;
}
.kpi .v{font-family: Menlo, ui-monospace, SFMono-Regular, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-weight:800; font-size:1.4rem;}
.kpi .l{color:var(--ter); font-size:.9rem;}
.table-wrap .stDataFrame{border-radius:var(--r-lg); overflow:hidden; border:1px solid var(--border);}
</style>
"""

st.set_page_config(
    page_title=f"{APP_NAME} — ES Futures",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(BASE_CSS, unsafe_allow_html=True)

# === Sidebar (global controls) ===
with st.sidebar:
    st.markdown('<div class="h2">🗓️ Session</div>', unsafe_allow_html=True)
    forecast_date: date = st.date_input("Target Session", value=date.today() + timedelta(days=1))
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Today", use_container_width=True):
            forecast_date = date.today()
            st.session_state._force_rerun = True
    with col_b:
        if st.button("Next Trading Day", use_container_width=True):
            wd = date.today().weekday()
            advance = 1 if wd < 4 else (7 - wd)  # next weekday
            forecast_date = date.today() + timedelta(days=advance)
            st.session_state._force_rerun = True

    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="h2">🎯 Detection</div>', unsafe_allow_html=True)
    tolerance = st.slider("Touch tolerance (pts)", 0.01, 2.00, 0.25, 0.01)

# Simple hero header
st.markdown(
    f"""
    <div class="card" style="padding:1.25rem;display:flex;justify-content:space-between;align-items:center;">
      <div>
        <div class="h1">{APP_NAME} — ES Futures</div>
        <div style="color:var(--ter);">v{VERSION} • {COMPANY}</div>
      </div>
      <div class="badge">RTH {RTH_START.strftime('%H:%M')}–{RTH_END.strftime('%H:%M')} CT</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Reusable slot generator
def make_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    cur = datetime(2025, 1, 1, start.hour, start.minute)  # dummy date
    stop = datetime(2025, 1, 1, end.hour, end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

SLOTS = make_slots(RTH_START, RTH_END)

def blocks_between(t1: datetime, t2: datetime) -> int:
    """Count 30-min blocks between two datetimes (right-closed bars)."""
    if t2 < t1:
        t1, t2 = t2, t1
    blocks, cur = 0, t1
    while cur < t2:
        blocks += 1
        cur += timedelta(minutes=30)
    return blocks
# =============================== END PART 1 =================================================================

# =============================== PART 2 — ES DATA ENGINE (YAHOO) ===========================================
import yfinance as yf

@st.cache_data(ttl=300)
def es_fetch_1m(start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """
    Pull 1-minute ES=F bars from Yahoo in the CT window provided.
    Returns columns: Dt(CT tz), Open, High, Low, Close
    """
    try:
        # yfinance requires UTC; ensure tz and convert.
        start_utc = start_dt_ct.astimezone(ZoneInfo("UTC"))
        end_utc = end_dt_ct.astimezone(ZoneInfo("UTC"))
        df = yf.download(
            ES_YF_SYMBOL, interval="1m", start=start_utc, end=end_utc, auto_adjust=False, progress=False
        )
        if df is None or df.empty:
            return pd.DataFrame()
        # yfinance index may be tz-aware UTC or naive; make UTC then CT
        idx = df.index
        if idx.tz is None:
            df.index = pd.to_datetime(idx).tz_localize("UTC").tz_convert(CT)
        else:
            df.index = pd.to_datetime(idx).tz_convert(CT)

        out = df[["Open", "High", "Low", "Close"]].copy()
        out.reset_index(inplace=True)
        out.rename(columns={"index": "Dt", "Datetime": "Dt"}, inplace=True)
        out["Dt"] = pd.to_datetime(out["Dt"]).dt.tz_convert(CT)
        return out.sort_values("Dt").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

def es_to_30m_rth(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1m bars to 30m OHLC and filter RTH window (08:30–14:30 CT)."""
    if df_1m.empty:
        return pd.DataFrame()
    df = df_1m.set_index("Dt").sort_index()
    ohlc = (
        df[["Open", "High", "Low", "Close"]]
        .resample("30min", label="right", closed="right")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
        .dropna(subset=["Open", "High", "Low", "Close"])
        .reset_index()
    )
    ohlc["Time"] = ohlc["Dt"].dt.strftime("%H:%M")
    mask = (ohlc["Time"] >= RTH_START.strftime("%H:%M")) & (ohlc["Time"] <= RTH_END.strftime("%H:%M"))
    return ohlc.loc[mask].reset_index(drop=True)

def es_project_line(base_price: float, base_dt: datetime, target_dt: datetime) -> float:
    """Linear projection using the global SLOPE_PER_BLOCK (per 30-min)."""
    return float(base_price + SLOPE_PER_BLOCK * blocks_between(base_dt, target_dt))

@st.cache_data(ttl=600)
def es_get_5pm_candle(forecast: date) -> dict | None:
    """
    Use the 17:00–17:29 CT candle from the PRIOR calendar day as the anchor.
    Returns dict with: base_high/low + base_time
    """
    try:
        # prior day 5:00pm CT
        prior = forecast - timedelta(days=1)
        start_ct = datetime.combine(prior, time(16, 45), tzinfo=CT)
        end_ct = datetime.combine(prior, time(17, 35), tzinfo=CT)
        df = es_fetch_1m(start_ct, end_ct)
        if df.empty:
            return None

        # build minute bucket to group [17:00–17:29]
        df["HHMM"] = df["Dt"].dt.strftime("%H:%M")
        candle = df[(df["HHMM"] >= "17:00") & (df["HHMM"] <= "17:29")].copy()
        if candle.empty:
            return None

        hi_idx = candle["High"].idxmax()
        lo_idx = candle["Low"].idxmin()
        base_high = float(candle.loc[hi_idx, "High"])
        base_low = float(candle.loc[lo_idx, "Low"])
        # choose the minute at which the high/low occurred as base time
        base_time_high: datetime = candle.loc[hi_idx, "Dt"].to_pydatetime()
        base_time_low: datetime = candle.loc[lo_idx, "Dt"].to_pydatetime()

        return {
            "anchor_date": prior,
            "base_high": base_high,
            "base_low": base_low,
            "base_time_high": base_time_high,
            "base_time_low": base_time_low,
        }
    except Exception:
        return None

def es_intraday_30m_for_day(d: date) -> pd.DataFrame:
    """Convenience: fetch 1m for the day and convert to 30m RTH."""
    start_ct = datetime.combine(d, time(6, 0), tzinfo=CT)
    end_ct = datetime.combine(d, time(16, 0), tzinfo=CT)
    df = es_fetch_1m(start_ct, end_ct)
    return es_to_30m_rth(df)

def es_channel_for_day(d: date, anchors: dict) -> pd.DataFrame:
    """Upper/Lower lines for every 30-min slot based on 5pm anchors."""
    rows = []
    for slot in SLOTS:
        hh, mm = map(int, slot.split(":"))
        tdt = datetime.combine(d, time(hh, mm), tzinfo=CT)
        up = es_project_line(anchors["base_high"], anchors["base_time_high"], tdt)
        lo = es_project_line(anchors["base_low"], anchors["base_time_low"], tdt)
        rows.append({"Time": slot, "UpperLine": round(up, 2), "LowerLine": round(lo, 2)})
    return pd.DataFrame(rows)
# =============================== END PART 2 =================================================================

# =============================== PART 3 — ANCHORS / FORECASTS / SIGNALS (ES) ================================

def _card(title: str, body_html: str = ""):
    st.markdown(f"""<div class="card"><div class="h2">{title}</div>{body_html}</div>""", unsafe_allow_html=True)

def render_es_anchors_and_forecast(d: date):
    anchors = es_get_5pm_candle(d)
    if not anchors:
        _card("⚓ ES 5:00pm Anchors", "<div>Unable to retrieve the 17:00–17:29 CT candle from prior day.</div>")
        return None, None

    # Show anchors
    col1, col2 = st.columns(2)
    with col1:
        _card(
            "⚓ ES 5:00pm Anchors",
            f"""
            <div class="grid2">
              <div class="kpi"><div class="v">{anchors['base_high']:.2f}</div><div class="l">5pm High</div></div>
              <div class="kpi"><div class="v">{anchors['base_low']:.2f}</div><div class="l">5pm Low</div></div>
            </div>
            <div style="color:var(--ter);margin-top:.5rem;">
                Prior: {anchors['anchor_date'].strftime('%a %Y-%m-%d')} • slope {SLOPE_PER_BLOCK:+.4f}/30m
            </div>
            """
        )
    # Build forecast lines table
    lines_df = es_channel_for_day(d, anchors)
    with col2:
        rng = lines_df["UpperLine"].max() - lines_df["LowerLine"].min()
        _card(
            "📋 Forecast Lines (30-min)",
            f"""
            <div class="kpi"><div class="v">{rng:.2f}</div><div class="l">Range (Upper−Lower)</div></div>
            """
        )

    st.markdown('<div class="table-wrap">', unsafe_allow_html=True)
    st.dataframe(
        lines_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "LowerLine": st.column_config.NumberColumn("Lower ($)", format="%.2f"),
            "UpperLine": st.column_config.NumberColumn("Upper ($)", format="%.2f"),
        },
    )
    st.markdown('</div>', unsafe_allow_html=True)

    return anchors, lines_df

def first_touch_close_above_es(d: date, anchors: dict, tol: float):
    """
    Touch + Close Above (either line) using ES 30m bars:
    - Touch: Low<=Line<=High within ±tol
    - Close condition: Close>=Line
    Returns dict with Time/Line/Close/LinePx/Δ or dashes.
    """
    intr = es_intraday_30m_for_day(d)
    if intr.empty:
        return {"Day": d, "Time": "—", "Line": "—", "Close": "—", "Line Px": "—", "Δ": "—"}

    ch = es_channel_for_day(d, anchors)
    merged = pd.merge(intr, ch, on="Time", how="inner")

    for _, r in merged.iterrows():
        lo_line = r["LowerLine"]
        hi_line = r["UpperLine"]
        lo, hi, close = r["Low"], r["High"], r["Close"]

        # Lower line: touch + close above
        if (lo - tol) <= lo_line <= (hi + tol) and close >= (lo_line - 1e-9):
            delta = round(float(close - lo_line), 2)
            return {"Day": d, "Time": r["Time"], "Line": "Lower",
                    "Close": round(float(close), 2), "Line Px": round(float(lo_line), 2), "Δ": delta}

        # Upper line: touch + close above
        if (lo - tol) <= hi_line <= (hi + tol) and close >= (hi_line - 1e-9):
            delta = round(float(close - hi_line), 2)
            return {"Day": d, "Time": r["Time"], "Line": "Upper",
                    "Close": round(float(close), 2), "Line Px": round(float(hi_line), 2), "Δ": delta}

    return {"Day": d, "Time": "—", "Line": "—", "Close": "—", "Line Px": "—", "Δ": "—"}

def render_es_signals_week(d: date, anchors: dict, tol: float):
    """Show Mon–Fri first touch+close-above signals for the week of the target session."""
    # Week for ‘d’: align to Monday
    monday = d - timedelta(days=d.weekday())
    days = [monday + timedelta(days=i) for i in range(5)]
    rows = [first_touch_close_above_es(x, anchors, tol) for x in days]
    df = pd.DataFrame(rows)
    df["Day"] = df["Day"].apply(lambda x: x.strftime("%a %Y-%m-%d") if isinstance(x, date) else x)

    _card("🎯 Signals (Mon–Fri)", "")
    st.markdown('<div class="table-wrap">', unsafe_allow_html=True)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Day": st.column_config.TextColumn("Day"),
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Line": st.column_config.TextColumn("Line", width="small"),
            "Close": st.column_config.NumberColumn("Close", format="%.2f"),
            "Line Px": st.column_config.NumberColumn("Line Px", format="%.2f"),
            "Δ": st.column_config.NumberColumn("Δ", format="%.2f"),
        },
    )
    st.markdown('</div>', unsafe_allow_html=True)
    return df

# === Main content areas (Overview/Anchors/Forecasts/Signals) ===
st.markdown('<div class="card"><div class="h2">Navigation</div></div>', unsafe_allow_html=True)
tabs = st.tabs(["Overview", "Anchors", "Forecasts", "Signals"])

with tabs[0]:
    # Simple, non-noisy overview
    colA, colB, colC = st.columns(3)
    with colA:
        st.markdown('<div class="kpi"><div class="v">ES Futures</div><div class="l">Instrument</div></div>', unsafe_allow_html=True)
    with colB:
        st.markdown(f'<div class="kpi"><div class="v">{SLOPE_PER_BLOCK:+.4f}</div><div class="l">Slope / 30m</div></div>', unsafe_allow_html=True)
    with colC:
        st.markdown(f'<div class="kpi"><div class="v">±{tolerance:.2f}</div><div class="l">Tolerance</div></div>', unsafe_allow_html=True)

with tabs[1]:
    anchors, _ = render_es_anchors_and_forecast(forecast_date)

with tabs[2]:
    if "anchors" not in locals() or anchors is None:
        anchors, _ = render_es_anchors_and_forecast(forecast_date)
    else:
        # already computed by Anchors tab; show lines table again
        _, lines_df = render_es_anchors_and_forecast(forecast_date)

with tabs[3]:
    if "anchors" not in locals() or anchors is None:
        anchors, _ = render_es_anchors_and_forecast(forecast_date)
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    render_es_signals_week(forecast_date, anchors, tolerance)
# =============================== END PART 3 =================================================================

# =============================== PART 4 — CONTRACT LINE TOOL (ES) ==========================================
from dataclasses import dataclass

@dataclass
class ContractConfig:
    low1_time: time
    low1_price: float
    low2_time: time
    low2_price: float
    rth_only: bool = True

def _blocks_between_times(base_day: date, t1: time, t2: time) -> int:
    return blocks_between(
        datetime.combine(base_day, t1, tzinfo=CT),
        datetime.combine(base_day, t2, tzinfo=CT),
    )

def compute_contract_slope(cfg: ContractConfig, base_day: date) -> float | None:
    """Slope per 30-min block from two points on same session (price2 - price1) / blocks."""
    b = _blocks_between_times(base_day, cfg.low1_time, cfg.low2_time)
    if b <= 0:
        return None
    return (cfg.low2_price - cfg.low1_price) / b

def project_contract_series(cfg: ContractConfig, base_day: date) -> pd.DataFrame:
    """Generate contract projections across SLOTS using computed slope from two points."""
    slope = compute_contract_slope(cfg, base_day)
    if slope is None:
        return pd.DataFrame()

    rows = []
    base_dt = datetime.combine(base_day, cfg.low1_time, tzinfo=CT)
    for slot in SLOTS:
        hh, mm = map(int, slot.split(":"))
        tdt = datetime.combine(base_day, time(hh, mm), tzinfo=CT)
        blocks = blocks_between(base_dt, tdt)
        px = cfg.low1_price + slope * blocks
        rows.append({"Time": slot, "Projected": round(px, 2), "Blocks": blocks})

    df = pd.DataFrame(rows)
    return df

def render_contract_tab_es(target_day: date):
    st.markdown('<div class="card"><div class="h2">📋 Contract Line</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        t1 = st.time_input("Low #1 Time", value=time(9, 0), step=300, key="ct_low1")
        p1 = st.number_input("Low #1 Price", min_value=0.0, value=100.00, step=0.25, key="cp_low1")
        t2 = st.time_input("Low #2 Time", value=time(10, 0), step=300, key="ct_low2")
        p2 = st.number_input("Low #2 Price", min_value=0.0, value=102.00, step=0.25, key="cp_low2")
        rth_only = True  # fixed for simplicity; ES projections already respect RTH by SLOTS

    with col2:
        cfg = ContractConfig(t1, p1, t2, p2, rth_only=rth_only)
        slope = compute_contract_slope(cfg, target_day)
        valid = slope is not None
        rng_html = ""
        if valid:
            proj = project_contract_series(cfg, target_day)
            if not proj.empty:
                rng_html = f'<div class="kpi"><div class="v">{proj["Projected"].min():.2f} → {proj["Projected"].max():.2f}</div><div class="l">Projected Range</div></div>'

        st.markdown(
            f"""
            <div class="grid2" style="margin-top:.5rem;">
              <div class="kpi"><div class="v">{slope:+.4f if valid else "—"}</div><div class="l">Slope / 30m</div></div>
              {rng_html if rng_html else '<div class="kpi"><div class="v">—</div><div class="l">Projected Range</div></div>'}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    if not valid:
        st.markdown(
            '<div class="card"><div style="color:var(--warning);">Provide two valid points with different times to compute a slope.</div></div>',
            unsafe_allow_html=True,
        )
        return None

    df = project_contract_series(cfg, target_day)
    if df.empty:
        st.markdown(
            '<div class="card"><div style="color:var(--error);">No projections generated.</div></div>',
            unsafe_allow_html=True,
        )
        return None

    st.markdown('<div class="card"><div class="h2">📊 Projections (30-min)</div>', unsafe_allow_html=True)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Projected": st.column_config.NumberColumn("Projected", format="%.2f"),
            "Blocks": st.column_config.NumberColumn("Blocks"),
        },
    )
    return {"config": cfg, "data": df, "slope": slope}

# Secondary tab group for tools
st.markdown('<div class="card"><div class="h2">Tools</div></div>', unsafe_allow_html=True)
tabs_tools = st.tabs(["Contract", "Fibonacci", "Export"])

with tabs_tools[0]:
    contract_state = render_contract_tab_es(forecast_date)
# =============================== END PART 4 =================================================================

# =============================== PART 5 — FIBONACCI TOOL (ES) ==============================================
def fib_levels(low: float, high: float) -> dict:
    if high <= low:
        return {}
    r = high - low
    return {
        "0.236": high - 0.236 * r,
        "0.382": high - 0.382 * r,
        "0.500": high - 0.500 * r,
        "0.618": high - 0.618 * r,
        "0.786": high - 0.786 * r,
        "1.000": low,
        "1.272": high + 0.272 * r,
        "1.618": high + 0.618 * r,
    }

def render_fibonacci_tab():
    st.markdown('<div class="card"><div class="h2">🌀 Fibonacci</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        lo = st.number_input("Bounce Low", min_value=0.0, value=100.00, step=0.25, key="fib_lo")
        hi = st.number_input("Bounce High", min_value=0.0, value=105.00, step=0.25, key="fib_hi")
    with c2:
        show_ext = st.toggle("Show Extensions (1.272 / 1.618)", value=True, key="fib_ext")

    st.markdown("</div>", unsafe_allow_html=True)

    if hi <= lo:
        st.markdown(
            '<div class="card" style="color:var(--warning);">Enter Low < High to compute levels.</div>',
            unsafe_allow_html=True,
        )
        return None

    lv = fib_levels(lo, hi)
    order = ["0.236", "0.382", "0.500", "0.618", "0.786", "1.000"]
    if show_ext:
        order += ["1.272", "1.618"]
    rows = [{"Level": L, "Price": round(lv[L], 2)} for L in order]

    st.markdown('<div class="card"><div class="h2">📊 Levels</div>', unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Level": st.column_config.TextColumn("Level", width="small"),
            "Price": st.column_config.NumberColumn("Price", format="%.2f"),
        },
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Optional confluence with Contract
    if "contract_state" in globals() and contract_state and contract_state.get("data") is not None:
        dfc = contract_state["data"]
        # compare each level to the nearest contract projection (by absolute difference)
        comp = []
        for L in order:
            price = lv[L]
            idx = (dfc["Projected"] - price).abs().idxmin()
            row = dfc.loc[idx]
            comp.append(
                {
                    "Level": L,
                    "Fib": round(price, 2),
                    "Nearest Time": row["Time"],
                    "Contract Px": round(float(row["Projected"]), 2),
                    "Δ": round(float(row["Projected"] - price), 2),
                }
            )

        st.markdown('<div class="card"><div class="h2">🔎 Confluence (vs Contract)</div>', unsafe_allow_html=True)
        st.dataframe(
            pd.DataFrame(comp),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Level": st.column_config.TextColumn("Level", width="small"),
                "Fib": st.column_config.NumberColumn("Fib", format="%.2f"),
                "Nearest Time": st.column_config.TextColumn("Nearest Time", width="small"),
                "Contract Px": st.column_config.NumberColumn("Contract Px", format="%.2f"),
                "Δ": st.column_config.NumberColumn("Δ", format="%.2f"),
            },
        )
        st.markdown("</div>", unsafe_allow_html=True)

    return {"low": lo, "high": hi, "levels": lv}

with tabs_tools[1]:
    fibonacci_state = render_fibonacci_tab()
# =============================== END PART 5 =================================================================

# =============================== PART 6 — EXPORT CENTER (ES) ===============================================
import io, zipfile

def build_es_lines_and_signals_for_export(target_day: date, tol: float):
    # Ensure anchors/lines/signals are computed
    anchors_local = es_get_5pm_candle(target_day)
    if not anchors_local:
        return None

    lines = es_channel_for_day(target_day, anchors_local)

    # Build weekly signals (Mon–Fri) using same logic as Part 3
    monday = target_day - timedelta(days=target_day.weekday())
    days = [monday + timedelta(days=i) for i in range(5)]
    rows = [first_touch_close_above_es(x, anchors_local, tol) for x in days]
    sig = pd.DataFrame(rows)
    sig["Day"] = sig["Day"].apply(lambda x: x.strftime("%a %Y-%m-%d") if isinstance(x, date) else x)

    # Intraday 30m of the target day
    intraday30 = es_intraday_30m_for_day(target_day)

    return anchors_local, lines, sig, intraday30

def export_zip_es(target_day: date, tol: float, contract_state, fibonacci_state):
    pkt = {}
    anchors_local, lines, sig, intraday30 = build_es_lines_and_signals_for_export(target_day, tol)

    ts = datetime.now(tz=CT).strftime("%Y%m%d_%H%M%S")

    # Lines
    if lines is not None and not lines.empty:
        df = lines.copy()
        df["Forecast_Date"] = target_day
        df["Slope_Per_Block"] = SLOPE_PER_BLOCK
        pkt[f"ES_Lines_{target_day}_{ts}.csv"] = df.to_csv(index=False).encode()

    # Signals
    if sig is not None and not sig.empty:
        df = sig.copy()
        df["Forecast_Date"] = target_day
        df["Tolerance"] = tol
        pkt[f"ES_Signals_{target_day}_{ts}.csv"] = df.to_csv(index=False).encode()

    # Intraday 30m (optional)
    if intraday30 is not None and not intraday30.empty:
        df = intraday30.copy()
        df["Forecast_Date"] = target_day
        pkt[f"ES_Intraday30_{target_day}_{ts}.csv"] = df.to_csv(index=False).encode()

    # Contract (optional)
    if contract_state and contract_state.get("data") is not None:
        dfc = contract_state["data"].copy()
        dfc["Forecast_Date"] = target_day
        dfc["Slope_Computed"] = contract_state.get("slope", 0.0)
        pkt[f"Contract_{target_day}_{ts}.csv"] = dfc.to_csv(index=False).encode()

    # Fibonacci (optional)
    if fibonacci_state and fibonacci_state.get("levels"):
        lv = fibonacci_state["levels"]
        rows = [{"Level": k, "Price": round(v, 2)} for k, v in lv.items()]
        dff = pd.DataFrame(rows)
        dff["Forecast_Date"] = target_day
        pkt[f"Fibonacci_{target_day}_{ts}.csv"] = dff.to_csv(index=False).encode()

    # Summary
    if anchors_local:
        summary = {
            "Export_Timestamp": [datetime.now(tz=CT)],
            "Forecast_Date": [target_day],
            "Anchor_Date(5pm)": [anchors_local.get("anchor_date")],
            "5pm_High": [anchors_local.get("base_high")],
            "5pm_Low": [anchors_local.get("base_low")],
            "Slope(ES)/30m": [SLOPE_PER_BLOCK],
            "Tolerance": [tol],
        }
        pkt[f"Summary_{target_day}_{ts}.csv"] = pd.DataFrame(summary).to_csv(index=False).encode()

    # Make ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in pkt.items():
            zf.writestr(name, data)
    return buf.getvalue(), len(pkt)

def render_export_tab_es():
    st.markdown('<div class="card"><div class="h2">📤 Export Center</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div style="color:var(--ter);margin-bottom:.5rem;">
          Download CSVs as a single ZIP: ES Lines, Weekly Signals, Intraday 30m (optional), Contract (optional), Fibonacci (optional), Summary.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("📦 Create Export Package", use_container_width=True):
        with st.spinner("Preparing export…"):
            data, nfiles = export_zip_es(forecast_date, tolerance, contract_state, fibonacci_state)
            fname = f"MarketLens_ES_Export_{datetime.now(tz=CT).strftime('%Y%m%d_%H%M%S')}.zip"
            st.download_button(
                "⬇️ Download ZIP",
                data=data,
                file_name=fname,
                mime="application/zip",
                use_container_width=True,
            )
            st.success(f"Ready • {nfiles} files")
    st.markdown("</div>", unsafe_allow_html=True)

with tabs_tools[2]:
    render_export_tab_es()
# =============================== END PART 6 =================================================================
