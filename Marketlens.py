# ═══════════════════════════════════════════════════════════════════════════════
# SPY/SPXW OPTIONS - PUT/CALL RATIO TESTER
# Using Polygon REST API to fetch open interest data
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
import pandas as pd
from datetime import date

st.set_page_config(page_title="Options P/C Ratio Tester", page_icon="🔍", layout="wide")

POLYGON_API_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"

st.title("🔍 Options Open Interest Put/Call Ratio")
st.caption("Works with SPY, SPXW, QQQ, etc.")

ticker = st.text_input("Underlying Symbol", value="SPY")
expiration = st.text_input("Expiration (YYYY-MM-DD)", value=date.today().isoformat())

# ═══════════════════════════════════════════════════════════════════════════════
# METHOD 1: Use snapshot endpoint (faster - gets OI in one call)
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def fetch_options_snapshot(symbol, expiry):
    """Fetch options chain with OI using snapshot endpoint"""
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol.upper()}"
    params = {
        "expiration_date": expiry,
        "limit": 250,
        "apiKey": POLYGON_API_KEY
    }
    
    all_results = []
    while True:
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code != 200:
                st.warning(f"Snapshot API returned {r.status_code}")
                break
            data = r.json()
            if "results" not in data:
                break
            all_results.extend(data["results"])
            if "next_url" in data:
                url = data["next_url"]
                params = {"apiKey": POLYGON_API_KEY}
            else:
                break
        except Exception as e:
            st.error(f"Error fetching snapshot: {e}")
            break
    
    return all_results

# ═══════════════════════════════════════════════════════════════════════════════
# METHOD 2: Fallback - fetch contracts then OI individually
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def fetch_options_chain(symbol, expiry):
    """Fetch options contracts list"""
    url = "https://api.polygon.io/v3/reference/options/contracts"
    params = {
        "underlying_ticker": symbol.upper(),
        "expiration_date": expiry,
        "limit": 1000,
        "apiKey": POLYGON_API_KEY
    }

    all_results = []
    while True:
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code != 200:
                break
            data = r.json()
            if "results" not in data:
                return []
            all_results.extend(data["results"])
            if "next_url" in data:
                url = data["next_url"]
                params = {"apiKey": POLYGON_API_KEY}
            else:
                break
        except:
            break

    return all_results


@st.cache_data(ttl=300)
def fetch_open_interest(option_ticker):
    """Fetch OI for a single option contract"""
    url = f"https://api.polygon.io/v3/snapshot/options/{option_ticker}"
    try:
        r = requests.get(url, params={"apiKey": POLYGON_API_KEY}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", {})
            if isinstance(results, dict):
                return results.get("day", {}).get("open_interest", 0) or 0
            elif isinstance(results, list) and len(results) > 0:
                return results[0].get("day", {}).get("open_interest", 0) or 0
        return 0
    except:
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
method = st.radio("Method", ["Snapshot (Faster)", "Individual Contracts (Slower)"], horizontal=True)

if st.button("Calculate Put/Call Ratio", type="primary"):

    if method == "Snapshot (Faster)":
        # ═══════════════════════════════════════════════════════════════════
        # SNAPSHOT METHOD
        # ═══════════════════════════════════════════════════════════════════
        with st.spinner("Fetching options snapshot..."):
            results = fetch_options_snapshot(ticker, expiration)
        
        if not results:
            st.error("No options returned. Check symbol or expiration, or try 'Individual Contracts' method.")
            st.stop()
        
        st.success(f"Found {len(results)} contracts!")
        
        rows = []
        total_calls_oi = 0
        total_puts_oi = 0
        
        for opt in results:
            details = opt.get("details", {})
            day = opt.get("day", {})
            
            contract_type = details.get("contract_type", "").lower()
            strike = details.get("strike_price", 0)
            oi = day.get("open_interest", 0) or 0
            volume = day.get("volume", 0) or 0
            
            rows.append({
                "Ticker": opt.get("ticker", ""),
                "Type": contract_type,
                "Strike": strike,
                "OpenInterest": oi,
                "Volume": volume
            })
            
            if contract_type == "call":
                total_calls_oi += oi
            elif contract_type == "put":
                total_puts_oi += oi
        
        df = pd.DataFrame(rows)
        
    else:
        # ═══════════════════════════════════════════════════════════════════
        # INDIVIDUAL CONTRACTS METHOD
        # ═══════════════════════════════════════════════════════════════════
        with st.spinner("Fetching options chain..."):
            chain = fetch_options_chain(ticker, expiration)

        if not chain:
            st.error("No options returned. Check symbol or expiration.")
            st.stop()

        st.info(f"Found {len(chain)} contracts. Fetching open interest (this may take a while)...")
        
        rows = []
        progress = st.progress(0)
        total_calls_oi = 0
        total_puts_oi = 0
        
        for i, opt in enumerate(chain):
            oi = fetch_open_interest(opt["ticker"])
            contract_type = opt.get("contract_type", "").lower()
            
            rows.append({
                "Ticker": opt["ticker"],
                "Type": contract_type,
                "Strike": opt["strike_price"],
                "OpenInterest": oi
            })
            
            if contract_type == "call":
                total_calls_oi += oi
            elif contract_type == "put":
                total_puts_oi += oi
            
            progress.progress((i + 1) / len(chain))

        df = pd.DataFrame(rows)

    # ═══════════════════════════════════════════════════════════════════════
    # DISPLAY RESULTS
    # ═══════════════════════════════════════════════════════════════════════
    ratio = round(total_puts_oi / total_calls_oi, 4) if total_calls_oi else None

    st.markdown("---")
    st.subheader("📊 Open Interest Summary")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Calls OI", f"{total_calls_oi:,}")
    col2.metric("Total Puts OI", f"{total_puts_oi:,}")
    
    if ratio:
        col3.metric("Put/Call Ratio", f"{ratio:.4f}")
        
        # Visual bar
        total_oi = total_calls_oi + total_puts_oi
        if total_oi > 0:
            calls_pct = total_calls_oi / total_oi * 100
            puts_pct = total_puts_oi / total_oi * 100
            
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
        
        # Determine dominant side
        if total_calls_oi > total_puts_oi:
            st.info("📊 **CALLS DOMINANT** - MMs may push price DOWN to avoid paying calls")
        elif total_puts_oi > total_calls_oi:
            st.warning("📊 **PUTS DOMINANT** - MMs may push price UP to avoid paying puts")
    else:
        st.error("Unable to compute ratio (no calls OI)")

    st.markdown("---")
    st.subheader("📋 Options Data")
    st.dataframe(df.sort_values("Strike"), use_container_width=True)
    
    # Top strikes by OI
    st.subheader("🎯 Top Strikes by OI")
    strike_summary = df.groupby("Strike").agg({"OpenInterest": "sum"}).reset_index()
    strike_summary = strike_summary.sort_values("OpenInterest", ascending=False).head(10)
    st.dataframe(strike_summary, use_container_width=True)
