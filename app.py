import streamlit as st
from datetime import datetime, time, timedelta
import pandas as pd

# --- SLOPE SETTINGS ---
SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.2583,
    "NVDA": -0.0871,
    "AAPL": -0.1775,
    "AMZN": -0.1714,
    "GOOGL": -0.2091,
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

def calculate_stock_blocks(a, t):
    prev_close = a.replace(hour=15, minute=0)
    bp = max(0, int((prev_close - a).total_seconds() // 1800))
    next_open = datetime.combine(t.date(), time(8,30))
    next_close= datetime.combine(t.date(), time(15,0))
    bn = 0 if t <= next_open else int((min(t,next_close) - next_open).total_seconds() // 1800)
    return bp + bn

def generate_spx(price, slope, anchor, fd):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_spx_blocks(anchor, tgt)
        entry = price + slope * b
        exit_ = price - slope * b
        rows.append({"Time": slot, "Entry": round(entry,2), "Exit": round(exit_,2)})
    return pd.DataFrame(rows)

def generate_stock(price, slope, anchor, fd, invert=False):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_stock_blocks(anchor, tgt)
        if invert:
            entry = price - slope * b
            exit_ = price + slope * b
        else:
            entry = price + slope * b
            exit_ = price - slope * b
        rows.append({"Time": slot, "Entry": round(entry,2), "Exit": round(exit_,2)})
    return pd.DataFrame(rows)

# --- STREAMLIT & CSS ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide")
st.markdown("""
<style>
body {background:#eef2f6;font-family:sans-serif;}
.sidebar .sidebar-content {background:#1f1f3b;color:#fff;padding:1rem;border-radius:0 1rem 1rem 0;}
.app-header {margin:1rem;padding:1.5rem;background:#fff;border-radius:1rem;box-shadow:0 4px 12px rgba(0,0,0,0.1);text-align:center;}
.tab-header {margin:1.5rem 2rem 0.5rem;font-size:1.25rem;color:#333;font-weight:600;}
.card {background:#fff;margin:1rem 2rem;padding:1rem;border-radius:1rem;box-shadow:0 4px 12px rgba(0,0,0,0.05);}
.metric-container {margin:1rem 2rem;}
.stButton>button {border-radius:0.5rem;padding:0.5rem 1rem;}
@media(max-width:768px){
  .app-header {margin:1rem;padding:1rem;}
  .tab-header {margin:1rem;font-size:1.1rem;}
  .card {margin:1rem;}
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header"><h1>📊 Dr Didy Forecast</h1></div>', unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", datetime.now().date()+timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_"," "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- TABS ---
tabs = st.tabs(["🧭 SPX","🚗 TSLA","🧠 NVDA","🍎 AAPL","📦 AMZN","🔍 GOOGL"])

# --- SPX TAB ---
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price", 6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("🕒 High Time", datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
    cp = c2.number_input("⏹️ Close Price", 6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("🕒 Close Time", datetime(2025,1,1,15,0).time(), step=1800, key="spx_ct")
    lp = c3.number_input("🔽 Low Price", 6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("🕒 Low Time", datetime(2025,1,1,13,30).time(), step=1800, key="spx_lt")
    if st.button("🔮 Generate SPX", key="btn_spx"):
        ah = datetime.combine(forecast_date - timedelta(days=1), ht)
        ac = datetime.combine(forecast_date - timedelta(days=1), ct)
        al = datetime.combine(forecast_date - timedelta(days=1), lt)
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        m1,m2,m3 = st.columns(3)
        m1.metric("🔼 High Anchor", f"{hp:.2f}", delta=f"{SLOPES['SPX_HIGH']:.4f}/blk")
        m2.metric("⏹️ Close Anchor", f"{cp:.2f}", delta=f"{SLOPES['SPX_CLOSE']:.4f}/blk")
        m3.metric("🔽 Low Anchor", f"{lp:.2f}", delta=f"{SLOPES['SPX_LOW']:.4f}/blk")
        st.markdown('</div>', unsafe_allow_html=True)
        for icon, title, price, slope, anchor in [
            ("🔼","High Anchor", hp, SLOPES["SPX_HIGH"], ah),
            ("⏹️","Close Anchor",cp, SLOPES["SPX_CLOSE"],ac),
            ("🔽","Low Anchor", lp, SLOPES["SPX_LOW"],  al),
        ]:
            with st.expander(f"{icon} {title} Table"):
                st.markdown('<div class="card">', unsafe_allow_html=True)
                df = generate_spx(price, slope, anchor, forecast_date)
                st.dataframe(df.round(2), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

# --- STOCK TABS ---
icons = {"TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","AMZN":"📦","GOOGL":"🔍"}
for i, label in enumerate(["TSLA","NVDA","AAPL","AMZN","GOOGL"], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>', unsafe_allow_html=True)
        col = st.columns(2)[0]
        lp = col.number_input("🔽 Prev-Day Low Price", 0.0, format="%.2f", key=f"{label}_low_price")
        lt = col.time_input("🕒 Prev-Day Low Time", datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_low_time")
        hp = col.number_input("🔼 Prev-Day High Price",0.0, format="%.2f", key=f"{label}_high_price")
        ht = col.time_input("🕒 Prev-Day High Time",datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_high_time")
        if st.button(f"🔮 Generate {label}", key=f"btn_{label}"):
            a_low  = datetime.combine(forecast_date - timedelta(days=1), lt)
            a_high = datetime.combine(forecast_date - timedelta(days=1), ht)
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            s1,s2 = st.columns(2)
            s1.metric("🔽 Low Anchor",  f"{lp:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
            s2.metric("🔼 High Anchor", f"{hp:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
            st.markdown('</div>', unsafe_allow_html=True)
            with st.expander("🔻 Low Anchor Table"):
                st.markdown('<div class="card">', unsafe_allow_html=True)
                df_low = generate_stock(lp, SLOPES[label], a_low, forecast_date, invert=True)
                st.dataframe(df_low.round(2), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with st.expander("🔺 High Anchor Table"):
                st.markdown('<div class="card">', unsafe_allow_html=True)
                df_high = generate_stock(hp, SLOPES[label], a_high, forecast_date, invert=False)
                st.dataframe(df_high.round(2), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
