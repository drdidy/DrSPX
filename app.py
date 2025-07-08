import streamlit as st
from datetime import datetime, time, timedelta
import pandas as pd
import altair as alt
import plotly.express as px

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
    out = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_spx_blocks(anchor, tgt)
        out.append({"Time": slot, "Entry": price + slope * b, "Exit": price - slope * b})
    return pd.DataFrame(out)

def generate_stock(price, slope, anchor, fd, invert=False):
    out = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_stock_blocks(anchor, tgt)
        entry = price - slope * b if invert else price + slope * b
        exit_ = price + slope * b if invert else price - slope * b
        out.append({"Time": slot, "Entry": entry, "Exit": exit_})
    return pd.DataFrame(out)

# --- CSS THEMES ---
neumo_css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
body {background:#e0e5ec; font-family:'Inter',sans-serif; margin:0;}
.sidebar .sidebar-content {
  background:#e0e5ec; color:#333;
  box-shadow:4px 0 12px rgba(0,0,0,0.06);
  padding:1rem; border-radius:0 1rem 1rem 0;
}
.app-header {
  margin:1rem 2rem; padding:1.5rem;
  background:#e0e5ec; border-radius:1rem;
  box-shadow:-8px -8px 16px #fff,8px 8px 16px rgba(0,0,0,0.1);
  text-align:center; color:#333;
}
.app-header h1 {margin:0; font-size:2.5rem; font-weight:600;}
.tab-header {margin:1.5rem 2rem 0.5rem; font-size:1.25rem; color:#333;}
.card {
  background:#e0e5ec; margin:1rem 2rem; padding:1rem; border-radius:1rem;
  box-shadow:-6px -6px 12px #fff,6px 6px 12px rgba(0,0,0,0.08);
  transition:transform 0.2s,box-shadow 0.2s;
}
.card:hover {
  transform:translateY(-4px);
  box-shadow:-8px -8px 16px #fff,8px 8px 16px rgba(0,0,0,0.15);
}
.card-high {border-left:8px solid #ff6b6b;}
.card-close{border-left:8px solid #4ecdc4;}
.card-low  {border-left:8px solid #f7b731;}
.metric-container {margin:1rem 2rem;}
.stButton>button {
  background:#e0e5ec; color:#333;
  box-shadow:-4px -4px 8px #fff,4px 4px 8px rgba(0,0,0,0.06);
  border-radius:0.75rem; padding:0.5rem 1rem;
}
.element-container .stDataFrame>div {border-radius:1rem!important; overflow:hidden;}
@media(max-width:768px){
  .app-header{margin:1rem; padding:1rem;}
  .tab-header{margin:1rem; font-size:1.1rem;}
  .card{margin:1rem;}
  .metric-container{margin:1rem;}
}
</style>"""
dark_css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
body {background:#1f1f1f; color:#e0e0e0; font-family:'Inter',sans-serif;}
.sidebar .sidebar-content {
  background:#292b2f; color:#e0e0e0; padding:1rem;
  box-shadow:4px 0 12px rgba(0,0,0,0.6); border-radius:0 1rem 1rem 0;
}
.app-header {
  margin:1rem 2rem; padding:1.5rem; border-radius:1rem;
  background:linear-gradient(90deg,#0f0c29,#24243e);
  box-shadow:0 8px 20px rgba(0,0,0,0.5); text-align:center; color:#f0f0f0;
}
.app-header h1{margin:0; font-size:2.5rem; font-weight:600;}
.tab-header{margin:1.5rem 2rem 0.5rem; font-size:1.25rem; color:#e0e0e0;}
.card {
  background:#292b2f; margin:1rem 2rem; padding:1rem; border-radius:1rem;
  box-shadow:inset 4px 4px 8px rgba(0,0,0,0.6),-4px -4px 8px rgba(255,255,255,0.1);
}
.card:hover {
  transform:translateY(-4px);
  box-shadow:inset 6px 6px 12px rgba(0,0,0,0.7),-6px -6px 12px rgba(255,255,255,0.15);
}
.card-high{border-left:8px solid #e74c3c;}
.card-close{border-left:8px solid #1abc9c;}
.card-low{border-left:8px solid #f1c40f;}
.metric-container{margin:1rem 2rem;}
.stButton>button {
  background:#292b2f; color:#e0e0e0;
  box-shadow:inset 2px 2px 4px rgba(0,0,0,0.6),-2px -2px 4px rgba(255,255,255,0.1);
  border-radius:0.75rem; padding:0.5rem 1rem;
}
.element-container .stDataFrame>div{border-radius:1rem!important; overflow:hidden;}
@media(max-width:768px){
  .app-header{margin:1rem; padding:1rem;}
  .tab-header{margin:1rem; font-size:1.1rem;}
  .card{margin:1rem;}
  .metric-container{margin:1rem;}
}
</style>"""
light_css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
body{background:#fafafa;color:#333;font-family:'Inter',sans-serif;}
.sidebar .sidebar-content {
  background:#fff;color:#333; padding:1rem;
  box-shadow:4px 0 12px rgba(0,0,0,0.1); border-radius:0 1rem 1rem 0;
}
.app-header {
  margin:1rem 2rem; padding:1.5rem; border-radius:1rem;
  background:#fff; box-shadow:0 8px 20px rgba(0,0,0,0.1);
  text-align:center; color:#333;
}
.app-header h1{margin:0; font-size:2.5rem; font-weight:600;}
.tab-header{margin:1.5rem 2rem 0.5rem; font-size:1.25rem; color:#333;}
.card {
  background:#fff; margin:1rem 2rem; padding:1rem; border-radius:1rem;
  box-shadow:0 4px 12px rgba(0,0,0,0.05);
}
.card:hover {
  transform:translateY(-4px);
  box-shadow:0 8px 24px rgba(0,0,0,0.1);
}
.card-high{border-left:8px solid #e74c3c;}
.card-close{border-left:8px solid #1abc9c;}
.card-low{border-left:8px solid #f1c40f;}
.metric-container{margin:1rem 2rem;}
.stButton>button {
  background:#fff;color:#333;
  box-shadow:2px 2px 6px rgba(0,0,0,0.1);
  border-radius:0.75rem;padding:0.5rem 1rem;
}
.element-container .stDataFrame>div{border-radius:1rem!important; overflow:hidden;}
@media(max-width:768px){
  .app-header{margin:1rem; padding:1rem;}
  .tab-header{margin:1rem; font-size:1.1rem;}
  .card{margin:1rem;}
  .metric-container{margin:1rem;}
}
</style>"""

# --- PAGE & THEME SELECTOR ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
theme = st.sidebar.radio("🎨 Theme", ["Neumorphic","Dark Mode","Light Mode"])
if theme == "Dark Mode":
    st.markdown(dark_css, unsafe_allow_html=True)
elif theme == "Light Mode":
    st.markdown(light_css, unsafe_allow_html=True)
else:
    st.markdown(neumo_css, unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<div class="app-header"><h1>📊 Dr Didy Forecast</h1></div>', unsafe_allow_html=True)

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", datetime.now().date() + timedelta(days=1))
    st.divider()
    st.subheader("Pick Stocks")
    all_stocks = ["TSLA","NVDA","AAPL","AMZN","GOOGL"]
    picks = st.multiselect("Generate tabs for:", all_stocks, default=all_stocks)
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_"," "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- BUILD TABS ---
tab_labels = ["SPX"] + picks
icons = {"SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","AMZN":"📦","GOOGL":"🔍"}
tabs = st.tabs([f"{icons[t]} {t}" for t in tab_labels])

# --- FOOTER ---
st.markdown(f"<div style='position:fixed;bottom:0;width:100%;text-align:center;"
            f"padding:0.5rem;color:gray;font-size:0.8rem;'>v1.3.0 • {datetime.now():%I:%M %p}</div>",
            unsafe_allow_html=True)

# --- TAB CONTENT ---
for idx, label in enumerate(tab_labels):
    with tabs[idx]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>', unsafe_allow_html=True)
        col = st.columns(2)[0]
        if label == "SPX":
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
                dfh = generate_spx(hp, SLOPES["SPX_HIGH"], ah, forecast_date)
                dfc = generate_spx(cp, SLOPES["SPX_CLOSE"], ac, forecast_date)
                dfl = generate_spx(lp, SLOPES["SPX_LOW"],   al, forecast_date)
                m1,m2,m3 = st.columns(3)
                for col_, df_, name, slope_key in zip(
                    (m1,m2,m3), (dfh,dfc,dfl),
                    ("High Anchor","Close Anchor","Low Anchor"),
                    ("SPX_HIGH","SPX_CLOSE","SPX_LOW")
                ):
                    col_.metric(name, f"{df_['Entry'].iloc[0]:.2f}", delta=f"{SLOPES[slope_key]:.4f}/blk")
                    spark = alt.Chart(df_).mark_line(size=2).encode(x='Time', y='Entry').properties(width=100, height=40)
                    col_.altair_chart(spark, use_container_width=True)
                for cls, ico, df_ in zip(
                    ("card-high","card-close","card-low"),
                    ("🔼","⏹️","🔽"),
                    (dfh,dfc,dfl)
                ):
                    with st.expander(f"{ico} {ico} Table"):
                        st.markdown(f'<div class="card {cls}">', unsafe_allow_html=True)
                        st.dataframe(df_.round(2), use_container_width=True)
                        fig = px.line(df_, x='Time', y=['Entry','Exit'], markers=True)
                        fig.update_layout(margin=dict(t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown("</div>", unsafe_allow_html=True)
        else:
            low_p  = col.number_input("🔽 Prev-Day Low Price", 0.0, format="%.2f", key=f"{label}_lp")
            low_t  = col.time_input("🕒 Prev-Day Low Time", datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_lt")
            high_p = col.number_input("🔼 Prev-Day High Price",0.0, format="%.2f", key=f"{label}_hp")
            high_t = col.time_input("🕒 Prev-Day High Time",datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_ht")
            if st.button(f"🔮 Generate {label}", key=f"btn_{label}"):
                a_low  = datetime.combine(forecast_date - timedelta(days=1), low_t)
                a_high = datetime.combine(forecast_date - timedelta(days=1), high_t)
                dfL = generate_stock(low_p, SLOPES[label], a_low, forecast_date, invert=True)
                dfH = generate_stock(high_p, SLOPES[label], a_high, forecast_date, invert=False)
                s1,s2 = st.columns(2)
                for col_, df_, name in zip((s1,s2), (dfL,dfH), ("Low Anchor","High Anchor")):
                    col_.metric(name, f"{df_['Entry'].iloc[0]:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
                    spark = alt.Chart(df_).mark_line(size=2).encode(x='Time', y='Entry').properties(width=100, height=40)
                    col_.altair_chart(spark, use_container_width=True)
                with st.expander("🔻 Low-Anchor Table"):
                    st.markdown(f'<div class="card card-low">', unsafe_allow_html=True)
                    st.dataframe(dfL.round(2), use_container_width=True)
                    fig = px.line(dfL, x='Time', y=['Entry','Exit'], markers=True)
                    fig.update_layout(margin=dict(t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                with st.expander("🔺 High-Anchor Table"):
                    st.markdown(f'<div class="card card-high">', unsafe_allow_html=True)
                    st.dataframe(dfH.round(2), use_container_width=True)
                    fig = px.line(dfH, x='Time', y=['Entry','Exit'], markers=True)
                    fig.update_layout(margin=dict(t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)
