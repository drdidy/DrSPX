# ═══════════════════════════════════════════════════════════════════════════════
# SPXW OPTIONS - PUT/CALL RATIO TESTER
# Using Polygon REST API to fetch open interest data
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
import pandas as pd
from datetime import date

st.set_page_config(page_title="SPXW P/C Ratio Tester", page_icon="🔍", layout="wide")

POLYGON_API_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"

st.title("🔍 SPXW Open Interest Put/Call Ratio")

ticker = st.text_input("Underlying Symbol", value="SPXW")
expiration = st.text_input("Expiration (YYYY-MM-DD)", value=date.today().isoformat())

@st.cache_data(ttl=300)
def fetch_options_chain(symbol, expiry):
    url = "https://api.polygon.io/v3/reference/options/contracts"
    params = {
        "underlying_ticker": symbol.upper(),
        "expiration_date": expiry,
        "limit": 1000,
        "apiKey": POLYGON_API_KEY
    }

    all_results = []
    while True:
        r = requests.get(url, params=params).json()
        if "results" not in r:
            return []
        all_results.extend(r["results"])
        if "next_url" in r:
            url = r["next_url"]
            params = {"apiKey": POLYGON_API_KEY}
        else:
            break

    return all_results


@st.cache_data(ttl=300)
def fetch_open_interest(option_ticker):
    url = f"https://api.polygon.io/v2/snapshot/options/{option_ticker}"
    r = requests.get(url, params={"apiKey": POLYGON_API_KEY}).json()
    try:
        return r["results"]["open_interest"]
    except:
        return 0


if st.button("Calculate Put/Call Ratio", type="primary"):

    with st.spinner("Fetching options chain..."):
        chain = fetch_options_chain(ticker, expiration)

    if not chain:
        st.error("No options returned. Check symbol or expiration.")
        st.stop()

    st.info(f"Found {len(chain)} contracts. Fetching open interest...")
    
    rows = []
    progress = st.progress(0)
    
    for i, opt in enumerate(chain):
        oi = fetch_open_interest(opt["ticker"])
        rows.append({
            "Ticker": opt["ticker"],
            "Type": opt["contract_type"],
            "Strike": opt["strike_price"],
            "OpenInterest": oi
        })
        progress.progress((i + 1) / len(chain))

    df = pd.DataFrame(rows)

    total_calls = df[df["Type"] == "call"]["OpenInterest"].sum()
    total_puts = df[df["Type"] == "put"]["OpenInterest"].sum()

    ratio = round(total_puts / total_calls, 4) if total_calls else None

    st.markdown("---")
    st.subheader("📊 Open Interest Summary")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Calls OI", f"{total_calls:,}")
    col2.metric("Total Puts OI", f"{total_puts:,}")
    
    if ratio:
        col3.metric("Put/Call Ratio", f"{ratio:.4f}")
        st.success(f"✅ Put/Call Ratio = {ratio}")
        
        # Determine dominant side
        if total_calls > total_puts:
            st.info("📊 **CALLS DOMINANT** - MMs may push price DOWN to avoid paying calls")
        elif total_puts > total_calls:
            st.warning("📊 **PUTS DOMINANT** - MMs may push price UP to avoid paying puts")
    else:
        st.error("Unable to compute ratio")

    st.markdown("---")
    st.subheader("📋 Options Data")
    st.dataframe(df.sort_values("Strike"), use_container_width=True)
