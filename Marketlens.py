# ═══════════════════════════════════════════════════════════════════════════════
# MASSIVE API - SPXW OPTIONS TESTER
# Using the Massive Python client to fetch 0DTE SPX options data
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
from datetime import date, timedelta
import pandas as pd

st.set_page_config(page_title="Massive SPXW Tester", page_icon="🔍", layout="wide")

st.title("🔍 Massive API - SPXW Options Tester")
st.markdown("Testing SPXW (0DTE SPX Options) data using Massive Python client")

# Your API key
API_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"

# Date selector
test_date = st.date_input("Expiry Date to Test", value=date.today())
exp_str = test_date.isoformat()

st.markdown("---")

if st.button("🚀 Fetch SPXW Options Data", type="primary"):
    
    try:
        from massive import RESTClient
        
        with st.spinner(f"Fetching 0DTE options for SPXW expiring on {exp_str}..."):
            client = RESTClient(API_KEY)
            
            try:
                params = {
                    "expiration_date": exp_str,
                    "limit": 1000  # Get more contracts
                }
                
                options_chain = []
                calls = []
                puts = []
                calls_oi = 0
                puts_oi = 0
                calls_vol = 0
                puts_vol = 0
                
                # Try SPXW first (weekly/0DTE options)
                st.info("Fetching SPXW (weekly/0DTE options)...")
                
                for contract in client.list_snapshot_options_chain("SPXW", params=params):
                    options_chain.append(contract)
                    
                    contract_type = contract.details.contract_type.upper() if contract.details else ""
                    strike = contract.details.strike_price if contract.details else 0
                    oi = contract.day.open_interest if contract.day else 0
                    vol = contract.day.volume if contract.day else 0
                    
                    if contract_type == "CALL":
                        calls.append({
                            "ticker": contract.ticker,
                            "strike": strike,
                            "oi": oi or 0,
                            "volume": vol or 0
                        })
                        calls_oi += (oi or 0)
                        calls_vol += (vol or 0)
                    elif contract_type == "PUT":
                        puts.append({
                            "ticker": contract.ticker,
                            "strike": strike,
                            "oi": oi or 0,
                            "volume": vol or 0
                        })
                        puts_oi += (oi or 0)
                        puts_vol += (vol or 0)
                
                st.success(f"✅ Retrieved {len(options_chain)} contracts!")
                
                # ═══════════════════════════════════════════════════════════════
                # SUMMARY METRICS
                # ═══════════════════════════════════════════════════════════════
                st.markdown("### 📊 Summary")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Contracts", len(options_chain))
                col2.metric("Calls", len(calls))
                col3.metric("Puts", len(puts))
                
                total_oi = calls_oi + puts_oi
                pc_ratio_oi = puts_oi / calls_oi if calls_oi > 0 else 0
                col4.metric("P/C Ratio (OI)", f"{pc_ratio_oi:.2f}")
                
                # ═══════════════════════════════════════════════════════════════
                # OPEN INTEREST
                # ═══════════════════════════════════════════════════════════════
                st.markdown("### 📈 Open Interest")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Calls OI", f"{calls_oi:,}")
                col2.metric("Puts OI", f"{puts_oi:,}")
                col3.metric("Total OI", f"{total_oi:,}")
                
                # Visual bar
                if total_oi > 0:
                    calls_pct = calls_oi / total_oi * 100
                    puts_pct = puts_oi / total_oi * 100
                    
                    st.markdown(f"""
                    <div style="display:flex;height:30px;border-radius:8px;overflow:hidden;margin:10px 0">
                        <div style="background:linear-gradient(90deg,#00d4aa,#00b894);width:{calls_pct}%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:white">
                            CALLS {calls_pct:.1f}%
                        </div>
                        <div style="background:linear-gradient(90deg,#ff4757,#ee3b4d);width:{puts_pct}%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:white">
                            PUTS {puts_pct:.1f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Dominant side
                if calls_oi > puts_oi:
                    st.success(f"📊 **CALLS DOMINANT** - MMs may push price DOWN to avoid paying calls")
                elif puts_oi > calls_oi:
                    st.error(f"📊 **PUTS DOMINANT** - MMs may push price UP to avoid paying puts")
                else:
                    st.info("📊 **NEUTRAL** - No clear dominant side")
                
                # ═══════════════════════════════════════════════════════════════
                # VOLUME
                # ═══════════════════════════════════════════════════════════════
                st.markdown("### 📉 Volume")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Calls Volume", f"{calls_vol:,}")
                col2.metric("Puts Volume", f"{puts_vol:,}")
                pc_ratio_vol = puts_vol / calls_vol if calls_vol > 0 else 0
                col3.metric("P/C Ratio (Vol)", f"{pc_ratio_vol:.2f}")
                
                # ═══════════════════════════════════════════════════════════════
                # TOP STRIKES BY OI
                # ═══════════════════════════════════════════════════════════════
                st.markdown("### 🎯 Top Strikes by Open Interest")
                
                # Aggregate by strike
                strike_data = {}
                for c in calls:
                    strike = c["strike"]
                    if strike not in strike_data:
                        strike_data[strike] = {"calls_oi": 0, "puts_oi": 0, "calls_vol": 0, "puts_vol": 0}
                    strike_data[strike]["calls_oi"] += c["oi"]
                    strike_data[strike]["calls_vol"] += c["volume"]
                
                for p in puts:
                    strike = p["strike"]
                    if strike not in strike_data:
                        strike_data[strike] = {"calls_oi": 0, "puts_oi": 0, "calls_vol": 0, "puts_vol": 0}
                    strike_data[strike]["puts_oi"] += p["oi"]
                    strike_data[strike]["puts_vol"] += p["volume"]
                
                # Sort by total OI
                sorted_strikes = sorted(
                    strike_data.items(),
                    key=lambda x: x[1]["calls_oi"] + x[1]["puts_oi"],
                    reverse=True
                )[:15]
                
                if sorted_strikes:
                    df = pd.DataFrame([
                        {
                            "Strike": k,
                            "Calls OI": v["calls_oi"],
                            "Puts OI": v["puts_oi"],
                            "Total OI": v["calls_oi"] + v["puts_oi"],
                            "Net (C-P)": v["calls_oi"] - v["puts_oi"]
                        }
                        for k, v in sorted_strikes
                    ])
                    st.dataframe(df, use_container_width=True)
                    
                    # Find max pain (strike with highest total OI)
                    max_pain_strike = sorted_strikes[0][0]
                    st.info(f"🎯 **Highest OI Strike (potential magnet):** {max_pain_strike}")
                
                # ═══════════════════════════════════════════════════════════════
                # RAW DATA SAMPLE
                # ═══════════════════════════════════════════════════════════════
                with st.expander("View Raw Contract Data (First 5)"):
                    for i, contract in enumerate(options_chain[:5]):
                        st.write(f"**Contract {i+1}:** {contract.ticker}")
                        st.write(f"  - Strike: {contract.details.strike_price if contract.details else 'N/A'}")
                        st.write(f"  - Type: {contract.details.contract_type if contract.details else 'N/A'}")
                        st.write(f"  - OI: {contract.day.open_interest if contract.day else 'N/A'}")
                        st.write(f"  - Volume: {contract.day.volume if contract.day else 'N/A'}")
                        st.write("---")
                
            finally:
                client.close()
                
    except ImportError:
        st.error("❌ Could not import 'massive' package. Install it with: `pip install massive`")
    except Exception as e:
        st.error(f"❌ Error: {e}")
        import traceback
        st.code(traceback.format_exc())

st.markdown("---")
st.markdown("### 📋 What This Tells Us")
st.markdown("""
- **CALLS DOMINANT** → MMs are short calls → They want price to stay DOWN → May break support
- **PUTS DOMINANT** → MMs are short puts → They want price to stay UP → May break resistance

Share the results and I'll integrate this into SPX Prophet V7!
""")
