import streamlit as st
import pandas as pd
import plotly.express as px
import io
import urllib.parse
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
from typing import Dict, Any, List

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dr Didy Forecast",
    page_icon="📈",
    layout="wide"
)

# ── SESSION STATE DEFAULTS ────────────────────────────────────────────────────
if "scenarios" not in st.session_state:
    st.session_state.scenarios: Dict[str, Any] = {}
if "theme" not in st.session_state:
    st.session_state.theme = "Light"
if "primary_color" not in st.session_state:
    st.session_state.primary_color = "#3b82f6"
if "card_bg" not in st.session_state:
    st.session_state.card_bg = "#f3f4f6"
if "slopes" not in st.session_state:
    st.session_state.slopes = {
        "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792,
        "TSLA": -0.1500,     "NVDA": -0.0485,      "AAPL": -0.075,
        "MSFT": -0.1964,     "AMZN": -0.0782,      "GOOGL": -0.0485,
    }

# ── THEME & COLORS ───────────────────────────────────────────────────────────
st.session_state.theme = st.sidebar.selectbox("🎨 Theme", ["Light", "Dark"], index=["Light","Dark"].index(st.session_state.theme))
st.session_state.primary_color = st.sidebar.color_picker("Primary Color", st.session_state.primary_color)
st.session_state.card_bg       = st.sidebar.color_picker("Card Background", st.session_state.card_bg)

BASE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
* {{ font-family:'Inter',sans-serif!important; }}
[data-testid="collapsedControl"] {{ visibility: hidden!important; }}
:root {{
  --bg: #fff; --text: #1f2937;
  --primary: {st.session_state.primary_color};
  --card-bg: {st.session_state.card_bg};
  --radius: 10px; --shadow: 0 6px 18px rgba(0,0,0,0.08);
}}
@media(prefers-color-scheme:dark) {{
  :root {{ --bg:#0f172a; --text:#e2e8f0; }}
}}
body {{ background:var(--bg)!important; color:var(--text)!important; }}
.hero {{
  background: linear-gradient(135deg,var(--primary),#9333ea);
  padding:2rem; border-radius:var(--radius); margin-bottom:1.5rem;
  color:#fff; animation:glow 4s ease-in-out infinite;
}}
@keyframes glow {{
  0%,100% {{ box-shadow:0 0 8px rgba(255,255,255,0.3); }}
  50% {{ box-shadow:0 0 20px rgba(255,255,255,0.6); }}
}}
.tab-header {{ font-size:1.6rem; font-weight:600; margin:1rem 0; }}
.metric-cards {{ display:flex; gap:1rem; margin:1rem 0; }}
.anchor-card {{
  background:var(--card-bg); padding:1rem; border-radius:var(--radius);
  box-shadow:var(--shadow); flex:1; display:flex; align-items:center;
}}
.anchor-card .icon {{ font-size:2rem; margin-right:.75rem; }}
.stButton>button {{
  background:var(--primary)!important; color:#fff!important;
  border-radius:var(--radius)!important; padding:.5rem 1.25rem!important;
  transition:transform .1s;
}}
.stButton>button:hover {{ transform:scale(1.03); }}
footer {{ text-align:center; color:gray; margin-top:2rem; font-size:.8rem; }}
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

# ── MULTI-PAGE NAVIGATION ────────────────────────────────────────────────────
page = st.sidebar.radio("Navigate", ["Forecast", "Scenarios", "Settings"])

# ── DATA STRUCTURES ───────────────────────────────────────────────────────────
@dataclass
class Anchor:
    label: str
    price: float
    t: time
    slope: float
    icon: str

TIME_SLOTS = [
    (datetime.strptime("07:30","%H:%M") + timedelta(minutes=30*i)).strftime("%H:%M")
    for i in range(15)
]
ICONS = {"SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}

# ── COMMON FUNCTIONS ──────────────────────────────────────────────────────────
@st.cache_data
def calculate_blocks(anchor: datetime, target: datetime, skip16: bool) -> int:
    cnt, cur = 0, anchor
    while cur < target:
        if not (skip16 and cur.hour == 16):
            cnt += 1
        cur += timedelta(minutes=30)
    return cnt

@st.cache_data
def build_table(anc: Anchor, is_spx: bool) -> pd.DataFrame:
    rows = []
    anchor_dt = datetime.combine(
        (forecast_date - timedelta(days=1)) if is_spx else forecast_date,
        anc.t
    )
    for slot in TIME_SLOTS:
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(forecast_date, time(h, m))
        b   = calculate_blocks(anchor_dt, tgt, skip16=is_spx)
        e   = anc.price + anc.slope * b
        x   = anc.price - anc.slope * b
        rows.append({"Time": slot, "Entry": round(e,2), "Exit": round(x,2)})
    return pd.DataFrame(rows)

# ── SETTINGS PAGE ─────────────────────────────────────────────────────────────
if page == "Settings":
    st.header("⚙️ Global Settings")
    st.subheader("Slopes (keep strategy intact)")
    for k, v in st.session_state.slopes.items():
        st.session_state.slopes[k] = st.slider(k.replace("_"," "), -1.0, 1.0, v, step=0.0001, help="Block slope")
    st.markdown("---")
    st.subheader("Theme & Colors")
    st.write("Choose your app palette")
    # color pickers already in sidebar
    st.markdown("---")
    st.subheader("Export Slopes / Colors")
    df_settings = pd.DataFrame({
        "setting": list(st.session_state.slopes.keys()) + ["primary_color","card_bg","theme"],
        "value": list(st.session_state.slopes.values()) + [st.session_state.primary_color, st.session_state.card_bg, st.session_state.theme]
    })
    st.data_editor(df_settings, num_rows="dynamic", use_container_width=True)

# ── SCENARIOS PAGE ────────────────────────────────────────────────────────────
elif page == "Scenarios":
    st.header("💾 Saved Scenarios")
    name = st.text_input("Scenario Name")
    if st.button("Save Scenario"):
        st.session_state.scenarios[name] = {
            "slopes": st.session_state.slopes.copy(),
            "primary_color": st.session_state.primary_color,
            "card_bg": st.session_state.card_bg,
            "theme": st.session_state.theme
        }
    for nm, cfg in st.session_state.scenarios.items():
        col1, col2, col3 = st.columns([4,1,1])
        col1.write(nm)
        if col2.button(f"Load##{nm}"):
            st.session_state.slopes      = cfg["slopes"].copy()
            st.session_state.primary_color = cfg["primary_color"]
            st.session_state.card_bg       = cfg["card_bg"]
            st.session_state.theme         = cfg["theme"]
        if col3.button(f"Del##{nm}"):
            del st.session_state.scenarios[nm]

# ── FORECAST PAGE ─────────────────────────────────────────────────────────────
else:
    st.markdown("""
    <div class="hero">
      <h1>📊 Dr Didy Forecast</h1>
      <p style="opacity:.8;">Standalone intraday block projections<br/>SPX & Top Tech Stocks</p>
    </div>
    """, unsafe_allow_html=True)

    forecast_date = st.date_input("Forecast Date", date.today() + timedelta(days=1),
                                  help="Choose date for your forecast", key="fdate")

    # SPX Tab
    tabs = st.tabs([f"{ICONS[s]} {s}" for s in ICONS])
    with tabs[0]:
        st.markdown(f'<div class="tab-header">🧭 SPX Forecast</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        hp = c1.number_input("🔼 High Price",    value=6185.8, format="%.2f", key="spx_hp", help="Prev-day high")
        ht = c1.time_input("🕒 High Time",       value=time(11,30), step=1800, key="spx_ht", help="Time of high")
        cp = c2.number_input("⏹️ Close Price",   value=6170.2, format="%.2f", key="spx_cp", help="Prev-day close")
        ct = c2.time_input("🕒 Close Time",      value=time(15,0),  step=1800, key="spx_ct", help="Time of close")
        lp = c3.number_input("🔽 Low Price",     value=6130.4, format="%.2f", key="spx_lp", help="Prev-day low")
        lt = c3.time_input("🕒 Low Time",        value=time(13,30), step=1800, key="spx_lt", help="Time of low")

        if st.button("🔮 Generate SPX", use_container_width=True):
            with st.spinner("Building SPX tables & charts…"):
                anchors = [
                    Anchor("High Anchor",  hp, ht, st.session_state.slopes["SPX_HIGH"],  "🔼"),
                    Anchor("Close Anchor", cp, ct, st.session_state.slopes["SPX_CLOSE"], "⏹️"),
                    Anchor("Low Anchor",   lp, lt, st.session_state.slopes["SPX_LOW"],   "🔽"),
                ]
                st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
                for a in anchors:
                    st.markdown(f'''
                        <div class="anchor-card">
                          <div class="icon">{a.icon}</div>
                          <div><div class="title">{a.label}</div><div class="value">{a.price:.2f}</div></div>
                        </div>
                    ''', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                for a in anchors:
                    df = build_table(a, is_spx=True)
                    st.subheader(f"{a.icon} {a.label}")
                    st.data_editor(df, use_container_width=True)
                    fig = px.line(df.reset_index().melt(id_vars="Time", value_vars=["Entry","Exit"]),
                                  x="Time", y="value", color="variable", markers=True,
                                  title=f"{a.label} Projection")
                    st.plotly_chart(fig, use_container_width=True)
                    # Excel download
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                        df.to_excel(writer, sheet_name=a.label, index=False)
                    st.download_button(f"⬇️ Excel {a.label}", buf.getvalue(), f"SPX_{a.label}.xlsx")

                    # Tweet link
                    tweet = f"Forecast for {forecast_date}: {a.label} Entry at {df['Entry'].iloc[0]}"
                    url = "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(tweet)
                    st.markdown(f"[🐦 Tweet {a.label} Forecast]({url})")

    # Other stock tabs
    for idx, sym in enumerate(list(ICONS)[1:], start=1):
        with tabs[idx]:
            st.markdown(f'<div class="tab-header">{ICONS[sym]} {sym} Forecast</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            low_p  = c1.number_input("🔽 Low Price", format="%.2f", key=f"{sym}_lp", help="Prev-day low")
            low_t  = c1.time_input("🕒 Low Time", value=time(7,30), step=1800, key=f"{sym}_lt", help="Time of low")
            high_p = c2.number_input("🔼 High Price", format="%.2f", key=f"{sym}_hp", help="Prev-day high")
            high_t = c2.time_input("🕒 High Time", value=time(7,30), step=1800, key=f"{sym}_ht", help="Time of high")

            if st.button(f"🔮 Generate {sym}", use_container_width=True):
                with st.spinner(f"Building {sym} tables & charts…"):
                    anchors = [
                        Anchor("Low Anchor",  low_p,  low_t,  st.session_state.slopes[sym], "🔽"),
                        Anchor("High Anchor", high_p, high_t, st.session_state.slopes[sym], "🔼"),
                    ]
                    st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
                    for a in anchors:
                        st.markdown(f'''
                            <div class="anchor-card">
                              <div class="icon">{a.icon}</div>
                              <div><div class="title">{a.label}</div><div class="value">{a.price:.2f}</div></div>
                            </div>
                        ''', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                    for a in anchors:
                        df = build_table(a, is_spx=False)
                        st.subheader(f"{a.icon} {a.label}")
                        st.data_editor(df, use_container_width=True)
                        fig = px.line(df.reset_index().melt(id_vars="Time", value_vars=["Entry","Exit"]),
                                      x="Time", y="value", color="variable", markers=True,
                                      title=f"{sym} {a.label}")
                        st.plotly_chart(fig, use_container_width=True)
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                            df.to_excel(writer, sheet_name=a.label, index=False)
                        st.download_button(f"⬇️ Excel {sym} {a.label}", buf.getvalue(),
                                           f"{sym}_{a.label}.xlsx")

    st.markdown("<footer>© 2025 Dr Didy Forecast • Standalone • Built with ❤ & Streamlit</footer>", unsafe_allow_html=True)