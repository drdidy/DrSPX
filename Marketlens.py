# ==============================  PART 1 — CORE SHELL + PREMIUM UI + YF FALLBACK  ==============================
# Bold, enterprise styling • Always-open sidebar • SPX + 8 stocks • Live banner with 1m→daily fallback
# --------------------------------------------------------------------------------------------------------------
# Drop this in your main file (e.g., MarketLens.py). It runs by itself.

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

# Instrument universe (you can add later)
INSTRUMENTS = {
    "SPX (S&P 500 Index)": "^GSPC",
    "AAPL — Apple": "AAPL",
    "MSFT — Microsoft": "MSFT",
    "AMZN — Amazon": "AMZN",
    "GOOGL — Alphabet": "GOOGL",
    "META — Meta": "META",
    "NVDA — NVIDIA": "NVDA",
    "TSLA — Tesla": "TSLA",
    "NFLX — Netflix": "NFLX",
}

# ───────────────────────────────  PAGE SETUP  ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────  PREMIUM CSS (Bold, 3D, Uniform Fonts)  ───────────────────────────────
st.markdown(r"""
<style>
/* Typography */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, .stApp { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }

/* App background */
.stApp {
  background: radial-gradient(1200px 700px at 10% -10%, #f5f8ff 0%, #ffffff 40%) fixed;
}

/* Keep native Streamlit header visible (you asked to keep it) */

/* Hero (3D card) */
.hero {
  border-radius: 22px;
  padding: 20px 22px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
  color: white;
  box-shadow:
    0 14px 30px rgba(99, 102, 241, 0.28),
    inset 0 1px 0 rgba(255,255,255,0.25);
}
.hero .title { font-weight: 900; font-size: 26px; letter-spacing: -0.02em; }
.hero .sub { opacity: 0.95; font-weight: 600; }
.hero .meta { opacity: 0.85; font-size: 13px; margin-top: 4px; }

/* KPI cards — glossy, 3D */
.kpi {
  display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-top: 14px;
}
.kpi .card {
  border-radius: 16px; padding: 14px 16px;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0.9) 100%),
    #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow:
    0 10px 24px rgba(2,6,23,0.08),
    inset 0 1px 0 rgba(255,255,255,0.6);
  backdrop-filter: blur(6px);
}
.kpi .label { color: #64748b; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
.kpi .value { font-weight: 900; font-size: 22px; color: #0f172a; letter-spacing: -0.02em; }

/* Sections */
.sec {
  margin-top: 18px; border-radius: 18px; padding: 18px;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.6) 0%, rgba(255,255,255,0.95) 100%),
    #ffffff;
  border: 1px solid rgba(15,23,42,0.08);
  box-shadow: 0 12px 28px rgba(2,6,23,0.08), inset 0 1px 0 rgba(255,255,255,0.6);
}
.sec h3 { margin: 0 0 8px 0; font-size: 18px; font-weight: 900; letter-spacing: -0.01em; }

/* Sidebar (sleek dark) */
section[data-testid="stSidebar"] {
  background: #0b1220 !important;
  color: #e5e7eb;
  border-right: 1px solid rgba(255,255,255,0.06);
}
.sidebar-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px; padding: 12px 12px; margin: 10px 0;
}
.sidebar-card h4 { margin: 0 0 6px 0; font-weight: 800; color: #f3f4f6; }

/* Chips */
.chip {
  display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px;
  border:1px solid rgba(15, 23, 42, 0.08); background:#f8fafc; font-size:12px; font-weight:800; color:#0f172a;
}
.chip.ok { background:#ecfdf5; border-color:#10b98130; color:#065f46; }
.chip.info { background:#eef2ff; border-color:#6366f130; color:#312e81; }

/* Table wrapper */
.table-wrap {
  border-radius: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,0.06);
  box-shadow: 0 10px 26px rgba(2,6,23,0.08);
}

/* Buttons */
.stButton > button, .stDownloadButton > button {
  border-radius: 14px !important;
  border: 1px solid rgba(15,23,42,0.1) !important;
  background: linear-gradient(180deg, #0ea5e9 0%, #6366f1 100%) !important;
  color: #fff !important; font-weight: 800 !important;
  box-shadow: 0 10px 20px rgba(99,102,241,0.25), inset 0 1px 0 rgba(255,255,255,0.3) !important;
}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────  HELPERS: YF FETCH + FALLBACK  ───────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def yf_fetch_intraday_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Pull up to last 7 days 1-minute bars from Yahoo and filter locally by time range.
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
        # Normalize datetime column
        if "Datetime" in df.columns:
            df.rename(columns={"Datetime":"Dt"}, inplace=True)
        elif "index" in df.columns:
            df.rename(columns={"index":"Dt"}, inplace=True)
        else:
            # yfinance sometimes returns plain index as datetime
            df.rename(columns={df.columns[0]:"Dt"}, inplace=True)

        df["Dt"] = pd.to_datetime(df["Dt"], utc=True).dt.tz_convert(ET).dt.tz_convert(CT)
        cols = [c for c in ["Open","High","Low","Close"] if c in df.columns]
        out = df[["Dt"] + cols].dropna(subset=cols)
        mask = (out["Dt"] >= start_dt) & (out["Dt"] <= end_dt)
        return out.loc[mask].sort_values("Dt").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

@st.cache_data(ttl=600, show_spinner=False)
def yf_fetch_recent_daily_close(symbol: str) -> tuple[str,str] | None:
    """
    Fallback: pull up to 14 days of daily candles and return last close + date.
    Returns (price_str, date_str) or None.
    """
    try:
        df = yf.download(symbol, interval="1d", period="14d", auto_adjust=False, progress=False, threads=True)
        if df is None or df.empty:
            return None
        last = df.dropna(subset=["Close"]).iloc[-1]
        px = f"{float(last['Close']):,.2f}"
        dt = last.name
        if not isinstance(dt, pd.Timestamp):
            return (px, "—")
        dt = pd.to_datetime(dt).tz_localize("UTC").tz_convert(ET)
        ds = dt.strftime("%a %b %d")
        return (px, f"{ds} (Daily Close)")
    except Exception:
        return None

def get_last_with_fallback(symbol: str) -> dict:
    """
    Try intraday 1m last; if empty, fall back to most recent daily close.
    Returns {"px": str, "ts": str, "source": "1m"|"1d"}.
    """
    try:
        end_ct = datetime.now(tz=CT)
        start_ct = end_ct - timedelta(hours=8)
        m1 = yf_fetch_intraday_1m(symbol, start_ct, end_ct)
        if not m1.empty:
            last = m1.iloc[-1]
            return {"px": f"{float(last['Close']):,.2f}", "ts": last["Dt"].strftime("%-I:%M %p CT"), "source": "1m"}
        # fallback: daily close
        daily = yf_fetch_recent_daily_close(symbol)
        if daily:
            px, ds = daily
            return {"px": px, "ts": ds, "source": "1d"}
        return {"px": "—", "ts": "—", "source": "none"}
    except Exception:
        return {"px": "—", "ts": "—", "source": "error"}

# ───────────────────────────────  SIDEBAR — NAV + SESSION + OVERNIGHT INPUTS  ───────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-card"><h4>📚 Navigation</h4>', unsafe_allow_html=True)
    page = st.radio(
        label="",
        options=["Overview", "Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"],
        index=0,
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><h4>📊 Instrument</h4>', unsafe_allow_html=True)
    chosen_label = st.selectbox("Select", list(INSTRUMENTS.keys()), index=0, label_visibility="collapsed")
    SYMBOL = INSTRUMENTS[chosen_label]
    st.caption(f"Data source: Yahoo Finance • {chosen_label}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><h4>📅 Session</h4>', unsafe_allow_html=True)
    forecast_date = st.date_input("Target session", value=date.today())
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-card"><h4>🌙 Overnight Anchors (Manual)</h4>', unsafe_allow_html=True)
    on_low_price  = st.number_input("Overnight Low Price", min_value=0.0, step=0.25, value=0.00, help="Enter the overnight swing LOW price.")
    on_low_time   = st.time_input("Overnight Low Time (ET)", value=time(21, 0), help="Time between 5:00 PM and 7:00 AM ET.")
    on_high_price = st.number_input("Overnight High Price", min_value=0.0, step=0.25, value=0.00, help="Enter the overnight swing HIGH price.")
    on_high_time  = st.time_input("Overnight High Time (ET)", value=time(22, 30), help="Time between 5:00 PM and 7:00 AM ET.")
    st.caption("Tip: Overnight entries light up later; inputs are saved immediately.")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  HERO + LIVE BANNER  ───────────────────────────────
last = get_last_with_fallback(SYMBOL)
source_chip = '<span class="chip ok">Yahoo • 1m</span>' if last["source"] == "1m" else (
              '<span class="chip info">Yahoo • Daily Close</span>' if last["source"] == "1d" else
              '<span class="chip info">Awaiting data</span>')

st.markdown(f"""
<div class="hero">
  <div class="title">{APP_NAME}</div>
  <div class="sub">{TAGLINE}</div>
  <div class="meta">v{VERSION} • {COMPANY}</div>

  <div class="kpi">
    <div class="card">
      <div class="label">{chosen_label} — Last</div>
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
      <div class="value">{source_chip}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────  OVERVIEW (CLEAN; HEAVY LOGIC COMES IN PART 2+)  ───────────────────────────────
if page == "Overview":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>Readiness</h3>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
            <span class="chip ok">Live price ready</span>
            <span class="chip info">Prev-day anchors & entries load in Part 2+</span>
            <span class="chip info">Overnight inputs captured</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  PLACEHOLDER PAGES (TO BE FILLED IN PARTS 2+)  ───────────────────────────────
if page in {"Anchors", "Forecasts", "Signals", "Contracts", "Fibonacci", "Export", "Settings"}:
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown(f"<h3>{page}</h3>", unsafe_allow_html=True)
    st.caption("This section lights up in the next parts with your full strategy, premium tables, and exports.")
    st.markdown('</div>', unsafe_allow_html=True)



# ==============================  PART 2 — SPX PREV-DAY ANCHORS + ENTRY/TP TABLES  ==============================
# Uses Part 1's prev_day_hlc_spx() and styling. No header changes; no ES dependency.

# ───────────────────────────────  SLOPES  ───────────────────────────────
SLOPE_DOWN = -0.2792  # per 30-min block from Prev H/C/L
SLOPE_UP   = +0.2792  # mirror for TP projections

# ───────────────────────────────  TIME SLOTS (08:30–14:30 CT)  ───────────────────────────────
def ct_slots_30m(start: time = time(8,30), end: time = time(14,30)) -> list[datetime]:
    d = forecast_date  # from Part 1 (sidebar)
    cur = datetime.combine(d, start, tzinfo=CT)
    stop = datetime.combine(d, end, tzinfo=CT)
    out = []
    while cur <= stop:
        out.append(cur)
        cur += timedelta(minutes=30)
    return out

def to_et(dt_ct: datetime) -> datetime:
    return dt_ct.astimezone(ET)

# ───────────────────────────────  PROJECTION MATH  ───────────────────────────────
def blocks_between_30m(t0_et: datetime, t1_et: datetime) -> int:
    """Integer number of 30m steps between t0 and t1 (round toward zero)."""
    delta = (t1_et - t0_et).total_seconds()
    return int(delta // 1800)

def project_line(base_price: float, base_time_et: datetime, target_time_et: datetime, slope_per_block: float) -> float:
    return base_price + slope_per_block * blocks_between_30m(base_time_et, target_time_et)

def mirror_tp(entry_line_px: float, asc_line_px: float) -> tuple[float, float]:
    """TP2 = asc_line_px; TP1 = midpoint between entry and TP2."""
    tp2 = asc_line_px
    tp1 = entry_line_px + (tp2 - entry_line_px) * 0.5
    return round(tp1, 2), round(tp2, 2)

# ───────────────────────────────  BUILD SPX ENTRY TABLE  ───────────────────────────────
def build_spx_prevday_entry_table(target_session: date) -> tuple[pd.DataFrame, dict] | tuple[None, None]:
    """
    For each 30-min slot in 08:30–14:30 CT:
      - draw descending lines from Prev High / Close / Low (slope -0.2792)
      - mirror with ascending +0.2792 for TP targets (same base time/price)
    """
    anchors = prev_day_hlc_spx(target_session)
    if not anchors:
        return None, None

    # Base points (ET timestamps from prev_day_hlc_spx)
    base = {
        "HIGH": (anchors["high"], anchors["high_time_et"]),
        "CLOSE": (anchors["close"], anchors["close_time_et"]),
        "LOW": (anchors["low"], anchors["low_time_et"]),
    }

    rows = []
    for t_ct in ct_slots_30m():
        t_et = to_et(t_ct)
        # For each anchor, compute descending entry & ascending mirror
        rec = {"Time (CT)": t_ct.strftime("%H:%M")}
        for key, (px0, t0_et) in base.items():
            entry = project_line(px0, t0_et, t_et, SLOPE_DOWN)
            asc   = project_line(px0, t0_et, t_et, SLOPE_UP)
            tp1, tp2 = mirror_tp(entry, asc)
            rec[f"{key} Entry"] = round(entry, 2)
            rec[f"{key} TP1"]   = tp1
            rec[f"{key} TP2"]   = tp2
        rows.append(rec)

    df = pd.DataFrame(rows)
    meta = {
        "prev_day": anchors["prev_day"],
        "high": anchors["high"],
        "low": anchors["low"],
        "close": anchors["close"],
        "high_t": anchors["high_time_et"].strftime("%-I:%M %p ET"),
        "low_t": anchors["low_time_et"].strftime("%-I:%M %p ET"),
        "close_t": anchors["close_time_et"].strftime("%-I:%M %p ET"),
        "slopes": {"down": SLOPE_DOWN, "up": SLOPE_UP},
    }
    return df, meta

# ───────────────────────────────  ANCHORS PAGE (fills the placeholder)  ───────────────────────────────
if page == "Anchors":
    if SYMBOL != "^GSPC":
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown("<h3>Previous Day Anchors</h3>", unsafe_allow_html=True)
        st.info("Select **SPX (S&P 500 Index)** in the sidebar to view SPX anchor tiles and projections. "
                "Equities anchor channels land in upcoming parts.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown("<h3>SPX — Previous Day Anchors</h3>", unsafe_allow_html=True)

        anchors = prev_day_hlc_spx(forecast_date)
        if not anchors:
            st.info("Could not compute anchors yet. Try a recent weekday — Yahoo 1-minute RTH can be patchy over long ranges.")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Prev Day High", f"{anchors['high']:.2f}")
                st.caption(f"Time: {anchors['high_time_et'].strftime('%-I:%M %p ET')}")
            with c2:
                st.metric("Prev Day Close", f"{anchors['close']:.2f}")
                st.caption(f"Time: {anchors['close_time_et'].strftime('%-I:%M %p ET')}")
            with c3:
                st.metric("Prev Day Low", f"{anchors['low']:.2f}")
                st.caption(f"Time: {anchors['low_time_et'].strftime('%-I:%M %p ET')}")

            st.caption(f"Session used: {anchors['prev_day'].strftime('%a %b %d, %Y')} • Slopes run in background (per 30-min).")
            st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────────  FORECASTS PAGE (SPX entries & TPs table)  ───────────────────────────────
if page == "Forecasts":
    if SYMBOL != "^GSPC":
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown("<h3>SPX Entry Projections</h3>", unsafe_allow_html=True)
        st.info("Switch to **SPX (S&P 500 Index)** in the sidebar to view the projection table. "
                "Equities (AAPL, MSFT, NVDA, …) arrive next.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="sec">', unsafe_allow_html=True)
        st.markdown("<h3>SPX Entry & TP Projections (Prev Day H/C/L)</h3>", unsafe_allow_html=True)

        table, meta = build_spx_prevday_entry_table(forecast_date)
        if table is None:
            st.info("Could not compute projections (missing Yahoo RTH 1-minute data). Try another recent weekday.")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.caption(
                f"Prev Day: {meta['prev_day'].strftime('%a %b %d, %Y')} • "
                f"H @ {meta['high_t']}, C @ {meta['close_t']}, L @ {meta['low_t']} • "
                f"Slopes: ↓ {meta['slopes']['down']:+.4f} / ↑ {meta['slopes']['up']:+.4f} (per 30m)"
            )
            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Time (CT)": st.column_config.TextColumn("Time (CT)", width="small"),
                    "HIGH Entry":  st.column_config.NumberColumn("High Entry",  format="%.2f"),
                    "HIGH TP1":    st.column_config.NumberColumn("High TP1",    format="%.2f"),
                    "HIGH TP2":    st.column_config.NumberColumn("High TP2",    format="%.2f"),
                    "CLOSE Entry": st.column_config.NumberColumn("Close Entry", format="%.2f"),
                    "CLOSE TP1":   st.column_config.NumberColumn("Close TP1",   format="%.2f"),
                    "CLOSE TP2":   st.column_config.NumberColumn("Close TP2",   format="%.2f"),
                    "LOW Entry":   st.column_config.NumberColumn("Low Entry",   format="%.2f"),
                    "LOW TP1":     st.column_config.NumberColumn("Low TP1",     format="%.2f"),
                    "LOW TP2":     st.column_config.NumberColumn("Low TP2",     format="%.2f"),
                },
            )
            st.markdown('</div>', unsafe_allow_html=True)



# ==============================  PART 3 — SPX OVERNIGHT (MANUAL) ENTRY TABLE  ==============================
# Uses the sidebar inputs from Part 1:
#  - on_low_price, on_low_time  (ET)
#  - on_high_price, on_high_time (ET)
# Slopes (per 30m):  Low → +0.2792  |  High → -0.2792

# ───────────────────────────────  UTILITIES  ───────────────────────────────
OVN_SLOPE_UP  = SPX_OVERNIGHT_SLOPES["overnight_low_up"]     # +0.2792
OVN_SLOPE_DN  = SPX_OVERNIGHT_SLOPES["overnight_high_down"]  # -0.2792

def ovn_anchor_dt_et(forecast_d: date, t_et: time) -> datetime:
    """
    Overnight window is 5:00 PM–7:00 AM ET leading into the target RTH session.
    If time >= 17:00 → anchor belongs to the PREVIOUS calendar day.
    Else (before 07:00) → same day.
    """
    if t_et >= time(17, 0):
        base_d = forecast_d - timedelta(days=1)
    else:
        base_d = forecast_d
    return datetime.combine(base_d, t_et, tzinfo=ET)

def project_from_anchor(base_px: float, base_dt_et: datetime, target_dt_et: datetime, slope_per_30m: float) -> float:
    steps = int((target_dt_et - base_dt_et).total_seconds() // 1800)
    return base_px + slope_per_30m * steps

def ct_slots_30m_ovn(start: time = time(8,30), end: time = time(14,30)) -> list[datetime]:
    """Reuse the same slot grid for RTH (08:30–14:30 CT)."""
    out, cur = [], datetime.combine(forecast_date, start, tzinfo=CT)
    stop = datetime.combine(forecast_date, end, tzinfo=CT)
    while cur <= stop:
        out.append(cur)
        cur += timedelta(minutes=30)
    return out

# ───────────────────────────────  BUILD OVERNIGHT TABLE  ───────────────────────────────
def build_overnight_table_spx(
    target_session: date,
    low_px: float, low_t_et: time,
    high_px: float, high_t_et: time
) -> tuple[pd.DataFrame, dict] | tuple[None, None]:

    # Basic validation: both anchors should be provided
    if (low_px or 0) <= 0 or (high_px or 0) <= 0:
        return None, None

    # Construct ET datetimes for anchors
    low_dt_et  = ovn_anchor_dt_et(target_session, low_t_et)
    high_dt_et = ovn_anchor_dt_et(target_session, high_t_et)

    # Build slot rows
    rows = []
    for t_ct in ct_slots_30m_ovn():
        t_et = t_ct.astimezone(ET)

        low_line  = project_from_anchor(low_px,  low_dt_et,  t_et, OVN_SLOPE_UP)
        high_line = project_from_anchor(high_px, high_dt_et, t_et, OVN_SLOPE_DN)
        rng = round(high_line - low_line, 2)

        rows.append({
            "Time (CT)": t_ct.strftime("%H:%M"),
            "Overnight Low Line (Entry)": round(low_line, 2),
            "Overnight High Line (Exit)": round(high_line, 2),
            "Range (Exit − Entry)": rng
        })

    df = pd.DataFrame(rows)
    meta = {
        "low_anchor":  {"px": low_px,  "t": low_dt_et.strftime("%a %b %d • %-I:%M %p ET")},
        "high_anchor": {"px": high_px, "t": high_dt_et.strftime("%a %b %d • %-I:%M %p ET")},
        "slopes": {"low_up": OVN_SLOPE_UP, "high_dn": OVN_SLOPE_DN},
    }
    return df, meta

# ───────────────────────────────  FORECASTS — OVERNIGHT SECTION  ───────────────────────────────
if page == "Forecasts" and SYMBOL == "^GSPC":
    st.markdown('<div class="sec">', unsafe_allow_html=True)
    st.markdown("<h3>SPX — Overnight Strategy (Manual Anchors)</h3>", unsafe_allow_html=True)

    # Read sidebar values defined in Part 1
    low_px  = float(on_low_price or 0.0)
    low_t   = on_low_time
    high_px = float(on_high_price or 0.0)
    high_t  = on_high_time

    # Guidance chip
    st.caption(
        "Provide **Overnight Low** and **Overnight High** (price & ET time) in the sidebar. "
        "We project the low line **up** and the high line **down** at ±0.2792 per 30m, "
        "and compute the intra-session range for each RTH slot."
    )

    df_ovn, meta_ovn = build_overnight_table_spx(forecast_date, low_px, low_t, high_px, high_t)

    if df_ovn is None:
        st.info("Enter both **Overnight Low** and **Overnight High** (price and time) in the sidebar to see the table.")
    else:
        st.caption(
            f"Low Anchor: {meta_ovn['low_anchor']['px']:.2f} @ {meta_ovn['low_anchor']['t']}  •  "
            f"High Anchor: {meta_ovn['high_anchor']['px']:.2f} @ {meta_ovn['high_anchor']['t']}"
        )
        st.dataframe(
            df_ovn,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Time (CT)": st.column_config.TextColumn("Time (CT)", width="small"),
                "Overnight Low Line (Entry)":  st.column_config.NumberColumn("Low Line (Entry)",  format="%.2f"),
                "Overnight High Line (Exit)": st.column_config.NumberColumn("High Line (Exit)",  format="%.2f"),
                "Range (Exit − Entry)":       st.column_config.NumberColumn("Range",             format="%.2f"),
            },
        )
    st.markdown('</div>', unsafe_allow_html=True)