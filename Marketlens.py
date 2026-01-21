import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta, time
import requests

# -----------------------------------------------------------------------------
# 1. CORE CONFIGURATION & CSS ENGINE
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPX PROPHET | GLASS",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed" # Collapsed for cleaner look
)

# --- THE GLASS UI INJECTOR ---
# This CSS handles the glassmorphism, animations, and custom typography.
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    /* 1. APP BACKGROUND & BASICS */
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgb(0, 0, 0) 0%, rgb(20, 20, 20) 90%);
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }
    
    /* 2. GLASSMORPHISM CARD CLASS */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }

    /* 3. NEON ACCENTS & TEXT */
    .neon-text-cyan {
        color: #00f3ff;
        text-shadow: 0 0 10px rgba(0, 243, 255, 0.5);
    }
    .neon-text-pink {
        color: #ff00ff;
        text-shadow: 0 0 10px rgba(255, 0, 255, 0.5);
    }
    .neon-text-yellow {
        color: #ffd700;
        text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
    }
    
    /* 4. ANIMATIONS */
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(0, 243, 255, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(0, 243, 255, 0); }
        100% { box-shadow: 0 0 0 0 rgba(0, 243, 255, 0); }
    }
    .status-live {
        display: inline-block;
        width: 10px;
        height: 10px;
        background-color: #00f3ff;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse 2s infinite;
    }

    /* 5. TYPOGRAPHY UTILS */
    .stat-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: rgba(255, 255, 255, 0.6);
        margin-bottom: 5px;
    }
    .stat-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #fff;
    }
    .big-signal {
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: -1px;
        line-height: 1;
    }

    /* 6. LOGO CONTAINER */
    .logo-container {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 30px;
    }
    .app-logo {
        font-size: 2rem;
        background: linear-gradient(45deg, #00f3ff, #ff00ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        letter-spacing: 2px;
    }

    /* Hide standard streamlit junk */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. LOGIC ENGINE (Keep calculations robust)
# -----------------------------------------------------------------------------
SLOPE = 0.48
TZ_CT = pytz.timezone('US/Central')

def get_current_time_ct():
    return datetime.now(TZ_CT)

def get_polygon_price(ticker, api_key):
    if not api_key: return None
    poly_ticker = f"I:{ticker}" if ticker in ['SPX', 'VIX'] else ticker
    url = f"https://api.polygon.io/v3/snapshot?ticker.any_of={poly_ticker}&apiKey={api_key}"
    try:
        r = requests.get(url, timeout=3)
        data = r.json()
        if 'results' in data and len(data['results']) > 0:
            return data['results'][0]['value']
    except:
        return None
    return None

@st.cache_data(ttl=300)
def fetch_and_analyze_data(target_date_str):
    ticker = "ES=F"
    end_date = datetime.now() + timedelta(days=1)
    start_date = end_date - timedelta(days=7)
    df = yf.download(ticker, start=start_date, end=end_date, interval="30m", progress=False)
    
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.index = df.index.tz_convert(TZ_CT)

    # Date Parsing
    trade_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    
    # Session Windows
    sydney_start = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(17, 0)))
    sydney_end = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(22, 0)))
    tokyo_start = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(19, 0)))
    tokyo_end = TZ_CT.localize(datetime.combine(trade_date, time(2, 0)))
    on_start = sydney_start
    on_end = TZ_CT.localize(datetime.combine(trade_date, time(8, 30)))
    
    sydney_df = df[(df.index >= sydney_start) & (df.index < sydney_end)]
    tokyo_df = df[(df.index >= tokyo_start) & (df.index < tokyo_end)]
    on_df = df[(df.index >= on_start) & (df.index < on_end)]
    
    if on_df.empty: return {"status": "WAITING_DATA"}

    # Logic
    s_high = sydney_df['High'].max() if not sydney_df.empty else 0
    s_low = sydney_df['Low'].min() if not sydney_df.empty else 0
    t_high = tokyo_df['High'].max() if not tokyo_df.empty else 0
    t_low = tokyo_df['Low'].min() if not tokyo_df.empty else 0
    
    channel_type = "UNKNOWN"
    if t_high > s_high and t_low >= s_low: channel_type = "RISING"
    elif t_low < s_low and t_high <= s_high: channel_type = "FALLING"
    elif t_high > s_high and t_low < s_low: channel_type = "EXPANDING"
    elif t_high < s_high and t_low > s_low: channel_type = "CONTRACTING"

    on_high = on_df['High'].max()
    on_low = on_df['Low'].min()
    on_high_time = on_df['High'].idxmax()
    on_low_time = on_df['Low'].idxmin()

    # Calculate Current Channel Bounds (Projected to NOW)
    now = get_current_time_ct()
    
    # Simple projection logic for display
    # (In a real app, this would need to update every second, here it updates on refresh)
    candles_h = (now - on_high_time).total_seconds() / 1800
    candles_l = (now - on_low_time).total_seconds() / 1800
    
    if channel_type in ["RISING", "EXPANDING"]:
        curr_ceil = on_high + (SLOPE * candles_h)
    else:
        curr_ceil = on_high - (SLOPE * candles_h)
        
    if channel_type in ["RISING", "CONTRACTING"]:
        curr_floor = on_low + (SLOPE * candles_l)
    else:
        curr_floor = on_low - (SLOPE * candles_l)

    return {
        "status": "READY",
        "type": channel_type,
        "ceil": curr_ceil,
        "floor": curr_floor,
        "es_last": df['Close'].iloc[-1]
    }

# -----------------------------------------------------------------------------
# 3. THE UI BUILDER
# -----------------------------------------------------------------------------

def main():
    # Sidebar Controls (Hidden logic, clean UI)
    with st.sidebar:
        st.markdown("### ⚙️ Backend")
        poly_key = st.text_input("Polygon Key", value="jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm", type="password")
        date_sel = st.date_input("Date", get_current_time_ct().date())
        offset = st.number_input("SPX Offset", 35.0)

    # Fetch Data
    data = fetch_and_analyze_data(str(date_sel))
    
    # Get Live Prices
    live_spx = get_polygon_price("SPX", poly_key)
    live_vix = get_polygon_price("VIX", poly_key)
    if not live_spx and data: live_spx = data['es_last'] - offset # Fallback
    
    # --- HEADER SECTION ---
    st.markdown("""
    <div class="logo-container">
        <i class="fa-solid fa-layer-group fa-2x" style="color: #00f3ff;"></i>
        <span class="app-logo">SPX PROPHET <span style="font-size: 1rem; color: #666; font-weight: 300;">v2.0</span></span>
    </div>
    """, unsafe_allow_html=True)

    if not data or data['status'] == "WAITING_DATA":
        st.warning("Awaiting Overnight Data...")
        return

    # --- TOP METRICS ROW (GLASS CARDS) ---
    col1, col2, col3, col4 = st.columns(4)
    
    # 1. LIVE SPX
    with col1:
        st.markdown(f"""
        <div class="glass-card">
            <div class="stat-label"><span class="status-live"></span>Live SPX</div>
            <div class="stat-value">{live_spx:,.2f}</div>
            <div style="font-size: 0.8rem; color: #888; margin-top: 5px;">
                <i class="fa-solid fa-clock"></i> 15m Delayed
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # 2. VIX
    with col2:
        vix_color = "#ff0055" if live_vix and live_vix > 20 else "#00f3ff"
        st.markdown(f"""
        <div class="glass-card">
            <div class="stat-label"><i class="fa-solid fa-radiation"></i> VIX Level</div>
            <div class="stat-value" style="color: {vix_color};">{live_vix:.2f}</div>
             <div style="font-size: 0.8rem; color: #888; margin-top: 5px;">
                Volatility Index
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 3. CHANNEL CEILING
    with col3:
        st.markdown(f"""
        <div class="glass-card" style="border-bottom: 3px solid #ff0055;">
            <div class="stat-label"><i class="fa-solid fa-arrow-up"></i> Ceiling</div>
            <div class="stat-value">{data['ceil']:,.2f}</div>
            <div style="font-size: 0.8rem; color: #ff0055; margin-top: 5px;">
                Resistance / Short Zone
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 4. CHANNEL FLOOR
    with col4:
        st.markdown(f"""
        <div class="glass-card" style="border-bottom: 3px solid #00f3ff;">
            <div class="stat-label"><i class="fa-solid fa-arrow-down"></i> Floor</div>
            <div class="stat-value">{data['floor']:,.2f}</div>
            <div style="font-size: 0.8rem; color: #00f3ff; margin-top: 5px;">
                Support / Long Zone
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- MAIN SIGNAL DISPLAY (HERO SECTION) ---
    
    # Determine Style based on Channel Type
    ctype = data['type']
    
    if ctype == "RISING":
        hero_color = "neon-text-cyan"
        icon = "fa-arrow-trend-up"
        desc = "Market structure is sloping UP. Look for Longs at Floor, Shorts at rejection of Ceiling."
        signal_badge = "BULLISH SLOPE"
    elif ctype == "FALLING":
        hero_color = "neon-text-pink"
        icon = "fa-arrow-trend-down"
        desc = "Market structure is sloping DOWN. Look for Shorts at Ceiling, Longs at rejection of Floor."
        signal_badge = "BEARISH SLOPE"
    elif ctype == "EXPANDING":
        hero_color = "neon-text-yellow"
        icon = "fa-expand-arrows-alt"
        desc = "Balanced Day (Megaphone). Volatility expanding. Fade the edges."
        signal_badge = "BALANCED / EXPANDING"
    else: # Contracting
        hero_color = "text-gray-500"
        icon = "fa-compress-arrows-alt"
        desc = "Market is compressing. NO TRADE ZONE."
        signal_badge = "CONTRACTING / DO NOT TRADE"

    # Strikes Calculation
    call_strike = round(((live_spx if live_spx else 0) + 20) / 5) * 5
    put_strike = round(((live_spx if live_spx else 0) - 20) / 5) * 5

    st.markdown(f"""
    <div class="glass-card" style="text-align: center; padding: 40px;">
        <div style="font-size: 1rem; color: #888; letter-spacing: 3px; margin-bottom: 10px;">TODAY'S STRUCTURE</div>
        <div class="big-signal {hero_color}">
            <i class="fa-solid {icon}"></i> {ctype}
        </div>
        <div style="margin-top: 20px; font-size: 1.2rem; max-width: 600px; margin-left: auto; margin-right: auto; line-height: 1.6;">
            {desc}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- ACTIONABLE INTEL ROW ---
    
    if ctype != "CONTRACTING":
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown(f"""
            <div class="glass-card">
                <h3 style="margin-top:0; color: #00f3ff;"><i class="fa-solid fa-bullseye"></i> TARGET STRIKES (0DTE)</h3>
                <div style="display: flex; justify-content: space-between; margin-top: 20px;">
                    <div style="text-align: center;">
                        <div style="color: #00f3ff; font-size: 0.9rem;">CALLS (OTM)</div>
                        <div style="font-size: 2rem; font-weight: bold;">{call_strike}</div>
                    </div>
                    <div style="border-right: 1px solid rgba(255,255,255,0.1);"></div>
                    <div style="text-align: center;">
                        <div style="color: #ff0055; font-size: 0.9rem;">PUTS (OTM)</div>
                        <div style="font-size: 2rem; font-weight: bold;">{put_strike}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            # Position Logic
            pos_text = "INSIDE CHANNEL"
            pos_color = "#ffd700"
            
            if live_spx > data['ceil']:
                pos_text = "ABOVE CHANNEL (Overbought)"
                pos_color = "#ff0055" # Ready for Puts
            elif live_spx < data['floor']:
                pos_text = "BELOW CHANNEL (Oversold)"
                pos_color = "#00f3ff" # Ready for Calls
                
            st.markdown(f"""
            <div class="glass-card">
                <h3 style="margin-top:0;"><i class="fa-solid fa-map-pin"></i> CURRENT POSITION</h3>
                <div style="font-size: 1.5rem; font-weight: bold; color: {pos_color}; margin-top: 20px; text-transform: uppercase;">
                    {pos_text}
                </div>
                <div style="font-size: 0.9rem; color: #888; margin-top: 10px;">
                    Wait for confirmation candle before entry.
                </div>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
