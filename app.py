import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from io import StringIO, BytesIO
import zipfile

# ── CONFIG ────────────────────────────────────────────────────────────────────
PAGE_TITLE  = "Dr Didy Forecast"
PAGE_ICON   = "📈"
LAYOUT      = "wide"
SIDEBAR     = "expanded"
VERSION     = "1.1"          # bump whenever you tweak

SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.1508,          # user’s latest default
    "NVDA": -0.0485,
    "AAPL": -0.0750,
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

# ── THEME ─────────────────────────────────────────────────────────────────────
BASE_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
  :root {{
    --bg: #FFFFFF;         /* replaced in dark mode */
    --text: #1F2937;
    --primary: #3B82F6;
    --card-bg: #F3F4F6;
    --radius: 8px;
    --shadow: 0 4px 12px rgba(0,0,0,0.05);
  }}
  html,body,section,div,span{{ background:var(--bg); color:var(--text); font-family:'Inter',sans-serif; }}
  .stApp {{ background:var(--bg); }}
  .main-container{{ padding:1rem; max-width:1200px; margin:auto; }}
  .app-header{{ padding:1rem; border-radius:var(--radius); box-shadow:var(--shadow); margin-bottom:1rem;
                background:var(--primary); color:#fff; }}
  .tab-header{{ font-size:1.5rem; font-weight:600; margin-bottom:0.5rem; }}
  .metric-cards{{ display:flex; gap:1rem; margin-bottom:1rem; overflow-x:auto; }}
  .anchor-card{{ background:var(--card-bg); border-radius:var(--radius); box-shadow:var(--shadow);
                 padding:1rem; flex:1; display:flex; align-items:center; min-width:160px; }}
  .anchor-card .icon-wrapper{{ font-size:2rem; margin-right:0.5rem; }}
  .anchor-card .title{{ font-size:0.875rem; opacity:0.7; }}
  .anchor-card .value{{ font-size:1.25rem; font-weight:600; }}
  .stDataFrame>div{{ border:none!important; }}
  .stButton>button{{ border:none; border-radius:var(--radius)!important; padding:0.5rem 1rem;
                     font-weight:600; transition:opacity .2s; background:var(--primary); color:#fff; }}
  .stButton>button:hover{{ opacity:.9; }}
</style>
"""

DARK_SWAP = {
    "--bg: #FFFFFF;": "--bg: #0F172A;",
    "--text: #1F2937;": "--text: #E2E8F0;",
    "--primary: #3B82F6;": "--primary: #6366F1;",
    "--card-bg: #F3F4F6;": "--card-bg: #1E293B;",
    "rgba(0,0,0,0.05)": "rgba(0,0,0,0.25)",
}
DARK_CSS = BASE_CSS
for k, v in DARK_SWAP.items():
    DARK_CSS = DARK_CSS.replace(k, v)

# ── PAGE SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(PAGE_TITLE, PAGE_ICON, LAYOUT, initial_sidebar_state=SIDEBAR)
theme_choice = st.sidebar.radio("🎨 Theme", ["Light", "Dark"], horizontal=True)
st.markdown(DARK_CSS if theme_choice == "Dark" else BASE_CSS, unsafe_allow_html=True)

# ── UTILITIES ────────────────────────────────────────────────────────────────
def gen_time_slots(start: time, end: time, freq: int = 30) -> list[str]:
    out, cur = [], datetime.combine(date.today(), start)
    end_dt   = datetime.combine(date.today(), end)
    while cur <= end_dt:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=freq)
    return out

@st.cache_data(show_spinner=False)
def generate_table(price: float, slope: float, anchor: datetime,
                   skip_4pm: bool = False, slots: list[str] | None = None) -> pd.DataFrame:
    rows, slots = [], slots or TIME_SLOTS
    for t in slots:
        h, m = map(int, t.split(":"))
        ts   = datetime.combine(forecast_date, time(h, m))
        blocks = 0
        cur = anchor
        while cur < ts:
            if not (skip_4pm and cur.hour == 16):
                blocks += 1
            cur += timedelta(minutes=30)
        rows.append({"Time": t,
                     "Entry": round(price + slope * blocks, 2),
                     "Exit":  round(price - slope * blocks, 2)})
    return pd.DataFrame(rows)

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# ── SIDEBAR SETTINGS ──────────────────────────────────────────────────────────
forecast_date = st.sidebar.date_input("Forecast Date", date.today() + timedelta(days=1))

with st.sidebar.expander("⏱ Time Slots"):
    start_t = st.time_input("Start", value=time(7,30), step=1800)
    end_t   = st.time_input("End",   value=time(14,30), step=1800)
    freq    = st.number_input("Interval (min)", 15, 60, 30, 15)
TIME_SLOTS = gen_time_slots(start_t, end_t, freq)

st.sidebar.divider()

with st.sidebar.expander("📉 Slopes"):
    for k in SLOPES:
        SLOPES[k] = st.slider(k.replace("_"," "), -1.0, 1.0, SLOPES[k], 0.0001)

with st.sidebar.container():
    st.markdown(f"<small>Version {VERSION}</small>", unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-container">', unsafe_allow_html=True)
st.markdown(f'<div class="app-header"><h1>{PAGE_ICON} {PAGE_TITLE}</h1></div>', unsafe_allow_html=True)
tabs = st.tabs([f"{ICONS[t]} {t}" for t in ICONS])

# ── SPX TAB ───────────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    hp = c1.number_input("🔼 High Price", 6185.8, key="spx_hp", format="%.2f")
    ht = c1.time_input("🕒 High Time",  time(11,30), key="spx_ht")
    cp = c2.number_input("⏹️ Close Price", 6170.2, key="spx_cp", format="%.2f")
    ct = c2.time_input("🕒 Close Time", time(15,0),   key="spx_ct")
    lp = c3.number_input("🔽 Low Price", 6130.4, key="spx_lp", format="%.2f")
    lt = c3.time_input("🕒 Low Time",   time(13,30), key="spx_lt")

    if st.button("🔮 Generate SPX"):
        with st.spinner("Calculating forecasts…"):
            df_high  = generate_table(hp, SLOPES["SPX_HIGH"],
                                      datetime.combine(forecast_date - timedelta(days=1), ht),
                                      True)
            df_close = generate_table(cp, SLOPES["SPX_CLOSE"],
                                      datetime.combine(forecast_date - timedelta(days=1), ct),
                                      True)
            pred_open  = df_high.iloc[0]["Entry"]
            pred_close = df_close.iloc[-1]["Exit"]

        st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
        for t,v,i in [("Predicted Open",pred_open,"📈"),("Predicted Close",pred_close,"📉")]:
            st.markdown(f"""
              <div class="anchor-card">
                <div class="icon-wrapper">{i}</div>
                <div><div class="title">{t}</div><div class="value">{v:.2f}</div></div>
              </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # anchor tables
        pack = BytesIO()
        with zipfile.ZipFile(pack, "w") as zf:
            for title, price, slope, tme in [
                ("High Anchor",hp,SLOPES["SPX_HIGH"],ht),
                ("Close Anchor",cp,SLOPES["SPX_CLOSE"],ct),
                ("Low Anchor",lp,SLOPES["SPX_LOW"],lt),
            ]:
                skip = True   # SPX skip rule
                df = generate_table(price, slope,
                                    datetime.combine(forecast_date - timedelta(days=1), tme),
                                    skip)
                st.subheader(f"{'🔼' if 'High' in title else '⏹️' if 'Close' in title else '🔽'} {title}")
                st.dataframe(df, use_container_width=True)
                csv_bytes = to_csv_bytes(df)
                st.download_button(f"Download {title} CSV", csv_bytes,
                                   f"SPX_{title.replace(' ','_')}.csv", "text/csv")
                st.line_chart(df.set_index("Time")[["Entry","Exit"]])
                zf.writestr(f"SPX_{title.replace(' ','_')}.csv", csv_bytes)
        st.download_button("⬇️ Download All SPX CSVs (Zip)", pack.getvalue(),
                           "SPX_Forecasts.zip", "application/zip")
        st.balloons()

# ── OTHER STOCKS ──────────────────────────────────────────────────────────────
for idx, tic in enumerate(list(ICONS)[1:], 1):
    with tabs[idx]:
        st.markdown(f'<div class="tab-header">{ICONS[tic]} {tic} Forecast</div>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        low_p = c1.number_input("🔽 Prev-Day Low Price", key=f"{tic}_low_p", format="%.2f")
        low_t = c1.time_input ("🕒 Prev-Day Low Time",  time(7,30), key=f"{tic}_low_t")
        high_p= c2.number_input("🔼 Prev-Day High Price",key=f"{tic}_high_p", format="%.2f")
        high_t= c2.time_input ("🕒 Prev-Day High Time", time(7,30), key=f"{tic}_high_t")

        if st.button(f"🔮 Generate {tic}"):
            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for t,v,i in [("Low Anchor",low_p,"🔽"),("High Anchor",high_p,"🔼")]:
                st.markdown(f"""
                  <div class="anchor-card">
                    <div class="icon-wrapper">{i}</div>
                    <div><div class="title">{t}</div><div class="value">{v:.2f}</div></div>
                  </div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            buf = BytesIO()
            with zipfile.ZipFile(buf,"w") as zf:
                for title, price, tme in [("Low Anchor",low_p,low_t),("High Anchor",high_p,high_t)]:
                    df = generate_table(price, SLOPES[tic],
                                        datetime.combine(forecast_date, tme),
                                        False)
                    st.subheader(f"{'🔻' if 'Low' in title else '🔺'} {title}")
                    st.dataframe(df, use_container_width=True)
                    csvb = to_csv_bytes(df)
                    st.download_button(f"Download {tic}_{title}.csv", csvb,
                                       f"{tic}_{title.replace(' ','_')}.csv", "text/csv")
                    st.line_chart(df.set_index("Time")[["Entry","Exit"]])
                    zf.writestr(f"{tic}_{title.replace(' ','_')}.csv", csvb)
            st.download_button(f"⬇️ Download All {tic} CSVs (Zip)", buf.getvalue(),
                               f"{tic}_Forecasts.zip", "application/zip")
            st.snow()

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    f"<div style='text-align:center;font-size:0.8rem;'>"
    f"Dr Didy Forecast v{VERSION} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    f"</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)