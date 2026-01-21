# ═══════════════════════════════════════════════════════════════════════════════
# POLYGON OPTIONS API TESTER
# Simple app to test what SPX options data is available
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
import json
from datetime import date, timedelta

st.set_page_config(page_title="Polygon Options Tester", page_icon="🔍", layout="wide")

st.title("🔍 Polygon Options API Tester")
st.markdown("Testing what SPX options data is available from your Polygon subscription")

POLYGON_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"
BASE = "https://api.polygon.io"

# Date selector
test_date = st.date_input("Expiry Date to Test", value=date.today())
exp_str = test_date.strftime("%Y-%m-%d")

st.markdown("---")

if st.button("🚀 Run All Tests", type="primary"):
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 1: Options Contracts Reference (SPX)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 1: Options Contracts Reference (SPX)")
    with st.spinner("Testing..."):
        try:
            url = f"{BASE}/v3/reference/options/contracts?underlying_ticker=SPX&expiration_date={exp_str}&limit=10&apiKey={POLYGON_KEY}"
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
    # TEST 2: Options Snapshot (SPX)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 2: Options Snapshot (SPX)")
    with st.spinner("Testing..."):
        try:
            url = f"{BASE}/v3/snapshot/options/SPX?expiration_date={exp_str}&limit=10&apiKey={POLYGON_KEY}"
            r = requests.get(url, timeout=15)
            st.write(f"**URL:** `{url.replace(POLYGON_KEY, 'XXXXX')}`")
            st.write(f"**Status:** {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                st.success(f"✅ Success! Found {len(results)} options")
                if results:
                    st.write("**Sample option data:**")
                    st.json(results[0])
                with st.expander("View Full Response"):
                    st.json(data)
            else:
                st.error(f"❌ Failed: {r.text[:500]}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 3: Options Snapshot (SPXW - Weeklies)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 3: Options Snapshot (SPXW - Weeklies)")
    with st.spinner("Testing..."):
        try:
            url = f"{BASE}/v3/snapshot/options/SPXW?expiration_date={exp_str}&limit=10&apiKey={POLYGON_KEY}"
            r = requests.get(url, timeout=15)
            st.write(f"**URL:** `{url.replace(POLYGON_KEY, 'XXXXX')}`")
            st.write(f"**Status:** {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                st.success(f"✅ Success! Found {len(results)} options")
                if results:
                    st.write("**Sample option data:**")
                    st.json(results[0])
                with st.expander("View Full Response"):
                    st.json(data)
            else:
                st.error(f"❌ Failed: {r.text[:500]}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 4: Options Chain (All strikes for expiry)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 4: Full Options Chain (SPX)")
    with st.spinner("Testing (this may take a moment)..."):
        try:
            url = f"{BASE}/v3/snapshot/options/SPX?expiration_date={exp_str}&apiKey={POLYGON_KEY}"
            r = requests.get(url, timeout=30)
            st.write(f"**URL:** `{url.replace(POLYGON_KEY, 'XXXXX')}`")
            st.write(f"**Status:** {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                
                # Count calls vs puts
                calls = [o for o in results if o.get("details", {}).get("contract_type", "").upper() == "CALL"]
                puts = [o for o in results if o.get("details", {}).get("contract_type", "").upper() == "PUT"]
                
                # Sum open interest
                calls_oi = sum(o.get("day", {}).get("open_interest", 0) or 0 for o in calls)
                puts_oi = sum(o.get("day", {}).get("open_interest", 0) or 0 for o in puts)
                
                st.success(f"✅ Success!")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Contracts", len(results))
                col2.metric("Calls", len(calls))
                col3.metric("Puts", len(puts))
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Calls OI", f"{calls_oi:,}")
                col2.metric("Puts OI", f"{puts_oi:,}")
                col3.metric("P/C Ratio", f"{puts_oi/calls_oi:.2f}" if calls_oi > 0 else "N/A")
                
                with st.expander("View Sample Data"):
                    if calls:
                        st.write("**Sample CALL:**")
                        st.json(calls[0])
                    if puts:
                        st.write("**Sample PUT:**")
                        st.json(puts[0])
            else:
                st.error(f"❌ Failed: {r.text[:500]}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 5: Index Ticker (I:SPX)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 5: Index Snapshot (I:SPX)")
    with st.spinner("Testing..."):
        try:
            url = f"{BASE}/v3/snapshot?ticker.any_of=I:SPX&apiKey={POLYGON_KEY}"
            r = requests.get(url, timeout=15)
            st.write(f"**URL:** `{url.replace(POLYGON_KEY, 'XXXXX')}`")
            st.write(f"**Status:** {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                st.success(f"✅ Success!")
                results = data.get("results", [])
                if results:
                    res = results[0]
                    value = res.get("value") or res.get("session", {}).get("close")
                    st.metric("SPX Value", f"{value:,.2f}" if value else "N/A")
                with st.expander("View Response"):
                    st.json(data)
            else:
                st.error(f"❌ Failed: {r.text[:500]}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 6: VIX Snapshot
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### Test 6: VIX Snapshot (I:VIX)")
    with st.spinner("Testing..."):
        try:
            url = f"{BASE}/v3/snapshot?ticker.any_of=I:VIX&apiKey={POLYGON_KEY}"
            r = requests.get(url, timeout=15)
            st.write(f"**URL:** `{url.replace(POLYGON_KEY, 'XXXXX')}`")
            st.write(f"**Status:** {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                st.success(f"✅ Success!")
                results = data.get("results", [])
                if results:
                    res = results[0]
                    value = res.get("value") or res.get("session", {}).get("close")
                    st.metric("VIX Value", f"{value:.2f}" if value else "N/A")
                with st.expander("View Response"):
                    st.json(data)
            else:
                st.error(f"❌ Failed: {r.text[:500]}")
        except Exception as e:
            st.error(f"❌ Error: {e}")

st.markdown("---")
st.markdown("### 📋 Summary")
st.markdown("""
After running the tests, share the results with me and I'll know:
1. Whether your Polygon plan includes SPX options data
2. What format the data comes in (open interest, volume, greeks, etc.)
3. How to best integrate it into SPX Prophet V7
""")
