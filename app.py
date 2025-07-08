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

# --- Helpers ---
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
    next_open  = datetime.combine(t.date(), time(8, 30))
    next_close = datetime.combine(t.date(), time(15, 0))
    bn = 0 if t <= next_open else int((min(t, next_close) - next_open).total_seconds() // 1800)
    return bp + bn

def generate_spx(price, slope, anchor, fd):
    out = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_spx_blocks(anchor, tgt)
        out.append({"Time": slot, "Entry": round(price + slope * b, 2), "Exit": round(price - slope * b, 2)})
    return out

def generate_stock(price, slope, anchor, fd, invert=False):
    out = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_stock_blocks(anchor, tgt)
        if invert:
            out.append({"Time": slot, "Entry": round(price - slope * b, 2), "Exit": round(price + slope * b, 2)})
        else:
            out.append({"Time": slot, "Entry": round(price + slope * b, 2), "Exit": round(price - slope * b, 2)})
    return out

# --- Streamlit & CSS ---
st.set_page_config(
    page_title="Dr Didy Forecast",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {background:#f7f8fa; font-family:'Segoe UI',sans-serif;}
/* sidebar styling */
.sidebar .sidebar-content {
    background:#0b132b; color:#fff; padding:1rem;
    border-radius:0 0.5rem 0.5rem 0;
}
/* header card */
.app-header {
    background:linear-gradient(90deg,#3a506b,#1f4068);
    padding:2rem; border-radius:0.5rem; margin-bottom:1.5rem;
    text-align:center; color:#fff; box-shadow:0 4px 12px rgba(0,0,0,0.2);
}
.app-header h1 {margin:0; font-size:2rem;}
.app-header p  {margin:0.5rem 0 0; color:#c5d2e0;}
.tab-header {font-size:1.1rem; color:#1f4068; margin-top:1rem; font-weight:600;}
.card {
    background:#fff; border-left:4px solid #1f4068;
    padding:1rem; border-radius:0.5rem; margin-bottom:1rem;
    box-shadow:0 4px 10px rgba(0,0,0,0.1);
}
.metric-container {margin-bottom:1.5rem;}
.stButton>button {border-radius:0.3rem;}
@media(max-width:768px) {
    .app-header {padding:1rem;}
    .app-header h1 {font-size:1.5rem;}
    .tab-header {font-size:1rem;}
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="app-header"><h1>📊 Dr Didy Forecast</h1>'
    '<p>Interactive entry/exit projections</p></div>',
    unsafe_allow_html=True,
)

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", datetime.now().date() + timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_", " "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- Tabs ---
tabs = st.tabs(["🧭 SPX", "🚗 TSLA", "🧠 NVDA", "🍎 AAPL", "📦 AMZN", "🔍 GOOGL"])

# --- SPX Tab ---
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price", value=6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("🕒 High Time", value=datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
    cp = c2.number_input("⏹️ Close Price", value=6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("🕒 Close Time", value=datetime(2025,1,1,15,0).time(), step=1800, key="spx_ct")
    lp = c3.number_input("🔽 Low Price", value=6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("🕒 Low Time", value=datetime(2025,1,1,13,30).time(), step=1800, key="spx_lt")
    if st.button("🔮 Generate SPX", key="btn_spx"):
        ah = datetime.combine(forecast_date - timedelta(days=1), ht)
        ac = datetime.combine(forecast_date - timedelta(days=1), ct)
        al = datetime.combine(forecast_date - timedelta(days=1), lt)
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("High Anchor", f"{hp:.2f}", delta=f"{SLOPES['SPX_HIGH']:.4f}/blk")
        m2.metric("Close Anchor", f"{cp:.2f}", delta=f"{SLOPES['SPX_CLOSE']:.4f}/blk")
        m3.metric("Low Anchor", f"{lp:.2f}", delta=f"{SLOPES['SPX_LOW']:.4f}/blk")
        st.markdown("</div>", unsafe_allow_html=True)
        for title, price, slope, anchor in [
            ("High", hp, SLOPES["SPX_HIGH"], ah),
            ("Close", cp, SLOPES["SPX_CLOSE"], ac),
            ("Low", lp, SLOPES["SPX_LOW"], al),
        ]:
            with st.expander(f"Show {title} Anchor Table"):
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.dataframe(generate_spx(price, slope, anchor, forecast_date), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

# --- Stock Tabs ---
icons = {"TSLA": "🚗", "NVDA": "🧠", "AAPL": "🍎", "AMZN": "📦", "GOOGL": "🔍"}
for i, label in enumerate(["TSLA", "NVDA", "AAPL", "AMZN", "GOOGL"], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>', unsafe_allow_html=True)
        col = st.columns(2)[0]
        low_p = col.number_input("🔽 Prev-Day Low Price", 0.0, format="%.2f", key=f"{label}_low_price")
        low_t = col.time_input("🕒 Prev-Day Low Time", datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_low_time")
        high_p = col.number_input("🔼 Prev-Day High Price", 0.0, format="%.2f", key=f"{label}_high_price")
        high_t = col.time_input("🕒 Prev-Day High Time", datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_high_time")
        if st.button(f"🔮 Generate {label}", key=f"btn_{label}"):
            a_low = datetime.combine(forecast_date - timedelta(days=1), low_t)
            a_high = datetime.combine(forecast_date - timedelta(days=1), high_t)
            with st.expander("🔻 Low-Anchor Table"):
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.dataframe(generate_stock(low_p, SLOPES[label], a_low, forecast_date, invert=True), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with st.expander("🔺 High-Anchor Table"):
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.dataframe(generate_stock(high_p, SLOPES[label], a_high, forecast_date, invert=False), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
