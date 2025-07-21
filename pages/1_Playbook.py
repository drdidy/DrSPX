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

### SPX Anchor Trading Rules

#### RTH Anchor Breaks
* **30-min close below RTH entry anchor**: Price may retrace above anchor line but **will fall below again shortly after**
* **Don't chase the bounce**: prepare for the inevitable breakdown

#### Extended Hours Behavior  
* **Price falls below SPX anchor in extended session**: If price rises back above same anchor then **Use that anchor as buy signal in RTH**
* Extended session weakness followed by recovery = RTH strength setup

#### Monday/Wednesday/Friday Anchor Touch Rule
* **No touch of high, close, or low anchor points** on Mon/Wed/Fri = **Potential sell day later in session**
* **Don't trade TO the anchor**: let the market give you the entry
* **Wait for price action confirmation** rather than anticipating anchor touches

#### Anchor Trading Psychology
* **Patience over precision**: anchors are magnets, not timing signals
* **Failed anchor tests** often lead to explosive moves in opposite direction
* **Extended session anchors** carry forward momentum into RTH

---

### Tuesday contract play  
* Identify **two overnight option low points that rise $400-$500**.  
* Use them to set the Tuesday contract slope (handled in the SPX tab).

### Thursday contract play  
* If **Wednesday's low premium was cheap**: Thursday low ≈ Wed low (**buy-day**).  
* If **Wednesday stayed pricey**: Thursday likely a **put-day** (avoid longs).

---

### Risk Management

#### Position Sizing Rules
* **Never risk more than 2% per trade**: consistency beats home runs
* **Scale into positions**: 1/3 initial, 1/3 on confirmation, 1/3 on momentum
* **Reduce size on Fridays**: weekend risk isn't worth it

#### Stop Loss Strategy
* **Hard stops at -15%** for options (no exceptions)
* **Trailing stops after +25%**: protect profits aggressively
* **Time stops at 3:45 PM**: avoid close volatility unless holding overnight

#### Market Context Awareness
* **VIX above 25**: Reduce position sizes by 50%
* **Major earnings week**: Avoid unrelated tickers (sympathy moves)
* **FOMC/CPI days**: Trade post-announcement only (10:30+ AM)

---

### Advanced Entry Techniques

#### Volume Confirmation
* **Entry volume > 20-day average**: Strong conviction signal
* **Declining volume on bounces**: Fade the move
* **Volume spike + anchor break**: High probability setup

#### Time-Based Patterns
* **9:30-10:00 AM**: Initial range, avoid FOMO entries
* **10:30-11:30 AM**: Institutional flow window, best entries
* **2:00-3:00 PM**: Final push time, momentum plays
* **3:30+ PM**: Scalps only, avoid new positions

#### Multi-Timeframe Alignment
* **5-min + 15-min + 1-hour** all pointing same direction = high conviction
* **Conflicting timeframes** = wait for resolution
* **Daily anchor + intraday setup** = strongest edge

---

### Psychological Rules

#### Emotional Discipline  
* **3 losses in a row**: Step away for 1 hour minimum
* **Big win euphoria**: Reduce next position size by 50%
* **Revenge trading**: Automatic day-end (no exceptions)

#### Daily Routine
* **Pre-market prep**: Review overnight anchors + news
* **Mid-day reset**: 12:00 PM evaluation of P&L and plan
* **Post-market review**: Log what worked/didn't work

#### Performance Tracking
* **Win rate target: 55%+** (more important than individual trade size)
* **Risk/reward minimum: 1:1.5** (risk $100 to make $150+)
* **Weekly P&L cap**: Stop trading after +20% or -10% weekly moves

---

### Golden rules 🔔  
* **Exit levels are exits - never entries.**  
* **SPX ignores the full 16:00 - 17:00 maintenance block.**
* **Anchors are magnets, not timing signals - let price come to you.**
* **The market will give you your entry - don't force it.**
* **Consistency in process trumps perfection in prediction.**
* **When in doubt, stay out - there's always another trade.**
""")