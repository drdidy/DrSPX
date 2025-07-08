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

# --- LIGHT & DARK CSS ---
LIGHT_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
<style>
/* Animated gradient background */
@keyframes bgMove {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
body {
  background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
  background-size: 400% 400%;
  animation: bgMove 15s ease infinite;
  font-family: 'Poppins', sans-serif;
  margin: 0;
}
/* Sticky header & sidebar */
.app-banner { position: sticky; top: 0; z-index: 1000; }
.sidebar .sidebar-content { position: sticky; top: 0; overflow: auto; height: 100vh; }
/* Neumorphic cards */
.card {
  background: #e0e5ec;
  margin: 1rem 2rem; padding: 1rem; border-radius: 1rem;
  box-shadow: -6px -6px 16px #fff, 6px 6px 16px rgba(0,0,0,0.1);
  transition: transform .2s, box-shadow .2s;
}
.card:hover {
  transform: translateY(-4px);
  box-shadow: -8px -8px 24px #fff, 8px 8px 24px rgba(0,0,0,0.15);
}
.card-high { border-left: 8px solid #ff6b6b; }
.card-close{ border-left: 8px solid #4ecdc4; }
.card-low  { border-left: 8px solid #f7b731; }
/* Tabs & header text */
.app-banner h1, .app-banner p, .tab-header { color: #333; }
.tab-header {
  margin: 1.5rem 2rem 0.5rem; font-size: 1.3rem; font-weight: 600;
}
/* Buttons */
.stButton>button {
  background: #e0e5ec; color: #333; border: none;
  box-shadow: -4px -4px 12px #fff, 4px 4px 12px rgba(0,0,0,0.1);
  border-radius: .75rem; padding: .6rem 1.2rem;
  transition: transform .1s, box-shadow .1s;
}
.stButton>button:hover {
  transform: translateY(-2px);
  box-shadow: -6px -6px 16px #fff, 6px 6px 16px rgba(0,0,0,0.15);
}
.stButton>button:active {
  transform: scale(.98);
  box-shadow: -2px -2px 6px #fff, 2px 2px 6px rgba(0,0,0,0.1);
}
/* Footer */
.footer {
  position: fixed; bottom: 0; width: 100%; text-align: center;
  padding: .5rem; font-size: .8rem; color: rgba(0,0,0,0.5);
}
/* Responsive */
@media(max-width:768px) {
  .card { margin: 1rem; }
  .tab-header { margin: 1rem; font-size: 1.1rem; }
}
</style>
"""

DARK_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
<style>
@keyframes bgMove {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
body {
  background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
  background-size: 400% 400%;
  animation: bgMove 15s ease infinite;
  font-family: 'Poppins', sans-serif;
  margin: 0; color: #e0e0e0;
}
.app-banner { position: sticky; top: 0; z-index: 1000; }
.sidebar .sidebar-content { position: sticky; top: 0; overflow: auto; height: 100vh; }
.card {
  background: #2b2f36; margin: 1rem 2rem; padding: 1rem; border-radius: 1rem;
  box-shadow: inset 4px 4px 12px rgba(0,0,0,0.6), -4px -4px 12px rgba(255,255,255,0.05);
  transition: transform .2s, box-shadow .2s;
}
.card:hover {
  transform: translateY(-4px);
  box-shadow: inset 6px 6px 16px rgba(0,0,0,0.7), -6px -6px 16px rgba(255,255,255,0.1);
}
.card-high { border-left: 8px solid #e74c3c; }
.card-close{ border-left: 8px solid #1abc9c; }
.card-low  { border-left: 8px solid #f1c40f; }
.app-banner h1, .app-banner p, .tab-header { color: #e0e0e0; }
.tab-header {
  margin: 1.5rem 2rem 0.5rem; font-size: 1.3rem; font-weight: 600;
}
.stButton>button {
  background: #2b2f36; color: #e0e0e0; border: none;
  box-shadow: inset 2px 2px 6px rgba(0,0,0,0.6), -2px -2px 6px rgba(255,255,255,0.1);
  border-radius: .75rem; padding: .6rem 1.2rem;
  transition: transform .1s, box-shadow .1s;
}
.stButton>button:hover {
  transform: translateY(-2px);
  box-shadow: inset 4px 4px 12px rgba(0,0,0,0.7), -4px -4px 12px rgba(255,255,255,0.15);
}
.stButton>button:active {
  transform: scale(.98);
  box-shadow: inset 1px 1px 4px rgba(0,0,0,0.6), -1px -1px 4px rgba(255,255,255,0.1);
}
.footer {
  position: fixed; bottom: 0; width: 100%; text-align: center;
  padding: .5rem; font-size: .8rem; color: rgba(255,255,255,0.5);
}
@media(max-width:768px) {
  .card { margin: 1rem; }
  .tab-header { margin: 1rem; font-size: 1.1rem; }
}
</style>
"""

# --- PAGE CONFIG & THEME ---
st.set_page_config(page_title="Dr Didy Forecast", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
mode = st.sidebar.radio("🎨 Theme", ["Light Mode", "Dark Mode"])
st.markdown(LIGHT_CSS if mode == "Light Mode" else DARK_CSS, unsa
