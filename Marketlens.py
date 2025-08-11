# ==============================  PART 1 — CORE SHELL (YOUR YFINANCE APPROACH)  ==============================
# Streamlit header visible • Always-open sidebar • SPX + equities
# Live strip via yf.Ticker(...).history(period="1d", interval="1m") with daily fallback
# Prev-day anchors via yf.Ticker(...).history(period="1mo", interval="1d")
# Overnight inputs (price+time) in sidebar • Mobile-polished 3D UI
# ------------------------------------------------------------------------------------------------------------

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# ───────────────────────────────  GLOBAL CONFIG  ───────────────────────────────
APP_NAME   = "MarketLens Pro"
TAGLINE    = "Enterprise SPX & Equities Forecasting"
VERSION    = "5.0"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Slope engine placeholders (used in later parts; kept here to match your spec)
SPX_SLOPES = {"prev_high_down": -0.2792, "prev_close_down": -0.2792, "prev_low_down": -0.2792, "tp_mirror_up": +0.2792}
SPX_OVERNIGHT_SLOPES = {"overnight_low_up": +0.2792, "overnight_high_down": -0.2792}

# App instruments (you can add/remove freely)
EQUITIES = ["^GSPC", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "TSLA"]

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS (DESKTOP + MOBILE)  ───────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

.stApp { background: radial-gradient(1200px 600px at 10% -10%, #f7faff 0%, #ffffff 35%) fixed; }

/* Hero */
.hero {
  border-radius: 24px;
  padding: 22px 24px;
  border: 1px solid rgba(15,23,42,.08);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 16px 36px rgba(99,102,241,.28);
}
.hero h1 { margin: 0; font-weight: 900; font-size: 28px; letter-spacing: -0.02em; }
.hero .sub { opacity: 0.95; font-weight: 700; margin-top: 2px; }
.hero .meta { opacity: 0.85; font-size: 12px; margin-top: 6px; }

/* KPI strip */
.kpi {
  display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 14px;
}
.kpi .card {
  border-radius: 16px; padding: 14px 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(2,6,23,.08);
  box-shadow: 0 8px 22px rgba(2,6,23,.10), inset 0 1px 0 rgba(255,255,255,.65);
}
.kpi .label { color: #64748b; font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.kpi .value { font-weight: 900; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }

/* Section card */
.sec { margin-top: 18px; border-radius: 20px; padding: 18px; 
  background: #ffffff; border: 1px solid rgba(2,6,23,.08);
  box-shadow: 0 14px 36px rgba(2,6,23,.08), inset 0 1px 0 rgba(255,255,255,.6);
}
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

/* Sidebar */
section[data-testid="stSidebar"] {
  background: #0b1220 !important; color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label { color: #e5e7eb !important; }
.sidebar-card {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px; margin: 10px 0;
}

/* Chips */
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(2,6,23,.08); background:#f8fafc; font-size:12px; font-weight:900; color:#0f172a;
}
.chip.ok   { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }

/* Table wrapper */
.table-wrap { border-radius: 16px; overflow: hidden; border: 1px solid rgba(2,6,23,.08); box-shadow: 0 10px 26px rgba(2,6,23,.08); }

/* ---------- MOBILE POLISH ---------- */
@media (max-width: 900px){
  .hero { border-radius: 20px; padding: 16px 16px 18px; }
  .hero h1 { font-size: 22px; line-height: 1.15; }
  .hero .sub { font-size: 13px; }
  .hero .meta { font-size: 11px; }
  .kpi { grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }
  .kpi .card { padding: 10px 12px; border-radius: 14px;
    box-shadow: 0 8px 18px rgba(2,6,23,.12), inset 0 1px 0 rgba(255,255,255,.25); }
  .kpi .label { font-size: 10px; }
  .kpi .value { font-size: 18px; }
  .sec { padding: 14px; border-radius: 16px; box-shadow: 0 10px 24px rgba(2,6,23,.07); }
  .sec h3 { font-size: 16px; }
  .chip { padding: 5px 8px; font-size: 11px; }
  .block-container { padding-left: 14px; padding-right: 14px; }
}
@media (max-width: 520px){
  .kpi { grid-template-columns: 1fr; }
  .hero h1 { font-size: 20px; }
  .kpi .value { font-size: 17px; }
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS — YOUR YF PATTERN  ───────────────────────────────
def previous_trading_day(ref_d: date) -> date:
    d = ref_d - timedelta(days=1)
    while d.weekday() >= 5:  # Sat/Sun
        d -= timedelta(days=1)
    return d

@st.cache_data(ttl=90, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """
    YOUR pattern: yf.Ticker(...).history(period='1d', interval='1m') for live,
    fallback to yf.Ticker(...).history(period='10d', interval='1d') for last close.
    """
    try:
        tkr = yf.Ticker(symbol)
        # Try intraday 1m (today)
        intraday = tkr.history(period="1d", interval="1m", prepost=True)
        if isinstance(intraday, pd.DataFrame) and not intraday.empty and "Close" in intraday.columns:
            last = intraday.iloc[-1]
            px = float(last["Close"])
            ts_idx = intraday.index[-1]
            # Ensure tz → ET
            if getattr(ts_idx, "tz", None) is None:
                ts = pd.Timestamp(ts_idx).tz_localize("UTC").tz_convert(ET)
            else:
                ts = pd.Timestamp(ts_idx).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a %-I:%M %p ET"), "source": "Yahoo 1m"}
        # Fallback to last daily close
        daily = tkr.history(period="10d", interval="1d")
        if isinstance(daily, pd.DataFrame) and not daily.empty and "Close" in daily.columns:
            last = daily.iloc[-1]
            px = float(last["Close"])
            ts_idx = daily.index[-1]
            if getattr(ts_idx, "tz", None) is None:
                ts = pd.Timestamp(ts_idx).tz_localize("UTC").tz_convert(ET)
            else:
                ts = pd.Timestamp(ts_idx).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a 4:00 PM ET"), "source": "Yahoo 1d"}
    except Exception:
        pass
    return {"px": "—", "ts": "—", "source": "—"}

@st.cache_data(ttl=300, show_spinner=False)
def get_previous_day_anchors(symbol: str, forecast_d: date) -> dict | None:
    """
    YOUR pattern: prev-day HIGH/CLOSE/LOW from daily candles.
    df = yf.Ticker(symbol).history(period='1mo', interval='1d')
    """
    try:
        prev_d = previous_trading_day(forecast_d)
        df = yf.Ticker(symbol).history(period="1mo", interval="1d")
        if df is None or df.empty:
            return None
        # Align index to ET date for matching
        idx = pd.Index(df.index)
        if getattr(idx[0], "tz", None) is None:
            dates_et = pd.to_datetime(idx).tz_localize("UTC").tz_convert(ET).date
        else:
            dates_et = pd.to_datetime(idx).tz_convert(ET).date
        df = df.assign(_d=list(dates_et))
        row = df[df["_d"] == prev_d]
        if row.empty:
            # conservative fallback to prior row
            row = df.iloc[[-2]] if len(df) >= 2 else df.iloc[[-1]]
            prev_d = row["_d"].iloc[-1]
        r = row.iloc[-1]
        return {
            "prev_day": prev_d,
            "high": float(r["High"]),
            "low": float(r["Low"]),
            "close": float(r["Close"]),
        }
    except Exception:
        return None

# ───────────────────────────────  SIDEBAR — NAV, ASSET, DATE, OVERNIGHT INPUTS  ───────────────────────────────
with st.sidebar:
    st.markdown("### 📚 Navigation")
    page = st.radio(
        label="",
        options=["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📈 Asset")
    asset = st.selectbox(
        "Choose instrument",
        options=EQUITIES,
        index=0,
        help="^GSPC = S&P 500 Index (SPX). Others are large-cap equities."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input(
        "Target session",
        value=date.today(),
        help="Used for previous-day anchor selection."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Overnight Anchor Inputs (manual price + time) — used in later parts
    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual)")
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing LOW price.")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Between 5:00 PM and 7:00 AM ET.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing HIGH price.")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Between 5:00 PM and 7:00 AM ET.")
    st.caption("These will power the Overnight Entries table in later parts.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE STRIP (YOUR FETCH)  ───────────────────────────────
# Friendly labels
label = "SPX" if asset == "^GSPC" else asset
last = fetch_live_quote(asset)

st.markdown(f"""
<div class="hero">
  <h1>{APP_NAME}</h1>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="card">
      <div class="label">{label} — Last</div>
      <div class="value">{last['px']}</div>
    </div>
    <div class="card">
      <div class="label">As of</div>
      <div class="value">{last['ts']}</div>
    </div>
    <div class="card">
      <div class="label">Session</div>
      <div class="value">{forecast_date.strftime('%a %b %d, %Y')}</div>
    </div>
    <div class="card">
      <div class="label">Engine</div>
      <div class="value"><span class="chip ok">{last['source']}</span></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────  OVERVIEW  ───────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)

    anchors = get_previous_day_anchors(asset, forecast_date)
    ready_chip = '<span class="chip ok">Prev-Day Anchors Ready</span>' if anchors else '<span class="chip info">Fetching daily data…</span>'

    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
            {ready_chip}
            <span class="chip info">Overnight inputs captured</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ───────────────────────────────  ANCHORS (DISPLAY)  ───────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Previous Day Anchors</h3>", unsafe_allow_html=True)

    anchors = get_previous_day_anchors(asset, forecast_date)
    if not anchors:
        st.info("Could not compute anchors yet. Try a recent weekday (Yahoo daily availability can vary).")
    else:
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Prev Day High", f"{anchors['high']:.2f}")
        with col2: st.metric("Prev Day Close", f"{anchors['close']:.2f}")
        with col3: st.metric("Prev Day Low",  f"{anchors['low']:.2f}")

        st.markdown(
            """
            <div class="table-wrap" style="margin-top:12px;">
              <div style="padding:12px 14px; color:#64748b; font-size:12px;">
                These anchors power your projections internally (descending lines from H/C/L with mirrored TP lines). 
                Nothing to configure here—fully automatic.
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDERS (LIGHT UP IN PARTS 2+)  ───────────────────────────────
if page in {"Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section will light up in the next parts with professional tables, detection, contract logic, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)






# ==============================  PART 2 — PREV-DAY PROJECTIONS (VISIBLE TEXT FIX + TABLE)  ==============================
# - Fixes invisible headings/text via small CSS override (safe on white backgrounds)
# - Computes prev-day H/L/C times from 1m (fallback to 4:00 PM ET)
# - Projects descending entry lines (−0.2792) and mirrored TP1/TP2 (+0.2792) 08:30–14:30 CT
# - Works for SPX (^GSPC) and all equities in your selector

# ---------- VISIBILITY FIX (safe override) ----------
st.markdown("""
<style>
div[data-testid="stMarkdownContainer"] h3,
div[data-testid="stMarkdownContainer"] h4,
div[data-testid="stMarkdownContainer"] p,
div[data-testid="stMarkdownContainer"] span {
  color: #0f172a !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- TIME & SLOTS HELPERS ----------
def _ct(dt):
    return pd.Timestamp(dt).tz_convert(CT)

def _et(dt):
    return pd.Timestamp(dt).tz_convert(ET)

def _slots_ct(start=time(8,30), end=time(14,30)):
    out, cur = [], datetime.combine(date(2025,1,1), start, tzinfo=CT)
    stop = datetime.combine(date(2025,1,1), end, tzinfo=CT)
    while cur <= stop:
        out.append(cur.time().strftime("%H:%M"))
        cur += timedelta(minutes=30)
    return out

SLOTS_30M = _slots_ct()

def _blocks_between_30m(t0: datetime, t1: datetime) -> int:
    """Count 30-min steps between t0->t1 (CT)."""
    if t1 < t0:
        t0, t1 = t1, t0
    delta = int((t1 - t0).total_seconds() // (30*60))
    return max(delta, 0)

def _project(price_base: float, t_base: datetime, t_target: datetime, slope_per_30m: float) -> float:
    return price_base + slope_per_30m * _blocks_between_30m(t_base, t_target)

# ---------- PREV-DAY INTRADAY TIMES (1m) ----------
@st.cache_data(ttl=300, show_spinner=False)
def _prevday_intraday_times(asset: str, prev_d: date) -> dict:
    """
    Try to locate the prev-day H/L time using 1-minute bars (RTH ET window).
    Fallback: use 4:00 PM ET for close, and 12:00 PM ET for H/L if 1m missing.
    """
    try:
        tkr = yf.Ticker(asset)
        # Pull 5d to be safe; filter locally to prev_d RTH
        df = tkr.history(period="5d", interval="1m", prepost=False)
        if isinstance(df, pd.DataFrame) and not df.empty:
            idx = df.index
            if getattr(idx[0], "tz", None) is None:
                df.index = pd.to_datetime(idx).tz_localize("UTC").tz_convert(ET)
            else:
                df.index = pd.to_datetime(idx).tz_convert(ET)

            day = df.loc[df.index.date == prev_d]
            # RTH filter 9:30–16:00 ET
            day = day.loc[(day.index.time >= time(9,30)) & (day.index.time <= time(16,0))]
            if not day.empty:
                hi_idx = day["High"].idxmax()
                lo_idx = day["Low"].idxmin()
                t_hi_ct = _ct(hi_idx)
                t_lo_ct = _ct(lo_idx)
                t_cl_ct = _ct(day.index[-1])
                return {"t_hi_ct": t_hi_ct, "t_lo_ct": t_lo_ct, "t_cl_ct": t_cl_ct}

        # Fallback times (RTH close & midday stand-ins)
        return {
            "t_hi_ct": _ct(datetime.combine(prev_d, time(12, 0), tzinfo=ET)),
            "t_lo_ct": _ct(datetime.combine(prev_d, time(12, 0), tzinfo=ET)),
            "t_cl_ct": _ct(datetime.combine(prev_d, time(16, 0), tzinfo=ET)),
        }
    except Exception:
        return {
            "t_hi_ct": _ct(datetime.combine(prev_d, time(12, 0), tzinfo=ET)),
            "t_lo_ct": _ct(datetime.combine(prev_d, time(12, 0), tzinfo=ET)),
            "t_cl_ct": _ct(datetime.combine(prev_d, time(16, 0), tzinfo=ET)),
        }

# ---------- PREV-DAY TABLE BUILDER ----------
@st.cache_data(ttl=240, show_spinner=False)
def _build_prevday_projection_table(asset: str, forecast_d: date) -> tuple[pd.DataFrame, dict] | tuple[None, None]:
    anchors = get_previous_day_anchors(asset, forecast_d)
    if not anchors:
        return None, None

    prev_d = anchors["prev_day"]
    times = _prevday_intraday_times(asset, prev_d)

    # Base prices & times (CT)
    base = {
        "HIGH": {"px": anchors["high"],  "t": times["t_hi_ct"]},
        "CLOSE":{"px": anchors["close"], "t": times["t_cl_ct"]},
        "LOW":  {"px": anchors["low"],   "t": times["t_lo_ct"]},
    }

    # Slopes
    s_dn = SPX_SLOPES["prev_high_down"]     # -0.2792 per 30m (same for H/C/L)
    s_up = SPX_SLOPES["tp_mirror_up"]       # +0.2792 per 30m

    # Build rows 08:30–14:30 CT for forecast date
    rows = []
    for hhmm in SLOTS_30M:
        h, m = map(int, hhmm.split(":"))
        t_target = datetime.combine(forecast_d, time(h, m), tzinfo=CT)

        # For each anchor: entry = descend from base, TP2 = ascend from base, TP1 = halfway
        rec = {"Time": hhmm}
        for key in ("HIGH", "CLOSE", "LOW"):
            entry = _project(base[key]["px"], base[key]["t"], t_target, s_dn)
            tp2   = _project(base[key]["px"], base[key]["t"], t_target, s_up)
            # Directional: if entry < tp2 ⇒ long context; else short context; TP1 halfway
            tp1 = entry + (tp2 - entry) * 0.5
            rec[f"{key}_Entry"] = round(entry, 2)
            rec[f"{key}_TP1"]   = round(tp1, 2)
            rec[f"{key}_TP2"]   = round(tp2, 2)
        rows.append(rec)

    df = pd.DataFrame(rows)
    meta = {
        "asset": asset,
        "prev_day": str(prev_d),
        "bases": {k: {"price": float(v["px"]), "time_ct": v["t"].strftime("%Y-%m-%d %H:%M CT")} for k,v in base.items()},
        "slopes": {"down_per_30m": s_dn, "up_per_30m": s_up}
    }
    return df, meta

# ---------- UI: FORECASTS PAGE ----------
if page == "Forecasts":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    label = "SPX500" if asset == "^GSPC" else asset
    st.markdown(f"<h3>{label} — Previous Day Line Projection: Entries & Targets</h3>", unsafe_allow_html=True)

    table, meta = _build_prevday_projection_table(asset, forecast_date)
    if table is None:
        st.info("Anchors not available yet (Yahoo daily/1m may be out for the chosen date). Try a recent weekday.")
    else:
        st.caption(
            f"Prev Day ({meta['prev_day']}) bases — "
            f"High {meta['bases']['HIGH']['price']:.2f} at {meta['bases']['HIGH']['time_ct']} • "
            f"Close {meta['bases']['CLOSE']['price']:.2f} at {meta['bases']['CLOSE']['time_ct']} • "
            f"Low {meta['bases']['LOW']['price']:.2f} at {meta['bases']['LOW']['time_ct']}"
        )

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Time": st.column_config.TextColumn("Time", width="small"),
                "HIGH_Entry": st.column_config.NumberColumn("High Entry ($)", format="$%.2f"),
                "HIGH_TP1":   st.column_config.NumberColumn("High TP1 ($)",   format="$%.2f"),
                "HIGH_TP2":   st.column_config.NumberColumn("High TP2 ($)",   format="$%.2f"),
                "CLOSE_Entry":st.column_config.NumberColumn("Close Entry ($)",format="$%.2f"),
                "CLOSE_TP1":  st.column_config.NumberColumn("Close TP1 ($)",  format="$%.2f"),
                "CLOSE_TP2":  st.column_config.NumberColumn("Close TP2 ($)",  format="$%.2f"),
                "LOW_Entry":  st.column_config.NumberColumn("Low Entry ($)",  format="$%.2f"),
                "LOW_TP1":    st.column_config.NumberColumn("Low TP1 ($)",    format="$%.2f"),
                "LOW_TP2":    st.column_config.NumberColumn("Low TP2 ($)",    format="$%.2f"),
            }
        )
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- UI: ANCHORS PAGE (ensure visible labels) ----------
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    label = "SPX500" if asset == "^GSPC" else asset
    st.markdown(f"<h3>{label} — Previous Day Anchors</h3>", unsafe_allow_html=True)

    anchors = get_previous_day_anchors(asset, forecast_date)
    if not anchors:
        st.info("Could not compute anchors yet. Try a recent weekday.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Prev Day High",  f"{anchors['high']:.2f}")
        with c2: st.metric("Prev Day Close", f"{anchors['close']:.2f}")
        with c3: st.metric("Prev Day Low",   f"{anchors['low']:.2f}")

        pd_times = _prevday_intraday_times(asset, anchors["prev_day"])
        st.caption(
            f"Anchor times (CT) — High: {pd_times['t_hi_ct'].strftime('%-I:%M %p')} • "
            f"Close: {pd_times['t_cl_ct'].strftime('%-I:%M %p')} • "
            f"Low: {pd_times['t_lo_ct'].strftime('%-I:%M %p')}  "
            "(intraday 1m fallback used if needed)"
        )

    st.markdown('</div>', unsafe_allow_html=True)
