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

# --- HELPERS (unchanged) ---
def generate_time_blocks():
    base = datetime.strptime("08:30", "%H:%M")
    return [(base + timedelta(minutes=30*i)).strftime("%H:%M") for i in range(13)]

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
    bn = 0 if t <= next_open else int((min(t,next_close)-next_open).total_seconds()//1800)
    return bp + bn

def generate_spx(price, slope, anchor, fd):
    rows=[]
    for slot in generate_time_blocks():
        h,m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h,m))
        b = calculate_spx_blocks(anchor, tgt)
        rows.append({"Time":slot,
                     "Entry": round(price+slope*b,2),
                     "Exit":  round(price-slope*b,2)})
    return pd.DataFrame(rows)

def generate_stock(price, slope, anchor, fd, invert=False):
    rows=[]
    for slot in generate_time_blocks():
        h,m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h,m))
        b = calculate_stock_blocks(anchor, tgt)
        if invert:
            e = price - slope*b
            x = price + slope*b
        else:
            e = price + slope*b
            x = price - slope*b
        rows.append({"Time":slot, "Entry":round(e,2), "Exit":round(x,2)})
    return pd.DataFrame(rows)

# --- CSS & THEMES (unchanged) ---
LIGHT_CSS = """<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<style>/* … your light-mode CSS here … */</style>"""
DARK_CSS  = """<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<style>/* … your dark-mode CSS here … */</style>"""

st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide")
mode = st.sidebar.radio("🎨 Theme", ["Light Mode", "Dark Mode"])
st.markdown(LIGHT_CSS if mode=="Light Mode" else DARK_CSS, unsafe_allow_html=True)

# --- HEADER: replace HTML icon with emoji ---
st.markdown(
    '<div class="app-header">📊 Dr Didy Forecast</div>',
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

# --- TABS: use emojis instead of HTML ---
tabs = st.tabs([
    "📈 SPX",
    "🚗 TSLA",
    "🧠 NVDA",
    "🍎 AAPL",
    "📦 AMZN",
    "🔍 GOOGL",
])

# --- TAB CONTENTS (unchanged) ---
for idx, label in enumerate(["SPX","TSLA","NVDA","AAPL","AMZN","GOOGL"]):
    with tabs[idx]:
        st.markdown(f'<div class="tab-header">{label} Forecast</div>', unsafe_allow_html=True)
        cols = st.columns(3 if label=="SPX" else 2)
        if label=="SPX":
            hp = cols[0].number_input("High Price", 6185.8, format="%.2f", key="spx_hp")
            ht = cols[0].time_input("High Time", datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
            cp = cols[1].number_input("Close Price",6170.2,format="%.2f",key="spx_cp")
            ct = cols[1].time_input("Close Time",datetime(2025,1,1,15,0).time(),step=1800,key="spx_ct")
            lp = cols[2].number_input("Low Price",6130.4,format="%.2f",key="spx_lp")
            lt = cols[2].time_input("Low Time",datetime(2025,1,1,13,30).time(),step=1800,key="spx_lt")
            if st.button("Generate SPX"):
                anchors = {
                    "SPX_HIGH": datetime.combine(forecast_date - timedelta(days=1), ht),
                    "SPX_CLOSE":datetime.combine(forecast_date - timedelta(days=1),ct),
                    "SPX_LOW":  datetime.combine(forecast_date - timedelta(days=1),lt),
                }
                st.success("Done!")
                mcols = st.columns(3)
                for col, key in zip(mcols, anchors):
                    val  = {"SPX_HIGH":hp,"SPX_CLOSE":cp,"SPX_LOW":lp}[key]
                    icon = {"SPX_HIGH":"🔼","SPX_CLOSE":"⏹️","SPX_LOW":"🔽"}[key]
                    col.metric(f"{icon} {key.split('_')[1].title()} Anchor",
                               f"{val:.2f}", delta=f"{SLOPES[key]:.4f}/blk")
                for key in anchors:
                    icon  = {"SPX_HIGH":"🔼","SPX_CLOSE":"⏹️","SPX_LOW":"🔽"}[key]
                    title = key.split('_')[1].title() + " Anchor"
                    with st.expander(f"{icon} {title} Table"):
                        df = generate_spx(
                            {"SPX_HIGH":hp,"SPX_CLOSE":cp,"SPX_LOW":lp}[key],
                            SLOPES[key], anchors[key], forecast_date
                        )
                        st.dataframe(df.round(2), use_container_width=True)
        else:
            lp = cols[0].number_input("Prev-Day Low",0.0,format="%.2f", key=f"{label}_lp")
            lt = cols[0].time_input("Prev-Day Low Time", datetime(2025,1,1,8,30).time(),
                                     step=1800, key=f"{label}_lt")
            hp = cols[1].number_input("Prev-Day High",0.0,format="%.2f", key=f"{label}_hp")
            ht = cols[1].time_input("Prev-Day High Time", datetime(2025,1,1,8,30).time(),
                                     step=1800, key=f"{label}_ht")
            if st.button(f"Generate {label}"):
                a_low  = datetime.combine(forecast_date - timedelta(days=1), lt)
                a_high = datetime.combine(forecast_date - timedelta(days=1), ht)
                st.success("Done!")
                s1,s2 = st.columns(2)
                s1.metric("🔽 Low Anchor",  f"{lp:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
                s2.metric("🔼 High Anchor", f"{hp:.2f}", delta=f"{SLOPES[label]:.4f}/blk")
                with st.expander("🔻 Low Anchor Table"):
                    df_low = generate_stock(lp, SLOPES[label], a_low, forecast_date, invert=True)
                    st.dataframe(df_low.round(2), use_container_width=True)
                with st.expander("🔺 High Anchor Table"):
                    df_high = generate_stock(hp, SLOPES[label], a_high, forecast_date, invert=False)
                    st.dataframe(df_high.round(2), use_container_width=True)

# --- FOOTER ---
st.markdown(
    f'<div class="footer">v1.4.0 • Built by Dr Didy • {datetime.now():%I:%M %p}</div>',
    unsafe_allow_html=True
)
