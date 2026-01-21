# ═══════════════════════════════════════════════════════════════════════════════
# POLYGON SPXW OPTIONS API TESTER
# Testing SPXW (0DTE/Weekly SPX Options) data availability
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
import json
from datetime import date, timedelta

st.set_page_config(page_title="SPXW Options Tester", page_icon="🔍", layout="wide")

st.title("🔍 Polygon SPXW Options API Tester")
st.markdown("Testing what **SPXW** (0DTE/Weekly SPX) options data is available")

POLYGON_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"
BASE = "https://api.polygon.io"

# Date selector
test_date = st.date_input("Expiry Date to Test", value=date.today())
exp_str = test_date.strftime("%Y-%m-%d")

st.markdown("---")

if st.button("🚀 Run SPXW Tests", type="primary"):
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 1: SPXW Options Contracts Reference
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 1: SPXW Options Contracts Reference")
    with st.spinner("Testing..."):
        try:
            url = f"{BASE}/v3/reference/options/contracts?underlying_ticker=SPXW&expiration_date={exp_str}&limit=10&apiKey={POLYGON_KEY}"
            r = requests.get(url, timeout=15)
            st.write(f"**URL:** `{url.replace(POLYGON_KEY, 'XXXXX')}`")
            st.write(f"**Status:** {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                st.success(f"✅ Success! Found {data.get('count', 0)} contracts")
                with st.expander("View Response"):
                    st.json(data)
            else:
                st.error(f"❌ Failed: {r.text[:500]}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 2: SPXW Options Snapshot
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 2: SPXW Options Snapshot (Sample)")
    with st.spinner("Testing..."):
        try:
            url = f"{BASE}/v3/snapshot/options/SPXW?expiration_date={exp_str}&limit=10&apiKey={POLYGON_KEY}"
            r = requests.get(url, timeout=15)
            st.write(f"**URL:** `{url.replace(POLYGON_KEY, 'XXXXX')}`")
            st.write(f"**Status:** {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                st.success(f"✅ Success! Found {len(results)} options in sample")
                if results:
                    st.write("**Sample option structure:**")
                    st.json(results[0])
            else:
                st.error(f"❌ Failed: {r.text[:500]}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 3: Full SPXW Chain with OI Calculation
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 3: Full SPXW Chain - Put/Call Open Interest")
    with st.spinner("Fetching full chain (this may take a moment)..."):
        try:
            # May need to paginate - start with no limit
            url = f"{BASE}/v3/snapshot/options/SPXW?expiration_date={exp_str}&apiKey={POLYGON_KEY}"
            r = requests.get(url, timeout=30)
            st.write(f"**URL:** `{url.replace(POLYGON_KEY, 'XXXXX')}`")
            st.write(f"**Status:** {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                
                # Count and sum
                calls = []
                puts = []
                calls_oi = 0
                puts_oi = 0
                calls_vol = 0
                puts_vol = 0
                
                for o in results:
                    details = o.get("details", {})
                    day = o.get("day", {})
                    contract_type = details.get("contract_type", "").upper()
                    oi = day.get("open_interest", 0) or 0
                    vol = day.get("volume", 0) or 0
                    
                    if contract_type == "CALL":
                        calls.append(o)
                        calls_oi += oi
                        calls_vol += vol
                    elif contract_type == "PUT":
                        puts.append(o)
                        puts_oi += oi
                        puts_vol += vol
                
                st.success(f"✅ Success! Fetched {len(results)} options")
                
                # Display metrics
                st.markdown("#### 📊 Summary")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Contracts", len(results))
                col2.metric("Calls", len(calls))
                col3.metric("Puts", len(puts))
                
                total_oi = calls_oi + puts_oi
                if total_oi > 0:
                    pc_ratio = puts_oi / calls_oi if calls_oi > 0 else 999
                    col4.metric("P/C Ratio (OI)", f"{pc_ratio:.2f}")
                
                st.markdown("#### 📈 Open Interest")
                col1, col2, col3 = st.columns(3)
                col1.metric("Calls OI", f"{calls_oi:,}")
                col2.metric("Puts OI", f"{puts_oi:,}")
                col3.metric("Total OI", f"{total_oi:,}")
                
                # Determine dominant side
                if calls_oi > puts_oi:
                    st.info(f"📊 **CALLS DOMINANT** - Calls OI ({calls_oi:,}) > Puts OI ({puts_oi:,})")
                elif puts_oi > calls_oi:
                    st.info(f"📊 **PUTS DOMINANT** - Puts OI ({puts_oi:,}) > Calls OI ({calls_oi:,})")
                else:
                    st.info("📊 **NEUTRAL** - Calls OI = Puts OI")
                
                st.markdown("#### 📉 Volume")
                col1, col2, col3 = st.columns(3)
                col1.metric("Calls Volume", f"{calls_vol:,}")
                col2.metric("Puts Volume", f"{puts_vol:,}")
                col3.metric("P/C Ratio (Vol)", f"{puts_vol/calls_vol:.2f}" if calls_vol > 0 else "N/A")
                
                # Show OI distribution by strike
                st.markdown("#### 🎯 OI by Strike (Top 10)")
                strike_data = {}
                for o in results:
                    details = o.get("details", {})
                    day = o.get("day", {})
                    strike = details.get("strike_price", 0)
                    contract_type = details.get("contract_type", "").upper()
                    oi = day.get("open_interest", 0) or 0
                    
                    if strike not in strike_data:
                        strike_data[strike] = {"calls_oi": 0, "puts_oi": 0}
                    
                    if contract_type == "CALL":
                        strike_data[strike]["calls_oi"] += oi
                    else:
                        strike_data[strike]["puts_oi"] += oi
                
                # Sort by total OI
                sorted_strikes = sorted(strike_data.items(), 
                                       key=lambda x: x[1]["calls_oi"] + x[1]["puts_oi"], 
                                       reverse=True)[:10]
                
                if sorted_strikes:
                    import pandas as pd
                    df = pd.DataFrame([
                        {"Strike": k, "Calls OI": v["calls_oi"], "Puts OI": v["puts_oi"], 
                         "Total OI": v["calls_oi"] + v["puts_oi"]}
                        for k, v in sorted_strikes
                    ])
                    st.dataframe(df, use_container_width=True)
                
                with st.expander("View Sample Call Data"):
                    if calls:
                        st.json(calls[0])
                
                with st.expander("View Sample Put Data"):
                    if puts:
                        st.json(puts[0])
                        
            else:
                st.error(f"❌ Failed: {r.text[:500]}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 4: SPX & VIX Index Values
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 4: SPX & VIX Current Values")
    col1, col2 = st.columns(2)
    
    with col1:
        with st.spinner("Fetching SPX..."):
            try:
                url = f"{BASE}/v3/snapshot?ticker.any_of=I:SPX&apiKey={POLYGON_KEY}"
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    if results:
                        res = results[0]
                        value = res.get("value") or res.get("session", {}).get("close")
                        st.metric("SPX", f"{value:,.2f}" if value else "N/A")
                else:
                    st.error(f"SPX fetch failed: {r.status_code}")
            except Exception as e:
                st.error(f"SPX error: {e}")
    
    with col2:
        with st.spinner("Fetching VIX..."):
            try:
                url = f"{BASE}/v3/snapshot?ticker.any_of=I:VIX&apiKey={POLYGON_KEY}"
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    if results:
                        res = results[0]
                        value = res.get("value") or res.get("session", {}).get("close")
                        st.metric("VIX", f"{value:.2f}" if value else "N/A")
                else:
                    st.error(f"VIX fetch failed: {r.status_code}")
            except Exception as e:
                st.error(f"VIX error: {e}")

st.markdown("---")
st.markdown("### 📋 What I Need to Know")
st.markdown("""
Share screenshots showing:
1. ✅ Whether SPXW data is available
2. ✅ The Open Interest numbers (Calls OI vs Puts OI)
3. ✅ The P/C Ratio
4. ✅ Any error messages

This will help me integrate the P/C ratio into SPX Prophet V7 to identify MM positioning!
""")
