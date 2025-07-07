import streamlit as st
from datetime import datetime, timedelta

# --- SLOPE SETTINGS ---
SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.1700,
    "NVDA": -0.0660,
    "AAPL": -0.0670,
    "AMZN": -0.1000,
    "GOOGL": -0.0920,
}

# --- Generate 30-min Time Slots (08:30–14:30) ---
def generate_time_blocks():
    base = datetime.strptime("08:30", "%H:%M")
    return [(base + timedelta(minutes=30*i)).strftime("%H:%M") for i in range(13)]

# --- SPX Block Counter (overnight + trading, skip 16:00–16:59) ---
def calculate_spx_blocks(a, t):
    dt, blocks = a, 0
    while dt < t:
        if dt.hour != 16:
            blocks += 1
        dt += timedelta(minutes=30)
    return blocks

# --- Stock Block Counter (exact anchor→target, 30-min steps) ---
def calculate_stock_blocks(a, t):
    if t < a: return 0
    dt, blocks = a, 0
    while dt <= t:
        blocks += 1
        dt += timedelta(minutes=30)
    return blocks

# --- SPX Forecast (entry + exit) ---
def generate_spx_forecast(price, slope, anchor_dt):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = anchor_dt.replace(hour=h, minute=m) + timedelta(days=1)
        b = calculate_spx_blocks(anchor_dt, tgt)
        rows.append({
            "Time": slot,
            "SPX Entry": round(price + slope*b, 2),
            "SPX Exit":  round(price - slope*b, 2)
        })
    return rows

# --- Stock Forecast (prev-day anchors entry from low, exit from high) ---
def generate_stock_forecast(low, high, slope, a_low, a_high):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt_low  = a_low.replace(hour=h, minute=m) 
        tgt_high = a_high.replace(hour=h, minute=m)
        bl = calculate_stock_blocks(a_low, tgt_low)
        bh = calculate_stock_blocks(a_high, tgt_high)
        rows.append({
            "Time": slot,
            "Entry": round(low  + slope*bl,  2),
            "Exit":  round(high - slope*bh, 2),
        })
    return rows

# --- Page & Theme ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide")
st.markdown("""
<style>
#MainMenu, footer {visibility:hidden;}
.sidebar .sidebar-content {background:#1f4068; color:white; padding:1rem;}
.header {background:linear-gradient(90deg,#2a5d84,#1f4068);padding:1rem;border-radius:0.5rem;margin-bottom:1rem;text-align:center;color:white;}
.tab-header {color:#1f4068;font-weight:bold;margin-top:1rem;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header"><h1>📊 Dr Didy Forecast</h1></div>', unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", value=datetime.now().date()+timedelta(days=1))
    st.markdown("---")
    st.subheader("Slopes")
    for k in SLOPES:
        SLOPES[k] = st.number_input(k.replace("_"," "), value=SLOPES[k], format="%.4f", key=f"slope_{k}")

# --- Tabs ---
tab_spx, tab_tsla, tab_nvda, tab_aapl, tab_amzn, tab_googl = st.tabs([
    "🧭 SPX","🚗 TSLA","🧠 NVDA","🍎 AAPL","📦 AMZN","🔍 GOOGL"
])

# --- SPX Tab ---
with tab_spx:
    st.markdown('<div class="tab-header">SPX Forecast (Yesterday’s High/Close/Low)</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    spx_high_p = c1.number_input("High Price",  value=6185.8, format="%.2f", key="spx_hp")
    spx_high_t = c1.time_input("High Time",  value=datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
    spx_close_p= c2.number_input("Close Price",value=6170.2, format="%.2f", key="spx_cp")
    spx_close_t= c2.time_input("Close Time",value=datetime(2025,1,1,15,0).time(), step=1800, key="spx_ct")
    spx_low_p  = c3.number_input("Low Price",   value=6130.4, format="%.2f", key="spx_lp")
    spx_low_t  = c3.time_input("Low Time",    value=datetime(2025,1,1,13,30).time(), step=1800, key="spx_lt")
    if st.button("🔮 Generate SPX", key="btn_spx"):
        ah = datetime.combine(forecast_date - timedelta(days=1), spx_high_t)
        ac = datetime.combine(forecast_date - timedelta(days=1), spx_close_t)
        al = datetime.combine(forecast_date - timedelta(days=1), spx_low_t)
        st.subheader("📈 High Anchor")
        st.dataframe(generate_spx_forecast(spx_high_p, SLOPES["SPX_HIGH"], ah), use_container_width=True)
        st.subheader("📉 Close Anchor")
        st.dataframe(generate_spx_forecast(spx_close_p, SLOPES["SPX_CLOSE"], ac), use_container_width=True)
        st.subheader("📊 Low Anchor")
        st.dataframe(generate_spx_forecast(spx_low_p, SLOPES["SPX_LOW"], al), use_container_width=True)

# --- Stock Tab Helper (prev-day anchors) ---
def stock_tab(tab, label):
    with tab:
        st.markdown(f'<div class="tab-header">{label} Forecast (Yesterday’s High/Low)</div>', unsafe_allow_html=True)
        col = st.columns(2)[0]
        low_p  = col.number_input(f"{label} Prev-Day Low Price",  value=0.0, format="%.2f", key=f"{label}_low_p")
        low_t  = col.time_input   (f"{label} Prev-Day Low Time",   value=datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_low_t")
        high_p = col.number_input(f"{label} Prev-Day High Price", value=0.0, format="%.2f", key=f"{label}_high_p")
        high_t = col.time_input   (f"{label} Prev-Day High Time",  value=datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_high_t")
        if st.button(f"🔮 Generate {label}", key=f"btn_{label}"):
            pd_low  = datetime.combine(forecast_date - timedelta(days=1), low_t)
            pd_high = datetime.combine(forecast_date - timedelta(days=1), high_t)
            df = generate_stock_forecast(low_p, high_p, SLOPES[label], pd_low, pd_high)
            st.dataframe(df, use_container_width=True)

# --- Apply to Stocks ---
stock_tab(tab_tsla, "TSLA")
stock_tab(tab_nvda, "NVDA")
stock_tab(tab_aapl, "AAPL")
stock_tab(tab_amzn, "AMZN")
stock_tab(tab_googl,"GOOGL")
