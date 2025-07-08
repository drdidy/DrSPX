import streamlit as st
from datetime import datetime, time, timedelta
import pandas as pd
import altair as alt
from st_aggrid import AgGrid, GridOptionsBuilder

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
/* Animated gradient background */
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
/* Sticky header & sidebar */
.app-header {position:sticky;top:0;z-index:1000;}
.sidebar .sidebar-content {position:sticky;top:0;overflow:auto;height:100vh;}

/* Neumorphic cards */
.card {
  background:#e0e5ec;margin:1rem 2rem;padding:1rem;border-radius:1rem;
  box-shadow:-6px -6px 16px #ffffff,6px 6px 16px rgba(0,0,0,0.1);
  transition:transform .2s,box-shadow .2s;
}
.card:hover {
  transform:translateY(-4px);
  box-shadow:-8px -8px 24px #ffffff,8px 8px 24px rgba(0,0,0,0.15);
}
.card-high {border-left:8px solid #ff6b6b;}
.card-close{border-left:8px solid #4ecdc4;}
.card-low  {border-left:8px solid #f7b731;}

/* Tabs & header */
.app-header, .tab-header {color:#333;}
.tab-header {margin:1.5rem 2rem 0.5rem;font-size:1.3rem;font-weight:600;}

/* Buttons */
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

/* AG-Grid zebra stripes */
.ag-theme-streamlit .ag-row:nth-child(odd) {background:#f7f9fc;}
.ag-theme-streamlit .ag-row:nth-child(even){background:#e9edf3;}

/* Footer */
.footer {
  position:fixed;bottom:0;width:100%;text-align:center;
  padding:.5rem;font-size:.8rem;color:rgba(0,0,0,0.5);
}

/* Responsive */
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

.ag-theme-streamlit .ag-row:nth-child(odd) {background:#34383f;}
.ag-theme-streamlit .ag-row:nth-child(even){background:#2b2f36;}

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

# --- PAGE CONFIG & THEME SELECTOR ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide")
mode = st.sidebar.radio("🎨 Theme", ["Light Mode","Dark Mode"])
st.markdown(LIGHT_CSS if mode=="Light Mode" else DARK_CSS, unsafe_allow_html=True)

# --- HEADER ---
st.markdown(
    '<div class="app-header"><i class="fas fa-chart-line"></i> <strong>Dr Didy Forecast</strong></div>',
    unsafe_allow_html=True
)

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", datetime.now().date()+timedelta(days=1))
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

# --- RENDERING ---
icons = {"SPX_HIGH":"🔼","SPX_CLOSE":"⏹️","SPX_LOW":"🔽"}
stock_icons = {"TSLA":"🔗","NVDA":"🔗","AAPL":"🔗","AMZN":"🔗","GOOGL":"🔗"}

for idx,label in enumerate(["SPX","TSLA","NVDA","AAPL","AMZN","GOOGL"]):
    with tabs[idx]:
        st.markdown(f'<div class="tab-header">{label} Forecast</div>', unsafe_allow_html=True)
        cols = st.columns(2 if label!="SPX" else 3)
        if label=="SPX":
            hp = cols[0].number_input("High Price", 6185.8, format="%.2f", key="spx_hp")
            ht = cols[0].time_input("High Time", datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
            cp = cols[1].number_input("Close Price",6170.2,format="%.2f",key="spx_cp")
            ct = cols[1].time_input("Close Time",datetime(2025,1,1,15,0).time(),step=1800,key="spx_ct")
            lp = cols[2].number_input("Low Price",6130.4,format="%.2f",key="spx_lp")
            lt = cols[2].time_input("Low Time",datetime(2025,1,1,13,30).time(),step=1800,key="spx_lt")
            if st.button("Generate SPX"):
                anchor_times = {
                    "SPX_HIGH": datetime.combine(forecast_date - timedelta(days=1), ht),
                    "SPX_CLOSE":datetime.combine(forecast_date - timedelta(days=1),ct),
                    "SPX_LOW":  datetime.combine(forecast_date - timedelta(days=1),lt),
                }
                # metrics with spinner + success
                with st.spinner("Computing…"):
                    for key in ["SPX_HIGH","SPX_CLOSE","SPX_LOW"]:
                        pass
                st.success("Done!")
                # show metrics
                mcols = st.columns(3)
                for col,key in zip(mcols,["SPX_HIGH","SPX_CLOSE","SPX_LOW"]):
                    val = {"SPX_HIGH":hp,"SPX_CLOSE":cp,"SPX_LOW":lp}[key]
                    col.metric(f"{icons[key]} {key.replace('SPX_','').title()} Anchor",
                               f"{val:.2f}",
                               delta=f"{SLOPES[key]:.4f}/blk")
                # tables via AG-Grid
                for key in ["SPX_HIGH","SPX_CLOSE","SPX_LOW"]:
                    with st.expander(f"{icons[key]} {key.replace('SPX_','').title()} Anchor Table"):
                        df = generate_spx(
                            {"SPX_HIGH":hp,"SPX_CLOSE":cp,"SPX_LOW":lp}[key],
                            SLOPES[key],
                            anchor_times[key],
                            forecast_date
                        )
                        gb = GridOptionsBuilder.from_dataframe(df)
                        gb.configure_pagination(paginationAutoPageSize=True)
                        gb.configure_default_column(flex=1,sortable=True,filter=True)
                        AgGrid(df,gridOptions=gb.build(),theme="streamlit")
        else:
            lp = cols[0].number_input("Prev-Day Low",0.0,format="%.2f",key=f"{label}_lp")
            lt = cols[0].time_input("Prev-Day Low Time",datetime(2025,1,1,8,30).time(),step=1800,key=f"{label}_lt")
            hp = cols[1].number_input("Prev-Day High",0.0,format="%.2f",key=f"{label}_hp")
            ht = cols[1].time_input("Prev-Day High Time",datetime(2025,1,1,8,30).time(),step=1800,key=f"{label}_ht")
            if st.button(f"Generate {label}"):
                anchor_low  = datetime.combine(forecast_date - timedelta(days=1), lt)
                anchor_high = datetime.combine(forecast_date - timedelta(days=1), ht)
                st.success("Done!")
                scols = st.columns(2)
                scols[0].metric(f"🔽 Low Anchor", f"{lp:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
                scols[1].metric(f"🔼 High Anchor",f"{hp:.2f}",delta=f"{SLOPES[label]:.4f}/blk")
                # low table
                with st.expander("🔻 Low Anchor Table"):
                    df = generate_stock(lp,SLOPES[label],anchor_low,forecast_date,invert=True)
                    gb = GridOptionsBuilder.from_dataframe(df)
                    gb.configure_pagination(paginationAutoPageSize=True)
                    gb.configure_default_column(flex=1,sortable=True,filter=True)
                    AgGrid(df,gridOptions=gb.build(),theme="streamlit")
                # high table
                with st.expander("🔺 High Anchor Table"):
                    df = generate_stock(hp,SLOPES[label],anchor_high,forecast_date,invert=False)
                    gb = GridOptionsBuilder.from_dataframe(df)
                    gb.configure_pagination(paginationAutoPageSize=True)
                    gb.configure_default_column(flex=1,sortable=True,filter=True)
                    AgGrid(df,gridOptions=gb.build(),theme="streamlit")

# --- FOOTER ---
st.markdown(
    f'<div class="footer">v1.4.0 • Built by Dr Didy • {datetime.now():%I:%M %p}</div>',
    unsafe_allow_html=True
)
