# ==============================  PART 1 — CORE SHELL + YF + TRADINGVIEW + SIGNALS (15m)  ==============================
# Enterprise shell, mobile-friendly, SPX shown as "SPX500" (uses ^GSPC under the hood), all equities supported.
# Includes: Live banner (last or fallback close), Prev-Day anchors, TradingView embed, 15m intraday signal detection.
# --------------------------------------------------------------------------------------------------------------

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
VERSION    = "5.1.1"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Display name → Yahoo Finance symbol
UNIVERSE = {
    "SPX500": "^GSPC",
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "AMZN": "AMZN",
    "GOOGL": "GOOGL",
    "META": "META",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "NFLX": "NFLX",
}

# TradingView mapping (best-effort)
TV_MAP = {
    "SPX500": "SP:SPX",        # alternatives: "CURRENCYCOM:US500", "OANDA:US500USD"
    "AAPL": "NASDAQ:AAPL",
    "MSFT": "NASDAQ:MSFT",
    "AMZN": "NASDAQ:AMZN",
    "GOOGL": "NASDAQ:GOOGL",
    "META": "NASDAQ:META",
    "NVDA": "NASDAQ:NVDA",
    "TSLA": "NASDAQ:TSLA",
    "NFLX": "NASDAQ:NFLX",
}

# Prev-day slopes (used in background)
SPX_SLOPE_PER_30M = -0.2792     # descending from prev H/C/L
TP_SLOPE_PER_30M  = +0.2792     # mirrored take-profit slope (ascending)

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS  ───────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

/* App bg */
.stApp { background: radial-gradient(1200px 600px at 10% -10%, #f8fbff 0%, #ffffff 35%) no-repeat fixed; }

/* Hero */
.hero {
  border-radius: 22px; padding: 20px 22px;
  border: 1px solid rgba(0,0,0,0.06);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white; box-shadow: 0 14px 36px rgba(99,102,241,.28);
}
.hero .title { font-weight: 900; font-size: 26px; letter-spacing: -0.02em; }
.hero .sub { opacity: .95; font-weight: 700; }
.hero .meta { opacity: .85; font-size: 12px; margin-top: 4px; }

/* KPI strip */
.kpi { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; margin-top: 14px; }
.kcard {
  border-radius: 16px; padding: 12px 14px; background: white;
  border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 8px 24px rgba(2,6,23,0.07);
}
.klabel { color: #6b7280; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }
.kvalue { font-weight: 900; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }

/* Section */
.sec {
  margin-top: 18px; border-radius: 20px; padding: 16px;
  background: white; border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 10px 32px rgba(2,6,23,0.06);
}
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #0b1220 !important; color: #e5e7eb; }
.sidebar-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px; margin: 10px 0;
}

/* Chips */
.chip { display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(0,0,0,0.08); background:#f8fafc; font-size:12px; font-weight:900; color:#0f172a; }
.chip.ok { background:#ecfdf5; border-color:#10b98133; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f133; color:#312e81; }

/* Table wrapper */
.table-wrap { border-radius: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 8px 24px rgba(2,6,23,0.05); }

/* Mobile tweaks */
@media (max-width: 768px) {
  .kpi { grid-template-columns: 1fr 1fr; }
  .hero .title { font-size: 22px; }
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  TIMEZONE HELPERS  ───────────────────────────────
def _to_ct_str(ts_like) -> str:
    """Robustly convert any timestamp (naive or tz-aware) to CT string."""
    try:
        ts = pd.to_datetime(ts_like)
        try:
            # If tz-aware, just convert
            ts = ts.tz_convert(CT)
        except Exception:
            # If tz-naive, assume UTC (Yahoo) then convert
            ts = ts.tz_localize("UTC").tz_convert(CT)
        return ts.strftime("%-I:%M %p CT")
    except Exception:
        return "—"

def _to_et_series(series) -> pd.Series:
    s = pd.to_datetime(series)
    try:
        return s.dt.tz_convert(ET)
    except Exception:
        return s.dt.tz_localize("UTC").dt.tz_convert(ET)

# ───────────────────────────────  HELPERS — YF  ───────────────────────────────
def _yf_hist(symbol: str, period: str, interval: str) -> pd.DataFrame:
    t = yf.Ticker(symbol)
    df = t.history(period=period, interval=interval, auto_adjust=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    # Normalize timestamp column
    if "Datetime" in df.columns:
        df.rename(columns={"Datetime":"Dt"}, inplace=True)
    elif "Date" in df.columns:
        df.rename(columns={"Date":"Dt"}, inplace=True)
    return df

@st.cache_data(ttl=60, show_spinner=False)
def fetch_live_strip(symbol_disp: str) -> dict:
    """Last price for banner; fallback to last daily close if intraday empty."""
    yfsym = UNIVERSE[symbol_disp]
    intraday = _yf_hist(yfsym, period="1d", interval="1m")
    if not intraday.empty and "Close" in intraday:
        last = intraday.iloc[-1]
        return {"price": float(last["Close"]), "asof": _to_ct_str(last["Dt"])}
    # fallback daily close
    daily = _yf_hist(yfsym, period="6mo", interval="1d")
    if not daily.empty and "Close" in daily:
        last = daily.iloc[-1]
        ts = _to_ct_str(last["Dt"])
        return {"price": float(last["Close"]), "asof": f"Last close • {ts}"}
    return {"price": None, "asof": "—"}

@st.cache_data(ttl=300, show_spinner=False)
def prev_day_anchors(symbol_disp: str, ref_session: date) -> dict | None:
    """Prev trading day H/L/C from daily bars."""
    yfsym = UNIVERSE[symbol_disp]
    daily = _yf_hist(yfsym, period="2mo", interval="1d")
    if daily.empty:
        return None
    daily["Dt"] = _to_et_series(daily["Dt"])
    daily["D"] = daily["Dt"].dt.date
    days = sorted(daily["D"].unique())
    prev_candidates = [d for d in days if d < ref_session]
    prev = prev_candidates[-1] if prev_candidates else days[-1]
    row = daily.loc[daily["D"]==prev].iloc[-1]
    return {"prev_day": prev, "high": float(row["High"]), "low": float(row["Low"]), "close": float(row["Close"])}

@st.cache_data(ttl=120, show_spinner=False)
def intraday_15m(symbol_disp: str) -> pd.DataFrame:
    """Recent 15m for signal detection (last 5d)."""
    yfsym = UNIVERSE[symbol_disp]
    df = _yf_hist(yfsym, period="5d", interval="15m")
    if df.empty: 
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
    df["Dt"] = _to_et_series(df["Dt"])
    return df[["Dt","Open","High","Low","Close"]].dropna()

# ───────────────────────────────  SIGNALS (15m)  ───────────────────────────────
def first_touch_table(df15: pd.DataFrame, anchors: dict, tol: float = 0.5) -> pd.DataFrame:
    """Detect first 15m candle that touches prev-day High / Low / Close (±tol)."""
    if df15.empty or not anchors:
        return pd.DataFrame(columns=["Line","Time (ET)","Close","Touched"])
    lines = {
        "Prev High": anchors["high"],
        "Prev Close": anchors["close"],
        "Prev Low": anchors["low"],
    }
    seen, rows = set(), []
    for _, r in df15.iterrows():
        lo, hi, cl = float(r["Low"]), float(r["High"]), float(r["Close"])
        t = r["Dt"]
        for name, lvl in lines.items():
            if name in seen:
                continue
            if (lo - tol) <= lvl <= (hi + tol):
                rows.append({"Line": name, "Time (ET)": t.strftime("%Y-%m-%d %H:%M"), "Close": round(cl, 2), "Touched": f"{lvl:.2f}"})
                seen.add(name)
        if len(seen) == 3:
            break
    return pd.DataFrame(rows)

# ───────────────────────────────  SIDEBAR  ───────────────────────────────
with st.sidebar:
    st.markdown("### 📚 Navigation")
    page = st.radio(
        label="",
        options=["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🎯 Instrument")
    asset = st.selectbox("Select Asset", list(UNIVERSE.keys()), index=0, help="SPX is shown as SPX500 (uses ^GSPC for data).")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input("Target session", value=date.today(), help="Used for prev-day anchor selection.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO  ───────────────────────────────
live = fetch_live_strip(asset)
last_px = "—" if live["price"] is None else f"{live['price']:,.2f}"
st.markdown(f"""
<div class="hero">
  <div class="title">{APP_NAME}</div>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="kcard">
      <div class="klabel">{asset} — Last</div>
      <div class="kvalue mono">{last_px}</div>
    </div>
    <div class="kcard">
      <div class="klabel">As of</div>
      <div class="kvalue">{live['asof']}</div>
    </div>
    <div class="kcard">
      <div class="klabel">Session</div>
      <div class="kvalue">{forecast_date.strftime('%a %b %d, %Y')}</div>
    </div>
    <div class="kcard">
      <div class="klabel">Engine</div>
      <div class="kvalue"><span class="chip ok">Yahoo Finance</span></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────  OVERVIEW — TRADINGVIEW  ───────────────────────────────
if page == "Overview":
    tv_symbol = TV_MAP.get(asset, "SP:SPX")
    st.markdown('<div class="sec"><h3>Live Chart</h3>', unsafe_allow_html=True)
    tv_html = f"""
    <div class="tradingview-widget-container" style="height:520px;">
      <div id="tv_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "container_id": "tv_chart",
          "symbol": "{tv_symbol}",
          "interval": "15",
          "timezone": "exchange",
          "theme": "light",
          "style": "1",
          "locale": "en",
          "enable_publishing": false,
          "hide_top_toolbar": false,
          "withdateranges": true,
          "allow_symbol_change": true,
          "details": false,
          "studies": [],
          "height": 520,
          "width": "100%"
        }});
      </script>
    </div>
    """
    st.components.v1.html(tv_html, height=540, scrolling=False)
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  ANCHORS  ───────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Previous Day Anchors</h3>", unsafe_allow_html=True)

    anchors = prev_day_anchors(asset, forecast_date)
    if not anchors:
        st.info("Could not compute anchors yet. Try a recent weekday.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Prev Day High", f"{anchors['high']:.2f}")
        with c2: st.metric("Prev Day Close", f"{anchors['close']:.2f}")
        with c3: st.metric("Prev Day Low", f"{anchors['low']:.2f}")
        st.caption("These anchors power intraday touch detection and projections behind the scenes.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  SIGNALS (15m Touch vs Prev H/L/C)  ───────────────────────────────
if page == "Signals":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Intraday Signals (15m)</h3>", unsafe_allow_html=True)

    anchors = prev_day_anchors(asset, forecast_date)
    df15 = intraday_15m(asset)
    if not df15.empty:
        df15["D"] = df15["Dt"].dt.date
        df_day = df15[df15["D"] == forecast_date].copy()
    else:
        df_day = pd.DataFrame()

    if df_day.empty or not anchors:
        st.info("No intraday 15m data for this session yet (or anchors unavailable). Try a recent trading day.")
    else:
        table = first_touch_table(df_day, anchors, tol=0.5)
        if table.empty:
            st.info("No touches detected yet (±$0.50 tolerance).")
        else:
            st.dataframe(
                table, hide_index=True, use_container_width=True,
                column_config={
                    "Line": st.column_config.TextColumn("Line"),
                    "Time (ET)": st.column_config.TextColumn("Time (ET)"),
                    "Close": st.column_config.NumberColumn("Close ($)", format="%.2f"),
                    "Touched": st.column_config.NumberColumn("Line Price ($)", format="%.2f"),
                }
            )
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDERS  ───────────────────────────────
if page in {"Forecasts", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section will light up in the next parts with pro tables, projections, contract logic, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)