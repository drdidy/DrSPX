# ==============================  PART 1 — CORE SHELL + LIVE SPX + ANCHOR INPUTS  ==============================
# Enterprise UI, always-open sidebar, SPX from Yahoo Finance, hidden slope engine, overnight inputs (price+time)
# --------------------------------------------------------------------------------------------------------------
# Drop this in your main file (e.g., MarketLens.py). It runs on its own — no other parts needed yet.

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

# ───────────────────────────────  GLOBAL CONFIG  ───────────────────────────────
APP_NAME   = "MarketLens Pro"
TAGLINE    = "Enterprise SPX & Equities Forecasting"
VERSION    = "5.0"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# SPX cash RTH in ET (displayed/filtered as needed)
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

# ───────────────────────────────  PREMIUM CSS (Clean, Bold, Product-Ready)  ───────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

.stApp { 
  background: radial-gradient(1200px 600px at 10% -10%, #f8fbff 0%, #ffffff 35%) no-repeat fixed;
}

/* Keep Streamlit header visible (do NOT hide) */
#MainMenu { display: none !important; }  /* OK to hide hamburger; header stays visible */

/* Brand Hero */
.hero {
  border-radius: 24px;
  padding: 22px 24px;
  border: 1px solid rgba(0,0,0,0.06);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 12px 30px rgba(99,102,241,0.25);
}
.hero .title { font-weight: 800; font-size: 26px; letter-spacing: -0.02em; }
.hero .sub { opacity: 0.95; font-weight: 500; }
.hero .meta { opacity: 0.8; font-size: 13px; margin-top: 4px; }

/* KPI strip */
.kpi {
  display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 14px;
}
.kpi .card {
  border-radius: 16px; padding: 14px 16px;
  background: white; border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 4px 16px rgba(2,6,23,0.05);
}
.kpi .label { color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.kpi .value { font-weight: 800; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }

/* Section */
.sec { margin-top: 18px; border-radius: 20px; padding: 18px; background: white; border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 8px 30px rgba(2,6,23,0.05); }
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 800; letter-spacing: -0.01em; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }

/* Sidebar polish */
section[data-testid="stSidebar"] {
  background: #0b1220 !important;
  color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label { color: #e5e7eb !important; }
.sidebar-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px 12px; margin: 10px 0;
}

/* Chips */
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(0,0,0,0.08); background:#f8fafc; font-size:12px; font-weight:700; color:#0f172a;
}
.chip.ok { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }

/* Table wrapper */
.table-wrap {
  border-radius: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 8px 24px rgba(2,6,23,0.05);
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS: YF FETCH + DATES  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_intraday_1m(symbol: str, start_dt: datetime | None = None, end_dt: datetime | None = None) -> pd.DataFrame:
    """
    Fetch 1m bars from Yahoo, return local CT timestamps with OHLC columns.
    Safe-guards against empty data and mixed columns. If no window is provided,
    returns the last ~7d then you can filter upstream.
    """
    try:
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
        # Normalize timestamp column name
        if "Datetime" in df.columns:
            df.rename(columns={"Datetime": "Dt"}, inplace=True)
        elif "index" in df.columns and "Dt" not in df.columns:
            df.rename(columns={"index": "Dt"}, inplace=True)

        if "Dt" not in df.columns:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

        dt_utc = pd.to_datetime(df["Dt"], utc=True)
        # Yahoo returns UTC → convert to ET then CT for display harmony
        df["Dt"] = dt_utc.dt.tz_convert(ET).dt.tz_convert(CT)

        cols = [c for c in ["Open","High","Low","Close"] if c in df.columns]
        out = df[["Dt"] + cols].dropna(subset=cols).sort_values("Dt").reset_index(drop=True)

        if start_dt is not None and end_dt is not None:
            mask = (out["Dt"] >= start_dt) & (out["Dt"] <= end_dt)
            out = out.loc[mask].reset_index(drop=True)

        return out
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

def to_ct(dt: datetime) -> datetime:
    return dt.astimezone(CT)

# ───────────────────────────────  CORE: PREV-DAY H/L/C (HIDDEN ENGINE)  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def prev_day_hlc_spx(ref_session: date) -> dict | None:
    """
    Compute Previous Day High / Low / Close for SPX (Yahoo ^GSPC) using 1m bars in ET RTH.
    Returns dict with values + ET timestamps. Gracefully returns None if data missing.
    """
    try:
        prev_d = previous_trading_day(ref_session)
        rth_s, rth_e = rth_window_et(prev_d)
        start_ct = to_ct(rth_s) - timedelta(minutes=5)
        end_ct   = to_ct(rth_e) + timedelta(minutes=5)
        df = yf_fetch_intraday_1m("^GSPC", start_ct, end_ct)
        if df.empty:
            return None

        # Constrain back to ET RTH for H/L/C calc
        df_et = df.copy()
        df_et["Dt_ET"] = df_et["Dt"].dt.tz_convert(ET)
        mask = (df_et["Dt_ET"].dt.time >= RTH_START_ET) & (df_et["Dt_ET"].dt.time <= RTH_END_ET)
        rth = df_et.loc[mask].copy()
        if rth.empty or not {"High","Low","Close"}.issubset(rth.columns):
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
def fetch_spx_last_banner() -> dict:
    """Last SPX price/time for the banner, with robust weekend/holiday fallback to most recent daily close."""
    try:
        # Try intraday first (last ~6h)
        end_ct = datetime.now(tz=CT)
        start_ct = end_ct - timedelta(hours=6)
        intraday = yf_fetch_intraday_1m("^GSPC", start_ct, end_ct)
        if not intraday.empty:
            last = intraday.iloc[-1]
            return {"px": f"{float(last['Close']):,.2f}", "ts": last["Dt"].strftime("%-I:%M %p %Z")}

        # Fallback: most recent daily close (covers weekends/holidays)
        daily = yf.Ticker("^GSPC").history(period="10d", auto_adjust=False)
        if not daily.empty:
            last_idx = daily.index[-1]
            # localize if tz-naive
            if getattr(last_idx, "tzinfo", None) is None:
                last_idx = pd.to_datetime(last_idx).tz_localize(ET)
            px = float(daily["Close"].iloc[-1])
            ts = last_idx.strftime("%a %b %d, %Y") + " (Close)"
            return {"px": f"{px:,.2f}", "ts": ts}

        return {"px": "—", "ts": "—"}
    except Exception:
        return {"px": "—", "ts": "—"}

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
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Pick a time between ~5:00 PM and 7:00 AM ET.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Enter the overnight swing HIGH price.")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Pick a time between ~5:00 PM and 7:00 AM ET.")
    st.caption("Tip: Leave blank for now — these drive the Overnight entries table in a later part.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE BANNER  ───────────────────────────────
last = fetch_spx_last_banner()
st.markdown(f"""
<div class="hero">
  <div class="title">{APP_NAME}</div>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="card">
      <div class="label">SPX — Last</div>
      <div class="value mono">{last['px']}</div>
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
      <div class="value"><span class="chip ok">Yahoo Finance</span></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────  OVERVIEW (LIGHT CONTENT, NO DEV NOISE)  ───────────────────────────────
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
            <div style="padding:12px 14px;">
              <div style="color:#6b7280;font-size:12px;">
                These anchors power your entry projections internally (descending lines from H/C/L with mirrored TP lines).
                Nothing to configure here — it’s automatic.
              </div>
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
    st.caption("This section will light up in the next parts with full professional tables, detection, contract logic, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)