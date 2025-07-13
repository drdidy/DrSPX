import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
from typing import List

# ── PAGE CONFIGURATION ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dr Didy Forecast",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── STYLES (Light & Dark, with animations!) ────────────────────────────────────
LIGHT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
:root {
  --bg: #ffffff; --text: #1f2937; --primary: #3b82f6;
  --card-bg: #f3f4f6; --radius: 10px; --shadow: 0 6px 18px rgba(0,0,0,0.08);
}
* { font-family: 'Inter', sans-serif !important; }
body { background: var(--bg) !important; color: var(--text) !important; }
.hero {
  background: linear-gradient(135deg, #3b82f6 0%, #9333ea 100%);
  padding: 2rem; border-radius: var(--radius); margin-bottom: 1.5rem;
  color: #fff; animation: glow 4s ease-in-out infinite;
}
@keyframes glow {
  0%,100% { box-shadow: 0 0 8px rgba(255,255,255,0.3); }
  50% { box-shadow: 0 0 20px rgba(255,255,255,0.6); }
}
.tab-header { font-size:1.6rem; font-weight:600; margin:1rem 0; }
.metric-cards { display:flex; gap:1rem; margin:1rem 0; }
.anchor-card {
  background: var(--card-bg); padding:1rem; border-radius:var(--radius);
  box-shadow:var(--shadow); flex:1; display:flex; align-items:center;
}
.anchor-card .icon { font-size:2rem; margin-right:.75rem; }
.stButton>button {
  background: var(--primary)!important; color:#fff!important;
  border:none!important; border-radius:var(--radius)!important;
  padding:.5rem 1.25rem!important; transition:transform .1s;
}
.stButton>button:hover { transform:scale(1.03); }
.stDataFrame table { border:none!important; }
footer { text-align:center; font-size:.8rem; margin-top:2rem; color:#888; }
</style>
"""
DARK_CSS = LIGHT_CSS.replace(
    "#ffffff", "#0f172a"
).replace(
    "#1f2937", "#e2e8f0"
).replace(
    "#f3f4f6", "#1e293b"
).replace(
    "rgba(0,0,0", "rgba(0,0,0,0.4)"
)

# ── THEME SWITCHER ──────────────────────────────────────────────────────────────
theme = st.sidebar.radio("🎨 Theme", ["Light", "Dark"])
st.markdown(DARK_CSS if theme == "Dark" else LIGHT_CSS, unsafe_allow_html=True)

# ── CONSTANTS & DATA STRUCTURES ────────────────────────────────────────────────
SLOPES = {
    "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792,
    "TSLA": -0.1500, "NVDA": -0.0485, "AAPL": -0.075,
    "MSFT": -0.1964, "AMZN": -0.0782, "GOOGL": -0.0485,
}
ICONS = {"SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}
TIME_SLOTS = [(datetime.strptime("07:30","%H:%M") + timedelta(minutes=30*i)).strftime("%H:%M") for i in range(15)]

@dataclass
class Anchor:
    label: str
    price: float
    time: time
    slope: float
    icon: str

# ── SIDEBAR CONTROLS ───────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Settings")
forecast_date = st.sidebar.date_input("Forecast Date", date.today() + timedelta(days=1),
                                      help="Choose the date for your forecast")
st.sidebar.divider()
st.sidebar.subheader("Adjust Slopes")
for key in SLOPES:
    SLOPES[key] = st.sidebar.slider(key.replace("_"," "), -1.0, 1.0, SLOPES[key], step=0.0001,
                                     help="Fine-tune the block-slope")

# ── UTILITY FUNCTIONS ──────────────────────────────────────────────────────────
@st.cache_data
def calculate_blocks(anchor: datetime, target: datetime, skip_16=False) -> int:
    blocks, current = 0, anchor
    while current < target:
        if not (skip_16 and current.hour == 16):
            blocks += 1
        current += timedelta(minutes=30)
    return blocks

@st.cache_data
def generate_table(anchors: Anchor, is_spx: bool) -> pd.DataFrame:
    rows = []
    for slot in TIME_SLOTS:
        h, m = map(int, slot.split(":"))
        dt = datetime.combine(forecast_date - (timedelta(days=1) if is_spx else timedelta(0)), anchors.time)
        tgt = datetime.combine(forecast_date, time(h, m))
        b = calculate_blocks(dt, tgt, skip_16=is_spx)
        entry = anchors.price + anchors.slope * b
        exit_ = anchors.price - anchors.slope * b
        rows.append({"Time": slot, "Entry": round(entry,2), "Exit": round(exit_,2)})
    return pd.DataFrame(rows)

# ── MAIN HEADER ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <h1>📊 Dr Didy Forecast</h1>
  <p style="opacity:.8">Instant intraday block-based projections for SPX & top tech stocks</p>
</div>
""", unsafe_allow_html=True)

# ── CREATE TABS ────────────────────────────────────────────────────────────────
tabs = st.tabs([f"{ICONS[sym]} {sym}" for sym in ICONS])

def render_tab(sym: str, idx: int):
    with tabs[idx]:
        st.markdown(f'<div class="tab-header">{ICONS[sym]} {sym} Forecast</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        low_p  = col1.number_input("🔽 Prev-Day Low Price", format="%.2f", key=f"{sym}_low_price")
        low_t  = col1.time_input("🕒 Prev-Day Low Time", value=time(7,30), step=1800, key=f"{sym}_low_time")
        high_p = col2.number_input("🔼 Prev-Day High Price", format="%.2f", key=f"{sym}_high_price")
        high_t = col2.time_input("🕒 Prev-Day High Time", value=time(7,30), step=1800, key=f"{sym}_high_time")

        anchors: List[Anchor] = [
            Anchor("Low Anchor", low_p, low_t, SLOPES[sym], "🔽"),
            Anchor("High Anchor", high_p, high_t, SLOPES[sym], "🔼"),
        ]

        if st.button(f"🔮 Generate {sym}", use_container_width=True):
            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for anc in anchors:
                st.markdown(f"""
                    <div class="anchor-card">
                      <div class="icon">{anc.icon}</div>
                      <div>
                        <div class="title">{anc.label}</div>
                        <div class="value">{anc.price:.2f}</div>
                      </div>
                    </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            for anc in anchors:
                st.subheader(f"{anc.icon} {anc.label} Table")
                df = generate_table(anc, is_spx=False)
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode()
                st.download_button(f"⬇️ Download {anc.label} CSV", csv, f"{sym}_{anc.label}.csv")

# ── SPX SPECIAL TAB ────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown(f'<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price",    value=6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("🕒 High Time",       value=time(11,30), step=1800, key="spx_ht")
    cp = c2.number_input("⏹️ Close Price",   value=6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("🕒 Close Time",      value=time(15,0),  step=1800, key="spx_ct")
    lp = c3.number_input("🔽 Low Price",     value=6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("🕒 Low Time",        value=time(13,30), step=1800, key="spx_lt")

    is_tue, is_thu = forecast_date.weekday()==1, forecast_date.weekday()==3

    if st.button("🔮 Generate SPX", use_container_width=True):
        # Tuesday & Thursday logic could be extended here...
        anchors = [
            Anchor("High Anchor", hp, ht, SLOPES["SPX_HIGH"], "🔼"),
            Anchor("Close Anchor", cp, ct, SLOPES["SPX_CLOSE"], "⏹️"),
            Anchor("Low Anchor",  lp, lt, SLOPES["SPX_LOW"],  "🔽"),
        ]
        st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
        for anc in anchors:
            st.markdown(f"""
                <div class="anchor-card">
                  <div class="icon">{anc.icon}</div>
                  <div>
                    <div class="title">{anc.label}</div>
                    <div class="value">{anc.price:.2f}</div>
                  </div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        for anc in anchors:
            st.subheader(f"{anc.icon} {anc.label} Table")
            df = generate_table(anc, is_spx=True)
            st.dataframe(df, use_container_width=True)
            st.download_button(f"⬇️ Download {anc.label} CSV", df.to_csv(index=False).encode(), f"SPX_{anc.label}.csv")

# ── RENDER OTHER STOCK TABS ────────────────────────────────────────────────────
for idx, sym in enumerate(list(ICONS)[1:], start=1):
    render_tab(sym, idx)

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("<footer>© 2025 Dr Didy Forecast • Built with ❤ and Streamlit</footer>", unsafe_allow_html=True)