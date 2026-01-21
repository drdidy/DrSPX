import streamlit as st
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, timedelta
import pytz

# -----------------------------------------------------------------------------
# 1. CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPY DATA | DIAGNOSTIC",
    page_icon="🛠️",
    layout="centered"
)

st.markdown("""
<style>
    /* CLEAN DARK THEME */
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
        font-family: 'Consolas', monospace;
    }
    
    /* DATA BOXES */
    .data-box {
        background: #161b22;
        border: 1px solid #30363d;
        padding: 15px;
        border-radius: 4px;
        text-align: center;
        margin-bottom: 10px;
    }
    .data-box label { display: block; font-size: 0.8rem; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; }
    .data-box .value { font-size: 1.8rem; font-weight: bold; color: #fff; margin-top: 5px; }
    
    /* ALERTS */
    .stAlert { background-color: #161b22; border: 1px solid #30363d; color: #e0e0e0; }
    
    /* COLORS */
    .bullish { color: #3fb950 !important; }
    .bearish { color: #f85149 !important; }
    .neutral { color: #e3b341 !important; }
    
    header, footer, #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# -----------------------------------------------------------------------------
TZ_CT = pytz.timezone('US/Central')

def get_smart_default_date():
    now = datetime.now(TZ_CT)
    if now.hour >= 16: 
        d = now.date() + timedelta(days=1)
        while d.weekday() > 4: d += timedelta(days=1)
        return d
    return now.date()

# -----------------------------------------------------------------------------
# 3. POLYGON ENGINE
# -----------------------------------------------------------------------------
def fetch_polygon_data(api_key, date_str):
    """
    Fetches SPY Snapshot for a specific expiration.
    Returns a dict with data OR a dict with 'error' message.
    """
    try:
        # 1. Spot Price
        r_spot = requests.get(f"https://api.polygon.io/v3/snapshot?ticker.any_of=SPY&apiKey={api_key}", timeout=5)
        if r_spot.status_code != 200:
            return {"error": f"Spot Price Error: {r_spot.status_code} - {r_spot.text}"}
            
        spot_data = r_spot.json()
        if 'results' not in spot_data:
             return {"error": "Spot Price: No results returned."}
        spy_price = spot_data['results'][0]['value']

        # 2. Options Chain
        # Note: We use the limit=250 default and paginate to be safe on all tiers
        url = f"https://api.polygon.io/v3/snapshot/options/SPY?expiration_date={date_str}&limit=250&apiKey={api_key}"
        
        results = []
        page_count = 0
        
        while url:
            r = requests.get(url, timeout=8)
            
            if r.status_code != 200:
                return {"error": f"Chain Error: {r.status_code} - {r.text}"}
                
            data = r.json()
            
            if 'results' in data:
                results.extend(data['results'])
            else:
                # If first page has no results, stop.
                if page_count == 0: break
                
            url = data.get('next_url')
            if url: url += f"&apiKey={api_key}"
            
            page_count += 1
            if page_count > 20: break # Safety break
            
        if not results:
            return {"error": f"No contracts found for {date_str}. (Empty List)"}

        # 3. Calculate
        c_vol, p_vol = 0, 0
        c_oi, p_oi = 0, 0
        
        for c in results:
            details = c.get('details', {})
            stats = c.get('day', {})
            vol = stats.get('volume', 0)
            oi = c.get('open_interest', 0)
            c_type = details.get('contract_type')
            
            if c_type == 'call':
                c_vol += vol
                c_oi += oi
            elif c_type == 'put':
                p_vol += vol
                p_oi += oi

        return {
            "price": spy_price,
            "c_vol": c_vol, "p_vol": p_vol,
            "c_oi": c_oi, "p_oi": p_oi,
            "pcr_vol": p_vol / c_vol if c_vol else 0,
            "pcr_oi": p_oi / c_oi if c_oi else 0
        }
    except Exception as e:
        return {"error": f"Exception: {str(e)}"}

# -----------------------------------------------------------------------------
# 4. YFINANCE ENGINE (FALLBACK)
# -----------------------------------------------------------------------------
def fetch_yahoo_data(date_str):
    try:
        spy = yf.Ticker("SPY")
        
        # Spot
        hist = spy.history(period="1d")
        if hist.empty: return {"error": "Yahoo: Could not get SPY price."}
        price = hist['Close'].iloc[-1]
        
        # Chain
        try:
            chain = spy.option_chain(date_str)
        except ValueError:
            return {"error": f"Yahoo: Data not available for {date_str} (or invalid date)."}
            
        calls, puts = chain.calls, chain.puts
        
        c_vol = calls['volume'].sum()
        p_vol = puts['volume'].sum()
        c_oi = calls['openInterest'].sum()
        p_oi = puts['openInterest'].sum()
        
        return {
            "price": price,
            "c_vol": c_vol, "p_vol": p_vol,
            "c_oi": c_oi, "p_oi": p_oi,
            "pcr_vol": p_vol / c_vol if c_vol else 0,
            "pcr_oi": p_oi / c_oi if c_oi else 0
        }
    except Exception as e:
        return {"error": f"Yahoo Exception: {str(e)}"}

# -----------------------------------------------------------------------------
# 5. UI
# -----------------------------------------------------------------------------
def main():
    st.title("SPY DATA ANALYZER")
    
    # --- CONTROLS ---
    with st.expander("🔌 CONNECTION SETTINGS", expanded=True):
        source = st.radio("Data Source", ["Polygon.io (Paid Key)", "Yahoo Finance (Free)"], horizontal=True)
        
        if "Polygon" in source:
            # Pre-filled with the last key you gave me
            api_key = st.text_input("Polygon API Key", value="6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ", type="password")
            debug_mode = st.checkbox("Show Raw Error Messages (Debug Mode)")
        else:
            api_key = None
            debug_mode = False
            
        default_date = get_smart_default_date()
        target_date = st.date_input("Expiration Date", default_date)

    if not target_date: return

    date_str = target_date.strftime('%Y-%m-%d')
    st.markdown("---")

    # --- FETCH LOGIC ---
    data = None
    
    with st.spinner(f"Fetching data from {source.split(' ')[0]}..."):
        if "Polygon" in source:
            if not api_key:
                st.error("Please enter an API Key.")
                return
            data = fetch_polygon_data(api_key, date_str)
        else:
            data = fetch_yahoo_data(date_str)

    # --- ERROR HANDLING ---
    if data and "error" in data:
        st.error(f"❌ DATA FAILED: {data['error']}")
        if "Polygon" in source and not debug_mode:
            st.info("Tip: Enable 'Debug Mode' above to see the full technical error.")
        if "Polygon" in source:
            st.warning("Try switching to 'Yahoo Finance' above to get data immediately.")
        return

    if not data:
