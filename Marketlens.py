import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz

# -----------------------------------------------------------------------------
# 1. CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPY DATA",
    page_icon="🔢",
    layout="centered" # Narrow layout for focus
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
    
    /* SENTIMENT HIGHLIGHTS */
    .bullish { color: #3fb950 !important; }
    .bearish { color: #f85149 !important; }
    .neutral { color: #e3b341 !important; }
    
    /* HIDE STREAMLIT ELEMENTS */
    header, footer, #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. DATA ENGINE
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300)
def get_spy_expirations():
    try:
        return yf.Ticker("SPY").options
    except:
        return []

@st.cache_data(ttl=60)
def fetch_spy_totals(date_str):
    try:
        spy = yf.Ticker("SPY")
        
        # 1. Get Spot Price
        hist = spy.history(period="1d")
        price = hist['Close'].iloc[-1] if not hist.empty else 0
        
        # 2. Get Chain
        chain = spy.option_chain(date_str)
        calls = chain.calls
        puts = chain.puts
        
        # 3. Aggregates
        c_vol = calls['volume'].sum()
        p_vol = puts['volume'].sum()
        c_oi = calls['openInterest'].sum()
        p_oi = puts['openInterest'].sum()
        
        return {
            "price": price,
            "implied_spx": price * 10,
            "c_vol": c_vol, "p_vol": p_vol,
            "c_oi": c_oi, "p_oi": p_oi,
            "pcr_vol": p_vol / c_vol if c_vol else 0,
            "pcr_oi": p_oi / c_oi if c_oi else 0
        }
    except:
        return None

# -----------------------------------------------------------------------------
# 3. UI
# -----------------------------------------------------------------------------
def main():
    st.title("SPY OPTION DATA")
    
    # Selector
    exps = get_spy_expirations()
    if not exps:
        st.error("Connection Error: Could not fetch SPY expirations.")
        return
        
    target_date = st.selectbox("EXPIRATION DATE", exps)
    
    if target_date:
        data = fetch_spy_totals(target_date)
        
        if not data:
            st.error("No data found for this date.")
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
            sent = "BEARISH"
            color = "bearish"
        elif pcr < 0.9:
            sent = "BULLISH"
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
                <div style="font-size:0.8rem; color:#888">Intraday Flow</div>
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
            
        st.markdown("### 3. PRICE LEVELS")
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
                <div class="value">{data['implied_spx']:.2f}</div>
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
