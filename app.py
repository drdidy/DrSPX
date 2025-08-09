from __future__ import annotations
import io, zipfile
from datetime import datetime, date, time, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import altair as alt

# Optional plotly (toggle in the UI). Safe to import if in requirements.
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False

APP_NAME = "MarketLens"
VERSION = "3.3.0"

# ----- Strategy constants (fixed per 30-min block; hidden in UI)
SPX_SLOPES_DOWN = {"HIGH": -0.2792, "CLOSE": -0.2792, "LOW": -0.2792}
SPX_SLOPES_UP   = {"HIGH": +0.3171, "CLOSE": +0.3171, "LOW": +0.3171}
TICK = 0.25

ICON_HIGH, ICON_CLOSE, ICON_LOW = "▲", "■", "▼"  # up triangle, square, down triangle

# ----- Verbatim content you asked to keep
SPX_GOLDEN_RULES = [
    "Exit levels are exits - never entries",
    "Anchors are magnets, not timing signals - let price come to you",
    "The market will give you your entry - don't force it",
    "Consistency in process trumps perfection in prediction",
    "When in doubt, stay out - there's always another trade",
    "SPX ignores the full 16:00-17:00 maintenance block",
]
SPX_ANCHOR_RULES = {
    "rth_breaks": [
        "30-min close below RTH entry anchor: price may retrace above anchor line but will fall below again shortly after",
        "Don't chase the bounce: prepare for the inevitable breakdown",
        "Wait for confirmation: let the market give you the entry",
    ],
    "extended_hours": [
        "Extended session weakness + recovery: use recovered anchor as buy signal in RTH",
        "Extended session anchors carry forward momentum into regular trading hours",
        "Extended bounce of anchors carry forward momentum into regular trading hours",
        "Overnight anchor recovery: strong setup for next day strength",
    ],
    "mon_wed_fri": [
        "No touch of high, close, or low anchors on Mon/Wed/Fri = potential sell day later",
        "Don't trade TO the anchor: let the market give you the entry",
        "Wait for price action confirmation rather than anticipating touches",
    ],
    "fibonacci_bounce": [
        "SPX Line Touch + Bounce: when SPX price touches line and bounces, contract follows the same pattern",
        "0.786 Fibonacci Entry: contract retraces to 0.786 fib level (low to high of bounce) = major algo entry point",
        "Next Hour Candle: the 0.786 retracement typically occurs in the NEXT hour candle, not the same one",
        "High Probability: algos consistently enter at 0.786 level for profitable runs",
        "Setup Requirements: clear bounce off SPX line + identifiable low-to-high swing for fib calculation",
    ],
}
CONTRACT_STRATEGIES = {
    "tuesday_play": [
        "Identify two overnight option low points that rise $400-$500",
        "Use them to set Tuesday contract slope",
        "Tuesday contract setups often provide best mid-week momentum",
    ],
    "thursday_play": [
        "If Wednesday's low premium was cheap: Thursday low ≈ Wed low (buy-day)",
        "If Wednesday stayed pricey: Thursday likely a put-day (avoid longs)",
        "Wednesday pricing telegraphs Thursday direction",
    ],
}
TIME_RULES = {
    "market_sessions": [
        "9:30-10:00 AM: initial range, avoid FOMO entries",
        "10:30-11:30 AM: institutional flow window, best entries",
        "2:00-3:00 PM: final push time, momentum plays",
        "3:30+ PM: scalps only, avoid new positions",
    ],
    "volume_patterns": [
        "Entry volume > 20-day average: strong conviction signal",
        "Declining volume on bounces: fade the move",
        "Volume spike + anchor break: high probability setup",
    ],
    "multi_timeframe": [
        "5-min + 15-min + 1-hour all pointing same direction = high conviction",
        "Conflicting timeframes = wait for resolution",
        "Daily anchor + intraday setup = strongest edge",
    ],
}
RISK_RULES = {
    "position_sizing": [
        "Never risk more than 2% per trade: consistency beats home runs",
        "Scale into positions: 1/3 initial, 1/3 confirmation, 1/3 momentum",
        "Reduce size on Fridays: weekend risk isn't worth it",
    ],
    "stop_strategy": [
        "Hard stops at -15% for options: no exceptions",
        "Trailing stops after +25%: protect profits aggressively",
        "Time stops at 3:45 PM: avoid close volatility",
    ],
    "market_context": [
        "VIX above 25: reduce position sizes by 50%",
        "Major earnings week: avoid unrelated tickers",
        "FOMC/CPI days: trade post-announcement only (10:30+ AM)",
    ],
    "psychological": [
        "3 losses in a row: step away for 1 hour minimum",
        "Big win euphoria: reduce next position size by 50%",
        "Revenge trading: automatic day-end (no exceptions)",
    ],
    "performance_targets": [
        "Win rate target: 55%+",
        "Risk/reward minimum: 1:1.5",
        "Weekly P&L cap: stop after +20% or -10% weekly moves",
    ],
}

# ===== Light-first Apple-like CSS (dark toggle supported) =====
CSS_BASE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{
  --bg:#FFFFFF; --surface:#F7F8FA; --card:#FFFFFF; --border:#E6E9EF;
  --text:#0F172A; --muted:#62708A; --accent:#2A6CFB; --good:#16A34A; --bad:#DC2626;
  --radius:14px; --shadow:0 8px 24px rgba(16,24,40,.06);
}
html,body,.stApp{font-family:Inter,-apple-system,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
.stApp{background:var(--surface); color:var(--text);}
#MainMenu, footer, .stDeployButton{display:none!important;}

.header{
  display:flex; align-items:center; justify-content:space-between; gap:1rem;
  padding:14px 18px; border:1px solid var(--border); border-radius:var(--radius);
  background:var(--card); box-shadow:var(--shadow); position:sticky; top:.5rem; z-index:10;
}
.brand{font-weight:800; letter-spacing:.2px}
.meta{color:var(--muted); font-size:.9rem}

.card{
  background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
  box-shadow:var(--shadow); padding:16px; margin:.8rem 0 1rem 0;
}
.hline{height:1px; background:#EEF1F6; margin:8px 0 12px 0}
.section-title{font-weight:700; letter-spacing:.2px; margin-bottom:.2rem}
.subtle{color:var(--muted); font-size:.92rem}
.bad{color:var(--bad)} .good{color:var(--good)}

.icon-chip{
  display:inline-flex; align-items:center; gap:.5rem; padding:.28rem .6rem;
  border:1px solid var(--border); border-radius:999px; background:#F5F7FB;
  font-weight:600; color:#0F172A;
}
.icon{
  display:inline-flex; width:22px; height:22px; align-items:center; justify-content:center;
  border:1px solid var(--border); border-radius:6px; background:#FFF; font-size:.85rem
}
.i-high{color:#16A34A}.i-close{color:#2A6CFB}.i-low{color:#DC2626}

/* DataFrames */
.table-wrap{border-radius:var(--radius); overflow:hidden; border:1px solid var(--border)}
.dataframe th{background:#F5F7FB!important; font-weight:600!important; color:#0F172A!important;}
.dataframe td, .dataframe th{font-size:0.95rem!important}

/* Primary buttons */
.stButton > button, .stDownloadButton > button {
  color:#fff !important; background:var(--accent) !important; border:1px solid var(--accent) !important;
  border-radius:12px !important; padding:12px 14px !important; font-weight:700 !important;
  box-shadow:0 6px 16px rgba(42,108,251,.18) !important;
}
.stButton > button:hover, .stDownloadButton > button:hover { filter:brightness(0.96); }

/* Inputs in light mode */
body:not(.dark) .stNumberInput input, 
body:not(.dark) .stTimeInput input, 
body:not(.dark) .stSelectbox div[data-baseweb="select"] {
  background:#fff !important; color:#0F172A !important; border-color:var(--border) !important;
}

/* Dark theme override */
body.dark{
  --bg:#0B0F14; --surface:#0F141B; --card:#0E141C; --border:#1E2633;
  --text:#E9EEF6; --muted:#9BA7B6; --accent:#4D7CFF; --shadow:0 10px 28px rgba(0,0,0,.28);
}
body.dark .stButton > button, body.dark .stDownloadButton > button{
  background:#2A3443 !important; border-color:#334155 !important; color:#E9EEF6 !important;
  box-shadow:0 8px 24px rgba(0,0,0,.35) !important;
}
</style>
"""
INJECT_DARK_TOGGLE = """
<script>
const setMode = (mode) => {
  const b = window.parent.document.body;
  if(mode === 'Dark'){ b.classList.add('dark'); } else { b.classList.remove('dark'); }
}
</script>
"""

# ===== Helpers =====
RTH_START, RTH_END = time(8,30), time(15,30)

def spx_blocks_between(t1: datetime, t2: datetime) -> int:
    if t2 < t1: t1, t2 = t2, t1
    blocks, cur = 0, t1
    while cur < t2:
        if cur.hour != 16:  # skip 16:00–16:59
            blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def make_slots(start: time, end: time, step_min:int=30) -> list[str]:
    cur = datetime(2025,1,1,start.hour,start.minute)
    stop= datetime(2025,1,1,end.hour,end.minute)
    out=[]
    while cur <= stop:
        out.append(cur.strftime("%H:%M")); cur += timedelta(minutes=step_min)
    return out

SPX_SLOTS = make_slots(RTH_START, RTH_END)
ETH_SLOTS = make_slots(time(7,30), RTH_END)

def round_to_tick(x: float, tick: float = TICK) -> float:
    if tick <= 0: return float(x)
    n = round(x / tick)
    return round(n * tick, 2)

def project(anchor_price: float, slope_per_block: float, blocks: int) -> float:
    return anchor_price + slope_per_block * blocks

def fib_levels(low: float, high: float) -> dict[str, float]:
    R = high - low
    return {
        "0.236": high - R*0.236, "0.382": high - R*0.382, "0.500": high - R*0.500,
        "0.618": high - R*0.618, "0.786": high - R*0.786, "1.000": low,
        "1.272": high + R*0.272, "1.618": high + R*0.618,
    }

# ===== State & page =====
if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.theme = "Light"
    st.session_state.locked_anchors = False
    st.session_state.forecasts_generated = False
    st.session_state.contract = {"anchor_time": None, "anchor_price": None, "slope": None, "label": "Manual"}
    st.session_state.print_mode = False

st.set_page_config(page_title=f"{APP_NAME} — SPX Console", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS_BASE, unsafe_allow_html=True)
st.markdown(INJECT_DARK_TOGGLE, unsafe_allow_html=True)

# ===== Live price (Yahoo) =====
@st.cache_data(ttl=60)
def fetch_spx_summary():
    try:
        t = yf.Ticker("^GSPC")
        intraday = t.history(period="1d", interval="1m")
        daily = t.history(period="5d", interval="1d")
        if intraday is None or intraday.empty or daily is None or daily.empty:
            return {"ok": False}
        last = intraday.iloc[-1]
        price = float(last["Close"])
        prev_close = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else price
        chg = price - prev_close
        pct = (chg / prev_close * 100) if prev_close else 0.0
        today_high = float(daily["High"].iloc[-1])
        today_low  = float(daily["Low"].iloc[-1])
        return {"ok": True, "price": price, "chg": chg, "pct": pct, "high": today_high, "low": today_low}
    except Exception:
        return {"ok": False}

@st.cache_data(ttl=120)
def fetch_spx_intraday_df():
    """RTH-only intraday (today), 1-min bars for overlay against anchor fans."""
    try:
        t = yf.Ticker("^GSPC")
        df = t.history(period="1d", interval="1m")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.rename(columns={"Datetime":"dt"}, inplace=True)
        if "dt" not in df.columns:
            df.rename(columns={df.columns[0]:"dt"}, inplace=True)  # yfinance returns first col as Datetime
        df["Time"] = df["dt"].dt.tz_localize(None).dt.strftime("%H:%M")
        # Filter to RTH window
        df = df[(df["Time"] >= "08:30") & (df["Time"] <= "15:30")]
        return df[["Time","Close"]].copy()
    except Exception:
        return pd.DataFrame()

# ===== Header =====
st.markdown(
    f"""
    <div class="header">
      <div class="brand">{APP_NAME}</div>
      <div class="meta">v{VERSION}</div>
    </div>
    """, unsafe_allow_html=True
)
sumy = fetch_spx_summary()
if sumy.get("ok"):
    color = "good" if sumy["chg"]>=0 else "bad"
    st.markdown(
        f"""
        <div class="card" style="padding:12px 16px;">
          <div style="display:flex;align-items:center;gap:16px;">
            <div class="icon-chip"><span class="icon i-close">{ICON_CLOSE}</span><span>SPX</span></div>
            <div style="font-weight:700">{sumy['price']:.2f}</div>
            <div class="{color}">{sumy['chg']:+.2f} ({sumy['pct']:+.2f}%)</div>
            <div style="margin-left:auto" class="subtle">H:{sumy['high']:.2f} · L:{sumy['low']:.2f}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.markdown(
        """
        <div class="card" style="padding:12px 16px;">
          <div class="subtle">Live SPX price unavailable (yfinance not installed or no connectivity).</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ===== Sidebar =====
with st.sidebar:
    st.subheader("Appearance")
    st.session_state.theme = st.radio("Theme", ["Light","Dark"], index=0 if st.session_state.theme=="Light" else 1, horizontal=True)
    st.markdown(f"<script>setMode('{st.session_state.theme}')</script>", unsafe_allow_html=True)
    st.session_state.print_mode = st.toggle("Print-friendly", value=st.session_state.print_mode)
    if st.session_state.print_mode:
        st.markdown('<style>.stApp{background:#fff!important;color:#111!important}.card{background:#fff!important;border-color:#ddd!important;box-shadow:none!important}</style>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Chart engine")
    use_plotly = st.toggle("Use Plotly instead of Altair", value=False, help="Altair is lighter with native pan/zoom. Plotly optional.")

    st.divider()
    st.subheader("Forecast Date")
    forecast_date = st.date_input("Target session", value=date.today() + timedelta(days=1))
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    st.info(f"{days[forecast_date.weekday()]} session • anchors reference the previous day.")

    st.divider()
    st.subheader("Documentation")
    with st.expander("Golden Rules", expanded=False):
        for r in SPX_GOLDEN_RULES: st.markdown(f"- {r}")
    with st.expander("Anchor Trading Rules", expanded=False):
        st.markdown("**RTH Anchor Breaks**");     [st.markdown(f"- {r}") for r in SPX_ANCHOR_RULES["rth_breaks"]]
        st.markdown("**Extended Hours**");        [st.markdown(f"- {r}") for r in SPX_ANCHOR_RULES["extended_hours"]]
        st.markdown("**Mon/Wed/Fri Rules**");     [st.markdown(f"- {r}") for r in SPX_ANCHOR_RULES["mon_wed_fri"]]
        st.markdown("**Fibonacci Bounce**");      [st.markdown(f"- {r}") for r in SPX_ANCHOR_RULES["fibonacci_bounce"]]
    with st.expander("Contract Strategies", expanded=False):
        st.markdown("**Tuesday Contract Play**"); [st.markdown(f"- {r}") for r in CONTRACT_STRATEGIES["tuesday_play"]]
        st.markdown("**Thursday Contract Play**");[st.markdown(f"- {r}") for r in CONTRACT_STRATEGIES["thursday_play"]]
    with st.expander("Time & Volume", expanded=False):
        st.markdown("**Market Sessions**");       [st.markdown(f"- {r}") for r in TIME_RULES["market_sessions"]]
        st.markdown("**Volume Patterns**");       [st.markdown(f"- {r}") for r in TIME_RULES["volume_patterns"]]
        st.markdown("**Multi-Timeframe**");       [st.markdown(f"- {r}") for r in TIME_RULES["multi_timeframe"]]

# ===== Anchors =====
def anchor_inputs(prefix: str, default_price: float, default_time: time):
    price = st.number_input(f"{prefix} price", value=float(default_price), step=0.1, min_value=0.0, key=f"{prefix}_price")
    when  = st.time_input(f"{prefix} time",  value=default_time, step=300, key=f"{prefix}_time")
    return price, when

with st.container():
    st.markdown('<div class="card"><div class="section-title">SPX Anchors (previous day)</div><div class="hline"></div>', unsafe_allow_html=True)
    col_high, col_close, col_low = st.columns(3)
    with col_high:
        st.markdown(f'<div class="icon-chip"><span class="icon i-high">{ICON_HIGH}</span><span>High</span></div>', unsafe_allow_html=True)
        high_price, high_time = anchor_inputs("High", 6185.80, time(11,30))
    with col_close:
        st.markdown(f'<div class="icon-chip"><span class="icon i-close">{ICON_CLOSE}</span><span>Close</span></div>', unsafe_allow_html=True)
        close_price, close_time = anchor_inputs("Close", 6170.20, time(15,0))
    with col_low:
        st.markdown(f'<div class="icon-chip"><span class="icon i-low">{ICON_LOW}</span><span>Low</span></div>', unsafe_allow_html=True)
        low_price, low_time = anchor_inputs("Low", 6130.40, time(13,30))

    colA, colB = st.columns([1,1])
    with colA:
        if not st.session_state.get("locked_anchors", False):
            if st.button("Lock anchors", use_container_width=True, type="primary"):
                st.session_state.locked_anchors = True
        else:
            if st.button("Edit anchors", use_container_width=True, type="primary"):
                st.session_state.locked_anchors = False
    with colB:
        generate = st.button("Generate forecast", use_container_width=True, type="primary")
    st.markdown('</div>', unsafe_allow_html=True)

# ===== Forecast dataframes (for tables & charts) =====
def build_fan_df(anchor_label: str, anchor_price: float, anchor_time: time) -> pd.DataFrame:
    rows=[]; anchor_dt = datetime.combine(forecast_date - timedelta(days=1), anchor_time)
    for slot in SPX_SLOTS:
        hh, mm = map(int, slot.split(":")); tdt = datetime.combine(forecast_date, time(hh, mm))
        blocks = spx_blocks_between(anchor_dt, tdt)
        entry = project(anchor_price, SPX_SLOPES_DOWN[anchor_label], blocks)
        exit_ = project(anchor_price, SPX_SLOPES_UP[anchor_label],   blocks)
        rows.append({"Time":slot, "Entry":round(entry,2), "Exit":round(exit_,2), "Blocks":blocks})
    return pd.DataFrame(rows)

intraday_df = fetch_spx_intraday_df()

def altair_fan_chart(df_fan: pd.DataFrame, title: str, intraday: pd.DataFrame | None):
    base = alt.Chart(df_fan).transform_fold(
        ["Entry","Exit"], as_=["Series","Price"]
    ).mark_line(strokeWidth=2).encode(
        x=alt.X('Time:T', title=None),
        y=alt.Y('Price:Q', title='Price'),
        color=alt.Color('Series:N', scale=alt.Scale(range=["#EF4444", "#16A34A"]))  # red=Entry(down), green=Exit(up)
    )
    overlays = []
    if intraday is not None and not intraday.empty:
        price_line = alt.Chart(intraday).mark_line(strokeWidth=1.5, opacity=0.8).encode(
            x='Time:T', y=alt.Y('Close:Q', title='Price'), color=alt.value('#2563EB')  # blue actual
        )
        overlays.append(price_line)
    chart = (base + sum(overlays, alt.Chart())).properties(width='container', height=300, title=title).interactive()
    return chart

def plotly_fan_chart(df_fan: pd.DataFrame, title: str, intraday: pd.DataFrame | None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_fan["Time"], y=df_fan["Entry"], name="Entry", line=dict(width=2, color="#EF4444")))
    fig.add_trace(go.Scatter(x=df_fan["Time"], y=df_fan["Exit"],  name="Exit",  line=dict(width=2, color="#16A34A"), fill='tonexty', fillcolor='rgba(22,163,74,0.12)'))
    if intraday is not None and not intraday.empty:
        fig.add_trace(go.Scatter(x=intraday["Time"], y=intraday["Close"], name="SPX", line=dict(width=2, color="#2563EB")))
    fig.update_layout(title=title, height=340, margin=dict(l=10,r=10,t=40,b=20), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    fig.update_xaxes(rangeslider_visible=True, showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    return fig

if generate or st.session_state.get("forecasts_generated", False):
    st.session_state.forecasts_generated = True
    with st.container():
        st.markdown('<div class="card"><div class="section-title">SPX Forecast (08:30–15:30)</div><div class="hline"></div>', unsafe_allow_html=True)

        df_high  = build_fan_df("HIGH",  high_price,  high_time)
        df_close = build_fan_df("CLOSE", close_price, close_time)
        df_low   = build_fan_df("LOW",   low_price,   low_time)

        # Tables
        st.markdown("**High anchor fan**")
        st.dataframe(df_high, use_container_width=True, hide_index=True)
        st.markdown("**Close anchor fan**")
        st.dataframe(df_close, use_container_width=True, hide_index=True)
        st.markdown("**Low anchor fan**")
        st.dataframe(df_low, use_container_width=True, hide_index=True)

        # Charts (Altair default, Plotly optional)
        st.markdown("<div class='hline'></div>", unsafe_allow_html=True)
        st.markdown("**Visuals (zoom/pan)**")
        if use_plotly and PLOTLY_AVAILABLE:
            st.plotly_chart(plotly_fan_chart(df_high,  "High Anchor — Fan vs SPX", intraday_df), use_container_width=True)
            st.plotly_chart(plotly_fan_chart(df_close, "Close Anchor — Fan vs SPX", intraday_df), use_container_width=True)
            st.plotly_chart(plotly_fan_chart(df_low,   "Low Anchor — Fan vs SPX", intraday_df), use_container_width=True)
        else:
            st.altair_chart(altair_fan_chart(df_high,  "High Anchor — Fan vs SPX", intraday_df), use_container_width=True)
            st.altair_chart(altair_fan_chart(df_close, "Close Anchor — Fan vs SPX", intraday_df), use_container_width=True)
            st.altair_chart(altair_fan_chart(df_low,   "Low Anchor — Fan vs SPX", intraday_df), use_container_width=True)

# ===== Contract Line =====
with st.container():
    st.markdown('<div class="card"><div class="section-title">Contract Line</div><div class="hline"></div>', unsafe_allow_html=True)
    col1,col2,col3 = st.columns([1,1,1])
    with col1:
        st.markdown(f'<span class="subtle">Low-1</span>', unsafe_allow_html=True)
        low1_time  = st.time_input("Time", value=time(2,0), step=300, key="low1_time")
        low1_price = st.number_input("Price", value=10.00, step=TICK, min_value=0.0, key="low1_price")
    with col2:
        st.markdown(f'<span class="subtle">Low-2</span>', unsafe_allow_html=True)
        low2_time  = st.time_input("Time ", value=time(3,30), step=300, key="low2_time")
        low2_price = st.number_input("Price ", value=12.00, step=TICK, min_value=0.0, key="low2_price")
    with col3:
        line_label = st.selectbox("Label", ["Manual","Tuesday Play","Thursday Play"], index=0)
        rth_only   = st.toggle("RTH slots only", value=True)
    gen_contract = st.button("Calculate contract line", use_container_width=True, type="primary")

    if gen_contract:
        t1 = datetime.combine(forecast_date, low1_time)
        t2 = datetime.combine(forecast_date, low2_time)
        blocks = spx_blocks_between(t1, t2)
        if blocks == 0:
            st.warning("Low-1 and Low-2 are too close in SPX blocks. Increase separation.")
        else:
            slope = (low2_price - low1_price) / blocks
            st.session_state.contract = {"anchor_time": t1, "anchor_price": low1_price, "slope": slope, "label": line_label}

    contract = st.session_state.contract
    if contract["anchor_time"] and contract["slope"] is not None:
        cA,cB,cC,cD = st.columns(4)
        with cA: st.metric("Anchor", contract['anchor_time'].strftime('%H:%M'), f"${contract['anchor_price']:.2f}")
        with cB: st.metric("Slope (per block)", f"{contract['slope']:+.4f}")
        with cC: st.metric("Label", contract["label"])
        with cD: st.metric("Forecast Date", forecast_date.strftime("%Y-%m-%d"))

        slots = SPX_SLOTS if rth_only else ETH_SLOTS
        rows=[]
        for slot in slots:
            hh,mm = map(int, slot.split(":"))
            tdt = datetime.combine(forecast_date, time(hh,mm))
            blk = spx_blocks_between(contract["anchor_time"], tdt)
            proj= project(contract["anchor_price"], contract["slope"], blk)
            rows.append({"Time":slot,"Projected":round_to_tick(proj),"Blocks":blk})
        df_contract = pd.DataFrame(rows)
        st.dataframe(df_contract, use_container_width=True, hide_index=True)

        # Contract chart
        if use_plotly and PLOTLY_AVAILABLE:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_contract["Time"], y=df_contract["Projected"], name="Contract", line=dict(width=2, color="#7C3AED")))
            fig.update_layout(title="Contract Projection", height=320, margin=dict(l=10,r=10,t=40,b=20))
            fig.update_xaxes(rangeslider_visible=True, showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            ch = alt.Chart(df_contract).mark_line(strokeWidth=2, color="#7C3AED").encode(
                x=alt.X('Time:T', title=None), y=alt.Y('Projected:Q', title='Projected')
            ).properties(height=300).interactive()
            st.altair_chart(ch, use_container_width=True)

        # Real-time lookup
        lk1, lk2 = st.columns([1,2])
        with lk1:
            lookup_time = st.time_input("Lookup time", value=time(9,30), step=300, key="lookup_time")
        with lk2:
            tdt = datetime.combine(forecast_date, lookup_time)
            blk = spx_blocks_between(contract["anchor_time"], tdt)
            proj = project(contract["anchor_price"], contract["slope"], blk)
            st.success(f"Projected @ {lookup_time.strftime('%H:%M')} → ${round_to_tick(proj):.2f} · {blk} blocks")

# ===== Fibonacci (up-bounce only) =====
with st.container():
    st.markdown('<div class="card"><div class="section-title">Fibonacci Bounce (up-bounce only)</div><div class="hline"></div>', unsafe_allow_html=True)
    fb1,fb2,fb3,fb4 = st.columns([1,1,1,1])
    with fb1: fib_low  = st.number_input("Bounce low (contract)",  value=0.00, step=TICK, min_value=0.0)
    with fb2: fib_high = st.number_input("Bounce high (contract)", value=0.00, step=TICK, min_value=0.0)
    with fb3: fib_low_time = st.time_input("Bounce low time", value=time(9,30), step=300)
    with fb4: show_targets = st.toggle("Show 1.272 / 1.618 targets", value=True)

    if fib_high > fib_low > 0:
        lv = fib_levels(fib_low, fib_high)
        rows=[]
        for k in ["0.236","0.382","0.500","0.618","0.786","1.000"]:
            rows.append({"Level":k, "Price": f"${round_to_tick(lv[k]):.2f}", "Note": ("ALGO ENTRY" if k=="0.786" else "")})
        if show_targets:
            for k in ["1.272","1.618"]:
                rows.append({"Level":k, "Price": f"${round_to_tick(lv[k]):.2f}", "Note":"Target"})
        df_fib = pd.DataFrame(rows)
        st.dataframe(df_fib, use_container_width=True, hide_index=True)

        # Simple visual: levels vs price
        level_df = pd.DataFrame({
            "Level": ["0.236","0.382","0.500","0.618","0.786","1.000"] + (["1.272","1.618"] if show_targets else []),
            "Price": [lv["0.236"],lv["0.382"],lv["0.500"],lv["0.618"],lv["0.786"],lv["1.000"]] + ([lv["1.272"],lv["1.618"]] if show_targets else [])
        })
        if use_plotly and PLOTLY_AVAILABLE:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=level_df["Level"], y=level_df["Price"], marker=dict(color="#10B981")))
            fig.update_layout(title="Fibonacci Levels", height=320, margin=dict(l=10,r=10,t=40,b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            ch = alt.Chart(level_df).mark_bar().encode(
                x=alt.X("Level:N", title=None),
                y=alt.Y("Price:Q", title="Price"),
                color=alt.value("#10B981")
            ).properties(height=300).interactive()
            st.altair_chart(ch, use_container_width=True)

        # Next-30-minute confluence vs Contract Line
        next_30_time = (datetime.combine(forecast_date, fib_low_time) + timedelta(minutes=30)).time()
        key_0786 = round_to_tick(lv["0.786"])
        st.markdown("**Next-30-min confluence (vs. Contract Line)**")
        contract = st.session_state.contract
        if contract["anchor_time"] and contract["slope"] is not None:
            t_star = datetime.combine(forecast_date, next_30_time)
            blk = spx_blocks_between(contract["anchor_time"], t_star)
            c_proj = round_to_tick(project(contract["anchor_price"], contract["slope"], blk))
            delta = abs(c_proj - key_0786)
            pct = (delta / key_0786 * 100.0) if key_0786 else float("inf")
            grade = "Strong" if pct < 0.50 else ("Moderate" if pct <= 1.00 else "Weak")
            st.markdown(
                f"""
                <div class="card" style="padding:12px 16px;">
                  <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;">
                    <div style="font-weight:700;">Fib 0.786</div>
                    <div>Entry ${key_0786:.2f}</div>
                    <div class="subtle">•</div>
                    <div>Contract @ {next_30_time.strftime('%H:%M')} → <b>${c_proj:.2f}</b></div>
                    <div class="subtle">•</div>
                    <div>Δ ${delta:.2f} ({pct:.2f}%)</div>
                    <div class="subtle">•</div>
                    <div><b>{grade}</b></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.warning("Configure the Contract Line to enable confluence check.")

        # Simple R:R helper
        entry = key_0786
        stop  = round_to_tick(fib_low - TICK)
        tp1   = round_to_tick(fib_high)
        tp2   = round_to_tick(lv["1.272"]) if show_targets else None
        tp3   = round_to_tick(lv["1.618"]) if show_targets else None

        risk_col, rr_col = st.columns([1,3])
        with risk_col:
            risk_val = st.number_input("Assumed $ risk (per contract)", value=0.50, step=0.25, min_value=0.25)
        with rr_col:
            stop_dist = max(entry - stop, 0.0001)
            def rr(tp): return (tp - entry) / stop_dist if tp else None
            st.write(f"- Entry: ${entry:.2f} · Stop: ${stop:.2f} (one tick below low) · Risk/contract: ${risk_val:.2f}")
            st.write(f"- TP1 (back to high): ${tp1:.2f} → R:R {rr(tp1):.2f}")
            if show_targets:
                st.write(f"- TP2 (1.272): ${tp2:.2f} → R:R {rr(tp2):.2f}")
                st.write(f"- TP3 (1.618): ${tp3:.2f} → R:R {rr(tp3):.2f}")
    else:
        st.info("Enter bounce low < bounce high to compute levels.")

# ===== Exports =====
with st.container():
    st.markdown('<div class="card"><div class="section-title">Exports</div><div class="hline"></div>', unsafe_allow_html=True)
    exportables={}
    if st.session_state.get("forecasts_generated", False):
        exportables["SPX_High_Fan.csv"]  = locals().get("df_high", pd.DataFrame()).to_csv(index=False).encode()
        exportables["SPX_Close_Fan.csv"] = locals().get("df_close", pd.DataFrame()).to_csv(index=False).encode()
        exportables["SPX_Low_Fan.csv"]   = locals().get("df_low", pd.DataFrame()).to_csv(index=False).encode()
    if 'df_contract' in locals():
        exportables["Contract_Line.csv"] = df_contract.to_csv(index=False).encode()
    if 'df_fib' in locals():
        exportables["Fib_Levels.csv"] = df_fib.to_csv(index=False).encode()

    if exportables:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
            for fn,data in exportables.items():
                if data: zf.writestr(fn,data)
        st.download_button("Download all CSVs (.zip)", data=buf.getvalue(), file_name="marketlens_exports.zip", mime="application/zip", type="primary", use_container_width=True)

# ===== Footer =====
st.markdown(
    f"""
    <div class="card" style="text-align:center">
      <div style="font-weight:700">{APP_NAME}</div>
      <div class="subtle">SPX Forecast Console • v{VERSION} • Educational use only</div>
    </div>
    """,
    unsafe_allow_html=True
)
