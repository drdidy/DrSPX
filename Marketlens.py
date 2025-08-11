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





# ==============================  PART 2 — FORECAST TABLE (PREV-DAY LINES)  ==============================
# Builds on Part 1: projects descending lines from Prev Day H/C/L and computes TP1/TP2 (mirrored +slope).
# No new imports; uses Part 1's asset, forecast_date, get_previous_day_anchors, SPX_SLOPES, CT.

# ───────────────────────────────  INTERNAL UTILS (LOCAL TO PART 2)  ───────────────────────────────
def _ct_slots_30m(start_h=8, start_m=30, end_h=14, end_m=30):
    """Return list of 'HH:MM' CT time labels from 08:30 → 14:30 inclusive (30-min step)."""
    base = datetime(2000, 1, 1, start_h, start_m)  # dummy date, CT concept
    end  = datetime(2000, 1, 1, end_h,   end_m)
    out = []
    cur = base
    while cur <= end:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=30)
    return out

def _blocks_between(base_dt_ct: datetime, target_dt_ct: datetime) -> int:
    """Count 30-min blocks from base_dt_ct → target_dt_ct (floor)."""
    if target_dt_ct <= base_dt_ct:
        return 0
    mins = (target_dt_ct - base_dt_ct).total_seconds() / 60.0
    return int(mins // 30)

def _project_line(base_price: float, slope_per_block: float, blocks: int) -> float:
    return base_price + slope_per_block * blocks

def _prev_day_1600_et_dt(prev_day: date) -> datetime:
    """Anchor time for prev-day lines = 4:00 PM ET previous day, converted to CT."""
    base_et = datetime.combine(prev_day, time(16, 0), tzinfo=ET)
    return base_et.astimezone(CT)

# ───────────────────────────────  RENDER — FORECASTS PAGE (PREV-DAY LINES)  ───────────────────────────────
if page == "Forecasts":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Prev-Day Line Projections — Entries & Targets</h3>", unsafe_allow_html=True)

    anchors = get_previous_day_anchors(asset, forecast_date)
    if not anchors:
        st.info("Anchors not available yet. Choose a recent weekday or try again.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # Slope engine (hidden logic): use SPX slopes for now (works for any asset). 
        slope_dn = float(SPX_SLOPES["prev_high_down"])    # -0.2792 per 30m
        slope_up = float(SPX_SLOPES["tp_mirror_up"])      # +0.2792 per 30m
        abs_s    = abs(slope_up)

        # Target horizon selector (how far TP1/TP2 extend from the entry time)
        colA, colB = st.columns([1, 2])
        with colA:
            horizon_blocks = st.slider(
                "Target horizon (30-min blocks)",
                min_value=2, max_value=10, value=4, step=1,
                help="How far TP1/TP2 are projected from the entry time using the mirrored +slope."
            )
        with colB:
            st.caption("TP2 distance = slope × horizon blocks • TP1 = 50% of TP2")

        # Prepare schedule rows
        slots = _ct_slots_30m()
        base_dt_ct = _prev_day_1600_et_dt(anchors["prev_day"])

        rows = []
        for s in slots:
            hh, mm = map(int, s.split(":"))
            slot_dt_ct = datetime.combine(forecast_date, time(hh, mm), tzinfo=CT)
            b = _blocks_between(base_dt_ct, slot_dt_ct)

            # Entry lines (descending) from Prev Day anchors
            high_entry  = _project_line(anchors["high"],  slope_dn, b)
            close_entry = _project_line(anchors["close"], slope_dn, b)
            low_entry   = _project_line(anchors["low"],   slope_dn, b)

            # Targets: mirror (+slope) from the entry moment forward by horizon
            # Long-from-Low (upward targets)
            low_tp2  = low_entry  + abs_s * horizon_blocks
            low_tp1  = low_entry  + abs_s * (horizon_blocks / 2.0)

            # Short-from-High (downward targets)
            high_tp2 = high_entry - abs_s * horizon_blocks
            high_tp1 = high_entry - abs_s * (horizon_blocks / 2.0)

            # From Close, show both directions (balanced view)
            close_tp2_long = close_entry + abs_s * horizon_blocks
            close_tp1_long = close_entry + abs_s * (horizon_blocks / 2.0)
            close_tp2_short = close_entry - abs_s * horizon_blocks
            close_tp1_short = close_entry - abs_s * (horizon_blocks / 2.0)

            rows.append({
                "Time (CT)": s,

                "High Entry ↓": round(high_entry, 2),
                "High TP1":     round(high_tp1, 2),
                "High TP2":     round(high_tp2, 2),

                "Close Entry ↓": round(close_entry, 2),
                "Close TP1 ↑":   round(close_tp1_long, 2),
                "Close TP2 ↑":   round(close_tp2_long, 2),
                "Close TP1 ↓":   round(close_tp1_short, 2),
                "Close TP2 ↓":   round(close_tp2_short, 2),

                "Low Entry ↓":  round(low_entry, 2),
                "Low TP1 ↑":    round(low_tp1, 2),
                "Low TP2 ↑":    round(low_tp2, 2),
            })

        df = pd.DataFrame(rows)

        # Friendly label for header card
        label = "SPX500" if asset == "^GSPC" else asset

        # KPI mini-strip
        st.markdown(
            f"""
            <div class="kpi" style="margin-top:8px;">
              <div class="card">
                <div class="label">Instrument</div>
                <div class="value">{label}</div>
              </div>
              <div class="card">
                <div class="label">Prev Day (ET)</div>
                <div class="value">{anchors['prev_day'].strftime('%a %b %d, %Y')}</div>
              </div>
              <div class="card">
                <div class="label">Slope / 30m</div>
                <div class="value">−0.2792 ↘︎ / +0.2792 ↗︎</div>
              </div>
              <div class="card">
                <div class="label">Horizon</div>
                <div class="value">{horizon_blocks} blocks</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Dataframe (polished)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Time (CT)": st.column_config.TextColumn("Time (CT)", width="small"),

                "High Entry ↓": st.column_config.NumberColumn("High Entry ↓", format="%.2f", width="small"),
                "High TP1":     st.column_config.NumberColumn("High TP1",     format="%.2f", width="small"),
                "High TP2":     st.column_config.NumberColumn("High TP2",     format="%.2f", width="small"),

                "Close Entry ↓": st.column_config.NumberColumn("Close Entry ↓", format="%.2f", width="small"),
                "Close TP1 ↑":   st.column_config.NumberColumn("Close TP1 ↑",   format="%.2f", width="small"),
                "Close TP2 ↑":   st.column_config.NumberColumn("Close TP2 ↑",   format="%.2f", width="small"),
                "Close TP1 ↓":   st.column_config.NumberColumn("Close TP1 ↓",   format="%.2f", width="small"),
                "Close TP2 ↓":   st.column_config.NumberColumn("Close TP2 ↓",   format="%.2f", width="small"),

                "Low Entry ↓":  st.column_config.NumberColumn("Low Entry ↓",  format="%.2f", width="small"),
                "Low TP1 ↑":    st.column_config.NumberColumn("Low TP1 ↑",    format="%.2f", width="small"),
                "Low TP2 ↑":    st.column_config.NumberColumn("Low TP2 ↑",    format="%.2f", width="small"),
            }
        )

        # Subtle helper note
        st.caption(
            "Entries are descending lines from previous day High / Close / Low. "
            "TP1/TP2 are mirrored with equal and half magnitudes using +0.2792 per 30-minute block from the entry time. "
            "Schedule spans 08:30 → 14:30 CT."
        )

        st.markdown('</div>', unsafe_allow_html=True)
# ==============================  END PART 2  ==============================