# =============================== PART 1 — CORE BOOTSTRAP (SPX) + OVERNIGHT INPUTS ===============================
# MarketLens Pro — Beautiful shell, robust SPX fetch, sidebar nav, and Overnight High/Low input preview
# ===============================================================================================================

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

# ─────────────────────────────── App Identity ───────────────────────────────
APP_NAME   = "MarketLens Pro"
COMPANY    = "Quantum Trading Systems"
VERSION    = "4.1.0"

# Primary instrument (Yahoo Finance)
SPX_SYMBOL = "^GSPC"   # S&P 500 Index

# For later equities pages (not used yet in Part 1, just declared)
EQUITY_SLOPES = {
    "TSLA": 0.1508, "NVDA": 0.0485, "AAPL": 0.0750,
    "MSFT": 0.17,   "AMZN": 0.03,   "GOOGL": 0.07,
    "META": 0.035,  "NFLX": 0.23,
}
EQUITY_LIST = list(EQUITY_SLOPES.keys())

# ─────────────────────────────── Time / Sessions ───────────────────────────────
ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# RTH we display (CT, for SPX)
RTH_START_CT = time(8, 30)
RTH_END_CT   = time(15, 0)

# Overnight capture window (ET) — you’ll enter the time/price manually
ON_START_ET  = time(18, 0)  # 6:00 PM ET (5:00 PM CT)
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
  --r:.8rem; --r2:1.25rem; --pad:1.1rem; --shadow:0 10px 15px rgba(0,0,0,.08),0 4px 6px rgba(0,0,0,.05);
}

html,body,.stApp{font-family:'Inter',system-ui;background:linear-gradient(135deg,#fff 0%,#f7f7fb 100%);color:var(--text);}

#MainMenu, footer, header[data-testid="stHeader"]{display:none !important;}

.hero{
  background:linear-gradient(135deg,#171A20 0%,#2f343b 100%);
  color:#fff;border-radius:24px;padding:28px 24px;margin:10px 0 18px;border:1px solid rgba(255,255,255,.08);
  box-shadow:var(--shadow);position:relative;overflow:hidden;
}
.hero .t{font-size:26px;font-weight:800;letter-spacing:-.02em;margin-bottom:6px}
.hero .s{opacity:.85}
.badge{
  display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.08);
  padding:8px 12px;border-radius:999px;font-weight:600;margin-top:10px
}

.panel{
  background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:18px;margin:8px 0;box-shadow:var(--shadow);
}

.kpi{display:flex;gap:14px;flex-wrap:wrap}
.kpi-item{padding:10px 14px;border-radius:12px;border:1px solid var(--border);background:#fff;min-width:160px}
.kpi .v{font:700 20px/1 'JetBrains Mono',monospace}
.ok{color:var(--success)} .warn{color:var(--warning)} .err{color:var(--error)}

.nav-pill{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 2px;}
.nav-pill a{
  text-decoration:none;border:1px solid var(--border);background:#fff;padding:8px 12px;border-radius:12px;
  font-weight:600;color:#111;transition:.2s;
}
.nav-pill a:hover{transform:translateY(-2px);box-shadow:var(--shadow)}

.caption{color:var(--muted);font-size:12px}
hr{border:none;border-top:1px solid var(--border);margin:18px 0}
.small{font-size:12px;color:var(--sub)}
label[data-baseweb="checkbox"] > div{font-size:13px}
</style>
"""
st.markdown(APPLE_CSS, unsafe_allow_html=True)

# ─────────────────────────────── Helpers ───────────────────────────────
def _now_et() -> datetime:
    return datetime.now(tz=ET)

def et_on(d: date, t: time) -> datetime:
    return datetime.combine(d, t).replace(tzinfo=ET)

def ct_slots_30m(start_ct: time, end_ct: time) -> list[str]:
    """RTH slots in CT as HH:MM."""
    cur = datetime(2025,1,1,start_ct.hour,start_ct.minute)
    end = datetime(2025,1,1,end_ct.hour,end_ct.minute)
    out=[]
    while cur <= end:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=30)
    return out

RTH_SLOTS = ct_slots_30m(RTH_START_CT, RTH_END_CT)

# ─────────────────────────────── Robust Yahoo Fetch (SPX) ───────────────────────────────
@st.cache_data(ttl=180)
def yf_fetch_intraday_spx(start_et: datetime, end_et: datetime) -> pd.DataFrame:
    """
    Robust SPX pull:
      1) 1m, 7d
      2) 5m, 30d
      3) 15m, 60d
    Returns: Dt(ET), Open, High, Low, Close (sorted)
    """
    attempts = [
        {"interval": "1m",  "period": "7d"},
        {"interval": "5m",  "period": "30d"},
        {"interval": "15m", "period": "60d"},
    ]
    for a in attempts:
        try:
            df = yf.download(
                SPX_SYMBOL,
                period=a["period"],
                interval=a["interval"],
                auto_adjust=False,
                progress=False,
            )
            if df is None or df.empty:
                continue
            df = df.rename(columns=str.title)
            need = ["Open","High","Low","Close"]
            if not set(need).issubset(df.columns):
                continue

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
                st.caption(f"🔎 {SPX_SYMBOL} {a['interval']} • period={a['period']} • rows={len(clip)}")
                return clip
        except Exception:
            continue
    st.caption(f"🔎 {SPX_SYMBOL} — no rows in the requested window (all fallbacks tried).")
    return pd.DataFrame()

@st.cache_data(ttl=120)
def latest_snapshot_spx() -> dict:
    """Tiny snapshot so Overview is never empty."""
    end_et = _now_et()
    start_et = end_et - timedelta(hours=6)
    df = yf_fetch_intraday_spx(start_et, end_et)
    if df.empty:
        return {"ok": False}
    last = df.iloc[-1]
    return {
        "ok": True,
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

    # Session date (used throughout tabs)
    default_session = (date.today() if date.today().weekday() < 5 else date.today() - timedelta(days=(date.today().weekday()-4)))
    forecast_date = st.date_input("Target Session (CT)", value=default_session, help="Trading session you want to analyze.")

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
      <div class="s">Professional SPX analytics (Yahoo Finance • {SPX_SYMBOL})</div>
      <div class="badge">1m → 5m → 15m fallbacks • Clean, fast, reliable</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ─────────────────────────────── Overview (live info) ───────────────────────────────
if page == "Overview":
    snap = latest_snapshot_spx()
    status_class = "ok" if snap.get("ok") else "err"
    status_text  = "Connected" if snap.get("ok") else "No data in window"

    st.markdown(
        f"""
        <div class="panel">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;">
            <div>
              <div style="font-weight:800;font-size:18px;">Market Data Connection</div>
              <div class="caption">Resilient SPX intraday fetch with interval fallbacks</div>
            </div>
            <div class="kpi">
              <div class="kpi-item"><div class="v {status_class}">{status_text}</div><div class="caption">Status</div></div>
              <div class="kpi-item"><div class="v">{SPX_SYMBOL}</div><div class="caption">Instrument</div></div>
              <div class="kpi-item"><div class="v">{forecast_date.strftime('%a %b %d')}</div><div class="caption">Session (CT)</div></div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if snap.get("ok"):
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
              <div class="warn" style="font-weight:700">Could not pull rows for the last 6 hours.</div>
              <div class="caption">Try viewing during market hours or choose today/yesterday. The app still runs; other tabs use the same robust loader.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ─────────────────────────────── Anchors — Overnight Inputs (time + price) ───────────────────────────────
if page == "Anchors":
    st.markdown(
        """
        <div class="panel">
          <div style="font-weight:800;font-size:18px;margin-bottom:6px">⚓ SPX Overnight Anchors (Manual)</div>
          <div class="caption">Enter your Overnight High/Low (time & price). Overnight window reference: 6:00 PM – 2:00 AM ET.</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col_hi, col_lo = st.columns(2)

    with col_hi:
        st.markdown("**Overnight High**")
        on_high_time = st.time_input("Time (ET)", value=time(21, 0), key="on_high_time")
        on_high_price = st.number_input("Price ($)", min_value=0.0, value=5000.00, step=0.25, key="on_high_price", format="%.2f")

    with col_lo:
        st.markdown("**Overnight Low**")
        on_low_time = st.time_input("Time  (ET)", value=time(0, 30), key="on_low_time")
        on_low_price = st.number_input("Price  ($)", min_value=0.0, value=4950.00, step=0.25, key="on_low_price", format="%.2f")

    # Store to session for later parts (entries/detection will be built in Part 2)
    st.session_state["OVN_INPUTS"] = {
        "date": forecast_date,
        "high_time_et": on_high_time, "high_price": float(on_high_price),
        "low_time_et": on_low_time,   "low_price":  float(on_low_price),
    }

    # Pretty confirmation strip
    st.markdown(
        f"""
        <div class="panel">
          <div style="display:flex;gap:14px;flex-wrap:wrap">
            <div class="kpi-item">
              <div class="v">{on_high_price:.2f}</div>
              <div class="caption">ON High @ {on_high_time.strftime('%H:%M')} ET</div>
            </div>
            <div class="kpi-item">
              <div class="v">{on_low_price:.2f}</div>
              <div class="caption">ON Low  @ {on_low_time.strftime('%H:%M')} ET</div>
            </div>
            <div class="kpi-item">
              <div class="v">{forecast_date.strftime('%a %b %d')}</div>
              <div class="caption">Session (CT)</div>
            </div>
          </div>
          <div class="small" style="margin-top:8px">These anchors will power the entries table & projections in Part 2.</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Simple preview table: RTH 30-min slots with flat ON levels (projections/detections come in Part 2)
    preview = pd.DataFrame({
        "Time (CT)": RTH_SLOTS,
        "Overnight High ($)": [on_high_price for _ in RTH_SLOTS],
        "Overnight Low  ($)": [on_low_price  for _ in RTH_SLOTS],
    })
    st.markdown("### 📋 Preview — RTH Slots with Overnight Levels")
    st.dataframe(
        preview,
        use_container_width=True,
        hide_index=True
    )

# ─────────────────────────────── Placeholders for other tabs ───────────────────────────────
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

if page == "Forecasts":
    _placeholder_card("Forecast Lines", "We’ll generate RTH projections & entry logic from your anchors in Part 2.")
elif page == "Signals":
    _placeholder_card("Signals", "Touch/confirmation detection and summaries arrive in Part 3.")
elif page == "Contract":
    _placeholder_card("Contract Line", "User-picked low pair slope tool lands in Part 3.")
elif page == "Fibonacci":
    _placeholder_card("Fibonacci", "Bounce tools and 0.786 confluence in Part 3.")
elif page == "Export":
    _placeholder_card("Export Center", "ZIP/CSV exports for tables and summaries in Part 3.")
elif page == "Settings / About":
    st.markdown(
        f"""
        <div class="panel">
          <div style="font-weight:800;font-size:18px;margin-bottom:6px">Settings / About</div>
          <div class="caption">Version {VERSION} • {COMPANY}</div>
          <hr/>
          <div class="caption">Equities enabled: {", ".join(EQUITY_LIST)}</div>
          <div class="caption">SPX RTH (CT): {RTH_START_CT.strftime('%H:%M')} – {RTH_END_CT.strftime('%H:%M')}</div>
          <div class="caption">Overnight window (ET): {ON_START_ET.strftime('%H:%M')} – {ON_END_ET.strftime('%H:%M')}</div>
          <div class="caption">Data Source: Yahoo Finance (^GSPC) with interval fallbacks</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ===============================================================================================================
# End of PART 1
# ===============================================================================================================