import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
from typing import Dict, Any

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dr Didy Forecast",
    page_icon="📈",
    layout="wide"
)

# ── SESSION STATE DEFAULTS ───────────────────────────────────────────────────
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

# ── GLOBAL SIDEBAR CONTROLS ──────────────────────────────────────────────────
st.session_state.theme = st.sidebar.selectbox(
    "🎨 Theme", ["Light", "Dark"],
    index=["Light", "Dark"].index(st.session_state.theme)
)
st.session_state.primary_color = st.sidebar.color_picker(
    "Primary Color", st.session_state.primary_color
)
st.session_state.card_bg = st.sidebar.color_picker(
    "Card Background", st.session_state.card_bg
)

# ── CSS: HIDE COLLAPSE BUTTON & CLEAN STYLING ────────────────────────────────
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
* {{ font-family: 'Inter', sans-serif!important; }}
/* hide Streamlit’s collapse/expand sidebar button entirely */
button[title="Collapse sidebar"], button[title="Expand sidebar"] {{
  display: none !important;
}}
:root {{
  --bg: #fff;
  --text: #1f2937;
  --primary: {st.session_state.primary_color};
  --card-bg: {st.session_state.card_bg};
  --radius: 10px;
  --shadow: 0 4px 12px rgba(0,0,0,0.1);
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #0f172a; --text: #e2e8f0; }}
}}
body {{ background: var(--bg)!important; color: var(--text)!important; }}
.hero {{
  background: linear-gradient(135deg, var(--primary), #9333ea);
  padding: 2rem;
  border-radius: var(--radius);
  margin-bottom: 1.5rem;
  color: #fff;
  animation: glow 4s ease-in-out infinite;
}}
@keyframes glow {{
  0%,100% {{ box-shadow: 0 0 8px rgba(255,255,255,0.3); }}
  50%    {{ box-shadow: 0 0 20px rgba(255,255,255,0.6); }}
}}
.tab-header {{ font-size: 1.5rem; font-weight: 600; margin: 1rem 0; }}
.metric-cards {{ display: flex; gap: 1rem; margin: 1rem 0; }}
.anchor-card {{
  background: var(--card-bg);
  padding: 1rem;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  flex: 1;
  display: flex;
  align-items: center;
}}
.anchor-card .icon {{ font-size: 1.75rem; margin-right: .5rem; }}
.stButton>button {{
  background: var(--primary)!important;
  color: #fff!important;
  border-radius: var(--radius)!important;
  padding: .5rem 1rem!important;
  transition: transform .1s;
}}
.stButton>button:hover {{ transform: scale(1.03); }}
footer {{ text-align: center; color: gray; margin-top: 2rem; font-size: .8rem; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ── MULTI‐PAGE NAVIGATION ────────────────────────────────────────────────────
pages = ["SPX", "TSLA", "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "Scenarios", "Settings"]
page = st.sidebar.radio("Navigate", pages)

# ── DATA STRUCTURES & HELPERS ─────────────────────────────────────────────────
@dataclass
class Anchor:
    label: str
    price: float
    t: time
    slope: float
    icon: str

TIME_SLOTS = [
    (datetime.strptime("07:30", "%H:%M") + timedelta(minutes=30 * i)).strftime("%H:%M")
    for i in range(15)
]
ICONS = {"SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}

@st.cache_data
def calculate_blocks(anchor: datetime, target: datetime, skip_16: bool) -> int:
    cnt, cur = 0, anchor
    while cur < target:
        if not (skip_16 and cur.hour == 16):
            cnt += 1
        cur += timedelta(minutes=30)
    return cnt

@st.cache_data
def build_table(anc: Anchor, is_spx: bool, fd: date) -> pd.DataFrame:
    rows = []
    anchor_dt = datetime.combine(
        fd - timedelta(days=1) if is_spx else fd,
        anc.t
    )
    for slot in TIME_SLOTS:
        h, m = map(int, slot.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b   = calculate_blocks(anchor_dt, tgt, skip_16=is_spx)
        e   = anc.price + anc.slope * b
        x   = anc.price - anc.slope * b
        rows.append({"Time": slot, "Entry": round(e, 2), "Exit": round(x, 2)})
    return pd.DataFrame(rows)

# ── SETTINGS PAGE ─────────────────────────────────────────────────────────────
if page == "Settings":
    st.header("⚙️ Settings")
    st.subheader("Slopes")
    for k, v in st.session_state.slopes.items():
        st.session_state.slopes[k] = st.slider(
            k.replace("_", " "), -1.0, 1.0, v, step=0.0001
        )

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
    for nm, cfg in st.session_state.scenarios.items():
        c1, c2, c3 = st.columns([4,1,1])
        c1.write(nm)
        if c2.button(f"Load##{nm}"):
            st.session_state.slopes       = cfg["slopes"].copy()
            st.session_state.primary_color = cfg["primary_color"]
            st.session_state.card_bg       = cfg["card_bg"]
            st.session_state.theme         = cfg["theme"]
        if c3.button(f"Del##{nm}"):
            del st.session_state.scenarios[nm]

# ── SPX & STOCK PAGES ─────────────────────────────────────────────────────────
else:
    st.markdown('<div class="hero"><h1>📊 Dr Didy Forecast</h1></div>', unsafe_allow_html=True)
    fd = st.date_input("Forecast Date", date.today() + timedelta(days=1))
    is_tue = (page == "SPX" and fd.weekday() == 1)
    is_thu = (page == "SPX" and fd.weekday() == 3)

    if page == "SPX":
        # Prev-day anchors
        hp = st.number_input("🔼 Prev-Day High Price", 6185.8, format="%.2f", key="spx_hp")
        ht = st.time_input("🕒 Prev-Day High Time", time(11,30), step=1800, key="spx_ht")
        cp = st.number_input("⏹️ Prev-Day Close Price", 6170.2, format="%.2f", key="spx_cp")
        ct = st.time_input("🕒 Prev-Day Close Time", time(15,0), step=1800, key="spx_ct")
        lp = st.number_input("🔽 Prev-Day Low Price", 6130.4, format="%.2f", key="spx_lp")
        lt = st.time_input("🕒 Prev-Day Low Time", time(13,30), step=1800, key="spx_lt")

        # Tuesday logic
        if is_tue:
            st.markdown("**Tuesday: Contract-Low Entry Projection**")
            t1, t2 = st.columns(2)
            tue_t = t1.time_input("Contract Low Time", time(7,30), key="tue_t")
            tue_p = t2.number_input("Contract Low Price", 5.0, step=0.1, key="tue_p")
            if st.button("🔮 Generate Tuesday"):
                rows = []
                for slot in TIME_SLOTS:
                    h, m = map(int, slot.split(":"))
                    tgt = datetime.combine(fd, time(h,m))
                    b = calculate_blocks(datetime.combine(fd, tue_t), tgt, skip_16=False)
                    rows.append({"Time": slot, "Projected": round(tue_p + (-0.5250)*b,2)})
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

        # Thursday logic
        elif is_thu:
            st.markdown("**Thursday: OTM-Line & Bounce-Low**")
            o1, o2 = st.columns(2)
            low1_t = o1.time_input("OTM Low 1 Time", time(7,30), key="low1_t")
            low1_p = o1.number_input("OTM Low 1 Price", 10.0, step=0.1, key="low1_p")
            low2_t = o2.time_input("OTM Low 2 Time", time(8,0), key="low2_t")
            low2_p = o2.number_input("OTM Low 2 Price", 12.0, step=0.1, key="low2_p")
            st.markdown("<br><strong>8 EMA Bounce-Low</strong>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            bounce_t = b1.time_input("Bounce Time", time(7,30), key="bounce_t")
            bounce_p = b2.number_input("Bounce Price", 6100.0, step=0.1, key="bounce_p")
            if st.button("🔮 Generate Thursday"):
                # OTM-Line
                n12 = calculate_blocks(
                    datetime.combine(fd, low1_t),
                    datetime.combine(fd, low2_t),
                    skip_16=False
                ) or 1
                alt_slope = (low2_p - low1_p)/n12
                otm = []
                for slot in TIME_SLOTS:
                    h,m = map(int, slot.split(":"))
                    tgt = datetime.combine(fd, time(h,m))
                    b = calculate_blocks(datetime.combine(fd, low1_t), tgt, skip_16=False)
                    otm.append({"Time": slot, "Projected": round(low1_p + alt_slope*b,2)})
                st.subheader("OTM-Line Forecast")
                st.dataframe(pd.DataFrame(otm), use_container_width=True)
                # Bounce-Low
                bl = []
                for slot in TIME_SLOTS:
                    h,m = map(int, slot.split(":"))
                    tgt = datetime.combine(fd, time(h,m))
                    b = calculate_blocks(datetime.combine(fd, bounce_t), tgt, skip_16=False)
                    bl.append({"Time": slot, "Projected": round(bounce_p + st.session_state.slopes["SPX_LOW"]*b,2)})
                st.subheader("Bounce-Low Forecast")
                st.dataframe(pd.DataFrame(bl), use_container_width=True)

        # Mon/Wed/Fri default
        else:
            if st.button("🔮 Generate SPX"):
                anchors = [
                    Anchor("High Anchor", hp, ht, st.session_state.slopes["SPX_HIGH"], "🔼"),
                    Anchor("Close Anchor", cp, ct, st.session_state.slopes["SPX_CLOSE"], "⏹️"),
                    Anchor("Low Anchor", lp, lt, st.session_state.slopes["SPX_LOW"], "🔽"),
                ]
                st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
                for a in anchors:
                    st.markdown(f'''
                        <div class="anchor-card">
                          <div class="icon">{a.icon}</div>
                          <div><div class="title">{a.label}</div>
                               <div class="value">{a.price:.2f}</div></div>
                        </div>
                    ''', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                for a in anchors:
                    df = build_table(a, is_spx=True, fd=fd)
                    st.subheader(f"{a.icon} {a.label}")
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
                    st.download_button(f"⬇️ Download {a.label} CSV", csv,
                                       f"SPX_{a.label}.csv", use_container_width=True)

    # ── OTHER STOCK PAGES ─────────────────────────────────────────────────────
    else:
        st.markdown(f'<h2 class="tab-header">{ICONS[page]} {page} Forecast</h2>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        low_p = c1.number_input("🔽 Prev-Day Low Price", format="%.2f", key=f"{page}_lp")
        low_t = c1.time_input("🕒 Prev-Day Low Time", time(7,30), step=1800, key=f"{page}_lt")
        high_p = c2.number_input("🔼 Prev-Day High Price", format="%.2f", key=f"{page}_hp")
        high_t = c2.time_input("🕒 Prev-Day High Time", time(7,30), step=1800, key=f"{page}_ht")
        if st.button(f"🔮 Generate {page}"):
            anchors = [
                Anchor("Low Anchor", low_p, low_t, st.session_state.slopes[page], "🔽"),
                Anchor("High Anchor", high_p, high_t, st.session_state.slopes[page], "🔼"),
            ]
            st.markdown('<div class="metric-cards">', unsafe_allow_html=True)
            for a in anchors:
                st.markdown(f'''
                    <div class="anchor-card">
                      <div class="icon">{a.icon}</div>
                      <div><div class="title">{a.label}</div>
                           <div class="value">{a.price:.2f}</div></div>
                    </div>
                ''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            for a in anchors:
                df = build_table(a, is_spx=False, fd=fd)
                st.subheader(f"{a.icon} {a.label}")
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
                )
                st.altair_chart(chart, use_container_width=True)
                csv = df.to_csv(index=False).encode()
                st.download_button(f"⬇️ Download {page} {a.label} CSV", csv,
                                   f"{page}_{a.label}.csv", use_container_width=True)

# ── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown(
    "<footer>© 2025 Dr Didy Forecast • Built with ❤ & Streamlit</footer>",
    unsafe_allow_html=True
)