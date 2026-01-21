import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import pytz

# -----------------------------------------------------------------------------
# 1. CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPX SKEW | FORWARD LOOK",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* TERMINAL AESTHETIC */
    .stApp {
        background-color: #0a0a0a;
        color: #e0e0e0;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    
    /* METRIC CARDS */
    .skew-card {
        background: #111;
        border: 1px solid #333;
        padding: 20px;
        border-radius: 4px;
        text-align: center;
        margin-bottom: 20px;
    }
    .skew-card h3 { margin: 0; font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 2px; }
    .skew-card .value { font-size: 2.2rem; font-weight: bold; margin: 10px 0; }
    
    /* SENTIMENT COLORS */
    .bullish { color: #00ffcc; text-shadow: 0 0 10px rgba(0, 255, 204, 0.2); }
    .bearish { color: #ff0066; text-shadow: 0 0 10px rgba(255, 0, 102, 0.2); }
    .neutral { color: #ffcc00; }
    
    /* HIDE JUNK */
    header, footer, #MainMenu {visibility: hidden;}
    
    /* DATE PICKER FIX */
    input[type="date"] {
        color: #fff !important; 
        background: #333 !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. DATA ENGINE (ROBUST CALCULATOR)
# -----------------------------------------------------------------------------
TZ_CT = pytz.timezone('US/Central')

def get_current_date():
    return datetime.now(TZ_CT).date()

def get_next_trading_day():
    """Returns the next likely trading day (skips weekends)."""
    d = get_current_date() + timedelta(days=1)
    while d.weekday() > 4: # If Sat/Sun, add day
        d += timedelta(days=1)
    return d

@st.cache_data(ttl=60)
def fetch_option_data(api_key, date_str):
    """
    Fetches the Option Chain for a specific expiration date.
    Calculates PCR from the raw data.
    """
    # 1. Get Spot Price
    try:
        r_spot = requests.get(f"https://api.polygon.io/v3/snapshot?ticker.any_of=I:SPX&apiKey={api_key}", timeout=3)
        spot_data = r_spot.json()
        spx_price = spot_data['results'][0]['value'] if 'results' in spot_data else 0
    except:
        spx_price = 0

    # 2. Get Option Chain (Aggregates)
    # We use the snapshot endpoint because it gives us OI and Vol in one go.
    url = f"https://api.polygon.io/v3/snapshot/options/I:SPX?expiration_date={date_str}&limit=1000&apiKey={api_key}"
    
    results = []
    try:
        while url:
            r = requests.get(url, timeout=5)
            data = r.json()
            if 'results' in data:
                results.extend(data['results'])
            
            # Pagination
            url = data.get('next_url')
            if url: url += f"&apiKey={api_key}"
            
    except Exception as e:
        return None

    if not results:
        return None

    # 3. Process & Calculate
    calls_vol, puts_vol = 0, 0
    calls_oi, puts_oi = 0, 0
    
    df_data = []
    
    for c in results:
        details = c.get('details', {})
        stats = c.get('day', {})
        
        strike = details.get('strike_price')
        c_type = details.get('contract_type')
        
        vol = stats.get('volume', 0)
        oi = c.get('open_interest', 0)
        
        # Accumulate Totals
        if c_type == 'call':
            calls_vol += vol
            calls_oi += oi
        elif c_type == 'put':
            puts_vol += vol
            puts_oi += oi
            
        # Add to DF if it has data
        if vol > 0 or oi > 0:
            df_data.append({
                'strike': strike,
                'type': c_type,
                'volume': vol,
                'oi': oi
            })

    # 4. Return Structured Data
    return {
        "spx_price": spx_price,
        "total_calls_vol": calls_vol,
        "total_puts_vol": puts_vol,
        "total_calls_oi": calls_oi,
        "total_puts_oi": puts_oi,
        "pcr_vol": puts_vol / calls_vol if calls_vol else 0,
        "pcr_oi": puts_oi / calls_oi if calls_oi else 0,
        "df": pd.DataFrame(df_data)
    }

# -----------------------------------------------------------------------------
# 3. UI LOGIC
# -----------------------------------------------------------------------------
def main():
    # --- HEADER & CONTROLS ---
    c_head, c_inputs = st.columns([1, 2])
    
    with c_head:
        st.markdown("## 🔭 SPX SKEW<br><span style='font-size:0.8rem; color:#888'>FORWARD ANALYZER</span>", unsafe_allow_html=True)
        
    with c_inputs:
        k1, k2 = st.columns(2)
        with k1:
            # Default to tomorrow if late at night
            default_date = get_next_trading_day()
            target_date = st.date_input("Select Expiry to Analyze", default_date)
        with k2:
            api_key = st.text_input("API Key", value="jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm", type="password")

    st.markdown("---")

    # --- DATA FETCH ---
    if not api_key: return
    
    date_str = target_date.strftime('%Y-%m-%d')
    
    with st.spinner(f"Pulling Option Chain for {date_str}..."):
        data = fetch_option_data(api_key, date_str)

    if not data:
        st.error(f"❌ No Data Found for {date_str}.")
        st.info("💡 HINT: If analyzing 'Today' after market close, switch date to **TOMORROW** to see the Open Interest for the next session.")
        return

    # --- ANALYSIS DASHBOARD ---
    
    # Check if we are looking at future (Planning) or past (Review)
    is_future = target_date > get_current_date()
    focus_metric = "OI" if is_future else "VOL"
    
    # Determine Sentiment based on PCR (Open Interest is key for planning)
    pcr_val = data['pcr_oi'] if is_future else data['pcr_vol']
    
    bias_text = "NEUTRAL"
    bias_color = "neutral"
    if pcr_val > 1.3:
        bias_text = "BEARISH HEDGING"
        bias_color = "bearish"
        bias_desc = "Market is heavy on Puts (Protection)."
    elif pcr_val < 0.7:
        bias_text = "BULLISH POSITIONING"
        bias_color = "bullish"
        bias_desc = "Market is heavy on Calls (Speculation)."
    else:
        bias_desc = "Put/Call balance is within normal range."

    # --- ROW 1: THE BIG NUMBERS ---
    st.markdown(f"### 📊 ANALYSIS FOR: <span style='color:#fff'>{date_str}</span>", unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.markdown(f"""
        <div class="skew-card">
            <h3>Put/Call Ratio ({focus_metric})</h3>
            <div class="value {bias_color}">{pcr_val:.2f}</div>
            <div style="font-size:0.7rem; color:#888;">{bias_text}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with m2:
        val = data['total_puts_oi'] if is_future else data['total_puts_vol']
        st.markdown(f"""
        <div class="skew-card">
            <h3>Total Puts ({focus_metric})</h3>
            <div class="value bearish">{val:,}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with m3:
        val = data['total_calls_oi'] if is_future else data['total_calls_vol']
        st.markdown(f"""
        <div class="skew-card">
            <h3>Total Calls ({focus_metric})</h3>
            <div class="value bullish">{val:,}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with m4:
        st.markdown(f"""
        <div class="skew-card">
            <h3>SPX Spot Ref</h3>
            <div class="value" style="color:#fff;">{data['spx_price']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown(f"<div style='text-align:center; color:#666; font-size:0.8rem; margin-bottom:20px;'>ℹ️ {bias_desc}</div>", unsafe_allow_html=True)

    # --- ROW 2: VISUALIZATION ---
    
    df = data['df']
    if not df.empty:
        # Focus on "Near the Money" strikes for better visibility
        center = data['spx_price'] if data['spx_price'] > 0 else 4000
        # If price is 0 (weekend), use median strike
        if center == 0: center = df['strike'].median()
            
        range_pts = 100
        mask = (df['strike'] >= center - range_pts) & (df['strike'] <= center + range_pts)
        chart_df = df[mask]
        
        # Decide what to plot
        plot_col = 'oi' if is_future else 'volume'
        plot_title = "OPEN INTEREST (Positioning)" if is_future else "VOLUME (Activity)"
        
        pivot = chart_df.pivot_table(index='strike', columns='type', values=plot_col, aggfunc='sum
