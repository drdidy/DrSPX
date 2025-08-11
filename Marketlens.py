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