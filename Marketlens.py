# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 1 — CORE SHELL + POLISHED UI + YF SPX ENGINE + OVERNIGHT INPUTS
# MarketLens Pro (Streamlit) — Clean professional landing with working data
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

APP_NAME = "MarketLens Pro"
VERSION = "4.1.0"
CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

# RTH (CT) for SPX: 8:30 → 15:00. We'll project to 14:30 final slot to match your 30m blocks.
RTH_START_CT = time(8, 30)
RTH_END_CT   = time(14, 30)

# Slopes per 30-min block (your latest direction: *descending* for prior-day levels)
SPX_SLOPE = {
    "HIGH": -0.2792,
    "CLOSE": -0.2792,
    "LOW": -0.2792,
}
# Overnight lines will use a *flat* default slope unless you change later
OVERNIGHT_SLOPE = 0.0

# ─────────────────────────── Streamlit page config ─────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — Professional SPX Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────── CSS (polished) ───────────────────────────
CSS = """
<style>
:root{
  --bg:#0f1115; --card:#151823; --card2:#10131b; --muted:#8b93a7;
  --accent:#5b8cff; --accent2:#8aa6ff; --success:#1fbf75; --warn:#f5a524; --error:#ff6b6b;
  --radius:18px; --pad:18px; --shadow: 0 10px 30px rgba(0,0,0,.25);
}
.stApp { background: radial-gradient(1200px 600px at 15% -10%, #1b2030 0%, #0f1115 40%); color: #e8ecf1;}
/* keep Streamlit header visible so the sidebar toggle exists */
#MainMenu, footer {display:none !important;}
.block-container {padding-top: 1.2rem !important;}
.card{
  background: linear-gradient(180deg, var(--card) 0%, var(--card2) 100%);
  border:1px solid rgba(255,255,255,.06); border-radius: var(--radius);
  padding: var(--pad); box-shadow: var(--shadow);
}
.hero{
  border-radius: 22px; padding: 28px 24px;
  background: linear-gradient(135deg, #121626 0%, #0d1220 60%),
              radial-gradient(800px 300px at 10% -20%, #24315c66 0%, transparent 60%);
  border:1px solid rgba(255,255,255,.06); box-shadow: var(--shadow);
}
.hero h1{font-size:2rem; margin:0 0 .25rem 0;}
.kpi{display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;}
.kpi .pill{
  background:#0c0f18; border:1px solid rgba(255,255,255,.08); border-radius: 14px;
  padding:14px; text-align:center;
}
.kpi .label{color:var(--muted); font-size:.85rem; margin-top:4px}
.badge{
  display:inline-flex; gap:8px; align-items:center; padding:8px 12px;
  border-radius:999px; font-weight:600; font-size:.9rem;
  background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.08)
}
.badge.ok{ background: linear-gradient(90deg, #123f2a, #0e2f20); color:#b7f7d5; border-color:#1c5f3d;}
.badge.warn{ background: linear-gradient(90deg, #3a2d12, #2b210e); color:#ffe0a6; border-color:#5f4a1c;}
.badge.err{ background: linear-gradient(90deg, #421d1d, #2a1313); color:#ffc1c1; border-color:#6b2a2a;}
h3.section{margin:12px 0 6px 0;}
.small{color:var(--muted); font-size:.9rem}
.tbl .blank{color:#6d7386}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ───────────────────────────── Utilities & data ────────────────────────────
def _to_ct(ts: pd.DatetimeIndex|pd.Series) -> pd.Series:
    return pd.to_datetime(ts, utc=True).tz_convert(CT)

@st.cache_data(ttl=300)
def yf_fetch_intraday(symbol: str, start_dt_ct: datetime, end_dt_ct: datetime) -> pd.DataFrame:
    """Resilient fetch: try 1m → 5m → 15m. Return Dt(Open/High/Low/Close) in CT or empty df."""
    tz = "America/Chicago"
    intervals = ["1m", "5m", "15m"]
    for itv in intervals:
        try:
            df = yf.download(
                symbol,
                start=start_dt_ct.astimezone(CT).strftime("%Y-%m-%d %H:%M"),
                end=end_dt_ct.astimezone(CT).strftime("%Y-%m-%d %H:%M"),
                interval=itv,
                auto_adjust=False, progress=False, prepost=True, threads=False,
            )
            if df is None or df.empty:
                continue
            df = df.reset_index().rename(columns={"Datetime":"Dt","Date":"Dt"})
            if "Dt" not in df.columns:
                # yfinance sometimes calls index 'index'
                if "index" in df.columns:
                    df = df.rename(columns={"index":"Dt"})
                else:
                    # fallback: the first column is the timestamp
                    df.columns = ["Dt"] + list(df.columns[1:])
            # Normalize column names
            cols = {c:c.capitalize() for c in df.columns}
            df = df.rename(columns=cols)
            need = {"Dt","Open","High","Low","Close"}
            if not need.issubset(set(df.columns)):  # not our structure
                continue
            df["Dt"] = _to_ct(df["Dt"])
            df = df.dropna(subset=["Open","High","Low","Close"]).sort_values("Dt")
            if df.empty:
                continue
            return df[["Dt","Open","High","Low","Close"]].copy()
        except Exception:
            continue
    return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

def rth_slots_30m(d: date) -> list[datetime]:
    base = datetime.combine(d, RTH_START_CT, tzinfo=CT)
    end  = datetime.combine(d, RTH_END_CT, tzinfo=CT)
    out=[]
    cur=base
    while cur<=end:
        out.append(cur)
        cur += timedelta(minutes=30)
    return out

def friendly_status(df: pd.DataFrame) -> tuple[str,str]:
    if df is None or df.empty:
        return ("err","No data for the selected window")
    return ("ok","Live data available")

# ───────────────────────────── Sidebar (nav + inputs) ──────────────────────
with st.sidebar:
    st.markdown("### Navigation")
    st.page_link("Marketlens.py", label="Overview", icon="🏠")
    st.markdown("---")
    st.markdown("### Session")
    target_session: date = st.date_input("Trading Session (CT)", value=date.today(), help="RTH projection date")

    st.markdown("### Overnight Levels (manual)")
    st.caption("Session from **5:00 PM → 2:00 AM CT**")
    colA, colB = st.columns(2)
    with colA:
        on_hi_price = st.number_input("Overnight High ($)", min_value=0.0, value=0.0, step=0.25, format="%.2f")
    with colB:
        on_hi_time  = st.time_input("High time", value=time(17, 0))
    colC, colD = st.columns(2)
    with colC:
        on_lo_price = st.number_input("Overnight Low ($)",  min_value=0.0, value=0.0, step=0.25, format="%.2f")
    with colD:
        on_lo_time  = st.time_input("Low time", value=time(17, 0))

# ───────────────────────────── Hero header ─────────────────────────────────
st.markdown(
    f"""
    <div class="hero">
      <div style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;">
        <div>
          <h1>{APP_NAME}</h1>
          <div class="small">Professional S&P 500 analytics powered by Yahoo Finance</div>
        </div>
        <div class="badge">v{VERSION}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ───────────────────────────── Market data status card ─────────────────────
# Fetch a small, recent window around the chosen session to verify connectivity.
check_start = datetime.combine(target_session - timedelta(days=1), time(7,0), tzinfo=CT)
check_end   = datetime.combine(target_session, time(16,0), tzinfo=CT)
df_check = yf_fetch_intraday("^GSPC", check_start, check_end)
state, msg = friendly_status(df_check)

st.markdown("### Market Data")
st.markdown(
    f"""
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
        <div class="badge {'ok' if state=='ok' else 'err'}">
          {'🟢 Connected' if state=='ok' else '🔴 Not available'}
        </div>
        <div class="small">{'S&P 500'}</div>
      </div>
      <div style="margin-top:10px;color:{'#b7f7d5' if state=='ok' else '#ffc1c1'}">{msg}</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ───────────────────────────── Overnight projection preview ────────────────
st.markdown("### Overnight Projections → Today’s RTH")
# Build a tiny, useful table even if no YF data was returned (so the page looks complete).
slots = rth_slots_30m(target_session)
def project_line(base_px: float, base_dt: datetime, t: datetime, slope_per_block: float) -> float:
    if base_px <= 0 or base_dt is None:
        return float("nan")
    # 30-minute block count from base_dt to t
    step = timedelta(minutes=30)
    blocks = int(np.floor((t - base_dt) / step))
    return round(base_px + slope_per_block * blocks, 2)

on_hi_dt = datetime.combine(
    target_session - timedelta(days=1) if on_hi_time >= time(17,0) else target_session,
    on_hi_time, tzinfo=CT
)
on_lo_dt = datetime.combine(
    target_session - timedelta(days=1) if on_lo_time >= time(17,0) else target_session,
    on_lo_time, tzinfo=CT
)

rows=[]
for t in slots:
    rows.append({
        "Time": t.strftime("%H:%M"),
        "ON High Line ($)": project_line(on_hi_price, on_hi_dt, t, OVERNIGHT_SLOPE),
        "ON Low Line ($)":  project_line(on_lo_price, on_lo_dt, t, OVERNIGHT_SLOPE),
        "Prev High Line ($)": project_line(0.0, on_hi_dt, t, 0.0),  # placeholder for Parts 2–3 (prior-day H/L/C)
    })
preview = pd.DataFrame(rows)

st.dataframe(
    preview[["Time","ON High Line ($)","ON Low Line ($)"]],
    use_container_width=True, hide_index=True,
    column_config={
        "Time": st.column_config.TextColumn("RTH Slot"),
        "ON High Line ($)": st.column_config.NumberColumn(format="$%.2f"),
        "ON Low Line ($)":  st.column_config.NumberColumn(format="$%.2f"),
    }
)

st.caption(
    "Tip: enter your **Overnight High/Low** (price + time between 5:00 PM and 2:00 AM CT). "
    "Lines are projected across today’s RTH in 30-minute slots. Slopes can be customized later."
)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# End of PART 1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# ============================== PART 2 — SPX DATA, ANCHORS & PROJECTIONS ==============================
# Includes:
# • Robust Yahoo Finance intraday fetch for ^GSPC (1m→5m→15m fallback)
# • Prior-day H/L/C (RTH 08:30–15:00 CT) extraction
# • User inputs for Overnight High/Low (+ time) (window 17:00–02:00 CT)
# • Slope config (per 30-min block) for: Previous Day High/Close/Low (all −0.2792) and Overnight H/L (user-set)
# • Projection table for today’s session (08:30–15:00 CT) for each active anchor line

import datetime as _dt
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st

CT = ZoneInfo("America/Chicago")

# ---------- Time helpers ----------
RTH_START_CT = time(8,30)
RTH_END_CT   = time(15,0)

def _dt_range_ct(d_from: datetime, d_to: datetime):
    """Ensure tz-aware CT datetimes (inclusive)."""
    if d_from.tzinfo is None: d_from = d_from.replace(tzinfo=CT)
    if d_to.tzinfo   is None: d_to   = d_to.replace(tzinfo=CT)
    return d_from.astimezone(CT), d_to.astimezone(CT)

def _slots_30m_for_day(d: date) -> list[datetime]:
    cur = datetime(d.year, d.month, d.day, RTH_START_CT.hour, RTH_START_CT.minute, tzinfo=CT)
    end = datetime(d.year, d.month, d.day, RTH_END_CT.hour, RTH_END_CT.minute, tzinfo=CT)
    out = []
    while cur <= end:
        out.append(cur)
        cur += timedelta(minutes=30)
    return out

# ---------- Yahoo fetch with resilient normalization ----------
@st.cache_data(ttl=300, show_spinner=False)
def yf_fetch_intraday(symbol: str, start_ct: datetime, end_ct: datetime) -> pd.DataFrame:
    """
    Return columns: Dt(CT tz), Open, High, Low, Close
    Tries 1m then 5m then 15m. Silently returns empty df if no rows.
    """
    start_ct, end_ct = _dt_range_ct(start_ct, end_ct)

    def _download(interval: str) -> pd.DataFrame:
        df = yf.download(
            tickers=symbol,
            interval=interval,
            start=start_ct.astimezone(_dt.timezone.utc),
            end=end_ct.astimezone(_dt.timezone.utc),
            auto_adjust=False,
            progress=False,
            prepost=True,
            threads=False,
        )
        if df is None or len(df) == 0:
            return pd.DataFrame()
        # Handle possible MultiIndex columns (("^GSPC","Open"), ...)
        if isinstance(df.columns, pd.MultiIndex):
            # pick the first level if present
            if symbol in df.columns.levels[0]:
                df = df.xs(symbol, axis=1, level=0)
            else:
                df.columns = [c[0] for c in df.columns]  # ("Open",) → "Open"
        df = df.rename_axis("ts").reset_index()
        # yfinance returns tz-aware index if start/end tz-aware; ensure UTC then convert CT
        if not pd.api.types.is_datetime64_any_dtype(df["ts"]):
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
        else:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df["Dt"] = df["ts"].dt.tz_convert(CT)
        keep = ["Dt","Open","High","Low","Close"]
        df = df[keep].dropna(subset=["Open","High","Low","Close"]).sort_values("Dt")
        return df

    for iv in ("1m","5m","15m"):
        try:
            got = _download(iv)
            if not got.empty:
                return got
        except Exception:
            continue
    return pd.DataFrame(columns=["Dt","Open","High","Low","Close"])

# ---------- Previous-day RTH H/L/C ----------
@st.cache_data(ttl=600, show_spinner=False)
def spx_prevday_hlc(target_session: date) -> dict | None:
    """
    Compute prior day High/Low/Close using RTH window (08:30–15:00 CT).
    Returns dict with prices and timestamps in CT.
    """
    prev = target_session - timedelta(days=1)
    # If weekend, walk back to last weekday
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)

    start_ct = datetime(prev.year, prev.month, prev.day, 8, 25, tzinfo=CT)
    end_ct   = datetime(prev.year, prev.month, prev.day, 15,  5, tzinfo=CT)

    df = yf_fetch_intraday("^GSPC", start_ct, end_ct)
    if df.empty:
        return None

    # Restrict strictly to 08:30–15:00 bars
    df = df.set_index("Dt").between_time(RTH_START_CT.strftime("%H:%M"), RTH_END_CT.strftime("%H:%M")).reset_index()
    if df.empty:
        return None

    hi_idx = df["High"].idxmax()
    lo_idx = df["Low"].idxmin()
    close_row = df.iloc[-1]

    return {
        "day": prev,
        "high": float(df.loc[hi_idx, "High"]),
        "high_t": df.loc[hi_idx, "Dt"].to_pydatetime(),
        "low": float(df.loc[lo_idx, "Low"]),
        "low_t": df.loc[lo_idx, "Dt"].to_pydatetime(),
        "close": float(close_row["Close"]),
        "close_t": close_row["Dt"].to_pydatetime(),
    }

# ---------- Slopes & line projection ----------
# Slopes are per 30-minute block (your provided values)
SPX_SLOPES = {
    "PD_HIGH": -0.2792,
    "PD_CLOSE": -0.2792,
    "PD_LOW": -0.2792,
    # Overnight slopes are user configurable (defaults below)
    "ON_HIGH": -0.2792,
    "ON_LOW": -0.2792,
}

def _blocks_between_30m(t0: datetime, t1: datetime) -> int:
    """Count 30-min steps (right-closed bar model)."""
    if t1 < t0: t0, t1 = t1, t0
    blocks = 0
    cur = t0.replace(second=0, microsecond=0)
    while cur < t1:
        blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def proj_price(base_px: float, base_time: datetime, slope_per_30m: float, target_time: datetime) -> float:
    blk = _blocks_between_30m(base_time, target_time)
    return base_px + slope_per_30m * blk

# ---------- UI: Anchor inputs (Overnight + preview) ----------
st.markdown("### ⚓ SPX Anchors & Slopes")

colA, colB = st.columns([2,1])
with colA:
    # Pull prior-day anchors
    _d = st.session_state.get("ml_target_session", date.today())
    prev = spx_prevday_hlc(_d)
    if prev is None:
        st.info("Prior-day H/L/C not available yet for the selected session.")
    else:
        st.success(
            f"Prev Day ({prev['day']:%a %b %d})  •  "
            f"H {prev['high']:.2f} @ {prev['high_t'].strftime('%H:%M')}  •  "
            f"L {prev['low']:.2f} @ {prev['low_t'].strftime('%H:%M')}  •  "
            f"C {prev['close']:.2f} @ {prev['close_t'].strftime('%H:%M')}"
        )

with colB:
    st.caption("Slopes per 30-min block (defaults fixed at −0.2792).")
    sl_pd_high  = st.number_input("Prev-Day High Slope",  value=SPX_SLOPES["PD_HIGH"],  step=0.0001, format="%.4f")
    sl_pd_close = st.number_input("Prev-Day Close Slope", value=SPX_SLOPES["PD_CLOSE"], step=0.0001, format="%.4f")
    sl_pd_low   = st.number_input("Prev-Day Low Slope",   value=SPX_SLOPES["PD_LOW"],   step=0.0001, format="%.4f")

st.markdown("#### 🌙 Overnight Anchors (5:00 PM → 2:00 AM CT)")
oc1, oc2, oc3 = st.columns([2,2,1])
with oc1:
    on_high_px = st.number_input("Overnight High Price", value=0.00, step=0.25, format="%.2f", help="Leave 0 to ignore")
    on_high_t  = st.time_input("Overnight High Time (CT)", value=time(17,0), help="Between 17:00 and 02:00")
with oc2:
    on_low_px  = st.number_input("Overnight Low Price",  value=0.00, step=0.25, format="%.2f", help="Leave 0 to ignore")
    on_low_t   = st.time_input("Overnight Low Time (CT)", value=time(17,30), help="Between 17:00 and 02:00")
with oc3:
    sl_on      = st.number_input("Overnight Slope (per 30m)", value=SPX_SLOPES["ON_LOW"], step=0.0001, format="%.4f")

# ---------- Projection table ----------
st.markdown("### 📋 Projection Table (08:30 – 15:00 CT)")

def build_projection_for_day(session_d: date) -> tuple[pd.DataFrame, dict]:
    """Create a table with lines from PD High/Close/Low and optional Overnight High/Low."""
    meta = {"session": session_d}
    slots = _slots_30m_for_day(session_d)

    rows = []
    if prev is not None:
        bases = [
            ("PD_HIGH",  prev["high"],  prev["high_t"],  sl_pd_high),
            ("PD_CLOSE", prev["close"], prev["close_t"], sl_pd_close),
            ("PD_LOW",   prev["low"],   prev["low_t"],   sl_pd_low),
        ]
        for label, px, t0, slope in bases:
            for t in slots:
                rows.append({
                    "Time": t.strftime("%H:%M"),
                    "Anchor": label.replace("PD_","PrevDay "),
                    "Price": round(proj_price(px, t0, slope, t), 2)
                })

    # Overnight anchors (optional)
    def _dt_for_time(session_ref: date, hhmm: time) -> datetime:
        # If 00:00–02:00, that is technically next calendar day → use session_ref (same date as session?)
        # We consider base time located on the *night before* the session:
        base_day = session_ref  # session day at 00:00 CT
        # if time is 17:00–23:59 → it’s the evening BEFORE session_d
        if hhmm >= time(17,0):
            base_day = session_ref - timedelta(days=1)
        # if time is 00:00–02:00 → early morning OF the session
        return datetime(base_day.year, base_day.month, base_day.day, hhmm.hour, hhmm.minute, tzinfo=CT)

    if on_high_px > 0:
        t0 = _dt_for_time(session_d, on_high_t)
        for t in slots:
            rows.append({
                "Time": t.strftime("%H:%M"),
                "Anchor": "Overnight High",
                "Price": round(proj_price(on_high_px, t0, sl_on, t), 2)
            })
    if on_low_px > 0:
        t0 = _dt_for_time(session_d, on_low_t)
        for t in slots:
            rows.append({
                "Time": t.strftime("%H:%M"),
                "Anchor": "Overnight Low",
                "Price": round(proj_price(on_low_px, t0, sl_on, t), 2)
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df, meta
    # Pivot to wide for a clean table (one row per 30m slot)
    wide = df.pivot_table(index="Time", columns="Anchor", values="Price", aggfunc="first").reset_index()
    # nice column order
    cols = ["Time"]
    for c in ["PrevDay High","PrevDay Close","PrevDay Low","Overnight High","Overnight Low"]:
        if c in wide.columns: cols.append(c)
    wide = wide[cols]
    return wide, meta

proj_table, proj_meta = build_projection_for_day(st.session_state.get("ml_target_session", date.today()))
if proj_table.empty:
    st.info("No projection yet. Verify prior-day data exists or add Overnight anchors.")
else:
    st.dataframe(
        proj_table,
        hide_index=True,
        use_container_width=True,
        column_config={"Time": st.column_config.TextColumn(width="small")}
    )
# ======================================================================================================