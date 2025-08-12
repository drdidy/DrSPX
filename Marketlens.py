# ==============================  PART 1 — CORE SHELL (ES→SPX, 5–8 PM CT)  ==============================
# Visible Streamlit header • Always-open sidebar • SPX shown as “SPX500” (uses ES=F under the hood)
# Live strip via yf.Ticker(...).history (1m with daily fallback)
# Basis: mean(ES - SPX) over 14:30–15:00 CT (last RTH half-hour); fallback to previous day
# Asian anchors auto-detect: 17:00–20:00 CT from ES, then SPX_proxy = ES - basis
# Manual Overnight High/Low overrides (price + time) • Mobile-polished 3D UI
# No charts; anchors preview only. Slopes are stored (used in Part 2+).
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
VERSION    = "5.1"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Symbols
SPX_UI_LABEL = "SPX500"   # UI label
SPX_YF       = "^GSPC"    # Yahoo symbol for SPX
ES_YF        = "ES=F"     # E-mini S&P (front month) for overnight anchors

# Slopes (stored; used in later parts)
SPX_SLOPES = {
    "asc_per_30m": +0.2432,   # ascending per 30m
    "desc_per_30m": -0.2432,  # descending per 30m
}
CONTRACT_DECAY_PER_HR = -0.30  # (used later)

# App instruments (SPX first, others visible but Asian logic applies only to SPX)
EQUITIES = [SPX_YF, "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "TSLA"]

# RTH & Asian windows (CT)
RTH_START_CT, RTH_END_CT = time(8, 30), time(15, 0)   # cash hours
ASIAN_START_CT, ASIAN_END_CT = time(17, 0), time(20, 0)  # 5–8 PM CT

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS (DESKTOP + MOBILE; Header visible)  ───────────────────────────────
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
.kpi .label { color: #5b6474; font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.kpi .value { font-weight: 900; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }

/* Section card */
.sec { margin-top: 18px; border-radius: 20px; padding: 18px;
  background: #ffffff; border: 1px solid rgba(2,6,23,.08);
  box-shadow: 0 14px 36px rgba(2,6,23,.08), inset 0 1px 0 rgba(255,255,255,.6);
}
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; color:#0f172a; }
.sec .muted { color:#475569; font-size:12px; }

/* Sidebar */
section[data-testid="stSidebar"] {
  background: #0b1220 !important; color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p { color: #e5e7eb !important; }
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

# ───────────────────────────────  HELPERS — YF FETCHES  ───────────────────────────────
def _safe_history(symbol: str, period: str, interval: str, prepost: bool = True) -> pd.DataFrame:
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval, prepost=prepost)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=90, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """1m today with fallback to last daily close; timestamp in ET."""
    try:
        intraday = _safe_history(symbol, "1d", "1m", prepost=True)
        if not intraday.empty and "Close" in intraday.columns:
            px = float(intraday["Close"].iloc[-1])
            ts_idx = intraday.index[-1]
            ts = (pd.Timestamp(ts_idx).tz_localize("UTC") if getattr(ts_idx, "tz", None) is None
                  else pd.Timestamp(ts_idx)).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a %-I:%M %p ET"), "source": "Yahoo 1m"}
        daily = _safe_history(symbol, "10d", "1d", prepost=False)
        if not daily.empty and "Close" in daily.columns:
            px = float(daily["Close"].iloc[-1])
            ts_idx = daily.index[-1]
            ts = (pd.Timestamp(ts_idx).tz_localize("UTC") if getattr(ts_idx, "tz", None) is None
                  else pd.Timestamp(ts_idx)).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a 4:00 PM ET"), "source": "Yahoo 1d"}
    except Exception:
        pass
    return {"px": "—", "ts": "—", "source": "—"}

def _to_ct(ts) -> datetime:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(CT).to_pydatetime()

def _filter_ct_window(df: pd.DataFrame, start_t: time, end_t: time) -> pd.DataFrame:
    if df.empty: return df
    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex):
        return pd.DataFrame()
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    ct = idx.tz_convert(CT)
    mask = (ct.time >= start_t) & (ct.time <= end_t)
    out = df.loc[mask].copy()
    out.index = ct[mask]
    return out

@st.cache_data(ttl=300, show_spinner=False)
def compute_basis_for_day(d: date) -> float | None:
    """
    Basis = mean(ES - SPX) over 14:30–15:00 CT on date d (or previous trading day if d has no data).
    """
    def _day_with_data(ref: date) -> date:
        # find most recent weekday with some SPX daily data
        dd = ref
        for _ in range(6):
            if dd.weekday() < 5:
                return dd
            dd -= timedelta(days=1)
        return ref

    ref_d = _day_with_data(d)
    intraday_es = _safe_history(ES_YF, "5d", "1m", prepost=True)
    intraday_spx = _safe_history(SPX_YF, "5d", "1m", prepost=True)
    if intraday_es.empty or intraday_spx.empty:
        return None

    # keep last two days to improve chance of overlap; then filter by CT & date
    es_ct = intraday_es.copy()
    spx_ct = intraday_spx.copy()
    es_ct.index = pd.DatetimeIndex(es_ct.index.tz_localize("UTC") if es_ct.index.tz is None else es_ct.index).tz_convert(CT)
    spx_ct.index = pd.DatetimeIndex(spx_ct.index.tz_localize("UTC") if spx_ct.index.tz is None else spx_ct.index).tz_convert(CT)

    es_day = es_ct[es_ct.index.date == ref_d]
    spx_day = spx_ct[spx_ct.index.date == ref_d]

    if es_day.empty or spx_day.empty:
        # fallback to previous weekday
        alt = ref_d - timedelta(days=1)
        while alt.weekday() >= 5:
            alt -= timedelta(days=1)
        es_day = es_ct[es_ct.index.date == alt]
        spx_day = spx_ct[spx_ct.index.date == alt]
        if es_day.empty or spx_day.empty:
            return None
        ref_d = alt

    # 14:30–15:00 CT window
    es_win = es_day.between_time("14:30", "15:00")
    spx_win = spx_day.between_time("14:30", "15:00")
    if es_win.empty or spx_win.empty:
        return None

    # align on timestamps (inner join)
    es_close = es_win["Close"].rename("ES")
    spx_close = spx_win["Close"].rename("SPX")
    both = pd.concat([es_close, spx_close], axis=1).dropna()
    if both.empty:
        return None

    basis = float((both["ES"] - both["SPX"]).mean())
    return basis

@st.cache_data(ttl=300, show_spinner=False)
def detect_asian_anchors_spx_proxy(session_d: date, manual: dict | None = None) -> dict | None:
    """
    Use ES=F 1m bars between 17:00–20:00 CT on session_d to find swing high/low.
    Convert to SPX proxy via basis from last RTH 14:30–15:00 CT.
    If manual override exists, prefer manual entries (price+time) selectively.
    Returns: { 'basis': float, 'high_px': float, 'high_time_ct': dt, 'low_px': float, 'low_time_ct': dt, 'source': 'auto'|'manual'|'mixed' }
    """
    # basis for conversion
    basis = compute_basis_for_day(session_d)
    if basis is None:
        basis = 0.0  # if no basis available we still allow manual inputs to pass through (assume ES≈SPX)
    # pull ES intraday
    es_1m = _safe_history(ES_YF, "5d", "1m", prepost=True)
    if es_1m.empty:
        es_1m = pd.DataFrame()

    if not es_1m.empty:
        es_1m_ct = es_1m.copy()
        es_1m_ct.index = pd.DatetimeIndex(es_1m_ct.index.tz_localize("UTC") if es_1m_ct.index.tz is None else es_1m_ct.index).tz_convert(CT)
        # filter to specific date and 17:00–20:00 CT
        day_mask = es_1m_ct.index.date == session_d
        win = es_1m_ct.loc[day_mask].between_time("17:00", "20:00")
    else:
        win = pd.DataFrame()

    auto_high, auto_low, high_t, low_t = None, None, None, None
    if not win.empty and {"High","Low"}.issubset(win.columns):
        # Use ES prices, then convert to SPX proxy by subtracting basis
        hi_idx = win["High"].idxmax()
        lo_idx = win["Low"].idxmin()
        auto_high = float(win.loc[hi_idx, "High"] - basis)
        auto_low  = float(win.loc[lo_idx, "Low"]  - basis)
        high_t = hi_idx.to_pydatetime()
        low_t  = lo_idx.to_pydatetime()

    # Manual overrides
    source = "auto"
    if manual:
        use_any = False
        if manual.get("high_px", 0) > 0 and isinstance(manual.get("high_time"), time):
            auto_high = float(manual["high_px"])
            # combine date with manual time in CT
            high_t = datetime.combine(session_d, manual["high_time"], tzinfo=CT)
            source = "mixed" if win is not None and not win.empty else "manual"
            use_any = True
        if manual.get("low_px", 0) > 0 and isinstance(manual.get("low_time"), time):
            auto_low = float(manual["low_px"])
            low_t = datetime.combine(session_d, manual["low_time"], tzinfo=CT)
            source = "mixed" if win is not None and not win.empty else "manual"
            use_any = True
        if not use_any and (auto_high is None or auto_low is None):
            return None

    if auto_high is None or auto_low is None or high_t is None or low_t is None:
        return None

    return {
        "basis": basis,
        "high_px": round(auto_high, 2),
        "high_time_ct": high_t,
        "low_px": round(auto_low, 2),
        "low_time_ct": low_t,
        "source": source
    }

# ───────────────────────────────  SIDEBAR — NAV, ASSET, DATE, MANUAL OVERNIGHT INPUTS  ───────────────────────────────
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
        help="SPX500 uses ES futures for Asian anchors internally."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input(
        "Target session",
        value=date.today(),
        help="Used for basis and Asian (5–8 PM CT) anchor detection."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Manual Overnight Anchor Inputs (optional override)
    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual, SPX)")
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Swing LOW price for SPX proxy.")
    on_low_time   = st.time_input("Overnight Low Time (CT)", value=time(17, 30), help="Between 5:00 PM and 8:00 PM CT.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Swing HIGH price for SPX proxy.")
    on_high_time  = st.time_input("Overnight High Time (CT)", value=time(18, 30), help="Between 5:00 PM and 8:00 PM CT.")
    st.caption("Tip: Leave as 0.00 to use automatic detection from ES (converted to SPX).")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE STRIP  ───────────────────────────────
label = SPX_UI_LABEL if asset == SPX_YF else asset
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
    # basis preview only when SPX
    if asset == SPX_YF:
        basis = compute_basis_for_day(forecast_date)
        if basis is None:
            st.markdown('<div class="muted">Basis not available yet (will fallback to previous day or use manual inputs).</div>', unsafe_allow_html=True)
            st.markdown('<span class="chip info">ES→SPX basis pending</span>', unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="chip ok">Basis ready: {basis:+.2f} (ES−SPX)</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="chip info">Equity selected — SPX Asian logic not applied</span>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ───────────────────────────────  ANCHORS (DISPLAY)  ───────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    if asset != SPX_YF:
        st.markdown("<h3>Anchors</h3>", unsafe_allow_html=True)
        st.markdown('<div class="muted">Anchors for individual equities arrive in Part 2+.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown("<h3>Asian Session Anchors (SPX via ES, 5–8 PM CT)</h3>", unsafe_allow_html=True)

        manual = {
            "high_px": on_high_price,
            "high_time": on_high_time,
            "low_px": on_low_price,
            "low_time": on_low_time,
        }

        anchors = detect_asian_anchors_spx_proxy(forecast_date, manual=manual)
        if not anchors:
            st.info("Could not compute anchors. Try a recent weekday and ensure ES data exists for 5–8 PM CT. Manual inputs also work.")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Basis (ES−SPX)", f"{anchors['basis']:+.2f}")
                st.caption("From 14:30–15:00 CT")
            with col2:
                st.metric("Overnight High (SPX proxy)", f"{anchors['high_px']:.2f}")
                st.caption(f"Time CT: {anchors['high_time_ct'].strftime('%-I:%M %p')}")
            with col3:
                st.metric("Overnight Low (SPX proxy)", f"{anchors['low_px']:.2f}")
                st.caption(f"Time CT: {anchors['low_time_ct'].strftime('%-I:%M %p')}")

            st.markdown(
                """
                <div class="table-wrap" style="margin-top:12px;">
                  <div style="padding:12px 14px; color:#475569; font-size:12px;">
                    Source: <strong>ES (converted to SPX)</strong> — detection window <strong>5:00–8:00 PM CT</strong>. 
                    Manual entries override per field. Slopes (±0.2432/30m) apply in the next part to generate entry/TP tables.
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
    st.caption("This section lights up in the next parts with professional tables (entries & TP1/TP2), contract decay lines, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)