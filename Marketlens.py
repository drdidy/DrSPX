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
import traceback  # Added for better error debugging

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
ES_SYMBOL = "ES=F"   # Fixed: Removed the ^ prefix - ES=F is the correct symbol

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
    """Enhanced error handling and debugging for live quotes."""
    try:
        # Debug: Show what we're fetching
        st.write(f"DEBUG: Attempting to fetch {symbol}")
        
        tkr = yf.Ticker(symbol)
        
        # Try 1-minute data first
        try:
            intraday = tkr.history(period="1d", interval="1m", prepost=True)
            st.write(f"DEBUG: Intraday data shape: {intraday.shape if not intraday.empty else 'Empty'}")
            st.write(f"DEBUG: Intraday columns: {list(intraday.columns) if not intraday.empty else 'N/A'}")
            
            if isinstance(intraday, pd.DataFrame) and not intraday.empty and "Close" in intraday.columns:
                last = intraday.iloc[-1]
                px = float(last["Close"])
                ts_idx = intraday.index[-1]
                
                # Better timezone handling
                if hasattr(ts_idx, 'tz') and ts_idx.tz is not None:
                    ts = pd.Timestamp(ts_idx).tz_convert(ET)
                else:
                    ts = pd.Timestamp(ts_idx).tz_localize("US/Eastern")
                
                return {
                    "px": f"{px:,.2f}", 
                    "ts": ts.strftime("%a %-I:%M %p ET"), 
                    "source": "Yahoo 1m"
                }
        except Exception as e:
            st.write(f"DEBUG: 1m data failed: {str(e)}")
        
        # Fallback to daily data
        try:
            daily = tkr.history(period="5d", interval="1d")  # Reduced period for faster fetch
            st.write(f"DEBUG: Daily data shape: {daily.shape if not daily.empty else 'Empty'}")
            
            if isinstance(daily, pd.DataFrame) and not daily.empty and "Close" in daily.columns:
                last = daily.iloc[-1]
                px = float(last["Close"])
                ts_idx = daily.index[-1]
                
                # Better timezone handling
                if hasattr(ts_idx, 'tz') and ts_idx.tz is not None:
                    ts = pd.Timestamp(ts_idx).tz_convert(ET)
                else:
                    ts = pd.Timestamp(ts_idx).tz_localize("US/Eastern")
                
                return {
                    "px": f"{px:,.2f}", 
                    "ts": ts.strftime("%a 4:00 PM ET"), 
                    "source": "Yahoo 1d"
                }
        except Exception as e:
            st.write(f"DEBUG: Daily data failed: {str(e)}")
            
    except Exception as e:
        st.write(f"DEBUG: Overall fetch failed for {symbol}: {str(e)}")
        st.write(f"DEBUG: Traceback: {traceback.format_exc()}")
    
    return {"px": "—", "ts": "—", "source": "Error"}

@st.cache_data(ttl=180, show_spinner=False)
def get_previous_day_anchors(symbol: str, forecast_d: date) -> dict | None:
    """Enhanced previous day anchors with better error handling."""
    try:
        prev_d = previous_trading_day(forecast_d)
        st.write(f"DEBUG: Getting anchors for {symbol} on {prev_d}")
        
        tkr = yf.Ticker(symbol)
        df = tkr.history(period="1mo", interval="1d")
        
        if df is None or df.empty:
            st.write("DEBUG: No historical data returned")
            return None
            
        st.write(f"DEBUG: Historical data shape: {df.shape}")
        st.write(f"DEBUG: Historical data date range: {df.index[0]} to {df.index[-1]}")
        
        # Simplified date handling
        df_dates = pd.to_datetime(df.index).date
        df = df.copy()
        df['_date'] = df_dates
        
        # Find the previous trading day
        matching_rows = df[df['_date'] == prev_d]
        if matching_rows.empty:
            # If exact date not found, use the most recent available
            st.write(f"DEBUG: Exact date {prev_d} not found, using most recent")
            row = df.iloc[-1]
            actual_date = df['_date'].iloc[-1]
        else:
            row = matching_rows.iloc[-1]
            actual_date = prev_d
            
        return {
            "prev_day": actual_date,
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"])
        }
        
    except Exception as e:
        st.write(f"DEBUG: Previous day anchors failed: {str(e)}")
        st.write(f"DEBUG: Traceback: {traceback.format_exc()}")
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
    Enhanced ES futures fetching with better error handling.
    """
    try:
        st.write(f"DEBUG: Fetching ES data from {start_ct} to {end_ct}")
        
        tkr = yf.Ticker(ES_SYMBOL)
        # Try different periods to ensure we get data
        for period in ["7d", "1mo", "3mo"]:
            try:
                raw = tkr.history(period=period, interval="15m", prepost=True)
                if raw is not None and not raw.empty:
                    break
                st.write(f"DEBUG: Period {period} returned empty data")
            except Exception as e:
                st.write(f"DEBUG: Period {period} failed: {str(e)}")
                continue
        else:
            st.write("DEBUG: All periods failed for ES data")
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
            
        st.write(f"DEBUG: ES raw data shape: {raw.shape}")
        
        df = raw.reset_index()
        
        # Handle different possible column names
        datetime_col = None
        for col in ["Datetime", "Date", "index"]:
            if col in df.columns:
                datetime_col = col
                break
                
        if datetime_col is None:
            st.write("DEBUG: No datetime column found in ES data")
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
            
        df = df.rename(columns={datetime_col: "Dt"})
        
        # Convert to datetime and timezone
        df["Dt"] = pd.to_datetime(df["Dt"])
        if df["Dt"].dt.tz is None:
            df["Dt"] = df["Dt"].dt.tz_localize("UTC")
        df["Dt"] = df["Dt"].dt.tz_convert(CT)
        
        # Filter columns and time window
        required_cols = ["Dt", "Open", "High", "Low", "Close"]
        df = df[required_cols].dropna()
        
        mask = (df["Dt"] >= start_ct) & (df["Dt"] <= end_ct)
        result = df.loc[mask].sort_values("Dt").reset_index(drop=True)
        
        st.write(f"DEBUG: Filtered ES data shape: {result.shape}")
        return result
        
    except Exception as e:
        st.write(f"DEBUG: ES fetch failed: {str(e)}")
        st.write(f"DEBUG: Traceback: {traceback.format_exc()}")
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

@st.cache_data(ttl=300, show_spinner=False)
def es_asian_anchors_as_spx(forecast_d: date) -> dict | None:
    """
    Compute Asian-session swing HIGH/LOW (5–8 PM CT) from ES and treat as SPX values (1:1 passthrough).
    """
    try:
        start_ct, end_ct = asian_window_ct(forecast_d)
        es = es_fetch_15m_ct(start_ct - timedelta(minutes=30), end_ct + timedelta(minutes=30))
        
        if es.empty:
            st.write("DEBUG: No ES data for Asian window")
            return None
            
        hi_idx = es["High"].idxmax()
        lo_idx = es["Low"].idxmin()
        
        return {
            "high_px": float(es.loc[hi_idx, "High"]),
            "high_time_ct": es.loc[hi_idx, "Dt"].to_pydatetime(),
            "low_px": float(es.loc[lo_idx, "Low"]),
            "low_time_ct": es.loc[lo_idx, "Dt"].to_pydatetime(),
        }
        
    except Exception as e:
        st.write(f"DEBUG: Asian anchors calculation failed: {str(e)}")
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

# Add debug toggle
with st.sidebar:
    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    debug_mode = st.checkbox("Enable Debug Mode", value=True, help="Show debug information for troubleshooting")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE STRIP  ───────────────────────────────
label = "SPX" if asset == "^GSPC" else asset

# Only show debug info if debug mode is enabled
if not debug_mode:
    # Temporarily disable debug prints
    import sys
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()

last = fetch_live_quote(asset)

if not debug_mode:
    sys.stdout = old_stdout

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

    if not debug_mode:
        old_stdout = sys.stdout
        sys.stdout = StringIO()

    anchors = get_previous_day_anchors(asset, forecast_date)
    asian = es_asian_anchors_as_spx(forecast_date)

    if not debug_mode:
        sys.stdout = old_stdout

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

    if not debug_mode:
        old_stdout = sys.stdout
        sys.stdout = StringIO()

    pd_anchors = get_previous_day_anchors(asset, forecast_date)

    if not debug_mode:
        sys.stdout = old_stdout

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

    if not debug_mode:
        old_stdout = sys.stdout
        sys.stdout = StringIO()

    asian = es_asian_anchors_as_spx(forecast_date)

    if not debug_mode:
        sys.stdout = old_stdout

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