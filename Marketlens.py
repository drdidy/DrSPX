import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import pytz
from datetime import datetime, timedelta, time
import requests

# -----------------------------------------------------------------------------
# 1. CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPX PROPHET | 0DTE SYSTEM",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cinematic Dark Theme CSS
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    /* Headers */
    h1, h2, h3 {
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 300;
        letter-spacing: 2px;
        color: #00ffcc; /* Neon Cyan */
        text-transform: uppercase;
    }
    /* Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        color: #ffffff;
        text-shadow: 0 0 10px rgba(0, 255, 204, 0.5);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 14px;
        color: #888;
    }
    /* Warning/Info Boxes */
    .stAlert {
        background-color: #1a1c24;
        border: 1px solid #333;
    }
    /* Custom Card Style */
    .prophet-card {
        background-color: #161b22;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00ffcc;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. CONSTANTS & UTILS
# -----------------------------------------------------------------------------
SLOPE = 0.48
TZ_CT = pytz.timezone('US/Central')

def get_current_time_ct():
    return datetime.now(TZ_CT)

# Polygon API Helper
def get_polygon_price(ticker, api_key):
    """Fetches real-time snapshot from Polygon."""
    if not api_key:
        return None
    
    # Map friendly names to Polygon tickers
    poly_ticker = f"I:{ticker}" if ticker in ['SPX', 'VIX'] else ticker
    
    url = f"https://api.polygon.io/v3/snapshot?ticker.any_of={poly_ticker}&apiKey={api_key}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if 'results' in data and len(data['results']) > 0:
            return data['results'][0]['value']
    except Exception as e:
        st.error(f"Polygon API Error: {e}")
    return None

# -----------------------------------------------------------------------------
# 3. DATA ENGINE (ES Futures & Channels)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300) # Cache for 5 mins
def fetch_es_data():
    """Fetches 7 days of ES=F 30m data from Yahoo Finance."""
    # ES=F is the source of truth for channel logic
    ticker = "ES=F"
    end_date = datetime.now() + timedelta(days=1) # Ensure we get today
    start_date = end_date - timedelta(days=7)
    
    df = yf.download(ticker, start=start_date, end=end_date, interval="30m", progress=False)
    
    if df.empty:
        return df
        
    # Flatten MultiIndex columns if present (yfinance v0.2.50+ fix)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Convert index to Central Time
    df.index = df.index.tz_convert(TZ_CT)
    return df

def analyze_session(df, analysis_date_str):
    """
    Core Logic: Slices data for Sydney, Tokyo, and Overnight sessions relative to a specific trade date.
    Input: df (index is datetime CT), analysis_date_str (YYYY-MM-DD of the TRADING DAY)
    """
    # Parse target trade date
    trade_date = datetime.strptime(analysis_date_str, "%Y-%m-%d").date()
    
    # Define session windows relative to Trade Date
    # Sydney: Prev Day 17:00 - 22:00
    sydney_start = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(17, 0)))
    sydney_end = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(22, 0)))
    
    # Tokyo: Prev Day 19:00 - Current Day 02:00
    tokyo_start = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=1), time(19, 0)))
    tokyo_end = TZ_CT.localize(datetime.combine(trade_date, time(2, 0)))
    
    # Full Overnight: Prev Day 17:00 - Current Day 08:30
    on_start = sydney_start
    on_end = TZ_CT.localize(datetime.combine(trade_date, time(8, 30)))
    
    # Prior RTH: Prev Day 08:30 - 15:00 (Handle Mondays: use Friday)
    days_back = 3 if trade_date.weekday() == 0 else 1
    prior_rth_start = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=days_back), time(8, 30)))
    prior_rth_end = TZ_CT.localize(datetime.combine(trade_date - timedelta(days=days_back), time(15, 0)))

    # Slice Data
    sydney_df = df[(df.index >= sydney_start) & (df.index < sydney_end)]
    tokyo_df = df[(df.index >= tokyo_start) & (df.index < tokyo_end)]
    on_df = df[(df.index >= on_start) & (df.index < on_end)]
    prior_rth_df = df[(df.index >= prior_rth_start) & (df.index <= prior_rth_end)]

    if on_df.empty:
        return None # Not enough data

    # 1. Determine Channel Type
    sydney_high = sydney_df['High'].max() if not sydney_df.empty else 0
    sydney_low = sydney_df['Low'].min() if not sydney_df.empty else 0
    tokyo_high = tokyo_df['High'].max() if not tokyo_df.empty else 0
    tokyo_low = tokyo_df['Low'].min() if not tokyo_df.empty else 0

    channel_type = "UNKNOWN"
    if tokyo_high > sydney_high and tokyo_low >= sydney_low:
        channel_type = "RISING" # Bullish Slope (not bias)
    elif tokyo_low < sydney_low and tokyo_high <= sydney_high:
        channel_type = "FALLING" # Bearish Slope (not bias)
    elif tokyo_high > sydney_high and tokyo_low < sydney_low:
        channel_type = "EXPANDING" # Balanced / Cone
    elif tokyo_high < sydney_high and tokyo_low > sydney_low:
        channel_type = "CONTRACTING" # NO TRADE
        
    # 2. Get Anchors (Overnight High/Low)
    on_high = on_df['High'].max()
    on_low = on_df['Low'].min()
    on_high_time = on_df['High'].idxmax()
    on_low_time = on_df['Low'].idxmin()

    # 3. Prior RTH Levels (Cone Rails)
    prior_high_wick = prior_rth_df['High'].max() if not prior_rth_df.empty else 0
    prior_low_close = prior_rth_df['Close'].min() if not prior_rth_df.empty else 0
    
    return {
        "type": channel_type,
        "on_high": on_high,
        "on_low": on_low,
        "on_high_time": on_high_time,
        "on_low_time": on_low_time,
        "sydney_range": (sydney_low, sydney_high),
        "tokyo_range": (tokyo_low, tokyo_high),
        "prior_rth": {
            "high_wick": prior_high_wick,
            "low_close": prior_low_close
        },
        "on_df": on_df
    }

# -----------------------------------------------------------------------------
# 4. UI COMPONENTS
# -----------------------------------------------------------------------------

def main():
    # --- Sidebar ---
    st.sidebar.title("🛠️ SYSTEM CONTROLS")
    
    # API Input
    polygon_key = st.sidebar.text_input("Polygon API Key", value="jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm", type="password")
    
    # Date Selection
    today_ct = get_current_time_ct().date()
    selected_date = st.sidebar.date_input("Trade Date", today_ct)
    
    # Inputs
    spx_offset = st.sidebar.number_input("ES-SPX Offset", value=35.0, step=0.5)
    
    # Manual Overrides (Hidden by default)
    with st.sidebar.expander("⚠️ Manual Overrides"):
        manual_override = st.checkbox("Enable Manual Data")
        man_on_high = st.number_input("Manual O/N High", value=0.0)
        man_on_low = st.number_input("Manual O/N Low", value=0.0)

    st.sidebar.markdown("---")
    st.sidebar.info(f"🕒 Central Time: {get_current_time_ct().strftime('%H:%M:%S')}")

    # --- Main Data Fetch ---
    with st.spinner("Analyzing Global Sessions..."):
        raw_df = fetch_es_data()
    
    if raw_df.empty:
        st.error("Could not fetch ES Futures data. Check connection or yfinance.")
        return

    # Filter data for chart (last 2 days for context)
    chart_start_time = TZ_CT.localize(datetime.combine(selected_date - timedelta(days=1), time(6, 0)))
    chart_df = raw_df[raw_df.index >= chart_start_time].copy()
    
    # Analyze Logic
    logic = analyze_session(raw_df, str(selected_date))
    
    # Live VIX/SPX from Polygon
    live_vix = get_polygon_price("VIX", polygon_key)
    live_spx = get_polygon_price("SPX", polygon_key)
    
    if live_vix is None: live_vix = 15.0 # Fallback default
    
    # --- UI HEADER ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("ES Futures (Live)", f"{chart_df['Close'].iloc[-1]:.2f}")
    with col2:
        val = f"{live_spx:.2f}" if live_spx else "Delayed"
        st.metric("SPX Index", val, delta=f"-{spx_offset} Offset")
    with col3:
        st.metric("VIX", f"{live_vix:.2f}")
    with col4:
        if logic:
            ctype = logic['type']
            color = "#00ffcc" if ctype == "RISING" else "#ff00ff" if ctype == "FALLING" else "#ffff00"
            st.markdown(f"<h3 style='color:{color}; text-align:center; border:1px solid {color}; padding: 5px;'>{ctype}</h3>", unsafe_allow_html=True)

    if not logic:
        st.warning("Not enough Overnight data yet to form a channel for this date.")
        st.dataframe(chart_df.tail())
        return

    # --- THE ORACLE (SIGNAL LOGIC) ---
    st.markdown("---")
    
    if logic['type'] == "CONTRACTING":
        st.error("⛔ **CONTRACTING CHANNEL DETECTED - NO TRADE DAY** ⛔")
        st.markdown("The market is compressing (Tokyo inside Sydney). Volatility is likely to be choppy. **Sit on your hands.**")
    else:
        # Calculate Current Levels
        # Just simple projection for display logic (actual chart does full lines)
        current_time = get_current_time_ct()
        mins_since_high = (current_time - logic['on_high_time']).total_seconds() / 60 / 30
        mins_since_low = (current_time - logic['on_low_time']).total_seconds() / 60 / 30
        
        # Display logic based on channel type
        st.markdown(f"### ⚡ TACTICAL BRIEF: {logic['type']} CHANNEL")
        
        col_sig1, col_sig2 = st.columns([2, 1])
        
        with col_sig1:
            if logic['type'] == "RISING":
                st.info("**STRATEGY:** Slope is UP. \n\n* **ABOVE Channel:** Wait for pullback to FLOOR → CALLS.\n* **BELOW Channel:** Wait for rally to FLOOR (Fail) → PUTS.\n* **INSIDE:** Trade the edges.")
            elif logic['type'] == "FALLING":
                st.info("**STRATEGY:** Slope is DOWN. \n\n* **BELOW Channel:** Wait for rally to CEILING → PUTS.\n* **ABOVE Channel:** Wait for drop to CEILING (Fail) → CALLS.\n* **INSIDE:** Trade the edges.")
            elif logic['type'] == "EXPANDING":
                st.warning("**STRATEGY:** BALANCED DAY (Megaphone). \n\n* Trade edges (Ceiling = Puts, Floor = Calls).\n* Expect mean reversion.")
                
        with col_sig2:
             # Option Strikes Calculator
             current_es = chart_df['Close'].iloc[-1]
             est_spx = current_es - spx_offset
             
             call_strike = round((est_spx + 20) / 5) * 5
             put_strike = round((est_spx - 20) / 5) * 5
             
             st.markdown("#### 🎯 0DTE STRIKES")
             st.code(f"CALLS: {call_strike}\nPUTS:  {put_strike}")

    # --- CINEMATIC CHART (PLOTLY) ---
    st.markdown("---")
    
    # Create Figure
    fig = go.Figure()

    # 1. Candlesticks (ES)
    fig.add_trace(go.Candlestick(
        x=chart_df.index,
        open=chart_df['Open'], high=chart_df['High'],
        low=chart_df['Low'], close=chart_df['Close'],
        name="ES Futures",
        increasing_line_color='#00ffcc', increasing_fillcolor='#162b26',
        decreasing_line_color='#ff0055', decreasing_fillcolor='#2b161c'
    ))

    # 2. Channel Drawing Logic
    # We generate points from O/N High/Low forward to end of chart
    
    # Time vector for projection (from earliest anchor to end of chart + 4 hours)
    start_proj = min(logic['on_high_time'], logic['on_low_time'])
    end_proj = chart_df.index[-1] + timedelta(hours=4)
    proj_times = pd.date_range(start=start_proj, end=end_proj, freq="30min")
    
    # Calculate Y values based on channel type
    ceil_vals = []
    floor_vals = []
    
    for t in proj_times:
        # Ceiling Projection
        candles_h = (t - logic['on_high_time']).total_seconds() / 1800 # 30 min periods
        if logic['type'] in ["RISING", "EXPANDING"]:
            ceil_vals.append(logic['on_high'] + (SLOPE * candles_h))
        else: # Falling or Contracting
            ceil_vals.append(logic['on_high'] - (SLOPE * candles_h))
            
        # Floor Projection
        candles_l = (t - logic['on_low_time']).total_seconds() / 1800
        if logic['type'] in ["RISING", "CONTRACTING"]: # Floor slopes UP
            floor_vals.append(logic['on_low'] + (SLOPE * candles_l))
        else: # Floor slopes DOWN
            floor_vals.append(logic['on_low'] - (SLOPE * candles_l))

    # Only Draw Lines if NOT Contracting (User request to hide signals on contracting)
    if logic['type'] != "CONTRACTING":
        # Ceiling Line
        fig.add_trace(go.Scatter(
            x=proj_times, y=ceil_vals, mode='lines',
            name='Channel Ceiling',
            line=dict(color='#00ffcc', width=2, dash='solid')
        ))
        
        # Floor Line
        fig.add_trace(go.Scatter(
            x=proj_times, y=floor_vals, mode='lines',
            name='Channel Floor',
            line=dict(color='#ff00ff', width=2, dash='solid')
        ))
        
        # Cone Rails (Profit Targets) - Derived from Prior RTH
        # Simple projection from Prior High Wick (Ascending) and Low Close (Descending)
        # Just drawing one example set for clarity
        prior_h_vals = [logic['prior_rth']['high_wick'] + (SLOPE * ((t - logic['on_high_time']).total_seconds()/1800)) for t in proj_times]
        fig.add_trace(go.Scatter(x=proj_times, y=prior_h_vals, mode='lines', name='Prior High Rail', line=dict(color='#ffff00', width=1, dash='dot')))

    # 3. Styling the Chart (Cinematic)
    fig.update_layout(
        title=f"ES FUTURES | {logic['type']} CHANNEL",
        title_font_color="#00ffcc",
        height=700,
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117',
        xaxis=dict(
            gridcolor='#333',
            range=[chart_start_time, end_proj], # Default zoom
            rangeslider=dict(visible=False),
            type="date"
        ),
        yaxis=dict(
            gridcolor='#333',
            side='right' # Price on right like trading platforms
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=10, r=10, t=40, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- RAW DATA EXPANDER ---
    with st.expander("查看 Raw Data & Session Details"):
        st.write("Sydney Range:", logic['sydney_range'])
        st.write("Tokyo Range:", logic['tokyo_range'])
        st.write("Overnight High:", logic['on_high'], "at", logic['on_high_time'])
        st.write("Overnight Low:", logic['on_low'], "at", logic['on_low_time'])

if __name__ == "__main__":
    main()
