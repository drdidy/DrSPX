import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta

# ── Configuration ─────────────────────────────────────────────────────────────
PAGE_TITLE = "Dr Didy Forecast"
PAGE_ICON = "📈"
LAYOUT = "wide"
SIDEBAR_STATE = "expanded"

# slopes must remain unchanged
SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.1500,
    "NVDA": -0.0485,
    "AAPL": -0.075,
    "MSFT": -0.1964,
    "AMZN": -0.0782,
    "GOOGL": -0.0485,
}

ICONS = {
    "SPX": "🧭",
    "TSLA": "🚗",
    "NVDA": "🧠",
    "AAPL": "🍎",
    "MSFT": "🪟",
    "AMZN": "📦",
    "GOOGL": "🔍",
}

# generate the fixed 07:30–14:30 slots once
def _gen_time_slots() -> list[str]:
    base = datetime.strptime("07:30", "%H:%M")
    return [(base + timedelta(minutes=30 * i)).strftime("%H:%M") for i in range(15)]
TIME_SLOTS = _gen_time_slots()

# ── THEME CSS ─────────────────────────────────────────────────────────────────
LIGHT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
:root {
  --bg: #ffffff; --text: #1f2937; --primary: #3b82f6;
  --card-bg: #f3f4f6; --radius: 8px; --shadow: 0 4px 12px rgba(0,0,0,0.05);
}
body { background-color: var(--bg)!important; color: var(--text)!important; font-family:'Inter',sans-serif!important; }
.main-container { padding:1rem; max-width:1200px; margin:auto; }
.app-header { background-color:var(--primary); color:#fff; padding:1rem; border-radius:var(--radius); box-shadow:var(--shadow); margin-bottom:1rem; }
.tab-header { font-size:1.5rem; font-weight:600; margin-bottom:0.5rem; }
.metric-cards { display:flex; gap:1rem; margin-bottom:1rem; }
.anchor-card { background-color:var(--card-bg); border-radius:var(--radius); box-shadow:var(--shadow); padding:1rem; flex:1; display:flex; align-items:center; }
.anchor-card .icon-wrapper { font-size:2rem; margin-right:0.5rem; }
.anchor-card .title { font-size:0.875rem; color:var(--text); }
.anchor-card .value { font-size:1.25rem; font-weight:600; }
.stButton>button { background-color:var(--primary)!important; color:#fff!important; border:none; border-radius:var(--radius)!important;
  padding:0.5rem 1rem; font-weight:600; transition:opacity 0.2s; }
.stButton>button:hover { opacity:0.9; }
.stDataFrame>div { border:none!important; }
</style>
"""
DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
:root {
  --bg: #0f172a; --text: #e2e8f0; --primary: #6366f1;
  --card-bg: #1e293b; --radius: 8px; --shadow: 0 4px 12px rgba(0,0,0,0.2);
}
body { background-color:var(--bg)!important; color:var(--text)!important; font-family:'Inter',sans-serif!important; }
.main-container { padding:1rem; max-width:1200px; margin:auto; }
.app-header { background-color:var(--primary); color:#fff; padding:1rem; border-radius:var(--radius); box-shadow:var(--shadow); margin-bottom:1rem; }
.tab-header { font-size:1.5rem; font-weight:600; margin-bottom:0.5rem; }
.metric-cards { display:flex; gap:1rem; margin-bottom:1rem; }
.anchor-card { background-color:var(--card-bg); border-radius:var(--radius); box-shadow:var(--shadow); padding:1rem; flex:1; display:flex; align-items:center; }
.anchor-card .icon-wrapper { font-size:2rem; margin-right:0.5rem; }
.anchor-card .title { font-size:0.875rem; color:var(--text); }
.anchor-card .value { font-size:1.25rem; font-weight:600; }
.stButton>button { background-color:var(--primary)!important; color:#fff!important; border:none; border-radius:var(--radius)!important;
  padding:0.5rem 1rem; font-weight:600; transition:opacity 0.2s; }
.stButton>button:hover { opacity:0.9; }
.stDataFrame>div { border:none!important; }
</style>
"""

# ── PAGE SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON,
                   layout=LAYOUT, initial_sidebar_state=SIDEBAR_STATE)

# theme selector
theme = st.sidebar.radio("🎨 Theme", ["Light", "Dark"])
st.markdown(DARK_CSS if theme == "Dark" else LIGHT_CSS, unsafe_allow_html=True)

# ── SIDEBAR CONTROLS ─────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Settings")
forecast_date = st.sidebar.date_input("Forecast Date", date.today() + timedelta(days=1))
st.sidebar.divider()
st.sidebar.subheader("Adjust Slopes")
for key in SLOPES:
    SLOPES[key] = st.sidebar.slider(key.replace("_", " "), -1.0, 1.0, SLOPES[key], step=0.0001)

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown('<div class="main-container">', unsafe_allow_html=True)
st.markdown(f'<div class="app-header"><h1>{PAGE_ICON} {PAGE_TITLE}</h1></div>', unsafe_allow_html=True)

# ── BLOCK CALCULATORS & GENERATORS ───────────────────────────────────────────
def calculate_spx_blocks(anchor: datetime, target: datetime) -> int:
    """Count 30-min blocks skipping 16:00–16:30 slot."""
    blocks = 0
    current = anchor
    while current < target:
        if current.hour != 16:
            blocks += 1
        current += timedelta(minutes=30)
    return blocks

def calculate_stock_blocks(anchor: datetime, target: datetime) -> int:
    """Simple continuous 30-min blocks."""
    if target <= anchor:
        return 0
    return int((target - anchor).total_seconds() // 1800)

def generate_spx_table(price: float, slope: float, anchor: datetime) -> pd.DataFrame:
    rows = []
    for slot in TIME_SLOTS:
        h, m = map(int, slot.split(":"))
        ts = datetime.combine(forecast_date, time(h, m))
        b = calculate_spx_blocks(anchor, ts)
        rows.append({
            "Time": slot,
            "Entry": round(price + slope * b, 2),
            "Exit":  round(price - slope * b, 2),
        })
    return pd.DataFrame(rows)

def generate_stock_table(price: float, slope: float, anchor: datetime) -> pd.DataFrame:
    rows = []
    for slot in TIME_SLOTS:
        h, m = map(int, slot.split(":"))
        ts = datetime.combine(forecast_date, time(h, m))
        b = calculate_stock_blocks(anchor, ts)
        rows.append({
            "Time": slot,
            "Entry": round(price + slope * b, 2),
            "Exit":  round(price - slope * b, 2),
        })
    return pd.DataFrame(rows)

# ── RENDER TABS ───────────────────────────────────────────────────────────────
tab_labels = list(ICONS.keys())
tabs = st.tabs([f"{ICONS[label]} {label}" for label in tab_labels])

# SPX tab
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

    if st.button("🔮 Generate SPX"):
        if not (is_tue or is_thu):
            # show metric cards
            anchors = [
                ("High Anchor", hp, SLOPES["SPX_HIGH"], ht),
                ("Close Anchor", cp, SLOPES["SPX_CLOSE"], ct),
                ("Low Anchor", lp, SLOPES["SPX_LOW"], lt),
            ]
            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for title, val, _, _ in anchors:
                st.markdown(f'''
                  <div class="anchor-card">
                    <div class="icon-wrapper">{"🔼" if "High" in title else "⏹️" if "Close" in title else "🔽"}</div>
                    <div>
                      <div class="title">{title}</div>
                      <div class="value">{val:.2f}</div>
                    </div>
                  </div>
                ''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # detailed tables
            for title, price, slope, tm in anchors:
                anchor_dt = datetime.combine(forecast_date - timedelta(days=1), tm)
                st.subheader(f"{'🔼' if 'High' in title else '⏹️' if 'Close' in title else '🔽'} {title} Table")
                df = generate_spx_table(price, slope, anchor_dt)
                st.dataframe(df, use_container_width=True)

        else:
            # special Tue/Thu logic
            st.warning("Tuesday/Thursday logic placeholder — customize as before")

# Other stocks
for i, label in enumerate(tab_labels[1:], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{ICONS[label]} {label} Forecast</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        low_p  = col1.number_input("🔽 Prev-Day Low Price", format="%.2f", key=f"{label}_low_price")
        low_t  = col1.time_input("🕒 Prev-Day Low Time", value=time(7,30), step=1800, key=f"{label}_low_time")
        high_p = col2.number_input("🔼 Prev-Day High Price", format="%.2f", key=f"{label}_high_price")
        high_t = col2.time_input("🕒 Prev-Day High Time", value=time(7,30), step=1800, key=f"{label}_high_time")

        if st.button(f"🔮 Generate {label}"):
            # show anchors
            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for title, val in [("Low Anchor", low_p), ("High Anchor", high_p)]:
                icon = "🔽" if "Low" in title else "🔼"
                st.markdown(f'''
                  <div class="anchor-card">
                    <div class="icon-wrapper">{icon}</div>
                    <div>
                      <div class="title">{title}</div>
                      <div class="value">{val:.2f}</div>
                    </div>
                  </div>
                ''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # tables
            a_low  = datetime.combine(forecast_date, low_t)
            a_high = datetime.combine(forecast_date, high_t)
            st.subheader("🔻 Low Anchor Table")
            st.dataframe(generate_stock_table(low_p, SLOPES[label], a_low), use_container_width=True)
            st.subheader("🔺 High Anchor Table")
            st.dataframe(generate_stock_table(high_p, SLOPES[label], a_high), use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)