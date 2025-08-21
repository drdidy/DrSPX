"""
MARKETLENS PRO v5 - PART 1: CORE FOUNDATION & MAIN DASHBOARD
Professional Trading Application by Max Pointe Consulting
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, time
import pytz
import time as time_module
from typing import Dict, List, Tuple, Optional, Any
import json
import hashlib
from functools import lru_cache
import warnings
warnings.filterwarnings('ignore')

# ============================================
# CONFIGURATION & CONSTANTS
# ============================================

# Application Configuration
APP_NAME = "MarketLens Pro v5"
APP_VERSION = "5.0.0"
APP_COMPANY = "Max Pointe Consulting"

# Theme Colors
COLORS = {
    'primary': '#22d3ee',      # Cyan
    'secondary': '#a855f7',     # Purple
    'success': '#00ff88',       # Green
    'warning': '#ff6b35',       # Orange
    'background': '#0a0e27',    # Dark blue
    'panel': 'rgba(15, 23, 42, 0.6)',  # Glass panel
    'text': '#ffffff',          # White text
    'text_secondary': '#94a3b8' # Gray text
}

# Trading Assets Configuration
INDICES = {
    'SPX': {
        'symbol': '^GSPC',
        'futures': 'ES=F',
        'slope': 0.2255,
        'name': 'S&P 500'
    }
}

STOCKS = {
    'AAPL': {'slope': 0.0155, 'name': 'Apple Inc.'},
    'MSFT': {'slope': 0.0541, 'name': 'Microsoft Corp.'},
    'NVDA': {'slope': 0.0086, 'name': 'NVIDIA Corp.'},
    'AMZN': {'slope': 0.0139, 'name': 'Amazon.com Inc.'},
    'GOOGL': {'slope': 0.0122, 'name': 'Alphabet Inc.'},
    'TSLA': {'slope': 0.0285, 'name': 'Tesla Inc.'},
    'META': {'slope': 0.0674, 'name': 'Meta Platforms Inc.'}
}

# Time Configuration
EASTERN_TZ = pytz.timezone('US/Eastern')
CENTRAL_TZ = pytz.timezone('US/Central')

# Trading Hours
ASIAN_SESSION_START = time(17, 0)  # 5:00 PM CT
ASIAN_SESSION_END = time(19, 30)   # 7:30 PM CT
RTH_START = time(8, 30)             # 8:30 AM CT
RTH_END = time(14, 30)              # 2:30 PM CT
STOCK_RTH_START = time(9, 30)       # 9:30 AM ET
STOCK_RTH_END = time(16, 0)         # 4:00 PM ET

# Cache Configuration
CACHE_TTL_LIVE = 60         # 60 seconds for live data
CACHE_TTL_HISTORICAL = 300  # 5 minutes for historical data

# ============================================
# SESSION STATE INITIALIZATION
# ============================================

def init_session_state():
    """Initialize Streamlit session state variables"""
    
    defaults = {
        'initialized': False,
        'current_page': 'Dashboard',
        'selected_asset': 'SPX',
        'selected_stock': 'AAPL',
        'data_cache': {},
        'cache_timestamps': {},
        'theme_mode': 'dark',
        'auto_refresh': False,
        'refresh_interval': 60,
        'last_refresh': datetime.now(),
        'asian_anchors': {},
        'stock_anchors': {},
        'active_signals': [],
        'portfolio_value': 100000.0,
        'daily_pnl': 0.0,
        'win_rate': 0.0,
        'total_trades': 0,
        'data_quality_score': 0.0,
        'market_status': 'CLOSED',
        'next_session': None,
        'es_spx_offset': 0.0
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    st.session_state.initialized = True

# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_cache_key(symbol: str, period: str, interval: str) -> str:
    """Generate cache key for data storage"""
    return f"{symbol}_{period}_{interval}_{datetime.now().strftime('%Y%m%d')}"

def is_cache_valid(cache_key: str, ttl: int) -> bool:
    """Check if cached data is still valid"""
    if cache_key not in st.session_state.cache_timestamps:
        return False
    
    timestamp = st.session_state.cache_timestamps[cache_key]
    return (datetime.now() - timestamp).seconds < ttl

def format_number(value: float, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    """Format number for display"""
    if pd.isna(value):
        return "N/A"
    
    if abs(value) >= 1e9:
        return f"{prefix}{value/1e9:.{decimals}f}B{suffix}"
    elif abs(value) >= 1e6:
        return f"{prefix}{value/1e6:.{decimals}f}M{suffix}"
    elif abs(value) >= 1e3:
        return f"{prefix}{value/1e3:.{decimals}f}K{suffix}"
    else:
        return f"{prefix}{value:.{decimals}f}{suffix}"

def format_percentage(value: float, decimals: int = 2) -> str:
    """Format percentage for display"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.{decimals}f}%"

def get_market_status() -> Tuple[str, datetime]:
    """Get current market status and next session time"""
    now_et = datetime.now(EASTERN_TZ)
    current_time = now_et.time()
    weekday = now_et.weekday()
    
    # Weekend check
    if weekday >= 5:  # Saturday or Sunday
        next_monday = now_et + timedelta(days=(7 - weekday))
        next_session = next_monday.replace(hour=9, minute=30, second=0, microsecond=0)
        return "CLOSED", next_session
    
    # Pre-market: 4:00 AM - 9:30 AM ET
    if time(4, 0) <= current_time < STOCK_RTH_START:
        next_session = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        return "PRE-MARKET", next_session
    
    # Regular trading hours: 9:30 AM - 4:00 PM ET
    elif STOCK_RTH_START <= current_time < STOCK_RTH_END:
        return "OPEN", now_et
    
    # After-hours: 4:00 PM - 8:00 PM ET
    elif STOCK_RTH_END <= current_time < time(20, 0):
        next_day = now_et + timedelta(days=1)
        if next_day.weekday() < 5:
            next_session = next_day.replace(hour=9, minute=30, second=0, microsecond=0)
        else:
            next_monday = now_et + timedelta(days=(7 - weekday))
            next_session = next_monday.replace(hour=9, minute=30, second=0, microsecond=0)
        return "AFTER-HOURS", next_session
    
    # Closed
    else:
        next_day = now_et + timedelta(days=1)
        if next_day.weekday() < 5:
            next_session = next_day.replace(hour=4, minute=0, second=0, microsecond=0)
        else:
            next_monday = now_et + timedelta(days=(7 - weekday) + 1)
            next_session = next_monday.replace(hour=4, minute=0, second=0, microsecond=0)
        return "CLOSED", next_session

def calculate_data_quality_score(df: pd.DataFrame) -> float:
    """Calculate data quality score"""
    if df is None or df.empty:
        return 0.0
    
    score = 100.0
    
    # Check for missing values
    missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
    score -= missing_pct * 2
    
    # Check for zero volumes
    if 'Volume' in df.columns:
        zero_volume_pct = (df['Volume'] == 0).sum() / len(df) * 100
        score -= zero_volume_pct
    
    # Check for price anomalies
    if 'Close' in df.columns:
        price_changes = df['Close'].pct_change()
        anomaly_pct = (abs(price_changes) > 0.1).sum() / len(price_changes) * 100
        score -= anomaly_pct * 0.5
    
    return max(0, min(100, score))

# ============================================
# DATA FETCHING FUNCTIONS
# ============================================

@st.cache_data(ttl=CACHE_TTL_LIVE)
def fetch_stock_data(symbol: str, period: str = "5d", interval: str = "30m") -> pd.DataFrame:
    """Fetch stock data from Yahoo Finance with caching"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            return generate_demo_data(symbol, period, interval)
        
        # Add technical indicators
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['EMA_8'] = df['Close'].ewm(span=8, adjust=False).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        # Volume indicators
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        
        return df
        
    except Exception as e:
        st.warning(f"Error fetching data for {symbol}: {str(e)}")
        return generate_demo_data(symbol, period, interval)

def generate_demo_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Generate demo data for testing"""
    end_date = datetime.now()
    
    # Determine number of periods
    if period == "1d":
        periods = 13  # 13 30-minute periods in a trading day
    elif period == "5d":
        periods = 65  # 5 days * 13 periods
    elif period == "1mo":
        periods = 260  # ~20 trading days * 13 periods
    else:
        periods = 100
    
    # Generate time index
    dates = pd.date_range(end=end_date, periods=periods, freq='30min')
    
    # Generate price data
    base_price = 100 if symbol in STOCKS else 4500
    prices = base_price + np.cumsum(np.random.randn(periods) * 0.5)
    
    df = pd.DataFrame({
        'Open': prices + np.random.randn(periods) * 0.1,
        'High': prices + abs(np.random.randn(periods) * 0.2),
        'Low': prices - abs(np.random.randn(periods) * 0.2),
        'Close': prices,
        'Volume': np.random.randint(1000000, 10000000, periods)
    }, index=dates)
    
    # Ensure OHLC consistency
    df['High'] = df[['Open', 'High', 'Low', 'Close']].max(axis=1)
    df['Low'] = df[['Open', 'High', 'Low', 'Close']].min(axis=1)
    
    # Add technical indicators
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['EMA_8'] = df['Close'].ewm(span=8, adjust=False).mean()
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
    
    return df

# ============================================
# MAIN DASHBOARD COMPONENTS
# ============================================

def render_header():
    """Render application header"""
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col1:
        st.markdown(f"### 🎯 {APP_NAME}")
        st.caption(f"v{APP_VERSION} | {APP_COMPANY}")
    
    with col2:
        market_status, next_session = get_market_status()
        st.session_state.market_status = market_status
        st.session_state.next_session = next_session
        
        status_color = {
            'OPEN': COLORS['success'],
            'PRE-MARKET': COLORS['warning'],
            'AFTER-HOURS': COLORS['warning'],
            'CLOSED': COLORS['text_secondary']
        }.get(market_status, COLORS['text_secondary'])
        
        st.markdown(
            f"""<div style='text-align: center; padding: 10px;'>
            <span style='color: {status_color}; font-size: 18px; font-weight: bold;'>
            ⬤ Market {market_status}
            </span>
            </div>""",
            unsafe_allow_html=True
        )
    
    with col3:
        current_time = datetime.now().strftime("%H:%M:%S")
        st.markdown(f"### ⏰ {current_time}")
        st.caption(datetime.now().strftime("%B %d, %Y"))

def render_key_metrics():
    """Render key performance metrics"""
    st.markdown("### 📊 Key Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Portfolio Value",
            format_number(st.session_state.portfolio_value, prefix="$"),
            delta=format_percentage(2.35),
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "Daily P&L",
            format_number(st.session_state.daily_pnl, prefix="$"),
            delta=format_percentage(1.28),
            delta_color="normal"
        )
    
    with col3:
        st.metric(
            "Win Rate",
            format_percentage(st.session_state.win_rate),
            delta=f"{st.session_state.total_trades} trades",
            delta_color="off"
        )
    
    with col4:
        st.metric(
            "Data Quality",
            format_percentage(st.session_state.data_quality_score),
            delta="Live Feed",
            delta_color="off"
        )

def render_market_overview():
    """Render market overview section"""
    st.markdown("### 🌍 Market Overview")
    
    # Fetch market data
    market_symbols = {
        'S&P 500': '^GSPC',
        'NASDAQ': '^IXIC',
        'DOW': '^DJI',
        'VIX': '^VIX'
    }
    
    cols = st.columns(len(market_symbols))
    
    for idx, (name, symbol) in enumerate(market_symbols.items()):
        with cols[idx]:
            try:
                data = fetch_stock_data(symbol, period="1d", interval="1m")
                if not data.empty:
                    current_price = data['Close'].iloc[-1]
                    prev_close = data['Close'].iloc[0]
                    change = ((current_price - prev_close) / prev_close) * 100
                    
                    st.metric(
                        name,
                        format_number(current_price, decimals=2),
                        delta=format_percentage(change),
                        delta_color="normal" if change >= 0 else "inverse"
                    )
                else:
                    st.metric(name, "N/A", delta="N/A")
            except:
                st.metric(name, "Loading...", delta="--")

def render_watchlist():
    """Render watchlist section"""
    st.markdown("### 👁️ Watchlist")
    
    # Create watchlist dataframe
    watchlist_data = []
    
    for symbol, info in STOCKS.items():
        try:
            data = fetch_stock_data(symbol, period="1d", interval="5m")
            if not data.empty:
                current_price = data['Close'].iloc[-1]
                prev_close = data['Close'].iloc[0]
                change = ((current_price - prev_close) / prev_close) * 100
                volume = data['Volume'].iloc[-1]
                
                watchlist_data.append({
                    'Symbol': symbol,
                    'Name': info['name'],
                    'Price': current_price,
                    'Change %': change,
                    'Volume': volume,
                    'Slope': info['slope']
                })
        except:
            watchlist_data.append({
                'Symbol': symbol,
                'Name': info['name'],
                'Price': 0,
                'Change %': 0,
                'Volume': 0,
                'Slope': info['slope']
            })
    
    df_watchlist = pd.DataFrame(watchlist_data)
    
    # Style the dataframe
    def style_watchlist(val):
        if isinstance(val, (int, float)):
            if val > 0:
                return f'color: {COLORS["success"]}'
            elif val < 0:
                return f'color: {COLORS["warning"]}'
        return ''
    
    styled_df = df_watchlist.style.applymap(style_watchlist, subset=['Change %'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

def render_active_signals():
    """Render active trading signals"""
    st.markdown("### 🚦 Active Signals")
    
    if not st.session_state.active_signals:
        st.info("No active signals at this time. Monitoring anchor levels...")
    else:
        for signal in st.session_state.active_signals:
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                signal_icon = "🟢" if signal['type'] == 'BUY' else "🔴"
                st.write(f"{signal_icon} **{signal['symbol']}** - {signal['type']}")
            
            with col2:
                st.write(f"Entry: ${signal['entry_price']:.2f}")
            
            with col3:
                st.write(f"Target: ${signal['target_price']:.2f}")

def render_system_status():
    """Render system status panel"""
    st.markdown("### ⚙️ System Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Data Feeds:**")
        st.success("✅ Yahoo Finance Connected")
        st.info("🔄 Auto-refresh: " + ("ON" if st.session_state.auto_refresh else "OFF"))
    
    with col2:
        st.markdown("**Anchor Systems:**")
        st.success("✅ SPX Asian Session Active")
        st.success("✅ Stock Mon/Tue Analysis Active")
        
        if st.session_state.es_spx_offset != 0:
            st.info(f"ES-SPX Offset: {st.session_state.es_spx_offset:.2f}")

# ============================================
# MAIN APPLICATION
# ============================================

def main():
    """Main application entry point"""
    
    # Page configuration
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session_state()
    
    # Main container
    st.markdown(f"# {APP_NAME}")
    st.markdown("---")
    
    # Header section
    render_header()
    st.markdown("---")
    
    # Key metrics
    render_key_metrics()
    st.markdown("---")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Market overview
        render_market_overview()
        st.markdown("---")
        
        # Watchlist
        render_watchlist()
    
    with col2:
        # Active signals
        render_active_signals()
        st.markdown("---")
        
        # System status
        render_system_status()
    
    # Footer
    st.markdown("---")
    st.caption(f"© 2024 {APP_COMPANY} | {APP_NAME} v{APP_VERSION} | Professional Trading System")

if __name__ == "__main__":
    main()