import streamlit as st
from datetime import datetime, time, timedelta

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
def calculate_spx_blocks(anchor_dt, target_dt):
    dt, blocks = anchor_dt, 0
    while dt < target_dt:
        if dt.hour != 16:
            blocks += 1
        dt += timedelta(minutes=30)
    return blocks

# --- Stock Block Counter (prev-day 08:30–15:00 & next-day 08:30–target, 30-min) ---
def calculate_stock_blocks(anchor_dt, target_dt):
    # prev-day
    prev_close = anchor_dt.replace(hour=15, minute=0)
    blocks_prev = max(0, int((prev_close - anchor_dt).total_seconds() // 1800))
    # next-day
    next_open = datetime.combine(target_dt.date(), time(8,30))
    next_close = datetime.combine(target_dt.date(), time(15,0))
    if target_dt <= next_open:
        blocks_next = 0
    else:
        blocks_next = int((min(target_dt, next_close) - next_open).total_seconds() // 1800)
    return blocks_prev + blocks_next

# --- SPX Forecast (entry + exit) ---
def generate_spx_forecast(price, slope, anchor_dt, forecast_date):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(forecast_date, time(h, m))
        blocks = calculate_spx_blocks(anchor_dt, tgt)
        rows.append({
            "Time":     slot,
            "Entry":    round(price + slope * blocks, 2),
            "Exit":     round(price - slope * blocks, 2),
        })
    return rows

# --- Stock High-Anchor Forecast ---
def generate_stock_high_table(high_price, slope, anchor_dt, forecast_date):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(forecast_date, time(h, m))
        blocks = calculate_stock_blocks(anchor_dt, tgt)
        rows.append({
            "Time":  slot,
            "Entry": round(high_price + slope * blocks, 2),
            "Exit":  round(high_price - slope * blocks, 2),
        })
    return rows

# --- Stock Low-Anchor Forecast ---
def generate_stock_low_table(low_price, slope, anchor_dt, forecast_date):
    # invert slope for low anchor
    slope_low = -slope
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(forecast_date, time(h, m))
        blocks = calculate_stock_blocks(anchor_dt, tgt)
        rows.append({
            "Time":  slot,
            "Entry": round(low_price + slope_low * blocks, 2),
            "Exit":  round(low_price - slope_low * blocks, 2),
        })
    return rows

# --- Streamlit Setup ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide")
st.markdown("""
<style>
#MainMenu, footer {visibility:hidden;}
.sidebar .sidebar-content {background:#1f4068; color:white; padding:1rem;}
.header {background:linear-gradient(90deg,#2a5d84,#1f4068); padding:1rem; border-radius:0.5rem; margin-bottom:1rem; text-align:center; color:white;}
.tab-header {color:#1f4068; font-weight:bold; margin-top:1rem;}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="header"><h1>📊 Dr Didy Forecast</h1></div>', unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", value=datetime.now().date() + timedelta(days=1))
    st.markdown("---")
    st.subheader("Slopes")
    for k in SLOPES:
        SLOPES[k] = st.number_input(k.replace("_", " "), value=SLOPES[k], format="%.4f")

# --- Tabs ---
tabs = st.tabs(["SPX","TSLA","NVDA","AAPL","AMZN","GOOGL"])

# --- SPX Tab ---
with tabs[0]:
    st.markdown('<div class="tab-header">SPX Forecast (Yesterday’s Anchors)</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    hp = c1.number_input("High Price",  value=6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("High Time",    value=datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
    cp = c2.number_input("Close Price",value=6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("Close Time",   value=datetime(2025,1,1,15,0).time(),  step=1800, key="spx_ct")
    lp = c3.number_input("Low Price",   value=6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("Low Time",     value=datetime(2025,1,1,13,30).time(), step=1800, key="spx_lt")
    if st.button("Generate SPX"):
        ah = datetime.combine(forecast_date - timedelta(days=1), ht)
        ac = datetime.combine(forecast_date - timedelta(days=1), ct)
        al = datetime.combine(forecast_date - timedelta(days=1), lt)
        for title, price, slope, anchor in [
            ("High Anchor", hp, SLOPES["SPX_HIGH"], ah),
            ("Close Anchor", cp, SLOPES["SPX_CLOSE"], ac),
            ("Low Anchor",   lp, SLOPES["SPX_LOW"],   al),
        ]:
            st.subheader(f"📈 {title}")
            st.dataframe(generate_spx_forecast(price, slope, anchor, forecast_date), use_container_width=True)

# --- Stock Tabs ---
for idx, label in enumerate(["TSLA","NVDA","AAPL","AMZN","GOOGL"], start=1):
    with tabs[idx]:
        st.markdown(f'<div class="tab-header">{label} Forecast (Prev-Day Anchors)</div>', unsafe_allow_html=True)
        col = st.columns(2)[0]
        low_p  = col.number_input("Prev-Day Low Price",  value=0.0, format="%.2f", key=f"{label}_low_p")
        low_t  = col.time_input("Prev-Day Low Time",    value=datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_low_t")
        high_p = col.number_input("Prev-Day High Price", value=0.0, format="%.2f", key=f"{label}_high_p")
        high_t = col.time_input("Prev-Day High Time",   value=datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_high_t")
        if st.button(f"Generate {label}"):
            a_low  = datetime.combine(forecast_date - timedelta(days=1), low_t)
            a_high = datetime.combine(forecast_date - timedelta(days=1), high_t)
            st.subheader("🔻 Low-Anchor Table")
            st.dataframe(generate_stock_low_table(low_p, SLOPES[label], a_low, forecast_date), use_container_width=True)
            st.subheader("🔺 High-Anchor Table")
            st.dataframe(generate_stock_high_table(high_p, SLOPES[label], a_high, forecast_date), use_container_width=True)
