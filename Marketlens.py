# =============================== PART 1 — CORE BOOTSTRAP & ROBUST DATA ENGINE ===============================
# MarketLens Pro — Core shell, theme, sidebar, symbols, and resilient Yahoo fetch (ES futures integrated)
# ===========================================================================================================

from __future__ import annotations
import sys
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

# ─────────────────────────────── App Identity ───────────────────────────────
APP_NAME   = "MarketLens Pro"
COMPANY    = "Quantum Trading Systems"
VERSION    = "4.1.0"

# Primary instruments
ES_SYMBOL  = "ES=F"     # S&P 500 E-mini futures (CME) — used for anchors/lines
SPX_SYMBOL = "^GSPC"    # S&P 500 index — used for display/validation later (conversion hidden)

# Supported equities (for later parts — pages/tabs will use these)
EQUITY_SLOPES = {
    "TSLA": 0.1508, "NVDA": 0.0485, "AAPL": 0.0750,
    "MSFT": 0.17,   "AMZN": 0.03,   "GOOGL": 0.07,
    "META": 0.035,  "NFLX": 0.23,
}
EQUITY_LIST = list(EQUITY_SLOPES.keys())

# ─────────────────────────────── Time / Sessions ───────────────────────────────
ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# RTH for SPX-style sessions we show in UI (CT); ES trades nearly 24h, but we anchor to RTH windows later
RTH_START_CT = time(8, 30)
RTH_END_CT   = time(15, 0)

# Overnight window for user-entered highs/lows (ET)
ON_START_ET  = time(18, 0)  # 6:00 PM ET (5:00 PM CT) — futures evening reopen
ON_END_ET    = time(2, 0)   # 2:00 AM ET

# ─────────────────────────────── Streamlit Page Config ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────── Premium CSS (Apple / Tesla) ───────────────────────────────
APPLE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;600;700&display=swap');

:root{
  --primary:#007AFF; --primary-dark:#0056CC; --secondary:#5AC8FA;
  --success:#34C759; --warning:#FF9500; --error:#FF3B30; --neutral:#8B5CF6;
  --bg:#FFFFFF; --panel:#F2F2F7; --surface:#FFFFFF; --border:rgba(0,0,0,.08);
  --text:#000; --sub:#3C3C43; --muted:#8E8E93;
  --r:1rem; --r2:1.5rem; --pad:1.25rem; --shadow:0 10px 15px rgba(0,0,0,.08),0 4px 6px rgba(0,0,0,.05);
}

html,body,.stApp{font-family:'Inter',system-ui;background:linear-gradient(135deg,#fff 0%,#f7f7fb 100%);color:var(--text);}

#MainMenu, footer, header[data-testid="stHeader"]{display:none !important;}

.hero{
  background:linear-gradient(135deg,#171A20 0%,#2f343b 100%);
  color:#fff;border-radius:24px;padding:32px 28px;margin:8px 0 20px;border:1px solid rgba(255,255,255,.08);
  box-shadow:var(--shadow);position:relative;overflow:hidden;
}
.hero .t{font-size:28px;font-weight:800;letter-spacing:-.02em;margin-bottom:6px}
.hero .s{opacity:.8}
.badge{
  display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.08);
  padding:8px 12px;border-radius:999px;font-weight:600;margin-top:8px
}
.panel{
  background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:18px;margin:8px 0;box-shadow:var(--shadow);
}
.kpi{display:flex;gap:14px;flex-wrap:wrap}
.kpi .v{font:700 20px/1 'JetBrains Mono',monospace}
.kpi-item{padding:10px 14px;border-radius:12px;border:1px solid var(--border);background:#fff;min-width:170px}
.ok{color:var(--success)} .warn{color:var(--warning)} .err{color:var(--error)}
.nav-pill{
  display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 2px;
}
.nav-pill a{
  text-decoration:none;border:1px solid var(--border);background:#fff;padding:8px 12px;border-radius:12px;
  font-weight:600;color:#111;transition:.2s;
}
.nav-pill a:hover{transform:translateY(-2px);box-shadow:var(--shadow)}
.caption{color:var(--muted);font-size:12px}
hr{border:none;border-top:1px solid var(--border);margin:18px 0}
</style>
"""
st.markdown(APPLE_CSS, unsafe_allow_html=True)

# ─────────────────────────────── Robust Yahoo Fetch (Integrated Patch) ───────────────────────────────
@st.cache_data(ttl=180)
def yf_fetch_intraday(symbol: str, start_et: datetime, end_et: datetime) -> pd.DataFrame:
    """
    Robust intraday pull for futures/stocks:
      1) Try 1m period=7d
      2) Fallback 5m period=30d
      3) Fallback 15m period=60d
    Then filter to [start_et, end_et] in ET.
    Returns: Dt(ET), Open, High, Low, Close  (sorted)
    """
    attempts = [
        {"interval": "1m",  "period": "7d"},
        {"interval": "5m",  "period": "30d"},
        {"interval": "15m", "period": "60d"},
    ]
    for a in attempts:
        try:
            df = yf.download(
                symbol,
                period=a["period"],
                interval=a["interval"],
                auto_adjust=False,
                progress=False,
            )
            if df is None or df.empty:
                continue
            df = df.rename(columns=str.title)
            need = ["Open", "High", "Low", "Close"]
            if not set(need).issubset(df.columns):
                continue

            # Index -> ET
            idx = df.index
            if idx.tz is None:
                idx = idx.tz_localize("UTC")
            dt_et = idx.tz_convert(ET)
            df = df.copy()
            df["Dt"] = dt_et
            df = df.reset_index(drop=True)
            df = df.dropna(subset=need).sort_values("Dt")

            pad = timedelta(minutes=2)
            mask = (df["Dt"] >= (start_et - pad)) & (df["Dt"] <= (end_et + pad))
            clip = df.loc[mask, ["Dt"] + need].copy()
            if not clip.empty:
                st.caption(f"🔎 {symbol} {a['interval']} • period={a['period']} • rows={len(clip)}")
                return clip
        except Exception:
            continue

    st.caption(f"🔎 {symbol} — no intraday rows in the requested window (all fallbacks failed).")
    return pd.DataFrame()

# Lightweight helpers used later (kept here so Part 1 runs self-contained)
def _now_et() -> datetime:
    return datetime.now(tz=ET)

def et_on(d: date, t: time) -> datetime:
    return datetime.combine(d, t).replace(tzinfo=ET)

def ct_on(d: date, t: time) -> datetime:
    return datetime.combine(d, t).replace(tzinfo=CT)

@st.cache_data(ttl=120)
def latest_snapshot(symbol: str) -> dict:
    """Return a tiny snapshot so Overview is never empty."""
    end_et = _now_et()
    start_et = end_et - timedelta(hours=6)
    df = yf_fetch_intraday(symbol, start_et, end_et)
    if df.empty:
        return {"ok": False, "symbol": symbol}
    last = df.iloc[-1]
    return {
        "ok": True,
        "symbol": symbol,
        "dt": last["Dt"],
        "open": float(last["Open"]),
        "high": float(last["High"]),
        "low": float(last["Low"]),
        "close": float(last["Close"]),
        "rows": len(df),
    }

# ─────────────────────────────── Sidebar / Navigation ───────────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div class="panel" style="text-align:center">
            <div style="font-weight:800;font-size:18px;color:#111;">{APP_NAME}</div>
            <div class="caption">v{VERSION} • {COMPANY}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Session date picker (what session we are analyzing in the app)
    default_session = (date.today() if date.today().weekday() < 5 else date.today() - timedelta(days=(date.today().weekday()-4)))
    forecast_date = st.date_input("Target Session (CT)", value=default_session, help="Used by analysis tabs in later parts.")

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.markdown("#### Navigation")
    page = st.radio(
        label="",
        options=["Overview", "Anchors", "Forecasts", "Signals", "Contract", "Fibonacci", "Export", "Settings / About"],
        index=0,
        label_visibility="collapsed",
    )

# ─────────────────────────────── Hero Header ───────────────────────────────
st.markdown(
    f"""
    <div class="hero">
      <div class="t">{APP_NAME}</div>
      <div class="s">Professional SPX (via ES futures) & Equities Analytics</div>
      <div class="badge">ES data via Yahoo Finance • Robust 1m/5m/15m fallback</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ─────────────────────────────── Overview (always shows live info) ───────────────────────────────
if page == "Overview":
    snap = latest_snapshot(ES_SYMBOL)
    es_ok = snap.get("ok", False)

    status_class = "ok" if es_ok else "err"
    status_text = "Connected" if es_ok else "No data in window"

    st.markdown(
        f"""
        <div class="panel">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;">
            <div>
              <div style="font-weight:800;font-size:18px;">Market Data Connection</div>
              <div class="caption">Resilient ES fetch with interval fallbacks</div>
            </div>
            <div class="kpi">
              <div class="kpi-item"><div class="v {status_class}">{status_text}</div><div class="caption">Status</div></div>
              <div class="kpi-item"><div class="v">{ES_SYMBOL}</div><div class="caption">Instrument</div></div>
              <div class="kpi-item"><div class="v">{forecast_date.strftime('%a %b %d')}</div><div class="caption">Session (CT)</div></div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if es_ok:
        # Price strip
        st.markdown(
            f"""
            <div class="panel">
              <div style="display:flex;gap:16px;flex-wrap:wrap;">
                <div class="kpi-item"><div class="v">{snap['close']:.2f}</div><div class="caption">Last</div></div>
                <div class="kpi-item"><div class="v">{snap['high']:.2f}</div><div class="caption">High (window)</div></div>
                <div class="kpi-item"><div class="v">{snap['low']:.2f}</div><div class="caption">Low (window)</div></div>
                <div class="kpi-item"><div class="v">{snap['rows']}</div><div class="caption">Rows Pulled</div></div>
              </div>
              <div class="caption" style="margin-top:8px;">As of {snap['dt'].astimezone(ET).strftime('%Y-%m-%d %H:%M ET')}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div class="panel">
              <div class="warn" style="font-weight:700">Could not pull rows for ES=F in the last 6 hours.</div>
              <div class="caption">Yahoo sometimes holes intraday futures data on older days. Try today/yesterday. The app
              will still run; analysis tabs use the same robust loader in later parts.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ─────────────────────────────── Placeholders for other tabs (non-empty, no errors) ───────────────────────────────
def _placeholder_card(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="panel">
          <div style="font-weight:800;font-size:18px;margin-bottom:6px">{title}</div>
          <div class="caption">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

if page == "Anchors":
    _placeholder_card("Anchors", "This tab will compute Overnight High/Low (6pm–2am ET) and Previous-Day H/L/C from ES with your slope rules in Part 2+.")
elif page == "Forecasts":
    _placeholder_card("Forecast Lines", "Projections into RTH using user-selected slopes. Comes in Part 2+.")
elif page == "Signals":
    _placeholder_card("Signals", "Touch + confirmation logic and summaries arrive in Part 3.")
elif page == "Contract":
    _placeholder_card("Contract Line", "User-picked low pair slope tool appears in Part 3.")
elif page == "Fibonacci":
    _placeholder_card("Fibonacci", "Bounce tools and 0.786 confluence come in Part 3.")
elif page == "Export":
    _placeholder_card("Export Center", "ZIP/CSV exports for tables and summaries. Part 3.")
elif page == "Settings / About":
    st.markdown(
        f"""
        <div class="panel">
          <div style="font-weight:800;font-size:18px;margin-bottom:6px">Settings / About</div>
          <div class="caption">Version {VERSION} • {COMPANY}</div>
          <hr/>
          <div class="caption">Equities enabled: {", ".join(EQUITY_LIST)}</div>
          <div class="caption">RTH (CT): {RTH_START_CT.strftime('%H:%M')} – {RTH_END_CT.strftime('%H:%M')}</div>
          <div class="caption">Overnight (ET): {ON_START_ET.strftime('%H:%M')} – {ON_END_ET.strftime('%H:%M')}</div>
          <div class="caption">Data Source: Yahoo Finance (1m→5m→15m fallbacks)</div>
        </div>
        """,
        unsafe_allow_html=True
    )
# ===========================================================================================================
# End of PART 1
# ===========================================================================================================