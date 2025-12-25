"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ███████╗██████╗ ██╗  ██╗    ██████╗ ██████╗  ██████╗ ██████╗ ██╗  ██╗███████╗████████╗║
║   ██╔════╝██╔══██╗╚██╗██╔╝    ██╔══██╗██╔══██╗██╔═══██╗██╔══██╗██║  ██║██╔════╝╚══██╔══╝║
║   ███████╗██████╔╝ ╚███╔╝     ██████╔╝██████╔╝██║   ██║██████╔╝███████║█████╗     ██║   ║
║   ╚════██║██╔═══╝  ██╔██╗     ██╔═══╝ ██╔══██╗██║   ██║██╔═══╝ ██╔══██║██╔══╝     ██║   ║
║   ███████║██║     ██╔╝ ██╗    ██║     ██║  ██║╚██████╔╝██║     ██║  ██║███████╗   ██║   ║
║   ╚══════╝╚═╝     ╚═╝  ╚═╝    ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚══════╝   ╚═╝   ║
║                                                                               ║
║                    "Where Structure Becomes Foresight"                        ║
║                              Version 6.0 Legendary                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

SPX Prophet v6.0 - Legendary Edition
Built for professional 0DTE SPX options trading using structural cone analysis
and VIX zone methodology.

Features:
- Glass neomorphism UI with light/dark themes
- Real SPY options data from Polygon.io (converted to SPX equivalent)
- Live Greeks: Delta, Gamma, Theta, Vega, IV
- VIX zone analysis with expected SPX move calculations
- Auto-pivot detection from 30-min candles + manual override
- Up to 6 cones (3 primary + 3 secondary)
- Institutional window highlighting (9:00-9:30 AM CT)
- Historical backtesting with 2-year options data
- Open Interest magnet levels
- Visual and sound alerts
- Collapsible dashboard sections

Author: Built with Claude for David
Date: December 2025
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import numpy as np
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import pytz
import json
import yfinance as yf

# =============================================================================
# CONFIGURATION
# =============================================================================

POLYGON_API_KEY = "jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm"
POLYGON_BASE_URL = "https://api.polygon.io"

# Timezone
CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

# Trading Constants
SLOPE_PER_30MIN = 0.45          # Cone expansion rate per 30-min block
MIN_CONE_WIDTH = 18.0           # Minimum tradeable cone width
STOP_LOSS_PTS = 6.0             # Stop loss in SPX points
RAIL_PROXIMITY = 3.0            # Points to consider "at rail"

# Premium Preferences (SPY prices, multiply by 100 for cost)
PREMIUM_MIN = 3.50              # Minimum acceptable premium
PREMIUM_SWEET_LOW = 4.00        # Sweet spot low
PREMIUM_SWEET_HIGH = 7.00       # Sweet spot high  
PREMIUM_MAX = 8.00              # Maximum acceptable premium

# Target Delta Range
DELTA_TARGET_LOW = 0.28
DELTA_TARGET_HIGH = 0.38
DELTA_IDEAL = 0.33

# VIX to SPX Move Calculation
# Formula: Expected SPX Move = VIX Zone Size × 175
VIX_TO_SPX_MULTIPLIER = 175

# Time Windows (CT)
MARKET_OPEN = time(8, 30)       # Pre-market activity
RTH_OPEN = time(9, 30)          # Regular trading hours open
INSTITUTIONAL_START = time(9, 0)
INSTITUTIONAL_END = time(9, 30)
ENTRY_TARGET = time(9, 40)      # Ideal entry time (10 min after open)
CUTOFF_TIME = time(11, 0)       # Stop trading after this
MARKET_CLOSE = time(16, 0)

# US Market Holidays 2025
HOLIDAYS_2025 = [
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 20),  # MLK Day
    date(2025, 2, 17),  # Presidents Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
]

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VIXZone:
    """VIX Zone data with bias calculation"""
    bottom: float = 0.0
    top: float = 0.0
    current: float = 0.0
    zone_size: float = 0.0
    position_pct: float = 50.0
    zones_away: int = 0                    # Positive = above, negative = below
    expected_spx_move: float = 0.0
    bias: str = "WAIT"                     # CALLS, PUTS, WAIT, INVALIDATED
    bias_reason: str = ""
    return_level: float = 0.0              # Level VIX should return to
    
@dataclass
class Pivot:
    """Price pivot point from prior day"""
    name: str = ""
    price: float = 0.0
    time: datetime = None
    pivot_type: str = ""                   # HIGH, LOW, CLOSE
    is_secondary: bool = False
    candle_high: float = 0.0               # For HIGH pivots: the wick high
    candle_open: float = 0.0               # For LOW pivots: open of bullish candle after
    
@dataclass  
class Cone:
    """Structural cone projected from a pivot"""
    name: str = ""
    pivot: Pivot = None
    ascending_rail: float = 0.0            # Upper boundary (PUTS entry)
    descending_rail: float = 0.0           # Lower boundary (CALLS entry)
    width: float = 0.0
    blocks: int = 0
    is_tradeable: bool = True

@dataclass
class OptionQuote:
    """Option quote data from Polygon"""
    ticker: str = ""
    underlying: str = ""                   # SPY or SPX
    strike: float = 0.0
    option_type: str = ""                  # C or P
    expiry: date = None
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    iv: float = 0.0
    open_interest: int = 0
    volume: int = 0
    in_sweet_spot: bool = False
    spx_equivalent: float = 0.0            # SPY price × 10

@dataclass
class TradeSetup:
    """Complete trade setup with entries, exits, and options"""
    direction: str = ""                    # CALLS or PUTS
    cone_name: str = ""
    cone_width: float = 0.0
    
    # SPX Levels
    entry: float = 0.0
    stop: float = 0.0
    target_25: float = 0.0
    target_50: float = 0.0
    target_75: float = 0.0
    
    # Distance from current price
    distance: float = 0.0
    is_active: bool = False                # Price at or near entry
    
    # SPY Option
    spy_option: OptionQuote = None
    
    # SPX Equivalent (estimated)
    spx_strike: int = 0
    spx_premium_est: float = 0.0
    
    # P&L Estimates
    risk_dollars: float = 0.0
    reward_25_dollars: float = 0.0
    reward_50_dollars: float = 0.0
    reward_75_dollars: float = 0.0
    rr_ratio: float = 0.0
    
    # Status
    status: str = "WAIT"                   # WAIT, ACTIVE, TRIGGERED, GREY (after 11am)

@dataclass
class HistoricalResult:
    """Historical backtest result for a single day"""
    trade_date: date = None
    direction: str = ""
    cone_name: str = ""
    entry_price: float = 0.0
    entry_premium: float = 0.0
    
    # What happened
    hit_stop: bool = False
    hit_25: bool = False
    hit_50: bool = False  
    hit_75: bool = False
    hit_100: bool = False
    
    # Prices at targets
    premium_at_25: float = 0.0
    premium_at_50: float = 0.0
    premium_at_75: float = 0.0
    
    # P&L
    exit_premium: float = 0.0
    pnl_dollars: float = 0.0
    pnl_pct: float = 0.0
    result: str = ""                       # WIN, LOSS, SCRATCH

@dataclass
class MarketData:
    """Current market data"""
    spx_price: float = 0.0
    spx_change: float = 0.0
    spx_change_pct: float = 0.0
    vix_price: float = 0.0
    spy_price: float = 0.0
    es_price: float = 0.0
    es_change: float = 0.0
    timestamp: datetime = None
    is_market_open: bool = False
    is_premarket: bool = False

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_ct_now() -> datetime:
    """Get current time in Central Time"""
    return datetime.now(CT_TZ)

def is_market_holiday(d: date) -> bool:
    """Check if date is a market holiday"""
    return d in HOLIDAYS_2025

def get_next_trading_day() -> date:
    """Get the next trading day (skips weekends and holidays)"""
    now = get_ct_now()
    today = now.date()
    current_time = now.time()
    
    # If after market close or holiday/weekend, start from tomorrow
    if current_time > MARKET_CLOSE or today.weekday() >= 5 or is_market_holiday(today):
        next_day = today + timedelta(days=1)
    else:
        next_day = today
    
    # Skip weekends and holidays
    while next_day.weekday() >= 5 or is_market_holiday(next_day):
        next_day += timedelta(days=1)
    
    return next_day

def get_prior_trading_day(from_date: date) -> date:
    """Get the trading day before the given date"""
    prior = from_date - timedelta(days=1)
    while prior.weekday() >= 5 or is_market_holiday(prior):
        prior -= timedelta(days=1)
    return prior

def format_time_ct(dt: datetime) -> str:
    """Format datetime as HH:MM CT"""
    if dt is None:
        return "--:--"
    if dt.tzinfo is None:
        dt = CT_TZ.localize(dt)
    else:
        dt = dt.astimezone(CT_TZ)
    return dt.strftime("%H:%M CT")

def format_currency(value: float) -> str:
    """Format as currency"""
    return f"${value:,.2f}"

def format_pct(value: float) -> str:
    """Format as percentage"""
    return f"{value:.1f}%"

def calculate_expected_spx_move(vix_zone_size: float) -> float:
    """Calculate expected SPX move from VIX zone size"""
    return vix_zone_size * VIX_TO_SPX_MULTIPLIER

def get_time_until(target_time: time) -> timedelta:
    """Get time remaining until target time today"""
    now = get_ct_now()
    target = CT_TZ.localize(datetime.combine(now.date(), target_time))
    if target < now:
        return timedelta(0)
    return target - now

def format_countdown(td: timedelta) -> str:
    """Format timedelta as countdown string"""
    if td.total_seconds() <= 0:
        return "NOW"
    hours, remainder = divmod(int(td.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds}s"


# =============================================================================
# POLYGON API FUNCTIONS
# =============================================================================

def polygon_get_spy_price() -> float:
    """Get current SPY price from Polygon"""
    try:
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/SPY/prev"
        params = {"apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                return data["results"][0].get("c", 0)
    except Exception as e:
        st.error(f"Error fetching SPY price: {e}")
    return 0.0

def polygon_get_spx_price() -> float:
    """Get current SPX price from Polygon"""
    try:
        url = f"{POLYGON_BASE_URL}/v3/snapshot?ticker.any_of=I:SPX"
        params = {"apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                return data["results"][0].get("value", 0)
    except Exception as e:
        st.error(f"Error fetching SPX price: {e}")
    return 0.0

def polygon_get_vix_price() -> float:
    """Get current VIX price from Polygon"""
    try:
        url = f"{POLYGON_BASE_URL}/v3/snapshot?ticker.any_of=I:VIX"
        params = {"apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                return data["results"][0].get("value", 0)
    except Exception as e:
        pass
    return 0.0

def polygon_get_spy_options_chain(expiry_date: date, strike_min: float, strike_max: float) -> List[Dict]:
    """Get SPY options chain from Polygon"""
    try:
        url = f"{POLYGON_BASE_URL}/v3/reference/options/contracts"
        params = {
            "underlying_ticker": "SPY",
            "expiration_date": expiry_date.strftime("%Y-%m-%d"),
            "strike_price.gte": strike_min,
            "strike_price.lte": strike_max,
            "limit": 100,
            "apiKey": POLYGON_API_KEY
        }
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])
    except Exception as e:
        st.error(f"Error fetching options chain: {e}")
    return []

def polygon_get_option_snapshot(ticker: str) -> Optional[Dict]:
    """Get option snapshot with Greeks from Polygon"""
    try:
        url = f"{POLYGON_BASE_URL}/v3/snapshot/options/{ticker}"
        params = {"apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("results")
    except Exception as e:
        pass
    return None

def polygon_get_option_quote(ticker: str) -> Optional[Dict]:
    """Get latest option quote from Polygon"""
    try:
        url = f"{POLYGON_BASE_URL}/v3/quotes/{ticker}"
        params = {"limit": 1, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                return data["results"][0]
    except Exception as e:
        pass
    return None

def polygon_get_historical_bars(ticker: str, from_date: date, to_date: date, timespan: str = "minute", multiplier: int = 30) -> List[Dict]:
    """Get historical price bars from Polygon"""
    try:
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}"
        params = {"adjusted": "true", "sort": "asc", "limit": 5000, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])
    except Exception as e:
        st.error(f"Error fetching historical bars: {e}")
    return []

def polygon_get_historical_option_data(option_ticker: str, trade_date: date) -> Optional[Dict]:
    """Get historical option data for backtesting"""
    try:
        # Get daily bar for the option on that date
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{option_ticker}/range/1/day/{trade_date.strftime('%Y-%m-%d')}/{trade_date.strftime('%Y-%m-%d')}"
        params = {"adjusted": "true", "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                return data["results"][0]
    except Exception as e:
        pass
    return None

def build_option_ticker(underlying: str, expiry: date, strike: float, option_type: str) -> str:
    """Build Polygon option ticker symbol"""
    date_str = expiry.strftime("%y%m%d")
    cp = "C" if option_type.upper() in ["C", "CALL", "CALLS"] else "P"
    strike_str = f"{int(strike * 1000):08d}"
    return f"O:{underlying}{date_str}{cp}{strike_str}"

def get_spy_option_for_strike(spx_entry: float, option_type: str, expiry: date) -> Optional[OptionQuote]:
    """Get the best SPY option for a given SPX entry level"""
    
    # Convert SPX level to SPY
    spy_level = spx_entry / 10
    
    # Determine strike range to search
    if option_type.upper() in ["C", "CALL", "CALLS"]:
        # For calls, we want OTM (strike above current price)
        strike_min = spy_level
        strike_max = spy_level + 10
    else:
        # For puts, we want OTM (strike below current price)
        strike_min = spy_level - 10
        strike_max = spy_level
    
    # Get options chain
    contracts = polygon_get_spy_options_chain(expiry, strike_min, strike_max)
    
    if not contracts:
        return None
    
    # Filter by option type
    cp = "call" if option_type.upper() in ["C", "CALL", "CALLS"] else "put"
    filtered = [c for c in contracts if c.get("contract_type") == cp]
    
    if not filtered:
        return None
    
    # Get snapshots for each and find best one
    best_option = None
    best_score = -999
    
    for contract in filtered[:10]:  # Check up to 10 strikes
        ticker = contract.get("ticker")
        snapshot = polygon_get_option_snapshot(ticker)
        
        if not snapshot:
            continue
        
        # Extract data
        greeks = snapshot.get("greeks", {})
        day = snapshot.get("day", {})
        
        delta = abs(greeks.get("delta", 0))
        bid = snapshot.get("last_quote", {}).get("bid", 0) or day.get("close", 0)
        ask = snapshot.get("last_quote", {}).get("ask", 0) or day.get("close", 0)
        mid = (bid + ask) / 2 if bid and ask else day.get("close", 0)
        
        # Score based on delta proximity and premium sweet spot
        delta_score = -abs(delta - DELTA_IDEAL) * 100
        
        premium_score = 0
        if PREMIUM_SWEET_LOW <= mid <= PREMIUM_SWEET_HIGH:
            premium_score = 50
        elif PREMIUM_MIN <= mid <= PREMIUM_MAX:
            premium_score = 25
        else:
            premium_score = -50
        
        total_score = delta_score + premium_score
        
        if total_score > best_score and mid > 0:
            best_score = total_score
            
            best_option = OptionQuote(
                ticker=ticker,
                underlying="SPY",
                strike=contract.get("strike_price", 0),
                option_type=cp[0].upper(),
                expiry=expiry,
                bid=bid,
                ask=ask,
                mid=mid,
                delta=greeks.get("delta", 0),
                gamma=greeks.get("gamma", 0),
                theta=greeks.get("theta", 0),
                vega=greeks.get("vega", 0),
                iv=snapshot.get("implied_volatility", 0),
                open_interest=snapshot.get("open_interest", 0),
                volume=day.get("volume", 0),
                in_sweet_spot=(PREMIUM_SWEET_LOW <= mid <= PREMIUM_SWEET_HIGH),
                spx_equivalent=mid * 10
            )
    
    return best_option

def get_open_interest_levels(expiry: date, spy_price: float) -> List[Dict]:
    """Get high open interest strikes as magnet levels"""
    
    # Get options around current price
    strike_min = spy_price - 15
    strike_max = spy_price + 15
    
    contracts = polygon_get_spy_options_chain(expiry, strike_min, strike_max)
    
    if not contracts:
        return []
    
    oi_levels = []
    
    for contract in contracts[:30]:
        ticker = contract.get("ticker")
        snapshot = polygon_get_option_snapshot(ticker)
        
        if snapshot:
            oi = snapshot.get("open_interest", 0)
            if oi > 5000:  # Significant OI threshold
                oi_levels.append({
                    "strike": contract.get("strike_price", 0),
                    "type": contract.get("contract_type", ""),
                    "oi": oi,
                    "spx_equiv": contract.get("strike_price", 0) * 10
                })
    
    # Sort by OI descending
    oi_levels.sort(key=lambda x: x["oi"], reverse=True)
    
    return oi_levels[:10]  # Top 10 levels


# =============================================================================
# VIX ZONE ANALYSIS
# =============================================================================

def analyze_vix_zone(vix_bottom: float, vix_top: float, vix_current: float) -> VIXZone:
    """Analyze VIX position and determine bias"""
    
    zone = VIXZone(
        bottom=vix_bottom,
        top=vix_top,
        current=vix_current
    )
    
    # Calculate zone size
    zone.zone_size = round(vix_top - vix_bottom, 2)
    
    # Calculate expected SPX move
    zone.expected_spx_move = calculate_expected_spx_move(zone.zone_size)
    
    # Determine position relative to zone
    if vix_current < vix_bottom:
        # Below zone
        zones_below = (vix_bottom - vix_current) / zone.zone_size if zone.zone_size > 0 else 0
        zone.zones_away = -int(np.ceil(zones_below))
        zone.position_pct = 0
        zone.return_level = vix_bottom  # VIX should return to bottom
        zone.bias = "CALLS"
        zone.bias_reason = f"VIX {abs(zone.zones_away)} zone(s) below → expect VIX to rise back to {vix_bottom:.2f}, SPX down then up"
        
    elif vix_current > vix_top:
        # Above zone
        zones_above = (vix_current - vix_top) / zone.zone_size if zone.zone_size > 0 else 0
        zone.zones_away = int(np.ceil(zones_above))
        zone.position_pct = 100
        zone.return_level = vix_top  # VIX should return to top
        zone.bias = "PUTS"
        zone.bias_reason = f"VIX {zone.zones_away} zone(s) above → expect VIX to fall back to {vix_top:.2f}, SPX up then down"
        
    else:
        # Inside zone
        zone.zones_away = 0
        if zone.zone_size > 0:
            zone.position_pct = ((vix_current - vix_bottom) / zone.zone_size) * 100
        else:
            zone.position_pct = 50
        
        # Determine bias based on position within zone
        if zone.position_pct >= 75:
            zone.bias = "CALLS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% of zone (top 25%) → expect VIX to fall, SPX up"
            zone.return_level = vix_top
        elif zone.position_pct <= 25:
            zone.bias = "PUTS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% of zone (bottom 25%) → expect VIX to rise, SPX down"
            zone.return_level = vix_bottom
        else:
            zone.bias = "WAIT"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% of zone (middle) → no clear edge, wait for breakout"
            zone.return_level = (vix_top + vix_bottom) / 2
    
    return zone

def get_vix_zone_extensions(zone: VIXZone, num_extensions: int = 4) -> Dict:
    """Calculate VIX zone extensions above and below"""
    
    extensions = {
        "above": [],
        "below": [],
        "zone": {"bottom": zone.bottom, "top": zone.top}
    }
    
    zone_size = zone.zone_size if zone.zone_size > 0 else 0.15
    
    for i in range(1, num_extensions + 1):
        extensions["above"].append({
            "level": i,
            "bottom": round(zone.top + (i - 1) * zone_size, 2),
            "top": round(zone.top + i * zone_size, 2)
        })
        extensions["below"].append({
            "level": -i,
            "bottom": round(zone.bottom - i * zone_size, 2),
            "top": round(zone.bottom - (i - 1) * zone_size, 2)
        })
    
    return extensions

# =============================================================================
# PIVOT DETECTION
# =============================================================================

def detect_pivots_from_candles(bars: List[Dict], pivot_date: date) -> List[Pivot]:
    """
    Auto-detect pivots from 30-minute candles.
    
    HIGH pivot: Green candle followed by red candle(s) that break below green's open
    LOW pivot: Red candle followed by green candle(s) that break above red's open
    """
    
    if not bars or len(bars) < 3:
        return []
    
    pivots = []
    
    # Convert to easier format
    candles = []
    for bar in bars:
        ts = bar.get("t", 0)
        if isinstance(ts, int):
            dt = datetime.fromtimestamp(ts / 1000, tz=ET_TZ).astimezone(CT_TZ)
        else:
            dt = ts
        
        candles.append({
            "time": dt,
            "open": bar.get("o", 0),
            "high": bar.get("h", 0),
            "low": bar.get("l", 0),
            "close": bar.get("c", 0),
            "is_green": bar.get("c", 0) >= bar.get("o", 0)
        })
    
    # Find HIGH pivots (highest wicks)
    # Look for green candle followed by red that breaks below green's open
    high_candidates = []
    
    for i in range(len(candles) - 1):
        curr = candles[i]
        next_c = candles[i + 1]
        
        # Green candle followed by red that breaks below
        if curr["is_green"] and not next_c["is_green"]:
            if next_c["close"] < curr["open"]:
                high_candidates.append({
                    "price": curr["high"],  # Use the wick high
                    "time": curr["time"],
                    "candle_high": curr["high"],
                    "candle_open": curr["open"]
                })
    
    # Find LOW pivots
    # Look for red candle followed by green that breaks above red's open
    low_candidates = []
    
    for i in range(len(candles) - 1):
        curr = candles[i]
        next_c = candles[i + 1]
        
        # Red candle followed by green that breaks above
        if not curr["is_green"] and next_c["is_green"]:
            if next_c["close"] > curr["open"]:
                low_candidates.append({
                    "price": next_c["open"],  # Use open of bullish candle after
                    "time": curr["time"],
                    "candle_low": curr["low"],
                    "candle_open": next_c["open"]
                })
    
    # Select the most significant pivots
    # Primary HIGH: highest high
    if high_candidates:
        high_candidates.sort(key=lambda x: x["price"], reverse=True)
        primary_high = high_candidates[0]
        pivots.append(Pivot(
            name="Prior High",
            price=primary_high["price"],
            time=primary_high["time"],
            pivot_type="HIGH",
            is_secondary=False,
            candle_high=primary_high["candle_high"],
            candle_open=primary_high["candle_open"]
        ))
        
        # Secondary highs (up to 2 more)
        for i, h in enumerate(high_candidates[1:3], 1):
            if h["price"] < primary_high["price"] * 0.999:  # At least slightly different
                pivots.append(Pivot(
                    name=f"High {i+1}",
                    price=h["price"],
                    time=h["time"],
                    pivot_type="HIGH",
                    is_secondary=True,
                    candle_high=h["candle_high"],
                    candle_open=h["candle_open"]
                ))
    
    # Primary LOW: lowest pivot price
    if low_candidates:
        low_candidates.sort(key=lambda x: x["price"])
        primary_low = low_candidates[0]
        pivots.append(Pivot(
            name="Prior Low",
            price=primary_low["price"],
            time=primary_low["time"],
            pivot_type="LOW",
            is_secondary=False,
            candle_low=primary_low.get("candle_low", 0),
            candle_open=primary_low["candle_open"]
        ))
        
        # Secondary lows (up to 2 more)
        for i, l in enumerate(low_candidates[1:3], 1):
            if l["price"] > primary_low["price"] * 1.001:
                pivots.append(Pivot(
                    name=f"Low {i+1}",
                    price=l["price"],
                    time=l["time"],
                    pivot_type="LOW",
                    is_secondary=True,
                    candle_low=l.get("candle_low", 0),
                    candle_open=l["candle_open"]
                ))
    
    # Add CLOSE pivot (always the last candle's close)
    if candles:
        last = candles[-1]
        pivots.append(Pivot(
            name="Prior Close",
            price=last["close"],
            time=CT_TZ.localize(datetime.combine(pivot_date, time(16, 0))),
            pivot_type="CLOSE",
            is_secondary=False
        ))
    
    return pivots

def create_manual_pivots(
    high_price: float, high_time: str,
    low_price: float, low_time: str,
    close_price: float,
    pivot_date: date,
    secondary_highs: List[Tuple[float, str]] = None,
    secondary_lows: List[Tuple[float, str]] = None
) -> List[Pivot]:
    """Create pivots from manual input"""
    
    pivots = []
    
    # Parse time strings (HH:MM format)
    def parse_time(time_str: str) -> datetime:
        try:
            h, m = map(int, time_str.split(":"))
            return CT_TZ.localize(datetime.combine(pivot_date, time(h, m)))
        except:
            return CT_TZ.localize(datetime.combine(pivot_date, time(12, 0)))
    
    # Primary HIGH
    if high_price > 0:
        pivots.append(Pivot(
            name="Prior High",
            price=high_price,
            time=parse_time(high_time),
            pivot_type="HIGH",
            is_secondary=False,
            candle_high=high_price
        ))
    
    # Primary LOW
    if low_price > 0:
        pivots.append(Pivot(
            name="Prior Low",
            price=low_price,
            time=parse_time(low_time),
            pivot_type="LOW",
            is_secondary=False,
            candle_open=low_price
        ))
    
    # CLOSE
    if close_price > 0:
        pivots.append(Pivot(
            name="Prior Close",
            price=close_price,
            time=CT_TZ.localize(datetime.combine(pivot_date, time(16, 0))),
            pivot_type="CLOSE",
            is_secondary=False
        ))
    
    # Secondary highs
    if secondary_highs:
        for i, (price, time_str) in enumerate(secondary_highs, 1):
            if price > 0:
                pivots.append(Pivot(
                    name=f"High {i+1}",
                    price=price,
                    time=parse_time(time_str),
                    pivot_type="HIGH",
                    is_secondary=True,
                    candle_high=price
                ))
    
    # Secondary lows
    if secondary_lows:
        for i, (price, time_str) in enumerate(secondary_lows, 1):
            if price > 0:
                pivots.append(Pivot(
                    name=f"Low {i+1}",
                    price=price,
                    time=parse_time(time_str),
                    pivot_type="LOW",
                    is_secondary=True,
                    candle_open=price
                ))
    
    return pivots


# =============================================================================
# CONE BUILDING
# =============================================================================

def count_blocks(start_time: datetime, eval_time: datetime) -> int:
    """
    Count 30-minute blocks between two times.
    Respects futures trading hours (freezes 4-5pm CT).
    """
    
    if eval_time <= start_time:
        return 0
    
    MAINTENANCE_START = time(16, 0)  # 4:00 PM CT
    MAINTENANCE_END = time(17, 0)    # 5:00 PM CT
    
    total_blocks = 0
    current = start_time
    
    # Ensure timezone aware
    if current.tzinfo is None:
        current = CT_TZ.localize(current)
    if eval_time.tzinfo is None:
        eval_time = CT_TZ.localize(eval_time)
    
    max_iterations = 1000
    iterations = 0
    
    while current < eval_time and iterations < max_iterations:
        iterations += 1
        current_t = current.time()
        weekday = current.weekday()
        
        # Skip weekends
        if weekday >= 5:  # Saturday or Sunday
            if weekday == 5:  # Saturday
                current = CT_TZ.localize(datetime.combine(
                    current.date() + timedelta(days=2), MAINTENANCE_END))
            else:  # Sunday
                if current_t < MAINTENANCE_END:
                    current = CT_TZ.localize(datetime.combine(
                        current.date(), MAINTENANCE_END))
                else:
                    current = CT_TZ.localize(datetime.combine(
                        current.date() + timedelta(days=1), MAINTENANCE_END))
            continue
        
        # Handle maintenance window (4-5pm CT)
        if MAINTENANCE_START <= current_t < MAINTENANCE_END:
            current = CT_TZ.localize(datetime.combine(current.date(), MAINTENANCE_END))
            continue
        
        # Friday after 4pm -> skip to Sunday 5pm
        if weekday == 4 and current_t >= MAINTENANCE_START:
            current = CT_TZ.localize(datetime.combine(
                current.date() + timedelta(days=2), MAINTENANCE_END))
            continue
        
        # Calculate next block
        next_block = current + timedelta(minutes=30)
        
        if next_block > eval_time:
            break
        
        # Check if crosses maintenance
        if current_t < MAINTENANCE_START and next_block.time() >= MAINTENANCE_START:
            total_blocks += 1
            current = CT_TZ.localize(datetime.combine(current.date(), MAINTENANCE_END))
            continue
        
        total_blocks += 1
        current = next_block
    
    return max(total_blocks, 1)

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    """Build structural cones from pivots at evaluation time"""
    
    cones = []
    
    for pivot in pivots:
        if pivot.price <= 0:
            continue
        
        # Count blocks from 30 min after pivot
        start_time = pivot.time + timedelta(minutes=30) if pivot.time else eval_time
        blocks = count_blocks(start_time, eval_time)
        
        # Calculate rail expansion
        expansion = blocks * SLOPE_PER_30MIN
        
        # For HIGH pivots, use candle_high for ascending rail
        # For LOW pivots, use candle_open (open of bullish candle after)
        if pivot.pivot_type == "HIGH":
            ascending = pivot.candle_high + expansion if pivot.candle_high > 0 else pivot.price + expansion
            descending = pivot.price - expansion
        elif pivot.pivot_type == "LOW":
            ascending = pivot.price + expansion
            descending = pivot.candle_open - expansion if pivot.candle_open > 0 else pivot.price - expansion
        else:  # CLOSE
            ascending = pivot.price + expansion
            descending = pivot.price - expansion
        
        width = ascending - descending
        
        cones.append(Cone(
            name=pivot.name,
            pivot=pivot,
            ascending_rail=round(ascending, 2),
            descending_rail=round(descending, 2),
            width=round(width, 2),
            blocks=blocks,
            is_tradeable=(width >= MIN_CONE_WIDTH)
        ))
    
    return cones

def get_cone_position(price: float, cones: List[Cone]) -> Dict:
    """Determine which cone price is in and distance to rails"""
    
    result = {
        "inside_cone": None,
        "nearest_cone": None,
        "nearest_rail": None,
        "distance_to_rail": float('inf'),
        "at_rail": False,
        "rail_type": None  # 'ascending' or 'descending'
    }
    
    if not cones:
        return result
    
    # Check each cone
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        dist_to_asc = cone.ascending_rail - price
        dist_to_desc = price - cone.descending_rail
        
        # Inside cone?
        if dist_to_asc >= 0 and dist_to_desc >= 0:
            result["inside_cone"] = cone
            
            # Which rail is closer?
            if dist_to_asc < dist_to_desc:
                result["nearest_rail"] = cone.ascending_rail
                result["distance_to_rail"] = dist_to_asc
                result["rail_type"] = "ascending"
            else:
                result["nearest_rail"] = cone.descending_rail
                result["distance_to_rail"] = dist_to_desc
                result["rail_type"] = "descending"
            
            # At rail?
            if result["distance_to_rail"] <= RAIL_PROXIMITY:
                result["at_rail"] = True
            
            return result
        
        # Track nearest rail overall
        for rail, rtype in [(cone.ascending_rail, "ascending"), (cone.descending_rail, "descending")]:
            dist = abs(price - rail)
            if dist < result["distance_to_rail"]:
                result["nearest_cone"] = cone
                result["nearest_rail"] = rail
                result["distance_to_rail"] = dist
                result["rail_type"] = rtype
                result["at_rail"] = (dist <= RAIL_PROXIMITY)
    
    return result

# =============================================================================
# TRADE SETUP GENERATION
# =============================================================================

def generate_setups(cones: List[Cone], current_price: float, vix_bias: str, expiry: date, is_after_cutoff: bool = False) -> List[TradeSetup]:
    """Generate trade setups with real options data"""
    
    setups = []
    
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        # ========== CALLS SETUP (Enter at Descending Rail) ==========
        entry_c = cone.descending_rail
        distance_c = abs(current_price - entry_c)
        
        # Targets based on cone width
        t25_c = round(entry_c + cone.width * 0.25, 2)
        t50_c = round(entry_c + cone.width * 0.50, 2)
        t75_c = round(entry_c + cone.width * 0.75, 2)
        stop_c = round(entry_c - STOP_LOSS_PTS, 2)
        
        # Get SPY option
        spy_option_c = get_spy_option_for_strike(entry_c, "C", expiry)
        
        # Calculate SPX equivalent strike (OTM above entry)
        spx_strike_c = int(round((entry_c + 17.5) / 5) * 5)
        
        # Status
        status_c = "GREY" if is_after_cutoff else ("ACTIVE" if distance_c <= RAIL_PROXIMITY else "WAIT")
        
        # P&L estimates using real delta if available
        delta = abs(spy_option_c.delta) if spy_option_c else DELTA_IDEAL
        risk_pts = STOP_LOSS_PTS * delta
        reward_25 = cone.width * 0.25 * delta
        reward_50 = cone.width * 0.50 * delta
        reward_75 = cone.width * 0.75 * delta
        
        setup_c = TradeSetup(
            direction="CALLS",
            cone_name=cone.name,
            cone_width=cone.width,
            entry=entry_c,
            stop=stop_c,
            target_25=t25_c,
            target_50=t50_c,
            target_75=t75_c,
            distance=round(distance_c, 1),
            is_active=(distance_c <= RAIL_PROXIMITY),
            spy_option=spy_option_c,
            spx_strike=spx_strike_c,
            spx_premium_est=spy_option_c.spx_equivalent if spy_option_c else 0,
            risk_dollars=round(risk_pts * 100, 0),
            reward_25_dollars=round(reward_25 * 100, 0),
            reward_50_dollars=round(reward_50 * 100, 0),
            reward_75_dollars=round(reward_75 * 100, 0),
            rr_ratio=round(reward_50 / risk_pts, 1) if risk_pts > 0 else 0,
            status=status_c
        )
        setups.append(setup_c)
        
        # ========== PUTS SETUP (Enter at Ascending Rail) ==========
        entry_p = cone.ascending_rail
        distance_p = abs(current_price - entry_p)
        
        t25_p = round(entry_p - cone.width * 0.25, 2)
        t50_p = round(entry_p - cone.width * 0.50, 2)
        t75_p = round(entry_p - cone.width * 0.75, 2)
        stop_p = round(entry_p + STOP_LOSS_PTS, 2)
        
        spy_option_p = get_spy_option_for_strike(entry_p, "P", expiry)
        spx_strike_p = int(round((entry_p - 17.5) / 5) * 5)
        
        status_p = "GREY" if is_after_cutoff else ("ACTIVE" if distance_p <= RAIL_PROXIMITY else "WAIT")
        
        delta_p = abs(spy_option_p.delta) if spy_option_p else DELTA_IDEAL
        risk_pts_p = STOP_LOSS_PTS * delta_p
        reward_25_p = cone.width * 0.25 * delta_p
        reward_50_p = cone.width * 0.50 * delta_p
        reward_75_p = cone.width * 0.75 * delta_p
        
        setup_p = TradeSetup(
            direction="PUTS",
            cone_name=cone.name,
            cone_width=cone.width,
            entry=entry_p,
            stop=stop_p,
            target_25=t25_p,
            target_50=t50_p,
            target_75=t75_p,
            distance=round(distance_p, 1),
            is_active=(distance_p <= RAIL_PROXIMITY),
            spy_option=spy_option_p,
            spx_strike=spx_strike_p,
            spx_premium_est=spy_option_p.spx_equivalent if spy_option_p else 0,
            risk_dollars=round(risk_pts_p * 100, 0),
            reward_25_dollars=round(reward_25_p * 100, 0),
            reward_50_dollars=round(reward_50_p * 100, 0),
            reward_75_dollars=round(reward_75_p * 100, 0),
            rr_ratio=round(reward_50_p / risk_pts_p, 1) if risk_pts_p > 0 else 0,
            status=status_p
        )
        setups.append(setup_p)
    
    return setups


# =============================================================================
# HISTORICAL BACKTESTING
# =============================================================================

def backtest_day(trade_date: date, pivots: List[Pivot], vix_zone: VIXZone) -> List[HistoricalResult]:
    """Backtest a single day with historical options data"""
    
    results = []
    
    # Build cones at 9:00 AM CT
    eval_time = CT_TZ.localize(datetime.combine(trade_date, time(9, 0)))
    cones = build_cones(pivots, eval_time)
    
    # Get SPX high/low for the day
    bars = polygon_get_historical_bars("I:SPX", trade_date, trade_date, "minute", 1)
    
    if not bars:
        return results
    
    day_high = max(b.get("h", 0) for b in bars)
    day_low = min(b.get("l", 0) for b in bars)
    day_open = bars[0].get("o", 0) if bars else 0
    day_close = bars[-1].get("c", 0) if bars else 0
    
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        # ========== CALLS Analysis ==========
        entry_c = cone.descending_rail
        t25_c = entry_c + cone.width * 0.25
        t50_c = entry_c + cone.width * 0.50
        t75_c = entry_c + cone.width * 0.75
        t100_c = cone.ascending_rail
        stop_c = entry_c - STOP_LOSS_PTS
        
        # Check if entry was hit
        if day_low <= entry_c:
            # Entry triggered
            hit_stop = day_low <= stop_c
            hit_25 = day_high >= t25_c
            hit_50 = day_high >= t50_c
            hit_75 = day_high >= t75_c
            hit_100 = day_high >= t100_c
            
            # Get historical option data
            spy_strike = int(round((entry_c + 17.5) / 10))
            option_ticker = build_option_ticker("SPY", trade_date, spy_strike, "C")
            option_data = polygon_get_historical_option_data(option_ticker, trade_date)
            
            entry_premium = option_data.get("o", 0) if option_data else 0
            exit_premium = 0
            result_str = ""
            pnl = 0
            
            if hit_stop and not hit_50:
                result_str = "LOSS"
                # Estimate exit premium (entry - stop loss impact)
                exit_premium = max(0, entry_premium - (STOP_LOSS_PTS * DELTA_IDEAL))
                pnl = (exit_premium - entry_premium) * 100
            elif hit_75:
                result_str = "WIN (75%)"
                exit_premium = entry_premium + (cone.width * 0.75 * DELTA_IDEAL)
                pnl = (exit_premium - entry_premium) * 100
            elif hit_50:
                result_str = "WIN (50%)"
                exit_premium = entry_premium + (cone.width * 0.50 * DELTA_IDEAL)
                pnl = (exit_premium - entry_premium) * 100
            elif hit_25:
                result_str = "WIN (25%)"
                exit_premium = entry_premium + (cone.width * 0.25 * DELTA_IDEAL)
                pnl = (exit_premium - entry_premium) * 100
            else:
                result_str = "SCRATCH"
                exit_premium = entry_premium
                pnl = 0
            
            results.append(HistoricalResult(
                trade_date=trade_date,
                direction="CALLS",
                cone_name=cone.name,
                entry_price=entry_c,
                entry_premium=entry_premium,
                hit_stop=hit_stop,
                hit_25=hit_25,
                hit_50=hit_50,
                hit_75=hit_75,
                hit_100=hit_100,
                exit_premium=exit_premium,
                pnl_dollars=round(pnl, 2),
                pnl_pct=round((pnl / (entry_premium * 100)) * 100, 1) if entry_premium > 0 else 0,
                result=result_str
            ))
        
        # ========== PUTS Analysis ==========
        entry_p = cone.ascending_rail
        t25_p = entry_p - cone.width * 0.25
        t50_p = entry_p - cone.width * 0.50
        t75_p = entry_p - cone.width * 0.75
        t100_p = cone.descending_rail
        stop_p = entry_p + STOP_LOSS_PTS
        
        if day_high >= entry_p:
            hit_stop = day_high >= stop_p
            hit_25 = day_low <= t25_p
            hit_50 = day_low <= t50_p
            hit_75 = day_low <= t75_p
            hit_100 = day_low <= t100_p
            
            spy_strike = int(round((entry_p - 17.5) / 10))
            option_ticker = build_option_ticker("SPY", trade_date, spy_strike, "P")
            option_data = polygon_get_historical_option_data(option_ticker, trade_date)
            
            entry_premium = option_data.get("o", 0) if option_data else 0
            exit_premium = 0
            result_str = ""
            pnl = 0
            
            if hit_stop and not hit_50:
                result_str = "LOSS"
                exit_premium = max(0, entry_premium - (STOP_LOSS_PTS * DELTA_IDEAL))
                pnl = (exit_premium - entry_premium) * 100
            elif hit_75:
                result_str = "WIN (75%)"
                exit_premium = entry_premium + (cone.width * 0.75 * DELTA_IDEAL)
                pnl = (exit_premium - entry_premium) * 100
            elif hit_50:
                result_str = "WIN (50%)"
                exit_premium = entry_premium + (cone.width * 0.50 * DELTA_IDEAL)
                pnl = (exit_premium - entry_premium) * 100
            elif hit_25:
                result_str = "WIN (25%)"
                exit_premium = entry_premium + (cone.width * 0.25 * DELTA_IDEAL)
                pnl = (exit_premium - entry_premium) * 100
            else:
                result_str = "SCRATCH"
                exit_premium = entry_premium
                pnl = 0
            
            results.append(HistoricalResult(
                trade_date=trade_date,
                direction="PUTS",
                cone_name=cone.name,
                entry_price=entry_p,
                entry_premium=entry_premium,
                hit_stop=hit_stop,
                hit_25=hit_25,
                hit_50=hit_50,
                hit_75=hit_75,
                hit_100=hit_100,
                exit_premium=exit_premium,
                pnl_dollars=round(pnl, 2),
                pnl_pct=round((pnl / (entry_premium * 100)) * 100, 1) if entry_premium > 0 else 0,
                result=result_str
            ))
    
    return results

# =============================================================================
# ALERTS
# =============================================================================

def check_alerts(setups: List[TradeSetup], vix_zone: VIXZone, current_time: time) -> List[Dict]:
    """Check for alert conditions"""
    
    alerts = []
    
    # Check for active setups (price at rail)
    for setup in setups:
        if setup.is_active and setup.status != "GREY":
            alerts.append({
                "type": "RAIL_TOUCH",
                "priority": "HIGH",
                "message": f"🎯 {setup.direction} setup ACTIVE at {setup.cone_name}! Entry: {setup.entry:,.2f}",
                "sound": True
            })
    
    # Check for approaching rails
    for setup in setups:
        if 3 < setup.distance <= 10 and setup.status != "GREY":
            alerts.append({
                "type": "APPROACHING",
                "priority": "MEDIUM", 
                "message": f"⚠️ Price approaching {setup.cone_name} {setup.direction} entry ({setup.distance:.1f} pts away)",
                "sound": False
            })
    
    # VIX zone break
    if vix_zone.zones_away != 0:
        alerts.append({
            "type": "VIX_BREAK",
            "priority": "HIGH",
            "message": f"📊 VIX broke zone! {abs(vix_zone.zones_away)} zone(s) {'above' if vix_zone.zones_away > 0 else 'below'}",
            "sound": True
        })
    
    # Institutional window
    if INSTITUTIONAL_START <= current_time <= INSTITUTIONAL_END:
        alerts.append({
            "type": "INSTITUTIONAL",
            "priority": "INFO",
            "message": "🏛️ Institutional Window (9:00-9:30 CT) - Watch for setups!",
            "sound": False
        })
    
    # Entry target time
    if current_time == ENTRY_TARGET:
        alerts.append({
            "type": "ENTRY_TIME",
            "priority": "HIGH",
            "message": "⏰ 9:40 CT - Optimal entry window!",
            "sound": True
        })
    
    return alerts


# =============================================================================
# LEGENDARY GLASS NEOMORPHISM UI
# =============================================================================

def generate_dashboard_html(
    market_data: MarketData,
    vix_zone: VIXZone,
    cones: List[Cone],
    calls_setups: List[TradeSetup],
    puts_setups: List[TradeSetup],
    prior_session: Dict,
    oi_levels: List[Dict],
    alerts: List[Dict],
    is_historical: bool = False,
    historical_date: date = None,
    historical_results: List[HistoricalResult] = None,
    theme: str = "light"
) -> str:
    """Generate the legendary glass neomorphism dashboard"""
    
    # Theme colors
    if theme == "dark":
        bg_primary = "#0f0f1a"
        bg_secondary = "#1a1a2e"
        bg_card = "rgba(30, 30, 50, 0.7)"
        bg_glass = "rgba(255, 255, 255, 0.03)"
        text_primary = "#ffffff"
        text_secondary = "#a0a0b0"
        text_muted = "#606070"
        border_color = "rgba(255, 255, 255, 0.1)"
        shadow_color = "rgba(0, 0, 0, 0.5)"
        glow_green = "rgba(16, 185, 129, 0.3)"
        glow_red = "rgba(239, 68, 68, 0.3)"
        glow_blue = "rgba(59, 130, 246, 0.3)"
    else:
        bg_primary = "#f0f4f8"
        bg_secondary = "#e2e8f0"
        bg_card = "rgba(255, 255, 255, 0.7)"
        bg_glass = "rgba(255, 255, 255, 0.5)"
        text_primary = "#1a202c"
        text_secondary = "#4a5568"
        text_muted = "#718096"
        border_color = "rgba(0, 0, 0, 0.1)"
        shadow_color = "rgba(0, 0, 0, 0.1)"
        glow_green = "rgba(16, 185, 129, 0.2)"
        glow_red = "rgba(239, 68, 68, 0.2)"
        glow_blue = "rgba(59, 130, 246, 0.2)"
    
    # Common colors
    green = "#10b981"
    red = "#ef4444"
    amber = "#f59e0b"
    blue = "#3b82f6"
    purple = "#8b5cf6"
    
    # Bias styling
    if vix_zone.bias == "CALLS":
        bias_color = green
        bias_glow = glow_green
        bias_icon = "▲"
        bias_text = "BULLISH"
    elif vix_zone.bias == "PUTS":
        bias_color = red
        bias_glow = glow_red
        bias_icon = "▼"
        bias_text = "BEARISH"
    elif vix_zone.bias == "INVALIDATED":
        bias_color = "#6b7280"
        bias_glow = "rgba(107, 114, 128, 0.3)"
        bias_icon = "✕"
        bias_text = "INVALIDATED"
    else:
        bias_color = amber
        bias_glow = "rgba(245, 158, 11, 0.3)"
        bias_icon = "●"
        bias_text = "NEUTRAL"
    
    # Time calculations
    now = get_ct_now()
    time_to_cutoff = get_time_until(CUTOFF_TIME)
    time_to_entry = get_time_until(ENTRY_TARGET)
    is_inst_window = INSTITUTIONAL_START <= now.time() <= INSTITUTIONAL_END
    is_after_cutoff = now.time() > CUTOFF_TIME
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SPX Prophet v6.0</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        :root {{
            --bg-primary: {bg_primary};
            --bg-secondary: {bg_secondary};
            --bg-card: {bg_card};
            --bg-glass: {bg_glass};
            --text-primary: {text_primary};
            --text-secondary: {text_secondary};
            --text-muted: {text_muted};
            --border-color: {border_color};
            --shadow-color: {shadow_color};
            --green: {green};
            --red: {red};
            --amber: {amber};
            --blue: {blue};
            --purple: {purple};
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 24px;
            background-image: 
                radial-gradient(ellipse at 20% 20%, {glow_blue} 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, {glow_green} 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, {bias_glow} 0%, transparent 60%);
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}
        
        /* Glass Card Effect */
        .glass-card {{
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 
                0 8px 32px var(--shadow-color),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
        }}
        
        .glass-card:hover {{
            transform: translateY(-2px);
            box-shadow: 
                0 12px 40px var(--shadow-color),
                inset 0 1px 0 rgba(255, 255, 255, 0.15);
        }}
        
        .glass-card.collapsed {{
            padding: 16px 24px;
        }}
        
        .glass-card.collapsed .card-content {{
            display: none;
        }}
        
        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            flex-wrap: wrap;
            gap: 20px;
        }}
        
        .logo {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        
        .logo-icon {{
            width: 64px;
            height: 64px;
            background: linear-gradient(135deg, {blue} 0%, {purple} 100%);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 900;
            color: white;
            box-shadow: 0 8px 24px rgba(59, 130, 246, 0.4);
        }}
        
        .logo-text h1 {{
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, {text_primary} 0%, {text_secondary} 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .logo-tagline {{
            font-size: 14px;
            color: var(--text-secondary);
            font-style: italic;
            margin-top: 4px;
        }}
        
        .header-right {{
            display: flex;
            align-items: center;
            gap: 24px;
        }}
        
        .time-display {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 32px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        .countdown {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}
        
        .countdown-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
        }}
        
        .countdown-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 18px;
            font-weight: 600;
            color: {amber};
        }}
        
        /* Section Headers */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            user-select: none;
        }}
        
        .section-title {{
            font-size: 14px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .section-title .icon {{
            font-size: 18px;
        }}
        
        .toggle-icon {{
            font-size: 20px;
            color: var(--text-muted);
            transition: transform 0.3s ease;
        }}
        
        .glass-card.collapsed .toggle-icon {{
            transform: rotate(-90deg);
        }}
        
        .card-content {{
            margin-top: 20px;
        }}
        
        /* VIX Zone Display */
        .vix-zone-container {{
            display: grid;
            grid-template-columns: 1fr 300px;
            gap: 24px;
            align-items: center;
        }}
        
        .vix-ladder {{
            position: relative;
            height: 180px;
            background: var(--bg-glass);
            border-radius: 16px;
            padding: 20px;
            overflow: hidden;
        }}
        
        .vix-zone-bar {{
            position: absolute;
            left: 20px;
            right: 20px;
            height: 40px;
            background: linear-gradient(90deg, 
                {green}40 0%, 
                var(--bg-secondary) 25%,
                var(--bg-secondary) 75%,
                {red}40 100%
            );
            border-radius: 20px;
            top: 50%;
            transform: translateY(-50%);
        }}
        
        .vix-marker {{
            position: absolute;
            width: 24px;
            height: 24px;
            background: {bias_color};
            border-radius: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            box-shadow: 0 0 20px {bias_color};
            border: 3px solid var(--bg-card);
            z-index: 10;
        }}
        
        .vix-labels {{
            display: flex;
            justify-content: space-between;
            position: absolute;
            bottom: 20px;
            left: 20px;
            right: 20px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--text-muted);
        }}
        
        .vix-info {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        
        .vix-stat {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: var(--bg-glass);
            border-radius: 12px;
        }}
        
        .vix-stat-label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .vix-stat-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 16px;
            font-weight: 600;
        }}
        
        /* Bias Display */
        .bias-card {{
            background: linear-gradient(135deg, {bias_color}20 0%, {bias_color}05 100%);
            border: 2px solid {bias_color}50;
            text-align: center;
            padding: 32px;
        }}
        
        .bias-icon {{
            font-size: 48px;
            color: {bias_color};
            margin-bottom: 12px;
            text-shadow: 0 0 30px {bias_color};
        }}
        
        .bias-label {{
            font-size: 24px;
            font-weight: 800;
            color: {bias_color};
            letter-spacing: 2px;
        }}
        
        .bias-reason {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 12px;
            line-height: 1.5;
        }}
        
        /* Setup Tables */
        .setups-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        thead {{
            background: var(--bg-glass);
        }}
        
        th {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            padding: 16px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        
        td {{
            padding: 16px 12px;
            font-size: 14px;
            border-bottom: 1px solid var(--border-color);
        }}
        
        tr:last-child td {{
            border-bottom: none;
        }}
        
        tbody tr {{
            transition: all 0.2s ease;
        }}
        
        tbody tr:hover {{
            background: var(--bg-glass);
        }}
        
        tbody tr.active {{
            background: linear-gradient(90deg, {green}20 0%, transparent 100%);
            animation: pulse 2s infinite;
        }}
        
        tbody tr.grey {{
            opacity: 0.4;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
        
        .mono {{
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .text-green {{ color: {green}; }}
        .text-red {{ color: {red}; }}
        .text-amber {{ color: {amber}; }}
        .text-blue {{ color: {blue}; }}
        
        /* Pills */
        .pill {{
            display: inline-flex;
            align-items: center;
            padding: 6px 14px;
            border-radius: 100px;
            font-size: 12px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .pill-green {{
            background: {green}20;
            color: {green};
        }}
        
        .pill-red {{
            background: {red}20;
            color: {red};
        }}
        
        .pill-amber {{
            background: {amber}20;
            color: {amber};
        }}
        
        .pill-blue {{
            background: {blue}20;
            color: {blue};
        }}
        
        .pill-grey {{
            background: rgba(107, 114, 128, 0.2);
            color: #6b7280;
        }}
        
        /* Sweet Spot Indicator */
        .sweet-spot {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            color: {green};
        }}
        
        .sweet-spot::before {{
            content: "★";
        }}
        
        /* Grid layouts */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
        }}
        
        .stat-card {{
            background: var(--bg-glass);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
        }}
        
        .stat-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 24px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        .stat-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-top: 8px;
        }}
        
        /* Institutional Window Banner */
        .inst-window {{
            background: linear-gradient(135deg, {amber}30 0%, {amber}10 100%);
            border: 2px solid {amber}50;
            border-radius: 16px;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 20px;
            animation: glow 2s ease-in-out infinite;
        }}
        
        @keyframes glow {{
            0%, 100% {{ box-shadow: 0 0 20px {amber}30; }}
            50% {{ box-shadow: 0 0 40px {amber}50; }}
        }}
        
        .inst-icon {{
            font-size: 32px;
        }}
        
        .inst-text {{
            flex: 1;
        }}
        
        .inst-title {{
            font-weight: 700;
            color: {amber};
            font-size: 16px;
        }}
        
        .inst-sub {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        
        /* Alert Box */
        .alert {{
            padding: 16px 20px;
            border-radius: 12px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .alert-high {{
            background: {red}20;
            border-left: 4px solid {red};
        }}
        
        .alert-medium {{
            background: {amber}20;
            border-left: 4px solid {amber};
        }}
        
        .alert-info {{
            background: {blue}20;
            border-left: 4px solid {blue};
        }}
        
        /* Historical Mode Banner */
        .historical-banner {{
            background: linear-gradient(135deg, {purple}30 0%, {purple}10 100%);
            border: 2px solid {purple}50;
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        
        .historical-icon {{
            font-size: 36px;
        }}
        
        .historical-date {{
            font-size: 20px;
            font-weight: 700;
            color: {purple};
        }}
        
        .historical-sub {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 32px;
            color: var(--text-muted);
            font-size: 12px;
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            body {{
                padding: 12px;
            }}
            
            .header {{
                flex-direction: column;
                text-align: center;
            }}
            
            .vix-zone-container {{
                grid-template-columns: 1fr;
            }}
            
            .setups-container {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
'''
    
    # Header
    html += f'''
        <div class="header">
            <div class="logo">
                <div class="logo-icon">SP</div>
                <div class="logo-text">
                    <h1>SPX Prophet</h1>
                    <div class="logo-tagline">Where Structure Becomes Foresight</div>
                </div>
            </div>
            <div class="header-right">
                <div class="countdown">
                    <span class="countdown-label">Time to 11am Cutoff</span>
                    <span class="countdown-value">{format_countdown(time_to_cutoff) if not is_after_cutoff else "CLOSED"}</span>
                </div>
                <div class="time-display">{now.strftime("%H:%M")} CT</div>
            </div>
        </div>
'''
    
    # Historical Mode Banner
    if is_historical and historical_date:
        html += f'''
        <div class="historical-banner">
            <div class="historical-icon">📅</div>
            <div>
                <div class="historical-date">{historical_date.strftime("%A, %B %d, %Y")}</div>
                <div class="historical-sub">Historical Analysis Mode</div>
            </div>
        </div>
'''
    
    # Institutional Window Banner
    if is_inst_window and not is_historical:
        html += f'''
        <div class="inst-window">
            <div class="inst-icon">🏛️</div>
            <div class="inst-text">
                <div class="inst-title">INSTITUTIONAL WINDOW ACTIVE</div>
                <div class="inst-sub">9:00 - 9:30 AM CT • Watch for large order flow and setup triggers</div>
            </div>
            <div class="countdown">
                <span class="countdown-value">{format_countdown(get_time_until(INSTITUTIONAL_END))}</span>
            </div>
        </div>
'''
    
    # Alerts Section
    if alerts:
        html += '''<div class="glass-card" style="padding: 16px 24px;">'''
        for alert in alerts[:3]:  # Show top 3 alerts
            alert_class = f"alert-{alert['priority'].lower()}"
            html += f'''
            <div class="alert {alert_class}">
                <span>{alert['message']}</span>
            </div>
'''
        html += '''</div>'''
    
    # VIX Zone Section (Priority 1)
    html += f'''
        <div class="glass-card">
            <div class="section-header" onclick="toggleCard(this)">
                <div class="section-title">
                    <span class="icon">📊</span>
                    VIX ZONE ANALYSIS
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="card-content">
                <div class="vix-zone-container">
                    <div class="vix-ladder">
                        <div class="vix-zone-bar"></div>
                        <div class="vix-marker" style="left: {min(max(vix_zone.position_pct, 5), 95)}%;"></div>
                        <div class="vix-labels">
                            <span>{vix_zone.bottom:.2f}</span>
                            <span>Zone: {vix_zone.zone_size:.2f}</span>
                            <span>{vix_zone.top:.2f}</span>
                        </div>
                    </div>
                    <div class="vix-info">
                        <div class="vix-stat">
                            <span class="vix-stat-label">Current VIX</span>
                            <span class="vix-stat-value">{vix_zone.current:.2f}</span>
                        </div>
                        <div class="vix-stat">
                            <span class="vix-stat-label">Position</span>
                            <span class="vix-stat-value">{vix_zone.position_pct:.0f}%{f" ({'+' if vix_zone.zones_away > 0 else ''}{vix_zone.zones_away} zones)" if vix_zone.zones_away != 0 else ""}</span>
                        </div>
                        <div class="vix-stat">
                            <span class="vix-stat-label">Expected SPX Move</span>
                            <span class="vix-stat-value text-blue">±{vix_zone.expected_spx_move:.0f} pts</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
'''
    
    # Bias Card (Priority 5)
    html += f'''
        <div class="glass-card bias-card">
            <div class="bias-icon">{bias_icon}</div>
            <div class="bias-label">{bias_text}</div>
            <div class="bias-reason">{vix_zone.bias_reason}</div>
        </div>
'''
    
    # Continue in next part...
    return html  # Temporary return, will be extended

def generate_setups_html(setups: List[TradeSetup], direction: str, color: str, theme: str) -> str:
    """Generate HTML for a setups table"""
    
    green = "#10b981"
    red = "#ef4444"
    amber = "#f59e0b"
    
    html = f'''
        <table>
            <thead>
                <tr>
                    <th>Cone</th>
                    <th>SPX Entry</th>
                    <th>SPY Option</th>
                    <th>Bid/Ask</th>
                    <th>SPX Est.</th>
                    <th>Delta</th>
                    <th>Theta</th>
                    <th>IV</th>
                    <th>Stop</th>
                    <th>T50%</th>
                    <th>R:R</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
'''
    
    filtered = [s for s in setups if s.direction == direction]
    
    for setup in filtered:
        row_class = ""
        if setup.status == "ACTIVE":
            row_class = "active"
        elif setup.status == "GREY":
            row_class = "grey"
        
        # Option data
        if setup.spy_option:
            opt = setup.spy_option
            spy_ticker = f"{int(opt.strike)}{opt.option_type}"
            bid_ask = f"${opt.bid:.2f}/${opt.ask:.2f}"
            spx_est = f"${opt.spx_equivalent:.0f}"
            delta_val = f"{abs(opt.delta):.2f}"
            theta_val = f"${opt.theta:.2f}"
            iv_val = f"{opt.iv*100:.1f}%"
            sweet = opt.in_sweet_spot
        else:
            spy_ticker = "--"
            bid_ask = "--"
            spx_est = "--"
            delta_val = "--"
            theta_val = "--"
            iv_val = "--"
            sweet = False
        
        # Status pill
        if setup.status == "ACTIVE":
            status_html = f'<span class="pill pill-green">🎯 ACTIVE</span>'
        elif setup.status == "GREY":
            status_html = f'<span class="pill pill-grey">CLOSED</span>'
        else:
            status_html = f'<span class="pill pill-amber">{setup.distance:.0f} pts</span>'
        
        entry_color = green if direction == "CALLS" else red
        
        html += f'''
                <tr class="{row_class}">
                    <td><strong>{setup.cone_name}</strong></td>
                    <td class="mono" style="color:{entry_color};">{setup.entry:,.2f}</td>
                    <td class="mono">{spy_ticker}{"<span class='sweet-spot'></span>" if sweet else ""}</td>
                    <td class="mono">{bid_ask}</td>
                    <td class="mono">{spx_est}</td>
                    <td class="mono">{delta_val}</td>
                    <td class="mono text-red">{theta_val}</td>
                    <td class="mono">{iv_val}</td>
                    <td class="mono" style="color:{red if direction == 'CALLS' else green};">{setup.stop:,.2f}</td>
                    <td class="mono">{setup.target_50:,.2f}</td>
                    <td class="mono text-green"><strong>1:{setup.rr_ratio:.1f}</strong></td>
                    <td>{status_html}</td>
                </tr>
'''
    
    html += '''
            </tbody>
        </table>
'''
    return html

def generate_full_dashboard_html(
    market_data: MarketData,
    vix_zone: VIXZone,
    cones: List[Cone],
    calls_setups: List[TradeSetup],
    puts_setups: List[TradeSetup],
    prior_session: Dict,
    oi_levels: List[Dict],
    alerts: List[Dict],
    is_historical: bool = False,
    historical_date: date = None,
    historical_results: List[HistoricalResult] = None,
    theme: str = "light"
) -> str:
    """Generate complete dashboard HTML"""
    
    # Start with base HTML from generate_dashboard_html
    html = generate_dashboard_html(
        market_data, vix_zone, cones, calls_setups, puts_setups,
        prior_session, oi_levels, alerts, is_historical, historical_date,
        historical_results, theme
    )
    
    green = "#10b981"
    red = "#ef4444"
    amber = "#f59e0b"
    blue = "#3b82f6"
    
    # CALLS Setups Section (Priority 2)
    html += f'''
        <div class="glass-card">
            <div class="section-header" onclick="toggleCard(this)">
                <div class="section-title" style="color:{green};">
                    <span class="icon">▲</span>
                    CALLS SETUPS
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="card-content">
                {generate_setups_html(calls_setups + puts_setups, "CALLS", green, theme)}
            </div>
        </div>
'''
    
    # PUTS Setups Section (Priority 3)
    html += f'''
        <div class="glass-card">
            <div class="section-header" onclick="toggleCard(this)">
                <div class="section-title" style="color:{red};">
                    <span class="icon">▼</span>
                    PUTS SETUPS
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="card-content">
                {generate_setups_html(calls_setups + puts_setups, "PUTS", red, theme)}
            </div>
        </div>
'''
    
    # Prior Session Section (Priority 4)
    html += f'''
        <div class="glass-card">
            <div class="section-header" onclick="toggleCard(this)">
                <div class="section-title">
                    <span class="icon">📈</span>
                    PRIOR SESSION
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="card-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value text-green">{prior_session.get('high', 0):,.2f}</div>
                        <div class="stat-label">High</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value text-red">{prior_session.get('low', 0):,.2f}</div>
                        <div class="stat-label">Low</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{prior_session.get('close', 0):,.2f}</div>
                        <div class="stat-label">Close</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value text-blue">{prior_session.get('high', 0) - prior_session.get('low', 0):,.0f}</div>
                        <div class="stat-label">Range</div>
                    </div>
                </div>
            </div>
        </div>
'''
    
    # Cone Rails Section (Priority 6)
    html += f'''
        <div class="glass-card">
            <div class="section-header" onclick="toggleCard(this)">
                <div class="section-title">
                    <span class="icon">📐</span>
                    STRUCTURAL CONES @ 9:00 AM CT
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="card-content">
                <table>
                    <thead>
                        <tr>
                            <th>Pivot</th>
                            <th>Ascending Rail (PUTS)</th>
                            <th>Descending Rail (CALLS)</th>
                            <th>Width</th>
                            <th>Blocks</th>
                            <th>Tradeable</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    
    for cone in cones:
        tradeable_html = f'<span class="pill pill-green">YES</span>' if cone.is_tradeable else f'<span class="pill pill-red">NO</span>'
        width_class = "text-green" if cone.width >= 25 else "text-amber" if cone.width >= MIN_CONE_WIDTH else "text-red"
        
        html += f'''
                        <tr>
                            <td><strong>{cone.name}</strong></td>
                            <td class="mono text-red">{cone.ascending_rail:,.2f}</td>
                            <td class="mono text-green">{cone.descending_rail:,.2f}</td>
                            <td class="mono {width_class}">{cone.width:.0f} pts</td>
                            <td class="mono">{cone.blocks}</td>
                            <td>{tradeable_html}</td>
                        </tr>
'''
    
    html += '''
                    </tbody>
                </table>
            </div>
        </div>
'''
    
    # Open Interest Section (Priority 8)
    if oi_levels:
        html += f'''
        <div class="glass-card collapsed">
            <div class="section-header" onclick="toggleCard(this)">
                <div class="section-title">
                    <span class="icon">🎯</span>
                    OPEN INTEREST MAGNETS
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="card-content">
                <table>
                    <thead>
                        <tr>
                            <th>SPY Strike</th>
                            <th>SPX Equiv</th>
                            <th>Type</th>
                            <th>Open Interest</th>
                        </tr>
                    </thead>
                    <tbody>
'''
        for oi in oi_levels[:8]:
            type_color = green if oi['type'] == 'call' else red
            html += f'''
                        <tr>
                            <td class="mono">{oi['strike']}</td>
                            <td class="mono">{oi['spx_equiv']:,.0f}</td>
                            <td style="color:{type_color};">{oi['type'].upper()}</td>
                            <td class="mono">{oi['oi']:,}</td>
                        </tr>
'''
        html += '''
                    </tbody>
                </table>
            </div>
        </div>
'''
    
    # Historical Results Section
    if is_historical and historical_results:
        total_pnl = sum(r.pnl_dollars for r in historical_results)
        wins = len([r for r in historical_results if "WIN" in r.result])
        losses = len([r for r in historical_results if r.result == "LOSS"])
        
        html += f'''
        <div class="glass-card">
            <div class="section-header" onclick="toggleCard(this)">
                <div class="section-title">
                    <span class="icon">📊</span>
                    BACKTEST RESULTS
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="card-content">
                <div class="stats-grid" style="margin-bottom: 20px;">
                    <div class="stat-card">
                        <div class="stat-value {"text-green" if total_pnl >= 0 else "text-red"}">${total_pnl:,.0f}</div>
                        <div class="stat-label">Total P&L</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value text-green">{wins}</div>
                        <div class="stat-label">Wins</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value text-red">{losses}</div>
                        <div class="stat-label">Losses</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{wins/(wins+losses)*100:.0f}%</div>
                        <div class="stat-label">Win Rate</div>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Direction</th>
                            <th>Cone</th>
                            <th>Entry</th>
                            <th>Premium</th>
                            <th>Hit 50%?</th>
                            <th>Result</th>
                            <th>P&L</th>
                        </tr>
                    </thead>
                    <tbody>
'''
        for r in historical_results:
            result_class = "text-green" if "WIN" in r.result else "text-red" if r.result == "LOSS" else ""
            dir_color = green if r.direction == "CALLS" else red
            html += f'''
                        <tr>
                            <td style="color:{dir_color};">{r.direction}</td>
                            <td>{r.cone_name}</td>
                            <td class="mono">{r.entry_price:,.2f}</td>
                            <td class="mono">${r.entry_premium:.2f}</td>
                            <td>{"✅" if r.hit_50 else "❌"}</td>
                            <td class="{result_class}">{r.result}</td>
                            <td class="mono {result_class}">${r.pnl_dollars:,.0f}</td>
                        </tr>
'''
        html += '''
                    </tbody>
                </table>
            </div>
        </div>
'''
    
    # Footer and Scripts
    html += f'''
        <div class="footer">
            <p>SPX Prophet v6.0 Legendary Edition • Built for Professional 0DTE Trading</p>
            <p style="margin-top: 8px; opacity: 0.7;">Data provided by Polygon.io • Not financial advice</p>
        </div>
    </div>
    
    <script>
        function toggleCard(header) {{
            const card = header.closest('.glass-card');
            card.classList.toggle('collapsed');
        }}
        
        // Sound alert function
        function playAlert() {{
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdH2Onp2ZjHdwa290hZSdmJKEd3Fydn+LmJyYkIR4c3N2foiUm5mShXl0c3Z9h5KZl5GFenV0dnyGkJeWkIV6dnV2fIWPk5OPhHp2dnd8hI2Rj4uCend4eX2EjI+Ni4F6eHl6fYOLjYqJgHp5ent+g4qMiYiAe3p7fH+Dh4mHhYB7e3t8f4KGhoOBfXx8fX+BhIOBfn19fX5+gIGAfX5+fn5+fn+Af35+fn5+fn5+fn5+fn5+');
            audio.play().catch(e => console.log('Audio play prevented'));
        }}
        
        // Check for alerts every 30 seconds
        setInterval(() => {{
            // Alert logic would go here in production
        }}, 30000);
    </script>
</body>
</html>
'''
    
    return html

# =============================================================================
# STREAMLIT MAIN APPLICATION
# =============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet v6.0 Legendary",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    defaults = {
        'theme': 'light',
        'use_manual_vix': True,
        'vix_bottom': 0.0,
        'vix_top': 0.0,
        'vix_current': 0.0,
        'use_manual_pivots': False,
        'manual_high_price': 0.0,
        'manual_high_time': "10:30",
        'manual_low_price': 0.0,
        'manual_low_time': "14:00",
        'manual_close_price': 0.0,
        'secondary_highs': [],
        'secondary_lows': [],
        'is_historical': False,
        'historical_date': None,
        'last_refresh': None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ SPX Prophet v6.0")
        st.markdown("*Legendary Edition*")
        st.markdown("---")
        
        # Theme Toggle
        theme = st.radio("🎨 Theme", ["Light", "Dark"], horizontal=True,
                        index=0 if st.session_state.theme == "light" else 1)
        st.session_state.theme = theme.lower()
        
        st.markdown("---")
        
        # Mode Selection
        mode = st.radio("📊 Mode", ["Live Trading", "Historical Analysis"], 
                       index=1 if st.session_state.is_historical else 0)
        st.session_state.is_historical = (mode == "Historical Analysis")
        
        if st.session_state.is_historical:
            historical_date = st.date_input(
                "📅 Select Date",
                value=st.session_state.historical_date or (get_ct_now().date() - timedelta(days=1)),
                max_value=get_ct_now().date() - timedelta(days=1),
                min_value=get_ct_now().date() - timedelta(days=730)  # 2 years
            )
            st.session_state.historical_date = historical_date
        
        st.markdown("---")
        
        # VIX Zone Input (Always Manual per user request)
        st.markdown("### 📊 VIX Zone (5pm-3am)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input(
                "Zone Bottom", 
                value=st.session_state.vix_bottom,
                step=0.01, format="%.2f"
            )
        with col2:
            st.session_state.vix_top = st.number_input(
                "Zone Top",
                value=st.session_state.vix_top,
                step=0.01, format="%.2f"
            )
        
        st.session_state.vix_current = st.number_input(
            "Current VIX (8am reading)",
            value=st.session_state.vix_current,
            step=0.01, format="%.2f"
        )
        
        # Auto-fetch current VIX button
        if st.button("🔄 Fetch Current VIX"):
            vix = polygon_get_vix_price()
            if vix > 0:
                st.session_state.vix_current = vix
                st.success(f"VIX: {vix:.2f}")
            else:
                st.warning("Could not fetch VIX")
        
        st.markdown("---")
        
        # Pivot Input
        st.markdown("### 📍 Prior Day Pivots")
        
        use_manual = st.checkbox("Manual Pivot Override", value=st.session_state.use_manual_pivots)
        st.session_state.use_manual_pivots = use_manual
        
        if use_manual:
            st.markdown("**Primary HIGH** (highest wick)")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.session_state.manual_high_price = st.number_input(
                    "High Price", value=st.session_state.manual_high_price,
                    step=0.01, format="%.2f", key="high_p"
                )
            with col2:
                st.session_state.manual_high_time = st.text_input(
                    "Time (HH:MM)", value=st.session_state.manual_high_time, key="high_t"
                )
            
            st.markdown("**Primary LOW** (open of bullish candle after)")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.session_state.manual_low_price = st.number_input(
                    "Low Price", value=st.session_state.manual_low_price,
                    step=0.01, format="%.2f", key="low_p"
                )
            with col2:
                st.session_state.manual_low_time = st.text_input(
                    "Time (HH:MM)", value=st.session_state.manual_low_time, key="low_t"
                )
            
            st.session_state.manual_close_price = st.number_input(
                "Prior Close", value=st.session_state.manual_close_price,
                step=0.01, format="%.2f"
            )
            
            # Secondary pivots
            st.markdown("---")
            st.markdown("**Secondary Pivots** (up to 3 each)")
            
            num_sec_highs = st.number_input("# Secondary Highs", 0, 3, len(st.session_state.secondary_highs))
            num_sec_lows = st.number_input("# Secondary Lows", 0, 3, len(st.session_state.secondary_lows))
            
            # Adjust lists
            while len(st.session_state.secondary_highs) < num_sec_highs:
                st.session_state.secondary_highs.append((0.0, "11:00"))
            st.session_state.secondary_highs = st.session_state.secondary_highs[:num_sec_highs]
            
            while len(st.session_state.secondary_lows) < num_sec_lows:
                st.session_state.secondary_lows.append((0.0, "13:00"))
            st.session_state.secondary_lows = st.session_state.secondary_lows[:num_sec_lows]
            
            for i in range(num_sec_highs):
                st.markdown(f"*High {i+2}*")
                col1, col2 = st.columns([2, 1])
                with col1:
                    price = st.number_input(f"Price##sh{i}", value=st.session_state.secondary_highs[i][0], step=0.01, format="%.2f")
                with col2:
                    time_str = st.text_input(f"Time##sht{i}", value=st.session_state.secondary_highs[i][1])
                st.session_state.secondary_highs[i] = (price, time_str)
            
            for i in range(num_sec_lows):
                st.markdown(f"*Low {i+2}*")
                col1, col2 = st.columns([2, 1])
                with col1:
                    price = st.number_input(f"Price##sl{i}", value=st.session_state.secondary_lows[i][0], step=0.01, format="%.2f")
                with col2:
                    time_str = st.text_input(f"Time##slt{i}", value=st.session_state.secondary_lows[i][1])
                st.session_state.secondary_lows[i] = (price, time_str)
        
        st.markdown("---")
        
        # Refresh Button
        if st.button("🔄 Refresh Data", use_container_width=True, type="primary"):
            st.session_state.last_refresh = get_ct_now()
            st.cache_data.clear()
            st.rerun()
        
        if st.session_state.last_refresh:
            st.caption(f"Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S CT')}")
    
    # ==========================================================================
    # MAIN PROCESSING
    # ==========================================================================
    
    now = get_ct_now()
    is_historical = st.session_state.is_historical
    
    # Determine dates
    if is_historical:
        trading_date = st.session_state.historical_date
        pivot_date = get_prior_trading_day(trading_date)
        expiry = trading_date
    else:
        trading_date = get_next_trading_day()
        pivot_date = get_prior_trading_day(trading_date)
        expiry = trading_date
    
    # Get market data
    market_data = MarketData()
    
    if not is_historical:
        market_data.spx_price = polygon_get_spx_price()
        market_data.spy_price = polygon_get_spy_price()
        market_data.vix_price = polygon_get_vix_price() if st.session_state.vix_current == 0 else st.session_state.vix_current
        market_data.timestamp = now
        market_data.is_market_open = (RTH_OPEN <= now.time() <= MARKET_CLOSE and trading_date == now.date())
    else:
        # Fetch historical data
        bars = polygon_get_historical_bars("I:SPX", trading_date, trading_date, "day", 1)
        if bars:
            market_data.spx_price = bars[-1].get("c", 0)
    
    # VIX Zone Analysis
    vix_zone = analyze_vix_zone(
        st.session_state.vix_bottom,
        st.session_state.vix_top,
        st.session_state.vix_current if st.session_state.vix_current > 0 else market_data.vix_price
    )
    
    # Get prior session data
    prior_bars = polygon_get_historical_bars("I:SPX", pivot_date, pivot_date, "day", 1)
    prior_session = {}
    if prior_bars:
        prior_session = {
            "high": prior_bars[0].get("h", 0),
            "low": prior_bars[0].get("l", 0),
            "close": prior_bars[0].get("c", 0),
            "open": prior_bars[0].get("o", 0)
        }
    
    # Build Pivots
    if st.session_state.use_manual_pivots and st.session_state.manual_high_price > 0:
        pivots = create_manual_pivots(
            high_price=st.session_state.manual_high_price,
            high_time=st.session_state.manual_high_time,
            low_price=st.session_state.manual_low_price,
            low_time=st.session_state.manual_low_time,
            close_price=st.session_state.manual_close_price,
            pivot_date=pivot_date,
            secondary_highs=st.session_state.secondary_highs,
            secondary_lows=st.session_state.secondary_lows
        )
    else:
        # Auto-detect pivots
        bars_30m = polygon_get_historical_bars("I:SPX", pivot_date, pivot_date, "minute", 30)
        if bars_30m:
            pivots = detect_pivots_from_candles(bars_30m, pivot_date)
        else:
            # Fallback to basic pivots from prior session
            pivots = [
                Pivot(name="Prior High", price=prior_session.get("high", 0), 
                      time=CT_TZ.localize(datetime.combine(pivot_date, time(10, 30))),
                      pivot_type="HIGH", candle_high=prior_session.get("high", 0)),
                Pivot(name="Prior Low", price=prior_session.get("low", 0),
                      time=CT_TZ.localize(datetime.combine(pivot_date, time(14, 0))),
                      pivot_type="LOW", candle_open=prior_session.get("low", 0)),
                Pivot(name="Prior Close", price=prior_session.get("close", 0),
                      time=CT_TZ.localize(datetime.combine(pivot_date, time(16, 0))),
                      pivot_type="CLOSE")
            ]
    
    # Build Cones at 9:00 AM CT
    eval_time = CT_TZ.localize(datetime.combine(trading_date, time(9, 0)))
    cones = build_cones(pivots, eval_time)
    
    # Current price for setup generation
    current_price = market_data.spx_price if market_data.spx_price > 0 else prior_session.get("close", 0)
    
    # Check if after cutoff
    is_after_cutoff = now.time() > CUTOFF_TIME if not is_historical else False
    
    # Generate Setups
    setups = generate_setups(cones, current_price, vix_zone.bias, expiry, is_after_cutoff)
    calls_setups = [s for s in setups if s.direction == "CALLS"]
    puts_setups = [s for s in setups if s.direction == "PUTS"]
    
    # Get Open Interest Levels
    spy_price = market_data.spy_price if market_data.spy_price > 0 else current_price / 10
    oi_levels = get_open_interest_levels(expiry, spy_price) if not is_historical else []
    
    # Check Alerts
    alerts = check_alerts(setups, vix_zone, now.time()) if not is_historical else []
    
    # Historical Results
    historical_results = None
    if is_historical:
        historical_results = backtest_day(trading_date, pivots, vix_zone)
    
    # Generate and Display Dashboard
    dashboard_html = generate_full_dashboard_html(
        market_data=market_data,
        vix_zone=vix_zone,
        cones=cones,
        calls_setups=calls_setups,
        puts_setups=puts_setups,
        prior_session=prior_session,
        oi_levels=oi_levels,
        alerts=alerts,
        is_historical=is_historical,
        historical_date=st.session_state.historical_date if is_historical else None,
        historical_results=historical_results,
        theme=st.session_state.theme
    )
    
    # Render HTML
    components.html(dashboard_html, height=2500, scrolling=True)
    
    # Auto-refresh every 5 minutes (live mode only)
    if not is_historical:
        st.markdown(
            """
            <script>
                setTimeout(function() {
                    window.parent.document.querySelector('button[kind="primary"]').click();
                }, 300000);
            </script>
            """,
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()
