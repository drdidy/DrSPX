# app.py — SPX PROPHET
# Tagline: Predicting Market Irrationality Accurately

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz

# ========= CONSTANTS =========
APP_NAME = "SPX PROPHET"
TAGLINE = "Predicting Market Irrationality Accurately"
CT = pytz.timezone("America/Chicago")
ASC_SLOPE_DEFAULT = 0.475     # per 30-min block
DESC_SLOPE_DEFAULT = -0.475   # per 30-min block
OFFSET_DEFAULT = 16.25        # points

# ========= SESSION SLOTS =========
def rth_slots_ct_dt(proj_date: date, start="08:30", end="14:30"):
    """Return 30-min timestamps for RTH session (CT) inclusive of 14:30 bar which closes at 15:00."""
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    start_dt = CT.localize(datetime.combine(proj_date, dtime(h1, m1)))
    end_dt = CT.localize(datetime.combine(proj_date, dtime(h2, m2)))
    idx = pd.date_range(start=start_dt, end=end_dt, freq="30min", tz=CT)
    return list(idx.to_pydatetime())

# ========= GEOMETRY =========
def project_anchor_lines(anchor_price, anchor_time_ct, slope, offset, slots):
    """
    Build forward-only rails from the anchor time:
      A0 = anchor + slope * blocks
      D0 = anchor - slope * blocks
      A+ = A0 + offset
      D- = D0 - offset
    Returns a DataFrame with fixed columns even if there are no rows (to avoid KeyError).
    """
    cols = ["Time (CT)", "A0 Ascending Inner", "Aplus Momentum Outer",
            "D0 Descending Inner", "Dminus Gravity Outer", "Pivot Top", "Pivot Bottom"]
    rows = []
    # Align anchor to the nearest 30-minute boundary at or before the given minute
    minute = 0 if anchor_time_ct.minute < 30 else 30
    anchor_aligned = anchor_time_ct.replace(minute=minute, second=0, microsecond=0)
    for dt in slots:
        # forward-only
        blocks = int((dt - anchor_aligned).total_seconds() // 1800)
        if blocks < 0:
            continue
        a0 = anchor_price + slope * blocks
        d0 = anchor_price - slope * blocks
        a_plus = a0 + offset
        d_minus = d0 - offset
        rows.append({
            "Time (CT)": dt.strftime("%I:%M %p"),
            "A0 Ascending Inner": round(a0, 2),
            "Aplus Momentum Outer": round(a_plus, 2),
            "D0 Descending Inner": round(d0, 2),
            "Dminus Gravity Outer": round(d_minus, 2),
            "Pivot Top": round(a0, 2),
            "Pivot Bottom": round(d0, 2)
        })
    return pd.DataFrame(rows, columns=cols)

def compute_dem(df):
    """DEM from 08:30 row: Upper = Aplus at 08:30, Lower = Dminus at 08:30. Safe if row missing."""
    result = {"Upper DEM": None, "Lower DEM": None}
    if "Time (CT)" not in df.columns or df.empty:
        return result
    open_rows = df[df["Time (CT)"] == "08:30 AM"]
    if open_rows.empty:
        return result
    r = open_rows.iloc[0]
    return {"Upper DEM": r["Aplus Momentum Outer"], "Lower DEM": r["Dminus Gravity Outer"]}

def label_state(price, a0, a_plus, d0, d_minus):
    """State relative to decks and corridor."""
    if price > a_plus:
        return "Above Momentum Deck"
    if (price >= a0) and (price <= a_plus):
        return "Inside Momentum Deck"
    if price < d_minus:
        return "Below Gravity Deck"
    if (price <= d0) and (price >= d_minus):
        return "Inside Gravity Deck"
    if (price < a0) and (price > d0):
        return "Inside Pivot Corridor"
    return ""

# ========= SIGNALS =========
def detect_touch_close_signals(df, opens, highs, lows, closes):
    """
    Your inclusive touch rules with strict close inside corridor:
      Sell trigger:
        - intrabar high >= A0
        - close strictly between D0 and A0
        - candle is bullish (close > open)
      Buy trigger:
        - intrabar low <= D0
        - close strictly between D0 and A0
        - candle is bearish (close < open)
      If candle color is opposite, do not trigger.
    """
    sells, buys = [], []
    n = len(df)

    def _get(seq, i):
        # pad or trim to df length
        if i < len(seq):
            return seq[i]
        return 0.0

    for i in range(n):
        r = df.iloc[i]
        a0 = r["A0 Ascending Inner"]
        d0 = r["D0 Descending Inner"]
        op = _get(opens, i)
        hi = _get(highs, i)
        lo = _get(lows, i)
        cl = _get(closes, i)

        close_inside_corridor = (cl > d0) and (cl < a0)  # STRICT inside
        bullish_candle = cl > op
        bearish_candle = cl < op

        # SELL
        if (hi >= a0) and close_inside_corridor and bullish_candle:
            sells.append("SELL")
        else:
            sells.append("")

        # BUY
        if (lo <= d0) and close_inside_corridor and bearish_candle:
            buys.append("BUY")
        else:
            buys.append("")

    df["Touch Close Sell"] = sells
    df["Touch Close Buy"] = buys
    return df

# ========= STREAMLIT UI (STYLE) =========
st.set_page_config(page_title=APP_NAME, page_icon="◈", layout="wide")

# Full CSS from your current app
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

* {
    font-family: 'Outfit', sans-serif;
    letter-spacing: -0.01em;
}
html, body, .main, .block-container {
    background: linear-gradient(135deg, #0f1419 0%, #1a1f2e 100%);
    color: #e8eaed;
}
.stApp {
    background: linear-gradient(135deg, #0f1419 0%, #1a1f2e 100%);
}
h1, h2, h3, h4, h5, h6, p, div, span, label {
    color: #e8eaed;
}
.prophet-header {
    position: relative;
    text-align: center;
    padding: 60px 40px 40px 40px;
    margin-bottom: 40px;
    background: linear-gradient(135deg, rgba(218, 165, 32, 0.05) 0%, rgba(100, 149, 237, 0.05) 100%);
    border-radius: 24px;
    border: 1px solid rgba(218, 165, 32, 0.1);
    backdrop-filter: blur(20px);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
.prophet-logo {
    font-size: 56px;
    font-weight: 900;
    background: linear-gradient(135deg, #daa520 0%, #6495ed 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 0.05em;
    margin: 0;
}
.prophet-subtitle {
    font-size: 14px;
    font-weight: 600;
    color: #7d8590;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    margin-top: 16px;
}
.premium-card {
    background: linear-gradient(135deg, rgba(26, 31, 46, 0.8) 0%, rgba(15, 20, 25, 0.9) 100%);
    border: 1px solid rgba(218, 165, 32, 0.15);
    border-radius: 20px;
    padding: 32px;
    margin: 24px 0;
    backdrop-filter: blur(10px);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.premium-card:hover {
    transform: translateY(-4px);
    border-color: rgba(218, 165, 32, 0.3);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 40px rgba(218, 165, 32, 0.15);
}
.card-title {
    font-size: 20px;
    font-weight: 700;
    color: #daa520;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 24px 0;
}
.metric-card {
    background: linear-gradient(135deg, rgba(218, 165, 32, 0.05) 0%, rgba(100, 149, 237, 0.05) 100%);
    border: 1px solid rgba(218, 165, 32, 0.15);
    border-radius: 16px;
    padding: 24px 20px;
    text-align: center;
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
    border-color: rgba(218, 165, 32, 0.3);
    box-shadow: 0 8px 32px rgba(218, 165, 32, 0.15);
}
.metric-label {
    font-size: 11px;
    font-weight: 700;
    color: #7d8590;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 12px;
}
.metric-value {
    font-size: 28px;
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    background: linear-gradient(135deg, #daa520, #6495ed);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.distance-item {
    background: linear-gradient(135deg, rgba(26, 31, 46, 0.6) 0%, rgba(15, 20, 25, 0.8) 100%);
    border: 1px solid rgba(218, 165, 32, 0.2);
    border-radius: 12px;
    padding: 16px 24px;
    margin: 8px 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: all 0.3s ease;
}
.distance-item:hover {
    transform: translateX(4px);
    border-color: rgba(218, 165, 32, 0.4);
    box-shadow: 0 4px 20px rgba(218, 165, 32, 0.15);
}
.distance-item.current {
    background: linear-gradient(135deg, rgba(218, 165, 32, 0.2) 0%, rgba(100, 149, 237, 0.2) 100%);
    border: 2px solid rgba(218, 165, 32, 0.5);
    font-size: 18px;
    font-weight: 800;
}
.distance-label { font-size: 15px; font-weight: 600; color: #e8eaed; }
.distance-value { font-size: 20px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
.distance-value.up { color: #22c55e; }
.distance-value.down { color: #ef4444; }
.probability-card {
    background: linear-gradient(135deg, rgba(218, 165, 32, 0.1) 0%, rgba(100, 149, 237, 0.1) 100%);
    border: 2px solid rgba(218, 165, 32, 0.3);
    border-radius: 16px;
    padding: 28px;
    margin: 20px 0;
    backdrop-filter: blur(10px);
}
.prob-title { font-size: 18px; font-weight: 700; color: #daa520; margin-bottom: 20px; text-align: center; }
.opening-context {
    background: linear-gradient(135deg, rgba(100, 149, 237, 0.1) 0%, rgba(100, 149, 237, 0.05) 100%);
    border: 1px solid rgba(100, 149, 237, 0.3);
    border-radius: 16px;
    padding: 24px;
    margin: 20px 0;
}
.context-title { font-size: 16px; font-weight: 700; color: #6495ed; margin-bottom: 12px; }
.context-text { font-size: 15px; color: #cbd5e1; line-height: 1.6; }
.expected-moves { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 20px 0; }
.move-card {
    background: linear-gradient(135deg, rgba(26, 31, 46, 0.6) 0%, rgba(15, 20, 25, 0.8) 100%);
    border: 1px solid rgba(218, 165, 32, 0.2);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}
.move-label { font-size: 12px; font-weight: 700; color: #7d8590; text-transform: uppercase; margin-bottom: 10px; }
.move-value { font-size: 28px; font-weight: 800; font-family: 'JetBrains Mono', monospace; color: #daa520; }
.fib-result {
    background: linear-gradient(135deg, rgba(26, 31, 46, 0.6) 0%, rgba(15, 20, 25, 0.8) 100%);
    border: 1px solid rgba(218, 165, 32, 0.2);
    border-radius: 12px;
    padding: 20px 28px;
    margin: 12px 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: all 0.3s ease;
}
.fib-result:hover { transform: translateX(4px); border-color: rgba(218, 165, 32, 0.4); }
.fib-result.primary {
    border-width: 2px;
    border-color: rgba(218, 165, 32, 0.4);
    background: linear-gradient(135deg, rgba(218, 165, 32, 0.1) 0%, rgba(100, 149, 237, 0.1) 100%);
}
.fib-label { font-size: 15px; font-weight: 600; color: #e8eaed; }
.fib-value { font-size: 24px; font-weight: 800; font-family: 'JetBrains Mono', monospace; color: #daa520; }
.stDataFrame { border: 1px solid rgba(218, 165, 32, 0.2); border-radius: 16px; overflow: hidden; }
.stDataFrame table { font-family: 'JetBrains Mono', monospace; }
.stDataFrame thead th {
    background: linear-gradient(135deg, rgba(218, 165, 32, 0.15), rgba(100, 149, 237, 0.15)) !important;
    color: #daa520 !important;
    font-weight: 800 !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    padding: 18px 16px !important;
    border-bottom: 2px solid rgba(218, 165, 32, 0.3) !important;
}
.stDataFrame tbody td {
    background: rgba(15, 20, 25, 0.4) !important;
    color: #e8eaed !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    padding: 16px !important;
    border-bottom: 1px solid rgba(218, 165, 32, 0.1) !important;
}
.stDataFrame tbody tr:hover td { background: rgba(218, 165, 32, 0.08) !important; }
.stNumberInput input, .stDateInput input, .stTimeInput input, .stTextInput input, .stTextArea textarea {
    background: rgba(15, 20, 25, 0.6) !important;
    border: 1.5px solid rgba(218, 165, 32, 0.2) !important;
    border-radius: 10px !important;
    color: #e8eaed !important;
    font-weight: 600 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 15px !important;
    padding: 12px 16px !important;
    transition: all 0.3s ease !important;
}
.stNumberInput input:focus, .stDateInput input:focus, .stTimeInput input:focus, .stTextInput input:focus, .stTextArea textarea:focus {
    border-color: rgba(218, 165, 32, 0.5) !important;
    box-shadow: 0 0 0 3px rgba(218, 165, 32, 0.1) !important;
}
.stNumberInput label, .stDateInput label, .stTimeInput label, .stTextInput label, .stTextArea label {
    color: #7d8590 !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
.stButton button, .stDownloadButton button {
    background: linear-gradient(135deg, #daa520, #6495ed) !important;
    color: #0f1419 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 14px 32px !important;
    font-weight: 800 !important;
    font-size: 13px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 6px 20px rgba(218, 165, 32, 0.3) !important;
}
.stButton button:hover, .stDownloadButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(218, 165, 32, 0.5) !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent;
    border-bottom: 1px solid rgba(218, 165, 32, 0.2);
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border: none;
    color: #7d8590;
    font-weight: 600;
    padding: 12px 24px;
}
.stTabs [aria-selected="true"] {
    color: #daa520;
    border-bottom: 2px solid #daa520;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(15, 20, 25, 0.95) 0%, rgba(26, 31, 46, 0.95) 100%);
    border-right: 1px solid rgba(218, 165, 32, 0.15);
    backdrop-filter: blur(20px);
}
section[data-testid="stSidebar"] * { color: #e8eaed; }
</style>
""", unsafe_allow_html=True)

# Sidebar + Header
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.info(f"Ascending {ASC_SLOPE_DEFAULT}")
    st.info(f"Descending {DESC_SLOPE_DEFAULT}")
    st.info(f"Offset {OFFSET_DEFAULT}")
    st.markdown("---")
    st.caption("Central Time (CT)")
    st.caption("RTH 08:30 to 15:00")
    st.caption("Manual inputs only")
    st.markdown("---")
    st.caption("Momentum Deck = A0 to Aplus")
    st.caption("Pivot Corridor = A0 to D0")
    st.caption("Gravity Deck = D0 to Dminus")

st.markdown(f"""
<div class="prophet-header">
  <div class="prophet-logo">◈ {APP_NAME}</div>
  <div class="prophet-subtitle">{TAGLINE}</div>
</div>
""", unsafe_allow_html=True)

# Tabs
tab1, tab2 = st.tabs(["📊 Anchor Deck System", "📐 Fibonacci Calculator"])

# ========= TAB 1: ANCHOR DECK SYSTEM =========
with tab1:
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚙️ Anchor Configuration</div>', unsafe_allow_html=True)

    proj_day = st.date_input("Projection Date", value=datetime.now(CT).date())
    c1, c2, c3 = st.columns(3)
    with c1:
        anchor_price = st.number_input("Anchor Price ($)", value=6800.00, step=0.01, format="%.2f")
    with c2:
        anchor_time = st.time_input("Anchor Time (CT)", value=dtime(15, 0), step=1800)
    with c3:
        direction = st.radio("Anchor Direction", ["Bullish (Ascending)", "Bearish (Descending)"])
    slope = ASC_SLOPE_DEFAULT if "Bullish" in direction else -ASC_SLOPE_DEFAULT
    offset = OFFSET_DEFAULT

    slots = rth_slots_ct_dt(proj_day, "08:30", "14:30")
    anchor_dt = CT.localize(datetime.combine(proj_day, anchor_time))
    df = project_anchor_lines(anchor_price, anchor_dt, slope, offset, slots)

    dem = compute_dem(df)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🌅 Expected Move Metrics at 08:30</div>', unsafe_allow_html=True)
    if dem["Upper DEM"] is None or dem["Lower DEM"] is None:
        st.warning("No 08:30 row found for this configuration. Check the anchor time. For same-day forward projection, the anchor must be at or before 14:30.")
    else:
        u, l = dem["Upper DEM"], dem["Lower DEM"]
        co1, co2 = st.columns(2)
        with co1:
            st.markdown(f"##### Upper DEM ${u:.2f}")
        with co2:
            st.markdown(f"##### Lower DEM ${l:.2f}")
    st.markdown('</div>', unsafe_allow_html=True)

    # Manual OHLC input for each 30-min bar to evaluate signals
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎯 Manual Price Inputs for Signal Testing</div>', unsafe_allow_html=True)

    default_len = max(1, len(df))
    zeros = ",".join(["0"] * default_len)

    col_ohlc1, col_ohlc2 = st.columns(2)
    with col_ohlc1:
        opens_txt = st.text_area("Opens (comma separated)", zeros, height=100)
        highs_txt = st.text_area("Highs (comma separated)", zeros, height=100)
    with col_ohlc2:
        lows_txt = st.text_area("Lows (comma separated)", zeros, height=100)
        closes_txt = st.text_area("Closes (comma separated)", zeros, height=100)

    def parse_series(txt):
        vals = [v.strip() for v in txt.split(",") if v.strip() != ""]
        out = []
        for v in vals:
            try:
                out.append(float(v))
            except:
                out.append(0.0)
        return out

    opens = parse_series(opens_txt)
    highs = parse_series(highs_txt)
    lows = parse_series(lows_txt)
    closes = parse_series(closes_txt)

    # pad or trim to df length
    def fit_length(seq, n):
        if len(seq) >= n:
            return seq[:n]
        return seq + [0.0] * (n - len(seq))

    nrows = len(df)
    opens = fit_length(opens, nrows)
    highs = fit_length(highs, nrows)
    lows = fit_length(lows, nrows)
    closes = fit_length(closes, nrows)

    if nrows > 0:
        df = detect_touch_close_signals(df, opens, highs, lows, closes)
    else:
        st.info("No projection rows. Choose an anchor time at or before 14:30 or enable a carry workflow for future enhancement.")

    st.markdown('</div>', unsafe_allow_html=True)

    # State at optional current price
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📈 Deck Projection Table</div>', unsafe_allow_html=True)

    current_price = st.number_input("Current SPX Price (optional)", value=0.00, step=0.01, format="%.2f", min_value=0.0)
    if current_price > 0 and nrows > 0:
        df["State at Price"] = df.apply(
            lambda r: label_state(current_price, r["A0 Ascending Inner"],
                                  r["Aplus Momentum Outer"],
                                  r["D0 Descending Inner"],
                                  r["Dminus Gravity Outer"]), axis=1)
    else:
        df["State at Price"] = ""

    st.dataframe(df, use_container_width=True, hide_index=True, height=520)

    cdl1, cdl2, cdl3 = st.columns(3)
    with cdl1:
        st.download_button("Complete Dataset", df.to_csv(index=False).encode(),
                           "spx_anchor_deck.csv", "text/csv", use_container_width=True)
    with cdl2:
        cols_anchor = ["Time (CT)", "A0 Ascending Inner", "D0 Descending Inner"]
        st.download_button("Inner Rails Only", df[cols_anchor].to_csv(index=False).encode(),
                           "spx_inner_rails.csv", "text/csv", use_container_width=True)
    with cdl3:
        cols_decks = ["Time (CT)", "Aplus Momentum Outer", "Dminus Gravity Outer"]
        st.download_button("Outer Rails Only", df[cols_decks].to_csv(index=False).encode(),
                           "spx_outer_rails.csv", "text/csv", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ========= TAB 2: FIBONACCI CALCULATOR (unchanged) =========
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

        st.markdown(f'''
            <div class="fib-result primary">
                <div>
                    <div class="fib-label">🎯 0.618 Retracement (Primary)</div>
                    <div style="color: #7d8590; font-size: 12px; margin-top: 4px;">Golden ratio entry</div>
                </div>
                <div class="fib-value">${fibs['0.618']}</div>
            </div>
        ''', unsafe_allow_html=True)

        st.markdown(f'''
            <div class="fib-result primary">
                <div>
                    <div class="fib-label">🎯 0.786 Retracement (Secondary)</div>
                    <div style="color: #7d8590; font-size: 12px; margin-top: 4px;">Deep retracement entry</div>
                </div>
                <div class="fib-value">${fibs['0.786']}</div>
            </div>
        ''', unsafe_allow_html=True)

        for lvl, val in fibs.items():
            st.markdown(f'<div class="fib-result"><div class="fib-label">{lvl}</div><div class="fib-value">${val}</div></div>', unsafe_allow_html=True)
        st.info(f"Range: ${fib_high:.2f} to ${fib_low:.2f} = ${rng:.2f}")
    elif fib_high > 0 and fib_low > 0:
        st.error("Contract High must be greater than Contract Low")

    st.markdown('</div>', unsafe_allow_html=True)

# ========= MAIN =========
if __name__ == "__main__":
    pass