# ==============================  PART 1 — CORE SHELL (YF + ES→SPX, VISIBILITY FIX)  ==============================
# Streamlit header visible • Always-open sidebar • SPX + equities
# Live strip via yf.Ticker(...).history(period="1d", interval="1m") with daily fallback
# Asian session anchors 5–8 PM CT from ES (^ES=F) → converted to SPX 1:1 for display/use
# Overnight inputs (price+time) in sidebar • Mobile-polished 3D UI • Visibility patch for light text
# -----------------------------------------------------------------------------------------------------------

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

# Slope engine placeholders (used later; kept here to match your spec)
SPX_SLOPES = {"prev_high_down": -0.2432, "prev_close_down": -0.2432, "prev_low_down": -0.2432, "tp_mirror_up": +0.2432}
SPX_OVERNIGHT_SLOPES = {"overnight_low_up": +0.2432, "overnight_high_down": -0.2432}

# Instruments
EQUITIES = ["^GSPC", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "TSLA"]
ES_SYMBOL = "^ES=F"   # CME E-mini S&P 500 futures (continuous)

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
.sec h3 { margin: 0 0 10px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; color:#0f172a; }
.sec .muted { color:#475569; }

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

/* ---------- VISIBILITY PATCH (Main area) ---------- */
.block-container, .block-container * { color: #0f172a; }
div[data-testid="stMetricLabel"]{ color:#64748b !important; }
div[data-testid="stMetricValue"]{ color:#0f172a !important; }
.stCaption, .stCaption p { color:#475569 !important; }

/* Keep hero text white */
.hero h1, .hero .sub, .hero .meta { color: #fff !important; }

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
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

@st.cache_data(ttl=90, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """Your pattern: 1m today, fallback to last daily close."""
    try:
        tkr = yf.Ticker(symbol)
        intraday = tkr.history(period="1d", interval="1m", prepost=True)
        if isinstance(intraday, pd.DataFrame) and not intraday.empty and "Close" in intraday.columns:
            last = intraday.iloc[-1]
            px = float(last["Close"])
            ts_idx = intraday.index[-1]
            ts = (pd.Timestamp(ts_idx).tz_localize("UTC") if getattr(ts_idx, "tz", None) is None else pd.Timestamp(ts_idx)).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a %-I:%M %p ET"), "source": "Yahoo 1m"}
        daily = tkr.history(period="10d", interval="1d")
        if isinstance(daily, pd.DataFrame) and not daily.empty and "Close" in daily.columns:
            last = daily.iloc[-1]
            px = float(last["Close"])
            ts_idx = daily.index[-1]
            ts = (pd.Timestamp(ts_idx).tz_localize("UTC") if getattr(ts_idx, "tz", None) is None else pd.Timestamp(ts_idx)).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a 4:00 PM ET"), "source": "Yahoo 1d"}
    except Exception:
        pass
    return {"px": "—", "ts": "—", "source": "—"}

@st.cache_data(ttl=180, show_spinner=False)
def get_previous_day_anchors(symbol: str, forecast_d: date) -> dict | None:
    """Prev-day HIGH/CLOSE/LOW from daily candles."""
    try:
        prev_d = previous_trading_day(forecast_d)
        df = yf.Ticker(symbol).history(period="1mo", interval="1d")
        if df is None or df.empty:
            return None
        idx = pd.Index(df.index)
        dates_et = (pd.to_datetime(idx).tz_localize("UTC").tz_convert(ET).date
                    if getattr(idx[0], "tz", None) is None else
                    pd.to_datetime(idx).tz_convert(ET).date)
        df = df.assign(_d=list(dates_et))
        row = df[df["_d"] == prev_d]
        if row.empty:
            row = df.iloc[[-2]] if len(df) >= 2 else df.iloc[[-1]]
            prev_d = row["_d"].iloc[-1]
        r = row.iloc[-1]
        return {"prev_day": prev_d, "high": float(r["High"]), "low": float(r["Low"]), "close": float(r["Close"])}
    except Exception:
        return None

# ───────────────────────────────  ES FUTURES → SPX: ASIAN WINDOW 5–8 PM CT  ───────────────────────────────
def asian_window_ct(forecast_d: date) -> tuple[datetime, datetime]:
    """
    For a given RTH session date D, the Asian window we use is the *prior evening*:
      D-1 17:00 CT  →  D-1 20:00 CT
    """
    prior = forecast_d - timedelta(days=1)
    start = datetime.combine(prior, time(17, 0), tzinfo=CT)
    end   = datetime.combine(prior, time(20, 0), tzinfo=CT)
    return start, end

@st.cache_data(ttl=300, show_spinner=False)
def es_fetch_15m_ct(start_ct: datetime, end_ct: datetime) -> pd.DataFrame:
    """
    Fetch ES (^ES=F) with 15m granularity around the window, convert timestamps to CT,
    and return a tidy OHLC dataframe.
    """
    try:
        tkr = yf.Ticker(ES_SYMBOL)
        # use a slightly wider period, then filter locally
        raw = tkr.history(period="7d", interval="15m", prepost=True)
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        df = raw.reset_index().rename(columns={"Datetime":"Dt"})
        if "Dt" not in df.columns:
            if "index" in df.columns:
                df["Dt"] = pd.to_datetime(df["index"])
            else:
                return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        dt = pd.to_datetime(df["Dt"], utc=True)
        df["Dt"] = dt.dt.tz_convert(CT)
        out = df[["Dt","Open","High","Low","Close"]].dropna()
        mask = (out["Dt"] >= start_ct) & (out["Dt"] <= end_ct)
        return out.loc[mask].sort_values("Dt").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

@st.cache_data(ttl=300, show_spinner=False)
def es_asian_anchors_as_spx(forecast_d: date) -> dict | None:
    """
    Compute Asian-session swing HIGH/LOW (5–8 PM CT) from ES and treat as SPX values (1:1 passthrough).
    Returns:
      { high_px, high_time_ct, low_px, low_time_ct }
    """
    start_ct, end_ct = asian_window_ct(forecast_d)
    es = es_fetch_15m_ct(start_ct - timedelta(minutes=30), end_ct + timedelta(minutes=30))
    if es.empty:
        return None
    hi_idx = es["High"].idxmax()
    lo_idx = es["Low"].idxmin()
    return {
        "high_px": float(es.loc[hi_idx, "High"]),
        "high_time_ct": es.loc[hi_idx, "Dt"].to_pydatetime(),
        "low_px": float(es.loc[lo_idx, "Low"]),
        "low_time_ct": es.loc[lo_idx, "Dt"].to_pydatetime(),
    }

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
        help="^GSPC = S&P 500 Index (SPX). ES futures are used in the background for Asian-session anchors."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input(
        "Target session",
        value=date.today(),
        help="Used for prev-day anchors and for the ES Asian window (prior evening 5–8 PM CT)."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Overnight manual inputs (kept for later parts)
    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual)")
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing LOW price.")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Between 5:00 PM and 7:00 AM ET.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing HIGH price.")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Between 5:00 PM and 7:00 AM ET.")
    st.caption("These will power the Overnight Entries table in later parts.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE STRIP  ───────────────────────────────
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
    asian = es_asian_anchors_as_spx(forecast_date)

    chips = []
    chips.append('<span class="chip ok">Live strip ready</span>' if last['px'] != "—" else '<span class="chip info">Waiting on Yahoo data…</span>')
    chips.append('<span class="chip ok">Prev-day anchors ready</span>' if anchors else '<span class="chip info">Prev-day anchors pending</span>')
    chips.append('<span class="chip ok">Asian anchors ready</span>' if asian else '<span class="chip info">Asian anchors pending</span>')

    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:8px;'>{''.join(chips)}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ───────────────────────────────  ANCHORS (DISPLAY)  ───────────────────────────────
if page == "Anchors":
    # Previous Day (daily)
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Previous Day Anchors (Daily)</h3>", unsafe_allow_html=True)

    pd_anchors = get_previous_day_anchors(asset, forecast_date)
    if not pd_anchors:
        st.info("Could not compute previous-day anchors. Try a recent weekday.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Prev Day High", f"{pd_anchors['high']:.2f}")
        with c2: st.metric("Prev Day Close", f"{pd_anchors['close']:.2f}")
        with c3: st.metric("Prev Day Low",  f"{pd_anchors['low']:.2f}")
        st.caption("These daily anchors power your projections internally.")

    st.markdown("</div>", unsafe_allow_html=True)

    # Asian Session via ES (5–8 PM CT)
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Asian Session Anchors (SPX via ES, 5–8 PM CT)</h3>", unsafe_allow_html=True)

    asian = es_asian_anchors_as_spx(forecast_date)
    if not asian:
        st.info("Could not compute anchors. Try a recent weekday and ensure ES data exists for 5–8 PM CT.")
    else:
        a1, a2 = st.columns(2)
        with a1:
            st.metric("Asian Swing High (SPX-equiv)", f"{asian['high_px']:.2f}")
            st.caption(f"Time CT: {asian['high_time_ct'].strftime('%-I:%M %p')}")
        with a2:
            st.metric("Asian Swing Low (SPX-equiv)", f"{asian['low_px']:.2f}")
            st.caption(f"Time CT: {asian['low_time_ct'].strftime('%-I:%M %p')}")
        start_ct, end_ct = asian_window_ct(forecast_date)
        st.caption(f"Window used: {start_ct.strftime('%b %d, %Y %-I:%M %p')} → {end_ct.strftime('%-I:%M %p')} CT (prior evening)")

    st.markdown("</div>", unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDERS (LIGHT UP IN PARTS 2+)  ───────────────────────────────
if page in {"Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section will light up in the next parts with professional tables, detection, contract logic, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)