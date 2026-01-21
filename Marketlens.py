import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import pytz

# -----------------------------------------------------------------------------
# 1. VISUAL ENGINE
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPX SKEW | TIME MACHINE",
    page_icon="⏳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* CORE THEME */
    .stApp {
        background-color: #050505;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* GLASS PANELS */
    .glass-metric {
        background: rgba(20, 20, 20, 0.6);
        border: 1px solid #333;
        border-radius: 8px;
        padding: 20px;
        backdrop-filter: blur(10px);
        margin-bottom: 15px;
    }
    
    /* COLORS */
    .bullish { color: #00f3ff; text-shadow: 0 0 10px rgba(0, 243, 255, 0.4); }
    .bearish { color: #ff0055; text-shadow: 0 0 10px rgba(255, 0, 85, 0.4); }
    .neutral { color: #ffd700; }
    
    /* METRICS */
    .metric-value { font-size: 2.5rem; font-weight: 800; letter-spacing: -1px; margin-top: 5px; }
    .metric-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 2px; color: #888; }
    
    /* HIDE DEFAULT STREAMLIT UI */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. DATA ENGINE
# -----------------------------------------------------------------------------
TZ_CT = pytz.timezone('US/Central')

def get_current_date():
    return datetime.now(TZ_CT).date()

@st.cache_data(ttl=60)
def fetch_live_skew(api_key, date_str):
    """
    Fetches REAL-TIME Snapshot for TODAY.
    Includes Volume AND Open Interest.
    """
    url = f"https://api.polygon.io/v3/snapshot/options/I:SPX?expiration_date={date_str}&limit=1000&apiKey={api_key}"
    
    results = []
    try:
        while url:
            r = requests.get(url, timeout=5)
            data = r.json()
            if 'results' in data:
                results.extend(data['results'])
            url = data.get('next_url')
            if url: url += f"&apiKey={api_key}"
    except Exception as e:
        return None
        
    if not results: return None
    
    # Process Live Data
    calls_vol, puts_vol = 0, 0
    calls_oi, puts_oi = 0, 0
    strike_data = []
    
    for c in results:
        details = c.get('details', {})
        stats = c.get('day', {})
        
        vol = stats.get('volume', 0)
        oi = c.get('open_interest', 0)
        strike = details.get('strike_price')
        ctype = details.get('contract_type')
        
        if vol > 0 or oi > 0:
            if ctype == 'call':
                calls_vol += vol
                calls_oi += oi
            else:
                puts_vol += vol
                puts_oi += oi
                
            strike_data.append({'strike': strike, 'type': ctype, 'volume': vol})
            
    return {
        "mode": "LIVE SNAPSHOT",
        "pcr_vol": puts_vol / calls_vol if calls_vol else 0,
        "pcr_oi": puts_oi / calls_oi if calls_oi else 0,
        "total_call_vol": calls_vol,
        "total_put_vol": puts_vol,
        "df": pd.DataFrame(strike_data)
    }

@st.cache_data(ttl=300)
def fetch_historical_skew(api_key, date_obj):
    """
    Fetches HISTORICAL End-of-Day Volume for a specific date.
    Uses 'Grouped Daily' endpoint to get actual trade volumes.
    """
    date_str = date_obj.strftime('%Y-%m-%d')
    short_date = date_obj.strftime('%y%m%d') # For ticker parsing (e.g., 231027)
    
    # 1. Get Grouped Daily for ALL Options (This is a large payload, but necessary for history)
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/options/{date_str}?adjusted=true&apiKey={api_key}"
    
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
    except:
        return None

    if 'results' not in data:
        return None
        
    # 2. Filter for SPXW 0DTEs locally
    # Ticker format: O:SPXW250120C04200000
    # Logic: Must contain 'SPX' and the specific date string
    
    calls_vol, puts_vol = 0, 0
    strike_data = []
    
    # Target identifiers
    target_date_str = short_date 
    
    for row in data['results']:
        ticker = row.get('T', '')
        
        # Strict Filter: Must be SPX/SPXW and expire on Selected Date
        if ('SPX' in ticker) and (target_date_str in ticker):
            
            # Parse Contract Details from Ticker String
            # Example: O:SPXW231027C04200000
            try:
                # Find C or P
                type_char = 'C' if f"{target_date_str}C" in ticker else 'P' if f"{target_date_str}P" in ticker else None
                if not type_char: continue
                
                # Extract Strike (Last 8 chars / 1000)
                strike_str = ticker[-8:]
                strike = float(strike_str) / 1000
                
                vol = row.get('v', 0)
                
                if vol > 0:
                    if type_char == 'C':
                        calls_vol += vol
                    else:
                        puts_vol += vol
                    
                    strike_data.append({'strike': strike, 'type': 'call' if type_char=='C' else 'put', 'volume': vol})
            except:
                continue

    if calls_vol == 0 and puts_vol == 0:
        return None

    return {
        "mode": "HISTORICAL EOD",
        "pcr_vol": puts_vol / calls_vol if calls_vol else 0,
        "pcr_oi": None, # OI not available in Grouped Daily
        "total_call_vol": calls_vol,
        "total_put_vol": puts_vol,
        "df": pd.DataFrame(strike_data)
    }

def get_spx_close(api_key, date_str):
    """Gets SPX price for context."""
    url = f"https://api.polygon.io/v1/open-close/I:SPX/{date_str}?adjusted=true&apiKey={api_key}"
    try:
        r = requests.get(url)
        data = r.json()
        return data.get('close', 0)
    except:
        return 0

# -----------------------------------------------------------------------------
# 3. UI LAYOUT
# -----------------------------------------------------------------------------
def main():
    # --- CONTROLS ---
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.markdown("## <i class='fa-solid fa-clock-rotate-left'></i> SPX SKEW <span style='color:#555;'>TIME MACHINE</span>", unsafe_allow_html=True)
    with c2:
        api_key = st.text_input("Polygon API Key", value="jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm", type="password")
    with c3:
        target_date = st.date_input("Select Analysis Date", get_current_date())

    if not api_key: return

    # --- LOGIC BRANCH ---
    today = get_current_date()
    
    if target_date > today:
        st.error("🔮 We cannot predict the future (yet). Select today or a past date.")
        return
        
    date_str = target_date.strftime('%Y-%m-%d')
    spx_price = get_spx_close(api_key, date_str)
    
    with st.spinner(f"Retrieving actual options data for {date_str}..."):
        if target_date == today:
            data = fetch_live_skew(api_key, date_str)
        else:
            data = fetch_historical_skew(api_key, target_date)

    if not data:
        st.warning(f"No SPX options data found for {date_str}. (Market Closed?)")
        return

    # --- DASHBOARD ---
    st.markdown(f"### 📅 REPORT FOR: <span style='color:#fff'>{date_str}</span> <span style='font-size:0.8rem; color:#888'>({data['mode']})</span>", unsafe_allow_html=True)

    # PCR Logic
    pcr = data['pcr_vol']
    if pcr > 1.2:
        sent_color, sent_text = "bearish", "BEARISH SKEW"
    elif pcr < 0.7:
        sent_color, sent_text = "bullish", "BULLISH SKEW"
    else:
        sent_color, sent_text = "neutral", "NEUTRAL FLOW"

    # METRICS ROW
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class="glass-metric">
            <div class="metric-label">Put/Call Ratio (Vol)</div>
            <div class="metric-value {sent_color}">{pcr:.2f}</div>
            <div style="font-size:0.8rem; margin-top:5px;">{sent_text}</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="glass-metric">
            <div class="metric-label">Total Put Vol</div>
            <div class="metric-value bearish">{data['total_put_vol']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="glass-metric">
            <div class="metric-label">Total Call Vol</div>
            <div class="metric-value bullish">{data['total_call_vol']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="glass-metric">
            <div class="metric-label">SPX Price</div>
            <div class="metric-value" style="color:#fff">{spx_price:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # --- CHARTING ---
    st.markdown("### 📊 VOLUMETRIC SKEW")
    
    df = data['df']
    if not df.empty:
        # Smart Zoom: Show range around the closing price
        center_price = spx_price if spx_price > 0 else 4000
        min_s = center_price - 75
        max_s = center_price + 75
        
        mask = (df['strike'] >= min_s) & (df['strike'] <= max_s)
        chart_df = df[mask]
        
        pivot = chart_df.pivot_table(index='strike', columns='type', values='volume', aggfunc='sum').fillna(0)
        
        fig = go.Figure()
        if 'call' in pivot.columns:
            fig.add_trace(go.Bar(x=pivot.index, y=pivot['call'], name='CALLS', marker_color='#00f3ff'))
        if 'put' in pivot.columns:
            fig.add_trace(go.Bar(x=pivot.index, y=pivot['put'], name='PUTS', marker_color='#ff0055'))

        fig.update_layout(
            title=f"Volume Distribution ({date_str})",
            title_font_color="#888",
            xaxis_title="Strike Price",
            yaxis_title="Volume",
            barmode='group',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#e0e0e0"),
            xaxis=dict(gridcolor='#222'),
            yaxis=dict(gridcolor='#222'),
            height=500,
            bargap=0.1
        )
        if spx_price > 0:
            fig.add_vline(x=spx_price, line_width=2, line_dash="dash", line_color="white", annotation_text="CLOSE")

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No volume data in the visible strike range.")

if __name__ == "__main__":
    main()
