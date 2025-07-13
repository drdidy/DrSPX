import streamlit as st
from datetime import datetime, time, timedelta
import pandas as pd

# --- SLOPE SETTINGS ---
SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.1180,
    "NVDA": -0.0485,
    "AAPL": -0.0200,
    "MSFT": -0.1964,
    "AMZN": -0.0782,
    "GOOGL": -0.0485,
}

# --- HELPERS ---
def generate_time_blocks():
    base = datetime.strptime("08:30", "%H:%M")
    return [(base + timedelta(minutes=30 * i)).strftime("%H:%M") for i in range(13)]

def calculate_spx_blocks(a, t):
    dt, blocks = a, 0
    while dt < t:
        if dt.hour != 16:
            blocks += 1
        dt += timedelta(minutes=30)
    return blocks

# ← only this helper changed, everything else is identical
def calculate_stock_blocks(a, t):
    if t <= a:
        return 0
    return int((t - a).total_seconds() // 1800)

def generate_spx(price, slope, anchor, fd):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_spx_blocks(anchor, tgt)
        rows.append({"Time": slot,
                     "Entry": round(price + slope * b, 2),
                     "Exit":  round(price - slope * b, 2)})
    return pd.DataFrame(rows)

def generate_stock(price, slope, anchor, fd, invert=False):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_stock_blocks(anchor, tgt)
        if invert:
            e = price - slope * b
            x = price + slope * b
        else:
            e = price + slope * b
            x = price - slope * b
        rows.append({"Time": slot, "Entry": round(e, 2), "Exit": round(x, 2)})
    return pd.DataFrame(rows)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Dr Didy Forecast",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME CSS BLOCKS (unchanged) ---
light_css = """<style>…</style>"""
dark_css  = """<style>…</style>"""

with st.sidebar:
    theme = st.radio("🎨 Theme", ["Light","Dark"])
if theme == "Dark":
    st.markdown(dark_css, unsafe_allow_html=True)
else:
    st.markdown(light_css, unsafe_allow_html=True)

# --- MAIN CONTAINER WRAP ---
st.markdown('<div class="main-container">', unsafe_allow_html=True)

# --- 🏷️ RESTORED BANNER ---
st.markdown(
    '<div class="app-header"><h1>📊 Dr Didy Forecast</h1></div>',
    unsafe_allow_html=True
)

# --- SIDEBAR SETTINGS (unchanged) ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", datetime.now().date() + timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_"," "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- TABS (with MSFT) ---
tabs = st.tabs(["🧭 SPX","🚗 TSLA","🧠 NVDA","🍎 AAPL","🪟 MSFT","📦 AMZN","🔍 GOOGL"])

# --- SPX TAB (Mon/Wed/Fri, Tue, Thu logic) ---
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)

    # inputs...
    c1, c2, c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price",  min_value=0.0, value=6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("🕒 High Time",     datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
    cp = c2.number_input("⏹️ Close Price", min_value=0.0, value=6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("🕒 Close Time",    datetime(2025,1,1,15,0).time(),  step=1800, key="spx_ct")
    lp = c3.number_input("🔽 Low Price",   min_value=0.0, value=6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("🕒 Low Time",      datetime(2025,1,1,13,30).time(), step=1800, key="spx_lt")

    is_tue = forecast_date.weekday() == 1
    is_thu = forecast_date.weekday() == 3

    # Tuesday and Thursday inputs (unchanged)...

    if st.button("🔮 Generate SPX", key="btn_spx"):
        ah = datetime.combine(forecast_date - timedelta(days=1), ht)
        ac = datetime.combine(forecast_date - timedelta(days=1), ct)
        al = datetime.combine(forecast_date - timedelta(days=1), lt)

        if is_tue:
            # Tuesday contract-low table...
            anchor_dt = datetime.combine(forecast_date, tue_cl_time)
            rows = []
            for slot in generate_time_blocks():
                h, m = map(int, slot.split(":"))
                tgt = datetime.combine(forecast_date, time(h, m))
                b = calculate_spx_blocks(anchor_dt, tgt)
                proj = tue_cl_price + (-0.5250) * b
                rows.append({"Time": slot, "Projected": round(proj, 2)})
            st.subheader("🔹 Tuesday Entry Table")
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

        elif is_thu:
            # Thursday OTM-line and bounce-low (unchanged)...

        else:
            # Mon/Wed/Fri high/close/low cards & tables (unchanged)...

# --- STOCK TABS (including MSFT) ---
icons = {"TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}
for i, label in enumerate(["TSLA","NVDA","AAPL","MSFT","AMZN","GOOGL"], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>', unsafe_allow_html=True)
        # inputs & Generate logic (unchanged)...

# --- CLOSE MAIN CONTAINER ---
st.markdown('</div>', unsafe_allow_html=True)