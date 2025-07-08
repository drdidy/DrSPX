import streamlit as st
from datetime import datetime, time, timedelta

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
    next_open  = datetime.combine(t.date(), time(8,30))
    next_close = datetime.combine(t.date(), time(15,0))
    bn = 0 if t <= next_open else int((min(t,next_close) - next_open).total_seconds() // 1800)
    return bp + bn

def generate_spx(price, slope, anchor, fd):
    out = []
    for slot in generate_time_blocks():
        h,m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h,m))
        b = calculate_spx_blocks(anchor, tgt)
        out.append({"Time": slot, "Entry": round(price + slope*b,2), "Exit": round(price - slope*b,2)})
    return out

def generate_stock(price, slope, anchor, fd, invert=False):
    out = []
    for slot in generate_time_blocks():
        h,m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h,m))
        b = calculate_stock_blocks(anchor, tgt)
        if invert:
            out.append({"Time": slot, "Entry": round(price - slope*b,2), "Exit": round(price + slope*b,2)})
        else:
            out.append({"Time": slot, "Entry": round(price + slope*b,2), "Exit": round(price - slope*b,2)})
    return out

# --- Streamlit Setup & Supercharge CSS ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
/* Responsive */
meta[name="viewport"] {width=device-width; initial-scale=1}

/* Base */
body {background: #eef2f6; font-family: 'Segoe UI', sans-serif; margin:0;}
.stApp {padding: 0;}

/* Sidebar */
.sidebar .sidebar-content {
  background: #252b42;
  color: #fff;
  padding: 1.2rem;
  border-radius: 0 1rem 1rem 0;
  box-shadow: 4px 0 20px rgba(0,0,0,0.3);
}

/* Header */
.app-header {
  background: linear-gradient(135deg, #3a506b, #1b1f3b);
  padding: 2rem;
  border-radius: 1rem;
  margin: 1rem 2rem 2rem 2rem;
  text-align: center;
  color: #fff;
  box-shadow: 0 12px 30px rgba(0,0,0,0.3);
}
.app-header h1 {
  margin: 0;
  font-size: 3rem;
  letter-spacing: 2px;
  text-shadow: 2px 2px 8px rgba(0,0,0,0.5);
}
.app-header p {
  margin: 0.5rem 0 0;
  font-size: 1.2rem;
  color: #c5d2e0;
  opacity: 0.9;
}

/* Tabs */
.tab-header {
  font-size: 1.3rem;
  color: #252b42;
  font-weight: 700;
  margin-top: 1.5rem;
}

/* Card Base */
.card {
  background: #fff;
  border-radius: 1rem;
  padding: 1.5rem;
  margin: 1rem 2rem;
  position: relative;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  box-shadow:
    0 4px 15px rgba(0,0,0,0.1),
    inset 0 0 0 1px rgba(0,0,0,0.05);
}

/* Card Hover for 3D lift */
.card:hover {
  transform: translateY(-8px) rotateX(2deg);
  box-shadow:
    0 16px 40px rgba(0,0,0,0.2),
    inset 0 0 0 1px rgba(0,0,0,0.08);
}

/* Accent Borders */
.card-high {border-left: 8px solid #ff6b6b;}
.card-close{border-left: 8px solid #4ecdc4;}
.card-low  {border-left: 8px solid #f7b731;}

/* Metrics container */
.metric-container {
  margin: 1rem 2rem;
}

/* Buttons */
.stButton>button {
  background: linear-gradient(135deg, #3a506b, #1b1f3b) !important;
  color: #fff !important;
  border: none;
  padding: 0.6rem 1.2rem;
  font-size: 1rem;
  border-radius: 0.6rem;
  box-shadow: 0 6px 20px rgba(0,0,0,0.2);
  transition: background 0.3s ease, transform 0.2s ease;
}
.stButton>button:hover {
  background: linear-gradient(135deg, #50638c, #2b324f) !important;
  transform: translateY(-2px);
}

/* DataFrame Styling */
.element-container .stDataFrame>div {
  border-radius: 1rem !important;
  overflow: hidden;
}

/* Responsive Tweaks */
@media(max-width: 768px) {
  .app-header {padding: 1rem; margin: 1rem;}
  .app-header h1 {font-size: 2rem;}
  .tab-header {font-size: 1.1rem;}
  .card {margin: 1rem;}
  .metric-container {margin: 1rem;}
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="app-header"><h1>📊 Dr Didy Forecast</h1>'
    '<p>Precision Entry/Exit Projections in Stunning 3D</p></div>',
    unsafe_allow_html=True
)

# --- Sidebar Controls ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", datetime.now().date() + timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_"," "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- Tabs ---
tabs = st.tabs(["🧭 SPX","🚗 TSLA","🧠 NVDA","🍎 AAPL","📦 AMZN","🔍 GOOGL"])

# --- SPX Tab ---
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
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
        # metrics
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        m1,m2,m3 = st.columns(3)
        m1.metric("High Anchor", f"{hp:.2f}", delta=f"{SLOPES['SPX_HIGH']:.4f}/blk")
        m2.metric("Close Anchor", f"{cp:.2f}", delta=f"{SLOPES['SPX_CLOSE']:.4f}/blk")
        m3.metric("Low Anchor", f"{lp:.2f}", delta=f"{SLOPES['SPX_LOW']:.4f}/blk")
        st.markdown('</div>', unsafe_allow_html=True)
        # tables
        for cls, icon, title, price, slope, anchor in [
            ("card-high","🔼","High", hp, SLOPES["SPX_HIGH"], ah),
            ("card-close","⏹️","Close",cp, SLOPES["SPX_CLOSE"],ac),
            ("card-low","🔽","Low",  lp, SLOPES["SPX_LOW"],  al),
        ]:
            with st.expander(f"{icon} {title} Anchor Table"):
                st.markdown(f'<div class="card {cls}">', unsafe_allow_html=True)
                st.dataframe(generate_spx(price, slope, anchor, forecast_date), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

# --- Stock Tabs ---
icons={"TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","AMZN":"📦","GOOGL":"🔍"}
for i,label in enumerate(["TSLA","NVDA","AAPL","AMZN","GOOGL"],start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>', unsafe_allow_html=True)
        col = st.columns(2)[0]
        low_p  = col.number_input("🔽 Prev-Day Low Price", 0.0, format="%.2f", key=f"{label}_low_price")
        low_t  = col.time_input("🕒 Prev-Day Low Time", datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_low_time")
        high_p = col.number_input("🔼 Prev-Day High Price", 0.0, format="%.2f", key=f"{label}_high_price")
        high_t = col.time_input("🕒 Prev-Day High Time", datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_high_time")
        if st.button(f"🔮 Generate {label}", key=f"btn_{label}"):
            a_low  = datetime.combine(forecast_date - timedelta(days=1), low_t)
            a_high = datetime.combine(forecast_date - timedelta(days=1), high_t)
            # metrics
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            s1,s2 = st.columns(2)
            s1.metric("Low Anchor",  f"{low_p:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
            s2.metric("High Anchor", f"{high_p:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
            st.markdown('</div>', unsafe_allow_html=True)
            # tables
            with st.expander("🔻 Low-Anchor Table"):
                st.markdown(f'<div class="card card-low">', unsafe_allow_html=True)
                st.dataframe(generate_stock(low_p, SLOPES[label], a_low, forecast_date, invert=True), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with st.expander("🔺 High-Anchor Table"):
                st.markdown(f'<div class="card card-high">', unsafe_allow_html=True)
                st.dataframe(generate_stock(high_p, SLOPES[label], a_high, forecast_date, invert=False), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
