# ==============================  PART 1 — CORE SHELL (YOUR YFINANCE APPROACH)  ==============================
# Streamlit header visible • Always-open sidebar • SPX + equities
# Live strip via yf.Ticker(...).history(period="1d", interval="1m") with daily fallback
# Prev-day anchors via yf.Ticker(...).history(period="1mo", interval="1d")
# Overnight inputs (price+time) in sidebar • Mobile-polished 3D UI
# ------------------------------------------------------------------------------------------------------------

from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

# ───────────────────────────────  GLOBAL CONFIG  ───────────────────────────────
APP_NAME   = "MarketLens Pro"
TAGLINE    = "Enterprise SPX & Equities Forecasting"
VERSION    = "5.0"
COMPANY    = "Quantum Trading Systems"

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Slope engine placeholders (used in later parts; kept here to match your spec)
SPX_SLOPES = {"prev_high_down": -0.2792, "prev_close_down": -0.2792, "prev_low_down": -0.2792, "tp_mirror_up": +0.2792}
SPX_OVERNIGHT_SLOPES = {"overnight_low_up": +0.2792, "overnight_high_down": -0.2792}

# App instruments (you can add/remove freely)
EQUITIES = ["^GSPC", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "TSLA"]

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
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

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
    while d.weekday() >= 5:  # Sat/Sun
        d -= timedelta(days=1)
    return d

@st.cache_data(ttl=90, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """
    YOUR pattern: yf.Ticker(...).history(period='1d', interval='1m') for live,
    fallback to yf.Ticker(...).history(period='10d', interval='1d') for last close.
    """
    try:
        tkr = yf.Ticker(symbol)
        # Try intraday 1m (today)
        intraday = tkr.history(period="1d", interval="1m", prepost=True)
        if isinstance(intraday, pd.DataFrame) and not intraday.empty and "Close" in intraday.columns:
            last = intraday.iloc[-1]
            px = float(last["Close"])
            ts_idx = intraday.index[-1]
            # Ensure tz → ET
            if getattr(ts_idx, "tz", None) is None:
                ts = pd.Timestamp(ts_idx).tz_localize("UTC").tz_convert(ET)
            else:
                ts = pd.Timestamp(ts_idx).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a %-I:%M %p ET"), "source": "Yahoo 1m"}
        # Fallback to last daily close
        daily = tkr.history(period="10d", interval="1d")
        if isinstance(daily, pd.DataFrame) and not daily.empty and "Close" in daily.columns:
            last = daily.iloc[-1]
            px = float(last["Close"])
            ts_idx = daily.index[-1]
            if getattr(ts_idx, "tz", None) is None:
                ts = pd.Timestamp(ts_idx).tz_localize("UTC").tz_convert(ET)
            else:
                ts = pd.Timestamp(ts_idx).tz_convert(ET)
            return {"px": f"{px:,.2f}", "ts": ts.strftime("%a 4:00 PM ET"), "source": "Yahoo 1d"}
    except Exception:
        pass
    return {"px": "—", "ts": "—", "source": "—"}

@st.cache_data(ttl=300, show_spinner=False)
def get_previous_day_anchors(symbol: str, forecast_d: date) -> dict | None:
    """
    YOUR pattern: prev-day HIGH/CLOSE/LOW from daily candles.
    df = yf.Ticker(symbol).history(period='1mo', interval='1d')
    """
    try:
        prev_d = previous_trading_day(forecast_d)
        df = yf.Ticker(symbol).history(period="1mo", interval="1d")
        if df is None or df.empty:
            return None
        # Align index to ET date for matching
        idx = pd.Index(df.index)
        if getattr(idx[0], "tz", None) is None:
            dates_et = pd.to_datetime(idx).tz_localize("UTC").tz_convert(ET).date
        else:
            dates_et = pd.to_datetime(idx).tz_convert(ET).date
        df = df.assign(_d=list(dates_et))
        row = df[df["_d"] == prev_d]
        if row.empty:
            # conservative fallback to prior row
            row = df.iloc[[-2]] if len(df) >= 2 else df.iloc[[-1]]
            prev_d = row["_d"].iloc[-1]
        r = row.iloc[-1]
        return {
            "prev_day": prev_d,
            "high": float(r["High"]),
            "low": float(r["Low"]),
            "close": float(r["Close"]),
        }
    except Exception:
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
        help="^GSPC = S&P 500 Index (SPX). Others are large-cap equities."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 Session")
    forecast_date = st.date_input(
        "Target session",
        value=date.today(),
        help="Used for previous-day anchor selection."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Overnight Anchor Inputs (manual price + time) — used in later parts
    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.markdown("#### 🌙 Overnight Anchors (Manual)")
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing LOW price.")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Between 5:00 PM and 7:00 AM ET.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Overnight swing HIGH price.")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Between 5:00 PM and 7:00 AM ET.")
    st.caption("These will power the Overnight Entries table in later parts.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE STRIP (YOUR FETCH)  ───────────────────────────────
# Friendly labels
label = "SPX" if asset == "^GSPC" else asset
last = fetch_live_quote(asset)

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

    anchors = get_previous_day_anchors(asset, forecast_date)
    ready_chip = '<span class="chip ok">Prev-Day Anchors Ready</span>' if anchors else '<span class="chip info">Fetching daily data…</span>'

    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
            {ready_chip}
            <span class="chip info">Overnight inputs captured</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ───────────────────────────────  ANCHORS (DISPLAY)  ───────────────────────────────
if page == "Anchors":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Previous Day Anchors</h3>", unsafe_allow_html=True)

    anchors = get_previous_day_anchors(asset, forecast_date)
    if not anchors:
        st.info("Could not compute anchors yet. Try a recent weekday (Yahoo daily availability can vary).")
    else:
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Prev Day High", f"{anchors['high']:.2f}")
        with col2: st.metric("Prev Day Close", f"{anchors['close']:.2f}")
        with col3: st.metric("Prev Day Low",  f"{anchors['low']:.2f}")

        st.markdown(
            """
            <div class="table-wrap" style="margin-top:12px;">
              <div style="padding:12px 14px; color:#64748b; font-size:12px;">
                These anchors power your projections internally (descending lines from H/C/L with mirrored TP lines). 
                Nothing to configure here—fully automatic.
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDERS (LIGHT UP IN PARTS 2+)  ───────────────────────────────
if page in {"Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section will light up in the next parts with professional tables, detection, contract logic, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)






# ==============================  PART 2 — PREV-DAY PROJECTIONS (SPX + EQUITIES)  ==============================
# Clean, visible UI; uses your Part 1 helpers (no re-imports). 
# For the selected asset (SPX or any equity):
# - Pull prev-day High/Close/Low (daily candles from Part 1 helper)
# - For each anchor, create a descending entry line (−0.2792/30m) and mirrored TP lines (+0.2792/30m)
# - Project for 08:30–14:30 CT at 30-minute steps
# NOTE: We anchor all three lines at the prior session’s 4:00 PM ET close time (consistent with daily-only data).
# ----------------------------------------------------------------------------------------------------------------

def _ct_slots_30m(start_t=time(8,30), end_t=time(14,30)):
    slots = []
    cur = datetime.combine(date(2025,1,1), start_t).replace(tzinfo=CT)
    stop = datetime.combine(date(2025,1,1), end_t).replace(tzinfo=CT)
    while cur <= stop:
        slots.append(cur.time().strftime("%H:%M"))
        cur += timedelta(minutes=30)
    return slots

_SLOTS_CT = _ct_slots_30m()

def _blocks_between_30m(base_dt_ct: datetime, tgt_dt_ct: datetime) -> int:
    if tgt_dt_ct < base_dt_ct:
        base_dt_ct, tgt_dt_ct = tgt_dt_ct, base_dt_ct
    # count 30m hops
    blocks = 0
    cur = base_dt_ct.replace(second=0, microsecond=0)
    while cur < tgt_dt_ct:
        cur += timedelta(minutes=30)
        blocks += 1
    return blocks

def _project_price(base_price: float, base_dt_ct: datetime, tgt_dt_ct: datetime, slope_per_block: float) -> float:
    b = _blocks_between_30m(base_dt_ct, tgt_dt_ct)
    return round(base_price + slope_per_block * b, 2)

def _make_projection_table(prev: dict, session_d: date, slopes: dict) -> pd.DataFrame:
    """
    prev = {'prev_day', 'high','low','close'}
    Anchor time = previous day's 16:00 ET (15:00 CT), consistent with daily-only source.
    """
    # Base times (CT)
    base_ct = datetime.combine(prev["prev_day"], time(15,0)).replace(tzinfo=CT)

    # Slopes (from your Part 1 globals)
    s_down = slopes.get("prev_high_down", -0.2792)  # use same abs value for H/C/L
    s_up   = slopes.get("tp_mirror_up",  +0.2792)

    rows = []
    for slot in _SLOTS_CT:
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(session_d, time(h,m)).replace(tzinfo=CT)

        # From High (desc for entries; asc for TPs)
        ent_h  = _project_price(prev["high"],  base_ct, tgt, s_down)
        tp2_h  = _project_price(prev["high"],  base_ct, tgt, s_up)
        tp1_h  = round(ent_h + (tp2_h - ent_h)/2, 2)

        # From Close
        ent_c  = _project_price(prev["close"], base_ct, tgt, s_down)
        tp2_c  = _project_price(prev["close"], base_ct, tgt, s_up)
        tp1_c  = round(ent_c + (tp2_c - ent_c)/2, 2)

        # From Low
        ent_l  = _project_price(prev["low"],   base_ct, tgt, s_down)
        tp2_l  = _project_price(prev["low"],   base_ct, tgt, s_up)
        tp1_l  = round(ent_l + (tp2_l - ent_l)/2, 2)

        rows.append({
            "Time (CT)": slot,
            "High Entry ↓": ent_h, "High TP1": tp1_h, "High TP2 ↑": tp2_h,
            "Close Entry ↓": ent_c, "Close TP1": tp1_c, "Close TP2 ↑": tp2_c,
            "Low Entry ↓": ent_l,  "Low TP1": tp1_l,  "Low TP2 ↑": tp2_l,
        })
    return pd.DataFrame(rows)

# ----------  ANCHORS PAGE (VISIBLE FIXES) ----------
if page == "Anchors":
    st.markdown(
        '<div class="sec" style="color:#0f172a;">'
        '<h3 style="color:#0f172a;">Previous Day Anchors</h3>',
        unsafe_allow_html=True
    )
    prev = get_previous_day_anchors(asset, forecast_date)
    if not prev:
        st.info("Could not compute anchors yet. Try a recent weekday.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Prev Day High", f"{prev['high']:.2f}")
            st.caption(f"Date: {prev['prev_day']}")
        with c2:
            st.metric("Prev Day Close", f"{prev['close']:.2f}")
            st.caption(f"Date: {prev['prev_day']}")
        with c3:
            st.metric("Prev Day Low", f"{prev['low']:.2f}")
            st.caption(f"Date: {prev['prev_day']}")

        st.markdown(
            '<div class="table-wrap" style="margin-top:12px;">'
            '<div style="padding:12px 14px; color:#475569; font-size:12px;">'
            'Anchored at prior session’s <b>4:00 PM ET</b>. Lines descend from H/C/L with mirrored ascending TP lines.'
            '</div></div>',
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

# ----------  FORECASTS PAGE (PROJECTIONS TABLE) ----------
if page == "Forecasts":
    st.markdown(
        '<div class="sec" style="color:#0f172a;">'
        '<h3 style="color:#0f172a;">Previous Day Line Projection — Entries & Targets</h3>'
        '<div style="color:#475569;margin-bottom:10px;">'
        'Projections for 08:30–14:30 CT in 30-minute steps. Entry lines: <b>−0.2792</b> per 30m. TP lines: <b>+0.2792</b> (mirrored).'
        '</div>',
        unsafe_allow_html=True
    )

    prev = get_previous_day_anchors(asset, forecast_date)
    if not prev:
        st.info("No anchors available yet. Try a recent weekday.")
    else:
        table = _make_projection_table(prev, forecast_date, SPX_SLOPES)
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Time (CT)": st.column_config.TextColumn("Time (CT)", width="small"),
                "High Entry ↓":  st.column_config.NumberColumn(format="%.2f"),
                "High TP1":      st.column_config.NumberColumn(format="%.2f"),
                "High TP2 ↑":    st.column_config.NumberColumn(format="%.2f"),
                "Close Entry ↓": st.column_config.NumberColumn(format="%.2f"),
                "Close TP1":     st.column_config.NumberColumn(format="%.2f"),
                "Close TP2 ↑":   st.column_config.NumberColumn(format="%.2f"),
                "Low Entry ↓":   st.column_config.NumberColumn(format="%.2f"),
                "Low TP1":       st.column_config.NumberColumn(format="%.2f"),
                "Low TP2 ↑":     st.column_config.NumberColumn(format="%.2f"),
            }
        )

        st.markdown(
            '<div style="color:#475569;font-size:12px;margin-top:10px;">'
            'Note: Using daily candles, all three anchors use the prior session’s 4:00 PM ET timestamp for projection.'
            '</div>',
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)