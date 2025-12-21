"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                           SPX PROPHET v5.1 PREMIUM                            ║
║                    The Complete 0DTE Trading System                           ║
║                       NEOMORPHIC UI + LIVE OPTIONS PRICING                    ║
║                                                                               ║
║  NEW IN v5.1:                                                                 ║
║  • Neomorphic UI Design - Soft shadows, depth, 3D tactile cards              ║
║  • Live SPX Options Pricing via Polygon                                      ║
║  • SPY Fallback with automatic conversion when SPX unavailable               ║
║  • Real bid/ask spreads for accurate entry planning                          ║
║  • Greeks display (Delta, Gamma, Theta)                                      ║
║  • Smart entry recommendations based on premium analysis                      ║
║                                                                               ║
║  POLYGON REQUIREMENTS:                                                        ║
║  • Options data requires Polygon Options subscription                         ║
║  • SPX options: O:SPX{DATE}{C/P}{STRIKE}                                     ║
║  • SPY options: O:SPY{DATE}{C/P}{STRIKE} (÷10 strike)                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, time
import pytz
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import streamlit.components.v1 as components
import yfinance as yf

# ============================================================================
# POLYGON.IO CONFIGURATION
# ============================================================================

POLYGON_API_KEY = "DCWuTS1R_fukpfjgf7QnXrLTEOS_giq6"
POLYGON_BASE_URL = "https://api.polygon.io"

POLYGON_SPX = "I:SPX"
POLYGON_VIX = "I:VIX"

POLYGON_HAS_INDICES = True
POLYGON_HAS_OPTIONS = True  # Options access
POLYGON_HAS_STOCKS = True

# ============================================================================
# CONFIGURATION
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

VIX_TO_SPX_MOVE = {
    0.10: (35, 40),
    0.15: (40, 45),
    0.20: (45, 50),
    0.25: (50, 55),
    0.30: (55, 60),
}

SLOPE_PER_30MIN = 0.45
MIN_CONE_WIDTH = 18.0
CONFLUENCE_THRESHOLD = 5.0
STOP_LOSS_PTS = 6.0
STRIKE_OTM_DISTANCE = 17.5
DELTA = 0.33
CONTRACT_MULTIPLIER = 100
LOW_VIX_THRESHOLD = 13.0
NARROW_CONE_THRESHOLD = 25.0

def get_ct_now() -> datetime:
    return datetime.now(CT_TZ)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Pivot:
    price: float
    time: datetime
    name: str
    is_secondary: bool = False
    price_for_ascending: float = 0.0
    price_for_descending: float = 0.0
    
    def __post_init__(self):
        if self.price_for_ascending == 0.0:
            self.price_for_ascending = self.price
        if self.price_for_descending == 0.0:
            self.price_for_descending = self.price

@dataclass
class Cone:
    name: str
    pivot: Pivot
    ascending_rail: float
    descending_rail: float
    width: float
    blocks: int

@dataclass
class VIXZone:
    bottom: float
    top: float
    current: float
    position_pct: float
    status: str
    bias: str
    breakout_time: str
    zones_above: List[float]
    zones_below: List[float]
    zone_size: float = 0.15
    expected_move: tuple = (40, 45)
    auto_detected: bool = False

@dataclass
class OptionQuote:
    """Live option pricing data"""
    ticker: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    mid: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_vol: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    underlying_price: float = 0.0
    in_the_money: bool = False
    
@dataclass
class TradeSetup:
    direction: str
    cone_name: str
    cone_width: float
    entry: float
    stop: float
    target_25: float  # T1 = 25% of cone
    target_50: float  # T2 = 50% of cone
    target_75: float  # T3 = 75% of cone
    strike: int
    spx_pts_25: float
    spx_pts_50: float
    spx_pts_75: float
    profit_25: float
    profit_50: float
    profit_75: float
    risk_per_contract: float
    rr_ratio: float
    distance: float
    is_active: bool = False
    # Options pricing - simplified
    current_option_price: float = 0.0  # Current mid price (SPX equivalent)
    est_entry_price_10am: float = 0.0  # Estimated price when SPX hits entry at 10AM
    spy_strike_used: int = 0
    using_spy: bool = False
    option_delta: float = 0.33  # Estimated delta for calculations
    # Stop loss details
    stop_loss_pts: float = 6.0  # Points from entry
    stop_loss_dollars: float = 0.0  # Dollar amount per contract
    # Risk/Reward in dollars
    risk_dollars: float = 0.0
    reward_t1_dollars: float = 0.0  # T1 = 25%
    reward_t2_dollars: float = 0.0  # T2 = 50%
    reward_t3_dollars: float = 0.0  # T3 = 75%

@dataclass
class ESData:
    """E-mini S&P 500 Futures Data"""
    current_price: float = 0.0
    prior_close: float = 0.0
    overnight_change: float = 0.0
    overnight_change_pct: float = 0.0
    spx_offset: float = 0.0  # ES - SPX (typically 9-10 pts)
    spx_equivalent: float = 0.0
    direction: str = "FLAT"  # UP, DOWN, FLAT
    likely_cone: str = ""  # HIGH, LOW, or empty
    vix_aligned: bool = False
    conflict_warning: str = ""

@dataclass
class ActiveConeInfo:
    """Information about which cone price is currently in"""
    cone_name: str = ""
    is_inside: bool = False
    ascending_rail: float = 0.0
    descending_rail: float = 0.0
    cone_width: float = 0.0
    distance_to_ascending: float = 0.0
    distance_to_descending: float = 0.0
    position_pct: float = 0.0  # 0% = at descending, 100% = at ascending
    nearest_rail: str = ""  # "ascending" or "descending"
    nearest_rail_price: float = 0.0
    at_rail: bool = False  # Within 5 pts of a rail
    trade_direction: str = ""  # CALLS or PUTS based on nearest rail

@dataclass
class DayAssessment:
    tradeable: bool
    score: int
    reasons: List[str]
    warnings: List[str]
    recommendation: str

@dataclass
class PolygonStatus:
    connected: bool = False
    last_update: Optional[datetime] = None
    data_delay: str = "Unknown"
    spx_price: float = 0.0
    vix_price: float = 0.0
    error_message: str = ""
    options_available: bool = False

# ============================================================================
# POLYGON API - OPTIONS PRICING
# ============================================================================

def build_option_ticker(underlying: str, expiry_date: datetime, strike: float, option_type: str) -> str:
    """
    Build Polygon option ticker symbol.
    Format: O:{UNDERLYING}{YYMMDD}{C/P}{STRIKE*1000}
    Example: O:SPX231215C06000000 for SPX Dec 15 2023 6000 Call
    """
    date_str = expiry_date.strftime("%y%m%d")
    cp = "C" if option_type.upper() in ["CALL", "C"] else "P"
    # Strike is multiplied by 1000 and zero-padded to 8 digits
    strike_str = f"{int(strike * 1000):08d}"
    return f"O:{underlying}{date_str}{cp}{strike_str}"

@st.cache_data(ttl=30)
def polygon_get_option_quote(option_ticker: str) -> Optional[OptionQuote]:
    """Get real-time option quote from Polygon."""
    try:
        # Get last quote
        url = f"{POLYGON_BASE_URL}/v3/quotes/{option_ticker}"
        params = {"limit": 1, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        
        quote = OptionQuote(ticker=option_ticker)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                result = data["results"][0]
                quote.bid = result.get("bid_price", 0) or 0
                quote.ask = result.get("ask_price", 0) or 0
                quote.mid = round((quote.bid + quote.ask) / 2, 2) if quote.bid and quote.ask else 0
        
        # Get last trade
        url2 = f"{POLYGON_BASE_URL}/v3/trades/{option_ticker}"
        params2 = {"limit": 1, "apiKey": POLYGON_API_KEY}
        response2 = requests.get(url2, params=params2, timeout=10)
        
        if response2.status_code == 200:
            data2 = response2.json()
            if data2.get("results") and len(data2["results"]) > 0:
                quote.last = data2["results"][0].get("price", 0) or 0
        
        # Get snapshot for greeks and OI
        url3 = f"{POLYGON_BASE_URL}/v3/snapshot/options/{option_ticker}"
        params3 = {"apiKey": POLYGON_API_KEY}
        response3 = requests.get(url3, params=params3, timeout=10)
        
        if response3.status_code == 200:
            data3 = response3.json()
            if data3.get("results"):
                result = data3["results"]
                quote.open_interest = result.get("open_interest", 0) or 0
                quote.implied_vol = result.get("implied_volatility", 0) or 0
                
                greeks = result.get("greeks", {})
                quote.delta = greeks.get("delta", 0) or 0
                quote.gamma = greeks.get("gamma", 0) or 0
                quote.theta = greeks.get("theta", 0) or 0
                quote.vega = greeks.get("vega", 0) or 0
                
                quote.underlying_price = result.get("underlying_asset", {}).get("price", 0) or 0
        
        # If we got any data, return it
        if quote.bid > 0 or quote.ask > 0 or quote.last > 0:
            return quote
        return None
        
    except Exception as e:
        return None

@st.cache_data(ttl=30)
def polygon_get_options_chain_snapshot(underlying: str, expiry_date: str, option_type: str = "call") -> List[Dict]:
    """Get options chain snapshot for a specific expiry."""
    try:
        url = f"{POLYGON_BASE_URL}/v3/snapshot/options/{underlying}"
        params = {
            "expiration_date": expiry_date,
            "contract_type": option_type,
            "limit": 250,
            "apiKey": POLYGON_API_KEY
        }
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])
        return []
    except:
        return []

def get_next_trading_day() -> datetime:
    """
    Get the next trading day (for 0DTE options).
    - If today is a weekday and market is open/will open, use today
    - If today is Saturday, use Monday
    - If today is Sunday, use Monday
    - If today is a weekday but after 4pm CT, use next weekday
    
    Note: This doesn't account for market holidays - would need a holiday calendar for that.
    """
    now = get_ct_now()
    today = now.date()
    weekday = today.weekday()  # Monday=0, Sunday=6
    current_time = now.time()
    market_close = time(16, 0)  # 4:00 PM CT
    
    if weekday == 5:  # Saturday
        # Next trading day is Monday
        next_day = today + timedelta(days=2)
    elif weekday == 6:  # Sunday
        # Next trading day is Monday
        next_day = today + timedelta(days=1)
    elif current_time > market_close:
        # After market close on a weekday, use next weekday
        if weekday == 4:  # Friday after close
            next_day = today + timedelta(days=3)  # Monday
        else:
            next_day = today + timedelta(days=1)
    else:
        # During trading hours or before market open on a weekday
        next_day = today
    
    return datetime.combine(next_day, time(0, 0))

def get_trading_day_label() -> str:
    """Get a human-readable label for the trading day being displayed."""
    now = get_ct_now()
    today = now.date()
    next_trading = get_next_trading_day().date()
    
    if next_trading == today:
        return "Today"
    elif next_trading == today + timedelta(days=1):
        return "Tomorrow"
    else:
        return next_trading.strftime("%A, %b %d")

def estimate_option_price_at_entry(current_price: float, current_spx: float, entry_spx: float, 
                                    strike: float, direction: str, delta: float = 0.33) -> float:
    """
    Estimate what the option price will be when SPX reaches the entry point.
    
    Uses delta approximation:
    - If SPX moves toward the strike (option goes more ITM), price increases
    - If SPX moves away from strike (option goes more OTM), price decreases
    
    For CALLS: entry is at descending rail (lower than current if we're above)
    For PUTS: entry is at ascending rail (higher than current if we're below)
    """
    spx_move = entry_spx - current_spx  # Positive = SPX going up, Negative = SPX going down
    
    if direction == "CALLS":
        # Call value increases when SPX goes up
        price_change = spx_move * delta
    else:
        # Put value increases when SPX goes down
        price_change = -spx_move * delta
    
    estimated_price = current_price + price_change
    
    # Round to nearest 0.10 and floor at 0.10
    return max(round(estimated_price * 10) / 10, 0.10)

def round_to_ten_cents(value: float) -> float:
    """Round a price to the nearest $0.10"""
    return round(value * 10) / 10

def get_option_pricing_for_setup(setup: TradeSetup, current_spx: float) -> TradeSetup:
    """
    Fetch option pricing and estimate entry price at 10 AM.
    
    Returns:
    - current_option_price: What the option costs RIGHT NOW (rounded to $0.10)
    - est_entry_price_10am: What it should cost when SPX hits the entry rail at 10 AM (rounded to $0.10)
    """
    expiry = get_next_trading_day()
    option_type = "C" if setup.direction == "CALLS" else "P"
    
    current_mid = 0.0
    delta = 0.33  # Default delta assumption for OTM options
    
    # Try SPX first
    spx_ticker = build_option_ticker("SPX", expiry, setup.strike, option_type)
    spx_quote = polygon_get_option_quote(spx_ticker)
    
    if spx_quote and (spx_quote.bid > 0 or spx_quote.ask > 0):
        setup.using_spy = False
        current_mid = spx_quote.mid if spx_quote.mid > 0 else (spx_quote.bid + spx_quote.ask) / 2
        if spx_quote.delta and abs(spx_quote.delta) > 0:
            delta = abs(spx_quote.delta)
    else:
        # Fallback to SPY (strike ÷ 10)
        spy_strike = round(setup.strike / 10)
        setup.spy_strike_used = spy_strike
        spy_ticker = build_option_ticker("SPY", expiry, spy_strike, option_type)
        spy_quote = polygon_get_option_quote(spy_ticker)
        
        if spy_quote and (spy_quote.bid > 0 or spy_quote.ask > 0):
            setup.using_spy = True
            # Convert SPY to SPX equivalent (multiply by 10)
            spy_mid = spy_quote.mid if spy_quote.mid > 0 else (spy_quote.bid + spy_quote.ask) / 2
            current_mid = spy_mid * 10
            if spy_quote.delta and abs(spy_quote.delta) > 0:
                delta = abs(spy_quote.delta)
    
    # Set current price (rounded to nearest $0.10)
    setup.current_option_price = round_to_ten_cents(current_mid)
    setup.option_delta = delta
    
    # Estimate price at 10 AM entry (already rounds to $0.10)
    if current_mid > 0:
        setup.est_entry_price_10am = estimate_option_price_at_entry(
            current_price=current_mid,
            current_spx=current_spx,
            entry_spx=setup.entry,
            strike=setup.strike,
            direction=setup.direction,
            delta=delta
        )
    else:
        # If no current price, estimate based on typical OTM pricing
        # Rough estimate: $0.33 per point of expected move × delta
        distance_to_strike = abs(setup.entry - setup.strike)
        setup.est_entry_price_10am = round_to_ten_cents(max(distance_to_strike * delta * 0.5, 1.00))
    
    return setup

# ============================================================================
# POLYGON API - MARKET DATA
# ============================================================================

@st.cache_data(ttl=30)
def polygon_get_snapshot(ticker: str) -> Optional[Dict]:
    """Get current snapshot for indices."""
    try:
        url = f"{POLYGON_BASE_URL}/v3/snapshot?ticker.any_of={ticker}"
        params = {"apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                result = data["results"][0]
                return {
                    "price": result.get("value", 0),
                    "change": result.get("session", {}).get("change", 0),
                    "change_pct": result.get("session", {}).get("change_percent", 0),
                    "timestamp": result.get("last_updated", 0)
                }
        return None
    except:
        return None

@st.cache_data(ttl=60)
def polygon_get_overnight_vix_range(session_date: datetime) -> Optional[Dict]:
    """Get VIX overnight range 2am-6am CT."""
    try:
        session_date_str = session_date.strftime("%Y-%m-%d")
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{POLYGON_VIX}/range/1/minute/{session_date_str}/{session_date_str}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                df = pd.DataFrame(data["results"])
                df['datetime'] = pd.to_datetime(df['t'], unit='ms', utc=True).dt.tz_convert(CT_TZ)
                
                zone_start = CT_TZ.localize(datetime.combine(session_date.date(), time(2, 0)))
                zone_end = CT_TZ.localize(datetime.combine(session_date.date(), time(6, 0)))
                
                zone_df = df[(df['datetime'] >= zone_start) & (df['datetime'] <= zone_end)]
                
                if not zone_df.empty:
                    return {
                        'bottom': round(float(zone_df['l'].min()), 2),
                        'top': round(float(zone_df['h'].max()), 2),
                        'zone_size': round(float(zone_df['h'].max()) - float(zone_df['l'].min()), 2),
                        'bar_count': len(zone_df)
                    }
        return None
    except:
        return None

@st.cache_data(ttl=60)
def polygon_get_prior_day_data(ticker: str) -> Optional[Dict]:
    """Get prior trading day OHLC."""
    try:
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/prev"
        params = {"adjusted": "true", "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                r = data["results"][0]
                return {"open": r.get("o", 0), "high": r.get("h", 0), "low": r.get("l", 0), "close": r.get("c", 0)}
        return None
    except:
        return None

# ============================================================================
# FALLBACK DATA
# ============================================================================

@st.cache_data(ttl=60)
def yf_fetch_current_spx() -> float:
    try:
        spx = yf.Ticker("^GSPC")
        data = spx.history(period='1d', interval='1m')
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    return 0.0

@st.cache_data(ttl=60)
def yf_fetch_current_vix() -> float:
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period='1d', interval='1m')
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    return 0.0

@st.cache_data(ttl=300)
def fetch_historical_day_data(ticker: str, date: datetime) -> Dict:
    """
    Fetch OHLC data for a specific historical date.
    Returns: {'open': x, 'high': x, 'low': x, 'close': x}
    """
    try:
        t = yf.Ticker(ticker)
        # Fetch a few days around the target date to ensure we get it
        start = date - timedelta(days=5)
        end = date + timedelta(days=1)
        data = t.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), interval='1d')
        
        if not data.empty:
            # Find the exact date
            target_str = date.strftime('%Y-%m-%d')
            for idx in data.index:
                if idx.strftime('%Y-%m-%d') == target_str:
                    row = data.loc[idx]
                    return {
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close'])
                    }
            
            # If exact date not found, return last available
            row = data.iloc[-1]
            return {
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close'])
            }
    except Exception as e:
        pass
    return {'open': 0, 'high': 0, 'low': 0, 'close': 0}

@st.cache_data(ttl=300)
def fetch_historical_intraday_data(ticker: str, date: datetime) -> pd.DataFrame:
    """
    Fetch intraday data for a specific historical date.
    Returns DataFrame with OHLCV data.
    """
    try:
        t = yf.Ticker(ticker)
        # For intraday, we need to be within 60 days
        start = date
        end = date + timedelta(days=1)
        data = t.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), interval='30m')
        return data
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def yf_fetch_es_futures() -> Dict:
    """
    Fetch E-mini S&P 500 Futures (ES=F) data from Yahoo Finance.
    Returns current price, prior close, and overnight change.
    """
    try:
        es = yf.Ticker("ES=F")
        
        # Get current data
        data = es.history(period='2d', interval='1m')
        if not data.empty:
            current_price = float(data['Close'].iloc[-1])
            
            # Get prior close from info or calculate from 2-day data
            info = es.info
            prior_close = info.get('previousClose', 0) or info.get('regularMarketPreviousClose', 0)
            
            # If prior close not available, estimate from 2-day data
            if prior_close == 0:
                # Find yesterday's last bar
                today = datetime.now().date()
                yesterday_data = data[data.index.date < today]
                if not yesterday_data.empty:
                    prior_close = float(yesterday_data['Close'].iloc[-1])
            
            overnight_change = current_price - prior_close if prior_close > 0 else 0
            overnight_change_pct = (overnight_change / prior_close * 100) if prior_close > 0 else 0
            
            return {
                'current': round(current_price, 2),
                'prior_close': round(prior_close, 2),
                'change': round(overnight_change, 2),
                'change_pct': round(overnight_change_pct, 2)
            }
    except Exception as e:
        pass
    
    return {'current': 0, 'prior_close': 0, 'change': 0, 'change_pct': 0}

def analyze_es_data(es_data: Dict, current_spx: float, vix_zone: 'VIXZone') -> ESData:
    """
    Analyze ES futures data in context of SPX and VIX.
    
    Logic:
    - ES up significantly → likely in HIGH cone
    - ES down significantly → likely in LOW cone
    - ES direction is inverse of VIX breakout (ES up = VIX down)
    """
    es = ESData()
    
    if es_data.get('current', 0) == 0:
        return es
    
    es.current_price = es_data['current']
    es.prior_close = es_data['prior_close']
    es.overnight_change = es_data['change']
    es.overnight_change_pct = es_data['change_pct']
    
    # Calculate offset (typically 9-10 points)
    if current_spx > 0:
        es.spx_offset = round(es.current_price - current_spx, 2)
        es.spx_equivalent = round(es.current_price - es.spx_offset, 2)
    
    # Determine direction (threshold: 5 points for significance)
    if es.overnight_change >= 5:
        es.direction = "UP"
        es.likely_cone = "HIGH"
    elif es.overnight_change <= -5:
        es.direction = "DOWN"
        es.likely_cone = "LOW"
    else:
        es.direction = "FLAT"
        es.likely_cone = ""
    
    # Check VIX alignment (ES and VIX should be inverse)
    # ES up + VIX below zone (bullish) = ALIGNED
    # ES down + VIX above zone (bearish) = ALIGNED
    # Otherwise = CONFLICT
    
    if es.direction == "UP":
        if vix_zone.status == "BELOW_ZONE":
            es.vix_aligned = True
        elif vix_zone.status == "ABOVE_ZONE":
            es.vix_aligned = False
            es.conflict_warning = "ES bullish but VIX bearish - wait for confirmation"
        else:
            es.vix_aligned = False
            es.conflict_warning = "VIX in zone - wait for breakout"
    elif es.direction == "DOWN":
        if vix_zone.status == "ABOVE_ZONE":
            es.vix_aligned = True
        elif vix_zone.status == "BELOW_ZONE":
            es.vix_aligned = False
            es.conflict_warning = "ES bearish but VIX bullish - wait for confirmation"
        else:
            es.vix_aligned = False
            es.conflict_warning = "VIX in zone - wait for breakout"
    else:
        es.vix_aligned = False
        es.conflict_warning = "ES flat - no clear direction"
    
    return es

# ============================================================================
# VIX ZONE LOGIC
# ============================================================================

def get_expected_move(zone_size: float) -> Tuple[int, int]:
    for threshold, move in sorted(VIX_TO_SPX_MOVE.items()):
        if zone_size <= threshold:
            return move
    return (60, 70)

def analyze_vix_zone(current: float, bottom: float, top: float) -> VIXZone:
    zone_size = round(top - bottom, 2)
    expected_move = get_expected_move(zone_size)
    
    if top - bottom > 0:
        position_pct = ((current - bottom) / (top - bottom)) * 100
    else:
        position_pct = 50.0
    
    position_pct = max(0, min(100, position_pct))
    
    zones_above = [round(top + (i * zone_size), 2) for i in range(1, 4)]
    zones_below = [round(bottom - (i * zone_size), 2) for i in range(1, 4)]
    
    if current < bottom:
        status = "BELOW_ZONE"
        bias = "CALLS"
    elif current > top:
        status = "ABOVE_ZONE"
        bias = "PUTS"
    else:
        status = "IN_ZONE"
        if position_pct < 30:
            bias = "CALLS"
        elif position_pct > 70:
            bias = "PUTS"
        else:
            bias = "WAIT"
    
    ct_now = get_ct_now()
    breakout_time = ""
    if time(6, 0) <= ct_now.time() <= time(6, 30):
        breakout_time = "RELIABLE BREAKOUT WINDOW"
    elif time(6, 30) < ct_now.time() <= time(9, 30):
        breakout_time = "DANGER ZONE - High reversal risk"
    
    return VIXZone(
        bottom=bottom, top=top, current=current,
        position_pct=position_pct, status=status, bias=bias,
        breakout_time=breakout_time, zones_above=zones_above,
        zones_below=zones_below, zone_size=zone_size, expected_move=expected_move
    )

# ============================================================================
# CONE & SETUP LOGIC
# ============================================================================

def count_blocks(start_time: datetime, eval_time: datetime) -> int:
    """
    Count 30-minute blocks from start_time to eval_time.
    
    Trading sessions (all times CT):
    - RTH: 8:30 AM - 3:00 PM
    - Post-RTH: 3:00 PM - 4:00 PM (2 candles)
    - Maintenance: 4:00 PM - 5:00 PM (NO trading)
    - Overnight: 5:00 PM - 8:30 AM next day
    
    Weekend: Friday 4:00 PM - Sunday 5:00 PM = NO candles
    
    The pivot candle is NOT counted - start_time should already be pivot + 30 min.
    """
    MAINTENANCE_START = time(16, 0)  # 4:00 PM
    MAINTENANCE_END = time(17, 0)    # 5:00 PM
    
    # Round start_time UP to next 30-min boundary
    start_minute = start_time.minute
    if start_minute == 0 or start_minute == 30:
        cone_start = start_time
    elif start_minute < 30:
        cone_start = start_time.replace(minute=30, second=0, microsecond=0)
    else:
        cone_start = (start_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    
    # Ensure cone_start is timezone-aware
    if cone_start.tzinfo is None:
        cone_start = CT_TZ.localize(cone_start)
    
    total_blocks = 0
    current = cone_start
    
    # Safety limit to prevent infinite loops
    max_iterations = 1000
    iterations = 0
    
    while current < eval_time and iterations < max_iterations:
        iterations += 1
        current_time = current.time()
        current_weekday = current.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        
        # Check if we're in weekend dead zone (Friday 4 PM - Sunday 5 PM)
        is_friday_after_close = current_weekday == 4 and current_time >= MAINTENANCE_START
        is_saturday = current_weekday == 5
        is_sunday_before_open = current_weekday == 6 and current_time < MAINTENANCE_END
        
        if is_friday_after_close or is_saturday or is_sunday_before_open:
            # Jump to Sunday 5:00 PM
            days_until_sunday = (6 - current_weekday) % 7
            if days_until_sunday == 0 and current_time >= MAINTENANCE_END:
                days_until_sunday = 7  # Next Sunday
            sunday = current.date() + timedelta(days=days_until_sunday)
            current = CT_TZ.localize(datetime.combine(sunday, MAINTENANCE_END))
            continue
        
        # Check if we're in maintenance window (4 PM - 5 PM on weekdays)
        if MAINTENANCE_START <= current_time < MAINTENANCE_END:
            # Jump to 5:00 PM (end of maintenance)
            current = CT_TZ.localize(datetime.combine(current.date(), MAINTENANCE_END))
            continue
        
        # Calculate next block
        next_block = current + timedelta(minutes=30)
        
        # Don't count if next block exceeds eval_time
        if next_block > eval_time:
            break
        
        # Check if next block would cross into maintenance
        if current_time < MAINTENANCE_START and next_block.time() > MAINTENANCE_START:
            # This block ends at 4 PM, count it, then jump to 5 PM
            total_blocks += 1
            current = CT_TZ.localize(datetime.combine(current.date(), MAINTENANCE_END))
            continue
        
        # Normal block - count it
        total_blocks += 1
        current = next_block
    
    return max(total_blocks, 1)

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    cones = []
    for pivot in pivots:
        start_time = pivot.time + timedelta(minutes=30)
        blocks = count_blocks(start_time, eval_time)
        ascending = pivot.price_for_ascending + (blocks * SLOPE_PER_30MIN)
        descending = pivot.price_for_descending - (blocks * SLOPE_PER_30MIN)
        width = ascending - descending
        cones.append(Cone(
            name=pivot.name, pivot=pivot,
            ascending_rail=round(ascending, 2),
            descending_rail=round(descending, 2),
            width=round(width, 2), blocks=blocks
        ))
    return cones

def find_active_cone(price: float, cones: List[Cone]) -> Dict:
    result = {'inside_cone': None, 'nearest_cone': None, 'distance': 0, 'at_rail': False, 'rail_type': None}
    if not cones:
        return result
    
    for cone in cones:
        if cone.descending_rail <= price <= cone.ascending_rail:
            result['inside_cone'] = cone
            dist_asc = cone.ascending_rail - price
            dist_desc = price - cone.descending_rail
            if dist_asc <= 3:
                result['at_rail'] = True
                result['rail_type'] = 'ascending'
                result['distance'] = round(dist_asc, 2)
            elif dist_desc <= 3:
                result['at_rail'] = True
                result['rail_type'] = 'descending'
                result['distance'] = round(dist_desc, 2)
            return result
    
    min_dist = float('inf')
    for cone in cones:
        for rail, rtype in [(cone.ascending_rail, 'ascending'), (cone.descending_rail, 'descending')]:
            d = abs(price - rail)
            if d < min_dist:
                min_dist = d
                result['nearest_cone'] = cone
                result['rail_type'] = rtype
                result['distance'] = round(d, 2)
    return result

def get_detailed_active_cone(price: float, cones: List[Cone]) -> ActiveConeInfo:
    """
    Get detailed information about which cone price is currently in.
    Returns ActiveConeInfo with position, distances, and trade direction.
    """
    info = ActiveConeInfo()
    
    if not cones:
        return info
    
    # First, check if we're inside any cone
    for cone in cones:
        if cone.descending_rail <= price <= cone.ascending_rail:
            info.cone_name = cone.name
            info.is_inside = True
            info.ascending_rail = cone.ascending_rail
            info.descending_rail = cone.descending_rail
            info.cone_width = cone.width
            info.distance_to_ascending = round(cone.ascending_rail - price, 2)
            info.distance_to_descending = round(price - cone.descending_rail, 2)
            
            # Calculate position percentage (0% = at descending, 100% = at ascending)
            info.position_pct = round((price - cone.descending_rail) / cone.width * 100, 1)
            
            # Determine nearest rail and trade direction
            if info.distance_to_ascending <= info.distance_to_descending:
                info.nearest_rail = "ascending"
                info.nearest_rail_price = cone.ascending_rail
                info.trade_direction = "PUTS"
            else:
                info.nearest_rail = "descending"
                info.nearest_rail_price = cone.descending_rail
                info.trade_direction = "CALLS"
            
            # Check if at rail (within 5 pts)
            info.at_rail = min(info.distance_to_ascending, info.distance_to_descending) <= 5
            
            return info
    
    # Not inside any cone - find nearest
    min_dist = float('inf')
    nearest_cone = None
    nearest_rail_type = ""
    
    for cone in cones:
        for rail_price, rail_type in [(cone.ascending_rail, 'ascending'), (cone.descending_rail, 'descending')]:
            d = abs(price - rail_price)
            if d < min_dist:
                min_dist = d
                nearest_cone = cone
                nearest_rail_type = rail_type
                info.nearest_rail_price = rail_price
    
    if nearest_cone:
        info.cone_name = nearest_cone.name
        info.is_inside = False
        info.ascending_rail = nearest_cone.ascending_rail
        info.descending_rail = nearest_cone.descending_rail
        info.cone_width = nearest_cone.width
        info.distance_to_ascending = round(abs(nearest_cone.ascending_rail - price), 2)
        info.distance_to_descending = round(abs(price - nearest_cone.descending_rail), 2)
        info.nearest_rail = nearest_rail_type
        info.trade_direction = "PUTS" if nearest_rail_type == "ascending" else "CALLS"
        info.at_rail = min_dist <= 5
    
    return info

def generate_setups(cones: List[Cone], current_price: float, vix_bias: str) -> List[TradeSetup]:
    setups = []
    for cone in cones:
        if cone.width < MIN_CONE_WIDTH:
            continue
        
        # CALLS - Entry at descending rail, targets going UP
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        t25_c = round(entry_c + cone.width * 0.25, 2)  # T1 = 25%
        t50_c = round(entry_c + cone.width * 0.50, 2)  # T2 = 50%
        t75_c = round(entry_c + cone.width * 0.75, 2)  # T3 = 75%
        strike_c = int(round((entry_c - STRIKE_OTM_DISTANCE) / 5) * 5)
        
        # Calculate stop loss and risk/reward in dollars
        stop_loss_dollars_c = round(STOP_LOSS_PTS * DELTA * CONTRACT_MULTIPLIER / 10) * 10  # Round to nearest 10
        reward_t1_c = round(cone.width * 0.25 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t2_c = round(cone.width * 0.50 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t3_c = round(cone.width * 0.75 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        
        setup_c = TradeSetup(
            direction="CALLS", cone_name=cone.name, cone_width=cone.width,
            entry=entry_c, stop=round(entry_c - STOP_LOSS_PTS, 2),
            target_25=t25_c, target_50=t50_c, target_75=t75_c,
            strike=strike_c,
            spx_pts_25=round(cone.width * 0.25, 2),
            spx_pts_50=round(cone.width * 0.50, 2),
            spx_pts_75=round(cone.width * 0.75, 2),
            profit_25=reward_t1_c,
            profit_50=reward_t2_c,
            profit_75=reward_t3_c,
            risk_per_contract=stop_loss_dollars_c,
            rr_ratio=round((cone.width * 0.50) / STOP_LOSS_PTS, 2),  # R:R based on T2
            distance=round(dist_c, 1),
            is_active=(dist_c <= 5 and vix_bias in ["CALLS", "WAIT"]),
            stop_loss_pts=STOP_LOSS_PTS,
            stop_loss_dollars=stop_loss_dollars_c,
            risk_dollars=stop_loss_dollars_c,
            reward_t1_dollars=reward_t1_c,
            reward_t2_dollars=reward_t2_c,
            reward_t3_dollars=reward_t3_c
        )
        setups.append(setup_c)
        
        # PUTS - Entry at ascending rail, targets going DOWN
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        t25_p = round(entry_p - cone.width * 0.25, 2)  # T1 = 25%
        t50_p = round(entry_p - cone.width * 0.50, 2)  # T2 = 50%
        t75_p = round(entry_p - cone.width * 0.75, 2)  # T3 = 75%
        # OTM put strike should be BELOW entry price (entry - distance)
        strike_p = int(round((entry_p - STRIKE_OTM_DISTANCE) / 5) * 5)
        
        # Calculate stop loss and risk/reward in dollars
        stop_loss_dollars_p = round(STOP_LOSS_PTS * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t1_p = round(cone.width * 0.25 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t2_p = round(cone.width * 0.50 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t3_p = round(cone.width * 0.75 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        
        setup_p = TradeSetup(
            direction="PUTS", cone_name=cone.name, cone_width=cone.width,
            entry=entry_p, stop=round(entry_p + STOP_LOSS_PTS, 2),
            target_25=t25_p, target_50=t50_p, target_75=t75_p,
            strike=strike_p,
            spx_pts_25=round(cone.width * 0.25, 2),
            spx_pts_50=round(cone.width * 0.50, 2),
            spx_pts_75=round(cone.width * 0.75, 2),
            profit_25=reward_t1_p,
            profit_50=reward_t2_p,
            profit_75=reward_t3_p,
            risk_per_contract=stop_loss_dollars_p,
            rr_ratio=round((cone.width * 0.50) / STOP_LOSS_PTS, 2),
            distance=round(dist_p, 1),
            is_active=(dist_p <= 5 and vix_bias in ["PUTS", "WAIT"]),
            stop_loss_pts=STOP_LOSS_PTS,
            stop_loss_dollars=stop_loss_dollars_p,
            risk_dollars=stop_loss_dollars_p,
            reward_t1_dollars=reward_t1_p,
            reward_t2_dollars=reward_t2_p,
            reward_t3_dollars=reward_t3_p
        )
        setups.append(setup_p)
    
    return setups

def assess_day(vix: VIXZone, cones: List[Cone]) -> DayAssessment:
    score = 50
    reasons = []
    warnings = []
    
    if vix.zone_size >= 0.15:
        score += 15
        reasons.append(f"Good VIX zone size: {vix.zone_size}")
    else:
        score -= 10
        warnings.append(f"Tight VIX zone: {vix.zone_size}")
    
    if vix.current < LOW_VIX_THRESHOLD:
        score -= 15
        warnings.append(f"Low VIX ({vix.current}) = choppy conditions")
    
    wide_cones = [c for c in cones if c.width >= NARROW_CONE_THRESHOLD]
    if len(wide_cones) >= 2:
        score += 20
        reasons.append(f"{len(wide_cones)} wide cones available")
    elif len(wide_cones) == 1:
        score += 10
        reasons.append("1 wide cone available")
    else:
        score -= 15
        warnings.append("No wide cones - limited setups")
    
    score = max(0, min(100, score))
    
    if score >= 70:
        rec = "FULL"
    elif score >= 50:
        rec = "REDUCED"
    else:
        rec = "SKIP"
    
    return DayAssessment(tradeable=score >= 50, score=score, reasons=reasons, warnings=warnings, recommendation=rec)

# ============================================================================
# NEOMORPHIC UI RENDERING
# ============================================================================

def render_neomorphic_dashboard(spx: float, vix: VIXZone, cones: List[Cone], setups: List[TradeSetup],
                                 assessment: DayAssessment, prior: Dict, active_cone_info: Dict = None,
                                 polygon_status: PolygonStatus = None, pivots: List[Pivot] = None,
                                 es_data: ESData = None, detailed_cone: ActiveConeInfo = None,
                                 trading_date: datetime = None, is_historical: bool = False) -> str:
    """Render premium neomorphic trading dashboard."""
    
    if pivots is None:
        pivots = []
    if es_data is None:
        es_data = ESData()
    if detailed_cone is None:
        detailed_cone = ActiveConeInfo()
    if trading_date is None:
        trading_date = get_ct_now()
    
    # Ensure trading_date is a date object
    if hasattr(trading_date, 'date'):
        eval_date = trading_date.date()
    else:
        eval_date = trading_date
    
    # Color palette
    bg = "#e8eef3"
    card_bg = "#e8eef3"
    shadow_dark = "#c5ccd3"
    shadow_light = "#ffffff"
    text_dark = "#2d3748"
    text_med = "#4a5568"
    text_light = "#718096"
    
    green = "#10b981"
    green_glow = "#34d399"
    red = "#ef4444"
    red_glow = "#f87171"
    amber = "#f59e0b"
    blue = "#3b82f6"
    
    # Bias colors
    if vix.bias == 'CALLS':
        bias_color = green
        bias_glow = green_glow
        bias_text = "BULLISH"
        bias_icon = "▲"
    elif vix.bias == 'PUTS':
        bias_color = red
        bias_glow = red_glow
        bias_text = "BEARISH"
        bias_icon = "▼"
    else:
        bias_color = amber
        bias_glow = "#fbbf24"
        bias_text = "NEUTRAL"
        bias_icon = "●"
    
    # Score color
    if assessment.score >= 70:
        score_color = green
    elif assessment.score >= 50:
        score_color = amber
    else:
        score_color = red
    
    # Connection indicator
    if polygon_status and polygon_status.connected:
        conn_html = f'<span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:10px;height:10px;background:{green};border-radius:50%;box-shadow:0 0 8px {green};"></span><span style="color:{green};font-weight:600;font-size:12px;">LIVE</span></span>'
    else:
        conn_html = f'<span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:10px;height:10px;background:{text_light};border-radius:50%;"></span><span style="color:{text_light};font-weight:600;font-size:12px;">OFFLINE</span></span>'
    
    html = f'''
<!DOCTYPE html>
<html>
<head>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            background: {bg};
            color: {text_dark};
            min-height: 100vh;
            padding: 32px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        /* Neomorphic base styles */
        .neo-card {{
            background: {card_bg};
            border-radius: 24px;
            box-shadow: 
                8px 8px 16px {shadow_dark},
                -8px -8px 16px {shadow_light};
            padding: 28px;
            margin-bottom: 24px;
            transition: all 0.3s ease;
        }}
        
        .neo-card:hover {{
            box-shadow: 
                10px 10px 20px {shadow_dark},
                -10px -10px 20px {shadow_light};
        }}
        
        .neo-inset {{
            background: {card_bg};
            border-radius: 16px;
            box-shadow: 
                inset 4px 4px 8px {shadow_dark},
                inset -4px -4px 8px {shadow_light};
            padding: 20px;
        }}
        
        .neo-button {{
            background: {card_bg};
            border-radius: 12px;
            box-shadow: 
                4px 4px 8px {shadow_dark},
                -4px -4px 8px {shadow_light};
            padding: 12px 24px;
            border: none;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
        
        .neo-button:active {{
            box-shadow: 
                inset 4px 4px 8px {shadow_dark},
                inset -4px -4px 8px {shadow_light};
        }}
        
        .neo-pill {{
            display: inline-flex;
            align-items: center;
            padding: 8px 16px;
            border-radius: 50px;
            font-size: 12px;
            font-weight: 600;
            box-shadow: 
                3px 3px 6px {shadow_dark},
                -3px -3px 6px {shadow_light};
        }}
        
        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
        }}
        
        .logo {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        
        .logo-icon {{
            width: 52px;
            height: 52px;
            background: linear-gradient(135deg, {blue} 0%, #8b5cf6 100%);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 
                6px 6px 12px {shadow_dark},
                -6px -6px 12px {shadow_light},
                inset 0 0 0 1px rgba(255,255,255,0.1);
        }}
        
        .logo-icon span {{
            font-size: 20px;
            font-weight: 800;
            color: white;
        }}
        
        .logo-text h1 {{
            font-size: 20px;
            font-weight: 800;
            color: {text_dark};
            letter-spacing: -0.5px;
            margin-bottom: 2px;
        }}
        
        .logo-tagline {{
            font-size: 12px;
            color: {text_med};
            font-weight: 500;
            font-style: italic;
            margin-bottom: 2px;
        }}
        
        .logo-text p {{
            font-size: 11px;
            color: {text_light};
            font-weight: 500;
        }}
        
        .header-right {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        
        .time-display {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 20px;
            font-weight: 600;
            color: {text_dark};
        }}
        
        /* Hero Grid */
        .hero-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr 320px;
            gap: 24px;
            margin-bottom: 32px;
        }}
        
        /* Price Card */
        .price-card {{
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .price-label {{
            font-size: 12px;
            font-weight: 600;
            color: {text_light};
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        
        .price-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 36px;
            font-weight: 700;
            color: {text_dark};
            letter-spacing: -1px;
            line-height: 1;
            margin-bottom: 12px;
        }}
        
        .price-meta {{
            display: flex;
            gap: 24px;
        }}
        
        .meta-item {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        
        .meta-label {{
            font-size: 11px;
            font-weight: 600;
            color: {text_light};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .meta-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            font-weight: 600;
            color: {text_dark};
        }}
        
        /* VIX Card */
        .vix-card {{
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .vix-zone-bar {{
            height: 16px;
            border-radius: 8px;
            background: linear-gradient(90deg, {green}40 0%, {bg} 40%, {bg} 60%, {red}40 100%);
            position: relative;
            margin: 16px 0;
            box-shadow: 
                inset 2px 2px 4px {shadow_dark},
                inset -2px -2px 4px {shadow_light};
        }}
        
        .vix-marker {{
            position: absolute;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 24px;
            height: 24px;
            background: {bias_color};
            border-radius: 50%;
            box-shadow: 0 0 12px {bias_glow}, 0 2px 8px rgba(0,0,0,0.2);
            border: 3px solid {card_bg};
        }}
        
        .vix-labels {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: {text_light};
            font-family: 'JetBrains Mono', monospace;
        }}
        
        /* Bias Card */
        .bias-card {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            background: linear-gradient(135deg, {bias_color}15 0%, {bias_color}05 100%);
            border: 2px solid {bias_color}30;
            position: relative;
            overflow: hidden;
        }}
        
        .bias-card::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, {bias_color}10 0%, transparent 70%);
            animation: pulse 3s ease-in-out infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 0.5; }}
            50% {{ transform: scale(1.1); opacity: 0.8; }}
        }}
        
        .bias-icon {{
            font-size: 32px;
            color: {bias_color};
            margin-bottom: 8px;
            position: relative;
            z-index: 1;
            text-shadow: 0 0 20px {bias_glow};
        }}
        
        .bias-label {{
            font-size: 20px;
            font-weight: 800;
            color: {bias_color};
            letter-spacing: 1px;
            position: relative;
            z-index: 1;
        }}
        
        .bias-sub {{
            font-size: 12px;
            color: {text_med};
            margin-top: 8px;
            position: relative;
            z-index: 1;
        }}
        
        .bias-pct {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            font-weight: 700;
            color: {bias_color};
            background: {card_bg};
            padding: 8px 20px;
            border-radius: 50px;
            margin-top: 16px;
            position: relative;
            z-index: 1;
            box-shadow: 
                4px 4px 8px {shadow_dark},
                -4px -4px 8px {shadow_light};
        }}
        
        /* Alert Banner */
        .alert-banner {{
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 24px 28px;
            border-radius: 20px;
            margin-bottom: 24px;
            box-shadow: 
                8px 8px 16px {shadow_dark},
                -8px -8px 16px {shadow_light};
        }}
        
        .alert-banner.success {{
            background: linear-gradient(135deg, {green}15, {green}05);
            border-left: 4px solid {green};
        }}
        
        .alert-banner.danger {{
            background: linear-gradient(135deg, {red}15, {red}05);
            border-left: 4px solid {red};
        }}
        
        .alert-icon {{
            width: 56px;
            height: 56px;
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            flex-shrink: 0;
        }}
        
        .alert-banner.success .alert-icon {{
            background: {green}20;
            box-shadow: 0 0 20px {green}30;
        }}
        
        .alert-banner.danger .alert-icon {{
            background: {red}20;
            box-shadow: 0 0 20px {red}30;
        }}
        
        .alert-content h3 {{
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 6px;
        }}
        
        .alert-banner.success h3 {{ color: {green}; }}
        .alert-banner.danger h3 {{ color: {red}; }}
        
        .alert-content p {{
            font-size: 12px;
            color: {text_med};
        }}
        
        /* Score Section */
        .score-section {{
            display: flex;
            align-items: center;
            gap: 28px;
            margin-bottom: 32px;
        }}
        
        .score-circle {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: {card_bg};
            box-shadow: 
                8px 8px 16px {shadow_dark},
                -8px -8px 16px {shadow_light},
                inset 0 0 0 4px {score_color}30;
            position: relative;
        }}
        
        .score-circle::before {{
            content: '';
            position: absolute;
            inset: 4px;
            border-radius: 50%;
            background: conic-gradient({score_color} {assessment.score}%, transparent {assessment.score}%);
            mask: radial-gradient(farthest-side, transparent calc(100% - 6px), black calc(100% - 6px));
            -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 6px), black calc(100% - 6px));
        }}
        
        .score-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 24px;
            font-weight: 700;
            color: {score_color};
        }}
        
        .score-label {{
            font-size: 11px;
            font-weight: 600;
            color: {text_light};
            text-transform: uppercase;
        }}
        
        .score-info {{
            flex: 1;
        }}
        
        .score-title {{
            font-size: 16px;
            font-weight: 700;
            color: {text_dark};
            margin-bottom: 8px;
        }}
        
        .score-rec {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            background: {score_color}20;
            color: {score_color};
            margin-bottom: 12px;
        }}
        
        .score-warnings {{
            font-size: 12px;
            color: {text_med};
            line-height: 1.6;
        }}
        
        /* Section Title */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        
        .section-title {{
            font-size: 14px;
            font-weight: 700;
            color: {text_light};
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        
        /* Tables */
        .table-card {{
            overflow: hidden;
        }}
        
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
        }}
        
        thead {{
            background: {bg};
        }}
        
        th {{
            font-size: 11px;
            font-weight: 700;
            color: {text_light};
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 16px 20px;
            text-align: left;
            border-bottom: 2px solid {shadow_dark};
        }}
        
        td {{
            font-size: 14px;
            padding: 18px 20px;
            color: {text_dark};
            border-bottom: 1px solid {shadow_dark}50;
        }}
        
        tr:last-child td {{
            border-bottom: none;
        }}
        
        tbody tr {{
            transition: all 0.2s ease;
        }}
        
        tbody tr:hover {{
            background: {shadow_light};
        }}
        
        .mono {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
        }}
        
        .text-green {{ color: {green}; }}
        .text-red {{ color: {red}; }}
        .text-amber {{ color: {amber}; }}
        .text-muted {{ color: {text_light}; }}
        .font-bold {{ font-weight: 700; }}
        
        /* Option Price Cell */
        .option-price {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        
        .option-price .bid-ask {{
            font-size: 12px;
            color: {text_light};
        }}
        
        .option-price .mid {{
            font-size: 16px;
            font-weight: 700;
            color: {text_dark};
        }}
        
        .option-price .recommendation {{
            font-size: 11px;
            color: {green};
            font-weight: 600;
        }}
        
        /* Pills */
        .pill {{
            display: inline-flex;
            align-items: center;
            padding: 6px 14px;
            border-radius: 50px;
            font-size: 12px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .pill-green {{
            background: {green}20;
            color: {green};
            box-shadow: inset 0 0 0 1px {green}30;
        }}
        
        .pill-red {{
            background: {red}20;
            color: {red};
            box-shadow: inset 0 0 0 1px {red}30;
        }}
        
        .pill-amber {{
            background: {amber}20;
            color: {amber};
            box-shadow: inset 0 0 0 1px {amber}30;
        }}
        
        .pill-neutral {{
            background: {bg};
            color: {text_med};
            box-shadow: 
                2px 2px 4px {shadow_dark},
                -2px -2px 4px {shadow_light};
        }}
        
        /* Active Row */
        .row-active {{
            background: linear-gradient(90deg, {green}15, transparent) !important;
            position: relative;
        }}
        
        .row-active::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: {green};
            box-shadow: 0 0 12px {green};
        }}
        
        /* Data Grid */
        .data-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
        }}
        
        .data-cell {{
            text-align: center;
            padding: 16px;
        }}
        
        .data-cell-label {{
            font-size: 11px;
            font-weight: 600;
            color: {text_light};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        
        .data-cell-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 16px;
            font-weight: 700;
            color: {text_dark};
        }}
        
        /* Greeks Display */
        .greeks {{
            display: flex;
            gap: 16px;
            margin-top: 8px;
        }}
        
        .greek {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 8px 12px;
            background: {bg};
            border-radius: 8px;
            box-shadow: 
                inset 2px 2px 4px {shadow_dark},
                inset -2px -2px 4px {shadow_light};
        }}
        
        .greek-label {{
            font-size: 11px;
            color: {text_light};
            font-weight: 600;
        }}
        
        .greek-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 600;
            color: {text_dark};
        }}
        
    </style>
</head>
<body>
    <div class="container">
        
        <!-- Header -->
        <div class="header">
            <div class="logo">
                <div class="logo-icon"><span>SP</span></div>
                <div class="logo-text">
                    <h1>SPX Prophet</h1>
                    <div class="logo-tagline">Where Structure Becomes Foresight</div>
                    <p>v5.1 Premium</p>
                </div>
            </div>
            <div class="header-right">
                {conn_html}
                <div class="time-display">{'📅 ' + eval_date.strftime('%b %d, %Y') if is_historical else get_ct_now().strftime('%H:%M') + ' CT'}</div>
            </div>
        </div>
'''
    
    # Historical Mode Banner
    if is_historical:
        html += f'''
        <div class="neo-card" style="background:linear-gradient(135deg, {amber}15, {amber}05);border:2px solid {amber}50;margin-bottom:24px;">
            <div style="display:flex;align-items:center;gap:16px;">
                <div style="font-size:24px;">📅</div>
                <div>
                    <div style="font-weight:700;font-size:14px;color:{amber};">Historical Mode — {eval_date.strftime('%A, %B %d, %Y')}</div>
                    <div style="font-size:12px;color:{text_med};margin-top:4px;">Viewing past data. SPX close: <strong>{spx:,.2f}</strong> • VIX estimated from daily range • No live options or ES data</div>
                </div>
            </div>
        </div>
'''
    
    html += f'''
        <!-- Hero Grid -->
        <div class="hero-grid">
            
            <!-- SPX Price Card -->
            <div class="neo-card price-card">
                <div class="price-label">S&P 500 Index{' (Close)' if is_historical else ''}</div>
                <div class="price-value">{spx:,.2f}</div>
                <div class="price-meta">
                    <div class="meta-item">
                        <span class="meta-label">VIX</span>
                        <span class="meta-value">{vix.current:.2f}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Expected</span>
                        <span class="meta-value">±{vix.expected_move[0]}-{vix.expected_move[1]}</span>
                    </div>
                </div>
            </div>
            
            <!-- VIX Zone Card -->
            <div class="neo-card vix-card">
                <div class="price-label">VIX Overnight Zone</div>
                <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:8px;">
                    <span class="meta-value">{vix.bottom:.2f}</span>
                    <span style="color:{text_light};">—</span>
                    <span class="meta-value">{vix.top:.2f}</span>
                    <span class="pill pill-neutral" style="margin-left:auto;">Δ {vix.zone_size:.2f}</span>
                </div>
                <div class="vix-zone-bar">
                    <div class="vix-marker" style="left:{vix.position_pct}%;"></div>
                </div>
                <div class="vix-labels">
                    <span>{vix.bottom:.2f}</span>
                    <span>VIX @ {vix.position_pct:.0f}%</span>
                    <span>{vix.top:.2f}</span>
                </div>
            </div>
            
            <!-- Bias Card -->
            <div class="neo-card bias-card">
                <div class="bias-icon">{bias_icon}</div>
                <div class="bias-label">{bias_text}</div>
                <div class="bias-sub">Market Bias</div>
                <div class="bias-pct">{vix.position_pct:.0f}%</div>
            </div>
            
        </div>
'''
    
    # Weekend/After-hours Planning Banner (only for live mode)
    if not is_historical:
        now = get_ct_now()
        weekday = now.weekday()
        current_time = now.time()
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        is_weekend = weekday >= 5
        is_after_hours = weekday < 5 and (current_time < market_open or current_time > market_close)
        
        if is_weekend or is_after_hours:
            next_trading = get_next_trading_day()
            trading_label = get_trading_day_label()
            
            if is_weekend:
                banner_title = "📅 Weekend Planning Mode"
                banner_text = f"Markets are closed. Showing projected setups and option prices for <strong>{trading_label} ({next_trading.strftime('%b %d')})</strong>. Prices will update when markets open."
            else:
                if current_time < market_open:
                    banner_title = "🌅 Pre-Market Planning"
                    banner_text = f"Market opens at 9:30 AM CT. Showing projected setups for <strong>today's session</strong>."
                else:
                    banner_title = "🌙 After-Hours Planning"
                    banner_text = f"Markets are closed. Showing projected setups for <strong>{trading_label} ({next_trading.strftime('%b %d')})</strong>."
            
            html += f'''
        <div class="neo-card" style="background:linear-gradient(135deg, {blue}15, {blue}05);border:1px solid {blue}30;margin-bottom:24px;">
            <div style="display:flex;align-items:center;gap:16px;">
                <div style="font-size:24px;">{banner_title.split()[0]}</div>
                <div>
                    <div style="font-weight:700;font-size:14px;color:{blue};">{banner_title[2:]}</div>
                    <div style="font-size:12px;color:{text_med};margin-top:4px;">{banner_text}</div>
                </div>
            </div>
        </div>
'''
    
    # ========================================================================
    # ES FUTURES + ACTIVE CONE ROW
    # ========================================================================
    html += f'''
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px;">
'''
    
    # ES Futures Card (only show data for live mode)
    if not is_historical and es_data.current_price > 0:
        es_direction_color = green if es_data.direction == "UP" else red if es_data.direction == "DOWN" else text_light
        es_arrow = "▲" if es_data.direction == "UP" else "▼" if es_data.direction == "DOWN" else "●"
        es_change_sign = "+" if es_data.overnight_change >= 0 else ""
        
        alignment_icon = "✅" if es_data.vix_aligned else "⚠️"
        alignment_text = "VIX Aligned" if es_data.vix_aligned else es_data.conflict_warning
        alignment_color = green if es_data.vix_aligned else amber
        
        html += f'''
            <div class="neo-card">
                <div class="price-label">ES Futures Overnight</div>
                <div style="display:flex;align-items:center;gap:16px;margin:12px 0;">
                    <span style="font-size:24px;color:{es_direction_color};">{es_arrow}</span>
                    <div>
                        <div class="mono" style="font-size:20px;font-weight:700;">{es_data.current_price:,.2f}</div>
                        <div class="mono" style="font-size:12px;color:{es_direction_color};">{es_change_sign}{es_data.overnight_change:,.2f} ({es_change_sign}{es_data.overnight_change_pct:.2f}%)</div>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px;">
                    <div class="neo-inset" style="padding:12px;text-align:center;">
                        <div style="font-size:11px;color:{text_light};text-transform:uppercase;">SPX Offset</div>
                        <div class="mono" style="font-size:14px;font-weight:600;">{es_data.spx_offset:+.2f} pts</div>
                    </div>
                    <div class="neo-inset" style="padding:12px;text-align:center;">
                        <div style="font-size:11px;color:{text_light};text-transform:uppercase;">Likely Cone</div>
                        <div style="font-size:14px;font-weight:700;color:{es_direction_color};">{es_data.likely_cone or "—"}</div>
                    </div>
                </div>
                <div style="margin-top:16px;padding:10px;background:{alignment_color}15;border-radius:8px;border-left:3px solid {alignment_color};">
                    <span style="font-weight:600;font-size:12px;color:{alignment_color};">{alignment_icon} {alignment_text}</span>
                </div>
            </div>
'''
    else:
        # Show appropriate message based on mode
        if is_historical:
            html += f'''
            <div class="neo-card">
                <div class="price-label">ES Futures Overnight</div>
                <div style="padding:16px 0;text-align:center;">
                    <div style="font-size:14px;color:{text_light};margin-bottom:8px;">📅 Historical Mode</div>
                    <div style="font-size:12px;color:{text_light};">ES futures data not available for past dates</div>
                </div>
            </div>
'''
        else:
            html += f'''
            <div class="neo-card">
                <div class="price-label">ES Futures Overnight</div>
                <div style="color:{text_light};padding:20px 0;text-align:center;">Loading ES data...</div>
            </div>
'''
    
    # Active Cone Indicator - update label for historical
    cone_label = "Cone Position (at Close)" if is_historical else "Active Cone Position"
    
    if detailed_cone.cone_name:
        position_color = green if detailed_cone.position_pct < 30 else red if detailed_cone.position_pct > 70 else amber
        trade_dir_color = green if detailed_cone.trade_direction == "CALLS" else red
        trade_arrow = "▲" if detailed_cone.trade_direction == "CALLS" else "▼"
        
        status_text = "INSIDE" if detailed_cone.is_inside else "OUTSIDE"
        at_rail_badge = f'<span class="pill pill-green" style="margin-left:12px;">🎯 AT RAIL</span>' if detailed_cone.at_rail and not is_historical else ''
        
        html += f'''
            <div class="neo-card">
                <div class="price-label">{cone_label}</div>
                <div style="display:flex;align-items:center;justify-content:space-between;margin:12px 0;">
                    <div style="font-size:16px;font-weight:700;">{detailed_cone.cone_name}</div>
                    <span class="pill pill-neutral">{status_text}</span>
                    {at_rail_badge}
                </div>
                
                <!-- Cone Position Bar -->
                <div style="margin:16px 0;">
                    <div style="display:flex;justify-content:space-between;font-size:11px;color:{text_light};margin-bottom:6px;">
                        <span>▲ CALLS Zone</span>
                        <span>▼ PUTS Zone</span>
                    </div>
                    <div style="height:10px;border-radius:5px;background:linear-gradient(90deg, {green}40 0%, {bg} 30%, {bg} 70%, {red}40 100%);position:relative;box-shadow:inset 2px 2px 4px {shadow_dark},inset -2px -2px 4px {shadow_light};">
                        <div style="position:absolute;top:50%;left:{detailed_cone.position_pct}%;transform:translate(-50%,-50%);width:16px;height:16px;background:{position_color};border-radius:50%;border:2px solid {card_bg};box-shadow:0 0 8px {position_color};"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:11px;margin-top:6px;">
                        <span class="mono" style="color:{green};">{detailed_cone.descending_rail:,.2f}</span>
                        <span class="mono" style="color:{text_med};">SPX @ {detailed_cone.position_pct:.0f}%</span>
                        <span class="mono" style="color:{red};">{detailed_cone.ascending_rail:,.2f}</span>
                    </div>
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
                    <div class="neo-inset" style="padding:10px;text-align:center;">
                        <div style="font-size:11px;color:{text_light};">To Ascending</div>
                        <div class="mono" style="font-size:12px;color:{red};">{detailed_cone.distance_to_ascending:.1f} pts</div>
                    </div>
                    <div class="neo-inset" style="padding:10px;text-align:center;">
                        <div style="font-size:11px;color:{text_light};">Cone Width</div>
                        <div class="mono" style="font-size:12px;">{detailed_cone.cone_width:.0f} pts</div>
                    </div>
                    <div class="neo-inset" style="padding:10px;text-align:center;">
                        <div style="font-size:11px;color:{text_light};">To Descending</div>
                        <div class="mono" style="font-size:12px;color:{green};">{detailed_cone.distance_to_descending:.1f} pts</div>
                    </div>
                </div>
                
                <div style="margin-top:14px;padding:10px;background:{trade_dir_color}15;border-radius:8px;text-align:center;">
                    <span style="font-size:16px;color:{trade_dir_color};">{trade_arrow}</span>
                    <span style="font-weight:700;font-size:12px;color:{trade_dir_color};margin-left:8px;">Nearest: {detailed_cone.nearest_rail.upper()} RAIL → {detailed_cone.trade_direction}</span>
                </div>
            </div>
'''
    else:
        html += f'''
            <div class="neo-card">
                <div class="price-label">Active Cone Position</div>
                <div style="color:{text_light};padding:20px 0;">No cone data available</div>
            </div>
'''
    
    html += '''
        </div>
'''
    
    # ========================================================================
    # QUICK TRADE CARD (When at Rail - within 5 pts) - ONLY FOR LIVE MODE
    # ========================================================================
    if not is_historical and detailed_cone.at_rail and detailed_cone.cone_name:
        # Find the matching setup
        matching_setup = None
        for s in setups:
            if s.cone_name == detailed_cone.cone_name and s.direction == detailed_cone.trade_direction:
                matching_setup = s
                break
        
        if matching_setup:
            s = matching_setup
            trade_color = green if s.direction == "CALLS" else red
            trade_arrow = "▲" if s.direction == "CALLS" else "▼"
            
            html += f'''
        <div class="neo-card" style="background:linear-gradient(135deg, {trade_color}15, {trade_color}05);border:2px solid {trade_color}50;margin-bottom:24px;position:relative;overflow:hidden;">
            <div style="position:absolute;top:0;right:0;background:{trade_color};color:white;padding:6px 16px;font-weight:700;font-size:11px;border-bottom-left-radius:10px;">
                🎯 TRADE ALERT
            </div>
            
            <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px;">
                <div style="font-size:28px;color:{trade_color};">{trade_arrow}</div>
                <div>
                    <div style="font-size:16px;font-weight:800;color:{trade_color};">{s.direction} @ {s.cone_name}</div>
                    <div style="font-size:12px;color:{text_med};">{"Descending" if s.direction == "CALLS" else "Ascending"} Rail Entry</div>
                </div>
            </div>
            
            <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:12px;margin-bottom:16px;">
                <div class="neo-inset" style="padding:12px;text-align:center;">
                    <div style="font-size:11px;color:{text_light};text-transform:uppercase;margin-bottom:4px;">SPX Entry</div>
                    <div class="mono" style="font-size:16px;font-weight:700;color:{trade_color};">{s.entry:,.2f}</div>
                </div>
                <div class="neo-inset" style="padding:12px;text-align:center;">
                    <div style="font-size:11px;color:{text_light};text-transform:uppercase;margin-bottom:4px;">Strike</div>
                    <div class="mono" style="font-size:16px;font-weight:700;">{s.strike}{"C" if s.direction == "CALLS" else "P"}</div>
                </div>
                <div class="neo-inset" style="padding:12px;text-align:center;">
                    <div style="font-size:11px;color:{text_light};text-transform:uppercase;margin-bottom:4px;">Est. Premium</div>
                    <div class="mono" style="font-size:16px;font-weight:700;color:{green};">${s.est_entry_price_10am:.1f}</div>
                </div>
                <div class="neo-inset" style="padding:12px;text-align:center;background:{red}15;">
                    <div style="font-size:11px;color:{red};text-transform:uppercase;margin-bottom:4px;">Stop Loss</div>
                    <div class="mono" style="font-size:16px;font-weight:700;color:{red};">{s.stop:,.2f}</div>
                </div>
            </div>
            
            <div style="background:{card_bg};border-radius:10px;padding:16px;box-shadow:inset 3px 3px 6px {shadow_dark},inset -3px -3px 6px {shadow_light};">
                <div style="font-size:11px;font-weight:700;color:{text_light};text-transform:uppercase;margin-bottom:10px;">Risk / Reward Per Contract</div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;">
                    <div style="text-align:center;padding:10px;background:{red}10;border-radius:8px;">
                        <div style="font-size:11px;color:{red};">MAX RISK</div>
                        <div class="mono" style="font-size:14px;font-weight:700;color:{red};">-${s.stop_loss_dollars:.0f}</div>
                        <div style="font-size:11px;color:{text_light};">6 pts</div>
                    </div>
                    <div style="text-align:center;padding:10px;background:{green}10;border-radius:8px;">
                        <div style="font-size:11px;color:{text_med};">T1 (25%)</div>
                        <div class="mono" style="font-size:14px;font-weight:700;color:{green};">+${s.reward_t1_dollars:.0f}</div>
                        <div style="font-size:11px;color:{text_light};">{s.target_25:,.2f}</div>
                    </div>
                    <div style="text-align:center;padding:10px;background:{green}15;border-radius:8px;">
                        <div style="font-size:11px;color:{text_med};">T2 (50%)</div>
                        <div class="mono" style="font-size:14px;font-weight:700;color:{green};">+${s.reward_t2_dollars:.0f}</div>
                        <div style="font-size:11px;color:{text_light};">{s.target_50:,.2f}</div>
                    </div>
                    <div style="text-align:center;padding:10px;background:{green}20;border-radius:8px;">
                        <div style="font-size:11px;color:{text_med};">T3 (75%)</div>
                        <div class="mono" style="font-size:14px;font-weight:700;color:{green};">+${s.reward_t3_dollars:.0f}</div>
                        <div style="font-size:11px;color:{text_light};">{s.target_75:,.2f}</div>
                    </div>
                </div>
                <div style="margin-top:12px;text-align:center;">
                    <span style="font-size:12px;color:{text_med};">R:R Ratio:</span>
                    <span class="mono" style="font-size:14px;font-weight:700;color:{green};margin-left:8px;">1:{s.rr_ratio:.1f}</span>
                </div>
            </div>
        </div>
'''
    
    # Legacy Alert Banner (fallback if no detailed_cone)
    elif active_cone_info:
        inside = active_cone_info.get('inside_cone')
        at_rail = active_cone_info.get('at_rail', False)
        distance = active_cone_info.get('distance', 0)
        rail_type = active_cone_info.get('rail_type')
        
        if inside and at_rail:
            if rail_type == 'ascending':
                html += f'''
        <div class="alert-banner danger">
            <div class="alert-icon">🎯</div>
            <div class="alert-content">
                <h3>At {inside.name} Ascending Rail — PUTS Entry Zone</h3>
                <p>Price is {distance:.1f} points from rail at {inside.ascending_rail:,.2f}. Look for puts entry.</p>
            </div>
        </div>
'''
            else:
                html += f'''
        <div class="alert-banner success">
            <div class="alert-icon">🎯</div>
            <div class="alert-content">
                <h3>At {inside.name} Descending Rail — CALLS Entry Zone</h3>
                <p>Price is {distance:.1f} points from rail at {inside.descending_rail:,.2f}. Look for calls entry.</p>
            </div>
        </div>
'''
    
    # Score Section
    warnings_text = ' • '.join(assessment.warnings) if assessment.warnings else 'No warnings for this session'
    html += f'''
        <!-- Score Section -->
        <div class="neo-card score-section">
            <div class="score-circle">
                <div class="score-value">{assessment.score}</div>
                <div class="score-label">Score</div>
            </div>
            <div class="score-info">
                <div class="score-rec">{assessment.recommendation} SIZE</div>
                <div class="score-title">Day Assessment</div>
                <div class="score-warnings">{warnings_text}</div>
            </div>
        </div>
'''
    
    # Cones Table
    html += f'''
        <div class="section-header">
            <div class="section-title">Structural Cones @ 10:00 AM CT</div>
        </div>
        
        <div class="neo-card table-card">
            <table>
                <thead>
                    <tr>
                        <th>Pivot</th>
                        <th>Ascending Rail</th>
                        <th>Descending Rail</th>
                        <th style="text-align:center;">Width</th>
                        <th style="text-align:center;">Blocks</th>
                    </tr>
                </thead>
                <tbody>
'''
    
    for cone in cones:
        if cone.width >= 25:
            width_pill = 'pill-green'
        elif cone.width >= MIN_CONE_WIDTH:
            width_pill = 'pill-amber'
        else:
            width_pill = 'pill-red'
        
        html += f'''
                    <tr>
                        <td class="font-bold">{cone.name}</td>
                        <td class="mono text-red">{cone.ascending_rail:,.2f}</td>
                        <td class="mono text-green">{cone.descending_rail:,.2f}</td>
                        <td style="text-align:center;"><span class="pill {width_pill}">{cone.width:.0f} pts</span></td>
                        <td class="mono text-muted" style="text-align:center;">{cone.blocks}</td>
                    </tr>
'''
    
    html += '''
                </tbody>
            </table>
        </div>
'''
    
    # Get trading day label for options
    if is_historical:
        trading_day_label = eval_date.strftime("%b %d, %Y")
        expiry_str = eval_date.strftime("%b %d")
        date_badge = f'<span class="pill pill-amber" style="font-size:11px;">📅 Historical</span>'
    else:
        trading_day_label = get_trading_day_label()
        next_expiry = get_next_trading_day()
        expiry_str = next_expiry.strftime("%b %d")
        date_badge = f'<span class="pill pill-neutral" style="font-size:11px;">0DTE {expiry_str} ({trading_day_label})</span>'
    
    # CALLS Setups
    calls_setups = [s for s in setups if s.direction == 'CALLS']
    if calls_setups:
        html += f'''
        <div class="section-header">
            <div class="section-title" style="color:{green};">▲ Calls Setups</div>
            <div style="display:flex;align-items:center;gap:12px;">
                {date_badge}
                <span style="font-size:11px;color:{text_light};">Enter at Descending Rail</span>
            </div>
        </div>
        
        <div class="neo-card table-card" style="overflow-x:auto;">
            <table style="min-width:100%;">
                <thead>
                    <tr>
                        <th>Cone</th>
                        <th>SPX Entry</th>
                        <th>Strike</th>
                        <th>Est. Premium</th>
                        <th>Stop (pts/$)</th>
                        <th>T1 25% (+$)</th>
                        <th>T2 50% (+$)</th>
                        <th>T3 75% (+$)</th>
                        <th>R:R</th>
                        <th style="text-align:right;">Dist</th>
                    </tr>
                </thead>
                <tbody>
'''
        for s in calls_setups:
            row_class = 'row-active' if s.is_active and not is_historical else ''
            
            # Premium display - different for historical
            if is_historical:
                premium_html = f'<span class="text-muted" style="font-size:11px;">Historical</span>'
            elif s.est_entry_price_10am > 0:
                premium_html = f'<span class="mono text-green font-bold">${s.est_entry_price_10am:.1f}</span>'
            elif s.current_option_price > 0:
                premium_html = f'<span class="mono">${s.current_option_price:.1f}</span>'
            else:
                premium_html = f'<span class="text-muted">—</span>'
            
            if s.using_spy and not is_historical:
                premium_html += f'<br><span style="font-size:9px;color:{text_light};">SPY {s.spy_strike_used}C</span>'
            
            dist_pill = 'pill-green' if s.distance <= 5 else 'pill-amber' if s.distance <= 15 else 'pill-neutral'
            
            html += f'''
                    <tr class="{row_class}">
                        <td class="font-bold">{s.cone_name}</td>
                        <td class="mono text-green">{s.entry:,.2f}</td>
                        <td class="mono">{s.strike}C</td>
                        <td>{premium_html}</td>
                        <td><span class="mono text-red">{s.stop:,.2f}</span><br><span style="font-size:11px;color:{red};">-${s.stop_loss_dollars:.0f}</span></td>
                        <td><span class="mono">{s.target_25:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t1_dollars:.0f}</span></td>
                        <td><span class="mono">{s.target_50:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t2_dollars:.0f}</span></td>
                        <td><span class="mono">{s.target_75:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t3_dollars:.0f}</span></td>
                        <td class="mono" style="color:{green};font-weight:700;">1:{s.rr_ratio:.1f}</td>
                        <td style="text-align:right;"><span class="pill {dist_pill}">{s.distance:.0f}</span></td>
                    </tr>
'''
        html += '''
                </tbody>
            </table>
        </div>
'''
    
    # PUTS Setups
    puts_setups = [s for s in setups if s.direction == 'PUTS']
    if puts_setups:
        html += f'''
        <div class="section-header">
            <div class="section-title" style="color:{red};">▼ Puts Setups</div>
            <div style="display:flex;align-items:center;gap:12px;">
                {date_badge}
                <span style="font-size:11px;color:{text_light};">Enter at Ascending Rail</span>
            </div>
        </div>
        
        <div class="neo-card table-card" style="overflow-x:auto;">
            <table style="min-width:100%;">
                <thead>
                    <tr>
                        <th>Cone</th>
                        <th>SPX Entry</th>
                        <th>Strike</th>
                        <th>Est. Premium</th>
                        <th>Stop (pts/$)</th>
                        <th>T1 25% (+$)</th>
                        <th>T2 50% (+$)</th>
                        <th>T3 75% (+$)</th>
                        <th>R:R</th>
                        <th style="text-align:right;">Dist</th>
                    </tr>
                </thead>
                <tbody>
'''
        for s in puts_setups:
            row_class = 'row-active' if s.is_active and not is_historical else ''
            
            # Premium display - different for historical
            if is_historical:
                premium_html = f'<span class="text-muted" style="font-size:11px;">Historical</span>'
            elif s.est_entry_price_10am > 0:
                premium_html = f'<span class="mono text-green font-bold">${s.est_entry_price_10am:.1f}</span>'
            elif s.current_option_price > 0:
                premium_html = f'<span class="mono">${s.current_option_price:.1f}</span>'
            else:
                premium_html = f'<span class="text-muted">—</span>'
            
            if s.using_spy and not is_historical:
                premium_html += f'<br><span style="font-size:9px;color:{text_light};">SPY {s.spy_strike_used}P</span>'
            
            dist_pill = 'pill-green' if s.distance <= 5 else 'pill-amber' if s.distance <= 15 else 'pill-neutral'
            
            html += f'''
                    <tr class="{row_class}">
                        <td class="font-bold">{s.cone_name}</td>
                        <td class="mono text-red">{s.entry:,.2f}</td>
                        <td class="mono">{s.strike}P</td>
                        <td>{premium_html}</td>
                        <td><span class="mono text-green">{s.stop:,.2f}</span><br><span style="font-size:11px;color:{red};">-${s.stop_loss_dollars:.0f}</span></td>
                        <td><span class="mono">{s.target_25:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t1_dollars:.0f}</span></td>
                        <td><span class="mono">{s.target_50:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t2_dollars:.0f}</span></td>
                        <td><span class="mono">{s.target_75:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t3_dollars:.0f}</span></td>
                        <td class="mono" style="color:{green};font-weight:700;">1:{s.rr_ratio:.1f}</td>
                        <td style="text-align:right;"><span class="pill {dist_pill}">{s.distance:.0f}</span></td>
                    </tr>
'''
        html += '''
                </tbody>
            </table>
        </div>
'''
    
    # Prior Session
    if prior:
        html += f'''
        <div class="section-header">
            <div class="section-title">Prior Session Reference</div>
        </div>
        
        <div class="neo-card">
            <div class="data-grid">
                <div class="neo-inset data-cell">
                    <div class="data-cell-label">High</div>
                    <div class="data-cell-value">{prior.get('high', 0):,.2f}</div>
                </div>
                <div class="neo-inset data-cell">
                    <div class="data-cell-label">Low</div>
                    <div class="data-cell-value">{prior.get('low', 0):,.2f}</div>
                </div>
                <div class="neo-inset data-cell">
                    <div class="data-cell-label">Close</div>
                    <div class="data-cell-value">{prior.get('close', 0):,.2f}</div>
                </div>
                <div class="neo-inset data-cell">
                    <div class="data-cell-label">Range</div>
                    <div class="data-cell-value">{prior.get('high', 0) - prior.get('low', 0):,.0f}</div>
                </div>
            </div>
        </div>
'''
    
    # ========================================================================
    # PIVOT TABLE - All entries at each 30-min block during RTH
    # ========================================================================
    if pivots:
        # RTH time slots: 8:30 AM to 3:00 PM CT in 30-min increments
        time_slots = []
        start_hour, start_min = 8, 30
        end_hour, end_min = 15, 0
        
        current_hour, current_min = start_hour, start_min
        while (current_hour < end_hour) or (current_hour == end_hour and current_min <= end_min):
            time_slots.append(f"{current_hour}:{current_min:02d}")
            current_min += 30
            if current_min >= 60:
                current_min = 0
                current_hour += 1
        
        # Use the trading date for calculations (historical or current)
        pivot_calc_date = eval_date
        
        # Show which date we're displaying
        date_label = pivot_calc_date.strftime('%A, %b %d, %Y')
        historical_badge = f'<span class="pill pill-amber" style="margin-left:12px;">📅 Historical</span>' if is_historical else ''
        
        html += f'''
        <div class="section-header" style="margin-top:32px;">
            <div class="section-title">📊 Pivot Table — All Entries by Time Block</div>
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:11px;color:{text_light};">{date_label}</span>
                {historical_badge}
            </div>
        </div>
        
        <div class="neo-card table-card" style="overflow-x:auto;">
            <table style="min-width:100%;font-size:12px;">
                <thead>
                    <tr>
                        <th style="position:sticky;left:0;background:{bg};z-index:10;">Time CT</th>
'''
        
        # Header row with pivot names (both directions)
        for pivot in pivots:
            html += f'''
                        <th colspan="2" style="text-align:center;border-left:2px solid {shadow_dark};">{pivot.name}</th>
'''
        
        html += '''
                    </tr>
                    <tr>
                        <th style="position:sticky;left:0;background:''' + bg + ''';">Block</th>
'''
        
        for pivot in pivots:
            html += f'''
                        <th style="color:{green};text-align:center;border-left:2px solid {shadow_dark};">▲ Calls</th>
                        <th style="color:{red};text-align:center;">▼ Puts</th>
'''
        
        html += '''
                    </tr>
                </thead>
                <tbody>
'''
        
        # Generate rows for each time slot
        for slot in time_slots:
            hour, minute = map(int, slot.split(':'))
            slot_time = CT_TZ.localize(datetime.combine(pivot_calc_date, time(hour, minute)))
            
            # Check if this is the institutional window (9:30-10:00)
            is_institutional = (hour == 9 and minute >= 30) or (hour == 10 and minute == 0)
            row_style = f'background:linear-gradient(90deg, {amber}20, {amber}05);' if is_institutional else ''
            row_highlight = f'<span style="color:{amber};font-weight:700;">🏛️</span> ' if is_institutional else ''
            
            html += f'''
                    <tr style="{row_style}">
                        <td style="position:sticky;left:0;background:{card_bg if not is_institutional else amber + '15'};font-weight:600;white-space:nowrap;">
                            {row_highlight}{slot}
                        </td>
'''
            
            for pivot in pivots:
                # Use proper block counting that respects RTH
                start_time = pivot.time + timedelta(minutes=30)
                blocks = count_blocks(start_time, slot_time)
                
                # Only show values if slot_time is after the cone would have started
                # For same-day pivots, check if slot is after pivot
                # For prior-day pivots (like Close), always show
                pivot_is_prior_day = pivot.time.date() < pivot_calc_date
                slot_after_pivot = slot_time > start_time
                
                if pivot_is_prior_day or slot_after_pivot:
                    ascending = pivot.price_for_ascending + (blocks * SLOPE_PER_30MIN)
                    descending = pivot.price_for_descending - (blocks * SLOPE_PER_30MIN)
                    
                    # Format values
                    calls_entry = f'{descending:,.2f}'
                    puts_entry = f'{ascending:,.2f}'
                else:
                    calls_entry = '—'
                    puts_entry = '—'
                
                html += f'''
                        <td class="mono" style="text-align:center;color:{green};border-left:2px solid {shadow_dark}40;">{calls_entry}</td>
                        <td class="mono" style="text-align:center;color:{red};">{puts_entry}</td>
'''
            
            html += '''
                    </tr>
'''
        
        html += '''
                </tbody>
            </table>
            <div style="margin-top:16px;padding:12px;background:''' + amber + '''15;border-radius:8px;border-left:4px solid ''' + amber + ''';">
                <span style="font-weight:600;color:''' + amber + ''';">🏛️ Institutional Window (9:30-10:00 AM)</span>
                <span style="color:''' + text_med + ''';margin-left:12px;">Large institutions typically enter positions during this period. Watch for volume confirmation.</span>
            </div>
        </div>
'''
    
    html += '''
    </div>
</body>
</html>
'''
    
    return html

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet v5.1 Premium",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Session state initialization
    defaults = {
        'use_manual_vix': False,
        'use_manual_pivots': False,
        'vix_bottom': 0.0,
        'vix_top': 0.0,
        'vix_current': 0.0,
        # Primary pivots
        'manual_high_wick': 0.0,        # Highest WICK for high cone
        'manual_high_time': "10:30",
        'manual_low_close': 0.0,        # Lowest CLOSE for low cone
        'manual_low_time': "14:00",
        'manual_close': 0.0,            # Prior close
        # Secondary pivots (optional)
        'use_secondary_high': False,
        'secondary_high_wick': 0.0,
        'secondary_high_time': "14:30",
        'use_secondary_low': False,
        'secondary_low_close': 0.0,
        'secondary_low_time': "11:00",
        # Other
        'fetch_options': True,
        'selected_date': None,
        'use_historical': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # Date Selection
        st.markdown("### 📅 Trading Date")
        
        # Get today and next trading day
        today = get_ct_now().date()
        next_trading = get_next_trading_day().date()
        
        date_mode = st.radio(
            "Select Mode",
            ["Live / Next Trading Day", "Historical Date"],
            index=1 if st.session_state.use_historical else 0,
            horizontal=True
        )
        
        st.session_state.use_historical = (date_mode == "Historical Date")
        
        if st.session_state.use_historical:
            # Historical date picker
            selected = st.date_input(
                "Select Date",
                value=st.session_state.selected_date or today - timedelta(days=1),
                max_value=today,
                min_value=today - timedelta(days=365)
            )
            st.session_state.selected_date = selected
            
            # Show what date is selected
            if selected.weekday() >= 5:
                st.warning(f"⚠️ {selected.strftime('%A, %b %d')} is a weekend - no trading data")
            else:
                st.info(f"📊 Showing data for **{selected.strftime('%A, %b %d, %Y')}**")
        else:
            # Show next trading day info
            trading_label = get_trading_day_label()
            st.info(f"📊 **{trading_label}** ({next_trading.strftime('%b %d, %Y')})")
            st.session_state.selected_date = None
        
        st.markdown("---")
        
        st.markdown("### 📊 VIX Zone")
        use_manual_vix = st.checkbox("Manual VIX Override", value=st.session_state.use_manual_vix)
        st.session_state.use_manual_vix = use_manual_vix
        
        if use_manual_vix:
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.vix_bottom = st.number_input("VIX Bottom", value=st.session_state.vix_bottom, step=0.01, format="%.2f")
            with col2:
                st.session_state.vix_top = st.number_input("VIX Top", value=st.session_state.vix_top, step=0.01, format="%.2f")
        
        st.markdown("### 📍 Prior Day Pivots")
        use_manual_pivots = st.checkbox("Manual Pivot Override", value=st.session_state.use_manual_pivots)
        st.session_state.use_manual_pivots = use_manual_pivots
        
        if use_manual_pivots:
            st.markdown("##### Primary Pivots")
            
            # High Cone - uses highest WICK
            st.markdown("**High Cone** (highest wick)")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.session_state.manual_high_wick = st.number_input(
                    "Highest Wick", 
                    value=st.session_state.manual_high_wick, 
                    step=0.01, 
                    format="%.2f",
                    key="high_wick"
                )
            with col2:
                st.session_state.manual_high_time = st.text_input(
                    "Time (HH:MM)", 
                    value=st.session_state.manual_high_time,
                    key="high_time"
                )
            
            # Low Cone - uses lowest CLOSE
            st.markdown("**Low Cone** (lowest close in RTH)")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.session_state.manual_low_close = st.number_input(
                    "Lowest Close", 
                    value=st.session_state.manual_low_close, 
                    step=0.01, 
                    format="%.2f",
                    key="low_close"
                )
            with col2:
                st.session_state.manual_low_time = st.text_input(
                    "Time (HH:MM)", 
                    value=st.session_state.manual_low_time,
                    key="low_time"
                )
            
            # Close
            st.session_state.manual_close = st.number_input(
                "Prior Close", 
                value=st.session_state.manual_close, 
                step=0.01, 
                format="%.2f"
            )
            
            st.markdown("---")
            st.markdown("##### Secondary Pivots (Optional)")
            
            # Secondary High
            st.session_state.use_secondary_high = st.checkbox(
                "Enable Secondary High", 
                value=st.session_state.use_secondary_high
            )
            if st.session_state.use_secondary_high:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.session_state.secondary_high_wick = st.number_input(
                        "2nd High Wick", 
                        value=st.session_state.secondary_high_wick, 
                        step=0.01, 
                        format="%.2f",
                        key="sec_high_wick"
                    )
                with col2:
                    st.session_state.secondary_high_time = st.text_input(
                        "Time", 
                        value=st.session_state.secondary_high_time,
                        key="sec_high_time"
                    )
            
            # Secondary Low
            st.session_state.use_secondary_low = st.checkbox(
                "Enable Secondary Low", 
                value=st.session_state.use_secondary_low
            )
            if st.session_state.use_secondary_low:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.session_state.secondary_low_close = st.number_input(
                        "2nd Low Close", 
                        value=st.session_state.secondary_low_close, 
                        step=0.01, 
                        format="%.2f",
                        key="sec_low_close"
                    )
                with col2:
                    st.session_state.secondary_low_time = st.text_input(
                        "Time", 
                        value=st.session_state.secondary_low_time,
                        key="sec_low_time"
                    )
        
        st.markdown("### 💰 Options")
        st.session_state.fetch_options = st.checkbox("Fetch Live Option Prices", value=st.session_state.fetch_options)
        
        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Determine if we're in historical mode
    is_historical = st.session_state.use_historical and st.session_state.selected_date is not None
    selected_date = st.session_state.selected_date
    
    # Get market data
    polygon_status = PolygonStatus()
    
    if is_historical:
        # HISTORICAL MODE - Fetch data for selected date
        historical_spx = fetch_historical_day_data("^GSPC", datetime.combine(selected_date, time(0, 0)))
        historical_vix = fetch_historical_day_data("^VIX", datetime.combine(selected_date, time(0, 0)))
        
        # Use close price as "current" for historical
        current_spx = historical_spx.get('close', 0)
        current_vix = historical_vix.get('close', 0)
        
        if current_spx > 0:
            polygon_status.connected = True
            polygon_status.spx_price = current_spx
            polygon_status.vix_price = current_vix
        
        # For historical, we need prior day data (day before selected date)
        prior_date = selected_date - timedelta(days=1)
        # Skip weekends for prior date
        while prior_date.weekday() >= 5:
            prior_date -= timedelta(days=1)
        
        prior_data = fetch_historical_day_data("^GSPC", datetime.combine(prior_date, time(0, 0)))
        if prior_data.get('high', 0) == 0:
            prior_data = {'high': current_spx + 20, 'low': current_spx - 20, 'close': current_spx, 'open': current_spx}
        
        # VIX Zone for historical - estimate based on daily range
        vix_range = historical_vix.get('high', current_vix) - historical_vix.get('low', current_vix)
        if vix_range > 0:
            vix_bottom = historical_vix.get('low', current_vix)
            vix_top = historical_vix.get('high', current_vix)
        else:
            vix_bottom = current_vix - 0.15
            vix_top = current_vix + 0.15
        vix_auto = False
        
        # ES data not available for historical
        es_data = ESData()
        
    else:
        # LIVE MODE - Current market data
        # SPX price
        spx_snapshot = polygon_get_snapshot(POLYGON_SPX) if POLYGON_HAS_INDICES else None
        if spx_snapshot and spx_snapshot.get('price', 0) > 0:
            current_spx = spx_snapshot['price']
            polygon_status.connected = True
            polygon_status.spx_price = current_spx
        else:
            current_spx = yf_fetch_current_spx()
        
        # VIX
        vix_snapshot = polygon_get_snapshot(POLYGON_VIX) if POLYGON_HAS_INDICES else None
        if vix_snapshot and vix_snapshot.get('price', 0) > 0:
            current_vix = vix_snapshot['price']
            polygon_status.vix_price = current_vix
        else:
            current_vix = yf_fetch_current_vix()
        
        # Prior day data
        prior_data = polygon_get_prior_day_data(POLYGON_SPX) if POLYGON_HAS_INDICES else None
        if not prior_data:
            prior_data = {'high': current_spx + 20, 'low': current_spx - 20, 'close': current_spx, 'open': current_spx}
        
        # Fetch ES Futures data
        es_raw = yf_fetch_es_futures()
    
    # VIX Zone - Manual override takes precedence
    if st.session_state.use_manual_vix and st.session_state.vix_bottom > 0 and st.session_state.vix_top > 0:
        vix_bottom = st.session_state.vix_bottom
        vix_top = st.session_state.vix_top
        vix_auto = False
    elif not is_historical:
        overnight = polygon_get_overnight_vix_range(get_ct_now()) if POLYGON_HAS_INDICES else None
        if overnight and overnight.get('bottom', 0) > 0:
            vix_bottom = overnight['bottom']
            vix_top = overnight['top']
            vix_auto = True
        else:
            vix_bottom = current_vix - 0.15
            vix_top = current_vix + 0.15
            vix_auto = False
    
    vix_zone = analyze_vix_zone(current_vix, vix_bottom, vix_top)
    vix_zone.auto_detected = vix_auto if not is_historical else False
    
    # ES data analysis (only for live mode)
    if not is_historical:
        es_data = analyze_es_data(es_raw, current_spx, vix_zone)
    
    # Build pivots
    if st.session_state.use_manual_pivots and st.session_state.manual_high_wick > 0:
        if is_historical:
            pivot_date = selected_date - timedelta(days=1)
            while pivot_date.weekday() >= 5:
                pivot_date -= timedelta(days=1)
        else:
            pivot_date = get_ct_now().date() - timedelta(days=1)
        
        pivots = []
        
        # Primary High (highest wick)
        h_parts = st.session_state.manual_high_time.split(':')
        high_time = CT_TZ.localize(datetime.combine(pivot_date, time(int(h_parts[0]), int(h_parts[1]))))
        pivots.append(Pivot(price=st.session_state.manual_high_wick, time=high_time, name="Prior High"))
        
        # Primary Low (lowest close)
        l_parts = st.session_state.manual_low_time.split(':')
        low_time = CT_TZ.localize(datetime.combine(pivot_date, time(int(l_parts[0]), int(l_parts[1]))))
        pivots.append(Pivot(price=st.session_state.manual_low_close, time=low_time, name="Prior Low"))
        
        # Prior Close (3 PM CT)
        pivots.append(Pivot(price=st.session_state.manual_close, time=CT_TZ.localize(datetime.combine(pivot_date, time(15, 0))), name="Prior Close"))
        
        # Secondary High (if enabled)
        if st.session_state.use_secondary_high and st.session_state.secondary_high_wick > 0:
            sh_parts = st.session_state.secondary_high_time.split(':')
            sec_high_time = CT_TZ.localize(datetime.combine(pivot_date, time(int(sh_parts[0]), int(sh_parts[1]))))
            pivots.append(Pivot(price=st.session_state.secondary_high_wick, time=sec_high_time, name="2nd High"))
        
        # Secondary Low (if enabled)
        if st.session_state.use_secondary_low and st.session_state.secondary_low_close > 0:
            sl_parts = st.session_state.secondary_low_time.split(':')
            sec_low_time = CT_TZ.localize(datetime.combine(pivot_date, time(int(sl_parts[0]), int(sl_parts[1]))))
            pivots.append(Pivot(price=st.session_state.secondary_low_close, time=sec_low_time, name="2nd Low"))
    else:
        if is_historical:
            pivot_date = selected_date - timedelta(days=1)
            while pivot_date.weekday() >= 5:
                pivot_date -= timedelta(days=1)
        else:
            pivot_date = get_ct_now().date() - timedelta(days=1)
        
        pivots = [
            Pivot(price=prior_data['high'], time=CT_TZ.localize(datetime.combine(pivot_date, time(10, 30))), name="Prior High"),
            Pivot(price=prior_data['low'], time=CT_TZ.localize(datetime.combine(pivot_date, time(14, 0))), name="Prior Low"),
            Pivot(price=prior_data['close'], time=CT_TZ.localize(datetime.combine(pivot_date, time(15, 0))), name="Prior Close")
        ]
    
    # Build cones at 10:00 AM CT for the trading date
    if is_historical:
        trading_date = selected_date
    else:
        trading_date = get_ct_now().date()
    
    eval_10am = CT_TZ.localize(datetime.combine(trading_date, time(10, 0)))
    cones = build_cones(pivots, eval_10am)
    
    # Generate setups
    setups = generate_setups(cones, current_spx, vix_zone.bias)
    
    # Fetch live options pricing (only for live mode)
    if st.session_state.fetch_options and not is_historical:
        with st.spinner("Fetching live options prices..."):
            for i, setup in enumerate(setups):
                setups[i] = get_option_pricing_for_setup(setup, current_spx)
    
    # Find active cone (legacy)
    active_cone_info = find_active_cone(current_spx, cones)
    
    # Get detailed active cone info
    detailed_cone = get_detailed_active_cone(current_spx, cones)
    
    # Day assessment
    assessment = assess_day(vix_zone, cones)
    
    # Render dashboard
    dashboard_html = render_neomorphic_dashboard(
        spx=current_spx,
        vix=vix_zone,
        cones=cones,
        setups=setups,
        assessment=assessment,
        prior=prior_data,
        active_cone_info=active_cone_info,
        polygon_status=polygon_status,
        pivots=pivots,
        es_data=es_data,
        detailed_cone=detailed_cone,
        trading_date=trading_date,
        is_historical=is_historical
    )
    
    components.html(dashboard_html, height=3200, scrolling=True)

if __name__ == "__main__":
    main()