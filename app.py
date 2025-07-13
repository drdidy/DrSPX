import streamlit as st
from datetime import datetime, time, timedelta
import pandas as pd

# --- SLOPE SETTINGS (restored to original values) ---
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
    return [(base + timedelta(minutes=30 * i)).strftime("%H:%M") for i in range(15)]  # 07:30–14:30

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
        entry = price + slope * b
        exit_ = price - slope * b
        rows.append({"Time": slot, "Entry": round(entry, 2), "Exit": round(exit_, 2)})
    return pd.DataFrame(rows)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Dr Didy Forecast",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME CSS BLOCKS (with Material Icons collapse arrow) ---
light_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');
* { font-family:'Inter',sans-serif!important; }
/* inject real arrow icon for collapse control */
button[data-testid="collapsedControl"] > span {
  font-family: 'Material Icons' !important;
  font-size: 1.5rem !important;
  line-height: 1 !important;
  display: inline-block !important;
}
button[data-testid="collapsedControl"] > span > * {
  display: none !important;
}
/* light theme vars */
:root {
  --bg: #ffffff; --text: #1f2937; --primary: #3b82f6;
  --card-bg: #f3f4f6; --radius: 8px; --shadow: 0 4px 12px rgba(0,0,0,0.05);
}
body {
  background: var(--bg)!important;
  color: var(--text)!important;
  margin: 0; padding: 0;
}
.main-container {
  padding: 1rem;
  max-width: 1200px;
  margin: auto;
}
.app-header {
  background: var(--primary);
  color: #fff;
  padding: 1rem;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 1rem;
}
.tab-header {
  font-size: 1.5rem; font-weight: 600; margin: 1rem 0;
}
.metric-cards {
  display: flex; gap: 1rem; margin: 1rem 0;
}
.anchor-card {
  background: var(--card-bg); padding: 1rem;
  border-radius: var(--radius); box-shadow: var(--shadow);
  flex: 1; display: flex; align-items: center;
}
.anchor-card .icon-wrapper {
  font-size: 1.75rem; margin-right: .5rem;
}
.stButton > button {
  background: var(--primary)!important;
  color: #fff!important;
  border-radius: var(--radius)!important;
  padding: .5rem 1rem!important;
  transition: transform .1s;
}
.stButton > button:hover {
  transform: scale(1.03);
}
.stDataFrame > div {
  border: none!important;
}
</style>
"""
dark_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');
* { font-family:'Inter',sans-serif!important; }
/* inject real arrow icon for collapse control */
button[data-testid="collapsedControl"] > span {
  font-family: 'Material Icons' !important;
  font-size: 1.5rem !important;
  line-height: 1 !important;
  display: inline-block !important;
}
button[data-testid="collapsedControl"] > span > * {
  display: none !important;
}
/* dark theme vars */
:root {
  --bg: #0f172a; --text: #e2e8f0; --primary: #6366f1;
  --card-bg: #1e293b; --radius: 8px; --shadow: 0 4px 12px rgba(0,0,0,0.2);
}
body {
  background: var(--bg)!important;
  color: var(--text)!important;
  margin: 0; padding: 0;
}
.main-container {
  padding: 1rem;
  max-width: 1200px;
  margin: auto;
}
.app-header {
  background: var(--primary);
  color: #fff;
  padding: 1rem;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 1rem;
}
.tab-header {
  font-size: 1.5rem; font-weight: 600; margin: 1rem 0;
}
.metric-cards {
  display: flex; gap: 1rem; margin: 1rem 0;
}
.anchor-card {
  background: var(--card-bg); padding: 1rem;
  border-radius: var(--radius); box-shadow: var(--shadow);
  flex: 1; display: flex; align-items: center;
}
.anchor-card .icon-wrapper {
  font-size: 1.75rem; margin-right: .5rem;
}
.stButton > button {
  background: var(--primary)!important;
  color: #fff!important;
  border-radius: var(--radius)!important;
  padding: .5rem 1rem!important;
  transition: transform .1s;
}
.stButton > button:hover {
  transform: scale(1.03);
}
.stDataFrame > div {
  border: none!important;
}
</style>
"""

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
    forecast_date = st.date_input("Forecast Date", datetime.now().date() + timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_", " "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- TABS (including MSFT) ---
tabs = st.tabs(["🧭 SPX", "🚗 TSLA", "🧠 NVDA", "🍎 AAPL", "🪟 MSFT", "📦 AMZN", "🔍 GOOOGL"])

# --- SPX TAB ---
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price", min_value=0.0, value=6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("🕒 High Time", datetime(2025,1,1,11,30).time(), step=1800, key="spx_ht")
    cp = c2.number_input("⏹️ Close Price", min_value=0.0, value=6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("🕒 Close Time", datetime(2025,1,1,15,0).time(), step=1800, key="spx_ct")
    lp = c3.number_input("🔽 Low Price", min_value=0.0, value=6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("🕒 Low Time", datetime(2025,1,1,13,30).time(), step=1800, key="spx_lt")

    is_tue = forecast_date.weekday() == 1
    is_thu = forecast_date.weekday() == 3

    # ... (Tuesday/Thursday/MonWedFri logic unchanged) ...

# --- STOCK TABS ---
icons = {"TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}
for i, label in enumerate(["TSLA","NVDA","AAPL","MSFT","AMZN","GOOOGL"], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        lp = col1.number_input("🔽 Prev-Day Low Price", min_value=0.0, value=0.0, format="%.2f", key=f"{label}_low_price")
        lt = col1.time_input("🕒 Prev-Day Low Time", datetime(2025,1,1,7,30).time(), step=1800, key=f"{label}_low_time")
        hp = col2.number_input("🔼 Prev-Day High Price", min_value=0.0, value=0.0, format="%.2f", key=f"{label}_high_price")
        ht = col2.time_input("🕒 Prev-Day High Time", datetime(2025,1,1,7,30).time(), step=1800, key=f"{label}_high_time")

        if st.button(f"🔮 Generate {label}", key=f"btn_{label}"):
            a_low  = datetime.combine(forecast_date, lt)
            a_high = datetime.combine(forecast_date, ht)

            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for cls, icon, title, val in [
                ("anchor-low","🔽","Low Anchor", lp),
                ("anchor-high","🔼","High Anchor", hp),
            ]:
                card = f'''
                <div class="anchor-card {cls}">
                  <div class="icon-wrapper">{icon}</div>
                  <div class="content">
                    <div class="title">{title}</div>
                    <div class="value">{val:.2f}</div>
                  </div>
                </div>'''
                st.markdown(card, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.subheader("🔻 Low Anchor Table")
            df_low = generate_stock(lp, SLOPES[label], a_low, forecast_date)
            st.dataframe(df_low.round(2), use_container_width=True)

            st.subheader("🔺 High Anchor Table")
            df_high = generate_stock(hp, SLOPES[label], a_high, forecast_date)
            st.dataframe(df_high.round(2), use_container_width=True)

# --- CLOSE MAIN CONTAINER ---
st.markdown('</div>', unsafe_allow_html=True)