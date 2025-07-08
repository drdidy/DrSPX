import streamlit as st
from datetime import datetime, time, timedelta
import pandas as pd

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

# --- PAGE CONFIG & STYLES ---
st.set_page_config(page_title="Precision Entry & Exit Projections", page_icon="📈", layout="wide")
st.markdown("""
<style>
body {background:#eef2f6; margin:0; font-family:sans-serif;}
.sidebar .sidebar-content {
  background:#1f1f3b; color:#fff; padding:1rem; border-radius:0 1rem 1rem 0;
}
.app-header {
  margin:1rem 2rem; padding:1.5rem; background:#fff; border-radius:1rem;
  box-shadow:0 4px 12px rgba(0,0,0,0.1); text-align:center;
}
.app-header h1 {margin:0; font-size:2.25rem; color:#1f4068;}
.tab-header {
  margin:1.5rem 2rem 0.5rem;
  font-size:1.25rem; color:#1f4068; font-weight:600;
}
.metric-cards {display:flex; gap:1rem; margin:1rem 2rem;}
.anchor-card {
  flex:1; display:flex; align-items:center; padding:1rem 1.5rem;
  border-radius:1rem; color:#fff; box-shadow:0 8px 20px rgba(0,0,0,0.1);
  transition:transform 0.2s, box-shadow 0.2s;
}
.anchor-card:hover {
  transform:translateY(-4px);
  box-shadow:0 12px 30px rgba(0,0,0,0.15);
}
.anchor-card .icon-wrapper {
  width:48px; height:48px; background:#fff; border-radius:50%;
  display:flex; align-items:center; justify-content:center; margin-right:1rem;
  font-size:1.5rem;
}
.anchor-card .content .title {
  font-weight:600; font-size:1.1rem;
}
.anchor-card .content .value {
  font-weight:300; font-size:2rem; margin-top:0.25rem;
}
.anchor-high {background:#ff6b6b;}
.anchor-close{background:#4ecdc4;}
.anchor-low  {background:#f7b731; color:#333;}
.card {
  background:#fff; margin:1rem 2rem; padding:1rem; border-radius:1rem;
  box-shadow:0 4px 12px rgba(0,0,0,0.05);
}
.stButton>button {
  border-radius:0.5rem; padding:0.5rem 1rem;
}
@media(max-width:768px){
  .metric-cards {flex-direction:column;}
  .app-header {margin:1rem; padding:1rem;}
  .tab-header {margin:1rem; font-size:1.1rem;}
  .card {margin:1rem;}
}
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<div class="app-header"><h1>📊 Precision Entry & Exit Projections</h1></div>', unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date = st.date_input("Forecast Date", datetime.now().date() + timedelta(days=1))
    st.divider()
    st.subheader("Adjust Slopes")
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_"," "), -1.0, 1.0, SLOPES[k], step=0.0001)

# --- TABS ---
tabs = st.tabs(["🧭 SPX","🚗 TSLA","🧠 NVDA","🍎 AAPL","📦 AMZN","🔍 GOOGL"])

# --- SPX TAB ---
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
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

        # colored anchor cards
        cards = f"""
        <div class="metric-cards">
          <div class="anchor-card anchor-high">
            <div class="icon-wrapper">🔼</div>
            <div class="content">
              <div class="title">High Anchor</div>
              <div class="value">{hp:.2f}</div>
            </div>
          </div>
          <div class="anchor-card anchor-close">
            <div class="icon-wrapper">⏹️</div>
            <div class="content">
              <div class="title">Close Anchor</div>
              <div class="value">{cp:.2f}</div>
            </div>
          </div>
          <div class="anchor-card anchor-low">
            <div class="icon-wrapper">🔽</div>
            <div class="content">
              <div class="title">Low Anchor</div>
              <div class="value">{lp:.2f}</div>
            </div>
          </div>
        </div>
        """
        st.markdown(cards, unsafe_allow_html=True)

        # tables
        for icon, title, price, slope, anchor in [
            ("🔼","High Anchor", hp, SLOPES["SPX_HIGH"], ah),
            ("⏹️","Close Anchor",cp, SLOPES["SPX_CLOSE"],ac),
            ("🔽","Low Anchor", lp, SLOPES["SPX_LOW"],  al),
        ]:
            st.subheader(f"{icon} {title} Table")
            st.markdown('<div class="card">', unsafe_allow_html=True)
            df = generate_spx(price, slope, anchor, forecast_date)
            st.dataframe(df.round(2), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# --- STOCK TABS ---
icons = {"TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","AMZN":"📦","GOOGL":"🔍"}
for i, label in enumerate(["TSLA","NVDA","AAPL","AMZN","GOOGL"], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>', unsafe_allow_html=True)
        col = st.columns(2)[0]
        lp = col.number_input("🔽 Prev-Day Low Price", 0.0, format="%.2f", key=f"{label}_low_price")
        lt = col.time_input("🕒 Prev-Day Low Time", datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_low_time")
        hp = col.number_input("🔼 Prev-Day High Price",0.0, format="%.2f", key=f"{label}_high_price")
        ht = col.time_input("🕒 Prev-Day High Time",datetime(2025,1,1,8,30).time(), step=1800, key=f"{label}_high_time")

        if st.button(f"🔮 Generate {label}", key=f"btn_{label}"):
            a_low  = datetime.combine(forecast_date - timedelta(days=1), lt)
            a_high = datetime.combine(forecast_date - timedelta(days=1), ht)

            cards = f"""
            <div class="metric-cards">
              <div class="anchor-card anchor-low">
                <div class="icon-wrapper">🔽</div>
                <div class="content">
                  <div class="title">Low Anchor</div>
                  <div class="value">{lp:.2f}</div>
                </div>
              </div>
              <div class="anchor-card anchor-high">
                <div class="icon-wrapper">🔼</div>
                <div class="content">
                  <div class="title">High Anchor</div>
                  <div class="value">{hp:.2f}</div>
                </div>
              </div>
            </div>
            """
            st.markdown(cards, unsafe_allow_html=True)

            st.subheader("🔻 Low Anchor Table")
            st.markdown('<div class="card">', unsafe_allow_html=True)
            df_low = generate_stock(lp, SLOPES[label], a_low, forecast_date, invert=True)
            st.dataframe(df_low.round(2), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.subheader("🔺 High Anchor Table")
            st.markdown('<div class="card">', unsafe_allow_html=True)
            df_high = generate_stock(hp, SLOPES[label], a_high, forecast_date, invert=False)
            st.dataframe(df_high.round(2), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
