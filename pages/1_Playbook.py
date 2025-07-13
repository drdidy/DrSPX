import streamlit as st

st.title("📖 Strategy Playbook")

st.markdown("""
### Best-day cheat-sheet  
| Ticker | Ideal trading days | Rationale |
|--------|-------------------|-----------|
| **NVDA 🧠** | **Tue / Thu** | High volatility and option liquidity mid-week |
| **TSLA 🚗** | **Mon / Wed** | Predictable post-weekend gamma squeeze & mid-week momentum |
| **AAPL 🍎** | **Mon / Wed** | Earnings drift & supply-chain news cadence |

---

### Tuesday contract play  
* Look for **two overnight price points** in the options chain that are **$400-$500 apart**.  
* Project Tuesday’s slope using those two points (you’ve automated this in the SPX tab).  

---

### Thursday contract play  
* **If Wednesday’s low premium was already cheap** → expect a **buy-day** (Thursday contract low ≈ Wed low).  
* **If Wednesday stayed pricey** → treat Thursday as a **put-day**; avoid knife-catching long entries.  

---

### Always remember  
* **Exit levels are *never* entry levels** – they exist to cap risk, not start a position.  
* SPX block between **16:00-17:00 is skipped** in projections (platform maintenance).  
* Slopes are adjustable; use *Aggressive / Moderate / Conservative* presets to match risk.  

---

### Preset tips  
* **Aggressive**  → wider negative slopes (capture more move, higher drawdown)  
* **Moderate**    → current default slopes  
* **Conservative**→ half the default slopes, for small-size accounts  

---

_Read this page whenever you’re tempted to deviate from the plan._  Good trades!  
""")