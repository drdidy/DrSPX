import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta

# ── Configuration ─────────────────────────────────────────────────────────────
PAGE_TITLE = "Dr Didy Forecast"
PAGE_ICON = "📈"
LAYOUT = "wide"
SIDEBAR_STATE = "expanded"
VERSION = "1.0"

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

# ── Utility Functions ──────────────────────────────────────────────────────────
def gen_time_slots(start: time, end: time, freq: int = 30) -> list[str]:
    slots = []
    current = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    while current <= end_dt:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=freq)
    return slots

@st.cache_data(show_spinner=False)
def generate_table(price: float, slope: float, anchor: datetime, is_spx: bool = False) -> pd.DataFrame:
    rows = []
    for slot in TIME_SLOTS:
        h, m = map(int, slot.split(":"))
        ts = datetime.combine(forecast_date, time(h, m))
        if is_spx:
            # skip 16:00–16:30
            b = 0
            cur = anchor
            while cur < ts:
                if cur.hour != 16:
                    b += 1
                cur += timedelta(minutes=30)
        else:
            b = max(0, int((ts - anchor).total_seconds() // 1800))
        rows.append({
            "Time": slot,
            "Entry": round(price + slope * b, 2),
            "Exit":  round(price - slope * b, 2),
        })
    return pd.DataFrame(rows)

# ── Theme CSS ─────────────────────────────────────────────────────────────────
BASE_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
  :root { --radius:8px; --shadow:0 4px 12px rgba(0,0,0,0.05); }
  body { font-family:'Inter',sans-serif!important; }
  .main-container { padding:1rem; max-width:1200px; margin:auto; }
  .app-header { padding:1rem; border-radius:var(--radius); box-shadow:var(--shadow); margin-bottom:1rem; }
  .tab-header { font-size:1.5rem; font-weight:600; margin-bottom:0.5rem; }
  .metric-cards { display:flex; gap:1rem; margin-bottom:1rem; overflow-x:auto; }
  .anchor-card { background-color:var(--card-bg); border-radius:var(--radius);
                 box-shadow:var(--shadow); padding:1rem; flex:1; display:flex; align-items:center; }
  .anchor-card .icon-wrapper { font-size:2rem; margin-right:0.5rem; }
  .anchor-card .title { font-size:0.875rem; color:var(--text); }
  .anchor-card .value { font-size:1.25rem; font-weight:600; }
  .stButton>button { border:none; border-radius:var(--radius)!important;
                     padding:0.5rem 1rem; font-weight:600; transition:opacity 0.2s; }
  .stButton>button:hover { opacity:0.9; }
  .stDataFrame>div { border:none!important; }
</style>
"""

LIGHT_CSS = BASE_CSS.replace("--bg: #ffffff;", "--bg: #ffffff;") \
                    .replace("--text: #1f2937;", "--text: #1f2937;") \
                    .replace("--primary: #3b82f6;", "--primary: #3b82f6;") \
                    .replace("--card-bg: #f3f4f6;", "--card-bg: #f3f4f6;")

DARK_CSS = BASE_CSS.replace("--bg: #0f172a;", "--bg: #0f172a;") \
                   .replace("--text: #e2e8f0;", "--text: #e2e8f0;") \
                   .replace("--primary: #6366f1;", "--primary: #6366f1;") \
                   .replace("--card-bg: #1e293b;", "--card-bg: #1e293b;") \
                   .replace("rgba(0,0,0,0.05)", "rgba(0,0,0,0.2)")

# ── Page Setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state=SIDEBAR_STATE,
)

theme = st.sidebar.radio("🎨 Theme", ["Light", "Dark"])
st.markdown(DARK_CSS if theme == "Dark" else LIGHT_CSS, unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
if uploaded_logo := st.sidebar.file_uploader("Upload Logo", type=["png","jpg","gif"]):
    st.sidebar.image(uploaded_logo, width=100)

st.sidebar.header("⚙️ Settings")
forecast_date = st.sidebar.date_input(
    "Forecast Date", date.today() + timedelta(days=1)
)

with st.sidebar.expander("⏱ Time Slots"):
    slot_start = st.time_input("Start Time", value=time(7,30), step=1800)
    slot_end   = st.time_input("End Time",   value=time(14,30), step=1800)
    freq       = st.number_input("Interval (min)", min_value=15, max_value=60, value=30, step=15)
TIME_SLOTS = gen_time_slots(slot_start, slot_end, freq)

st.sidebar.divider()
st.sidebar.subheader("Adjust Slopes")
for key in SLOPES:
    SLOPES[key] = st.sidebar.slider(key.replace("_", " "), -1.0, 1.0, SLOPES[key], step=0.0001)

with st.sidebar.expander("ℹ️ About this app"):
    st.write("""
      • Uses 30-min block slopes to project Entry/Exit  
      • SPX skips 16:00–16:30; other stocks continuous  
      • Adjust slopes, customize slots, export CSV & charts  
    """)

# ── Main Header ────────────────────────────────────────────────────────────────
st.markdown('<div class="main-container">', unsafe_allow_html=True)
st.markdown(
    f'<div class="app-header" style="background-color:var(--primary); color:#fff;">'
    f'<h1>{PAGE_ICON} {PAGE_TITLE}</h1></div>',
    unsafe_allow_html=True
)

tabs = st.tabs([f"{ICONS[t]} {t}" for t in ICONS])

# ── SPX Tab ───────────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price", value=6185.8, format="%.2f", key="spx_hp")
    ht = c1.time_input("🕒 High Time", value=time(11,30), key="spx_ht")
    cp = c2.number_input("⏹️ Close Price", value=6170.2, format="%.2f", key="spx_cp")
    ct = c2.time_input("🕒 Close Time", value=time(15,0),  key="spx_ct")
    lp = c3.number_input("🔽 Low Price",  value=6130.4, format="%.2f", key="spx_lp")
    lt = c3.time_input("🕒 Low Time",    value=time(13,30), key="spx_lt")

    if st.button("🔮 Generate SPX"):
        with st.spinner("Generating SPX forecasts..."):
            # Summary metrics
            df_high  = generate_table(hp, SLOPES["SPX_HIGH"],  datetime.combine(forecast_date - timedelta(days=1), ht), True)
            df_close = generate_table(cp, SLOPES["SPX_CLOSE"], datetime.combine(forecast_date - timedelta(days=1), ct), True)
            pred_open  = df_high.iloc[0]["Entry"]
            pred_close = df_close.iloc[-1]["Exit"]

        st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
        for title, val, icon in [
            ("Predicted Open",  pred_open,  "📈"),
            ("Predicted Close", pred_close, "📉")
        ]:
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

        # Detailed tables & downloads & charts
        for title, price, slope, tme in [
            ("High Anchor",  hp, SLOPES["SPX_HIGH"], ht),
            ("Close Anchor", cp, SLOPES["SPX_CLOSE"], ct),
            ("Low Anchor",   lp, SLOPES["SPX_LOW"],  lt),
        ]:
            st.subheader(f"{'🔼' if 'High' in title else '⏹️' if 'Close' in title else '🔽'} {title} Table")
            df = generate_table(price, slope, datetime.combine(forecast_date - timedelta(days=1), tme), True)
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(f"Download {title} CSV", data=csv,
                               file_name=f"SPX_{title.replace(' ','_')}.csv", mime="text/csv")
            st.line_chart(df.set_index("Time")[["Entry", "Exit"]])
        st.balloons()

# ── Other Stocks Tabs ─────────────────────────────────────────────────────────
for i, ticker in enumerate(list(ICONS)[1:], start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{ICONS[ticker]} {ticker} Forecast</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        low_p  = col1.number_input("🔽 Prev-Day Low Price",  format="%.2f", key=f"{ticker}_low_price")
        low_t  = col1.time_input("🕒 Prev-Day Low Time",    value=time(7,30), key=f"{ticker}_low_time")
        high_p = col2.number_input("🔼 Prev-Day High Price", format="%.2f", key=f"{ticker}_high_price")
        high_t = col2.time_input("🕒 Prev-Day High Time",   value=time(7,30), key=f"{ticker}_high_time")

        if st.button(f"🔮 Generate {ticker}"):
            with st.spinner(f"Generating {ticker} forecasts..."):
                # nothing to precompute here
                pass

            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for title, val, icon in [
                ("Low Anchor",  low_p,  "🔽"),
                ("High Anchor", high_p, "🔼"),
            ]:
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

            for title, price, tme in [
                ("Low Anchor",  low_p,  low_t),
                ("High Anchor", high_p, high_t),
            ]:
                icon2 = "🔻" if "Low" in title else "🔺"
                st.subheader(f"{icon2} {title} Table")
                anchor_dt = datetime.combine(forecast_date, tme)
                df = generate_table(price, SLOPES[ticker], anchor_dt, False)
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(f"Download {ticker}_{title} CSV", data=csv,
                                   file_name=f"{ticker}_{title.replace(' ','_')}.csv", mime="text/csv")
                st.line_chart(df.set_index("Time")[["Entry", "Exit"]])
            st.balloons()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    f"<div style='text-align:center; font-size:0.8rem;'>"
    f"App version {VERSION} — Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    f"</div>", unsafe_allow_html=True
)
st.markdown("</div>", unsafe_allow_html=True)