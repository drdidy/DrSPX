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
    page_title="SPX PROPHET | COMMAND",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ADVANCED CSS & ANIMATIONS ---
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* MAIN THEME */
    :root {
        --neon-blue: #00f3ff;
        --neon-pink: #bc13fe;
        --neon-green: #0aff68;
        --bg-dark: #050505;
        --card-bg: #111111;
        --border: #333;
    }
    
    .stApp {
        background-color: var(--bg-dark);
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace; /* Tech font */
    }
    
    /* CUSTOM CARDS */
    .tech-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 20px;
        position: relative;
        overflow: hidden;
        margin-bottom: 20px;
    }
    
    .tech-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 100%; height: 2px;
        background: linear-gradient(90deg, var(--neon-blue), transparent);
    }

    .tech-card:hover {
        border-color: var(--neon-blue);
        box-shadow: 0 0 15px rgba(0, 243, 255, 0.1);
    }

    /* METRICS GRID */
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: -1px;
        color: #fff;
    }
    .metric-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #666;
        letter-spacing: 1px;
        margin-bottom: 5px;
    }
    
    /* OVERRIDE PANEL STYLE */
    .override-panel {
        background: #1a1a1a;
        border-left: 3px solid var(--neon-pink);
        padding: 15px;
        margin-bottom: 20px;
    }

    /* STATUS INDICATORS */
    .status-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 3px;
        font-size: 0.7rem;
        font-weight: bold;
        text-transform: uppercase;
    }
    .status-live { background: rgba(0, 243, 255, 0.1); color: var(--neon-blue); border: 1px solid var(--neon-blue); }
    .status-manual { background: rgba(188, 19, 254, 0.1); color: var(--neon-pink); border: 1px solid var(--neon-pink); }

    /* HIDE STREAMLIT BRANDING */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. LOGIC ENGINE
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
    """Fetches raw data only, logic happens in main for override support."""
    end_date = datetime.now() + timedelta(days=1)
    start_date = end_date - timedelta(days=7)
    df = yf.download(ticker, start=start_date, end=end_date, interval="30m", progress=False)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.index = df.index.tz_convert(TZ_CT)
    return df

# -----------------------------------------------------------------------------
# 3. UI & APP LOGIC
# -----------------------------------------------------------------------------

def main():
    # --- SIDEBAR CONFIGURATION ---
    with st.sidebar:
        st.markdown("### 🔐 SYSTEM ACCESS")
        poly_key = st.text_input("Polygon API Key", value="jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm", type="password")
        
        st.markdown("---")
        st.markdown("### 📅 SESSION PARAMETERS")
        trade_mode = st.radio("Operation Mode", ["Live Trading", "Planning Mode"], horizontal=True)
        selected_date = st.date_input("Target Trade Date", get_current_time_ct().date())
        spx_offset = st.number_input("ES-SPX Offset", value=35.0, step=0.5, help="Standard offset is 34-36 points.")

        st.markdown("---")
        st.markdown("### ⚠️ MANUAL OVERRIDES")
        st.caption("Enable this if feeds fail or for holiday planning.")
        enable_override = st.checkbox("ACTIVATE OVERRIDE SYSTEM")
        
        if enable_override:
            st.error("MANUAL INPUTS ACTIVE")
            man_syd_high = st.number_input("Sydney High", 0.0)
            man_syd_low = st.number_input("Sydney Low", 0.0)
            man_tok_high = st.number_input("Tokyo High", 0.0)
            man_tok_low = st.number_input("Tokyo Low", 0.0)
            man_on_high = st.number_input("Overnight High", 0.0)
            man_on_low = st.number_input("Overnight Low", 0.0)
            
            # Time overrides usually need a full datetime, simplifying to hours ago for UI
            st.caption("Anchor Timing (Hours Ago)")
            man_h_ago = st.number_input("High occurred X hours ago", value=4.0)
            man_l_ago = st.number_input("Low occurred X hours ago", value=6.0)

    # --- MAIN CONTENT ---
    
    # 1. HEADER
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fa-solid fa-microchip fa-2x" style="color: var(--neon-blue);"></i>
            <h1 style="margin:0; font-size: 2.5rem; letter-spacing: -2px;">SPX PROPHET <span style="font-size: 1rem; color: #666;">v3.0</span></h1>
        </div>
        """, unsafe_allow_html=True)
    with col_h2:
        ct_time = get_current_time_ct().strftime('%H:%M:%S')
        st.markdown(f"<div style='text-align:right; font-family: monospace; color: #666;'>CHICAGO TIME<br><span style='color: #fff; font-size: 1.2rem;'>{ct_time}</span></div>", unsafe_allow_html=True)

    st.markdown("---")

    # 2. DATA PROCESSING & OVERRIDE LOGIC
    # Fetch Data
    df = fetch_raw_data()
    
    # Defaults
    channel_type = "WAITING"
    on_high, on_low = 0, 0
    on_high_time, on_low_time = None, None
    syd_h, syd_l, tok_h, tok_l = 0, 0, 0, 0
    
    # If AUTO
    if not enable_override and not df.empty:
        # Session Parsing Logic
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

    # If MANUAL
    elif enable_override:
        syd_h, syd_l = man_syd_high, man_syd_low
        tok_h, tok_l = man_tok_high, man_tok_low
        on_high, on_low = man_on_high, man_on_low
        # Fake times based on input
        now = get_current_time_ct()
        on_high_time = now - timedelta(hours=man_h_ago)
        on_low_time = now - timedelta(hours=man_l_ago)

    # Determine Channel Type
    if tok_h > syd_h and tok_l >= syd_l: channel_type = "RISING"
    elif tok_l < syd_l and tok_h <= syd_h: channel_type = "FALLING"
    elif tok_h > syd_h and tok_l < syd_l: channel_type = "EXPANDING"
    elif tok_h < syd_h and tok_l > syd_l: channel_type = "CONTRACTING"
    else: channel_type = "WAITING"

    # 3. MISSION CONTROL DASHBOARD (Top Row)
    c1, c2, c3, c4 = st.columns(4)
    
    # Get Live Prices
    live_spx = get_polygon_price("SPX", poly_key)
    live_vix = get_polygon_price("VIX", poly_key)
    
    # Fallback for Planning Mode or API Fail
    if trade_mode == "Planning Mode" or live_spx is None:
        live_spx = on_high - spx_offset # Estimate
        live_vix = 15.00
    
    with c1:
        st.markdown(f"""
        <div class="tech-card">
            <div class="metric-label"><i class="fa-solid fa-chart-line"></i> SPX Index</div>
            <div class="metric-value">{live_spx:,.2f}</div>
            <div class="status-badge {'status-live' if not enable_override else 'status-manual'}">
                {('LIVE FEED' if not enable_override else 'MANUAL/EST')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div class="tech-card">
            <div class="metric-label"><i class="fa-solid fa-radiation"></i> VIX</div>
            <div class="metric-value" style="color: {'#ff0055' if live_vix > 20 else '#00f3ff'}">{live_vix:.2f}</div>
            <div style="font-size: 0.7rem; color: #888;">IV Multiplier: {'1.5x' if live_vix < 20 else '2.0x'}</div>
        </div>
        """, unsafe_allow_html=True)

    # Calculate Channel Levels (Projected)
    if channel_type != "WAITING":
        now = get_current_time_ct()
        candles_h = (now - on_high_time).total_seconds() / 1800
        candles_l = (now - on_low_time).total_seconds() / 1800
        
        # Slope Logic
        if channel_type in ["RISING", "EXPANDING"]:
             curr_ceil = on_high + (SLOPE * candles_h)
        else: # Falling/Contracting
             curr_ceil = on_high - (SLOPE * candles_h)
             
        if channel_type in ["RISING", "CONTRACTING"]:
             curr_floor = on_low + (SLOPE * candles_l)
        else:
             curr_floor = on_low - (SLOPE * candles_l)
             
        # Apply Offset for SPX
        spx_ceil = curr_ceil - spx_offset
        spx_floor = curr_floor - spx_offset

        with c3:
            st.markdown(f"""
            <div class="tech-card" style="border-bottom: 2px solid #ff0055;">
                <div class="metric-label">Resistance (Ceiling)</div>
                <div class="metric-value" style="font-size: 1.8rem;">{spx_ceil:,.2f}</div>
                <div style="color: #ff0055; font-size: 0.7rem;">SHORT ZONE</div>
            </div>
            """, unsafe_allow_html=True)
            
        with c4:
            st.markdown(f"""
            <div class="tech-card" style="border-bottom: 2px solid #00f3ff;">
                <div class="metric-label">Support (Floor)</div>
                <div class="metric-value" style="font-size: 1.8rem;">{spx_floor:,.2f}</div>
                <div style="color: #00f3ff; font-size: 0.7rem;">LONG ZONE</div>
            </div>
            """, unsafe_allow_html=True)

    # 4. STRATEGY OUTPUT
    if channel_type == "CONTRACTING":
        st.markdown("""
        <div style="background: rgba(255,0,0,0.1); border: 1px solid red; padding: 30px; text-align: center; border-radius: 10px; margin-top: 20px;">
            <h2 style="color: red; margin:0;"><i class="fa-solid fa-ban"></i> NO TRADE DETECTED</h2>
            <p style="margin-top: 10px;">Market is contracting. Tokyo session is inside Sydney. Low conviction day.</p>
        </div>
        """, unsafe_allow_html=True)
    elif channel_type != "WAITING":
        # Determine Color
        t_color = "var(--neon-blue)"
        if channel_type == "FALLING": t_color = "var(--neon-pink)"
        if channel_type == "EXPANDING": t_color = "#ffd700"
        
        st.markdown(f"""
        <div class="tech-card" style="margin-top: 20px; text-align: center;">
            <div style="font-size: 1rem; color: #666; letter-spacing: 2px;">TODAY'S STRUCTURE</div>
            <div style="font-size: 4rem; font-weight: 900; color: {t_color}; line-height: 1;">{channel_type}</div>
            <div style="margin-top: 15px; font-size: 1.2rem; max-width: 800px; margin-left: auto; margin-right: auto;">
                <i class="fa-solid fa-crosshairs"></i> 
                { "Look for PULLBACKS to Floor (Long)" if channel_type == "RISING" else 
                  "Look for RALLIES to Ceiling (Short)" if channel_type == "FALLING" else 
                  "Trade the EDGES (Fade move)" }
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 5. STRIKE CALCULATOR
        call_strike = round((live_spx + 20) / 5) * 5
        put_strike = round((live_spx - 20) / 5) * 5
        
        c_str1, c_str2 = st.columns(2)
        with c_str1:
            st.markdown(f"""
            <div class="tech-card">
                <div style="color: var(--neon-blue); font-weight: bold;">CALL STRIKE (20pt OTM)</div>
                <div style="font-size: 2.5rem;">{call_strike}</div>
                <div style="font-size: 0.8rem; color: #888;">Entry: Close > Ceiling</div>
            </div>
            """, unsafe_allow_html=True)
        with c_str2:
            st.markdown(f"""
            <div class="tech-card">
                <div style="color: var(--neon-pink); font-weight: bold;">PUT STRIKE (20pt OTM)</div>
                <div style="font-size: 2.5rem;">{put_strike}</div>
                <div style="font-size: 0.8rem; color: #888;">Entry: Close < Floor</div>
            </div>
            """, unsafe_allow_html=True)

    # 6. MANUAL DATA AUDIT (If Override Active)
    if enable_override:
        with st.expander("📝 Data Audit (Manual Mode)"):
            st.json({
                "Sydney High": syd_h,
                "Sydney Low": syd_l,
                "Tokyo High": tok_h,
                "Tokyo Low": tok_l,
                "Calculated Type": channel_type
            })

if __name__ == "__main__":
    main()
