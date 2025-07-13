import streamlit as st import pandas as pd import altair as alt from datetime import datetime, date, time, timedelta from dataclasses import dataclass from typing import List

── PAGE CONFIG ───────────────────────────────────────────────────────────────

st.set_page_config( page_title="Dr Didy Forecast", page_icon="📈", layout="wide" )

── STATE: SLOPES ──────────────────────────────────────────────────────────────

if "slopes" not in st.session_state: st.session_state.slopes = { "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792, "TSLA": -0.1500,     "NVDA": -0.0485,      "AAPL": -0.075, "MSFT": -0.1964,     "AMZN": -0.0782,      "GOOGL": -0.0485, }

── THEME SWITCHER ────────────────────────────────────────────────────────────

theme = st.sidebar.radio("🎨 Theme", ["Light", "Dark"])

light_css = """

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

── INTRO HERO ───────────────────────────────────────────────────────────────

st.markdown("""

<div class="hero">
  <h1>📊 Dr Didy Forecast</h1>
  <p>Visualize projected price movement with elegance and precision.</p>
</div>
""", unsafe_allow_html=True)── APP LOGIC CONTINUES HERE (CHARTS, FILTERS, ETC.) ─────────────────────────

You can continue pasting your main app logic here below this section...

── FOOTER ───────────────────────────────────────────────────────────────────

st.markdown('<footer>© 2025 Dr Didy Forecast • Built with ❤ & Streamlit</footer>', unsafe_allow_html=True)

