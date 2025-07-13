import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
from typing import Dict, Any

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide")

# ── Session defaults ──────────────────────────────────────────────────────────
if "scenarios" not in st.session_state:
    st.session_state.scenarios: Dict[str, Any] = {}
if "slopes" not in st.session_state:
    st.session_state.slopes = {
        "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792,
        "TSLA": -0.1500,     "NVDA": -0.0485,      "AAPL": -0.075,
        "MSFT": -0.1964,     "AMZN": -0.0782,      "GOOGL": -0.0485,
    }
if "primary_color" not in st.session_state:
    st.session_state.primary_color = "#3b82f6"
if "card_bg" not in st.session_state:
    st.session_state.card_bg = "#f3f4f6"
if "theme" not in st.session_state:
    st.session_state.theme = "Light"

# ── Global sidebar controls ───────────────────────────────────────────────────
st.session_state.theme = st.sidebar.selectbox(
    "🎨 Theme", ["Light", "Dark"], index=["Light", "Dark"].index(st.session_state.theme)
)
st.session_state.primary_color = st.sidebar.color_picker(
    "Primary Color", st.session_state.primary_color
)
st.session_state.card_bg = st.sidebar.color_picker(
    "Card Background", st.session_state.card_bg
)

# ── CSS: hide collapse control entirely ───────────────────────────────────────
BASE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
* {{ font-family:'Inter',sans-serif!important; }}
/* hide the collapse-sidebar handle */
[data-testid="collapsedControl"] {{ display: none !important; }}

:root {{
  --bg: #fff; --text: #1f2937;
  --primary: {st.session_state.primary_color};
  --card-bg: {st.session_state.card_bg};
  --radius: 10px; --shadow: 0 6px 18px rgba(0,0,0,0.08);
}}
@media(prefers-color-scheme:dark) {{
  :root {{ --bg:#0f172a; --text:#e2e8f0; }}
}}
body {{ background: var(--bg)!important; color: var(--text)!important; }}
.hero {{
  background: linear-gradient(135deg,var(--primary),#9333ea);
  padding: 2rem; border-radius: var(--radius); margin-bottom: 1.5rem;
  color: #fff; animation: glow 4s ease-in-out infinite;
}}
@keyframes glow {{
  0%,100% {{ box-shadow: 0 0 8px rgba(255,255,255,0.3); }}
  50%    {{ box-shadow: 0 0 20px rgba(255,255,255,0.6); }}
}}
.tab-header {{ font-size: 1.6rem; font-weight: 600; margin: 1rem 0; }}
.metric-cards {{ display: flex; gap: 1rem; margin: 1rem 0; }}
.anchor-card {{
  background: var(--card-bg); padding: 1rem; border-radius: var(--radius);
  box-shadow: var(--shadow); flex: 1; display: flex; align-items: center;
}}
.anchor-card .icon {{ font-size: 2rem; margin-right: .75rem; }}
.stButton>button {{
  background: var(--primary)!important; color: #fff!important;
  border-radius: var(--radius)!important; padding: .5rem 1rem!important;
  transition: transform .1s;
}}
.stButton>button:hover {{ transform: scale(1.03); }}
footer {{ text-align: center; color: gray; margin-top: 2rem; font-size: .8rem; }}
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

# ── Multi‐page router ─────────────────────────────────────────────────────────
pages = ["SPX","TSLA","NVDA","AAPL","MSFT","AMZN","GOOGL","Scenarios","Settings"]
page = st.sidebar.radio("Navigate", pages)

# ── Shared structures & helpers ───────────────────────────────────────────────
@dataclass
class Anchor:
    label: str; price: float; t: time; slope: float; icon: str

TIME_SLOTS = [
    (datetime.strptime("07:30","%H:%M") + timedelta(minutes=30*i)).strftime("%H:%M")
    for i in range(15)
]
ICONS = {"SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}

@st.cache_data
def calculate_blocks(a: datetime, tgt: datetime, skip16: bool) -> int:
    cnt, cur = 0, a
    while cur < tgt:
        if not (skip16 and cur.hour == 16): cnt += 1
        cur += timedelta(minutes=30)
    return cnt

@st.cache_data
def build_table(anc: Anchor, is_spx: bool, fd: date) -> pd.DataFrame:
    rows = []
    anchor_dt = datetime.combine(fd - timedelta(days=1) if is_spx else fd, anc.t)
    for slot in TIME_SLOTS:
        h,m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h,m))
        b   = calculate_blocks(anchor_dt, tgt, skip16=is_spx)
        e   = anc.price + anc.slope*b
        x   = anc.price - anc.slope*b
        rows.append({"Time": slot, "Entry": round(e,2), "Exit": round(x,2)})
    return pd.DataFrame(rows)

# ── SETTINGS PAGE ─────────────────────────────────────────────────────────────
if page == "Settings":
    st.header("⚙️ Settings")
    for k,v in st.session_state.slopes.items():
        st.session_state.slopes[k] = st.slider(k.replace("_"," "), -1.0,1.0, v, step=0.0001)
    st.markdown("---")
    st.subheader("Theme & Colors")
    st.write("Use the sidebar to adjust theme and palette.")

# ── SCENARIOS PAGE ────────────────────────────────────────────────────────────
elif page == "Scenarios":
    st.header("💾 Scenarios")
    name = st.text_input("Scenario name")
    if st.button("Save"):
        st.session_state.scenarios[name] = {
            "slopes": st.session_state.slopes.copy(),
            "primary_color": st.session_state.primary_color,
            "card_bg": st.session_state.card_bg,
            "theme": st.session_state.theme
        }
    for nm,cfg in st.session_state.scenarios.items():
        c1,c2,c3 = st.columns([4,1,1])
        c1.write(nm)
        if c2.button(f"Load##{nm}"):
            st.session_state.slopes       = cfg["slopes"].copy()
            st.session_state.primary_color = cfg["primary_color"]
            st.session_state.card_bg       = cfg["card_bg"]
            st.session_state.theme         = cfg["theme"]
        if c3.button(f"Del##{nm}"):
            del st.session_state.scenarios[nm]

# ── STOCK/SPX PAGES ────────────────────────────────────────────────────────────
else:
    st.markdown('<div class="hero"><h1>📊 Dr Didy Forecast</h1></div>', unsafe_allow_html=True)
    fd = st.date_input("Forecast Date", date.today()+timedelta(days=1))
    # inputs
    cols = 3 if page=="SPX" else 2
    cs = st.columns(cols)
    if page=="SPX":
        hp = cs[0].number_input("🔼 High Price", 6185.8, format="%.2f", key="spx_hp")
        ht = cs[0].time_input("🕒 High Time", time(11,30), step=1800, key="spx_ht")
        cp = cs[1].number_input("⏹️ Close Price", 6170.2, format="%.2f", key="spx_cp")
        ct = cs[1].time_input("🕒 Close Time", time(15,0), step=1800, key="spx_ct")
        lp = cs[2].number_input("🔽 Low Price", 6130.4, format="%.2f", key="spx_lp")
        lt = cs[2].time_input("🕒 Low Time", time(13,30), step=1800, key="spx_lt")
        anchors = [
            Anchor("High Anchor", hp, ht, st.session_state.slopes["SPX_HIGH"], "🔼"),
            Anchor("Close Anchor",cp, ct, st.session_state.slopes["SPX_CLOSE"],"⏹️"),
            Anchor("Low Anchor", lp, lt, st.session_state.slopes["SPX_LOW"], "🔽"),
        ]
    else:
        p = cs[0].number_input("🔽 Prev-Day Low Price", format="%.2f", key=f"{page}_lp")
        t = cs[0].time_input("🕒 Prev-Day Low Time", time(7,30), step=1800, key=f"{page}_lt")
        P = cs[1].number_input("🔼 Prev-Day High Price", format="%.2f", key=f"{page}_hp")
        T = cs[1].time_input("🕒 Prev-Day High Time", time(7,30), step=1800, key=f"{page}_ht")
        anchors = [
            Anchor("Low Anchor", p, t, st.session_state.slopes[page], "🔽"),
            Anchor("High Anchor",P, T, st.session_state.slopes[page], "🔼"),
        ]

    if st.button(f"🔮 Generate {page}", use_container_width=True):
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
            df = build_table(a, is_spx=(page=="SPX"), fd=fd)
            st.subheader(f"{a.icon} {a.label} Table")
            st.dataframe(df, use_container_width=True)
            chart = (
                alt.Chart(df.reset_index().melt(id_vars="Time", value_vars=["Entry","Exit"]))
                .mark_line(point=True)
                .encode(
                    x=alt.X("Time:N", sort=TIME_SLOTS),
                    y="value:Q",
                    color="variable:N",
                    tooltip=["Time","value"]
                )
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)
            csv = df.to_csv(index=False).encode()
            st.download_button(f"⬇️ Download {a.label} CSV", csv, f"{page}_{a.label}.csv", use_container_width=True)

    st.markdown(
        "<footer>© 2025 Dr Didy Forecast • Built with ❤ & Streamlit</footer>",
        unsafe_allow_html=True
    )