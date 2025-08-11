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

# ─────────────────────────────────────────────────────────────────────────────
# ██████  PART 4 — SPX 5:00 CANDLE ANCHOR DETECTION (via SPY)
# ─────────────────────────────────────────────────────────────────────────────

def spx_get_5pm_candle(session_date: date) -> pd.DataFrame:
    """
    For the given forecast date, pull SPY minute data 3PM–6PM CT
    and extract rows for the 5:00–5:29 PM CT candle window.
    Returns DataFrame with Dt, Open, High, Low, Close.
    """
    start_pull = datetime.combine(session_date, time(15, 0), tzinfo=CT)
    end_pull = datetime.combine(session_date, time(18, 0), tzinfo=CT)
    df = fetch_1m_yf(SPX_YF, start_pull, end_pull)  # SPX_YF = "SPY"
    if df.empty:
        return pd.DataFrame(columns=["Dt", "Open", "High", "Low", "Close"])
    win = df[(df["Dt"].dt.time >= time(17, 0)) & (df["Dt"].dt.time <= time(17, 29))]
    return win.reset_index(drop=True)

def render_spx_anchors_page(session_date: date):
    """
    Renders the Anchors page with SPX 5:00–5:29 PM CT candle info.
    """
    st.markdown('<div class="section"><div class="section-title">⚓ SPX 5:00 Candle Anchors</div>', unsafe_allow_html=True)
    
    anchors_df = spx_get_5pm_candle(session_date)
    if anchors_df.empty:
        st.warning("No 5:00–5:29 PM CT data found for SPX (via SPY) on this date.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.dataframe(anchors_df, use_container_width=True)

    high_val = anchors_df["High"].max()
    low_val = anchors_df["Low"].min()
    st.metric("5PM High", f"{high_val:.2f}")
    st.metric("5PM Low", f"{low_val:.2f}")

    st.markdown("</div>", unsafe_allow_html=True)

# ===== Hook into nav
if nav == "Anchors":
    if instrument != SPX_LABEL:
        st.info("Anchors are only available for SPX.")
    else:
        render_spx_anchors_page(forecast_date)

# ─────────────────────────────────────────────────────────────────────────────
# ██████  PART 5 — FORECASTS PAGE (SPY Anchors → SPX Levels)
# ─────────────────────────────────────────────────────────────────────────────

def get_spx_open_ratio(session_date: date) -> float:
    """
    Returns SPX/SPY ratio at 8:30 AM CT open for the session_date.
    """
    start_dt = datetime.combine(session_date, time(8, 30), tzinfo=CT)
    end_dt = start_dt + timedelta(minutes=1)
    spy_df = fetch_1m_yf(SPX_YF, start_dt, end_dt)  # SPY
    spx_df = fetch_1m_yf("^GSPC", start_dt, end_dt)  # SPX index
    if spy_df.empty or spx_df.empty:
        return None
    spy_open = spy_df.iloc[0]["Open"]
    spx_open = spx_df.iloc[0]["Open"]
    return spx_open / spy_open if spy_open != 0 else None

def project_spx_levels_from_spy(anchor_price: float, slopes: list, ratio: float) -> pd.DataFrame:
    """
    Given a SPY anchor price, slopes (list of slope values), and SPX/SPY ratio,
    project SPX price targets (TP1, TP2).
    """
    data = []
    for slope in slopes:
        spy_proj = anchor_price + slope
        spx_proj = spy_proj * ratio
        data.append({
            "SPY Level": round(spy_proj, 2),
            "SPX Level": round(spx_proj, 2),
            "Slope": slope
        })
    return pd.DataFrame(data)

def render_spx_forecasts_page(session_date: date):
    """
    Render Forecasts page with SPX targets converted from SPY anchors.
    """
    st.markdown('<div class="section"><div class="section-title">📈 SPX Forecasts</div>', unsafe_allow_html=True)

    anchors_df = spx_get_5pm_candle(session_date)
    if anchors_df.empty:
        st.warning("No SPY 5:00 PM anchor found for forecasts.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    ratio = get_spx_open_ratio(session_date)
    if not ratio:
        st.error("Could not fetch SPX/SPY open ratio for conversion.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Example slope logic (replace with your actual strategy)
    high_anchor = anchors_df["High"].max()
    slopes = [0.3171, -0.3171]  # Example: up & down projections from high anchor

    forecast_df = project_spx_levels_from_spy(high_anchor, slopes, ratio)
    st.dataframe(forecast_df, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ===== Hook into nav
if nav == "Forecasts":
    if instrument != SPX_LABEL:
        st.info("Forecasts only available for SPX in this section.")
    else:
        render_spx_forecasts_page(forecast_date)

