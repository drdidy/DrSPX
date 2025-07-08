import streamlit as st
from datetime import datetime, time, timedelta
import pandas as pd
import altair as alt

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
    next_open  = datetime.combine(t.date(), time(8,30))
    next_close = datetime.combine(t.date(), time(15,0))
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

# --- CSS & FONTS ---
LIGHT_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
<style>
@keyframes bgMove {
  0%{background-position:0% 50%}
  50%{background-position:100% 50%}
  100%{background-position:0% 50%}
}
body {
  background: linear-gradient(135deg,#f5f7fa,#c3cfe2);
  background-size:400% 400%;
  animation:bgMove 15s ease infinite;
  font-family:'Poppins',sans-serif;
  margin:0;
}
.app-header {position:sticky;top:0;z-index:1000;}
.sidebar .sidebar-content {position:sticky;top:0;overflow:auto;height:100vh;}
.card {
  background:#e0e5ec;margin:1rem 2rem;padding:1rem;border-radius:1rem;
  box-shadow:-6px -6px 16px #fff,6px 6px 16px rgba(0,0,0,0.1);
  transition:transform .2s,box-shadow .2s;
}
.card:hover {
  transform:translateY(-4px);
  box-shadow:-8px -8px 24px #fff,8px 8px 24px rgba(0,0,0,0.15);
}
.card-high {border-left:8px solid #ff6b6b;}
.card-close{border-left:8px solid #4ecdc4;}
.card-low  {border-left:8px solid #f7b731;}
.app-header, .tab-header {color:#333;}
.tab-header {margin:1.5rem 2rem 0.5rem;font-size:1.3rem;font-weight:600;}
.stButton>button {
  background:#e0e5ec;color:#333;border:none;
  box-shadow:-4px -4px 12px #fff,4px 4px 12px rgba(0,0,0,0.1);
  border-radius:0.75rem;padding:.6rem 1.2rem;
  transition:transform .1s,box-shadow .1s;
}
.stButton>button:hover {
  transform:translateY(-2px);
  box-shadow:-6px -6px 16px #fff,6px 6px 16px rgba(0,0,0,0.15);
}
.stButton>button:active {
  transform:scale(.98);
  box-shadow:-2px -2px 6px #fff,2px 2px 6px rgba(0,0,0,0.1);
}
.footer {
  position:fixed;bottom:0;width:100%;text-align:center;
  padding:.5rem;font-size:.8rem;color:rgba(0,0,0,0.5);
}
@media(max-width:768px){
  .card {margin:1rem;}
  .tab-header {margin:1rem;font-size:1.1rem;}
}
</style>
"""

DARK_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
<style>
@keyframes bgMove {
  0%{background-position:0% 50%}
  50%{background-position:100% 50%}
  100%{background-position:0% 50%}
}
body {
  background: linear-gradient(135deg,#0f0c29,#302b63,#24243e);
  background-size:400% 400%;
  animation:bgMove 15s ease infinite;
  font-family:'Poppins',sans-serif;
  margin:0;color:#e0e0e0;
}
.app-header {position:sticky;top:0;z-index:1000;}
.sidebar .sidebar-content {position:sticky;top:0;overflow:auto;height:100vh;}
.card {
  background:#2b2f36;margin:1rem 2rem;padding:1rem;border-radius:1rem;
  box-shadow:inset 4px 4px 12px rgba(0,0,0,0.6),-4px -4px 12px rgba(255,255,255,0.05);
  transition:transform .2s,box-shadow .2s;
}
.card:hover {
  transform:translateY(-4px);
  box-shadow:inset 6px 6px 16px rgba(0,0,0,0.7),-6px -6px 16px rgba(255,255,255,0.1);
}
.card-high {border-left:8px solid #e74c3c;}
.card-close{border-left:8px solid #1abc9c;}
.card-low  {border-left:8px solid #f1c40f;}
.app-header, .tab-header {color:#e0e0e0;}
.tab-header {margin:1.5rem 2rem 0.5rem;font-size:1.3rem;font-weight:600;}
.stButton>button {
  background:#2b2f36;color:#e0e0e0;border:none;
  box-shadow:inset 2px 2px 6px rgba(0,0,0,0.6),-2px -2px 6px rgba(255,255,255,0.1);
  border-radius:0.75rem;padding:.6rem 1.2rem;
  transition:transform .1s,box-shadow .1s;
}
.stButton>button:hover {
  transform:translateY(-2px);
  box-shadow:inset 4px 4px 12px rgba(0,0,0,0.7),-4px -4px 12px rgba(255,255,255,0.15);
}
.stButton>button:active {
  transform:scale(.98);
  box-shadow:inset 1px 1px 4px rgba(0,0,0,0.6),-1px -1px 4px rgba(255,255,255,0.1);
}
.footer {
  position:fixed;bottom:0;width:100%;text-align:center;
  padding:.5rem;font-size:.8rem;color:rgba(255,255,255,0.5);
}
@media(max-width:768px){
  .card {margin:1rem;}
  .tab-header {margin:1rem;font-size:1.1rem;}
}
</style>
"""

# --- PAGE CONFIG & THEME ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide")
theme = st.sidebar.radio("🎨 Theme", ["Light Mode", "Dark Mode"])
st.markdown(LIGHT_CSS if theme == "Light Mode" else DARK_CSS, unsafe_allow_html=True)

# --- HEADER ---
st.markdown(
    '<div class="app-header"><i class="fas fa-chart-line"></i> <strong>Dr Didy Forecast</strong></div>',
    unsafe_allow_html=True
)

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", datetime.now().date() + timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_"," "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- TABS ---
tabs = st.tabs([
    '<i class="fas fa-chart-line"></i> SPX',
    '<i class="fas fa-car-side"></i> TSLA',
    '<i class="fas fa-microchip"></i> NVDA',
    '<i class="fas fa-apple-alt"></i> AAPL',
    '<i class="fas fa-box"></i> AMZN',
    '<i class="fas fa-search"></i> GOOGL',
])

# --- RENDER TABS ---
for idx, label in enumerate(["SPX","TSLA","NVDA","AAPL","AMZN","GOOGL"]):
    with tabs[idx]:
        st.markdown(f'<div class="tab-header">{label} Forecast</div>', unsafe_allow_html=True)
        cols = st.columns(3 if label=="SPX" else 2)
        if label == "SPX":
            hp = cols[0].number_input("High Price", 6185.8, format="%.2f", key="spx_hp")
            ht = cols[0].time_input("High Time", datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
            cp = cols[1].number_input("Close Price",6170.2,format="%.2f",key="spx_cp")
            ct = cols[1].time_input("Close Time",datetime(2025,1,1,15,0).time(),step=1800,key="spx_ct")
            lp = cols[2].number_input("Low Price",6130.4,format="%.2f",key="spx_lp")
            lt = cols[2].time_input("Low Time",datetime(2025,1,1,13,30).time(),step=1800,key="spx_lt")
            if st.button("Generate SPX"):
                anchors = {
                    "SPX_HIGH": datetime.combine(forecast_date - timedelta(days=1), ht),
                    "SPX_CLOSE": datetime.combine(forecast_date - timedelta(days=1), ct),
                    "SPX_LOW": datetime.combine(forecast_date - timedelta(days=1), lt),
                }
                st.success("Computed!")
                mcols = st.columns(3)
                for col, key in zip(mcols, anchors):
                    val = {"SPX_HIGH":hp, "SPX_CLOSE":cp, "SPX_LOW":lp}[key]
                    icon = {"SPX_HIGH":"🔼","SPX_CLOSE":"⏹️","SPX_LOW":"🔽"}[key]
                    col.metric(f"{icon} {key.replace('SPX_','').title()} Anchor",
                               f"{val:.2f}",
                               delta=f"{SLOPES[key]:.4f}/blk")
                for key in anchors:
                    icon = {"SPX_HIGH":"🔼","SPX_CLOSE":"⏹️","SPX_LOW":"🔽"}[key]
                    title = key.replace("SPX_","").title() + " Anchor"
                    with st.expander(f"{icon} {title} Table"):
                        df = generate_spx(
                            {"SPX_HIGH":hp,"SPX_CLOSE":cp,"SPX_LOW":lp}[key],
                            SLOPES[key],
                            anchors[key],
                            forecast_date
                        )
                        st.dataframe(df.round(2), use_container_width=True)
        else:
            lp = cols[0].number_input("Prev-Day Low",0.0,format="%.2f",key=f"{label}_lp")
            lt = cols[0].time_input("Prev-Day Low Time",datetime(2025,1,1,8,30).time(),step=1800,key=f"{label}_lt")
            hp = cols[1].number_input("Prev-Day High",0.0,format="%.2f",key=f"{label}_hp")
            ht = cols[1].time_input("Prev-Day High Time",datetime(2025,1,1,8,30).time(),step=1800,key=f"{label}_ht")
            if st.button(f"Generate {label}"):
                anchor_low  = datetime.combine(forecast_date - timedelta(days=1), lt)
                anchor_high = datetime.combine(forecast_date - timedelta(days=1), ht)
                st.success("Computed!")
                scols = st.columns(2)
                scols[0].metric("🔽 Low Anchor", f"{lp:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
                scols[1].metric("🔼 High Anchor", f"{hp:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
                with st.expander("🔻 Low Anchor Table"):
                    df_low = generate_stock(lp, SLOPES[label], anchor_low, forecast_date, invert=True)
                    st.dataframe(df_low.round(2), use_container_width=True)
                with st.expander("🔺 High Anchor Table"):
                    df_high = generate_stock(hp, SLOPES[label], anchor_high, forecast_date, invert=False)
                    st.dataframe(df_high.round(2), use_container_width=True)

# --- FOOTER ---
st.markdown(
    f'<div class="footer">v1.4.0 • Built by Dr Didy • {datetime.now():%I:%M %p}</div>',
    unsafe_allow_html=True
)
