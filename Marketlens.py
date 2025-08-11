# ─────────────────────────────────────────────────────────────────────────────
# ██████  PART 1 — APP SHELL, LAYOUT, NAV, SIDEBAR (MarketLens.py)
# ─────────────────────────────────────────────────────────────────────────────
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

# ===== App constants
APP_NAME = "MarketLens Pro"
COMPANY = "Quantum Trading Systems"
VERSION = "4.1.0"

# Timezones
CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

# Core symbols (SPX uses SPY for reliable minute data)
SPX_LABEL = "SPX (via SPY)"
SPX_YF = "SPY"
EQUITY_SYMBOLS = ["AAPL", "MSFT", "NVDA", "META", "TSLA", "AMZN", "GOOGL"]

# UI defaults
DEFAULT_TOLERANCE = 0.05  # dollars
RTH_START, RTH_END = time(8, 30), time(14, 30)  # CT

# ===== Streamlit page config
st.set_page_config(
    page_title=f"{APP_NAME} — Professional SPX & Equities Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# ██████  PART 2 — THEME / CSS & TOP HERO
# ─────────────────────────────────────────────────────────────────────────────
APPLE_MIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
:root{
  --primary:#007AFF; --secondary:#5AC8FA; --surface:#FFFFFF; --bg:#F2F2F7;
  --text:#0B0C0E; --muted:#6B7280; --border:rgba(0,0,0,0.08);
  --radius:16px; --space:16px;
}
html, body, .stApp{font-family:'Inter',system-ui,-apple-system,BlinkMacSystemFont,sans-serif;background:linear-gradient(135deg,#fff 0%,#f7f8fb 100%);}
#MainMenu, footer, header[data-testid="stHeader"]{display:none!important;}
.section{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;box-shadow:0 8px 24px rgba(0,0,0,.06);margin:12px 0;}
.section-title{font-weight:800;font-size:20px;border-bottom:2px solid var(--primary);padding-bottom:6px;margin-bottom:12px;}
.hero{background:linear-gradient(135deg,#111 0%,#2b2b2b 100%);color:#fff;border-radius:24px;padding:32px;margin-bottom:18px;border:1px solid rgba(255,255,255,.08);}
.kpi{display:flex;gap:18px;flex-wrap:wrap}
.kpi .tile{flex:1;min-width:180px;background:#fff;border:1px solid var(--border);border-radius:14px;padding:16px}
.small{color:var(--muted);font-size:12px}
.btn-primary button{background:linear-gradient(135deg,#007AFF,#0056CC)!important;color:#fff!important;border:none!important;border-radius:999px!important;}
</style>
"""
st.markdown(APPLE_MIN_CSS, unsafe_allow_html=True)

# Top hero
st.markdown(
    f"""
    <div class="hero">
      <div style="font-size:28px;font-weight:800;letter-spacing:-.02em;">{APP_NAME}</div>
      <div class="small">Professional SPX & Equities Analytics • v{VERSION} • {COMPANY}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# ██████  PART 3 — DATA ENGINE (YFINANCE 1-MIN), UTILITIES, DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
import yfinance as yf

def _ensure_recent_1m_window(start_dt_ct: datetime, end_dt_ct: datetime) -> tuple[datetime, datetime]:
    """
    Yahoo 1-minute data is only available for ~7 days.
    We clamp start to (now-6d) if older, and clamp end to now.
    """
    now_ct = datetime.now(tz=CT)
    if end_dt_ct > now_ct:
        end_dt_ct = now_ct
    seven_days_ago = now_ct - timedelta(days=6)
    if start_dt_ct < seven_days_ago:
        start_dt_ct = seven_days_ago
    if start_dt_ct >= end_dt_ct:
        start_dt_ct = end_dt_ct - timedelta(hours=6)
    return start_dt_ct, end_dt_ct

@st.cache_data(ttl=120)
def fetch_1m_yf(symbol: str, start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """
    Return 1-minute bars from Yahoo as a tidy DataFrame with:
      Dt(CT tz), Open, High, Low, Close
    """
    s_ct, e_ct = _ensure_recent_1m_window(start_dt_ct, end_dt_ct)

    # yfinance expects naive UTC OR aware; we'll pass UTC naive via tz_convert on index
    s_utc = s_ct.astimezone(timezone.utc)
    e_utc = e_ct.astimezone(timezone.utc)

    # Yahoo sometimes ignores start/end with 1m; using period='7d' then slicing locally is more reliable
    df = yf.download(symbol, interval="1m", period="7d", progress=False, auto_adjust=False)
    if df is None or df.empty:
        return pd.DataFrame(columns=["Dt", "Open", "High", "Low", "Close"])

    # Index to UTC, then to CT, filter by our window
    df = df.tz_localize(timezone.utc) if df.index.tz is None else df.tz_convert(timezone.utc)
    df = df.tz_convert(CT).reset_index().rename(columns={"index": "Dt"})
    if "Datetime" in df.columns:
        df.rename(columns={"Datetime": "Dt"}, inplace=True)

    df = df[(df["Dt"] >= s_ct) & (df["Dt"] <= e_ct)]
    if df.empty:
        return pd.DataFrame(columns=["Dt", "Open", "High", "Low", "Close"])

    return df[["Dt", "Open", "High", "Low", "Close"]].sort_values("Dt").reset_index(drop=True)

def make_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    cur = datetime(2025, 1, 1, start.hour, start.minute)
    stop = datetime(2025, 1, 1, end.hour, end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

SLOTS = make_slots(RTH_START, RTH_END)

# ===== Sidebar (instrument, nav, date, tolerance)
with st.sidebar:
    st.markdown('<div class="section-title">Instrument</div>', unsafe_allow_html=True)
    instrument = st.selectbox(
        "Select",
        [SPX_LABEL] + EQUITY_SYMBOLS,
        index=0,
        help="SPX uses SPY for reliable minute data",
    )

    st.markdown('<div class="section-title">Navigation</div>', unsafe_allow_html=True)
    nav = st.radio(
        "",
        ["Overview", "Anchors", "Forecasts", "Signals", "Contract", "Fibonacci", "Export", "Settings / About"],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown('<div class="section-title">Session</div>', unsafe_allow_html=True)
    # Default: next trading day (Mon-Fri)
    def _next_trading_day(d: date) -> date:
        wd = d.weekday()
        if wd < 4:
            return d + timedelta(days=1)
        # Fri → Mon
        return d + timedelta(days=(7 - wd))

    forecast_date = st.date_input(
        "Target Session",
        value=_next_trading_day(date.today()),
        help="Choose the session you want to analyze",
    )

    tolerance = st.slider("Touch Tolerance ($)", 0.01, 0.60, DEFAULT_TOLERANCE, 0.01)

# ===== Simple Overview content (kept minimal & professional)
if nav == "Overview":
    st.markdown('<div class="section"><div class="section-title">Overview</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Instrument", instrument)
    with col2:
        st.metric("Session", forecast_date.strftime("%a %b %d, %Y"))
    with col3:
        st.metric("Tolerance", f"±${tolerance:.2f}")
    st.markdown("</div>", unsafe_allow_html=True)

# ===== Diagnostics (useful immediately to validate data presence)
with st.expander("Diagnostics", expanded=False):
    diag_symbol = SPX_YF if instrument == SPX_LABEL else instrument
    st.write("Ticker used:", diag_symbol)
    # 3pm–6pm CT window to test if 5:00–5:29 CT exists
    start_diag = datetime.combine(forecast_date, time(15, 0), tzinfo=CT)
    end_diag = datetime.combine(forecast_date, time(18, 0), tzinfo=CT)
    try:
        df_diag = fetch_1m_yf(diag_symbol, start_diag, end_diag)
        st.write("Rows returned:", len(df_diag))
        if not df_diag.empty:
            st.dataframe(df_diag.tail(10), use_container_width=True)
            win = df_diag[
                (df_diag["Dt"].dt.time >= time(17, 0)) & (df_diag["Dt"].dt.time <= time(17, 29))
            ]
            st.write("5:00–5:29 CT rows:", len(win))
            if win.empty:
                st.info("No 5:00–5:29 CT rows for this date/ticker from Yahoo (normal for some dates).")
    except Exception as e:
        st.error(f"Diagnostics error: {e}")

# ===== Placeholder sections (will be fleshed out in later parts)
def _coming_soon(title: str):
    st.markdown(f'<div class="section"><div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.info("This section will activate in the next parts once anchors & projections are wired.")
    st.markdown("</div>", unsafe_allow_html=True)

if nav == "Anchors":
    _coming_soon("Anchors")
elif nav == "Forecasts":
    _coming_soon("Forecasts")
elif nav == "Signals":
    _coming_soon("Signals")
elif nav == "Contract":
    _coming_soon("Contract")
elif nav == "Fibonacci":
    _coming_soon("Fibonacci")
elif nav == "Export":
    _coming_soon("Export")
elif nav == "Settings / About":
    st.markdown('<div class="section"><div class="section-title">Settings / About</div>', unsafe_allow_html=True)
    st.write(f"**App:** {APP_NAME}  \n**Version:** {VERSION}  \n**Company:** {COMPANY}")
    st.markdown("</div>", unsafe_allow_html=True)

# ===========================================
# PART 4 — ES FUTURES DATA ENGINE (Yahoo)
# ===========================================
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf
import streamlit as st

CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

ES_SYMBOL = "ES=F"          # CME E-mini S&P 500 continuous
RTH_START, RTH_END = time(8,30), time(14,30)   # CT session window
SLOPE_UP_PER_BLOCK   = 0.3171   # 30m blocks slope from 5:00pm HIGH (ascending)
SLOPE_DOWN_PER_BLOCK = -0.3171  # 30m blocks slope from 5:00pm LOW  (descending)

def _ensure_tz(dt: datetime, tz=CT) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)

def _slots(start: time, end: time, step_min=30) -> list[str]:
    cur = datetime(2025,1,1,start.hour,start.minute)
    stop = datetime(2025,1,1,end.hour,end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

SPX_SLOTS_30M = _slots(RTH_START, RTH_END)

@st.cache_data(ttl=300, show_spinner=False)
def es_fetch_1m(start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """1m ES bars via Yahoo. Returns tz-aware CT index column 'Dt' and OHLCV."""
    start_dt_ct = _ensure_tz(start_dt_ct, CT)
    end_dt_ct   = _ensure_tz(end_dt_ct, CT)
    # Yahoo expects UTC; yfinance handles tz internally but returns tz-aware UTC index
    df = yf.download(
        tickers=ES_SYMBOL,
        interval="1m",
        start=start_dt_ct.astimezone(ET).tz_convert(None),
        end=end_dt_ct.astimezone(ET).tz_convert(None),
        prepost=True,
        auto_adjust=False,
        progress=False,
        threads=True
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns=str.title)
    df = df.reset_index().rename(columns={"Datetime":"Dt"})
    # Localize to CT
    df["Dt"] = pd.to_datetime(df["Dt"], utc=True).dt.tz_convert(CT)
    df = df[["Dt","Open","High","Low","Close","Volume"]].sort_values("Dt")
    return df

def _resample_30m_ct(df_1m: pd.DataFrame) -> pd.DataFrame:
    if df_1m.empty: 
        return pd.DataFrame()
    x = df_1m.set_index("Dt").sort_index()
    ohlc = x[["Open","High","Low","Close","Volume"]].resample("30min", label="right", closed="right").agg({
        "Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"
    }).dropna(subset=["Open","High","Low","Close"]).reset_index()
    ohlc["Time"] = ohlc["Dt"].dt.strftime("%H:%M")
    # RTH clip (still CT)
    ohlc = ohlc[(ohlc["Time"] >= RTH_START.strftime("%H:%M")) & (ohlc["Time"] <= RTH_END.strftime("%H:%M"))]
    return ohlc

@st.cache_data(ttl=300, show_spinner=False)
def es_fetch_day_30m(d: date) -> pd.DataFrame:
    """RTH 30m bars for target date in CT."""
    start_ct = datetime.combine(d, time(7,0), tzinfo=CT)
    end_ct   = datetime.combine(d, time(16,0), tzinfo=CT)
    df1m = es_fetch_1m(start_ct, end_ct)
    return _resample_30m_ct(df1m)

def _blocks_between_30m(a: datetime, b: datetime) -> int:
    """Inclusive 30-min steps count moving forward in time (CT)."""
    a = _ensure_tz(a, CT); b = _ensure_tz(b, CT)
    if b < a: a, b = b, a
    # Count boundary steps, not wall clock minutes
    blocks, cur = 0, a.replace(second=0, microsecond=0)
    # Move cur to next :00 or :30 boundary
    if cur.minute % 30 != 0:
        add = 30 - (cur.minute % 30)
        cur = cur + timedelta(minutes=add)
    while cur <= b:
        blocks += 1
        cur += timedelta(minutes=30)
    return max(blocks-1, 0)

def _project_from_anchor(base_price: float, base_time_ct: datetime, target_time_ct: datetime,
                         slope_per_block: float) -> float:
    return base_price + slope_per_block * _blocks_between_30m(base_time_ct, target_time_ct)

@st.cache_data(ttl=600, show_spinner=False)
def es_get_5pm_anchors(forecast: date) -> dict | None:
    """
    Find the 17:00–17:29 CT '5pm candle' that opens the evening SESSION for the forecast date.
    Anchors: use that bar's High (upper anchor) and Low (lower anchor), time set to 17:00 CT.
    Fallback to the previous calendar day if empty.
    """
    def _grab(day: date):
        win_start = datetime.combine(day, time(16,30), tzinfo=CT)
        win_end   = datetime.combine(day, time(17,30), tzinfo=CT)
        df = es_fetch_1m(win_start, win_end)
        if df.empty:
            return None
        # Slice rows in the 17:00…17:29 bucket
        df["HHMM"] = df["Dt"].dt.strftime("%H:%M")
        bucket = df[(df["HHMM"] >= "17:00") & (df["HHMM"] < "17:30")]
        if bucket.empty:
            return None
        hi, lo = float(bucket["High"].max()), float(bucket["Low"].min())
        base_t = datetime.combine(day, time(17,0), tzinfo=CT)
        return {"base_time": base_t, "upper_anchor": hi, "lower_anchor": lo}

    anchors = _grab(forecast)
    if anchors is None:
        anchors = _grab(forecast - timedelta(days=1))
    return anchors
