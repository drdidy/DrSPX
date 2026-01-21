import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

# -----------------------------------------------------------------------------
# 1. CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPY DATA (POLYGON)",
    page_icon="🕵️",
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
    
    /* METRIC BOXES */
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
    
    /* COLORS */
    .bullish { color: #3fb950 !important; }
    .bearish { color: #f85149 !important; }
    .neutral { color: #e3b341 !important; }
    
    /* HIDE STREAMLIT ELEMENTS */
    header, footer, #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. DATA ENGINE (POLYGON -> SPY)
# -----------------------------------------------------------------------------
TZ_CT = pytz.timezone('US/Central')
API_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"

def get_smart_default_date():
    """Defaults to TOMORROW if market is closed (After 4PM CT)."""
    now = datetime.now(TZ_CT)
    # If it's late, assume we want to plan for the next day
    if now.hour >= 16: 
        d = now.date() + timedelta(days=1)
        while d.weekday() > 4: d += timedelta(days=1) # Skip weekends
        return d
    return now.date()

@st.cache_data(ttl=60)
def fetch_polygon_spy(date_str):
    try:
        # 1. Get Spot Price (SPY)
        r_spot = requests.get(f"https://api.polygon.io/v3/snapshot?ticker.any_of=SPY&apiKey={API_KEY}", timeout=3)
        spot_data = r_spot.json()
        spy_price = spot_data['results'][0]['value'] if 'results' in spot_data else 0

        # 2. Get Option Chain (SPY)
        # Note: SPY options are American style, standard ticker matches underlying
        url = f"https://api.polygon.io/v3/snapshot/options/SPY?expiration_date={date_str}&limit=1000&apiKey={API_KEY}"
        
        results = []
        while url:
            r = requests.get(url, timeout=5)
            data = r.json()
            if 'results' in data:
                results.extend(data['results'])
            url = data.get('next_url')
            if url: url += f"&apiKey={API_KEY}"
            
        if not results:
            return None

        # 3. Calculate Aggregates
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
            "implied_spx": spy_price * 10, # Proxy Calculation
            "c_vol": c_vol, "p_vol": p_vol,
            "c_oi": c_oi, "p_oi": p_oi,
            "pcr_vol": p_vol / c_vol if c_vol else 0,
            "pcr_oi": p_oi / c_oi if c_oi else 0
        }
    except Exception as e:
        return None

# -----------------------------------------------------------------------------
# 3. UI
# -----------------------------------------------------------------------------
def main():
    st.title("SPY OPTION DATA (POLYGON)")
    
    # Date Picker
    default_date = get_smart_default_date()
    target_date = st.date_input("EXPIRATION DATE", default_date)
    
    if target_date:
        date_str = target_date.strftime('%Y-%m-%d')
        
        with st.spinner(f"Fetching SPY Chain for {date_str}..."):
            data = fetch_polygon_spy(date_str)
        
        if not data:
            st.error(f"No SPY data found for {date_str}.")
            return
            
        # SENTIMENT LOGIC (OI)
        pcr = data['pcr_oi']
        if pcr > 1.5:
            sent = "EXTREME BEARISH"
            color = "bearish"
        elif pcr < 0.7:
            sent = "EXTREME BULLISH"
            color = "bullish"
        elif pcr > 1.2:
            sent = "BEARISH SKEW"
            color = "bearish"
        elif pcr < 0.9:
            sent = "BULLISH SKEW"
            color = "bullish"
        else:
            sent = "NEUTRAL"
            color = "neutral"

        # --- THE NUMBERS ---
        st.markdown("### 1. RATIOS & SENTIMENT")
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown(f"""
            <div class="data-box">
                <label>Put/Call Ratio (OI)</label>
                <div class="value {color}">{pcr:.2f}</div>
                <div style="font-size:0.8rem; color:#888">{sent}</div>
            </div>""", unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
            <div class="data-box">
                <label>Put/Call Ratio (Vol)</label>
                <div class="value">{data['pcr_vol']:.2f}</div>
                <div style="font-size:0.8rem; color:#888">Intraday Activity</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("### 2. TOTALS (OPEN INTEREST)")
        c3, c4 = st.columns(2)
        with c3:
            st.markdown(f"""
            <div class="data-box">
                <label>Total Calls</label>
                <div class="value bullish">{int(data['c_oi']):,}</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="data-box">
                <label>Total Puts</label>
                <div class="value bearish">{int(data['p_oi']):,}</div>
            </div>""", unsafe_allow_html=True)
            
        st.markdown("### 3. REFERENCE")
        c5, c6 = st.columns(2)
        with c5:
            st.markdown(f"""
            <div class="data-box">
                <label>SPY Price</label>
                <div class="value">${data['price']:.2f}</div>
            </div>""", unsafe_allow_html=True)
        with c6:
             st.markdown(f"""
            <div class="data-box">
                <label>Implied SPX</label>
                <div class="value">{data['implied_spx']:,.2f}</div>
            </div>""", unsafe_allow_html=True)

        # Raw Table Toggle
        with st.expander("Show Raw Data Table"):
            st.table(pd.DataFrame({
                "Metric": ["Calls (Vol)", "Puts (Vol)", "Calls (OI)", "Puts (OI)"],
                "Value": [
                    f"{int(data['c_vol']):,}", 
                    f"{int(data['p_vol']):,}", 
                    f"{int(data['c_oi']):,}", 
                    f"{int(data['p_oi']):,}"
                ]
            }))

if __name__ == "__main__":
    main()
