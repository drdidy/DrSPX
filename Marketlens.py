# ==============================  PART 1 — CORE SHELL (Yahoo ES=F + YFinance)  ==============================
# • Asian session anchors for SPX via Yahoo ES=F (5–8 PM CT), auto-converted to SPX (basis adjustable)
# • Live strip for SPX & equities via your yfinance pattern (1m with daily fallback)
# • Clean, high-contrast UI (mobile friendly), visible header, always-open sidebar
# ============================================================================================================
from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# ─────────────────────────────  GLOBALS  ─────────────────────────────
APP_NAME   = "MarketLens Pro"
TAGLINE    = "Enterprise SPX & Equities Forecasting"
VERSION    = "5.1"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# ES → SPX conversion (basis tweak if you ever notice consistent offset)
ES_TO_SPX_BASIS = 0.0     # points to add after mapping ES → SPX (keep 0 unless you measure a bias)

# Your slopes (used in later parts)
SPX_SLOPES = {"prev_high_down": -0.2432, "prev_close_down": -0.2432, "prev_low_down": -0.2432, "tp_mirror_up": +0.2432}
CONTRACT_DECAY_PER_HOUR = 0.30  # for options tables later

# App instruments
EQUITIES = ["^GSPC", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "TSLA"]

# ─────────────────────────────  PAGE CONFIG  ─────────────────────────────
st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# ─────────────────────────────  PREMIUM CSS (high contrast + mobile)  ─────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
.stApp { background: radial-gradient(1200px 600px at 10% -10%, #f7faff 0%, #ffffff 35%) fixed; }

/* Hero banner */
.hero { border-radius: 24px; padding: 22px 24px; border: 1px solid rgba(15,23,42,.08);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%); color: #0b1220; position: relative; }
.hero .glass { position:absolute; inset:6px; border-radius:20px; background: rgba(255,255,255,.16); }
.hero .content { position:relative; z-index:2; color: #fff; }
.hero h1 { margin:0; font-weight:900; font-size:28px; letter-spacing:-.02em; }
.hero .sub { opacity:.95; font-weight:700; margin-top:2px; }
.hero .meta { opacity:.90; font-size:12px; margin-top:6px; }

/* KPI cards (3D look) */
.kpi { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:14px; margin-top:14px; }
.kpi .card { border-radius:16px; padding:14px 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(2,6,23,.10);
  box-shadow: 0 10px 28px rgba(2,6,23,.12), inset 0 1px 0 rgba(255,255,255,.70); }
.kpi .label { color:#0f172a; opacity:.66; font-size:11px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; }
.kpi .value { font-weight:900; font-size:22px; color:#0f172a; letter-spacing:-.02em; }

/* Section card */
.sec { margin-top:18px; border-radius:20px; padding:18px; background:#ffffff;
  border: 1px solid rgba(2,6,23,.10);
  box-shadow: 0 14px 36px rgba(2,6,23,.10), inset 0 1px 0 rgba(255,255,255,.7); }
.sec h3 { margin:0 0 10px 0; font-size:22px; font-weight:900; letter-spacing:-.01em; color:#0b1220; }

/* Sidebar */
section[data-testid="stSidebar"]{ background:#0b1220 !important; color:#e5e7eb; border-right:1px solid rgba(255,255,255,.06); }
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label { color:#e5e7eb !important; }
.sidebar-card{ background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); border-radius:14px; padding:12px; margin:10px 0; }

/* Chips */
.chip{ display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(2,6,23,.12); background:#eef2ff; font-size:12px; font-weight:900; color:#312e81; }
.chip.ok{ background:#ecfdf5; border-color:#10b98133; color:#065f46; }

/* Info alert */
.info { background:#e0f2fe; color:#0c4a6e; border:1px solid #7dd3fc; border-radius:14px; padding:14px 16px; }

/* Mobile polish */
@media (max-width: 900px){
  .hero{ border-radius:20px; padding:16px; }
  .kpi{ grid-template-columns: repeat(2, minmax(0,1fr)); gap:10px; }
  .kpi .card{ padding:10px 12px; border-radius:14px; }
  .kpi .value{ font-size:18px; }
  .sec{ padding:14px; border-radius:16px; }
}
@media (max-width: 520px){ .kpi{ grid-template-columns: 1fr; } .hero h1{ font-size:20px; } }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────  YF HELPERS  ─────────────────────────────
def previous_trading_day(ref_d: date) -> date:
    d = ref_d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

@st.cache_data(ttl=90, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """Your pattern: try 1m today, fallback to last daily close."""
    try:
        tkr = yf.Ticker(symbol)
        intraday = tkr.history(period="1d", interval="1m", prepost=True)
        if isinstance(intraday, pd.DataFrame) and not intraday.empty and "Close" in intraday.columns:
            last = intraday.iloc[-1]
            px = float(last["Close"])
            ts_idx = intraday.index[-1]
            ts = (pd.Timestamp(ts_idx).tz_localize("UTC") if getattr(ts_idx,"tz",None) is None else pd.Timestamp(ts_idx)).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a %-I:%M %p ET"), "source": "Yahoo 1m"}
        daily = tkr.history(period="10d", interval="1d")
        if isinstance(daily, pd.DataFrame) and not daily.empty and "Close" in daily.columns:
            last = daily.iloc[-1]
            px = float(last["Close"])
            ts_idx = daily.index[-1]
            ts = (pd.Timestamp(ts_idx).tz_localize("UTC") if getattr(ts_idx,"tz",None) is None else pd.Timestamp(ts_idx)).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a 4:00 PM ET"), "source": "Yahoo 1d"}
    except Exception:
        pass
    return {"px":"—","ts":"—","source":"—"}

def es_to_spx(es_px: float) -> float:
    return float(es_px) + ES_TO_SPX_BASIS

def asian_window_ct_for(session_d: date) -> tuple[datetime, datetime]:
    """Asian window = PRIOR calendar day, 5:00–8:00 PM CT."""
    prior = session_d - timedelta(days=1)
    start_ct = datetime.combine(prior, time(17,0), tzinfo=CT)
    end_ct   = datetime.combine(prior, time(20,0), tzinfo=CT)
    return start_ct, end_ct

@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_es1m_ct(start_ct: datetime, end_ct: datetime) -> pd.DataFrame:
    """Fetch ES=F 1m (fallback 5m) from Yahoo, return CT-indexed DataFrame with OHLC."""
    try:
        # pull a bigger bucket then filter locally
        df = yf.Ticker("ES=F").history(period="7d", interval="1m")  # 1m first
        if (df is None or df.empty) and True:
            df = yf.Ticker("ES=F").history(period="60d", interval="5m")  # fallback
        if df is None or df.empty:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        df = df.reset_index()
        # Normalize datetime column name
        if "Datetime" in df.columns:
            dt = pd.to_datetime(df["Datetime"])
        elif "Date" in df.columns:
            dt = pd.to_datetime(df["Date"])
        else:
            dt = pd.to_datetime(df[df.columns[0]])
        # Yahoo often returns UTC tz-naive; force UTC then convert → CT
        if dt.dt.tz is None:
            dt = dt.dt.tz_localize("UTC")
        dt_ct = dt.dt.tz_convert(CT)
        out = pd.DataFrame({
            "Dt": dt_ct,
            "Open": df["Open"].astype(float),
            "High": df["High"].astype(float),
            "Low":  df["Low"].astype(float),
            "Close":df["Close"].astype(float),
        }).dropna()
        mask = (out["Dt"] >= start_ct) & (out["Dt"] <= end_ct)
        return out.loc[mask].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

@st.cache_data(ttl=300, show_spinner=False)
def compute_spx_asian_anchors(session_d: date) -> dict | None:
    """Find swing High/Low during 5–8 PM CT from ES=F, map to SPX levels."""
    start_ct, end_ct = asian_window_ct_for(session_d)
    es = yf_fetch_es1m_ct(start_ct, end_ct)
    if es.empty:
        return None
    es["SPX_High"] = es["High"].apply(es_to_spx)
    es["SPX_Low"]  = es["Low"].apply(es_to_spx)
    hi_idx = es["SPX_High"].idxmax()
    lo_idx = es["SPX_Low"].idxmin()
    return {
        "win_start": start_ct, "win_end": end_ct,
        "swing_high": float(es.loc[hi_idx, "SPX_High"]),
        "swing_high_time": es.loc[hi_idx, "Dt"].to_pydatetime(),
        "swing_low": float(es.loc[lo_idx, "SPX_Low"]),
        "swing_low_time": es.loc[lo_idx, "Dt"].to_pydatetime(),
        "source": "Yahoo ES=F",
    }

# ─────────────────────────────  SIDEBAR — NAV, ASSET, DATE, OVERNIGHT INPUTS  ─────────────────────────────
with st.sidebar:
    st.markdown("### 📚 Navigation")
    page = st.radio(label="", options=["Overview","Anchors","Forecasts","Signals","Contracts","Fibonacci","Export","Settings"],
                    index=0, label_visibility="collapsed")

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📈 Asset")
    asset = st.selectbox("Choose instrument", options=EQUITIES, index=0,
                         help="^GSPC = S&P 500 Index (displayed as SPX). Others are large-cap equities.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input("Target session", value=date.today(), help="Chooses the prior evening Asian window.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual)")
    on_low_price  = st.number_input("Overnight Low Price",  min_value=0.0, step=0.25, value=0.00)
    on_low_time   = st.time_input("Overnight Low Time (ET)",  value=time(21, 0))
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00)
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30))
    st.caption("Used later for the Overnight Entries tables.")
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────  HERO  ─────────────────────────────
label = "SPX" if asset == "^GSPC" else asset
live = fetch_live_quote(asset)

st.markdown(f"""
<div class="hero">
  <div class="glass"></div>
  <div class="content">
    <h1>{APP_NAME}</h1>
    <div class="sub">{TAGLINE}</div>
    <div class="meta">v{VERSION} • {COMPANY}</div>

    <div class="kpi">
      <div class="card"><div class="label">{label} — Last</div><div class="value">{live['px']}</div></div>
      <div class="card"><div class="label">As of</div><div class="value">{live['ts']}</div></div>
      <div class="card"><div class="label">Session</div><div class="value">{forecast_date.strftime('%a %b %d, %Y')}</div></div>
      <div class="card"><div class="label">Engine</div><div class="value"><span class="chip ok">{live['source']}</span></div></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────  OVERVIEW  ─────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
          <span class="chip ok">Yahoo: Connected</span>
          <span class="chip">Overnight inputs captured</span>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────  ANCHORS (ES→SPX, 5–8 PM CT)  ─────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Asian Session Anchors (SPX via ES, 5–8 PM CT)</h3>", unsafe_allow_html=True)

    anchors = compute_spx_asian_anchors(forecast_date)
    if not anchors:
        st.markdown('<div class="info">Could not compute anchors. Try a recent weekday and ensure ES=F data exists for 5–8 PM CT.</div>', unsafe_allow_html=True)
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Swing High (SPX est.)", f"{anchors['swing_high']:.2f}")
            st.caption(f"Time (CT): {anchors['swing_high_time'].strftime('%-I:%M %p')}")
        with c2:
            st.metric("Swing Low (SPX est.)", f"{anchors['swing_low']:.2f}")
            st.caption(f"Time (CT): {anchors['swing_low_time'].strftime('%-I:%M %p')}")
        st.caption(f"Window: {anchors['win_start'].strftime('%a %-I:%M %p')}–{anchors['win_end'].strftime('%-I:%M %p')} CT • Source: Yahoo ES=F")

    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────  PLACEHOLDERS (lit in Part 2+)  ─────────────────────────────
if page in {"Forecasts","Signals","Contracts","Fibonacci","Export","Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section lights up next with tables & entries (SPX lines + contract decay).")
    st.markdown('</div>', unsafe_allow_html=True)