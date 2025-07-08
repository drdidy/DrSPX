import streamlit as st
from datetime import datetime, time, timedelta

# --- SLOPE SETTINGS ---
SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.1478,
    "NVDA": -0.0871,
    "AAPL": -0.1775,
    "AMZN": -0.1714,
    "GOOGL": -0.2091,
}

# --- Generate 30-min slots 08:30–14:30 ---
def generate_time_blocks():
    base = datetime.strptime("08:30", "%H:%M")
    return [(base + timedelta(minutes=30 * i)).strftime("%H:%M") for i in range(13)]

# --- SPX block counter (overnight + trading; skip 16:00–16:59) ---
def calculate_spx_blocks(a, t):
    dt, blocks = a, 0
    while dt < t:
        if dt.hour != 16:
            blocks += 1
        dt += timedelta(minutes=30)
    return blocks

# --- Stock block counter (prev-day 08:30–15:00 & next-day 08:30–target) ---
def calculate_stock_blocks(a, t):
    prev_close = a.replace(hour=15, minute=0)
    blocks_prev = max(0, int((prev_close - a).total_seconds() // 1800))
    next_open  = datetime.combine(t.date(), time(8, 30))
    next_close = datetime.combine(t.date(), time(15, 0))
    if t <= next_open:
        blocks_next = 0
    else:
        blocks_next = int((min(t, next_close) - next_open).total_seconds() // 1800)
    return blocks_prev + blocks_next

# --- Forecast generators ---
def generate_spx_forecast(price, slope, anchor_dt, forecast_date):
    out = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(forecast_date, time(h, m))
        b = calculate_spx_blocks(anchor_dt, tgt)
        out.append({"Time": slot, "Entry": round(price + slope * b, 2), "Exit": round(price - slope * b, 2)})
    return out

def generate_stock_table(price, slope, anchor_dt, forecast_date, invert=False):
    out = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(forecast_date, time(h, m))
        b = calculate_stock_blocks(anchor_dt, tgt)
        if invert:
            out.append({"Time": slot,
                        "Entry": round(price - slope * b, 2),
                        "Exit":  round(price + slope * b, 2)})
        else:
            out.append({"Time": slot,
                        "Entry": round(price + slope * b, 2),
                        "Exit":  round(price - slope * b, 2)})
    return out

# --- Streamlit page setup & CSS ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide")
st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
.app-header {
    font-family: 'Segoe UI', sans-serif;
    background: linear-gradient(90deg, #2a5d84, #1f4068);
    padding: 1.5rem; text-align: center; border-radius: 0.5rem;
    margin-bottom: 1rem; color: white;
}
.sidebar .sidebar-content {
    background-color: #1f4068; color: white; padding: 1rem;
    border-radius: 0 0.5rem 0.5rem 0; margin-bottom: 1rem;
}
.card {
    background: white; padding: 1rem; border-radius: 0.5rem;
    box-shadow: 0 4px 10px rgba(0,0,0,0.1); margin-bottom: 1rem;
}
.tab-header {
    color: #1f4068; font-weight: 600; margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header"><h1>📊 Dr Didy Forecast</h1></div>', unsafe_allow_html=True)

# --- Sidebar controls ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date",
                                  value=datetime.now().date() + timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(f"{k.replace('_',' ')}", -1.0, 1.0,
                              value=SLOPES[k], step=0.0001)

# --- Tabs ---
tabs = st.tabs(["🧭 SPX","🚗 TSLA","🧠 NVDA","🍎 AAPL","📦 AMZN","🔍 GOOGL"])

# --- SPX Tab ---
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast (Yesterday’s Anchors)</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price", value=6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("🕒 High Time",   value=datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
    cp = c2.number_input("⏹️ Close Price", value=6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("🕒 Close Time",  value=datetime(2025,1,1,15,0).time(), step=1800, key="spx_ct")
    lp = c3.number_input("🔽 Low Price",  value=6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("🕒 Low Time",    value=datetime(2025,1,1,13,30).time(), step=1800, key="spx_lt")

    if st.button("🔮 Generate SPX"):
        ah = datetime.combine(forecast_date - timedelta(days=1), ht)
        ac = datetime.combine(forecast_date - timedelta(days=1), ct)
        al = datetime.combine(forecast_date - timedelta(days=1), lt)
        for icon, title, price, slope, anchor in [
            ("🔼", "High Anchor", hp, SLOPES["SPX_HIGH"], ah),
            ("⏹️", "Close Anchor", cp, SLOPES["SPX_CLOSE"], ac),
            ("🔽", "Low Anchor", lp, SLOPES["SPX_LOW"], al),
        ]:
            st.markdown(f"### {icon} {title}")
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.dataframe(generate_spx_forecast(price, slope, anchor, forecast_date),
                             use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

# --- Stock Tabs ---
icons = {"TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","AMZN":"📦","GOOGL":"🔍"}
for i, label in enumerate(["TSLA","NVDA","AAPL","AMZN","GOOGL"], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast (Prev-Day Anchors)</div>', unsafe_allow_html=True)
        col = st.columns(2)[0]
        low_p  = col.number_input(f"🔽 Prev-Day Low Price",  value=0.0, format="%.2f", key=f"{label}_low_p")
        low_t  = col.time_input(f"🕒 Prev-Day Low Time",    value=datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_low_t")
        high_p = col.number_input(f"🔼 Prev-Day High Price", value=0.0, format="%.2f", key=f"{label}_high_p")
        high_t = col.time_input(f"🕒 Prev-Day High Time",   value=datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_high_t")

        if st.button(f"🔮 Generate {label}"):
            a_low  = datetime.combine(forecast_date - timedelta(days=1), low_t)
            a_high = datetime.combine(forecast_date - timedelta(days=1), high_t)

            st.markdown("#### 🔻 Low-Anchor Table")
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.dataframe(generate_stock_table(low_p, SLOPES[label], a_low, forecast_date, invert=True),
                             use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("#### 🔺 High-Anchor Table")
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.dataframe(generate_stock_table(high_p, SLOPES[label], a_high, forecast_date, invert=False),
                             use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
