# ==============================  PART 1 — CORE SHELL + PREMIUM UI + LIVE SPX + ANCHOR INPUTS  ==============================
# Enterprise UI, always-open sidebar, SPX from Yahoo Finance, hidden slope engine, overnight inputs (price+time)
# --------------------------------------------------------------------------------------------------------------
# Drop this in your main file (e.g., MarketLens.py). It runs on its own — no other parts needed yet.

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

# Market hours (SPX cash) in ET → converted in code as needed
RTH_START_ET, RTH_END_ET = time(9, 30), time(16, 0)
RTH_START_CT, RTH_END_CT = time(8, 30), time(15, 0)

# SPX core slopes (per 30-minute block) — WORKS IN BACKGROUND (not shown in UI)
# Previous-day anchors (descending from H/C/L; mirror ascending for TP)
SPX_SLOPES = {
    "prev_high_down": -0.2792,
    "prev_close_down": -0.2792,
    "prev_low_down": -0.2792,
    "tp_mirror_up": +0.2792,
}
# Overnight anchors (user inputs): low uses ascending; high uses descending
SPX_OVERNIGHT_SLOPES = {
    "overnight_low_up": +0.2792,
    "overnight_high_down": -0.2792,
}

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — SPX",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS (Bold, Uniform, 3D)  ───────────────────────────────
st.markdown("""
<style>
/* Fonts - lock to Inter for uniformity */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
html, body, .stApp * { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important; }

/* App background */
.stApp { 
  background: radial-gradient(1200px 600px at 10% -10%, #f6f9ff 0%, #ffffff 35%) no-repeat fixed;
}

/* Keep Streamlit header visible (no hiding) */

/* Hero */
.hero {
  border-radius: 22px;
  padding: 22px 24px;
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  border: 1px solid rgba(255,255,255,0.18);
  box-shadow:
    0 14px 30px rgba(99,102,241,0.28),
    inset 0 0 1px rgba(255,255,255,0.35);
}
.hero .title { font-weight: 800; font-size: 26px; letter-spacing: -0.02em; }
.hero .sub { opacity: 0.95; font-weight: 600; }
.hero .meta { opacity: 0.85; font-size: 12px; margin-top: 4px; }

/* KPI Grid - true 3D cards */
.kpi { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 14px; }
.kpi .card {
  border-radius: 16px; padding: 14px 16px; background: #ffffff;
  border: 1px solid rgba(15,23,42,0.06);
  box-shadow:
    0 12px 28px rgba(2,6,23,0.10),
    0 2px 6px rgba(2,6,23,0.08),
    inset 0 1px 0 rgba(255,255,255,0.8);
  transition: transform 180ms ease, box-shadow 180ms ease;
}
.kpi .card:hover { transform: translateY(-2px); box-shadow:
    0 18px 40px rgba(2,6,23,0.12),
    0 6px 12px rgba(2,6,23,0.10),
    inset 0 1px 0 rgba(255,255,255,0.9); }
.kpi .label { color: #64748b; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
.kpi .value { font-weight: 800; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }
.kpi .value.mono { font-variant-numeric: tabular-nums; }

/* Section card */
.sec {
  margin-top: 18px; border-radius: 20px; padding: 18px; background: #ffffff;
  border: 1px solid rgba(15,23,42,0.06);
  box-shadow:
    0 14px 36px rgba(2,6,23,0.10),
    0 2px 8px rgba(2,6,23,0.06),
    inset 0 1px 0 rgba(255,255,255,0.8);
}
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 800; letter-spacing: -0.01em; }

/* Sidebar (always open) */
section[data-testid="stSidebar"] {
  background: #0b1220 !important; color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label { color: #e5e7eb !important; }
.sidebar-card {
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px; margin: 12px 0;
}
.sidebar-card .hint { color: #cbd5e1; font-size: 12px; opacity: 0.9; }

/* Pills / Chips */
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(15,23,42,0.08); background:#f8fafc; font-size:12px; font-weight:800; color:#0f172a;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.9);
}
.chip.ok { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }

/* Table wrapper */
.table-wrap {
  border-radius: 16px; overflow: hidden; border: 1px solid rgba(15,23,42,0.06);
  box-shadow: 0 8px 24px rgba(2,6,23,0.08), inset 0 1px 0 rgba(255,255,255,0.9);
}

/* Top tabs look (for future use) */
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
  height: 42px; border-radius: 999px; padding: 0 16px; font-weight: 700;
  background: #f1f5f9; color:#0f172a; border: 1px solid rgba(15,23,42,0.06);
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%); color: #fff; border: none;
  box-shadow: 0 6px 18px rgba(99,102,241,0.25);
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS: YF FETCH + DATES  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_intraday_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Fetch 1m bars from Yahoo, return local CT timestamps with OHLC columns.
    Safe-guards against empty data and weekend gaps.
    """
    try:
        # Yahoo 1m works ~7 days back; fetch recent window and filter locally.
        df = yf.download(
            symbol,
            interval="1m",
            period="7d",
            auto_adjust=False,
            progress=False,
            prepost=True,
            threads=True,
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        df = df.reset_index()
        # yfinance returns "Datetime" (UTC tz-aware index) in recent versions
        ts_col = "Datetime" if "Datetime" in df.columns else ("index" if "index" in df.columns else None)
        if ts_col is None: 
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        df["Dt"] = pd.to_datetime(df[ts_col], utc=True).dt.tz_convert(CT)
        cols = [c for c in ["Open","High","Low","Close"] if c in df.columns]
        out = df[["Dt"] + cols].dropna(subset=cols).sort_values("Dt").reset_index(drop=True)
        mask = (out["Dt"] >= start_dt) & (out["Dt"] <= end_dt)
        return out.loc[mask].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

def previous_trading_day(ref_d: date) -> date:
    d = ref_d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def rth_window_et(d: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(d, RTH_START_ET, tzinfo=ET),
        datetime.combine(d, RTH_END_ET, tzinfo=ET),
    )

# ───────────────────────────────  CORE: PREV-DAY H/L/C (HIDDEN ENGINE)  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def prev_day_hlc_spx(ref_session: date) -> dict | None:
    """
    Compute Previous Day High / Low / Close for SPX (Yahoo ^GSPC) using 1m bars in ET RTH.
    Returns dict with values + ET timestamps. Gracefully returns None if data missing.
    """
    try:
        prev_d = previous_trading_day(ref_session)
        rth_s_et, rth_e_et = rth_window_et(prev_d)
        # Pull a local CT window slightly wider to be safe
        start_ct = rth_s_et.astimezone(CT) - timedelta(minutes=5)
        end_ct   = rth_e_et.astimezone(CT) + timedelta(minutes=5)
        df = yf_fetch_intraday_1m("^GSPC", start_ct, end_ct)
        if df.empty or not {"High","Low","Close"}.issubset(df.columns):
            return None

        # Convert to ET for “time of” displays
        dfe = df.copy()
        dfe["Dt_ET"] = dfe["Dt"].dt.tz_convert(ET)
        mask = (dfe["Dt_ET"].dt.time >= RTH_START_ET) & (dfe["Dt_ET"].dt.time <= RTH_END_ET)
        rth = dfe.loc[mask]
        if rth.empty: 
            return None

        hi_idx = rth["High"].idxmax()
        lo_idx = rth["Low"].idxmin()
        prev_high = float(rth.loc[hi_idx,"High"])
        prev_low  = float(rth.loc[lo_idx,"Low"])
        prev_close = float(rth["Close"].iloc[-1])
        hi_time_et = rth.loc[hi_idx,"Dt_ET"].to_pydatetime()
        lo_time_et = rth.loc[lo_idx,"Dt_ET"].to_pydatetime()
        close_time_et = rth["Dt_ET"].iloc[-1].to_pydatetime()

        return {
            "prev_day": prev_d,
            "high": prev_high,
            "low": prev_low,
            "close": prev_close,
            "high_time_et": hi_time_et,
            "low_time_et": lo_time_et,
            "close_time_et": close_time_et,
        }
    except Exception:
        return None

# ───────────────────────────────  LIVE PRICE (BANNER)  ───────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_last() -> dict:
    """
    Last SPX price (1m). On weekends/holidays, roll back to most recent weekday close.
    """
    # Try recent 12h first
    end_ct = datetime.now(tz=CT)
    start_ct = end_ct - timedelta(hours=12)
    df = yf_fetch_intraday_1m("^GSPC", start_ct, end_ct)
    if df.empty:
        # Fallback: last weekday RTH close
        d = datetime.now(tz=ET).date()
        tries = 0
        while tries < 7:
            d = previous_trading_day(d)
            r1, r2 = rth_window_et(d)
            sct, ect = r1.astimezone(CT), r2.astimezone(CT)
            dd = yf_fetch_intraday_1m("^GSPC", sct, ect)
            if not dd.empty:
                last = dd.iloc[-1]
                return {"px": f"{float(last['Close']):,.2f}", "ts": f"{d.strftime('%a %b %d')} Close"}
            tries += 1
        return {"px":"—","ts":"—"}
    last = df.iloc[-1]
    return {"px": f"{float(last['Close']):,.2f}", "ts": last["Dt"].strftime("%-I:%M %p CT")}

# ───────────────────────────────  SIDEBAR — NAV, DATE, ANCHOR INPUTS  ───────────────────────────────
with st.sidebar:
    st.markdown("### 📚 Navigation")
    page = st.radio(
        label="",
        options=["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input(
        "Target session",
        value=date.today(),
        help="RTH session to analyze (SPX 09:30–16:00 ET)."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Overnight Anchor Inputs (manual price + time) — used later for entries table
    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual)")
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Enter the overnight swing LOW price.")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="5:00 PM → 7:00 AM ET window.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Enter the overnight swing HIGH price.")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="5:00 PM → 7:00 AM ET window.")
    st.markdown('<div class="hint">These levels power the Overnight tab once you move there.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE BANNER  ───────────────────────────────
last = fetch_spx_last()
st.markdown("""
<div class="hero">
  <div class="title">MarketLens Pro</div>
  <div class="sub">Enterprise SPX & Equities Forecasting</div>
  <div class="meta">v%s • %s</div>
  <div class="kpi">
    <div class="card">
      <div class="label">SPX — Last</div>
      <div class="value mono">%s</div>
    </div>
    <div class="card">
      <div class="label">As of</div>
      <div class="value">%s</div>
    </div>
    <div class="card">
      <div class="label">Session</div>
      <div class="value">%s</div>
    </div>
    <div class="card">
      <div class="label">Engine</div>
      <div class="value"><span class="chip ok">Yahoo Finance • 1m</span></div>
    </div>
  </div>
</div>
""" % (
    VERSION, COMPANY,
    last['px'],
    last['ts'],
    forecast_date.strftime('%a %b %d, %Y')
), unsafe_allow_html=True)

# ───────────────────────────────  OVERVIEW  ───────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)

    anchors = prev_day_hlc_spx(forecast_date)
    ready_chip = '<span class="chip ok">Prev-Day H/L/C Ready</span>' if anchors else '<span class="chip info">Fetching recent data…</span>'

    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
            {ready_chip}
            <span class="chip info">Overnight inputs waiting</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ───────────────────────────────  ANCHORS (DISPLAY-ONLY PREVIEW)  ───────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Previous Day Anchors (SPX)</h3>", unsafe_allow_html=True)

    anchors = prev_day_hlc_spx(forecast_date)
    if not anchors:
        st.info("Could not compute anchors yet. Try a recent weekday (Yahoo 1-minute data availability can vary).")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Prev Day High", f"{anchors['high']:.2f}")
            st.caption(f"Time ET: {anchors['high_time_et'].strftime('%-I:%M %p')}")
        with col2:
            st.metric("Prev Day Close", f"{anchors['close']:.2f}")
            st.caption(f"Time ET: {anchors['close_time_et'].strftime('%-I:%M %p')}")
        with col3:
            st.metric("Prev Day Low", f"{anchors['low']:.2f}")
            st.caption(f"Time ET: {anchors['low_time_et'].strftime('%-I:%M %p')}")

        st.markdown(
            """
            <div class="table-wrap" style="margin-top:12px;">
              <div style="padding:12px 14px; color:#475569; font-size:13px;">
                These anchors power your entry projections internally (descending lines from H/C/L with mirrored TP lines).
                No configuration needed here — it’s automatic.
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDER PAGES (WILL LIGHT UP IN PARTS 2+)  ───────────────────────────────
if page in {"Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section will light up in the next parts with professional tables, detection, contract logic, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)