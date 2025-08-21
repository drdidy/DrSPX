# ============================================================================
# MARKETLENS PRO V5 - PART 1: ELITE TRADING ANALYTICS PLATFORM
# BY MAX POINTE CONSULTING
# Professional Market Intelligence & Signal Advisory System
# ============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import datetime
import pytz
import time
import warnings
from typing import Dict, List, Tuple, Optional, Any
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, time as dt_time
import math

warnings.filterwarnings('ignore')

# ============================================================================
# ELITE TRADING CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="MarketLens Pro v5 - Elite Trading Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Core trading universe
TRADING_UNIVERSE = {
    'INDEX': '^GSPC',  # SPX
    'FUTURES': 'ES=F',  # ES Futures
    'MEGA_CAPS': {
        'AAPL': {'name': 'Apple Inc.', 'sector': 'Technology', 'slope': 0.0155},
        'MSFT': {'name': 'Microsoft Corp.', 'sector': 'Technology', 'slope': 0.0541},
        'NVDA': {'name': 'NVIDIA Corp.', 'sector': 'Technology', 'slope': 0.0086},
        'GOOGL': {'name': 'Alphabet Inc.', 'sector': 'Technology', 'slope': 0.0122},
        'AMZN': {'name': 'Amazon.com Inc.', 'sector': 'Consumer Disc.', 'slope': 0.0139},
        'TSLA': {'name': 'Tesla Inc.', 'sector': 'Consumer Disc.', 'slope': 0.0285},
        'META': {'name': 'Meta Platforms Inc.', 'sector': 'Technology', 'slope': 0.0674}
    }
}

# Time zones
ET_TZ = pytz.timezone('US/Eastern')
CT_TZ = pytz.timezone('US/Central')

# ============================================================================
# ELITE CSS STYLING SYSTEM
# ============================================================================

def apply_elite_styling():
    """Apply elite trading platform styling"""
    st.markdown("""
    <style>
    /* Elite Trading Platform Theme */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }
    
    /* Hero Header */
    .elite-header {
        background: linear-gradient(135deg, #0a0f1c 0%, #1a202c 50%, #0a0f1c 100%);
        border: 2px solid #22d3ee;
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
        text-align: center;
        position: relative;
        overflow: hidden;
        box-shadow: 0 20px 40px rgba(34, 211, 238, 0.3);
    }
    
    .elite-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(34, 211, 238, 0.1) 0%, transparent 70%);
        animation: pulse 4s ease-in-out infinite;
    }
    
    .elite-header h1 {
        color: #22d3ee;
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
        text-shadow: 0 0 30px rgba(34, 211, 238, 0.8);
        position: relative;
        z-index: 1;
    }
    
    .elite-header p {
        color: #94a3b8;
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
        position: relative;
        z-index: 1;
    }
    
    /* Trading Cards - Mobile Optimized */
    .trading-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
        border: 1px solid rgba(34, 211, 238, 0.4);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        height: 220px;
        overflow-y: auto;
        color: #ffffff !important;
    }
    
    .trading-card h4 {
        color: #22d3ee !important;
        font-size: 1rem !important;
        margin-bottom: 0.5rem !important;
        font-weight: 600 !important;
    }
    
    .trading-card p {
        color: #ffffff !important;
        font-size: 0.85rem !important;
        line-height: 1.4 !important;
        margin: 0.3rem 0 !important;
    }
    
    .trading-card ul {
        color: #ffffff !important;
        font-size: 0.8rem !important;
        line-height: 1.3 !important;
        margin: 0.5rem 0 !important;
        padding-left: 1rem !important;
    }
    
    .trading-card li {
        color: #ffffff !important;
        margin: 0.2rem 0 !important;
    }
    
    .trading-card:hover {
        border-color: rgba(34, 211, 238, 0.8);
        box-shadow: 0 12px 32px rgba(34, 211, 238, 0.2);
        transform: translateY(-2px);
    }
    
    /* Metric Cards - Mobile Optimized */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
        border: 1px solid rgba(34, 211, 238, 0.3);
        border-radius: 12px;
        padding: 0.8rem;
        margin: 0.5rem 0;
        backdrop-filter: blur(15px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
        min-height: 90px;
        transition: all 0.3s ease;
    }
    
    [data-testid="metric-container"] [data-testid="metric-label"],
    [data-testid="metric-container"] [data-testid="metric-value"],
    [data-testid="metric-container"] [data-testid="metric-delta"] {
        color: #ffffff !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    [data-testid="metric-container"] [data-testid="metric-label"] {
        font-size: 0.8rem !important;
    }
    
    [data-testid="metric-container"] [data-testid="metric-value"] {
        font-size: 1.1rem !important;
        font-weight: bold !important;
    }
    
    [data-testid="metric-container"] [data-testid="metric-delta"] {
        font-size: 0.75rem !important;
    }
    
    [data-testid="metric-container"]:hover {
        border-color: rgba(34, 211, 238, 0.6);
        transform: translateY(-1px);
    }
    
    /* Status Indicators - Enhanced Visibility */
    .status-bull { color: #00ff88 !important; font-weight: bold; font-size: 0.9rem; }
    .status-bear { color: #ff4757 !important; font-weight: bold; font-size: 0.9rem; }
    .status-neutral { color: #ffa502 !important; font-weight: bold; font-size: 0.9rem; }
    .status-premium { color: #22d3ee !important; font-weight: bold; font-size: 0.9rem; }
    
    /* Mobile Responsive - Enhanced */
    @media (max-width: 768px) {
        .elite-header h1 { font-size: 1.8rem; }
        .elite-header p { font-size: 0.9rem; }
        
        .trading-card { 
            height: 200px; 
            padding: 0.8rem;
        }
        
        .trading-card h4 {
            font-size: 0.9rem !important;
        }
        
        .trading-card p {
            font-size: 0.8rem !important;
        }
        
        .trading-card ul {
            font-size: 0.75rem !important;
        }
        
        [data-testid="metric-container"] { 
            min-height: 75px; 
            padding: 0.6rem;
        }
        
        [data-testid="metric-container"] [data-testid="metric-label"] {
            font-size: 0.7rem !important;
        }
        
        [data-testid="metric-container"] [data-testid="metric-value"] {
            font-size: 1rem !important;
        }
        
        [data-testid="metric-container"] [data-testid="metric-delta"] {
            font-size: 0.7rem !important;
        }
    }
    
    /* Dataframe Styling - Enhanced Text Visibility */
    .stDataFrame > div {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
        border: 1px solid rgba(34, 211, 238, 0.3);
        border-radius: 12px;
        backdrop-filter: blur(15px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    }
    
    .stDataFrame table {
        color: #ffffff !important;
        font-size: 0.85rem !important;
    }
    
    .stDataFrame th {
        color: #22d3ee !important;
        font-weight: bold !important;
        background-color: rgba(34, 211, 238, 0.1) !important;
    }
    
    .stDataFrame td {
        color: #ffffff !important;
    }
    
    /* Enhanced Text Visibility - Force Dark Text on Light, White on Dark */
    
    /* Alert Boxes - Enhanced Visibility */
    .stAlert > div {
        color: #ffffff !important;
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.98) 0%, rgba(15, 23, 42, 0.98) 100%) !important;
    }
    
    .stAlert p, .stAlert div, .stAlert span, .stAlert strong {
        color: #ffffff !important;
    }
    
    /* Dataframe Styling - Enhanced Text Visibility */
    .stDataFrame > div {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
        border: 1px solid rgba(34, 211, 238, 0.3);
        border-radius: 12px;
        backdrop-filter: blur(15px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    }
    
    .stDataFrame table {
        color: #ffffff !important;
        font-size: 0.85rem !important;
        background-color: rgba(15, 23, 42, 0.95) !important;
    }
    
    .stDataFrame th {
        color: #22d3ee !important;
        font-weight: bold !important;
        background-color: rgba(15, 23, 42, 0.98) !important;
        border-bottom: 1px solid rgba(34, 211, 238, 0.3) !important;
    }
    
    .stDataFrame td {
        color: #ffffff !important;
        background-color: rgba(15, 23, 42, 0.95) !important;
        border-bottom: 1px solid rgba(34, 211, 238, 0.1) !important;
    }
    
    /* Force all table text to be white */
    .stDataFrame table tbody tr td,
    .stDataFrame table thead tr th,
    .stDataFrame table tbody tr td div,
    .stDataFrame table thead tr th div {
        color: #ffffff !important;
        background-color: transparent !important;
    }
    
    /* Caption and small text */
    .stCaption, .caption {
        color: #94a3b8 !important;
        font-size: 0.8rem !important;
    }
    
    /* Markdown text in containers */
    .stMarkdown p, .stMarkdown div, .stMarkdown span {
        color: #ffffff !important;
    }
    
    /* Subheadings */
    h1, h2, h3, h4, h5, h6 {
        color: #22d3ee !important;
    }
    
    /* Warning, info, success, error boxes */
    .stAlert[data-baseweb="notification"] {
        background-color: rgba(15, 23, 42, 0.95) !important;
        color: #ffffff !important;
        border: 1px solid rgba(34, 211, 238, 0.3) !important;
    }
    
    .stAlert[data-baseweb="notification"] > div {
        color: #ffffff !important;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 0.8; }
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# ELITE DATA STRUCTURES
# ============================================================================

@dataclass
class MarketIntelligence:
    """Elite market intelligence data structure"""
    symbol: str
    price: float
    change_pct: float
    volume: int
    volatility: float
    rsi: float
    momentum_score: float
    trend_direction: str
    support_level: float
    resistance_level: float
    anchor_projection: Dict[str, float]

@dataclass
class TradingOpportunity:
    """Professional trading opportunity identification"""
    symbol: str
    opportunity_type: str  # 'BREAKOUT', 'REVERSAL', 'MOMENTUM', 'ANCHOR_TOUCH'
    entry_zone: Tuple[float, float]
    target_zones: List[float]
    stop_loss: float
    risk_reward_ratio: float
    confidence_score: float
    time_horizon: str
    market_context: str

# ============================================================================
# SESSION STATE MANAGEMENT
# ============================================================================

def initialize_elite_session():
    """Initialize elite trading session state"""
    if 'elite_initialized' not in st.session_state:
        # Core session
        st.session_state.elite_initialized = True
        st.session_state.session_start = datetime.now()
        st.session_state.market_intelligence = {}
        st.session_state.trading_opportunities = []
        st.session_state.watchlist = list(TRADING_UNIVERSE['MEGA_CAPS'].keys())[:5]
        
        # Analytics metrics
        st.session_state.market_regime = 'ANALYZING'
        st.session_state.fear_greed_index = 50
        st.session_state.sector_rotation = 'TECH_LEADERSHIP'
        st.session_state.volatility_regime = 'NORMAL'
        
        # Performance tracking
        st.session_state.opportunities_today = 0
        st.session_state.signals_generated = 0
        st.session_state.market_sync_score = 0.0
        
        # Data quality
        st.session_state.data_quality = {
            'connection_health': 100.0,
            'latency_ms': 45,
            'update_success_rate': 100.0,
            'last_sync': datetime.now()
        }

# ============================================================================
# ELITE UTILITY FUNCTIONS
# ============================================================================

def get_market_time():
    """Get current market time"""
    return datetime.now(ET_TZ)

def get_market_state():
    """Determine current market state"""
    now = get_market_time()
    
    if now.weekday() >= 5:  # Weekend
        return "🔒 WEEKEND", "#64748b"
    
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    if market_open <= now <= market_close:
        return "⚡ LIVE TRADING", "#00ff88"
    elif now.hour < 9:
        return "🌅 PRE-MARKET", "#ffa502"
    elif now.hour >= 16:
        return "🌙 AFTER-HOURS", "#ff6b35"
    else:
        return "⏸️ CLOSED", "#64748b"

def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate RSI indicator"""
    if len(prices) < period + 1:
        return 50.0
    
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

def calculate_volatility_regime(vol: float) -> str:
    """Determine volatility regime"""
    if vol < 15:
        return "LOW_VOL"
    elif vol < 25:
        return "NORMAL_VOL"
    elif vol < 35:
        return "HIGH_VOL"
    else:
        return "EXTREME_VOL"

def assess_market_regime(market_data: Dict) -> str:
    """Assess overall market regime"""
    if not market_data:
        return "ANALYZING"
    
    # Simple regime analysis based on volatility and momentum
    avg_vol = np.mean([data.get('volatility', 20) for data in market_data.values()])
    
    if avg_vol > 30:
        return "HIGH_VOLATILITY"
    elif avg_vol < 15:
        return "LOW_VOLATILITY"
    else:
        return "TRENDING"

# ============================================================================
# ELITE DATA FETCHING - REAL YAHOO FINANCE DATA
# ============================================================================

def fetch_elite_quote(symbol: str) -> Optional[Dict]:
    """Fetch REAL elite market data with advanced metrics"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='30d', interval='1d')
        
        if hist.empty:
            return None
        
        current_price = float(hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
        
        # Get actual volume
        current_volume = int(hist['Volume'].iloc[-1])
        
        # Calculate REAL advanced metrics
        returns = hist['Close'].pct_change().dropna()
        volatility = float(returns.std() * np.sqrt(252) * 100) if len(returns) > 1 else 0.0
        
        # Real RSI calculation
        rsi = calculate_rsi(hist['Close'])
        
        # Real momentum calculations
        momentum_5d = (current_price - hist['Close'].iloc[-6]) / hist['Close'].iloc[-6] * 100 if len(hist) > 5 else 0
        momentum_20d = (current_price - hist['Close'].iloc[-21]) / hist['Close'].iloc[-21] * 100 if len(hist) > 20 else 0
        
        # Real Support/Resistance levels
        high_20d = float(hist['High'].tail(20).max())
        low_20d = float(hist['Low'].tail(20).min())
        
        # Real change calculation
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close != 0 else 0
        
        return {
            'symbol': symbol,
            'price': current_price,
            'change': change,
            'change_pct': change_pct,
            'volume': current_volume,
            'volatility': volatility,
            'rsi': rsi,
            'momentum_5d': momentum_5d,
            'momentum_20d': momentum_20d,
            'support': low_20d,
            'resistance': high_20d,
            'vol_regime': calculate_volatility_regime(volatility),
            'last_update': datetime.now().strftime('%H:%M:%S')
        }
        
    except Exception:
        return None

def update_market_intelligence():
    """Update comprehensive market intelligence with REAL data"""
    intelligence = {}
    
    # Fetch data for all symbols silently in background
    all_symbols = [TRADING_UNIVERSE['INDEX']] + list(TRADING_UNIVERSE['MEGA_CAPS'].keys())
    
    for symbol in all_symbols:
        data = fetch_elite_quote(symbol)
        if data:
            intelligence[symbol] = data
    
    # Update session state with real data
    st.session_state.market_intelligence = intelligence
    st.session_state.market_regime = assess_market_regime(intelligence)
    
    # Update sync score based on successful data fetches
    success_rate = len(intelligence) / len(all_symbols) * 100
    st.session_state.market_sync_score = success_rate
    
    return intelligence

# ============================================================================
# ELITE DASHBOARD COMPONENTS
# ============================================================================

def render_elite_header():
    """Render elite trading platform header"""
    st.markdown("""
    <div class="elite-header">
        <h1>⚡ MarketLens Pro v5</h1>
        <p>Elite Trading Intelligence & Market Analytics Platform</p>
    </div>
    """, unsafe_allow_html=True)

def render_market_command_center():
    """Render market command center"""
    st.markdown("### 🎯 Market Command Center")
    
    # Mobile-friendly: 3 columns instead of 5
    col1, col2, col3 = st.columns(3)
    
    market_state, state_color = get_market_state()
    session_time = (datetime.now() - st.session_state.session_start).total_seconds() / 3600
    
    with col1:
        # Shorten text for mobile
        state_short = market_state.replace("TRADING", "").replace("MARKET", "").strip()
        st.metric("Market", state_short, get_market_time().strftime('%H:%M ET'))
    
    with col2:
        regime_short = st.session_state.market_regime.replace("_", " ").replace("VOLATILITY", "VOL")
        st.metric("Regime", regime_short, st.session_state.volatility_regime.replace("_VOL", ""))
    
    with col3:
        st.metric("Session", f"{session_time:.1f}h", f"{st.session_state.signals_generated} signals")
    
    # Second row for remaining metrics
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.metric("Opportunities", st.session_state.opportunities_today, "identified")
    
    with col5:
        st.metric("Sync Score", f"{st.session_state.market_sync_score:.1f}%", "real-time")
    
    with col6:
        # Add a useful metric like watchlist size
        st.metric("Watchlist", len(st.session_state.watchlist), "symbols")

def render_trading_intelligence():
    """Render elite trading intelligence dashboard"""
    st.markdown("### 📊 Trading Intelligence Matrix")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="trading-card">
            <h4 class="status-premium">⚓ SPX Anchor Engine</h4>
            <p><strong>Asian Session Analysis</strong></p>
            <ul>
                <li>ES Futures: 5:00-7:30 PM CT</li>
                <li>Skyline/Baseline: ✅ Active</li>
                <li>Slope Projections: Real-time</li>
                <li>Signal Generation: Live</li>
            </ul>
            <p><strong>Next Analysis:</strong> 17:00 CT</p>
            <p><strong>Status:</strong> <span class="status-bull">OPERATIONAL</span></p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="trading-card">
            <h4 class="status-premium">📈 Stock Anchor Matrix</h4>
            <p><strong>Mon/Tue Cross-Analysis</strong></p>
            <ul>
                <li>7 Mega-Cap Stocks</li>
                <li>Cross-Day Swing: ✅</li>
                <li>Individual Slopes</li>
                <li>Wed/Thu Signals</li>
            </ul>
            <p><strong>Portfolio:</strong> Tech Leaders</p>
            <p><strong>Analysis:</strong> <span class="status-bull">READY</span></p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        intelligence = st.session_state.market_intelligence
        active_count = len(intelligence)
        avg_rsi = np.mean([data.get('rsi', 50) for data in intelligence.values()]) if intelligence else 50
        
        rsi_signal = "OVERSOLD" if avg_rsi < 30 else "OVERBOUGHT" if avg_rsi > 70 else "NEUTRAL"
        rsi_color = "status-bull" if avg_rsi < 30 else "status-bear" if avg_rsi > 70 else "status-neutral"
        
        st.markdown(f"""
        <div class="trading-card">
            <h4 class="status-premium">🧠 Market Intelligence</h4>
            <p><strong>Real-Time Analytics</strong></p>
            <ul>
                <li>Symbols Tracked: {active_count}/8</li>
                <li>Average RSI: {avg_rsi:.1f}</li>
                <li>Market Regime: {st.session_state.market_regime}</li>
                <li>Fear/Greed: {st.session_state.fear_greed_index}</li>
            </ul>
            <p><strong>RSI Signal:</strong> <span class="{rsi_color}">{rsi_signal}</span></p>
            <p><strong>Data Quality:</strong> <span class="status-bull">PREMIUM</span></p>
        </div>
        """, unsafe_allow_html=True)

def render_live_market_matrix():
    """Render comprehensive live market matrix with REAL data"""
    st.markdown("### 📈 Live Market Matrix")
    
    intelligence = st.session_state.market_intelligence
    
    if not intelligence:
        st.warning("⏳ Loading market data...")
        return
    
    # Create market matrix dataframe with REAL data
    matrix_data = []
    
    for symbol, data in intelligence.items():
        # Use actual fetched data
        price = data.get('price', 0)
        change_pct = data.get('change_pct', 0)
        rsi = data.get('rsi', 50)
        volatility = data.get('volatility', 0)
        support = data.get('support', 0)
        resistance = data.get('resistance', 0)
        volume = data.get('volume', 0)
        
        # Determine trend direction from REAL momentum
        momentum = data.get('momentum_5d', 0)
        if momentum > 1:
            trend = "🟢 BULLISH"
        elif momentum < -1:
            trend = "🔴 BEARISH"
        else:
            trend = "🟡 NEUTRAL"
        
        # Risk assessment from REAL volatility
        if volatility > 30:
            risk_level = "HIGH"
        elif volatility > 20:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        matrix_data.append({
            'Symbol': symbol,
            'Price': f"${price:.2f}",
            'Change %': f"{change_pct:+.2f}%",
            'Volume': f"{volume:,.0f}",
            'RSI': f"{rsi:.1f}",
            'Volatility': f"{volatility:.1f}%",
            'Trend': trend,
            'Risk': risk_level,
            'Support': f"${support:.2f}",
            'Resistance': f"${resistance:.2f}"
        })
    
    if matrix_data:
        df = pd.DataFrame(matrix_data)
        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Symbol': st.column_config.TextColumn('Symbol', width='small'),
                'Price': st.column_config.TextColumn('Price', width='small'),
                'Change %': st.column_config.TextColumn('Change %', width='small'),
                'Volume': st.column_config.TextColumn('Volume', width='medium'),
                'RSI': st.column_config.TextColumn('RSI', width='small'),
                'Volatility': st.column_config.TextColumn('Vol %', width='small'),
                'Trend': st.column_config.TextColumn('Trend', width='medium'),
                'Risk': st.column_config.TextColumn('Risk', width='small'),
                'Support': st.column_config.TextColumn('Support', width='small'),
                'Resistance': st.column_config.TextColumn('Resistance', width='small')
            }
        )
        
        # Show last update time with better styling
        last_update = datetime.now().strftime('%H:%M:%S ET')
        st.markdown(f"""
        <div style="text-align: right; color: #94a3b8; font-size: 0.8rem; margin-top: 0.5rem;">
            Last updated: {last_update}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("No market data available")

def render_elite_insights():
    """Render elite market insights"""
    st.markdown("### 💡 Elite Market Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🎯 Today's Focus")
        
        intelligence = st.session_state.market_intelligence
        if intelligence:
            # Find most volatile stock
            most_volatile = max(intelligence.items(), key=lambda x: x[1].get('volatility', 0))
            
            # Find strongest momentum
            strongest_momentum = max(intelligence.items(), key=lambda x: x[1].get('momentum_5d', 0))
            
            # Find oversold/overbought
            rsi_values = [(k, v.get('rsi', 50)) for k, v in intelligence.items()]
            most_oversold = min(rsi_values, key=lambda x: x[1])
            most_overbought = max(rsi_values, key=lambda x: x[1])
            
            st.markdown(f"""
            **🔥 Highest Volatility:** {most_volatile[0]} ({most_volatile[1].get('volatility', 0):.1f}%)
            
            **⚡ Strongest Momentum:** {strongest_momentum[0]} ({strongest_momentum[1].get('momentum_5d', 0):+.1f}%)
            
            **📉 Most Oversold:** {most_oversold[0]} (RSI: {most_oversold[1]:.1f})
            
            **📈 Most Overbought:** {most_overbought[0]} (RSI: {most_overbought[1]:.1f})
            """, unsafe_allow_html=False)
        else:
            st.markdown("Loading market insights...", unsafe_allow_html=False)
    
    with col2:
        st.markdown("#### ⚡ Trading Alerts")
        
        # Generate dynamic alerts based on market conditions
        alerts = []
        
        if intelligence:
            for symbol, data in intelligence.items():
                rsi = data.get('rsi', 50)
                vol = data.get('volatility', 20)
                momentum = data.get('momentum_5d', 0)
                
                if rsi < 30 and momentum > 0:
                    alerts.append(f"🟢 {symbol}: Oversold bounce opportunity")
                elif rsi > 70 and momentum < 0:
                    alerts.append(f"🔴 {symbol}: Overbought reversal watch")
                elif vol > 35:
                    alerts.append(f"⚡ {symbol}: Extreme volatility - high risk/reward")
                elif abs(momentum) > 5:
                    alerts.append(f"🚀 {symbol}: Strong momentum - trend following")
        
        if alerts:
            for alert in alerts[:5]:  # Show top 5 alerts
                st.markdown(f"⚠️ {alert}", unsafe_allow_html=False)
        else:
            st.markdown("✅ No critical alerts - Market in balance", unsafe_allow_html=False)

def render_main_dashboard():
    """Render the main elite dashboard"""
    apply_elite_styling()
    
    # Update market intelligence
    update_market_intelligence()
    
    # Render all components
    render_elite_header()
    render_market_command_center()
    
    st.divider()
    
    render_trading_intelligence()
    
    st.divider()
    
    render_live_market_matrix()
    
    st.divider()
    
    render_elite_insights()
    
    # Elite footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; opacity: 0.8; padding: 1rem;">
        <strong>MarketLens Pro v5</strong> - Elite Trading Intelligence Platform | 
        Real-time market analytics and signal generation | 
        © 2024 Max Pointe Consulting
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class EliteMarketLens:
    """Elite MarketLens Pro application"""
    
    def __init__(self):
        initialize_elite_session()
    
    def run(self):
        """Run the elite trading platform"""
        render_main_dashboard()
        
        # Auto-refresh during market hours
        market_state, _ = get_market_state()
        if "LIVE" in market_state or "PRE" in market_state:
            time.sleep(3)
            st.rerun()

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

def main():
    """Main application entry point"""
    app = EliteMarketLens()
    app.run()

if __name__ == "__main__":
    main()
