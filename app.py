# ═══════════════════════════════════════════════════════════════════════════════
# 🕶️ MarketLens — SPX Forecast Console (One-File, Premium UI, Altair Charts)
# Spec: SPX-only • Fixed slopes • Auto-zoom charts (Altair) • Deep navy→charcoal
#       Upgraded Fibonacci & Contract tools • 12 visual UX enhancements
#       Optional Yahoo Finance summary (15m delay) with graceful fallback
#       No Plotly, No Matplotlib (Altair is built into Streamlit)
# Timezone note: America/Chicago (display text only; datetimes naive in code)
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import io
import json
import math
import textwrap
import zipfile
from datetime import datetime, date, time, timedelta

import pandas as pd
import numpy as np
import streamlit as st
import altair as alt  # ← Altair for interactive charts (no extra install needed)

# ──────────────────────────────────────────────────────────────────────────────
# APP METADATA / BRAND
# ──────────────────────────────────────────────────────────────────────────────
APP_NAME = "MarketLens"
PAGE_ICON = "🕶️"
VERSION = "3.1.0"

# ──────────────────────────────────────────────────────────────────────────────
# FIXED SLOPES (LOCKED)
# Descending/Entry (per 30-min SPX block); Ascending/Exit (per 30-min block)
# ──────────────────────────────────────────────────────────────────────────────
SPX_SLOPES_DOWN = {"HIGH": -0.2792, "CLOSE": -0.2792, "LOW": -0.2792}
SPX_SLOPES_UP   = {"HIGH": +0.3171,  "CLOSE": +0.3171,  "LOW": +0.3171}

# Tick size (SPX/ES-style): stops/targets/rounding
TICK = 0.25

# Anchor iconography/colors (professional palette)
ICON_HIGH  = "▲"  # green up-triangle
ICON_CLOSE = "■"  # steel-blue square
ICON_LOW   = "▼"  # red down-triangle

COLOR_HIGH  = "#16A34A"  # green
COLOR_CLOSE = "#2563EB"  # steel blue
COLOR_LOW   = "#DC2626"  # red
COLOR_ENTRY = "#1F2937"  # near-black gray for entry line
COLOR_EXIT  = "#475569"  # slate gray for exit line

# ──────────────────────────────────────────────────────────────────────────────
# VERBATIM SPX DOCS (kept exactly, as requested)
# ──────────────────────────────────────────────────────────────────────────────
SPX_GOLDEN_RULES = [
    "🚪 **Exit levels are exits - never entries**",
    "🧲 **Anchors are magnets, not timing signals - let price come to you**",
    "🎁 **The market will give you your entry - don't force it**",
    "🔄 **Consistency in process trumps perfection in prediction**",
    "❓ **When in doubt, stay out - there's always another trade**",
    "🏗️ **SPX ignores the full 16:00-17:00 maintenance block**"
]
SPX_ANCHOR_RULES = {
    "rth_breaks": [
        "📉 **30-min close below RTH entry anchor**: Price may retrace above anchor line but will fall below again shortly after",
        "🚫 **Don't chase the bounce**: Prepare for the inevitable breakdown",
        "⏱️ **Wait for confirmation**: Let the market give you the entry"
    ],
    "extended_hours": [
        "🌙 **Extended session weakness + recovery**: Use recovered anchor as buy signal in RTH",
        "📈 **Extended session anchors carry forward momentum** into regular trading hours",
        "📈 **Extended bounce of anchors carry forward momentum** into regular trading hours",
        "🎯 **Overnight anchor recovery**: Strong setup for next day strength"
    ],
    "mon_wed_fri": [
        "📅 **No touch of high, close, or low anchors** on Mon/Wed/Fri = Potential sell day later",
        "⏳ **Don't trade TO the anchor**: Let the market give you the entry",
        "✅ **Wait for price action confirmation** rather than anticipating touches"
    ],
    "fibonacci_bounce": [
        "📈 **SPX Line Touch + Bounce**: When SPX price touches line and bounces, contract follows the same pattern",
        "🎯 **0.786 Fibonacci Entry**: Contract retraces to 0.786 fib level (low to high of bounce) = major algo entry point",
        "⏰ **Next Hour Candle**: The 0.786 retracement typically occurs in the NEXT hour candle, not the same one",
        "💰 **High Probability**: Algos consistently enter at 0.786 level for profitable runs",
        "📊 **Setup Requirements**: Clear bounce off SPX line + identifiable low-to-high swing for fib calculation"
    ]
}
CONTRACT_STRATEGIES = {
    "tuesday_play": [
        "🎯 **Identify two overnight option low points** that rise $400-$500",
        "📐 **Use them to set Tuesday contract slope** (handled in SPX tab)",
        "⚡ **Tuesday contract setups often provide best mid-week momentum**"
    ],
    "thursday_play": [
        "💰 **If Wednesday's low premium was cheap**: Thursday low ≈ Wed low (buy-day)",
        "📉 **If Wednesday stayed pricey**: Thursday likely a put-day (avoid longs)",
        "🔄 **Wednesday pricing telegraphs Thursday direction**"
    ]
}
TIME_RULES = {
    "market_sessions": [
        "🕘 **9:30-10:00 AM**: Initial range, avoid FOMO entries",
        "🕙 **10:30-11:30 AM**: Institutional flow window, best entries",
        "🕐 **2:00-3:00 PM**: Final push time, momentum plays",
        "🕞 **3:30+ PM**: Scalps only, avoid new positions"
    ],
    "volume_patterns": [
        "📊 **Entry volume > 20-day average**: Strong conviction signal",
        "📉 **Declining volume on bounces**: Fade the move",
        "⚡ **Volume spike + anchor break**: High probability setup"
    ],
    "multi_timeframe": [
        "🎯 **5-min + 15-min + 1-hour** all pointing same direction = high conviction",
        "❓ **Conflicting timeframes** = wait for resolution",
        "📊 **Daily anchor + intraday setup** = strongest edge"
    ]
}
RISK_RULES = {
    "position_sizing": [
        "🎯 **Never risk more than 2% per trade**: Consistency beats home runs",
        "📈 **Scale into positions**: 1/3 initial, 1/3 confirmation, 1/3 momentum",
        "📅 **Reduce size on Fridays**: Weekend risk isn't worth it"
    ],
    "stop_strategy": [
        "🛑 **Hard stops at -15% for options**: No exceptions",
        "📈 **Trailing stops after +25%**: Protect profits aggressively",
        "🕞 **Time stops at 3:45 PM**: Avoid close volatility"
    ],
    "market_context": [
        "📊 **VIX above 25**: Reduce position sizes by 50%",
        "📈 **Major earnings week**: Avoid unrelated tickers",
        "📢 **FOMC/CPI days**: Trade post-announcement only (10:30+ AM)"
    ],
    "psychological": [
        "🛑 **3 losses in a row**: Step away for 1 hour minimum",
        "🎉 **Big win euphoria**: Reduce next position size by 50%",
        "😡 **Revenge trading**: Automatic day-end (no exceptions)"
    ],
    "performance_targets": [
        "🎯 **Win rate target: 55%+**: More important than individual trade size",
        "💰 **Risk/reward minimum: 1:1.5**: Risk $100 to make $150+",
        "📊 **Weekly P&L cap**: Stop after +20% or -10% weekly moves"
    ]
}

# ──────────────────────────────────────────────────────────────────────────────
# THEME & CSS (deep navy → charcoal, glass cards, gradient headers, print mode)
# ──────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
:root {
  --bg1:#0D1117; --bg2:#161B22; --card:#0f1521; --border:rgba(255,255,255,.08);
  --text:#E8EDF5; --muted:#A9B4C4; --shadow:0 10px 30px rgba(0,0,0,.25);
  --radius:16px; --accent:#1E293B; --focus:#2563EB; --good:#16A34A; --bad:#DC2626;
}
.stApp { background: linear-gradient(135deg, var(--bg1), var(--bg2)); color: var(--text); }
#MainMenu, footer, .stDeployButton { display:none !important; }

.header {
  display:flex; gap:.75rem; align-items:center; justify-content:space-between;
  padding: .9rem 1.1rem; border:1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow);
  background: linear-gradient(90deg, rgba(37,99,235,.08), rgba(30,41,59,.12));
  position: sticky; top: .5rem; z-index: 9;
}
.brand { font-weight:800; letter-spacing:.2px; }
.badge { padding:.2rem .6rem; border:1px solid var(--border); border-radius:999px; font-size:.8rem; opacity:.9; }

.card {
  background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
  border: 1px solid var(--border); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: 1rem 1rem; margin:.6rem 0 1rem 0;
  backdrop-filter: blur(6px);
}
.card .bar { height: 3px; border-radius: 3px; margin-bottom:.6rem; opacity:.9; }
.bar-green { background: linear-gradient(90deg, #16A34A, rgba(22,163,74,.2)); }
.bar-blue  { background: linear-gradient(90deg, #2563EB, rgba(37,99,235,.2)); }
.bar-red   { background: linear-gradient(90deg, #DC2626, rgba(220,38,38,.2)); }

.section-title { display:flex; align-items:center; gap:.6rem; font-weight:700; }
.icon { display:inline-flex; width:28px; height:28px; align-items:center; justify-content:center;
  border-radius:6px; background: rgba(255,255,255,.06); border:1px solid var(--border); }

.kv { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap:.6rem; }

.pill { padding:.1rem .5rem; border-radius:999px; border:1px solid var(--border); font-weight:600; font-size:.8rem; }
.good { color: var(--good); } .bad { color: var(--bad); }

.table-wrap { border-radius: var(--radius); overflow:hidden; border:1px solid var(--border); }
.small { font-size:.9rem; color: var(--muted); }

.spinner { width:18px; height:18px; border-radius:50%;
  border:2px solid rgba(255,255,255,.25); border-top-color:#2563EB; animation:spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.print-clean * { box-shadow:none !important; background: #fff !important; color: #111 !important; }
</style>
"""

# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────
RTH_START = time(8,30)
RTH_END   = time(15,30)

def spx_blocks_between(t1: datetime, t2: datetime) -> int:
    """30-min blocks between t1 and t2 skipping the full 16:00-17:00 block."""
    if t2 < t1:
        t1, t2 = t2, t1
    blocks = 0
    cur = t1
    while cur < t2:
        nxt = cur + timedelta(minutes=30)
        # Skip any interval that starts within 16:00-16:59
        if cur.hour != 16:
            blocks += 1
        cur = nxt
    return blocks

def make_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    cur = datetime(2025,1,1,start.hour,start.minute)
    stop= datetime(2025,1,1,end.hour,end.minute)
    out=[]
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
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
        "0.236": high - R*0.236,
        "0.382": high - R*0.382,
        "0.500": high - R*0.500,
        "0.618": high - R*0.618,
        "0.786": high - R*0.786,
        "1.000": low,
        "1.272": high + R*0.272,
        "1.618": high + R*0.618,
    }

def easter_date(y:int) -> date:
    a=y%19; b=y//100; c=y%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    month=(h+l-7*m+114)//31; day=((h+l-7*m+114)%31)+1
    return date(y, month, day)

def us_market_holidays(year:int) -> set[date]:
    def nth_weekday(month, weekday, n):
        d = date(year, month, 1)
        while d.weekday() != weekday: d += timedelta(days=1)
        return d + timedelta(days=7*(n-1))
    def last_weekday(month, weekday):
        d = date(year, month+1, 1) - timedelta(days=1)
        while d.weekday() != weekday: d -= timedelta(days=1)
        return d
    hol=set()
    d=date(year,1,1); hol.add(d if d.weekday()<5 else (d+timedelta(days=1) if d.weekday()==5 else d+timedelta(days=2)))
    hol.add(nth_weekday(1,0,3))  # MLK
    hol.add(nth_weekday(2,0,3))  # Presidents'
    hol.add(easter_date(year)-timedelta(days=2))  # Good Friday
    hol.add(last_weekday(5,0))   # Memorial
    d=date(year,6,19); hol.add(d if d.weekday()<5 else (d-timedelta(days=1) if d.weekday()==5 else d+timedelta(days=1)))
    d=date(year,7,4);  hol.add(d if d.weekday()<5 else (d-timedelta(days=1) if d.weekday()==5 else d+timedelta(days=1)))
    hol.add(nth_weekday(9,0,1))  # Labor
    hol.add(nth_weekday(11,3,4)) # Thanksgiving
    d=date(year,12,25); hol.add(d if d.weekday()<5 else (d-timedelta(days=1) if d.weekday()==5 else d+timedelta(days=1)))
    return hol

# ──────────────────────────────────────────────────────────────────────────────
# STATE INIT
# ──────────────────────────────────────────────────────────────────────────────
if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.theme = "Dark"
    st.session_state.locked_anchors = False
    st.session_state.forecasts_generated = False
    st.session_state.contract = {"anchor_time": None, "anchor_price": None, "slope": None, "label": "Manual"}
    st.session_state.saved_snapshot = None
    st.session_state.show_charts = True
    st.session_state.print_mode = False
    st.session_state.collapse_mem = {"fib": False, "contract": False, "fans": True}

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG / CSS
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title=f"{APP_NAME} — SPX Console", page_icon=PAGE_ICON, layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# HEADER + (Optional) Yahoo Finance Today Summary (no status pill)
# ──────────────────────────────────────────────────────────────────────────────
def get_spx_summary():
    try:
        import yfinance as yf
        @st.cache_data(ttl=60)
        def _fetch():
            t = yf.Ticker("^GSPC")
            intraday = t.history(period="1d", interval="1m")
            daily = t.history(period="5d", interval="1d")
            return intraday, daily
        intraday, daily = _fetch()
        if intraday is not None and len(intraday):
            last = intraday.iloc[-1]
            price = float(last["Close"])
            prev_close = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else price
            chg = price - prev_close
            pct = (chg / prev_close * 100) if prev_close else 0.0
            today_high = float(daily["High"].iloc[-1]) if len(daily) else price
            today_low  = float(daily["Low"].iloc[-1])  if len(daily) else price
            return {"ok": True, "price": price, "chg": chg, "pct": pct, "high": today_high, "low": today_low}
        return {"ok": False, "reason": "No intraday data"}
    except Exception:
        return {"ok": False, "reason": "Offline/No yfinance"}

with st.container():
    st.markdown(
        f"""
        <div class="header">
          <div style="display:flex;align-items:center;gap:.7rem;">
            <span class="brand">{PAGE_ICON} <span style="font-weight:900;">{APP_NAME}</span></span>
            <span class="badge">v{VERSION}</span>
            <span class="badge">TZ: America/Chicago</span>
          </div>
          <div id="clock" class="small">{" "}</div>
        </div>
        """, unsafe_allow_html=True
    )

sumy = get_spx_summary()
if sumy.get("ok"):
    color_bg = "rgba(22,163,74,.12)" if sumy["chg"]>=0 else "rgba(220,38,38,.12)"
    chg_txt = f"{sumy['chg']:+.2f} ({sumy['pct']:+.2f}%)"
    st.markdown(
        f"""
        <div class="card" style="padding:.6rem 1rem; background:{color_bg};">
          <div style="display:flex;align-items:center;gap:1rem;">
            <div><b>SPX</b> {sumy['price']:.2f}</div>
            <div class="{ 'good' if sumy['chg']>=0 else 'bad' }">{chg_txt}</div>
            <div class="small" style="margin-left:auto;">H:{sumy['high']:.2f} · L:{sumy['low']:.2f}</div>
          </div>
        </div>
        """, unsafe_allow_html=True
    )
else:
    st.markdown(
        """
        <div class="card" style="padding:.6rem 1rem;">
          <div style="display:flex;align-items:center;gap:.6rem;">
            <div class="spinner"></div>
            <div class="small">Live summary unavailable · using session inputs</div>
          </div>
        </div>
        """, unsafe_allow_html=True
    )

# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR — Theme, Date, Docs, Utilities
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("🎛️ Display")
    theme_choice = st.radio("Theme", ["Dark","Light"], horizontal=True, index=0 if st.session_state.theme=="Dark" else 1)
    st.session_state.theme = theme_choice
    st.session_state.print_mode = st.toggle("🖨️ Print-Friendly Mode", value=st.session_state.print_mode)
    if st.session_state.print_mode:
        st.markdown('<style>.stApp{background:#fff!important;color:#111!important}.card{background:#fff!important;border-color:#ddd!important}</style>', unsafe_allow_html=True)

    st.divider()
    st.subheader("📅 Forecast Date")
    forecast_date = st.date_input("Target Session", value=date.today() + timedelta(days=1))
    wd = forecast_date.weekday()
    day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    st.info(f"**{day_names[wd]}** session • Anchors use **previous day** of this target date.")
    warn=[]
    if wd>=5: warn.append("Weekend selected.")
    try:
        if forecast_date in us_market_holidays(forecast_date.year): warn.append("U.S. market holiday.")
    except Exception: pass
    if warn: st.warning(" ".join(warn))

    st.divider()
    st.subheader("📚 SPX Docs")
    with st.expander("🔔 Golden Rules", expanded=False):
        for r in SPX_GOLDEN_RULES: st.markdown(r)
    with st.expander("⚓ Anchor Trading Rules", expanded=False):
        st.markdown("**📈 RTH Anchor Breaks**")
        for r in SPX_ANCHOR_RULES["rth_breaks"]: st.markdown(f"• {r}")
        st.markdown("**🌙 Extended Hours**")
        for r in SPX_ANCHOR_RULES["extended_hours"]: st.markdown(f"• {r}")
        st.markdown("**📅 Mon/Wed/Fri Rules**")
        for r in SPX_ANCHOR_RULES["mon_wed_fri"]: st.markdown(f"• {r}")
        st.markdown("**🧮 Fibonacci Bounce**")
        for r in SPX_ANCHOR_RULES["fibonacci_bounce"]: st.markdown(f"• {r}")
    with st.expander("📏 Contract Strategies", expanded=False):
        st.markdown("**📊 Tuesday Contract Play**")
        for r in CONTRACT_STRATEGIES["tuesday_play"]: st.markdown(f"• {r}")
        st.markdown("**📈 Thursday Contract Play**")
        for r in CONTRACT_STRATEGIES["thursday_play"]: st.markdown(f"• {r}")
    with st.expander("⏰ Time & Volume", expanded=False):
        st.markdown("**🕐 Market Sessions**")
        for r in TIME_RULES["market_sessions"]: st.markdown(f"• {r}")
        st.markdown("**📊 Volume Patterns**")
        for r in TIME_RULES["volume_patterns"]: st.markdown(f"• {r}")
        st.markdown("**🎯 Multi-Timeframe**")
        for r in TIME_RULES["multi_timeframe"]: st.markdown(f"• {r}")
    with st.expander("🛡️ Risk Rules", expanded=False):
        st.markdown("**📏 Position Sizing**")
        for r in RISK_RULES["position_sizing"]: st.markdown(f"• {r}")
        st.markdown("**🛑 Stop Strategy**")
        for r in RISK_RULES["stop_strategy"]: st.markdown(f"• {r}")
        st.markdown("**📊 Market Context**")
        for r in RISK_RULES["market_context"]: st.markdown(f"• {r}")
        st.markdown("**🧠 Psychology**")
        for r in RISK_RULES["psychological"]: st.markdown(f"• {r}")
        st.markdown("**🎯 Performance Targets**")
        for r in RISK_RULES["performance_targets"]: st.markdown(f"• {r}")

    st.divider()
    st.subheader("🧰 Utilities")
    colA, colB = st.columns(2)
    with colA:
        if st.button("Reset Session", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k not in ["init","theme","print_mode","collapse_mem"]:
                    del st.session_state[k]
            st.rerun()
    with colB:
        st.session_state.show_charts = st.toggle("Sparklines", value=st.session_state.show_charts)

# ──────────────────────────────────────────────────────────────────────────────
# QUICK RULES POPOVER (top 3)
# ──────────────────────────────────────────────────────────────────────────────
_pop = getattr(st, "popover", None)
if _pop:
    with st.popover("🔔 Quick Rules"):
        for r in SPX_GOLDEN_RULES[:3]: st.markdown(r)
else:
    with st.expander("🔔 Quick Rules", expanded=False):
        for r in SPX_GOLDEN_RULES[:3]: st.markdown(r)

# ──────────────────────────────────────────────────────────────────────────────
# FIXED SLOPES (READ-ONLY)
# ──────────────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown(f'<div class="card"><div class="bar-blue"></div><div class="section-title"><span class="icon">⚙️</span>Fixed Slopes (per 30-min block)</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Entry (Descending)**  \n{ICON_HIGH} High: `{SPX_SLOPES_DOWN['HIGH']:+.4f}`  \n{ICON_CLOSE} Close: `{SPX_SLOPES_DOWN['CLOSE']:+.4f}`  \n{ICON_LOW} Low: `{SPX_SLOPES_DOWN['LOW']:+.4f}`")
    with c2:
        st.markdown(f"**Exit (Ascending)**  \n{ICON_HIGH} High→UP: `{SPX_SLOPES_UP['HIGH']:+.4f}`  \n{ICON_CLOSE} Close→UP: `{SPX_SLOPES_UP['CLOSE']:+.4f}`  \n{ICON_LOW} Low→UP: `{SPX_SLOPES_UP['LOW']:+.4f}`")

# ──────────────────────────────────────────────────────────────────────────────
# ANCHOR INPUTS (previous day of target date)
# ──────────────────────────────────────────────────────────────────────────────
def anchor_inputs(prefix: str, default_price: float, default_time: time):
    price = st.number_input(f"{prefix} Price", value=float(default_price), step=0.1, min_value=0.0, key=f"{prefix}_price")
    when  = st.time_input(f"{prefix} Time",  value=default_time, step=300, key=f"{prefix}_time")
    return price, when

with st.container():
    st.markdown(f'<div class="card"><div class="bar-blue"></div><div class="section-title"><span class="icon">⚓</span>SPX Anchors (Previous Day)</div>', unsafe_allow_html=True)
    colH, colC, colL = st.columns(3)
    with colH:
        st.markdown(f'<div class="bar-green"></div><div class="section-title"><span class="icon" style="border-color:{COLOR_HIGH};color:{COLOR_HIGH}">{ICON_HIGH}</span><span>High Anchor</span></div>', unsafe_allow_html=True)
        high_price, high_time = anchor_inputs("High", 6185.80, time(11,30))
    with colC:
        st.markdown(f'<div class="bar-blue"></div><div class="section-title"><span class="icon" style="border-color:{COLOR_CLOSE};color:{COLOR_CLOSE}">{ICON_CLOSE}</span><span>Close Anchor</span></div>', unsafe_allow_html=True)
        close_price, close_time = anchor_inputs("Close", 6170.20, time(15,0))
    with colL:
        st.markdown(f'<div class="bar-red"></div><div class="section-title"><span class="icon" style="border-color:{COLOR_LOW};color:{COLOR_LOW}">{ICON_LOW}</span><span>Low Anchor</span></div>', unsafe_allow_html=True)
        low_price, low_time = anchor_inputs("Low", 6130.40, time(13,30))

    colA, colB = st.columns([1,1])
    with colA:
        if not st.session_state.get("locked_anchors", False):
            if st.button("🔒 Lock Anchors", use_container_width=True):
                st.session_state.locked_anchors = True
        else:
            if st.button("✏️ Edit Anchors", use_container_width=True):
                st.session_state.locked_anchors = False
    with colB:
        generate = st.button("🚀 Generate Forecast", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# FORECAST (Auto-zoom charts with Altair)
# ──────────────────────────────────────────────────────────────────────────────
def build_fan_df(anchor_label: str, anchor_price: float, anchor_time: time) -> pd.DataFrame:
    rows=[]
    anchor_dt = datetime.combine(forecast_date - timedelta(days=1), anchor_time)
    for slot in SPX_SLOTS:
        hh, mm = map(int, slot.split(":"))
        tdt = datetime.combine(forecast_date, time(hh, mm))
        blocks = spx_blocks_between(anchor_dt, tdt)
        entry = project(anchor_price, SPX_SLOPES_DOWN[anchor_label], blocks)
        exit_ = project(anchor_price, SPX_SLOPES_UP[anchor_label],   blocks)
        rows.append({"Time": slot, "Entry": entry, "Exit": exit_, "Blocks": blocks, "Δ from Anchor": entry - anchor_price})
    return pd.DataFrame(rows)

def plot_fan(df: pd.DataFrame, title: str, color_main: str):
    # Auto-zoom (pad 5%)
    y_vals = pd.concat([df["Entry"], df["Exit"]])
    ymin, ymax = float(y_vals.min()), float(y_vals.max())
    pad = max(1.0, (ymax - ymin) * 0.05)
    y_domain = [ymin - pad, ymax + pad]

    # Long-form for Altair
    df_long = pd.melt(
        df[["Time", "Entry", "Exit"]],
        id_vars=["Time"],
        value_vars=["Entry", "Exit"],
        var_name="Series",
        value_name="Value"
    )
    time_sort = list(df["Time"])
    chart = (
        alt.Chart(df_long)
        .mark_line(point=False)
        .encode(
            x=alt.X("Time:N", sort=time_sort, axis=alt.Axis(labelAngle=45)),
            y=alt.Y("Value:Q", scale=alt.Scale(domain=y_domain)),
            color=alt.Color(
                "Series:N",
                scale=alt.Scale(domain=["Entry", "Exit"], range=[COLOR_ENTRY, COLOR_EXIT]),
                legend=alt.Legend(title=None)
            ),
            strokeDash=alt.StrokeDash(
                "Series:N",
                scale=alt.Scale(domain=["Entry", "Exit"], range=[[1, 0], [6, 3]])
            ),
            tooltip=["Time:N", "Series:N", alt.Tooltip("Value:Q", format=".2f")],
        )
        .properties(title=title, height=220)
        .configure_title(color=color_main, fontSize=12)
        .configure_axis(grid=True, gridOpacity=0.15)
    )
    st.altair_chart(chart, use_container_width=True)

if generate or st.session_state.get("forecasts_generated", False):
    st.session_state.forecasts_generated = True
    st.session_state.last_generate_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with st.container():
        st.markdown(f'<div class="card"><div class="bar-blue"></div><div class="section-title"><span class="icon">📊</span>SPX Forecast Fans (RTH 08:30–15:30)</div>', unsafe_allow_html=True)
        # High
        df_high = build_fan_df("HIGH", high_price, high_time)
        if st.session_state.show_charts: plot_fan(df_high, f"{ICON_HIGH} High Anchor Fan", COLOR_HIGH)
        st.dataframe(df_high.round({"Entry":2,"Exit":2,"Δ from Anchor":2}), use_container_width=True, hide_index=True)

        # Close
        df_close = build_fan_df("CLOSE", close_price, close_time)
        if st.session_state.show_charts: plot_fan(df_close, f"{ICON_CLOSE} Close Anchor Fan", COLOR_CLOSE)
        st.dataframe(df_close.round({"Entry":2,"Exit":2,"Δ from Anchor":2}), use_container_width=True, hide_index=True)

        # Low
        df_low = build_fan_df("LOW", low_price, low_time)
        if st.session_state.show_charts: plot_fan(df_low, f"{ICON_LOW} Low Anchor Fan", COLOR_LOW)
        st.dataframe(df_low.round({"Entry":2,"Exit":2,"Δ from Anchor":2}), use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────────────────────────────────────
# CONTRACT LINE — Two-point slope (SPX blocks), optional RTH-only slots
# ──────────────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown(f'<div class="card"><div class="bar-blue"></div><div class="section-title"><span class="icon">📏</span>Contract Line</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        st.markdown("**🎯 Low-1 Point**")
        low1_time = st.time_input("Time", value=time(2,0), step=300, key="low1_time")
        low1_price= st.number_input("Price", value=10.00, step=TICK, min_value=0.0, key="low1_price")
    with col2:
        st.markdown("**🎯 Low-2 Point**")
        low2_time = st.time_input("Time ", value=time(3,30), step=300, key="low2_time")
        low2_price= st.number_input("Price ", value=12.00, step=TICK, min_value=0.0, key="low2_price")
    with col3:
        line_label = st.selectbox("Label", ["Manual","Tuesday Play","Thursday Play"], index=0)
        rth_only = st.toggle("RTH slots only", value=True)
    gen_contract = st.button("⚡ Calculate Contract Line", use_container_width=True)

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
        cA, cB, cC, cD = st.columns(4)
        with cA: st.metric("Anchor", contract['anchor_time'].strftime('%H:%M'), f"${contract['anchor_price']:.2f}")
        with cB: st.metric("Slope (per block)", f"{contract['slope']:+.4f}")
        with cC: st.metric("Label", contract["label"])
        with cD: st.metric("Forecast Date", forecast_date.strftime("%Y-%m-%d"))

        slots = SPX_SLOTS if rth_only else ETH_SLOTS
        rows=[]
        for slot in slots:
            hh, mm = map(int, slot.split(":"))
            tdt = datetime.combine(forecast_date, time(hh, mm))
            blk = spx_blocks_between(contract["anchor_time"], tdt)
            proj = project(contract["anchor_price"], contract["slope"], blk)
            rows.append({"Time":slot,"Projected":round_to_tick(proj),"Blocks":blk,"Δ from Anchor": round(proj - contract["anchor_price"],2)})
        df_contract = pd.DataFrame(rows)

        # Altair chart (auto-zoom)
        if st.session_state.show_charts:
            y = df_contract["Projected"]
            ymin, ymax = float(y.min()), float(y.max())
            pad = max(TICK, (ymax - ymin) * 0.05)
            y_domain = [ymin - pad, ymax + pad]

            time_sort = list(df_contract["Time"])
            chart = (
                alt.Chart(df_contract)
                .mark_line()
                .encode(
                    x=alt.X("Time:N", sort=time_sort, axis=alt.Axis(labelAngle=45)),
                    y=alt.Y("Projected:Q", scale=alt.Scale(domain=y_domain)),
                    color=alt.value(COLOR_CLOSE),
                    tooltip=[
                        "Time:N",
                        alt.Tooltip("Projected:Q", format=".2f"),
                        "Blocks:Q",
                        alt.Tooltip("Δ from Anchor:Q", format=".2f"),
                    ],
                )
                .properties(title="Contract Projection", height=220)
                .configure_axis(grid=True, gridOpacity=0.15)
            )
            st.altair_chart(chart, use_container_width=True)

        st.dataframe(df_contract, use_container_width=True, hide_index=True)

        # Real-time lookup
        lk1, lk2 = st.columns([1,2])
        with lk1:
            lookup_time = st.time_input("🕐 Lookup Time", value=time(9,30), step=300, key="lookup_time")
        with lk2:
            tdt = datetime.combine(forecast_date, lookup_time)
            blk = spx_blocks_between(contract["anchor_time"], tdt)
            proj= project(contract["anchor_price"], contract["slope"], blk)
            st.success(f"Projected @ {lookup_time.strftime('%H:%M')} → **${round_to_tick(proj):.2f}** · {blk} blocks · Δ {proj - contract['anchor_price']:+.2f}")

# ──────────────────────────────────────────────────────────────────────────────
# FIBONACCI (Up-bounce only) — 0.786 entry, TP1 back to high, TP2 1.272, TP3 1.618
# Stop = one tick (0.25) below bounce low
# ──────────────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown(f'<div class="card"><div class="bar-blue"></div><div class="section-title"><span class="icon">📈</span>Fibonacci Bounce (Up-Bounce Only)</div>', unsafe_allow_html=True)
    fb1, fb2, fb3, fb4 = st.columns([1,1,1,1])
    with fb1: fib_low  = st.number_input("Bounce Low (Contract)",  value=0.00, step=TICK, min_value=0.0)
    with fb2: fib_high = st.number_input("Bounce High (Contract)", value=0.00, step=TICK, min_value=0.0)
    with fb3: fib_low_time = st.time_input("Bounce Low Time", value=time(9,30), step=300)
    with fb4: show_targets = st.toggle("Show Targets (1.272 / 1.618)", value=True)

    if fib_high > fib_low > 0:
        levels = fib_levels(fib_low, fib_high)
        rows=[]
        for k in ["0.236","0.382","0.500","0.618","0.786","1.000"]:
            price = round_to_tick(levels[k])
            rows.append({"Level":k, "Price": f"${price:.2f}", "Note": ("⭐ ALGO ENTRY" if k=="0.786" else "")})
        if show_targets:
            for k in ["1.272","1.618"]:
                rows.append({"Level":k, "Price": f"${round_to_tick(levels[k]):.2f}", "Note":"Target"})
        df_fib = pd.DataFrame(rows)
        st.dataframe(df_fib, use_container_width=True, hide_index=True)

        # Next-hour confluence vs Contract Line
        nh_time = (datetime.combine(forecast_date, fib_low_time) + timedelta(hours=1)).time()
        key_0786 = round_to_tick(levels["0.786"])
        st.markdown("**Next-Hour Confluence (vs Contract Line)**")
        contract = st.session_state.contract
        if contract["anchor_time"] and contract["slope"] is not None:
            t_star = datetime.combine(forecast_date, nh_time)
            blk = spx_blocks_between(contract["anchor_time"], t_star)
            c_proj = round_to_tick(project(contract["anchor_price"], contract["slope"], blk))
            delta = abs(c_proj - key_0786)
            pct = (delta / key_0786 * 100.0) if key_0786 else float('inf')
            badge = "🟢 **Strong**" if pct < 0.5 else ("🟡 **Moderate**" if pct <= 1.0 else "🟠 **Weak**")
            st.info(f"Fib 0.786: **${key_0786:.2f}** · Contract @ {nh_time.strftime('%H:%M')}: **${c_proj:.2f}** · Δ=${delta:.2f} ({pct:.2f}%) → {badge}")
        else:
            st.warning("Configure the Contract Line to enable confluence check.")

        # Entry/Stop/Targets
        entry = key_0786
        stop  = round_to_tick(fib_low - TICK)
        tp1   = round_to_tick(levels["1.000"] + (levels["1.000"] - fib_low) + (fib_high - fib_low))  # equals back to high
        # The line above is equivalent to fib_high, but left expanded for clarity. We still set to high directly:
        tp1   = round_to_tick(fib_high)
        tp2   = round_to_tick(levels["1.272"]) if show_targets else None
        tp3   = round_to_tick(levels["1.618"]) if show_targets else None

        risk_col, rr_col = st.columns([1,3])
        with risk_col:
            risk_val = st.number_input("Assumed $ Risk (per contract)", value=0.50, step=0.25, min_value=0.25)
        with rr_col:
            stop_dist = max(entry - stop, 0.0001)
            def rr(tp): return (tp - entry) / stop_dist if tp else None
            st.write(f"- Entry: **${entry:.2f}** · Stop: **${stop:.2f}** (one tick below low) · Risk/contract: **${risk_val:.2f}**")
            st.write(f"- TP1 (Back to High): **${tp1:.2f}** → R:R **{rr(tp1):.2f}**")
            if show_targets:
                st.write(f"- TP2 (1.272): **${tp2:.2f}** → R:R **{rr(tp2):.2f}**")
                st.write(f"- TP3 (1.618): **${tp3:.2f}** → R:R **{rr(tp3):.2f}**")
    else:
        st.info("Enter **Bounce Low < Bounce High** to compute Fib levels.")

# ──────────────────────────────────────────────────────────────────────────────
# SNAPSHOTS & EXPORTS
# ──────────────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown(f'<div class="card"><div class="bar-blue"></div><div class="section-title"><span class="icon">🧩</span>Workflows & Snapshots</div>', unsafe_allow_html=True)
    snap_col1, snap_col2 = st.columns(2)
    with snap_col1:
        if st.button("💾 Save Session Snapshot", use_container_width=True):
            snapshot = {
                "forecast_date": str(forecast_date),
                "anchors": {
                    "high": {"price": high_price, "time": high_time.strftime("%H:%M")},
                    "close":{"price": close_price,"time": close_time.strftime("%H:%M")},
                    "low":  {"price": low_price,  "time": low_time.strftime("%H:%M")},
                },
                "contract": {
                    "low1_time": st.session_state.get("low1_time", time(2,0)).strftime("%H:%M"),
                    "low1_price": st.session_state.get("low1_price", 10.0),
                    "low2_time": st.session_state.get("low2_time", time(3,30)).strftime("%H:%M"),
                    "low2_price": st.session_state.get("low2_price", 12.0),
                    "label": st.session_state.contract.get("label","Manual")
                },
                "fib": {
                    "low": fib_low,
                    "high": fib_high,
                    "low_time": fib_low_time.strftime("%H:%M"),
                    "show_targets": show_targets
                }
            }
            bio = io.BytesIO(json.dumps(snapshot, indent=2).encode())
            st.download_button("⬇️ Download Snapshot (.json)", data=bio.getvalue(), file_name="marketlens_snapshot.json", mime="application/json", use_container_width=True)
    with snap_col2:
        uploaded = st.file_uploader("📂 Load Snapshot (.json)", type=["json"])
        if uploaded:
            try:
                data = json.loads(uploaded.read().decode())
                st.session_state["High_price"]  = float(data["anchors"]["high"]["price"])
                st.session_state["High_time"]   = datetime.strptime(data["anchors"]["high"]["time"], "%H:%M").time()
                st.session_state["Close_price"] = float(data["anchors"]["close"]["price"])
                st.session_state["Close_time"]  = datetime.strptime(data["anchors"]["close"]["time"], "%H:%M").time()
                st.session_state["Low_price"]   = float(data["anchors"]["low"]["price"])
                st.session_state["Low_time"]    = datetime.strptime(data["anchors"]["low"]["time"], "%H:%M").time()
                st.success("Snapshot loaded. Re-generate to refresh tables.")
            except Exception as e:
                st.error(f"Failed to load snapshot: {e}")

    # Export all CSVs
    exportables={}
    if st.session_state.get("forecasts_generated", False):
        exportables["SPX_High_Fan.csv"]  = df_high.round(2).to_csv(index=False).encode()
        exportables["SPX_Close_Fan.csv"] = df_close.round(2).to_csv(index=False).encode()
        exportables["SPX_Low_Fan.csv"]   = df_low.round(2).to_csv(index=False).encode()
    if st.session_state.contract["anchor_time"] and st.session_state.contract["slope"] is not None:
        exportables["Contract_Line.csv"] = df_contract.round(2).to_csv(index=False).encode()
    if 'df_fib' in locals():
        exportables["Fib_Levels.csv"] = df_fib.to_csv(index=False).encode()
    if exportables:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn, data in exportables.items(): zf.writestr(fn, data)
        st.download_button("⬇️ Export All CSVs (zip)", data=buf.getvalue(), file_name="marketlens_exports.zip", mime="application/zip", use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="card" style="text-align:center;">
      <div><b>{APP_NAME}</b> • SPX Forecast Console • v{VERSION}</div>
      <div class="small">Disclaimer: Educational/analysis use only. Not financial advice.</div>
    </div>
    """, unsafe_allow_html=True
)

