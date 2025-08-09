# ═══════════════════════════════════════════════════════════════════════════════
# 📈 Dr Didy SPX Forecast – SPX-Only Console (One-File Build)
# Spec: fixed slopes (no sliders), SPX-only, modern UI, upgraded Fib & Contract tools,
#       sidebar Docs (verbatim), workflow & export utilities, no Plotly, fast + legible.
# Timezone context: America/Chicago (displayed for clarity; naive datetimes in code).
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import io
import json
import math
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta

import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# APP METADATA
# ──────────────────────────────────────────────────────────────────────────────
PAGE_TITLE = "Dr Didy SPX Forecast"
PAGE_ICON = "📈"
VERSION = "2.0.0-spx-only"

# ──────────────────────────────────────────────────────────────────────────────
# FIXED SLOPES (LOCKED; NOT ADJUSTABLE IN UI)
# Descending/Entry (per 30-min SPX block); Ascending/Exit (per 30-min SPX block)
# ──────────────────────────────────────────────────────────────────────────────
SPX_SLOPES_DOWN = {
    "HIGH": -0.2792,
    "CLOSE": -0.2792,
    "LOW": -0.2792,
}
SPX_SLOPES_UP = {
    "HIGH": +0.3171,   # Ascending/Exit slope drawn from prior-day high
    "CLOSE": +0.3171,  # Ascending/Exit slope drawn from prior-day close
    "LOW": +0.3171,    # Ascending/Exit slope drawn from prior-day low
}

# ──────────────────────────────────────────────────────────────────────────────
# VERBATIM SPX DOCS (kept exactly as provided)
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
# THEME & CSS (modern, minimal, fast)
# ──────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
:root {
  --radius: 16px;
  --shadow: 0 6px 24px rgba(0,0,0,0.15);
  --ink: #0b1220; --ink-2:#0e1217; --text:#e6eaf2;
  --ink-light:#f5f7fb; --text-dark:#0b1220;
  --acc-blue:#60a5fa; --acc-violet:#a78bfa; --acc-green:#22c55e; --acc-amber:#f59e0b;
}
html, body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Inter, "Helvetica Neue", Arial, "Apple Color Emoji","Segoe UI Emoji"; }
.stApp[data-theme="Neo Dark"] { background: linear-gradient(135deg, var(--ink) 0%, var(--ink-2) 100%); color: var(--text); }
.stApp[data-theme="Neo Light"] { background: #fbfcfe; color: #0f172a; }
#MainMenu, footer, .stDeployButton { display:none!important; }

.header {
  border-radius: var(--radius);
  padding: 1.25rem 1.25rem;
  box-shadow: var(--shadow);
  position: sticky; top: 0.5rem; z-index: 9;
  background: linear-gradient(90deg, rgba(96,165,250,.12), rgba(167,139,250,.12));
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(6px);
}
.badge {
  display:inline-flex; align-items:center; gap:.5rem;
  padding:.25rem .6rem; border-radius:999px; font-size:.85rem; font-weight:600;
  border:1px solid rgba(255,255,255,0.2);
}
.section {
  border-radius: var(--radius); padding: 1rem 1rem; margin: .75rem 0 1rem 0;
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.12);
  box-shadow: var(--shadow);
}
.section.light {
  background: rgba(15,23,42,.04); border: 1px solid rgba(2,6,23,.08);
}
.h-rule { height:1px; background: rgba(255,255,255,.12); margin:.75rem 0 1rem 0; }
.h-rule.light { background: rgba(2,6,23,.08); }
.kv { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap:.5rem; }
.pill { padding:.1rem .5rem; border-radius:999px; font-weight:600; font-size:.8rem; border:1px solid rgba(255,255,255,.18); }
.ok { color:#16a34a; } .warn { color:#d97706; } .err { color:#dc2626; }
.table-wrap { border-radius: var(--radius); overflow:hidden; border: 1px solid rgba(255,255,255,.12); }
.small { font-size:.85rem; opacity:.85; }
.footer {
  border-radius: var(--radius);
  border: 1px solid rgba(255,255,255,.12);
  padding: 1rem; text-align:center; opacity:.9;
}
</style>
"""

# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────
RTH_START = time(8, 30)   # 08:30
RTH_END   = time(15, 30)  # 15:30

def spx_blocks_between(t1: datetime, t2: datetime) -> int:
    """30-min blocks between t1 and t2 skipping the full 16:00-17:00 block."""
    if t2 < t1:
        t1, t2 = t2, t1
    blocks = 0
    cur = t1
    while cur < t2:
        # increment to next 30-min boundary
        nxt = cur + timedelta(minutes=30)
        # skip the 16:00-17:00 maintenance hour entirely
        if not (cur.hour == 16 or (cur.hour == 15 and nxt.hour == 16) or (cur.hour == 17 and cur.minute == 0)):
            blocks += 1
        cur = nxt
    return blocks

def make_time_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    base = datetime(2025, 1, 1, start.hour, start.minute)
    out = []
    cur = base
    stop = datetime(2025, 1, 1, end.hour, end.minute)
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

SPX_SLOTS = make_time_slots(RTH_START, RTH_END)   # RTH slots for SPX forecasts
ETH_SLOTS = make_time_slots(time(7,30), RTH_END)  # Extended slots for contract (optional)

def round_to_tick(x: float, tick: float) -> float:
    if tick <= 0: return x
    return round(round(x / tick) * tick, int(abs(math.log10(tick))))

def project_line(anchor_price: float, slope_per_block: float, blocks: int) -> float:
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
        # Extensions:
        "1.272": high + R*0.272,
        "1.618": high + R*0.618,
    }

def easter_date(y:int) -> date:
    # Anonymous Gregorian algorithm
    a=y%19; b=y//100; c=y%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30; i=c//4; k=c%4
    l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    month=(h+l-7*m+114)//31; day=((h+l-7*m+114)%31)+1
    return date(y, month, day)

def us_market_holidays(year:int) -> set[date]:
    # NYSE regular full-day holidays (approx; no early closures)
    def nth_weekday(month, weekday, n):
        # weekday: Mon=0..Sun=6
        d = date(year, month, 1)
        while d.weekday() != weekday: d += timedelta(days=1)
        return d + timedelta(days=7*(n-1))
    def last_weekday(month, weekday):
        d = date(year, month+1, 1) - timedelta(days=1)
        while d.weekday() != weekday: d -= timedelta(days=1)
        return d

    hol = set()
    # New Year's (observed)
    d = date(year,1,1); hol.add(d if d.weekday()<5 else (d+timedelta(days=1) if d.weekday()==5 else d+timedelta(days=2)))
    # MLK (3rd Mon Jan)
    hol.add(nth_weekday(1, 0, 3))
    # Presidents' Day (3rd Mon Feb)
    hol.add(nth_weekday(2, 0, 3))
    # Good Friday
    hol.add(easter_date(year) - timedelta(days=2))
    # Memorial Day (last Mon May)
    hol.add(last_weekday(5, 0))
    # Juneteenth (observed)
    d = date(year,6,19); hol.add(d if d.weekday()<5 else (d-timedelta(days=1) if d.weekday()==5 else d+timedelta(days=1)))
    # Independence Day (observed)
    d = date(year,7,4); hol.add(d if d.weekday()<5 else (d-timedelta(days=1) if d.weekday()==5 else d+timedelta(days=1)))
    # Labor Day (1st Mon Sep)
    hol.add(nth_weekday(9, 0, 1))
    # Thanksgiving (4th Thu Nov)
    hol.add(nth_weekday(11, 3, 4))
    # Christmas (observed)
    d = date(year,12,25); hol.add(d if d.weekday()<5 else (d-timedelta(days=1) if d.weekday()==5 else d+timedelta(days=1)))
    return hol

# ──────────────────────────────────────────────────────────────────────────────
# STATE INIT
# ──────────────────────────────────────────────────────────────────────────────
if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.theme = "Neo Dark"  # "Neo Dark" | "Neo Light"
    st.session_state.locked_anchors = False
    st.session_state.forecasts_generated = False
    st.session_state.contract = {"anchor_time": None, "anchor_price": None, "slope": None, "label": "Manual"}
    st.session_state.saved_snapshot = None
    st.session_state.show_charts = True

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG & CSS
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

# attach theme marker (for CSS)
st.markdown(f"""<script>
const root=document.querySelector('section.main'); if(root) root.parentElement.setAttribute('data-theme','{st.session_state.theme}');
</script>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown(
        f"""
        <div class="header">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem;">
            <div style="display:flex;align-items:center;gap:.75rem;">
              <div class="badge">📈 <strong>{PAGE_TITLE}</strong></div>
              <span class="pill">v{VERSION}</span>
              <span class="pill">TZ: America/Chicago</span>
            </div>
            <div style="display:flex;align-items:center;gap:.5rem;">
              <span class="small">Last generate:</span>
              <span class="pill" id="lastgen">{st.session_state.get('last_generate_at','—')}</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR: THEME, DATE, DOCS (verbatim), UTILITIES
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("🎨 Appearance")
    theme_choice = st.radio("Theme", ["Neo Dark", "Neo Light"], horizontal=True, index=0 if st.session_state.theme=="Neo Dark" else 1, label_visibility="collapsed")
    if theme_choice != st.session_state.theme:
        st.session_state.theme = theme_choice
        st.rerun()

    st.divider()
    st.subheader("📅 Forecast Date")
    forecast_date = st.date_input("Target Session", value=date.today() + timedelta(days=1))
    wd = forecast_date.weekday()
    day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    st.info(f"**{day_names[wd]}** session • Anchors use **previous day** of this target date.")

    # Weekend/holiday notice
    warn_msgs = []
    if wd >= 5: warn_msgs.append("Selected date is a weekend.")
    try:
        if forecast_date in us_market_holidays(forecast_date.year):
            warn_msgs.append("U.S. market holiday observed on selected date.")
    except Exception:
        pass
    if warn_msgs:
        st.warning(" | ".join(warn_msgs))

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
        if st.button("Reset Session", type="secondary", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k not in ["init","theme"]:
                    del st.session_state[k]
            st.rerun()
    with colB:
        st.session_state.show_charts = st.toggle("Sparklines", value=st.session_state.show_charts, help="Toggle mini charts above tables")

# ──────────────────────────────────────────────────────────────────────────────
# QUICK RULES POPOVER
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section">', unsafe_allow_html=True)
_pop = getattr(st, "popover", None)
if _pop:
    with st.popover("🔔 Quick Rules"):
        for r in SPX_GOLDEN_RULES[:3]: st.markdown(r)
else:
    with st.expander("🔔 Quick Rules"):
        for r in SPX_GOLDEN_RULES[:3]: st.markdown(r)
st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# FIXED SLOPES (READ-ONLY DISPLAY)
# ──────────────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="section"><b>Fixed Slopes (per 30-min SPX block)</b></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Descending / Entry**")
        st.markdown(f"- High: `{SPX_SLOPES_DOWN['HIGH']:+.4f}`")
        st.markdown(f"- Close: `{SPX_SLOPES_DOWN['CLOSE']:+.4f}`")
        st.markdown(f"- Low: `{SPX_SLOPES_DOWN['LOW']:+.4f}`")
    with c2:
        st.markdown("**Ascending / Exit**")
        st.markdown(f"- High→UP: `{SPX_SLOPES_UP['HIGH']:+.4f}`")
        st.markdown(f"- Close→UP: `{SPX_SLOPES_UP['CLOSE']:+.4f}`")
        st.markdown(f"- Low→UP: `{SPX_SLOPES_UP['LOW']:+.4f}`")

# ──────────────────────────────────────────────────────────────────────────────
# ANCHOR INPUTS (SPX prior-day anchors)
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section">', unsafe_allow_html=True)
st.subheader("⚓ SPX Anchors (Previous Day of Target Session)")
colH, colC, colL = st.columns(3)

def anchor_inputs(prefix: str, default_price: float, default_time: time):
    price = st.number_input(f"{prefix} Price", value=float(default_price), step=0.1, min_value=0.0, key=f"{prefix}_price")
    when  = st.time_input(f"{prefix} Time", value=default_time, step=300, key=f"{prefix}_time")
    return price, when

with colH:
    st.markdown("#### 📈 High Anchor")
    high_price, high_time = anchor_inputs("High", 6185.80, time(11,30))
with colC:
    st.markdown("#### 📊 Close Anchor")
    close_price, close_time = anchor_inputs("Close", 6170.20, time(15,0))
with colL:
    st.markdown("#### 📉 Low Anchor")
    low_price, low_time = anchor_inputs("Low", 6130.40, time(13,30))

colA, colB = st.columns([1,1])
with colA:
    if not st.session_state.get("locked_anchors", False):
        if st.button("🔒 Lock Anchors", type="primary", use_container_width=True):
            st.session_state.locked_anchors = True
    else:
        if st.button("✏️ Edit Anchors", type="secondary", use_container_width=True):
            st.session_state.locked_anchors = False

with colB:
    generate = st.button("🚀 Generate Forecast", type="primary", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# if locked, disable inputs visually (Streamlit doesn't fully disable; we respect flag for logic)
if st.session_state.locked_anchors and not generate:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# FORECAST GENERATION (SPX fans with asymmetric up/down slopes)
# ──────────────────────────────────────────────────────────────────────────────
def build_fan_table(anchor_label: str, anchor_price: float, anchor_time: time) -> pd.DataFrame:
    rows = []
    for slot in SPX_SLOTS:
        hh, mm = map(int, slot.split(":"))
        target_dt = datetime.combine(forecast_date, time(hh, mm))
        # anchor occurs on previous day of target session
        anchor_dt = datetime.combine(forecast_date - timedelta(days=1), anchor_time)
        blocks = spx_blocks_between(anchor_dt, target_dt)
        down = SPX_SLOPES_DOWN[anchor_label]  # entry
        up   = SPX_SLOPES_UP[anchor_label]    # exit
        entry = project_line(anchor_price, down, blocks)
        exit_ = project_line(anchor_price, up, blocks)
        rows.append({
            "Time": slot,
            "Entry (↓)": round(entry, 2),
            "Exit (↑)": round(exit_,  2),
            "Δ from Anchor": round((entry - anchor_price), 2)
        })
    return pd.DataFrame(rows)

if generate or st.session_state.get("forecasts_generated", False):
    st.session_state.forecasts_generated = True
    st.session_state.last_generate_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.markdown('<div class="section"><b>📊 SPX Forecast Tables (RTH 08:30–15:30)</b></div>', unsafe_allow_html=True)

    # High
    st.markdown("### 📈 High Anchor Fan")
    df_high = build_fan_table("HIGH", high_price, high_time)
    if st.session_state.show_charts:
        st.line_chart(df_high.set_index("Time")[["Entry (↓)", "Exit (↑)"]])
    st.dataframe(df_high, use_container_width=True, hide_index=True)

    # Close
    st.markdown("### 📊 Close Anchor Fan")
    df_close = build_fan_table("CLOSE", close_price, close_time)
    if st.session_state.show_charts:
        st.line_chart(df_close.set_index("Time")[["Entry (↓)", "Exit (↑)"]])
    st.dataframe(df_close, use_container_width=True, hide_index=True)

    # Low
    st.markdown("### 📉 Low Anchor Fan")
    df_low = build_fan_table("LOW", low_price, low_time)
    if st.session_state.show_charts:
        st.line_chart(df_low.set_index("Time")[["Entry (↓)", "Exit (↑)"]])
    st.dataframe(df_low, use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────────────────────────────────────
# CONTRACT LINE CONFIGURATION & ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section">', unsafe_allow_html=True)
st.subheader("📏 Contract Line")

col1, col2, col3 = st.columns([1,1,1])
with col1:
    st.markdown("**🎯 Low-1 Point**")
    low1_time = st.time_input("Time", value=time(2,0), step=300, key="low1_time")
    low1_price = st.number_input("Price", value=10.0, step=0.05, min_value=0.0, key="low1_price")
with col2:
    st.markdown("**🎯 Low-2 Point**")
    low2_time = st.time_input("Time ", value=time(3,30), step=300, key="low2_time")
    low2_price = st.number_input("Price ", value=12.0, step=0.05, min_value=0.0, key="low2_price")
with col3:
    line_label = st.selectbox("Label", ["Manual","Tuesday Play","Thursday Play"], index=0)

rth_only = st.toggle("Snap slots to RTH (08:30–15:30)", value=True, help="If off, use extended slots from 07:30")

gen_contract = st.button("⚡ Calculate Contract Line", type="primary")
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
    st.markdown("**Contract Metrics**")
    cA, cB, cC, cD = st.columns(4)
    with cA: st.metric("Anchor", f"{contract['anchor_time'].strftime('%H:%M')}", f"${contract['anchor_price']:.2f}")
    with cB: st.metric("Slope (per block)", f"{contract['slope']:+.4f}")
    with cC: st.metric("Label", contract["label"])
    with cD: st.metric("Forecast Date", forecast_date.strftime("%Y-%m-%d"))

    slots = SPX_SLOTS if rth_only else ETH_SLOTS
    rows=[]
    for slot in slots:
        hh, mm = map(int, slot.split(":"))
        target_dt = datetime.combine(forecast_date, time(hh, mm))
        blocks = spx_blocks_between(contract["anchor_time"], target_dt)
        proj = project_line(contract["anchor_price"], contract["slope"], blocks)
        rows.append({"Time": slot, "Projected": round_to_tick(proj, 0.05), "Blocks": blocks, "Δ from Anchor": round(proj - contract["anchor_price"], 2)})
    df_contract = pd.DataFrame(rows)
    if st.session_state.show_charts:
        st.line_chart(df_contract.set_index("Time")[["Projected"]])
    st.dataframe(df_contract, use_container_width=True, hide_index=True)

    # Real-time lookup
    lk1, lk2 = st.columns([1,2])
    with lk1:
        lookup_time = st.time_input("🕐 Lookup Time", value=time(9,30), step=300, key="lookup_time")
    with lk2:
        tdt = datetime.combine(forecast_date, lookup_time)
        blocks = spx_blocks_between(contract["anchor_time"], tdt)
        proj = project_line(contract["anchor_price"], contract["slope"], blocks)
        st.success(f"**Projected @ {lookup_time.strftime('%H:%M')}** → **${round_to_tick(proj, 0.05):.2f}**  •  {blocks} blocks  •  Δ {proj - contract['anchor_price']:+.2f}")
st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# FIBONACCI BOUNCE ANALYZER (Up-bounce only)
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section">', unsafe_allow_html=True)
st.subheader("📈 Fibonacci Bounce (Up-Bounce Only)")

fb1, fb2, fb3, fb4 = st.columns([1,1,1,1])
with fb1:
    fib_low  = st.number_input("Bounce Low (Contract)", value=0.00, step=0.05, min_value=0.0)
with fb2:
    fib_high = st.number_input("Bounce High (Contract)", value=0.00, step=0.05, min_value=0.0)
with fb3:
    fib_low_time = st.time_input("Bounce Low Time", value=time(9,30), step=300)
with fb4:
    show_targets = st.toggle("Show Targets (1.272 / 1.618)", value=True)

if fib_high > fib_low > 0:
    levels = fib_levels(fib_low, fib_high)
    # Table (round contract to $0.05; SPX display would be 0.01 if we ever show index levels)
    rows=[]
    for k in ["0.236","0.382","0.500","0.618","0.786","1.000"]:
        price = round_to_tick(levels[k], 0.05)  # contract tick
        rows.append({"Level": k, "Price": f"${price:.2f}", "Note": ("⭐ ALGO ENTRY" if k=="0.786" else "")})
    if show_targets:
        for k in ["1.272","1.618"]:
            price = round_to_tick(levels[k], 0.05)
            rows.append({"Level": k, "Price": f"${price:.2f}", "Note": "Target"})

    df_fib = pd.DataFrame(rows)
    st.markdown("**Retracement & Targets**")
    st.dataframe(df_fib, use_container_width=True, hide_index=True)

    # Next-hour confluence vs Contract Line
    nh_time = (datetime.combine(forecast_date, fib_low_time) + timedelta(hours=1)).time()
    key_0786 = round_to_tick(levels["0.786"], 0.05)
    st.markdown("**Next-Hour Confluence (vs Contract Line)**")
    if contract["anchor_time"] and contract["slope"] is not None:
        t_star = datetime.combine(forecast_date, nh_time)
        blk = spx_blocks_between(contract["anchor_time"], t_star)
        c_proj = round_to_tick(project_line(contract["anchor_price"], contract["slope"], blk), 0.05)
        delta = abs(c_proj - key_0786)
        pct = (delta / key_0786 * 100.0) if key_0786 != 0 else float('inf')
        badge = "🟢 **Strong**" if pct < 0.5 else ("🟡 **Moderate**" if pct <= 1.0 else "🟠 **Weak**")
        st.info(f"Fib 0.786: **${key_0786:.2f}**  •  Contract @ {nh_time.strftime('%H:%M')}: **${c_proj:.2f}**  •  Δ=${delta:.2f} ({pct:.2f}%) → {badge}")
    else:
        st.warning("Configure the Contract Line to enable confluence check.")

    # Simple entry/stop/targets math (transparent only)
    entry = key_0786
    stop  = round_to_tick(fib_low - 0.05, 0.05)  # one tick below low
    tp1   = round_to_tick(fib_high, 0.05)
    tp2   = round_to_tick(levels["1.272"], 0.05) if show_targets else None
    tp3   = round_to_tick(levels["1.618"], 0.05) if show_targets else None

    st.markdown("**Planning Aids (transparent math)**")
    risk_col, rr_col = st.columns([1,3])
    with risk_col:
        risk_val = st.number_input("Assumed $ Risk (per contract)", value=0.40, step=0.05, min_value=0.05)
    with rr_col:
        stop_dist = max(entry - stop, 0.0001)
        def rr(tp): return (tp - entry) / stop_dist if tp else None
        info = f"- Entry: **${entry:.2f}**  •  Stop: **${stop:.2f}**  •  Risk/contract: **${risk_val:.2f}**"
        st.write(info)
        st.write(f"- TP1 (Back to High): **${tp1:.2f}**  → R:R **{rr(tp1):.2f}**")
        if show_targets:
            st.write(f"- TP2 (1.272): **${tp2:.2f}**  → R:R **{rr(tp2):.2f}**")
            st.write(f"- TP3 (1.618): **${tp3:.2f}**  → R:R **{rr(tp3):.2f}**")
else:
    st.info("Enter **Bounce Low < Bounce High** to compute Fib levels.")
st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# INTEGRATION SHORTCUTS (row → contract / fib) & SNAPSHOTS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section">', unsafe_allow_html=True)
st.subheader("🧩 Workflows & Snapshots")

# Snapshots: save/load current inputs (no slopes)
snap_col1, snap_col2 = st.columns(2)
with snap_col1:
    if st.button("💾 Save Session Snapshot", type="secondary", use_container_width=True):
        snapshot = {
            "forecast_date": str(forecast_date),
            "anchors": {
                "high": {"price": high_price, "time": high_time.strftime("%H:%M")},
                "close": {"price": close_price, "time": close_time.strftime("%H:%M")},
                "low": {"price": low_price, "time": low_time.strftime("%H:%M")},
            },
            "contract": {
                "low1_time": st.session_state.get("low1_time", time(2,0)).strftime("%H:%M"),
                "low1_price": st.session_state.get("low1_price", 10.0),
                "low2_time": st.session_state.get("low2_time", time(3,30)).strftime("%H:%M"),
                "low2_price": st.session_state.get("low2_price", 12.0),
                "label": st.session_state.get("label", "Manual") if "label" in st.session_state else "Manual"
            },
            "fib": {
                "low": fib_low, "high": fib_high, "low_time": fib_low_time.strftime("%H:%M"),
                "show_targets": show_targets
            }
        }
        st.session_state.saved_snapshot = snapshot
        bio = io.BytesIO(json.dumps(snapshot, indent=2).encode())
        st.download_button("⬇️ Download Snapshot (.json)", data=bio.getvalue(), file_name="spx_session_snapshot.json", mime="application/json", use_container_width=True)

with snap_col2:
    uploaded = st.file_uploader("📂 Load Snapshot (.json)", type=["json"])
    if uploaded:
        try:
            data = json.loads(uploaded.read().decode())
            # Basic restore (anchors only; others require re-click for recompute)
            st.session_state["High_price"]  = float(data["anchors"]["high"]["price"])
            st.session_state["High_time"]   = datetime.strptime(data["anchors"]["high"]["time"], "%H:%M").time()
            st.session_state["Close_price"] = float(data["anchors"]["close"]["price"])
            st.session_state["Close_time"]  = datetime.strptime(data["anchors"]["close"]["time"], "%H:%M").time()
            st.session_state["Low_price"]   = float(data["anchors"]["low"]["price"])
            st.session_state["Low_time"]    = datetime.strptime(data["anchors"]["low"]["time"], "%H:%M").time()
            st.success("Snapshot loaded. Adjust any inputs and re-generate.")
        except Exception as e:
            st.error(f"Failed to load snapshot: {e}")

# Export all CSVs (if available)
exportables = {}
if st.session_state.get("forecasts_generated", False):
    exportables["SPX_High_Fan.csv"]  = df_high.to_csv(index=False).encode()
    exportables["SPX_Close_Fan.csv"] = df_close.to_csv(index=False).encode()
    exportables["SPX_Low_Fan.csv"]   = df_low.to_csv(index=False).encode()
if st.session_state.contract["anchor_time"] and st.session_state.contract["slope"] is not None:
    exportables["Contract_Line.csv"] = df_contract.to_csv(index=False).encode()
if "df_fib" in locals():
    exportables["Fib_Levels.csv"] = df_fib.to_csv(index=False).encode()

if exportables:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, data in exportables.items():
            zf.writestr(fname, data)
    st.download_button("⬇️ Export All CSVs (zip)", data=buf.getvalue(), file_name="spx_exports.zip", mime="application/zip", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="footer">
      <div>📈 <b>{PAGE_TITLE}</b> • Advanced Market Forecasting • v{VERSION}</div>
      <div class="small">Disclaimer: Educational/analysis use only. Not financial advice.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

