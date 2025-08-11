# ==============================  PART 1 — CORE SHELL (SPX + STOCKS)  ==============================
# Enterprise-grade shell with premium UI, SPX + Equities modules, Yahoo Finance engine, and Overnight inputs for SPX.
# - Visible Streamlit header
# - Always-open sidebar with pro 3D nav (option-menu)
# - SPX prev-day H/L/C engine (hidden), overnight manual inputs (price+time)
# - Stocks module (AAPL, MSFT, AMZN, GOOGL, META, NVDA, TSLA, NFLX) with live last-price banners
# - Robust weekend/holiday fallback to most recent daily close
# --------------------------------------------------------------------------------------------------

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# Try premium nav; gracefully fallback to radio if not installed
try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except Exception:
    HAS_OPTION_MENU = False

# ───────────────────────────────  GLOBAL CONFIG  ───────────────────────────────
APP_NAME   = "MarketLens Pro"
TAGLINE    = "Enterprise SPX & Multi-Asset Forecasting"
VERSION    = "5.0"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# RTH (SPX cash) in ET
RTH_START_ET, RTH_END_ET = time(9, 30), time(16, 0)

# Slopes per 30-minute block (hidden engine)
SPX_SLOPES = {
    "prev_high_down": -0.2792,
    "prev_close_down": -0.2792,
    "prev_low_down":  -0.2792,
    "tp_mirror_up":   +0.2792,
}
SPX_OVERNIGHT_SLOPES = {
    "overnight_low_up":  +0.2792,  # entry up from ON low
    "overnight_high_down": -0.2792 # entry down from ON high
}

# Equities you requested
EQUITY_TICKERS = ["AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","NFLX"]

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM THEME (High-contrast, depth, 3D)  ───────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

.stApp {
  background:
    radial-gradient(1200px 600px at 0% -10%, #0ea5e933 0%, transparent 40%),
    linear-gradient(180deg, #0b1220 0%, #0b1220 220px, #0f172a 220px, #0f172a 100%);
}

/* Keep Streamlit header visible (only hide hamburger) */
#MainMenu { display:none !important; }

/* Sidebar: glass + depth */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(15,23,42,0.85) 0%, rgba(2,6,23,0.85) 100%) !important;
  backdrop-filter: blur(12px);
  border-right: 1px solid rgba(255,255,255,0.08);
  color: #e5e7eb !important;
}
section[data-testid="stSidebar"] * { color: #e5e7eb !important; }
.sidebar-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 16px; padding: 14px 14px; margin: 10px 0;
  box-shadow: 0 10px 30px rgba(0,0,0,0.25) inset, 0 8px 20px rgba(0,0,0,0.35);
}

/* Option-menu (3D nav) */
.nav-link {
  border-radius: 12px !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02)) !important;
  box-shadow: 0 2px 0 rgba(255,255,255,0.08) inset, 0 12px 24px rgba(0,0,0,0.25);
  margin: 4px 0;
  font-weight: 700 !important;
}
.nav-link.active, .nav-pills .show > .nav-link {
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%) !important;
  border-color: rgba(255,255,255,0.18) !important;
  box-shadow: 0 2px 0 rgba(255,255,255,0.18) inset, 0 18px 28px rgba(99,102,241,0.45);
}

/* Main hero card */
.hero {
  border-radius: 24px;
  padding: 22px 24px;
  border: 1px solid rgba(255,255,255,0.12);
  background:
    radial-gradient(800px 300px at 10% 0%, rgba(99,102,241,0.35), transparent 60%),
    linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 24px 64px rgba(99,102,241,0.35);
}
.hero .title { font-weight: 900; font-size: 28px; letter-spacing: -0.01em; }
.hero .sub { opacity: 0.95; font-weight: 600; }
.hero .meta { opacity: 0.85; font-size: 13px; margin-top: 6px; }

/* KPI strip (cards with depth) */
.kpi { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 14px; }
.kcard {
  border-radius: 16px; padding: 14px 16px;
  background: linear-gradient(180deg, #0b1220, #0b1323);
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: 0 8px 22px rgba(2,6,23,0.55), 0 1px 0 rgba(255,255,255,0.06) inset;
  color: #f8fafc;
}
.klabel { color: #cbd5e1; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
.kvalue { font-weight: 900; font-size: 22px; letter-spacing: -0.02em; }

/* Section card */
.sec {
  margin-top: 18px; border-radius: 20px; padding: 18px;
  background: linear-gradient(180deg, #0b1220, #0b1323);
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: 0 18px 40px rgba(2,6,23,0.55), 0 1px 0 rgba(255,255,255,0.06) inset;
  color: #e5e7eb;
}
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

/* Metrics on dark */
.css-1xarl3l, .css-10trblm { color: #e5e7eb !important; }

/* Dataframe wrapper */
.table-wrap {
  border-radius: 16px; overflow: hidden;
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: 0 18px 40px rgba(2,6,23,0.55), 0 1px 0 rgba(255,255,255,0.06) inset;
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS: YF FETCH + FALLBACKS  ───────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_intraday_1m(symbol: str) -> pd.DataFrame:
    """Latest ~7d of 1m OHLC in CT. Returns empty DF on failure."""
    try:
        df = yf.download(symbol, interval="1m", period="7d", auto_adjust=False, progress=False, prepost=True, threads=True)
        if df is None or df.empty:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        df = df.reset_index()
        # yfinance can return 'Datetime' index column — normalize
        if "Datetime" in df.columns:
            df.rename(columns={"Datetime":"Dt"}, inplace=True)
        elif "index" in df.columns and "Dt" not in df.columns:
            df.rename(columns={"index":"Dt"}, inplace=True)
        if "Dt" not in df.columns:
            return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])
        dt_utc = pd.to_datetime(df["Dt"], utc=True)
        df["Dt"] = dt_utc.dt.tz_convert(ET).dt.tz_convert(CT)
        cols = [c for c in ["Open","High","Low","Close"] if c in df.columns]
        return df[["Dt"] + cols].dropna(subset=cols).sort_values("Dt").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

def last_price_banner(symbol: str, label: str) -> dict:
    """
    Return banner dict {px, ts} using 1m if available; else most recent daily close.
    label only used for clarity; not shown.
    """
    try:
        intr = yf_fetch_intraday_1m(symbol)
        if not intr.empty:
            last = intr.iloc[-1]
            return {"px": f"{float(last['Close']):,.2f}", "ts": last["Dt"].strftime("%-I:%M %p %Z")}
        # fallback daily close (covers weekends/holidays)
        daily = yf.Ticker(symbol).history(period="10d", auto_adjust=False)
        if not daily.empty:
            idx = daily.index[-1]
            if getattr(idx, "tzinfo", None) is None:
                idx = pd.to_datetime(idx).tz_localize(ET)
            return {"px": f"{float(daily['Close'].iloc[-1]):,.2f}", "ts": idx.strftime("%a %b %d, %Y (Close)")}
        return {"px": "—", "ts": "—"}
    except Exception:
        return {"px": "—", "ts": "—"}

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

@st.cache_data(ttl=300, show_spinner=False)
def prev_day_hlc_spx(ref_session: date) -> dict | None:
    """Prev-day H/L/C for SPX (^GSPC), computed on ET RTH using 1m data."""
    try:
        prev_d = previous_trading_day(ref_session)
        start_et, end_et = rth_window_et(prev_d)
        # Pull broad 1m, then filter by ET RTH
        intr = yf_fetch_intraday_1m("^GSPC")
        if intr.empty:
            return None
        df = intr.copy()
        df["Dt_ET"] = df["Dt"].dt.tz_convert(ET)
        m = (df["Dt_ET"] >= start_et) & (df["Dt_ET"] <= end_et)
        rth = df.loc[m]
        if rth.empty:
            return None
        hi_ix, lo_ix = rth["High"].idxmax(), rth["Low"].idxmin()
        return {
            "prev_day": prev_d,
            "high": float(rth.loc[hi_ix,"High"]),
            "low": float(rth.loc[lo_ix,"Low"]),
            "close": float(rth["Close"].iloc[-1]),
            "high_time_et": rth.loc[hi_ix,"Dt_ET"].to_pydatetime(),
            "low_time_et": rth.loc[lo_ix,"Dt_ET"].to_pydatetime(),
            "close_time_et": rth["Dt_ET"].iloc[-1].to_pydatetime(),
        }
    except Exception:
        return None

# ───────────────────────────────  SIDEBAR — NAV, SESSION, INPUTS  ───────────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-card" style="display:flex;gap:12px;align-items:center;">
            <div style="width:10px;height:10px;border-radius:999px;background:linear-gradient(135deg,#22d3ee,#6366f1);box-shadow:0 0 0 4px rgba(99,102,241,.2)"></div>
            <div>
                <div style="font-weight:900;letter-spacing:.01em;">{APP_NAME}</div>
                <div style="opacity:.85;font-size:12px;">v{VERSION} • {COMPANY}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if HAS_OPTION_MENU:
        top_section = option_menu(
            None,
            ["SPX", "Equities"],
            icons=["activity","briefcase"],
            menu_icon="cast",
            default_index=0,
            orientation="vertical",
            styles={"nav-link": {"font-size":"14px","font-weight":"700"}}
        )
    else:
        st.markdown("### 📚 Navigation")
        top_section = st.radio("", ["SPX","Equities"], label_visibility="collapsed")

    # Session chooser
    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input(
        "Target session",
        value=date.today(),
        help="RTH session to analyze (SPX 09:30–16:00 ET)."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Sub-navigation & inputs per section
    if top_section == "SPX":
        if HAS_OPTION_MENU:
            spx_page = option_menu(
                "SPX",
                ["Overview", "Anchors", "Overnight", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
                icons=["speedometer","pin-map","moon","graph-up","target","layers","bezier","download","gear"],
                menu_icon="activity",
                default_index=0,
                orientation="vertical",
            )
        else:
            st.markdown("#### SPX Pages")
            spx_page = st.radio("", ["Overview","Anchors","Overnight","Forecasts","Signals","Contracts","Fibonacci","Export","Settings"], label_visibility="collapsed")

        # Overnight inputs (manual)
        st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
        st.markdown("#### 🌙 Overnight Anchors (Manual)")
        on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing LOW.")
        on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21,0), help="Between ~5:00 PM and 7:00 AM ET.")
        on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing HIGH.")
        on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22,30), help="Between ~5:00 PM and 7:00 AM ET.")
        st.caption("These levels will drive Overnight entries in the SPX module.")
        st.markdown('</div>', unsafe_allow_html=True)

    else:  # Equities
        if HAS_OPTION_MENU:
            eq_page = option_menu(
                "Equities",
                ["Overview","Anchors","Signals","Export","Settings"],
                icons=["speedometer","pin-map","target","download","gear"],
                menu_icon="briefcase",
                default_index=0,
                orientation="vertical",
            )
        else:
            st.markdown("#### Equities Pages")
            eq_page = st.radio("", ["Overview","Anchors","Signals","Export","Settings"], label_visibility="collapsed")

        st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
        st.markdown("#### 🎯 Ticker")
        sel_ticker = st.selectbox("Symbol", EQUITY_TICKERS, index=0)
        st.caption("Weekly channel method (Mon/Tue anchors) will power entries in upcoming parts.")
        st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + KPI BANNER  ───────────────────────────────
if 'top_section' not in locals():
    top_section = "SPX"

if top_section == "SPX":
    last = last_price_banner("^GSPC", "SPX")
    title = "SPX — S&P 500 Index"
    sub   = TAGLINE
else:
    last = last_price_banner(locals().get("sel_ticker","AAPL"), "Equity")
    title = f"Equities — {locals().get('sel_ticker','AAPL')}"
    sub   = "Professional Weekly Channel & Signal Engine"

st.markdown(f"""
<div class="hero">
  <div class="title">{title}</div>
  <div class="sub">{sub}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="kcard">
      <div class="klabel">Last</div>
      <div class="kvalue">{last['px']}</div>
    </div>
    <div class="kcard">
      <div class="klabel">As of</div>
      <div class="kvalue">{last['ts']}</div>
    </div>
    <div class="kcard">
      <div class="klabel">Session</div>
      <div class="kvalue">{forecast_date.strftime('%a %b %d, %Y')}</div>
    </div>
    <div class="kcard">
      <div class="klabel">Data Engine</div>
      <div class="kvalue">Yahoo Finance</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────  MAIN CONTENT  ───────────────────────────────
if top_section == "SPX":
    page = locals().get("spx_page","Overview")

    if page == "Overview":
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)
        anchors = prev_day_hlc_spx(forecast_date)
        chip = "✅ Prev-Day H/L/C Ready" if anchors else "ℹ️ Fetching recent data…"
        st.write(chip)
        st.markdown("</div>", unsafe_allow_html=True)

    if page == "Anchors":
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown("<h3>Previous Day Anchors (SPX)</h3>", unsafe_allow_html=True)
        anchors = prev_day_hlc_spx(forecast_date)
        if not anchors:
            st.info("Could not compute anchors yet. Try a recent weekday (Yahoo 1-minute availability can vary).")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Prev Day High", f"{anchors['high']:.2f}")
                st.caption(f"Time ET: {anchors['high_time_et'].strftime('%-I:%M %p')}")
            with c2:
                st.metric("Prev Day Close", f"{anchors['close']:.2f}")
                st.caption(f"Time ET: {anchors['close_time_et'].strftime('%-I:%M %p')}")
            with c3:
                st.metric("Prev Day Low", f"{anchors['low']:.2f}")
                st.caption(f"Time ET: {anchors['low_time_et'].strftime('%-I:%M %p')}")
            st.caption("Descending lines from H/C/L with mirrored TP lines run in the background.")
        st.markdown('</div>', unsafe_allow_html=True)

    if page == "Overnight":
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown("<h3>Overnight Anchors</h3>", unsafe_allow_html=True)
        st.write(
            f"- Low: **{locals().get('on_low_price',0):.2f}** @ **{locals().get('on_low_time',time(0,0)).strftime('%-I:%M %p ET')}**\n"
            f"- High: **{locals().get('on_high_price',0):.2f}** @ **{locals().get('on_high_time',time(0,0)).strftime('%-I:%M %p ET')}**"
        )
        st.caption("These levels will project entries from 08:30–14:30 CT using your slope rules in the next part.")
        st.markdown('</div>', unsafe_allow_html=True)

    if page in {"Forecasts","Signals","Contracts","Fibonacci","Export","Settings"}:
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
        st.caption("This section activates with full tables and visuals in Part 2+.")
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # EQUITIES MODULE
    page = locals().get("eq_page","Overview")
    if page == "Overview":
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown("<h3>Overview</h3>", unsafe_allow_html=True)
        st.write("Weekly channel method: Monday/Tuesday anchors → projected channel → touch entries & profit targets.")
        st.markdown('</div>', unsafe_allow_html=True)

    if page in {"Anchors","Signals","Export","Settings"}:
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
        st.caption("Detailed channel build, entries table, and exports arrive in Part 2+ for Equities.")
        st.markdown('</div>', unsafe_allow_html=True)