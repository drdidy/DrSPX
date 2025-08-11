# ==============================  PART 1 — CORE SHELL (SPX + STOCKS)  ==============================
# Enterprise UI, always-open sidebar, Yahoo Finance fetch with weekend/holiday fallback,
# hidden slope engine (not shown), overnight inputs (price+time) ready for Part 2+.
# ================================================================================================

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

# Market hours (SPX cash) in ET
RTH_START_ET, RTH_END_ET = time(9, 30), time(16, 0)
RTH_START_CT, RTH_END_CT = time(8, 30), time(15, 0)

# Default equities universe (you can change later)
EQUITY_LIST = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "NFLX"]

# SPX core slopes (per 30-minute block) — hidden engine (not shown in UI yet)
SPX_SLOPES = {
    "prev_high_down": -0.2792,
    "prev_close_down": -0.2792,
    "prev_low_down":  -0.2792,
    "tp_mirror_up":   +0.2792,
}
# Overnight anchors (user inputs): low uses ascending; high uses descending
SPX_OVERNIGHT_SLOPES = {
    "overnight_low_up":  +0.2792,
    "overnight_high_down": -0.2792,
}

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS (Bold, High-Contrast, Header Visible)  ───────────────────────────────
st.markdown("""
<style>
/* Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

/* Background */
.stApp { 
  background: radial-gradient(1200px 700px at 0% -10%, #eef4ff 0%, #ffffff 40%) fixed;
}

/* Keep Streamlit header visible (no hiding) */
#MainMenu { display: none !important; } /* menu only */

/* Brand Hero */
.hero {
  border-radius: 24px;
  padding: 20px 22px;
  border: 1px solid rgba(2,6,23,0.08);
  background: linear-gradient(135deg, #111827 0%, #1f2937 60%, #334155 100%);
  color: white;
  box-shadow: 0 16px 40px rgba(15,23,42,0.35);
}
.hero .title { font-weight: 900; font-size: 28px; letter-spacing: -0.02em; }
.hero .sub { opacity: 0.92; font-weight: 600; }
.hero .meta { opacity: 0.75; font-size: 13px; margin-top: 4px; }

/* KPI strip */
.kpi {
  display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 14px;
}
.kpi .card {
  border-radius: 16px; padding: 14px 16px;
  background: #0b1220; border: 1px solid rgba(255,255,255,0.08);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.03);
}
.kpi .label { color: #94a3b8; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }
.kpi .value { font-weight: 900; font-size: 22px; color: #ffffff; letter-spacing: -0.02em; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }

/* Light sections */
.sec { margin-top: 18px; border-radius: 20px; padding: 18px; background: #ffffff; border: 1px solid rgba(2,6,23,0.06); box-shadow: 0 10px 30px rgba(2,6,23,0.08); }
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

/* Sidebar premium */
section[data-testid="stSidebar"] {
  background: #0b1220 !important;
  color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
.sidebar-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 14px; padding: 12px 12px; margin: 10px 0;
}
section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] h4,
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p {
  color: #e5e7eb !important;
}
section[data-testid="stSidebar"] .stCheckbox > label, 
section[data-testid="stSidebar"] .stRadio > label { color: #e5e7eb !important; }

/* Chips */
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(0,0,0,0.08); background:#f8fafc; font-size:12px; font-weight:800; color:#0f172a;
}
.chip.ok { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }

/* Tables wrapper */
.table-wrap {
  border-radius: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 8px 24px rgba(2,6,23,0.05);
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  YAHOO HELPERS  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_intraday_1m(symbol: str, start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """
    Fetch 1m bars from Yahoo for last ~7d, local-filter to [start_dt_ct, end_dt_ct] in CT.
    Returns columns: Dt (tz-aware CT), Open/High/Low/Close.
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
        # yfinance uses "Datetime" or "index" depending on version
        if "Datetime" in df.columns:
            df.rename(columns={"Datetime": "Dt"}, inplace=True)
        elif "index" in df.columns:
            df.rename(columns={"index": "Dt"}, inplace=True)
        if "Dt" not in df.columns:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

        # Convert UTC -> ET -> CT (for display/filter)
        dt_utc = pd.to_datetime(df["Dt"], utc=True)
        df["Dt"] = dt_utc.dt.tz_convert(ET).dt.tz_convert(CT)

        cols = [c for c in ["Open","High","Low","Close"] if c in df.columns]
        out = df[["Dt"] + cols].dropna(subset=cols)
        mask = (out["Dt"] >= start_dt_ct) & (out["Dt"] <= end_dt_ct)
        return out.loc[mask].sort_values("Dt").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

@st.cache_data(ttl=90, show_spinner=False)
def fetch_last_quote(symbol: str) -> dict:
    """
    Get a robust "last" price for banner:
    - Try last 1m bar (6h window).
    - If none (weekend/holiday), fall back to last daily close within 10 days.
    """
    try:
        end_ct = datetime.now(tz=CT)
        start_ct = end_ct - timedelta(hours=6)
        intraday = yf_fetch_intraday_1m(symbol, start_ct, end_ct)
        if not intraday.empty:
            row = intraday.iloc[-1]
            return {"px": float(row["Close"]), "ts": row["Dt"].strftime("%-I:%M %p CT"), "source": "1m"}

        # Fallback to daily last close (last 10 days)
        hist = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False)
        if hist is not None and not hist.empty:
            last_row = hist.tail(1)
            px = float(last_row["Close"].iloc[0])
            # Use last market date in ET
            last_date = last_row.index[-1].to_pydatetime().replace(tzinfo=ZoneInfo("UTC")).astimezone(ET)
            ts = last_date.strftime("%a %b %d (Close) ET")
            return {"px": px, "ts": ts, "source": "1d-close"}

        return {"px": None, "ts": "—", "source": "—"}
    except Exception:
        return {"px": None, "ts": "—", "source": "—"}

# Prev trading day helper
def previous_trading_day(ref_d: date) -> date:
    d = ref_d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

# ───────────────────────────────  SIDEBAR — NAV, DATE, OVERNIGHT INPUTS  ───────────────────────────────
with st.sidebar:
    st.markdown("### 📚 Navigation")
    top_section = st.radio(
        label="",
        options=["SPX", "Equities"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )

    if top_section == "SPX":
        spx_page = st.radio("SPX Pages", ["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"], index=0)
    else:
        eq_page = st.radio("Equities Pages", ["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"], index=0)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input(
        "Target session",
        value=date.today(),
        help="RTH session in ET (09:30–16:00)."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if top_section == "SPX":
        st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
        st.markdown("#### 🌙 Overnight Anchors (Manual)")
        on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing LOW (price).")
        on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Between 5:00 PM and 7:00 AM ET.")
        on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing HIGH (price).")
        on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Between 5:00 PM and 7:00 AM ET.")
        st.caption("These feed the Overnight module in Part 2+. You can leave them blank for now.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
        st.markdown("#### 📈 Equity")
        eq_symbol = st.selectbox("Choose symbol", EQUITY_LIST, index=0)
        st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + KPI BANNER  ───────────────────────────────
if top_section == "SPX":
    last = fetch_last_quote("^GSPC")
    last_px = "—" if last["px"] is None else f"{last['px']:,.2f}"
    st.markdown(f"""
    <div class="hero">
      <div class="title">{APP_NAME}</div>
      <div class="sub">{TAGLINE}</div>
      <div class="meta">v{VERSION} • {COMPANY}</div>

      <div class="kpi">
        <div class="card">
          <div class="label">SPX — Last</div>
          <div class="value mono">{last_px}</div>
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
          <div class="value"><span class="chip ok">Yahoo Finance • {last['source']}</span></div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    last_eq = fetch_last_quote(eq_symbol)
    last_px = "—" if last_eq["px"] is None else f"{last_eq['px']:,.2f}"
    st.markdown(f"""
    <div class="hero">
      <div class="title">{APP_NAME}</div>
      <div class="sub">{TAGLINE}</div>
      <div class="meta">v{VERSION} • {COMPANY}</div>

      <div class="kpi">
        <div class="card">
          <div class="label">{eq_symbol} — Last</div>
          <div class="value mono">{last_px}</div>
        </div>
        <div class="card">
          <div class="label">As of</div>
          <div class="value">{last_eq['ts']}</div>
        </div>
        <div class="card">
          <div class="label">Session</div>
          <div class="value">{forecast_date.strftime('%a %b %d, %Y')}</div>
        </div>
        <div class="card">
          <div class="label">Engine</div>
          <div class="value"><span class="chip ok">Yahoo Finance • {last_eq['source']}</span></div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ───────────────────────────────  MAIN CONTENT PLACEHOLDERS (will light up in Part 2+)  ───────────────────────────────
if top_section == "SPX":
    page = locals().get("spx_page", "Overview")
    if page == "Overview":
        st.markdown('<div class="sec"><h3>SPX — Overview</h3>', unsafe_allow_html=True)
        st.markdown(
            "Enterprise shell ready. Prev-day anchors, projections, and detection tables arrive in **Part 2+**.",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="sec"><h3>SPX — {page}</h3>', unsafe_allow_html=True)
        st.info("This section will be activated in the next part.")
        st.markdown('</div>', unsafe_allow_html=True)
else:
    page = locals().get("eq_page", "Overview")
    if page == "Overview":
        st.markdown('<div class="sec"><h3>Equities — Overview</h3>', unsafe_allow_html=True)
        st.markdown(
            f"Selected symbol: **{eq_symbol}**. Weekly channel logic & entries will be enabled in **Part 2+**.",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="sec"><h3>Equities — {page}</h3>', unsafe_allow_html=True)
        st.info("This section will be activated in the next part.")
        st.markdown('</div>', unsafe_allow_html=True)