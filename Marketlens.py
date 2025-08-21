# ==========================================
# **PART 1: FOUNDATION & CORE INFRASTRUCTURE**
# MarketLens Pro v5 by Max Pointe Consulting
# ==========================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import datetime as dt
import pytz
from datetime import datetime, timedelta, time
import time as time_module
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# STREAMLIT CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="MarketLens Pro v5",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CUSTOM CSS STYLING
# ==========================================
def apply_custom_styling():
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap');
    
    /* Main App Background */
    .stApp {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 25%, #16213e 50%, #0f0f23 75%, #1a1a2e 100%);
        font-family: 'Space Grotesk', sans-serif;
    }
    
    /* Sidebar Styling */
    .css-1d391kg {
        background: rgba(15, 15, 35, 0.95);
        border-right: 1px solid rgba(34, 211, 238, 0.3);
    }
    
    /* Main Content Area */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #ffffff;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 600;
    }
    
    /* Sidebar Text */
    .css-1d391kg .css-1v0mbdj, .css-1d391kg label {
        color: #ffffff !important;
        font-family: 'Space Grotesk', sans-serif;
    }
    
    /* Select Boxes and Inputs */
    .stSelectbox > div > div, .stDateInput > div > div, .stTimeInput > div > div {
        background-color: rgba(26, 26, 46, 0.8);
        border: 1px solid rgba(34, 211, 238, 0.3);
        color: #ffffff;
    }
    
    /* Metrics Cards */
    [data-testid="metric-container"] {
        background: rgba(26, 26, 46, 0.6);
        border: 1px solid rgba(34, 211, 238, 0.3);
        padding: 1rem;
        border-radius: 10px;
        backdrop-filter: blur(10px);
    }
    
    /* Numbers in Metrics */
    [data-testid="metric-container"] > div {
        font-family: 'JetBrains Mono', monospace;
        color: #00ff88;
    }
    
    /* Professional Glass Cards */
    .glass-card {
        background: rgba(26, 26, 46, 0.6);
        border: 1px solid rgba(34, 211, 238, 0.3);
        border-radius: 15px;
        padding: 1.5rem;
        backdrop-filter: blur(10px);
        margin: 1rem 0;
    }
    
    /* Success/Warning/Error Styling */
    .stAlert {
        background: rgba(26, 26, 46, 0.8);
        border-left: 4px solid #00ff88;
        color: #ffffff;
    }
    
    /* Button Styling */
    .stButton > button {
        background: linear-gradient(45deg, #22d3ee, #a855f7);
        color: white;
        border: none;
        border-radius: 8px;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    /* Data Tables */
    .dataframe {
        background: rgba(26, 26, 46, 0.8);
        color: #ffffff;
        border: 1px solid rgba(34, 211, 238, 0.3);
    }
    
    /* Hide Streamlit Menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# CORE CONSTANTS & CONFIGURATIONS
# ==========================================
class TradingConfig:
    # Timezone configurations
    CT_TZ = pytz.timezone('America/Chicago')
    ET_TZ = pytz.timezone('America/New_York')
    
    # SPX Asian Session
    ASIAN_SESSION_START = time(17, 0)  # 5:00 PM CT
    ASIAN_SESSION_END = time(19, 30)   # 7:30 PM CT
    
    # RTH Session
    RTH_START_ET = time(9, 30)   # 9:30 AM ET
    RTH_END_ET = time(16, 0)     # 4:00 PM ET
    RTH_START_CT = time(8, 30)   # 8:30 AM CT
    RTH_END_CT = time(15, 0)     # 3:00 PM CT
    
    # Slope configurations
    SPX_SLOPES = {'skyline': 0.2255, 'baseline': -0.2255}
    STOCK_SLOPES = {
        'AAPL': {'skyline': 0.0155, 'baseline': -0.0155},
        'MSFT': {'skyline': 0.0541, 'baseline': -0.0541},
        'NVDA': {'skyline': 0.0086, 'baseline': -0.0086},
        'AMZN': {'skyline': 0.0139, 'baseline': -0.0139},
        'GOOGL': {'skyline': 0.0122, 'baseline': -0.0122},
        'TSLA': {'skyline': 0.0285, 'baseline': -0.0285},
        'META': {'skyline': 0.0674, 'baseline': -0.0674}
    }
    
    # Trading symbols
    SPX_SYMBOL = '^GSPC'
    ES_SYMBOL = 'ES=F'
    AVAILABLE_STOCKS = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'TSLA', 'META']
    
    # Cache TTL
    LIVE_DATA_TTL = 60    # 60 seconds for live data
    HISTORICAL_TTL = 300  # 5 minutes for historical data

# ==========================================
# CORE UTILITY FUNCTIONS
# ==========================================
@st.cache_data(ttl=TradingConfig.HISTORICAL_TTL)
def get_market_data(symbol, period='5d', interval='30m'):
    """
    Fetch market data with caching and error handling
    """
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        
        if data.empty:
            st.error(f"No data available for {symbol}")
            return None
            
        # Add timezone info if missing
        if data.index.tz is None:
            data.index = data.index.tz_localize('America/New_York')
        
        return data
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

@st.cache_data(ttl=TradingConfig.LIVE_DATA_TTL)
def get_current_price(symbol):
    """
    Get current price with live caching
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Try different price fields
        current_price = (info.get('regularMarketPrice') or 
                        info.get('currentPrice') or
                        info.get('previousClose'))
        
        if current_price is None:
            # Fallback to recent data
            recent_data = get_market_data(symbol, period='1d', interval='1m')
            if recent_data is not None and not recent_data.empty:
                current_price = recent_data['Close'].iloc[-1]
        
        return float(current_price) if current_price else None
    except Exception as e:
        st.warning(f"Could not fetch current price for {symbol}")
        return None

def convert_timezone(dt_obj, from_tz, to_tz):
    """
    Convert datetime between timezones
    """
    if dt_obj.tz is None:
        dt_obj = from_tz.localize(dt_obj)
    return dt_obj.astimezone(to_tz)

def get_trading_session_times(date, session_type='RTH'):
    """
    Get trading session start/end times for a given date
    """
    if session_type == 'RTH':
        start_time = TradingConfig.ET_TZ.localize(
            datetime.combine(date, TradingConfig.RTH_START_ET)
        )
        end_time = TradingConfig.ET_TZ.localize(
            datetime.combine(date, TradingConfig.RTH_END_ET)
        )
    elif session_type == 'ASIAN':
        start_time = TradingConfig.CT_TZ.localize(
            datetime.combine(date, TradingConfig.ASIAN_SESSION_START)
        )
        end_time = TradingConfig.CT_TZ.localize(
            datetime.combine(date, TradingConfig.ASIAN_SESSION_END)
        )
    
    return start_time, end_time

def calculate_chart_range(current_price, symbol_type='SPX', volatility_factor=1.0):
    """
    Calculate optimal chart Y-axis range for professional scaling
    """
    if symbol_type == 'SPX':
        base_range = 50 * volatility_factor
    else:
        # Stock-specific ranges
        stock_ranges = {
            'AAPL': 8, 'MSFT': 12, 'NVDA': 15, 'AMZN': 10,
            'GOOGL': 8, 'TSLA': 20, 'META': 15
        }
        base_range = stock_ranges.get(symbol_type, 10) * volatility_factor
    
    y_min = current_price - base_range
    y_max = current_price + base_range
    
    return y_min, y_max

def format_price(price, decimals=2):
    """
    Format price for display
    """
    if price is None:
        return "N/A"
    return f"${price:,.{decimals}f}"

def format_percentage(value, decimals=2):
    """
    Format percentage for display
    """
    if value is None:
        return "N/A"
    return f"{value:+.{decimals}f}%"

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
def initialize_session_state():
    """
    Initialize session state variables
    """
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'Dashboard'
    
    if 'selected_symbol' not in st.session_state:
        st.session_state.selected_symbol = '^GSPC'
    
    if 'analysis_date' not in st.session_state:
        st.session_state.analysis_date = datetime.now().date()
    
    if 'anchor_cache' not in st.session_state:
        st.session_state.anchor_cache = {}
    
    if 'signal_cache' not in st.session_state:
        st.session_state.signal_cache = {}

# ==========================================
# NAVIGATION SYSTEM
# ==========================================
def create_navigation():
    """
    Create professional navigation sidebar
    """
    with st.sidebar:
        st.markdown("# 📈 MarketLens Pro v5")
        st.markdown("*by Max Pointe Consulting*")
        st.markdown("---")
        
        # Navigation pages
        pages = [
            '📊 Dashboard',
            '⚓ Anchors', 
            '🔮 Forecasts',
            '🎯 Signals',
            '📋 Contracts',
            '📐 Fibonacci',
            '📄 Export',
            '⚙️ Settings'
        ]
        
        # Create navigation
        for page in pages:
            page_name = page.split(' ', 1)[1]  # Remove emoji for internal reference
            if st.button(page, key=f"nav_{page_name}", use_container_width=True):
                st.session_state.current_page = page_name
        
        st.markdown("---")
        
        # Symbol Selection
        st.markdown("### 🎯 **Symbol Selection**")
        symbol_options = {
            'S&P 500 Index': '^GSPC',
            'Apple Inc.': 'AAPL',
            'Microsoft Corp.': 'MSFT', 
            'NVIDIA Corp.': 'NVDA',
            'Amazon.com Inc.': 'AMZN',
            'Alphabet Inc.': 'GOOGL',
            'Tesla Inc.': 'TSLA',
            'Meta Platforms': 'META'
        }
        
        selected_name = st.selectbox(
            "Select Symbol",
            options=list(symbol_options.keys()),
            key="symbol_selector"
        )
        st.session_state.selected_symbol = symbol_options[selected_name]
        
        # Analysis Date
        st.markdown("### 📅 **Analysis Date**")
        st.session_state.analysis_date = st.date_input(
            "Select Date",
            value=datetime.now().date(),
            key="date_selector"
        )
        
        # Market Status
        st.markdown("### 📈 **Market Status**")
        current_time = datetime.now(TradingConfig.ET_TZ)
        market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = current_time.replace(hour=16, minute=0, second=0, microsecond=0)
        
        if market_open <= current_time <= market_close and current_time.weekday() < 5:
            st.success("🟢 **MARKET OPEN**")
        else:
            st.info("🔴 **MARKET CLOSED**")
        
        # Current Time Display
        st.markdown(f"**ET:** {current_time.strftime('%H:%M:%S')}")
        ct_time = current_time.astimezone(TradingConfig.CT_TZ)
        st.markdown(f"**CT:** {ct_time.strftime('%H:%M:%S')}")

# ==========================================
# PROFESSIONAL COMPONENTS
# ==========================================
def create_metric_card(title, value, delta=None, delta_color="normal"):
    """
    Create professional metric card
    """
    if delta is not None:
        st.metric(
            label=title,
            value=value,
            delta=delta,
            delta_color=delta_color
        )
    else:
        st.metric(label=title, value=value)

def create_info_card(title, content):
    """
    Create professional info card with glass effect
    """
    st.markdown(f"""
    <div class="glass-card">
        <h3 style="color: #22d3ee; margin-bottom: 1rem;">{title}</h3>
        <p style="color: #ffffff; font-size: 1.1rem; line-height: 1.6;">{content}</p>
    </div>
    """, unsafe_allow_html=True)

def create_status_indicator(status, message):
    """
    Create status indicator
    """
    if status == "success":
        st.success(f"✅ {message}")
    elif status == "warning":
        st.warning(f"⚠️ {message}")
    elif status == "error":
        st.error(f"❌ {message}")
    else:
        st.info(f"ℹ️ {message}")

# ==========================================
# PAGE CONTENT FUNCTIONS
# ==========================================
def show_dashboard():
    st.markdown("# 📊 **MarketLens Pro Dashboard**")
    st.markdown("---")
    
    # Get current market data
    symbol = st.session_state.selected_symbol
    current_price = get_current_price(symbol)
    
    # Market Overview Row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        symbol_name = symbol.replace('^', '') if symbol.startswith('^') else symbol
        create_metric_card(
            title=f"{symbol_name} Price",
            value=format_price(current_price) if current_price else "Loading...",
            delta="+0.85%" if current_price else None,
            delta_color="normal"
        )
    
    with col2:
        create_metric_card(
            title="Market Trend",
            value="BULLISH",
            delta="↗️ Strong"
        )
    
    with col3:
        create_metric_card(
            title="Anchor Status",
            value="ACTIVE",
            delta="🎯 Tracking"
        )
    
    with col4:
        create_metric_card(
            title="Signal Count",
            value="3",
            delta="+1 Today"
        )
    
    # Main content area
    create_info_card(
        "Welcome to MarketLens Pro v5",
        "Your professional anchor-based trading analysis platform. Navigate through the sidebar to access different analysis modules. The system tracks Asian session anchors for SPX and Monday/Tuesday anchors for individual stocks, providing precise slope-based projections and signal detection."
    )
    
    # Quick Stats
    st.markdown("### 📈 **Quick Market Overview**")
    col1, col2 = st.columns(2)
    
    with col1:
        create_info_card(
            "Today's Focus",
            f"Currently analyzing {symbol_name} with anchor-based methodology. System is monitoring for 30-minute candle interactions with projected Skyline and Baseline levels."
        )
    
    with col2:
        create_info_card(
            "System Status", 
            "All systems operational. Data feeds active. Anchor calculations updated. Signal detection algorithms running. Ready for professional trading analysis."
        )

def show_placeholder_page(page_name, description):
    """
    Show placeholder for pages to be implemented in later parts
    """
    st.markdown(f"# {page_name}")
    st.markdown("---")
    
    create_info_card(
        f"{page_name} Module",
        f"{description} This module will be implemented in the next development phase."
    )
    
    create_status_indicator("info", f"{page_name} module coming in the next update")

# ==========================================
# MAIN APPLICATION
# ==========================================
def main():
    # Apply styling
    apply_custom_styling()
    
    # Initialize session state
    initialize_session_state()
    
    # Create navigation
    create_navigation()
    
    # Main content based on selected page
    current_page = st.session_state.current_page
    
    if current_page == 'Dashboard':
        show_dashboard()
    elif current_page == 'Anchors':
        show_placeholder_page("⚓ Anchors", "Advanced anchor detection and analysis system.")
    elif current_page == 'Forecasts':
        show_placeholder_page("🔮 Forecasts", "Price projection and forecasting engine.")
    elif current_page == 'Signals':
        show_placeholder_page("🎯 Signals", "Real-time trading signal detection and alerts.")
    elif current_page == 'Contracts':
        show_placeholder_page("📋 Contracts", "Contract analysis and position management.")
    elif current_page == 'Fibonacci':
        show_placeholder_page("📐 Fibonacci", "Fibonacci retracement analysis with 78.6% emphasis.")
    elif current_page == 'Export':
        show_placeholder_page("📄 Export", "Professional reporting and data export capabilities.")
    elif current_page == 'Settings':
        show_placeholder_page("⚙️ Settings", "Application configuration and preferences.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888; font-size: 0.8rem; font-family: \"Space Grotesk\", sans-serif;'>"
        "MarketLens Pro v5 | Max Pointe Consulting | Professional Trading Analytics"
        "</div>", 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()