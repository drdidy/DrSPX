# app.py  (SPX PROPHET – Predicting Market Irrationality Accurately)
# ------------------------------------------------------------------

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz

# ------------------------------------------------------------------
#  CONSTANTS
# ------------------------------------------------------------------
APP_NAME = "SPX PROPHET"
TAGLINE = "Predicting Market Irrationality Accurately"
CT = pytz.timezone("America/Chicago")
ASC_SLOPE_DEFAULT = 0.475
DESC_SLOPE_DEFAULT = -0.475
OFFSET_DEFAULT = 16.25

# ------------------------------------------------------------------
#  HELPERS
# ------------------------------------------------------------------
def rth_slots_ct_dt(proj_date: date, start="08:30", end="14:30"):
    """Return 30-min time stamps for RTH session (CT)."""
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    start_dt = CT.localize(datetime.combine(proj_date, dtime(h1, m1)))
    end_dt = CT.localize(datetime.combine(proj_date, dtime(h2, m2)))
    idx = pd.date_range(start=start_dt, end=end_dt, freq="30min", tz=CT)
    return list(idx.to_pydatetime())

def project_anchor_lines(anchor_price, anchor_time_ct, slope, offset, slots):
    """Compute A₀, A₊, D₀, D₋ for every 30-min slot."""
    minute = 0 if anchor_time_ct.minute < 30 else 30
    anchor_aligned = anchor_time_ct.replace(minute=minute, second=0, microsecond=0)
    rows = []
    for dt in slots:
        blocks = int((dt - anchor_aligned).total_seconds() // 1800)
        if blocks < 0:
            continue
        a0 = anchor_price + slope * blocks
        d0 = anchor_price - slope * blocks
        a_plus = a0 + offset
        d_minus = d0 - offset
        rows.append({
            "Time (CT)": dt.strftime("%I:%M %p"),
            "A₀ Ascending Inner": round(a0, 2),
            "A₊ Momentum Outer": round(a_plus, 2),
            "D₀ Descending Inner": round(d0, 2),
            "D₋ Gravity Outer": round(d_minus, 2),
            "Pivot Top": round(a0, 2),
            "Pivot Bottom": round(d0, 2)
        })
    return pd.DataFrame(rows)

def compute_dem(df):
    """Upper / Lower DEM from 08:30 row."""
    open_row = df[df["Time (CT)"] == "08:30 AM"].iloc[0]
    return {
        "Upper DEM": open_row["A₊ Momentum Outer"],
        "Lower DEM": open_row["D₋ Gravity Outer"]
    }

def label_state(price, a0, a_plus, d0, d_minus):
    """Return simple textual state."""
    if price > a_plus:
        return "Above Momentum Deck"
    elif price >= a0 and price <= a_plus:
        return "Inside Momentum Deck"
    elif price < d_minus:
        return "Below Gravity Deck"
    elif price <= d0 and price >= d_minus:
        return "Inside Gravity Deck"
    elif price < a0 and price > d0:
        return "Inside Pivot Corridor"
    else:
        return "—"

def detect_signals(df, highs, lows, closes):
    """Apply Touch-and-Close Sell / Buy rules inclusive >= <= ."""
    sells, buys = [], []
    for i, r in df.iterrows():
        hi, lo, cl = highs[i], lows[i], closes[i]
        a0, d0 = r["A₀ Ascending Inner"], r["D₀ Descending Inner"]
        if hi >= a0 and cl < hi and cl >= d0 and cl <= a0:
            sells.append("SELL ⚠️")
        else:
            sells.append("")
        if lo <= d0 and cl > lo and cl >= d0 and cl <= a0:
            buys.append("BUY ⚡")
        else:
            buys.append("")
    df["Touch-Sell"] = sells
    df["Touch-Buy"] = buys
    return df

# ------------------------------------------------------------------
#  UI  – STYLE
# ------------------------------------------------------------------
st.set_page_config(page_title=APP_NAME, page_icon="◈", layout="wide")

st.markdown("""
<style>
/*  ——– imported from original SPX PROPHET ——–  */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;900&family=JetBrains+Mono:wght@400;500;700&display=swap');
* {font-family:'Outfit',sans-serif;}
html,body,.main,.block-container{background:linear-gradient(135deg,#0f1419 0%,#1a1f2e 100%);color:#e8eaed;}
.stApp{background:linear-gradient(135deg,#0f1419 0%,#1a1f2e 100%);}
h1,h2,h3,h4,h5,h6,p,div,span,label{color:#e8eaed;}
.prophet-header{text-align:center;padding:60px 40px 40px;margin-bottom:40px;background:linear-gradient(135deg,rgba(218,165,32,0.05)0%,rgba(100,149,237,0.05)100%);
border-radius:24px;border:1px solid rgba(218,165,32,0.1);backdrop-filter:blur(20px);
box-shadow:0 20px 60px rgba(0,0,0,0.5),inset 0 1px 0 rgba(255,255,255,0.1);}
.prophet-logo{font-size:56px;font-weight:900;background:linear-gradient(135deg,#daa520 0%,#6495ed 100%);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:0.05em;margin:0;}
.prophet-subtitle{font-size:14px;font-weight:600;color:#7d8590;text-transform:uppercase;letter-spacing:0.2em;margin-top:12px;}
/* keep rest identical to your prior CSS */
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
#  SIDEBAR + HEADER
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.info(f"Ascending slope +{ASC_SLOPE_DEFAULT}")
    st.info(f"Descending slope {DESC_SLOPE_DEFAULT}")
    st.info(f"Offset ±{OFFSET_DEFAULT}")
    st.markdown("---")
    st.caption("Central Time (CT) | RTH 08:30 – 15:00")
    st.caption("Manual inputs only – no live data")
    st.markdown("---")
    st.caption("Momentum Deck = A₀↔A₊   Pivot Corridor = A₀↔D₀   Gravity Deck = D₀↔D₋")

st.markdown(f"""
<div class="prophet-header">
  <div class="prophet-logo">◈ {APP_NAME}</div>
  <div class="prophet-subtitle">{TAGLINE}</div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
#  TABS
# ------------------------------------------------------------------
tab1, tab2 = st.tabs(["📊 Anchor Deck System", "📐 Fibonacci Calculator"])
# ------------------------------------------------------------------
#  TAB 1 :  ANCHOR DECK SYSTEM
# ------------------------------------------------------------------
with tab1:
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚙️ Anchor Configuration</div>', unsafe_allow_html=True)

    proj_day = st.date_input("Projection Date", value=datetime.now(CT).date())
    col1, col2, col3 = st.columns(3)
    with col1:
        anchor_price = st.number_input("Anchor Price ($)", value=6800.00, step=0.01, format="%.2f")
    with col2:
        anchor_time = st.time_input("Anchor Time (CT)", value=dtime(15, 0), step=1800)
    with col3:
        direction = st.radio("Anchor Direction", ["Bullish (Ascending)", "Bearish (Descending)"])
    slope = ASC_SLOPE_DEFAULT if "Bullish" in direction else -ASC_SLOPE_DEFAULT
    offset = OFFSET_DEFAULT

    slots = rth_slots_ct_dt(proj_day, "08:30", "14:30")
    anchor_dt = CT.localize(datetime.combine(proj_day, anchor_time))
    df = project_anchor_lines(anchor_price, anchor_dt, slope, offset, slots)
    dem = compute_dem(df)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🌅 Expected Move Metrics (08:30 AM)</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"##### ☁️ Upper DEM    ${dem['Upper DEM']:.2f}")
    with col2:
        st.markdown(f"##### 🔻 Lower DEM    ${dem['Lower DEM']:.2f}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎯 Manual Price Inputs for Signal Testing</div>', unsafe_allow_html=True)
    highs = st.text_area("Highs (comma-separated)", "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    lows = st.text_area("Lows (comma-separated)", "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    closes = st.text_area("Closes (comma-separated)", "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")

    highs = [float(x) for x in highs.split(",") if x.strip() != ""]
    lows = [float(x) for x in lows.split(",") if x.strip() != ""]
    closes = [float(x) for x in closes.split(",") if x.strip() != ""]
    if len(highs) == len(df) and len(lows) == len(df) and len(closes) == len(df):
        df = detect_signals(df, highs, lows, closes)
    else:
        df["Touch-Sell"] = ""
        df["Touch-Buy"] = ""

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📈 Deck Projection Table</div>', unsafe_allow_html=True)

    current_price = st.number_input("Current SPX Price (optional)", value=0.00, step=0.01, format="%.2f", min_value=0.0)
    if current_price > 0:
        df["State at Price"] = df.apply(
            lambda r: label_state(current_price, r["A₀ Ascending Inner"], r["A₊ Momentum Outer"],
                                  r["D₀ Descending Inner"], r["D₋ Gravity Outer"]), axis=1)
    else:
        df["State at Price"] = ""

    st.dataframe(df, use_container_width=True, hide_index=True, height=500)
    st.download_button("💾 Download Projection CSV", df.to_csv(index=False).encode(),
                       "spx_anchor_deck.csv", "text/csv", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
#  TAB 2 :  FIBONACCI CALCULATOR – UNCHANGED
# ------------------------------------------------------------------
with tab2:
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📐 Fibonacci Retracement</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        fib_high = st.number_input("Contract High ($)", value=0.00, step=0.01, key="fib_high", format="%.2f", min_value=0.0)
    with col2:
        fib_low = st.number_input("Contract Low ($)", value=0.00, step=0.01, key="fib_low", format="%.2f", min_value=0.0)

    if fib_high > 0 and fib_low > 0 and fib_high > fib_low:
        rng = fib_high - fib_low
        fibs = {
            "0.618": round(fib_high - (rng * 0.618), 2),
            "0.786": round(fib_high - (rng * 0.786), 2),
            "0.500": round(fib_high - (rng * 0.500), 2),
            "0.382": round(fib_high - (rng * 0.382), 2),
            "0.236": round(fib_high - (rng * 0.236), 2)
        }

        st.markdown(f"""
        <div class="fib-result primary">
          <div><div class="fib-label">🎯 0.618 Retracement (Primary)</div>
          <div style="color:#7d8590;font-size:12px;margin-top:4px;">Golden ratio entry</div></div>
          <div class="fib-value">${fibs['0.618']}</div></div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="fib-result primary">
          <div><div class="fib-label">🎯 0.786 Retracement (Secondary)</div>
          <div style="color:#7d8590;font-size:12px;margin-top:4px;">Deep retracement entry</div></div>
          <div class="fib-value">${fibs['0.786']}</div></div>""", unsafe_allow_html=True)

        for lvl, val in fibs.items():
            st.markdown(f'<div class="fib-result"><div class="fib-label">{lvl}</div><div class="fib-value">${val}</div></div>', unsafe_allow_html=True)
        st.info(f"Range: ${fib_high:.2f} – ${fib_low:.2f} = ${rng:.2f}")
    elif fib_high > 0 and fib_low > 0:
        st.error("Contract High must be greater than Contract Low")

    st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
#  MAIN
# ------------------------------------------------------------------
if __name__ == "__main__":
    pass