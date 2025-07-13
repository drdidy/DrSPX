import streamlit as st import pandas as pd import altair as alt from datetime import datetime, date, time, timedelta from dataclasses import dataclass from typing import List

── PAGE CONFIG ───────────────────────────────────────────────────────────────

st.set_page_config( page_title="Dr Didy Forecast", page_icon="📈", layout="wide" )

── STATE: SLOPES ──────────────────────────────────────────────────────────────

if "slopes" not in st.session_state: st.session_state.slopes = { "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792, "TSLA": -0.1500,     "NVDA": -0.0485,      "AAPL": -0.075, "MSFT": -0.1964,     "AMZN": -0.0782,      "GOOGL": -0.0485, }

── THEME SWITCHER ────────────────────────────────────────────────────────────

theme = st.sidebar.radio("🎨 Theme", ["Light", "Dark"]) light_css = """

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
* { font-family: 'Inter', sans-serif!important; }
:root {
  --bg: #ffffff; --text: #1f2937; --primary: #3b82f6;
  --card-bg: #f9fafb; --radius: 12px; --shadow: 0 4px 16px rgba(0,0,0,0.06);
}
body {
  background: var(--bg)!important;
  color: var(--text)!important;
  transition: background 0.3s ease;
}
header, .stSidebar, footer {
  transition: all 0.3s ease;
}
section[data-testid="stSidebar"] {
  border-top-right-radius: var(--radius);
  border-bottom-right-radius: var(--radius);
  box-shadow: 4px 0 12px rgba(0,0,0,0.05);
}
section[data-testid="stSidebar"]::before {
  content: '';
  position: absolute;
  top: 0; bottom: 0; left: 0;
  width: 4px;
  background: var(--primary);
  border-top-left-radius: var(--radius);
  border-bottom-left-radius: var(--radius);
}
button[data-testid="collapsedControl"] {
  border-radius: 50%;
  background-color: var(--primary)!important;
  color: #fff!important;
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.4);
  border: none;
  width: 36px; height: 36px;
  transition: background 0.3s ease, transform 0.2s ease;
}
button[data-testid="collapsedControl"]:hover {
  background-color: #2563eb!important;
  transform: scale(1.05);
}
.hero {
  background: linear-gradient(135deg, var(--primary), #9333ea);
  padding: 2rem; border-radius: var(--radius); margin-bottom: 1.5rem;
  color: #fff; animation: glow 4s ease-in-out infinite;
  text-align: center;
}
@keyframes glow {
  0%,100% { box-shadow: 0 0 8px rgba(255,255,255,0.2); }
  50%    { box-shadow: 0 0 20px rgba(255,255,255,0.4); }
}
.metric-cards {
  display: flex;
  gap: 1rem;
  margin: 1rem 0;
}
.anchor-card {
  background: var(--card-bg);
  padding: 1rem;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: transform 0.2s ease;
}
.anchor-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 24px rgba(0,0,0,0.1);
}
.anchor-card .icon {
  font-size: 1.75rem;
  margin-right: .5rem;
}
.stButton>button {
  background: var(--primary)!important;
  color: #fff!important;
  border-radius: var(--radius)!important;
  padding: .5rem 1rem!important;
  transition: transform .1s, background 0.3s;
}
.stButton>button:hover {
  transform: scale(1.03);
  background: #1d4ed8!important;
}
footer {
  text-align: center;
  color: gray;
  margin-top: 2rem;
  font-size: .8rem;
}
::-webkit-scrollbar {
  width: 8px;
}
::-webkit-scrollbar-thumb {
  background-color: #d1d5db;
  border-radius: 8px;
}
</style>""" dark_css = light_css.replace( "--bg: #ffffff", "--bg: #0f172a" ).replace( "--text: #1f2937", "--text: #e2e8f0" ).replace( "--card-bg: #f9fafb", "--card-bg: #1e293b" ).replace( "rgba(0,0,0,0.06)", "rgba(0,0,0,0.25)" ) st.markdown(dark_css if theme == "Dark" else light_css, unsafe_allow_html=True)

── INTRO HERO ────────────────────────────────────────────────────────────────

st.markdown("""

<div class="hero">
  <h1>📊 Dr Didy Forecast</h1>
  <p>Visualize projected price movement with elegance and precision.</p>
</div>
""", unsafe_allow_html=True)── SPARKLINE DEMO SECTION (Preview Only) ─────────────────────────────────────

spark_df = pd.DataFrame({ "Time": ["7:30", "8:00", "8:30", "9:00", "9:30"], "Entry": [6230, 6220, 6205, 6190, 6178], "Exit": [6235, 6240, 6250, 6265, 6280] }) sparkline = alt.Chart(spark_df.melt(id_vars="Time")).mark_line().encode( x=alt.X("Time:N", axis=None), y=alt.Y("value:Q", axis=None), color="variable:N" ).properties(height=50, width=150)

st.markdown("### 📈 Sample Sparkline") st.altair_chart(sparkline, use_container_width=False)

── AI SIDEBAR CHAT BOT (DYNAMIC RESPONSE) ────────────────────────────────────

st.sidebar.markdown("---") st.sidebar.markdown("### 🤖 Ask ForecastBot") user_question = st.sidebar.text_input("Your question:") if user_question: if "highest" in user_question.lower(): max_slope_key = max(st.session_state.slopes, key=st.session_state.slopes.get) st.sidebar.success(f"ForecastBot: The highest slope is {max_slope_key}: {st.session_state.slopes[max_slope_key]:.4f}") elif "lowest" in user_question.lower(): min_slope_key = min(st.session_state.slopes, key=st.session_state.slopes.get) st.sidebar.success(f"ForecastBot: The lowest slope is {min_slope_key}: {st.session_state.slopes[min_slope_key]:.4f}") elif "slope" in user_question.lower(): st.sidebar.info("ForecastBot: A slope represents expected price change per time block based on your anchor.") else: st.sidebar.info("ForecastBot: Sorry, I didn't understand that. Try asking about 'highest slope' or 'slope meaning'.")

── DAILY HIGHLIGHT CARDS (DYNAMIC + TOOLTIP & ICON) ──────────────────────────

def trend_icon(value): return "⬆️" if value > 0 else "⬇️"

def slope_tooltip(value): return f"{value:.4f} per 30-minute block"

max_slope = max(st.session_state.slopes.items(), key=lambda x: x[1]) min_slope = min(st.session_state.slopes.items(), key=lambda x: x[1])

st.markdown("""

<div class="metric-cards">
  <div class="anchor-card" title="{1}">
    <div class="icon">📈 {0}</div>
    <div><div class="title">Highest Slope</div><div class="value">{2} {3}</div></div>
  </div>
  <div class="anchor-card" title="{5}">
    <div class="icon">📉 {4}</div>
    <div><div class="title">Lowest Slope</div><div class="value">{6} {7}</div></div>
  </div>
</div>
""".format(
    max_slope[0], slope_tooltip(max_slope[1]), trend_icon(max_slope[1]), f"{max_slope[1]:.4f}",
    min_slope[0], slope_tooltip(min_slope[1]), trend_icon(min_slope[1]), f"{min_slope[1]:.4f}"
), unsafe_allow_html=True)── STOCK FILTERS ─────────────────────────────────────────────────────────────

st.markdown("### 🔍 Select Stocks to Display") all_stocks = list(st.session_state.slopes.keys()) selected_stocks = st.multiselect("Choose stocks: ", all_stocks, default=all_stocks[:4]) st.write("You selected:", selected_stocks)

── EXPORTABLE PDF (CSV TABLE FOR NOW) ────────────────────────────────────────

st.markdown("### 📄 Export Forecast Data") data = pd.DataFrame(st.session_state.slopes.items(), columns=["Stock", "Slope"]) csv = data.to_csv(index=False).encode("utf-8") st.download_button("Download Slope Data as CSV", csv, "forecast_slopes.csv")

── FOOTER ───────────────────────────────────────────────────────────────────

st.markdown('<footer>© 2025 Dr Didy Forecast • Built with ❤ & Streamlit</footer>', unsafe_allow_html=True)

