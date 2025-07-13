import streamlit as st

st.set_page_config(page_title="Playbook", page_icon="📖")
st.title("📖 Strategy Playbook")

st.markdown("""
### Best-day cheat-sheet
| Ticker | Ideal trading days | Rationale |
|--------|-------------------|-----------|
| **NVDA 🧠**  | **Tue / Thu** | Highest volatility and option-flow mid-week |
| **META 📘**  | **Tue / Thu** | News-feed reprice, AI headlines often drop Tue/Thu |
| **TSLA 🚗**  | **Mon / Wed** | Post-weekend gamma squeeze & mid-week momentum |
| **AAPL 🍎**  | **Mon / Wed** | Earnings drift & supply-chain headlines |
| **AMZN 📦**  | **Wed / Thu** | Mid-week marketplace volume & OPEX flow |
| **GOOGL 🔍** | **Thu / Fri** | Search-ad spend updates tilt end-week |
| **NFLX 📺**  | **Tue / Fri** | Subscriber metrics chatter on Tue, positioning unwind on Fri |

---

### Tuesday contract play  
* Identify **two overnight option prints \$400–\$500 apart**.  
* Use them to set the Tuesday contract slope (handled in the SPX tab).

### Thursday contract play  
* If **Wednesday’s low premium was cheap** → Thursday low ≈ Wed low (**buy-day**).  
* If **Wednesday stayed pricey** → Thursday likely a **put-day** (avoid longs).

---

### Golden rules 🔔  
* **Exit levels are exits — never entries.**  
* SPX ignores the full **16 : 00 – 17 : 00** maintenance block.
""")