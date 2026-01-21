import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta, time
import requests

# -----------------------------------------------------------------------------
# 1. VISUAL CORE (CSS ENGINE)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPX PROPHET | ULTIMATE",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- THE "GLASS & NEON" STYLESHEET ---
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* ANIMATED BACKGROUND */
    @keyframes gradient {
        0% {background-position: 0% 50%;}
        50% {background-position: 100% 50%;}
        100% {background-position: 0% 50%;}
    }
    
    .stApp {
        background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #000000);
        background-size: 400% 400%;
        animation: gradient 15s ease infinite;
        font-family: 'Inter', sans-serif;
        color: #fff;
    }

    /* GLASSMORPHISM CARD */
    .glass-panel {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(12.6px);
        -webkit-backdrop-filter: blur(12.6px);
        border: 1px solid rgba(255, 255, 255, 0.09);
        padding: 24px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    
    .glass-panel:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 20px rgba(0, 243, 255, 0.15);
        border: 1px solid rgba(0, 243, 255, 0.3);
    }

    /* NEON TEXT UTILS */
    .neon-blue { color: #00f3ff; text-shadow: 0 0 10px rgba(0, 243, 255, 0.6); }
    .neon-pink { color: #ff00ff; text-shadow: 0 0 10px rgba(255, 0, 255, 0.6); }
    .neon-gold { color: #ffd700; text-shadow: 0 0 10px rgba(255, 215, 0, 0.6); }
    .neon-red { color: #ff3333; text-shadow: 0 0 10px rgba(255, 51, 51, 0.6); }

    /* ANIMATIONS */
    @keyframes pulse-glow {
        0% { box-shadow: 0 0 0 0 rgba(0, 243, 255, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(0, 243, 255, 0); }
        100% { box-shadow: 0 0 0 0 rgba(0, 243, 255, 0); }
    }
    
    .live-indicator {
        width: 12px; height: 12px;
        background: #00f3ff;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: pulse-glow 2s infinite;
    }

    /* METRIC STYLING */
    .hero-metric { font-size: 2.5rem; font-weight: 800; letter-spacing: -1px; margin-top: 5px; }
    .metric-sub { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 2px; color: rgba(255,255,255,0.6); }
    
    /* CUSTOM INPUT STYLING */
    div[data-testid="stExpander"] {
        background: rgba(0,0,0,0.4);
        border: 1px solid #333;
        border-radius: 12px;
    }
    
    /* HIDE DEFAULT STREAMLIT ELEMENTS */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. LOGIC ENGINE (CORRECTED)
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
def fetch_raw_data(ticker="ES=F"):
    end_date = datetime.now() + timedelta(days=1)
    start_date = end_date - timedelta(days=7)
    df = yf.download(ticker, start=start_date, end=end_date, interval="30m", progress=False)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.index = df.index.tz_convert(TZ_CT)
    return df

# -----------------------------------------------------------------------------
# 3. UI LAYOUT
# -----------------------------------------------------------------------------
def main():
    # --- HEADER ---
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 15px;">
            <i class="fa-solid fa-meteor fa-2x neon-blue"></i>
            <div>
                <h1 style="margin:0; font-size: 2.2rem; font-weight: 900; background: -webkit-linear-gradient(#eee, #333); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">SPX PROPHET</h1>
                <div style="font-size: 0.8rem; letter-spacing: 4px; color: #00f3ff; text-shadow: 0 0 5px rgba(0,243,255,0.5);">ULTIMATE EDITION</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        ct_now = get_current_time_ct().strftime('%H:%M:%S')
        st.markdown(f"""
        <div class="glass-panel" style="padding: 10px; text-align: right; margin-bottom: 0;">
            <div style="font-size: 0.7rem; color: #888;">CHICAGO TIME</div>
            <div style="font-size: 1.2rem; font-weight: bold;">{ct_now}</div>
        </div>
        """, unsafe_allow_html=True)

    # --- MISSION CONTROL (EXPANDER) ---
    with st.expander("⚙️ MISSION CONTROL & OVERRIDES", expanded=True):
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
        with col_ctrl1:
            st.markdown("##### 📡 DATA & API")
            poly_key = st.text_input("Polygon Key", value="jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm", type="password")
            trade_mode = st.radio("Mode", ["Live Trading", "Planning Mode"], horizontal=True)
        with col_ctrl2:
            st.markdown("##### 📅 CONFIGURATION")
            selected_date = st.date_input("Trade Date", get_current_time_ct().date())
            spx_offset = st.number_input("ES-SPX Offset", 35.0, step=0.5)
        with col_ctrl3:
            st.markdown("##### ⚠️ MANUAL OVERRIDE SYSTEM")
            enable_override = st.checkbox("ACTIVATE MANUAL INPUTS")
            
        if enable_override:
            st.markdown("---")
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                man_syd_high = st.number_input("Sydney High", 0.0)
                man_syd_low = st.number_input("Sydney Low", 0.0)
            with m2:
                man_tok_high = st.number_input("Tokyo High", 0.0)
                man_tok_low = st.number_input("Tokyo Low", 0.0)
            with m3:
                man_on_high = st.number_input("O/N High", 0.0)
                man_on_low = st.number_input("O/N Low", 0.0)
            with m4:
                man_h_ago = st.number_input("High (Hours Ago)", 4.0)
                man_l_ago = st.number_input("Low (Hours Ago)", 6.0)

    # --- DATA PROCESSING ---
    df = fetch_raw_data()
    
    # Defaults
    channel_type = "WAITING"
    on_high, on_low = 0, 0
    on_high_time, on_low_time = None, None
    syd_h, syd_l, tok_h, tok_l = 0, 0, 0, 0

    # 1. AUTO LOGIC
    if not enable_override and not df.empty:
        trade_date = selected_date
        sydney_start = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(17, 0)))
        sydney_end = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(22, 0)))
        tokyo_start = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(19, 0)))
        tokyo_end = TZ_CT.localize(datetime.combine(trade_date, time(2, 0)))
        on_start = sydney_start
        on_end = TZ_CT.localize(datetime.combine(trade_date, time(8, 30)))
        
        sydney_df = df[(df.index >= sydney_start) & (df.index < sydney_end)]
        tokyo_df = df[(df.index >= tokyo_start) & (df.index < tokyo_end)]
        on_df = df[(df.index >= on_start) & (df.index < on_end)]
        
        if not on_df.empty:
            syd_h = sydney_df['High'].max() if not sydney_df.empty else 0
            syd_l = sydney_df['Low'].min() if not sydney_df.empty else 0
            tok_h = tokyo_df['High'].max() if not tokyo_df.empty else 0
            tok_l = tokyo_df['Low'].min() if not tokyo_df.empty else 0
            on_high = on_df['High'].max()
            on_low = on_df['Low'].min()
            on_high_time = on_df['High'].idxmax()
            on_low_time = on_df['Low'].idxmin()

    # 2. MANUAL LOGIC
    elif enable_override:
        syd_h, syd_l = man_syd_high, man_syd_low
        tok_h, tok_l = man_tok_high, man_tok_low
        on_high, on_low = man_on_high, man_on_low
        now = get_current_time_ct()
        on_high_time = now - timedelta(hours=man_h_ago)
        on_low_time = now - timedelta(hours=man_l_ago)

    # 3. CHANNEL DETERMINATION
    if tok_h > syd_h and tok_l >= syd_l: channel_type = "RISING"
    elif tok_l < syd_l and tok_h <= syd_h: channel_type = "FALLING"
    elif tok_h > syd_h and tok_l < syd_l: channel_type = "EXPANDING"
    elif tok_h < syd_h and tok_l > syd_l: channel_type = "CONTRACTING"
    else: channel_type = "WAITING"

    # --- LIVE DATA GRID ---
    live_spx = get_polygon_price("SPX", poly_key)
    live_vix = get_polygon_price("VIX", poly_key)
    
    # Fallbacks
    if trade_mode == "Planning Mode" or live_spx is None:
        live_spx = on_high - spx_offset if on_high > 0 else 4000
        live_vix = 15.0
        
    # --- LEVEL CALCULATION ---
    spx_ceil, spx_floor = 0.0, 0.0
    if channel_type not in ["WAITING", "CONTRACTING"] and on_high > 0:
        now = get_current_time_ct()
        candles_h = (now - on_high_time).total_seconds() / 1800
        candles_l = (now - on_low_time).total_seconds() / 1800
        
        # Slope Logic
        if channel_type in ["RISING", "EXPANDING"]:
            curr_ceil = on_high + (SLOPE * candles_h)
        else: # FALLING
            curr_ceil = on_high - (SLOPE * candles_h)
            
        if channel_type in ["RISING"]:
            curr_floor = on_low + (SLOPE * candles_l)
        else: # FALLING / EXPANDING
            curr_floor = on_low - (SLOPE * candles_l)
            
        spx_ceil = curr_ceil - spx_offset
        spx_floor = curr_floor - spx_offset

    # --- UI: MAIN METRICS ROW ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="glass-panel">
            <div class="metric-sub"><span class="live-indicator"></span>SPX INDEX</div>
            <div class="hero-metric">{live_spx:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        vix_col = "neon-pink" if live_vix > 20 else "neon-blue"
        st.markdown(f"""
        <div class="glass-panel">
            <div class="metric-sub"><i class="fa-solid fa-wave-square"></i> VIX</div>
            <div class="hero-metric {vix_col}">{live_vix:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="glass-panel" style="border-bottom: 3px solid #ff3333;">
            <div class="metric-sub">RESISTANCE / CEILING</div>
            <div class="hero-metric" style="color: #ff9999;">{spx_ceil:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="glass-panel" style="border-bottom: 3px solid #00f3ff;">
            <div class="metric-sub">SUPPORT / FLOOR</div>
            <div class="hero-metric" style="color: #ccffff;">{spx_floor:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # --- STRATEGIC ANALYSIS ENGINE (THE FIX) ---
    
    st.markdown("### 🧠 ALGORITHMIC ANALYSIS")
    
    if channel_type == "CONTRACTING":
        st.markdown("""
        <div class="glass-panel" style="background: rgba(255, 0, 0, 0.15); border: 1px solid red; text-align: center;">
            <h1 class="neon-red"><i class="fa-solid fa-ban"></i> NO TRADE DETECTED</h1>
            <p style="font-size: 1.2rem;">MARKET IS CONTRACTING (Tokyo Inside Sydney). SIT ON HANDS.</p>
        </div>
        """, unsafe_allow_html=True)
        
    elif channel_type != "WAITING":
        # 1. DETERMINE POSITION RELATIVE TO CHANNEL
        position = "INSIDE"
        pos_color = "neon-gold"
        
        if live_spx > spx_ceil:
            position = "ABOVE"
            pos_color = "neon-red"
        elif live_spx < spx_floor:
            position = "BELOW"
            pos_color = "neon-blue"
            
        # 2. DETERMINE STRATEGY BASED ON (SHAPE + POSITION) [Source: Tables 6.2, 6.3]
        strategy_text = ""
        setup_type = "WAIT"
        
        if channel_type == "RISING":
            # RISING Logic
            if position == "ABOVE":
                setup_type = "CALLS"
                strategy_text = "Wait for Pullback to FLOOR -> Enter CALLS"
            elif position == "BELOW":
                setup_type = "PUTS"
                strategy_text = "Wait for Rally to FLOOR (Must Close Below) -> Enter PUTS"
            else: # INSIDE
                strategy_text = "Wait for price to touch edges. Break Up = Calls. Break Down = Puts."
                
        elif channel_type == "FALLING":
            # FALLING Logic
            if position == "ABOVE":
                setup_type = "CALLS"
                strategy_text = "Wait for Drop to CEILING (Must Close Above) -> Enter CALLS"
            elif position == "BELOW":
                setup_type = "PUTS"
                strategy_text = "Wait for Rally to CEILING -> Enter PUTS"
            else: # INSIDE
                strategy_text = "Wait for price to touch edges."
                
        elif channel_type == "EXPANDING":
            strategy_text = "BALANCED DAY. Trade both edges. Ceiling = Puts. Floor = Calls."

        # DISPLAY LOGIC
        c_an1, c_an2 = st.columns([1, 2])
        
        with c_an1:
            # Channel Shape Card
            st.markdown(f"""
            <div class="glass-panel" style="text-align: center; height: 100%;">
                <div class="metric-sub">CHANNEL SHAPE</div>
                <div style="font-size: 2rem; font-weight: 900; margin: 15px 0;">{channel_type}</div>
                <div class="metric-sub" style="color: #888;">Does NOT determine bias alone</div>
            </div>
            """, unsafe_allow_html=True)
            
        with c_an2:
            # The "Oracle" Card
            st.markdown(f"""
            <div class="glass-panel" style="height: 100%; border-left: 5px solid { '#00f3ff' if setup_type=='CALLS' else '#ff00ff' if setup_type=='PUTS' else '#ffd700' };">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div class="metric-sub">CURRENT POSITION</div>
                        <div class="{pos_color}" style="font-size: 1.5rem; font-weight: bold;">{position} CHANNEL</div>
                    </div>
                    <div style="text-align: right;">
                        <div class="metric-sub">SETUP BIAS</div>
                        <div style="font-size: 1.5rem; font-weight: bold;">{setup_type}</div>
                    </div>
                </div>
                <hr style="border-color: rgba(255,255,255,0.1);">
                <div style="font-size: 1.3rem; line-height: 1.6;">
                    <i class="fa-solid fa-chess-knight"></i> {strategy_text}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        # STRIKES ROW
        st.markdown("### 🎯 0DTE TARGET STRIKES")
        c_st1, c_st2 = st.columns(2)
        
        call_strike = round((live_spx + 20) / 5) * 5
        put_strike = round((live_spx - 20) / 5) * 5
        
        with c_st1:
            st.markdown(f"""
            <div class="glass-panel" style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <div class="metric-sub neon-blue">CALL STRIKE (OTM)</div>
                    <div style="font-size: 0.8rem; color: #888;">Entry Condition: Green Candle Close > Trigger</div>
                </div>
                <div style="font-size: 2.5rem; font-weight: bold;">{call_strike}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with c_st2:
            st.markdown(f"""
            <div class="glass-panel" style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <div class="metric-sub neon-pink">PUT STRIKE (OTM)</div>
                    <div style="font-size: 0.8rem; color: #888;">Entry Condition: Red Candle Close < Trigger</div>
                </div>
                <div style="font-size: 2.5rem; font-weight: bold;">{put_strike}</div>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
