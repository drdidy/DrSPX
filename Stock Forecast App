import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta

# --- SLOPE SETTINGS (restored original slopes) ---
SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.1500,
    "NVDA": -0.0485,
    "AAPL": -0.0750,
    "MSFT": -0.1964,
    "AMZN": -0.0782,
    "GOOGL": -0.0485,
}

# --- HELPERS ---
def generate_time_blocks():
    base = datetime.strptime("07:30", "%H:%M")
    return [(base + timedelta(minutes=30 * i)).strftime("%H:%M") for i in range(15)]

def calculate_spx_blocks(a, t):
    dt, blocks = a, 0
    while dt < t:
        if dt.hour != 16:
            blocks += 1
        dt += timedelta(minutes=30)
    return blocks

def calculate_stock_blocks(a, t):
    if t <= a:
        return 0
    return int((t - a).total_seconds() // 1800)

def generate_spx(price, slope, anchor, fd):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_spx_blocks(anchor, tgt)
        rows.append({
            "Time": slot,
            "Entry": round(price + slope * b, 2),
            "Exit":  round(price - slope * b, 2)
        })
    return pd.DataFrame(rows)

def generate_stock(price, slope, anchor, fd):
    rows = []
    for slot in generate_time_blocks():
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = calculate_stock_blocks(anchor, tgt)
        rows.append({
            "Time": slot,
            "Entry": round(price + slope * b, 2),
            "Exit": round(price - slope * b, 2)
        })
    return pd.DataFrame(rows)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Dr Didy Forecast",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME CSS BLOCKS (no collapse hacks) ---
light_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
* { font-family:'Inter',sans-serif!important; }

/* light theme variables */
:root {
  --bg: #ffffff; --text: #1f2937; --primary: #3b82f6;
  --card-bg: #f3f4f6; --radius: 8px; --shadow: 0 4px 12px rgba(0,0,0,0.05);
}
body {
  background: var(--bg)!important;
  color: var(--text)!important;
  margin: 0; padding: 0;
}
.main-container { padding: 1rem; max-width: 1200px; margin: auto; }
.app-header {
  background: var(--primary); color: #fff; padding: 1rem;
  border-radius: var(--radius); box-shadow: var(--shadow);
  margin-bottom: 1rem;
}
.tab-header { font-size: 1.5rem; font-weight: 600; margin: 1rem 0; }
.metric-cards { display: flex; gap: 1rem; margin: 1rem 0; }
.anchor-card {
  background: var(--card-bg); padding: 1rem; border-radius: var(--radius);
  box-shadow: var(--shadow); flex: 1; display: flex; align-items: center;
}
.anchor-card .icon-wrapper { font-size: 1.75rem; margin-right: .5rem; }
.stButton > button {
  background: var(--primary)!important; color: #fff!important;
  border-radius: var(--radius)!important; padding: .5rem 1rem!important;
  transition: transform .1s;
}
.stButton > button:hover { transform: scale(1.03); }
.stDataFrame > div { border: none!important; }
</style>
"""

dark_css = light_css.replace(
    "--bg: #ffffff", "--bg: #0f172a"
).replace(
    "--text: #1f2937", "--text: #e2e8f0"
).replace(
    "--card-bg: #f3f4f6", "--card-bg: #1e293b"
).replace(
    "rgba(0,0,0,0.05)", "rgba(0,0,0,0.2)"
)

# --- THEME SWITCH ---
with st.sidebar:
    theme = st.radio("🎨 Theme", ["Light", "Dark"])
if theme == "Dark":
    st.markdown(dark_css, unsafe_allow_html=True)
else:
    st.markdown(light_css, unsafe_allow_html=True)

# --- MAIN CONTAINER WRAP ---
st.markdown('<div class="main-container">', unsafe_allow_html=True)

# --- HEADER BANNER ---
st.markdown(
    '<div class="app-header"><h1>📊 Dr Didy Forecast</h1></div>',
    unsafe_allow_html=True
)

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", date.today() + timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_", " "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- TABS (including MSFT) ---
tabs = st.tabs(["🧭 SPX","🚗 TSLA","🧠 NVDA","🍎 AAPL","🪟 MSFT","📦 AMZN","🔍 GOOOGL"])

# --- SPX TAB ---
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price", value=6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("🕒 High Time", value=time(11,30), step=1800, key="spx_ht")
    cp = c2.number_input("⏹️ Close Price", value=6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("🕒 Close Time", value=time(15,0), step=1800, key="spx_ct")
    lp = c3.number_input("🔽 Low Price", value=6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("🕒 Low Time", value=time(13,30), step=1800, key="spx_lt")

    is_tue = forecast_date.weekday() == 1
    is_thu = forecast_date.weekday() == 3

    if is_tue:
        st.markdown("**Tuesday: Contract-Low Entry Projection**")
        t1, t2 = st.columns(2)
        tue_time  = t1.time_input("Contract Low Time", value=time(7,30), key="tue_time")
        tue_price = t2.number_input("Contract Low Price", value=5.0, step=0.1, key="tue_price")

    if is_thu:
        st.markdown("**Thursday SPX methods**")
        o1, o2 = st.columns(2)
        low1_time  = o1.time_input("OTM Low 1 Time", value=time(7,30), key="low1_time")
        low1_price = o1.number_input("OTM Low 1 Price", value=10.0, step=0.1, key="low1_price")
        low2_time  = o2.time_input("OTM Low 2 Time", value=time(8,0), key="low2_time")
        low2_price = o2.number_input("OTM Low 2 Price", value=12.0, step=0.1, key="low2_price")
        st.markdown("<br><strong>8 EMA Bounce-Low Anchor</strong>", unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        bounce_time  = b1.time_input("Bounce Low Time", value=time(7,30), key="bounce_time")
        bounce_price = b2.number_input("Bounce Low Price", value=6100.0, step=0.1, key="bounce_price")

    if st.button("🔮 Generate SPX"):
        ah = datetime.combine(forecast_date - timedelta(days=1), ht)
        ac = datetime.combine(forecast_date - timedelta(days=1), ct)
        al = datetime.combine(forecast_date - timedelta(days=1), lt)

        if is_tue:
            rows = []
            anchor_dt = datetime.combine(forecast_date, tue_time)
            for slot in generate_time_blocks():
                h, m = map(int, slot.split(":"))
                tgt = datetime.combine(forecast_date, time(h, m))
                b = calculate_spx_blocks(anchor_dt, tgt)
                rows.append({"Time": slot, "Projected": round(tue_price + (-0.5250)*b, 2)})
            st.subheader("🔹 Tuesday Entry Table")
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

        elif is_thu:
            dt1 = datetime.combine(forecast_date - timedelta(days=1), low1_time)
            dt2 = datetime.combine(forecast_date - timedelta(days=1), low2_time)
            n12 = calculate_spx_blocks(dt1, dt2) or 1
            alt_slope = (low2_price - low1_price)/n12
            orows = []
            for slot in generate_time_blocks():
                h, m = map(int, slot.split(":"))
                tgt = datetime.combine(forecast_date, time(h, m))
                b = calculate_spx_blocks(dt1, tgt)
                orows.append({"Time": slot, "Projected": round(low1_price + alt_slope*b, 2)})
            st.subheader("🌀 Thu: OTM-Line Forecast")
            st.dataframe(pd.DataFrame(orows), use_container_width=True)

            brows = []
            bounce_dt = datetime.combine(forecast_date - timedelta(days=1), bounce_time)
            for slot in generate_time_blocks():
                h, m = map(int, slot.split(":"))
                tgt = datetime.combine(forecast_date, time(h, m))
                b = calculate_spx_blocks(bounce_dt, tgt)
                brows.append({"Time": slot, "Projected": round(bounce_price + SLOPES["SPX_LOW"]*b, 2)})
            st.subheader("📈 Thu: Bounce-Low Slope Forecast")
            st.dataframe(pd.DataFrame(brows), use_container_width=True)

        else:
            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for cls, icon, title, val in [
                ("anchor-high","🔼","High Anchor", hp),
                ("anchor-close","⏹️","Close Anchor", cp),
                ("anchor-low","🔽","Low Anchor", lp),
            ]:
                st.markdown(f'''
                    <div class="anchor-card {cls}">
                      <div class="icon-wrapper">{icon}</div>
                      <div class="content">
                        <div class="title">{title}</div>
                        <div class="value">{val:.2f}</div>
                      </div>
                    </div>''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            for icon, title, price, slope, anchor in [
                ("🔼","High Anchor", hp, SLOPES["SPX_HIGH"], ah),
                ("🔽","Low Anchor", lp, SLOPES["SPX_LOW"],  al),
                ("⏹️","Close Anchor", cp, SLOPES["SPX_CLOSE"], ac),
            ]:
                st.subheader(f"{icon} {title} Table")
                df = generate_spx(price, slope, anchor, forecast_date)
                st.dataframe(df.round(2), use_container_width=True)

# --- STOCK TABS ---
icons = {"TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}
for i, label in enumerate(["TSLA","NVDA","AAPL","MSFT","AMZN","GOOGL"], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        lp = col1.number_input("🔽 Prev-Day Low Price", min_value=0.0, value=0.0, format="%.2f", key=f"{label}_low_price")
        lt = col1.time_input("🕒 Prev-Day Low Time", value=time(7,30), step=1800, key=f"{label}_low_time")
        hp = col2.number_input("🔼 Prev-Day High Price", min_value=0.0, value=0.0, format="%.2f", key=f"{label}_high_price")
        ht = col2.time_input("🕒 Prev-Day High Time", value=time(7,30), step=1800, key=f"{label}_high_time")

        if st.button(f"🔮 Generate {label}", key=f"btn_{label}"):
            a_low  = datetime.combine(forecast_date, lt)
            a_high = datetime.combine(forecast_date, ht)
            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for cls, icon, title, val in [
                ("anchor-low","🔽","Low Anchor", lp),
                ("anchor-high","🔼","High Anchor", hp),
            ]:
                st.markdown(f'''
                    <div class="anchor-card {cls}">
                      <div class="icon-wrapper">{icon}</div>
                      <div class="content">
                        <div class="title">{title}</div>
                        <div class="value">{val:.2f}</div>
                      </div>
                    </div>''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.subheader("🔻 Low Anchor Table")
            df_low = generate_stock(lp, SLOPES[label], a_low, forecast_date)
            st.dataframe(df_low.round(2), use_container_width=True)
            st.subheader("🔺 High Anchor Table")
            df_high = generate_stock(hp, SLOPES[label], a_high, forecast_date)
            st.dataframe(df_high.round(2), use_container_width=True)

# --- CLOSE MAIN CONTAINER ---
st.markdown('</div>', unsafe_allow_html=True)