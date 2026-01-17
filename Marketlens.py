# ═══════════════════════════════════════════════════════════════════════════════════════
#
#   ███████╗██████╗ ██╗  ██╗    ██████╗ ██████╗  ██████╗ ██████╗ ██╗  ██╗███████╗████████╗
#   ██╔════╝██╔══██╗╚██╗██╔╝    ██╔══██╗██╔══██╗██╔═══██╗██╔══██╗██║  ██║██╔════╝╚══██╔══╝
#   ███████╗██████╔╝ ╚███╔╝     ██████╔╝██████╔╝██║   ██║██████╔╝███████║█████╗     ██║   
#   ╚════██║██╔═══╝  ██╔██╗     ██╔═══╝ ██╔══██╗██║   ██║██╔═══╝ ██╔══██║██╔══╝     ██║   
#   ███████║██║     ██╔╝ ██╗    ██║     ██║  ██║╚██████╔╝██║     ██║  ██║███████╗   ██║   
#   ╚══════╝╚═╝     ╚═╝  ╚═╝    ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚══════╝   ╚═╝   
#
#   VERSION 6.0 - UNIFIED INSTITUTIONAL TRADING SYSTEM
#   ─────────────────────────────────────────────────────────────────────────────────────
#   • ES-Native Architecture with Auto SPX Offset Calibration
#   • Sydney/Tokyo Channel Selection Algorithm  
#   • 8:30 AM Candle Validation Framework
#   • Cone Rail Target System with Priority Ranking
#   • Multi-Signal Flow Bias Detection
#   • Black-Scholes Option Price Projections
#   • Institutional-Grade UI/UX
#
#   Created by David for 0DTE SPX Options Trading
#   ─────────────────────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import pytz
import json
import os
import math
import time as time_module
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass

# ═══════════════════════════════════════════════════════════════════════════════════════
# ENUMS - Trading State Machine
# ═══════════════════════════════════════════════════════════════════════════════════════

class Channel(Enum):
    """Daily channel selection based on Sydney vs Tokyo session behavior"""
    RISING = "RISING"       # Tokyo High > Sydney High → Use Ceiling Rising + Floor Rising
    FALLING = "FALLING"     # Tokyo Low < Sydney Low → Use Ceiling Falling + Floor Falling
    UNDETERMINED = "UNDETERMINED"

class PreOpenPosition(Enum):
    """Where is price relative to the active channel before 8:30 AM"""
    ABOVE = "ABOVE_CHANNEL"   # Broken above ceiling by 6+ pts OR 30min close above
    BELOW = "BELOW_CHANNEL"   # Broken below floor by 6+ pts OR 30min close below
    INSIDE = "INSIDE_CHANNEL" # Price contained within channel edges

class SetupStatus(Enum):
    """8:30 AM candle validation status"""
    AWAITING_830 = "AWAITING_830"     # Waiting for candle to complete
    VALID = "VALID"                   # Setup confirmed - ready for entry
    INVALIDATED = "INVALIDATED"       # Setup failed - alternate plan activated
    TREND_DAY = "TREND_DAY"           # Candle touched edge, closed inside - trade the range

class TradingPhase(Enum):
    """Current phase in the trading day lifecycle"""
    PRE_MARKET = "PRE_MARKET"         # Before 8:30 AM CT - Planning phase
    VALIDATING = "VALIDATING_830"     # 8:30-9:00 AM CT - Watching candle
    ENTRY_WINDOW = "ENTRY_WINDOW"     # 9:00-9:10 AM CT - Primary entry time
    SECONDARY_ENTRY = "SECONDARY"     # 9:10-9:30 AM CT - Secondary entry (inside channel breaks)
    IN_TRADE = "IN_TRADE"             # Active position
    MARKET_CLOSED = "MARKET_CLOSED"   # After 3:00 PM CT

class Direction(Enum):
    """Trade direction"""
    CALLS = "CALLS"
    PUTS = "PUTS"
    NEUTRAL = "NEUTRAL"

# ═══════════════════════════════════════════════════════════════════════════════════════
# DATA CLASSES - Structured Data Containers
# ═══════════════════════════════════════════════════════════════════════════════════════

@dataclass
class SessionLevels:
    """High/Low levels for a trading session"""
    high: Optional[float] = None
    low: Optional[float] = None
    high_time: Optional[datetime] = None
    low_time: Optional[datetime] = None

@dataclass
class ChannelEdge:
    """A single channel boundary line"""
    name: str
    level: float
    anchor: float
    blocks: int
    expansion: float
    entry_type: Direction

@dataclass
class ConeRail:
    """A cone projection line from prior day"""
    name: str
    anchor: float
    ascending: float
    descending: float
    blocks: int
    expansion: float

@dataclass
class TradeSetup:
    """Complete trade setup with all parameters"""
    direction: Direction
    entry_level: float
    entry_edge: str
    strike: int
    targets: List[Dict]
    invalidation_level: float
    entry_window: str
    confidence: int

# ═══════════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="SPX Prophet V6.0",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Timezone
CT = pytz.timezone("America/Chicago")

# Structure Parameters
SLOPE = 0.48                    # Expansion per 30-min block
CHANNEL_BREAK_THRESHOLD = 6.0   # Points outside channel = broken
CONFLUENCE_THRESHOLD = 5.0      # Points for confluence detection

# Session Times (CT) - For auto-detection
SESSIONS = {
    "SYDNEY": {"start": time(17, 0), "end": time(20, 30), "day_offset": -1},  # Previous day
    "TOKYO": {"start": time(21, 0), "end": time(1, 30), "spans_midnight": True},
    "OVERNIGHT": {"start": time(17, 0), "end": time(8, 30), "spans_midnight": True},
}

# Key Times (CT)
MARKET_OPEN = time(8, 30)
VALIDATION_END = time(9, 0)
ENTRY_WINDOW_END = time(9, 10)
SECONDARY_ENTRY_END = time(9, 30)
MARKET_CLOSE = time(15, 0)

# API Configuration
POLYGON_KEY = "DCWuTS1R_fukpfjgf7QnXrLTEOS_giq6"
POLYGON_BASE = "https://api.polygon.io"

# Persistence
SAVE_FILE = "spx_prophet_v6_inputs.json"

# VIX Regime Classification
VIX_ZONES = {
    "EXTREME_LOW": {"range": (0, 12), "desc": "Complacency → Reversals likely", "color": "#22d3ee", "bias": "CAUTIOUS"},
    "LOW": {"range": (12, 16), "desc": "Calm → Good for directional", "color": "#10b981", "bias": "BULLISH"},
    "NORMAL": {"range": (16, 20), "desc": "Standard conditions", "color": "#8b5cf6", "bias": "NEUTRAL"},
    "ELEVATED": {"range": (20, 25), "desc": "Caution → Wider stops needed", "color": "#f59e0b", "bias": "CAUTIOUS"},
    "HIGH": {"range": (25, 35), "desc": "Fear → Premium expensive", "color": "#ff6b35", "bias": "BEARISH"},
    "EXTREME": {"range": (35, 100), "desc": "Panic → Mean reversion plays", "color": "#ef4444", "bias": "REVERSAL"}
}

# ═══════════════════════════════════════════════════════════════════════════════════════
# MATHEMATICAL FUNCTIONS (Black-Scholes without scipy dependency)
# ═══════════════════════════════════════════════════════════════════════════════════════

def norm_cdf(x: float) -> float:
    """
    Cumulative distribution function for standard normal distribution.
    Uses Abramowitz & Stegun approximation (error < 1.5e-7)
    """
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution"""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

def black_scholes(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """
    Black-Scholes option pricing model.
    
    Args:
        S: Current underlying price (SPX)
        K: Strike price
        T: Time to expiration in years
        r: Risk-free rate (default 5%)
        sigma: Implied volatility (decimal, e.g., 0.18 for 18%)
        option_type: "CALL" or "PUT"
    
    Returns:
        Theoretical option price
    """
    if T <= 0:
        # At expiration - return intrinsic value
        if option_type == "CALL":
            return max(0, S - K)
        else:
            return max(0, K - S)
    
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        if option_type == "CALL":
            price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        else:
            price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
        
        return max(0, price)
    except:
        return 0.0

def calculate_delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Calculate option delta"""
    if T <= 0:
        return 1.0 if option_type == "CALL" and S > K else -1.0 if option_type == "PUT" and S < K else 0.0
    
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        if option_type == "CALL":
            return norm_cdf(d1)
        else:
            return norm_cdf(d1) - 1
    except:
        return 0.0



# ═══════════════════════════════════════════════════════════════════════════════════════
# CSS STYLES - Premium Institutional Dark Theme (COMPLETE)
# ═══════════════════════════════════════════════════════════════════════════════════════

STYLES = """
<style>
/* ═══════════════════════════════════════════════════════════════════════════════════
   FONT IMPORTS - Premium Typography Stack
   ═══════════════════════════════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

/* ═══════════════════════════════════════════════════════════════════════════════════
   CSS VARIABLES - Design System Tokens
   ═══════════════════════════════════════════════════════════════════════════════════ */
:root {
    --bg-primary: #06060a;
    --bg-secondary: #0a0a10;
    --bg-tertiary: #0f0f16;
    --bg-card: rgba(255,255,255,0.015);
    --bg-card-hover: rgba(255,255,255,0.03);
    --bg-elevated: rgba(255,255,255,0.04);
    --border-subtle: rgba(255,255,255,0.04);
    --border-default: rgba(255,255,255,0.08);
    --border-bright: rgba(255,255,255,0.15);
    --text-primary: #ffffff;
    --text-secondary: rgba(255,255,255,0.65);
    --text-muted: rgba(255,255,255,0.4);
    --text-disabled: rgba(255,255,255,0.25);
    --green-400: #4ade80;
    --green-500: #22c55e;
    --green-600: #16a34a;
    --red-400: #f87171;
    --red-500: #ef4444;
    --red-600: #dc2626;
    --amber-400: #fbbf24;
    --amber-500: #f59e0b;
    --purple-400: #a78bfa;
    --purple-500: #8b5cf6;
    --purple-600: #7c3aed;
    --cyan-400: #22d3ee;
    --cyan-500: #06b6d4;
    --blue-500: #3b82f6;
    --color-bullish: var(--green-500);
    --color-bearish: var(--red-500);
    --color-neutral: var(--amber-500);
    --color-info: var(--cyan-500);
    --color-accent: var(--purple-500);
    --glow-green: 0 0 40px rgba(34, 197, 94, 0.3);
    --glow-red: 0 0 40px rgba(239, 68, 68, 0.3);
    --glow-purple: 0 0 40px rgba(139, 92, 246, 0.25);
    --glow-cyan: 0 0 40px rgba(6, 182, 212, 0.25);
    --glow-amber: 0 0 40px rgba(245, 158, 11, 0.25);
    --font-display: 'Outfit', sans-serif;
    --font-body: 'Inter', sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 16px;
    --radius-xl: 24px;
    --transition-fast: 0.15s ease;
    --transition-normal: 0.25s ease;
}

*, *::before, *::after { box-sizing: border-box; }

.stApp {
    background: var(--bg-primary);
    background-image: 
        radial-gradient(ellipse 100% 80% at 50% -40%, rgba(139, 92, 246, 0.12), transparent 70%),
        radial-gradient(ellipse 80% 60% at 100% -20%, rgba(6, 182, 212, 0.08), transparent 60%),
        radial-gradient(ellipse 60% 40% at 0% 100%, rgba(139, 92, 246, 0.05), transparent 50%);
    font-family: var(--font-body);
    color: var(--text-primary);
}

.stApp > header { background: transparent !important; }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: var(--border-bright); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%) !important;
    border-right: 1px solid var(--border-subtle) !important;
}
[data-testid="stSidebar"]::before {
    content: '';
    position: absolute;
    top: 0; right: 0;
    width: 1px; height: 100%;
    background: linear-gradient(180deg, rgba(139,92,246,0.3) 0%, transparent 50%, rgba(6,182,212,0.3) 100%);
}
[data-testid="stSidebar"] * { color: var(--text-primary) !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stNumberInput label,
[data-testid="stSidebar"] .stTextInput label {
    font-size: 11px !important;
    color: var(--text-muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.hero-container {
    background: linear-gradient(135deg, rgba(139,92,246,0.06) 0%, rgba(6,182,212,0.06) 100%);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-xl);
    padding: 28px 36px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.hero-container::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, var(--purple-500) 30%, var(--cyan-500) 70%, transparent 100%);
    opacity: 0.6;
}
.hero-container::after {
    content: '';
    position: absolute;
    bottom: 0; left: 10%; right: 10%;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
}

.hero-grid {
    display: grid;
    grid-template-columns: 280px 1fr 280px;
    gap: 32px;
    align-items: center;
}

.hero-left { text-align: left; }
.hero-brand {
    font-family: var(--font-display);
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.5px;
    background: linear-gradient(135deg, var(--purple-400) 0%, var(--cyan-400) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 0 0 60px rgba(139, 92, 246, 0.5);
}
.hero-version {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 500;
    color: var(--text-muted);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 4px;
}
.hero-offset-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background: rgba(139,92,246,0.1);
    border: 1px solid rgba(139,92,246,0.25);
    border-radius: var(--radius-md);
    padding: 10px 16px;
    margin-top: 16px;
}
.hero-offset-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--purple-400);
    text-transform: uppercase;
    letter-spacing: 1px;
}
.hero-offset-value {
    font-family: var(--font-mono);
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
}

.hero-center { text-align: center; }
.hero-price-container { position: relative; display: inline-block; }
.hero-price {
    font-family: var(--font-mono);
    font-size: 64px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1;
    letter-spacing: -3px;
    text-shadow: 0 0 80px rgba(255,255,255,0.1);
}
.hero-price-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 3px;
    margin-top: 8px;
}
.hero-es-price {
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--text-secondary);
    margin-top: 12px;
}
.hero-es-price span {
    color: var(--cyan-400);
    font-weight: 600;
}

.hero-right { text-align: right; }
.hero-time {
    font-family: var(--font-mono);
    font-size: 28px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -1px;
}
.hero-timezone {
    font-size: 12px;
    color: var(--text-muted);
    margin-left: 4px;
}
.hero-date {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
}

.phase-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    border-radius: 50px;
    font-family: var(--font-display);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-top: 16px;
    transition: var(--transition-normal);
}
.phase-pre-market {
    background: rgba(139,92,246,0.15);
    border: 1px solid rgba(139,92,246,0.4);
    color: var(--purple-400);
}
.phase-validating {
    background: rgba(245,158,11,0.15);
    border: 1px solid rgba(245,158,11,0.4);
    color: var(--amber-400);
    animation: pulse-glow-amber 2s ease-in-out infinite;
}
.phase-entry-window {
    background: rgba(34,197,94,0.15);
    border: 1px solid rgba(34,197,94,0.5);
    color: var(--green-400);
    animation: pulse-glow-green 1.5s ease-in-out infinite;
    box-shadow: var(--glow-green);
}
.phase-in-trade {
    background: rgba(6,182,212,0.15);
    border: 1px solid rgba(6,182,212,0.4);
    color: var(--cyan-400);
}
.phase-closed {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border-default);
    color: var(--text-muted);
}

@keyframes pulse-glow-amber {
    0%, 100% { box-shadow: 0 0 20px rgba(245,158,11,0.2); }
    50% { box-shadow: 0 0 35px rgba(245,158,11,0.4); }
}
@keyframes pulse-glow-green {
    0%, 100% { box-shadow: 0 0 20px rgba(34,197,94,0.3); }
    50% { box-shadow: 0 0 40px rgba(34,197,94,0.5); }
}

.command-center {
    background: linear-gradient(180deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0.01) 100%);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-xl);
    padding: 0;
    margin-bottom: 24px;
    overflow: hidden;
    position: relative;
}
.command-center::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--purple-500), var(--cyan-500));
}

.command-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 28px;
    background: rgba(0,0,0,0.2);
    border-bottom: 1px solid var(--border-subtle);
}
.command-header-left {
    display: flex;
    align-items: center;
    gap: 16px;
}
.command-icon {
    width: 52px;
    height: 52px;
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, var(--purple-500) 0%, var(--cyan-500) 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    box-shadow: 0 8px 32px rgba(139,92,246,0.3);
}
.command-title {
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
}
.command-subtitle {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
}

.confidence-display { text-align: right; }
.confidence-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
}
.confidence-value {
    font-family: var(--font-mono);
    font-size: 36px;
    font-weight: 700;
    line-height: 1;
}
.confidence-high { color: var(--green-400); }
.confidence-medium { color: var(--amber-400); }
.confidence-low { color: var(--red-400); }

.command-body { padding: 24px 28px; }

.channel-container {
    background: rgba(0,0,0,0.3);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 24px;
    margin-bottom: 20px;
}

.channel-visual {
    display: grid;
    grid-template-columns: 1fr 120px 1fr;
    gap: 24px;
    align-items: center;
}

.channel-edge {
    background: rgba(255,255,255,0.02);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: 20px;
    text-align: center;
    transition: var(--transition-normal);
}
.channel-edge:hover {
    background: rgba(255,255,255,0.04);
    border-color: var(--border-bright);
}
.channel-edge.ceiling { border-top: 3px solid var(--green-500); }
.channel-edge.floor { border-bottom: 3px solid var(--red-500); }
.channel-edge-name {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 12px;
}
.channel-edge-price {
    font-family: var(--font-mono);
    font-size: 28px;
    font-weight: 700;
}
.channel-edge-price.bullish { color: var(--green-400); }
.channel-edge-price.bearish { color: var(--red-400); }
.channel-edge-es {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 8px;
}

.channel-middle { text-align: center; }
.channel-type-badge {
    display: inline-block;
    padding: 8px 16px;
    border-radius: var(--radius-sm);
    font-family: var(--font-display);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
}
.channel-type-badge.rising {
    background: rgba(34,197,94,0.15);
    border: 1px solid rgba(34,197,94,0.3);
    color: var(--green-400);
}
.channel-type-badge.falling {
    background: rgba(239,68,68,0.15);
    border: 1px solid rgba(239,68,68,0.3);
    color: var(--red-400);
}
.channel-type-badge.undetermined {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border-default);
    color: var(--text-muted);
}
.channel-arrow {
    font-size: 48px;
    line-height: 1;
    margin: 8px 0;
}
.channel-arrow.rising { color: var(--green-400); }
.channel-arrow.falling { color: var(--red-400); }
.channel-width {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
}

.position-indicator {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-radius: var(--radius-md);
    margin-bottom: 20px;
}
.position-indicator.above {
    background: linear-gradient(90deg, rgba(34,197,94,0.1) 0%, rgba(34,197,94,0.02) 100%);
    border: 1px solid rgba(34,197,94,0.25);
    border-left: 4px solid var(--green-500);
}
.position-indicator.below {
    background: linear-gradient(90deg, rgba(239,68,68,0.1) 0%, rgba(239,68,68,0.02) 100%);
    border: 1px solid rgba(239,68,68,0.25);
    border-left: 4px solid var(--red-500);
}
.position-indicator.inside {
    background: linear-gradient(90deg, rgba(245,158,11,0.1) 0%, rgba(245,158,11,0.02) 100%);
    border: 1px solid rgba(245,158,11,0.25);
    border-left: 4px solid var(--amber-500);
}
.position-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.position-value {
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 600;
}
.position-value.above { color: var(--green-400); }
.position-value.below { color: var(--red-400); }
.position-value.inside { color: var(--amber-400); }

.candle-830-container {
    background: rgba(0,0,0,0.25);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 20px;
    margin-bottom: 20px;
}
.candle-830-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}
.candle-830-title {
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}
.candle-830-status {
    font-size: 10px;
    font-weight: 600;
    padding: 5px 12px;
    border-radius: 50px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.candle-830-status.awaiting {
    background: rgba(139,92,246,0.15);
    color: var(--purple-400);
}
.candle-830-status.forming {
    background: rgba(245,158,11,0.15);
    color: var(--amber-400);
    animation: pulse-glow-amber 2s infinite;
}
.candle-830-status.complete {
    background: rgba(34,197,94,0.15);
    color: var(--green-400);
}

.candle-830-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}
.candle-830-item {
    background: rgba(255,255,255,0.02);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px;
    text-align: center;
}
.candle-830-item-label {
    font-size: 9px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}
.candle-830-item-value {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
}
.candle-830-item-value.high { color: var(--green-400); }
.candle-830-item-value.low { color: var(--red-400); }

.trade-setup-card {
    border-radius: var(--radius-lg);
    padding: 24px;
    margin-top: 20px;
    position: relative;
    overflow: hidden;
}
.trade-setup-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
}
.trade-setup-card.calls {
    background: linear-gradient(135deg, rgba(34,197,94,0.08) 0%, rgba(6,182,212,0.05) 100%);
    border: 1px solid rgba(34,197,94,0.3);
}
.trade-setup-card.calls::before {
    background: linear-gradient(90deg, var(--green-500), var(--cyan-500));
}
.trade-setup-card.puts {
    background: linear-gradient(135deg, rgba(239,68,68,0.08) 0%, rgba(245,158,11,0.05) 100%);
    border: 1px solid rgba(239,68,68,0.3);
}
.trade-setup-card.puts::before {
    background: linear-gradient(90deg, var(--red-500), var(--amber-500));
}

.trade-setup-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
}
.trade-direction-container {
    display: flex;
    align-items: center;
    gap: 16px;
}
.trade-direction-badge {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 800;
    padding: 12px 28px;
    border-radius: var(--radius-md);
    text-transform: uppercase;
    letter-spacing: 2px;
}
.trade-direction-badge.calls {
    background: linear-gradient(135deg, var(--green-500) 0%, var(--green-600) 100%);
    color: #000;
    box-shadow: 0 4px 20px rgba(34,197,94,0.4);
}
.trade-direction-badge.puts {
    background: linear-gradient(135deg, var(--red-500) 0%, var(--red-600) 100%);
    color: #fff;
    box-shadow: 0 4px 20px rgba(239,68,68,0.4);
}
.trade-setup-reason {
    font-size: 13px;
    color: var(--text-secondary);
    max-width: 300px;
}
.trade-entry-window { text-align: right; }
.trade-entry-window-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.trade-entry-window-value {
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 600;
    color: var(--cyan-400);
    margin-top: 4px;
}

.trade-metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;
}
.trade-metric {
    background: rgba(0,0,0,0.3);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 16px;
    text-align: center;
    transition: var(--transition-fast);
}
.trade-metric:hover {
    background: rgba(0,0,0,0.4);
    border-color: var(--border-default);
}
.trade-metric-label {
    font-size: 9px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}
.trade-metric-value {
    font-family: var(--font-mono);
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
}
.trade-metric-value.highlight { color: var(--cyan-400); }
.trade-metric-value.bullish { color: var(--green-400); }
.trade-metric-value.bearish { color: var(--red-400); }
.trade-metric-subtitle {
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 4px;
}

.targets-section {
    background: rgba(0,0,0,0.25);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 20px;
}
.targets-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}
.targets-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1px;
}
.targets-subtitle {
    font-size: 10px;
    color: var(--text-muted);
}

.target-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    background: rgba(255,255,255,0.02);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    margin-bottom: 10px;
    transition: var(--transition-fast);
}
.target-row:hover { background: rgba(255,255,255,0.04); }
.target-row.primary {
    background: rgba(6,182,212,0.1);
    border-color: rgba(6,182,212,0.3);
    border-left: 4px solid var(--cyan-500);
}
.target-row.primary:hover { background: rgba(6,182,212,0.15); }

.target-info {
    display: flex;
    align-items: center;
    gap: 12px;
}
.target-rank {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: rgba(255,255,255,0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 700;
    color: var(--text-secondary);
}
.target-row.primary .target-rank {
    background: var(--cyan-500);
    color: #000;
}
.target-name {
    font-size: 13px;
    color: var(--text-secondary);
}
.target-row.primary .target-name {
    color: var(--text-primary);
    font-weight: 500;
}

.target-data {
    display: flex;
    align-items: center;
    gap: 24px;
}
.target-price {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
}
.target-distance {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
    min-width: 70px;
    text-align: right;
}
.target-profit {
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 700;
    color: var(--green-400);
    min-width: 60px;
    text-align: right;
}

.scenarios-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 20px;
}

.scenario-card {
    background: rgba(0,0,0,0.2);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: 20px;
    position: relative;
    transition: var(--transition-normal);
}
.scenario-card:hover { background: rgba(0,0,0,0.3); }
.scenario-card.valid { border-left: 4px solid var(--green-500); }
.scenario-card.invalid { border-left: 4px solid var(--red-500); }
.scenario-card.trend { border-left: 4px solid var(--amber-500); }

.scenario-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 16px;
}
.scenario-icon {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
}
.scenario-card.valid .scenario-icon { background: rgba(34,197,94,0.15); }
.scenario-card.invalid .scenario-icon { background: rgba(239,68,68,0.15); }
.scenario-card.trend .scenario-icon { background: rgba(245,158,11,0.15); }
.scenario-title {
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}
.scenario-condition {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
}

.scenario-details {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}
.scenario-detail-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-subtle);
}
.scenario-detail-label {
    font-size: 11px;
    color: var(--text-muted);
}
.scenario-detail-value {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
}
.scenario-detail-value.calls { color: var(--green-400); }
.scenario-detail-value.puts { color: var(--red-400); }

.trend-day-banner {
    background: linear-gradient(135deg, rgba(245,158,11,0.12) 0%, rgba(139,92,246,0.08) 100%);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    margin-bottom: 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.trend-day-banner::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--amber-500), var(--purple-500));
}
.trend-day-icon {
    font-size: 32px;
    margin-bottom: 8px;
}
.trend-day-title {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 700;
    color: var(--amber-400);
    margin-bottom: 4px;
}
.trend-day-description {
    font-size: 13px;
    color: var(--text-secondary);
}

.trend-trades-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-top: 20px;
}
.trend-trade-card {
    border-radius: var(--radius-md);
    padding: 20px;
    text-align: center;
    transition: var(--transition-normal);
}
.trend-trade-card:hover { transform: translateY(-2px); }
.trend-trade-card.buy {
    background: linear-gradient(135deg, rgba(34,197,94,0.1) 0%, rgba(34,197,94,0.02) 100%);
    border: 1px solid rgba(34,197,94,0.3);
}
.trend-trade-card.buy:hover { box-shadow: var(--glow-green); }
.trend-trade-card.sell {
    background: linear-gradient(135deg, rgba(239,68,68,0.1) 0%, rgba(239,68,68,0.02) 100%);
    border: 1px solid rgba(239,68,68,0.3);
}
.trend-trade-card.sell:hover { box-shadow: var(--glow-red); }

.trend-trade-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
}
.trend-trade-level {
    font-family: var(--font-mono);
    font-size: 26px;
    font-weight: 700;
    margin-bottom: 8px;
}
.trend-trade-card.buy .trend-trade-level { color: var(--green-400); }
.trend-trade-card.sell .trend-trade-level { color: var(--red-400); }
.trend-trade-target {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 12px;
}
.trend-trade-strike {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    display: inline-block;
}
.trend-trade-card.buy .trend-trade-strike {
    background: rgba(34,197,94,0.15);
    color: var(--green-400);
}
.trend-trade-card.sell .trend-trade-strike {
    background: rgba(239,68,68,0.15);
    color: var(--red-400);
}

.confidence-section {
    background: rgba(0,0,0,0.2);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 20px;
    margin-top: 20px;
}
.confidence-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}
.confidence-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1px;
}
.confidence-score-large {
    font-family: var(--font-mono);
    font-size: 28px;
    font-weight: 700;
}

.confidence-bar-container { margin-bottom: 20px; }
.confidence-bar {
    height: 10px;
    background: rgba(255,255,255,0.1);
    border-radius: 5px;
    overflow: hidden;
    position: relative;
}
.confidence-bar-fill {
    height: 100%;
    border-radius: 5px;
    transition: width 0.5s ease;
    position: relative;
}
.confidence-bar-fill.high {
    background: linear-gradient(90deg, var(--green-500), var(--cyan-500));
    box-shadow: 0 0 20px rgba(34,197,94,0.4);
}
.confidence-bar-fill.medium {
    background: linear-gradient(90deg, var(--amber-500), var(--green-500));
    box-shadow: 0 0 20px rgba(245,158,11,0.4);
}
.confidence-bar-fill.low {
    background: linear-gradient(90deg, var(--red-500), var(--amber-500));
    box-shadow: 0 0 20px rgba(239,68,68,0.4);
}
.confidence-bar-markers {
    display: flex;
    justify-content: space-between;
    margin-top: 6px;
    font-size: 9px;
    color: var(--text-muted);
}

.confidence-factors-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
}
.confidence-factor {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: rgba(255,255,255,0.02);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    transition: var(--transition-fast);
}
.confidence-factor:hover { background: rgba(255,255,255,0.04); }
.confidence-factor-name {
    font-size: 11px;
    color: var(--text-muted);
}
.confidence-factor-value {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
}
.confidence-factor-value.positive { color: var(--green-400); }
.confidence-factor-value.negative { color: var(--red-400); }
.confidence-factor-value.neutral { color: var(--text-secondary); }

.analysis-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-top: 24px;
}

.analysis-card {
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: 20px;
    transition: var(--transition-normal);
    position: relative;
    overflow: hidden;
}
.analysis-card:hover {
    background: var(--bg-card-hover);
    border-color: var(--border-bright);
    transform: translateY(-2px);
}
.analysis-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    opacity: 0;
    transition: var(--transition-normal);
}
.analysis-card:hover::before { opacity: 1; }
.analysis-card.flow::before { background: var(--purple-500); }
.analysis-card.vix::before { background: var(--red-500); }
.analysis-card.momentum::before { background: var(--cyan-500); }

.analysis-card-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}
.analysis-card-icon {
    width: 42px;
    height: 42px;
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
}
.analysis-card.flow .analysis-card-icon { background: rgba(139,92,246,0.15); }
.analysis-card.vix .analysis-card-icon { background: rgba(239,68,68,0.15); }
.analysis-card.momentum .analysis-card-icon { background: rgba(6,182,212,0.15); }

.analysis-card-title {
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}
.analysis-card-subtitle {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
}

.analysis-value {
    font-family: var(--font-mono);
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 8px;
}
.analysis-badge {
    display: inline-block;
    padding: 6px 14px;
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.analysis-badge.bullish {
    background: rgba(34,197,94,0.15);
    border: 1px solid rgba(34,197,94,0.3);
    color: var(--green-400);
}
.analysis-badge.bearish {
    background: rgba(239,68,68,0.15);
    border: 1px solid rgba(239,68,68,0.3);
    color: var(--red-400);
}
.analysis-badge.neutral {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border-default);
    color: var(--text-secondary);
}

.analysis-details {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--border-subtle);
}
.analysis-detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    font-size: 12px;
}
.analysis-detail-row:not(:last-child) { border-bottom: 1px solid var(--border-subtle); }
.analysis-detail-label { color: var(--text-muted); }
.analysis-detail-value {
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text-primary);
}

.flow-meter-container { margin: 16px 0; }
.flow-meter {
    height: 12px;
    background: linear-gradient(90deg, var(--red-500) 0%, var(--amber-500) 50%, var(--green-500) 100%);
    border-radius: 6px;
    position: relative;
}
.flow-meter-marker {
    position: absolute;
    top: -4px;
    width: 8px;
    height: 20px;
    background: #fff;
    border-radius: 4px;
    transform: translateX(-50%);
    box-shadow: 0 2px 8px rgba(0,0,0,0.3), 0 0 12px rgba(255,255,255,0.3);
    transition: left 0.5s ease;
}
.flow-meter-labels {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    font-size: 9px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.session-table-container {
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    overflow: hidden;
}
.session-table {
    width: 100%;
    border-collapse: collapse;
}
.session-table thead { background: rgba(0,0,0,0.3); }
.session-table th {
    padding: 14px 16px;
    text-align: left;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid var(--border-default);
}
.session-table td {
    padding: 14px 16px;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--text-primary);
    border-bottom: 1px solid var(--border-subtle);
}
.session-table tbody tr { transition: var(--transition-fast); }
.session-table tbody tr:hover { background: rgba(255,255,255,0.02); }
.session-table tbody tr:last-child td { border-bottom: none; }
.session-table .session-name {
    font-family: var(--font-body);
    font-weight: 500;
    color: var(--text-secondary);
}
.session-table .highlight-row { background: rgba(139,92,246,0.05); }
.session-table .highlight-row td { font-weight: 600; }
.session-table .value-high { color: var(--green-400); }
.session-table .value-low { color: var(--red-400); }

.cones-container {
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: 20px;
}
.cones-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-subtle);
}
.cones-title {
    font-family: var(--font-display);
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
}
.cones-subtitle {
    font-size: 11px;
    color: var(--text-muted);
}

.cones-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
}
.cone-card {
    background: rgba(0,0,0,0.25);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 16px;
    text-align: center;
    transition: var(--transition-normal);
}
.cone-card:hover {
    background: rgba(0,0,0,0.35);
    border-color: var(--border-default);
}
.cone-card-name {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 16px;
}
.cone-card-anchor {
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-subtle);
}
.cone-card-anchor span {
    color: var(--text-muted);
    font-size: 10px;
    margin-right: 6px;
}
.cone-card-levels {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}
.cone-level {
    padding: 10px;
    border-radius: var(--radius-sm);
}
.cone-level.asc {
    background: rgba(34,197,94,0.08);
    border: 1px solid rgba(34,197,94,0.2);
}
.cone-level.desc {
    background: rgba(239,68,68,0.08);
    border: 1px solid rgba(239,68,68,0.2);
}
.cone-level-label {
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.cone-level.asc .cone-level-label { color: var(--green-500); }
.cone-level.desc .cone-level-label { color: var(--red-500); }
.cone-level-value {
    font-family: var(--font-mono);
    font-size: 15px;
    font-weight: 600;
}
.cone-level.asc .cone-level-value { color: var(--green-400); }
.cone-level.desc .cone-level-value { color: var(--red-400); }

.cone-card-meta {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border-subtle);
    font-size: 10px;
    color: var(--text-muted);
}
.cone-card-meta span {
    font-family: var(--font-mono);
    color: var(--text-secondary);
}

.all-trades-container {
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: 20px;
}
.all-trades-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-subtle);
}
.all-trades-title {
    font-family: var(--font-display);
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
}

.all-trades-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
}
.structure-line-card {
    background: rgba(0,0,0,0.2);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: 18px;
    transition: var(--transition-normal);
    position: relative;
    overflow: hidden;
}
.structure-line-card:hover {
    background: rgba(0,0,0,0.3);
    border-color: var(--border-bright);
    transform: translateY(-2px);
}
.structure-line-card.active {
    border-color: var(--cyan-500);
    box-shadow: var(--glow-cyan);
}
.structure-line-card.active::before {
    content: 'ACTIVE';
    position: absolute;
    top: 10px;
    right: 10px;
    font-size: 8px;
    font-weight: 700;
    color: var(--cyan-400);
    background: rgba(6,182,212,0.15);
    padding: 3px 8px;
    border-radius: 4px;
    letter-spacing: 1px;
}

.structure-line-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
}
.structure-line-name {
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}
.structure-line-type {
    font-size: 9px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.structure-line-type.calls {
    background: rgba(34,197,94,0.15);
    color: var(--green-400);
}
.structure-line-type.puts {
    background: rgba(239,68,68,0.15);
    color: var(--red-400);
}

.structure-line-level {
    font-family: var(--font-mono);
    font-size: 26px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 6px;
}
.structure-line-distance {
    font-family: var(--font-mono);
    font-size: 12px;
    margin-bottom: 14px;
}
.structure-line-distance.above { color: var(--green-400); }
.structure-line-distance.below { color: var(--red-400); }

.structure-line-meta {
    display: flex;
    justify-content: space-between;
    padding-top: 12px;
    border-top: 1px solid var(--border-subtle);
    font-size: 11px;
    color: var(--text-muted);
}
.structure-line-meta-value {
    font-family: var(--font-mono);
    color: var(--text-secondary);
}

.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    font-family: var(--font-display) !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
}
.streamlit-expanderHeader:hover {
    background: var(--bg-card-hover) !important;
    border-color: var(--border-bright) !important;
}
.streamlit-expanderContent {
    border: 1px solid var(--border-default) !important;
    border-top: none !important;
    border-radius: 0 0 var(--radius-md) var(--radius-md) !important;
    background: var(--bg-secondary) !important;
}

.debug-container {
    background: rgba(239,68,68,0.05);
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: var(--radius-md);
    padding: 20px;
    margin-top: 20px;
}
.debug-title {
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 600;
    color: var(--red-400);
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.debug-section {
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(239,68,68,0.1);
}
.debug-section:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
}
.debug-section-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.debug-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 12px;
}
.debug-label { color: var(--text-muted); }
.debug-value {
    font-family: var(--font-mono);
    color: var(--text-primary);
}

.app-footer {
    text-align: center;
    padding: 32px 20px;
    margin-top: 40px;
    border-top: 1px solid var(--border-subtle);
    position: relative;
}
.app-footer::before {
    content: '';
    position: absolute;
    top: 0;
    left: 20%;
    right: 20%;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(139,92,246,0.3), rgba(6,182,212,0.3), transparent);
}
.footer-brand {
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
}
.footer-brand span {
    background: linear-gradient(135deg, var(--purple-400), var(--cyan-400));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.footer-meta {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
}
.footer-meta span {
    margin: 0 8px;
    color: var(--border-bright);
}

.text-green { color: var(--green-400) !important; }
.text-red { color: var(--red-400) !important; }
.text-amber { color: var(--amber-400) !important; }
.text-purple { color: var(--purple-400) !important; }
.text-cyan { color: var(--cyan-400) !important; }
.text-muted { color: var(--text-muted) !important; }

.bg-green { background: rgba(34,197,94,0.15) !important; }
.bg-red { background: rgba(239,68,68,0.15) !important; }
.bg-amber { background: rgba(245,158,11,0.15) !important; }
.bg-purple { background: rgba(139,92,246,0.15) !important; }
.bg-cyan { background: rgba(6,182,212,0.15) !important; }

.glow-green { box-shadow: var(--glow-green) !important; }
.glow-red { box-shadow: var(--glow-red) !important; }
.glow-purple { box-shadow: var(--glow-purple) !important; }
.glow-cyan { box-shadow: var(--glow-cyan) !important; }

.mono { font-family: var(--font-mono) !important; }
.display { font-family: var(--font-display) !important; }

.mt-0 { margin-top: 0 !important; }
.mt-1 { margin-top: 8px !important; }
.mt-2 { margin-top: 16px !important; }
.mt-3 { margin-top: 24px !important; }
.mb-0 { margin-bottom: 0 !important; }
.mb-1 { margin-bottom: 8px !important; }
.mb-2 { margin-bottom: 16px !important; }
.mb-3 { margin-bottom: 24px !important; }

@media (max-width: 1200px) {
    .hero-grid {
        grid-template-columns: 1fr;
        gap: 20px;
        text-align: center;
    }
    .hero-left, .hero-right { text-align: center; }
    .analysis-grid { grid-template-columns: 1fr; }
    .trade-metrics-grid { grid-template-columns: repeat(2, 1fr); }
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes slideIn {
    from { opacity: 0; transform: translateX(-20px); }
    to { opacity: 1; transform: translateX(0); }
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

.animate-fade-in { animation: fadeIn 0.4s ease-out; }
.animate-slide-in { animation: slideIn 0.4s ease-out; }
.animate-pulse { animation: pulse 2s infinite; }

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stDeployButton { display: none; }
</style>
"""


# ═══════════════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════════════

def get_now_ct() -> datetime:
    """Get current time in Central Time"""
    return datetime.now(CT)

def count_30min_blocks(start_dt: datetime, end_dt: datetime) -> int:
    """Count number of 30-minute blocks between two datetimes"""
    if start_dt >= end_dt:
        return 0
    diff = end_dt - start_dt
    return int(diff.total_seconds() / 1800)  # 1800 seconds = 30 minutes

def get_trading_phase(now: datetime, trading_date: date) -> TradingPhase:
    """Determine current phase in the trading day"""
    if now.date() != trading_date:
        return TradingPhase.MARKET_CLOSED
    
    current_time = now.time()
    
    if current_time < MARKET_OPEN:
        return TradingPhase.PRE_MARKET
    elif current_time < VALIDATION_END:
        return TradingPhase.VALIDATING
    elif current_time < ENTRY_WINDOW_END:
        return TradingPhase.ENTRY_WINDOW
    elif current_time < SECONDARY_ENTRY_END:
        return TradingPhase.SECONDARY_ENTRY
    elif current_time < MARKET_CLOSE:
        return TradingPhase.IN_TRADE
    else:
        return TradingPhase.MARKET_CLOSED

def es_to_spx(es_price: float, offset: float) -> float:
    """Convert ES price to SPX (SPX = ES - offset)"""
    return round(es_price - offset, 2)

def spx_to_es(spx_price: float, offset: float) -> float:
    """Convert SPX price to ES (ES = SPX + offset)"""
    return round(spx_price + offset, 2)

def select_strike(entry_level: float, direction: Direction) -> int:
    """
    Select option strike ~20 points OTM from entry level.
    
    For CALLS: Strike = Entry + 20 (buy OTM call that gains value as price rises)
    For PUTS: Strike = Entry - 20 (buy OTM put that gains value as price falls)
    """
    if direction == Direction.CALLS:
        raw_strike = entry_level + 20
    else:
        raw_strike = entry_level - 20
    
    # Round to nearest 5
    return int(round(raw_strike / 5) * 5)

def format_time_ct(dt: datetime) -> str:
    """Format datetime to readable CT string"""
    return dt.strftime("%I:%M %p CT")

def format_price(price: float) -> str:
    """Format price with commas and 2 decimal places"""
    return f"{price:,.2f}"

# ═══════════════════════════════════════════════════════════════════════════════════════
# PERSISTENCE - Save/Load User Inputs
# ═══════════════════════════════════════════════════════════════════════════════════════

def save_inputs(inputs: Dict) -> bool:
    """Save user inputs to JSON file"""
    try:
        serializable = {}
        for key, value in inputs.items():
            if isinstance(value, datetime):
                serializable[key] = value.isoformat()
            elif isinstance(value, date):
                serializable[key] = value.isoformat()
            elif isinstance(value, time):
                serializable[key] = value.strftime("%H:%M")
            elif isinstance(value, Enum):
                serializable[key] = value.value
            else:
                serializable[key] = value
        
        with open(SAVE_FILE, 'w') as f:
            json.dump(serializable, f, indent=2)
        return True
    except Exception as e:
        return False

def load_inputs() -> Dict:
    """Load user inputs from JSON file"""
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# ═══════════════════════════════════════════════════════════════════════════════════════
# POLYGON API - Data Fetching
# ═══════════════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_from_polygon() -> Optional[float]:
    """Fetch current SPX price from Polygon API"""
    try:
        url = f"{POLYGON_BASE}/v3/snapshot?ticker.any_of=I:SPX&apiKey={POLYGON_KEY}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                # Try multiple price fields
                price = (
                    result.get("value") or
                    result.get("session", {}).get("close") or
                    result.get("session", {}).get("previous_close")
                )
                if price:
                    return round(float(price), 2)
    except Exception:
        pass
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_from_polygon() -> Optional[float]:
    """Fetch current VIX price from Polygon API"""
    try:
        url = f"{POLYGON_BASE}/v3/snapshot?ticker.any_of=I:VIX&apiKey={POLYGON_KEY}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                price = (
                    result.get("value") or
                    result.get("session", {}).get("close") or
                    result.get("session", {}).get("previous_close")
                )
                if price:
                    return round(float(price), 2)
    except Exception:
        pass
    return None

def build_option_ticker(expiry_date: date, strike: float, option_type: str) -> str:
    """
    Build SPXW option ticker for Polygon API.
    Format: O:SPXW{YYMMDD}{C/P}{strike*1000 as 8 digits}
    """
    date_str = expiry_date.strftime("%y%m%d")
    type_char = "C" if option_type == "CALL" else "P"
    strike_int = int(strike * 1000)
    strike_str = f"{strike_int:08d}"
    return f"O:SPXW{date_str}{type_char}{strike_str}"

@st.cache_data(ttl=30, show_spinner=False)
def fetch_option_quote(ticker: str) -> Optional[Dict]:
    """Fetch option quote from Polygon API"""
    try:
        # Try quotes endpoint first
        url = f"{POLYGON_BASE}/v3/quotes/{ticker}?limit=1&apiKey={POLYGON_KEY}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                bid = result.get("bid_price", 0)
                ask = result.get("ask_price", 0)
                midpoint = (bid + ask) / 2 if bid and ask else None
                
                return {
                    "last_price": midpoint,
                    "bid": bid,
                    "ask": ask,
                    "ticker": ticker
                }
        
        # Fallback to snapshot
        url = f"{POLYGON_BASE}/v3/snapshot/options/{ticker}?apiKey={POLYGON_KEY}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data:
                result = data["results"]
                day_data = result.get("day", {})
                last_quote = result.get("last_quote", {})
                
                return {
                    "last_price": day_data.get("close") or day_data.get("last_trade", {}).get("price"),
                    "bid": last_quote.get("bid"),
                    "ask": last_quote.get("ask"),
                    "iv": result.get("implied_volatility"),
                    "delta": result.get("greeks", {}).get("delta"),
                    "ticker": ticker
                }
    except Exception:
        pass
    return None

# ═══════════════════════════════════════════════════════════════════════════════════════
# YAHOO FINANCE - ES Futures Data
# ═══════════════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120, show_spinner=False)
def fetch_es_data(days: int = 5) -> Optional[pd.DataFrame]:
    """
    Fetch ES futures 30-minute candles from Yahoo Finance.
    Returns DataFrame with OHLCV data indexed by CT datetime.
    """
    for attempt in range(3):
        try:
            es = yf.Ticker("ES=F")
            data = es.history(period=f"{days}d", interval="30m")
            
            if data is not None and not data.empty:
                # Ensure timezone-aware index in CT
                if data.index.tz is None:
                    data.index = data.index.tz_localize('America/New_York').tz_convert(CT)
                else:
                    data.index = data.index.tz_convert(CT)
                return data
        except Exception:
            time_module.sleep(1)
    return None

def get_current_es_price(es_data: Optional[pd.DataFrame]) -> Optional[float]:
    """Get most recent ES price from DataFrame"""
    try:
        if es_data is not None and not es_data.empty:
            return round(es_data['Close'].iloc[-1], 2)
    except Exception:
        pass
    return None

# ═══════════════════════════════════════════════════════════════════════════════════════
# SESSION LEVEL DETECTION - Sydney, Tokyo, Overnight
# ═══════════════════════════════════════════════════════════════════════════════════════

def get_session_levels(
    es_data: pd.DataFrame,
    trading_date: date,
    session: str
) -> SessionLevels:
    """
    Extract high/low levels for a specific trading session from ES data.
    
    Sessions (CT times):
    - SYDNEY: 5:00 PM - 8:30 PM (previous day)
    - TOKYO: 9:00 PM (previous day) - 1:30 AM (trading day)
    - OVERNIGHT: 5:00 PM (previous day) - 8:30 AM (trading day)
    """
    prev_date = trading_date - timedelta(days=1)
    
    # Define session boundaries
    if session == "SYDNEY":
        start = CT.localize(datetime.combine(prev_date, time(17, 0)))
        end = CT.localize(datetime.combine(prev_date, time(20, 30)))
    elif session == "TOKYO":
        start = CT.localize(datetime.combine(prev_date, time(21, 0)))
        end = CT.localize(datetime.combine(trading_date, time(1, 30)))
    elif session == "OVERNIGHT":
        start = CT.localize(datetime.combine(prev_date, time(17, 0)))
        end = CT.localize(datetime.combine(trading_date, time(8, 30)))
    else:
        return SessionLevels()
    
    try:
        # Filter data for session window
        mask = (es_data.index >= start) & (es_data.index <= end)
        session_data = es_data[mask]
        
        if session_data.empty:
            return SessionLevels()
        
        # Find high and low
        high_val = session_data['High'].max()
        low_val = session_data['Low'].min()
        high_time = session_data['High'].idxmax()
        low_time = session_data['Low'].idxmin()
        
        return SessionLevels(
            high=round(high_val, 2),
            low=round(low_val, 2),
            high_time=high_time,
            low_time=low_time
        )
    except Exception:
        return SessionLevels()

def get_830_candle(
    es_data: pd.DataFrame,
    trading_date: date
) -> Dict[str, Any]:
    """
    Extract the 8:30 AM candle from ES data.
    Returns OHLC values and completion status.
    """
    try:
        candle_start = CT.localize(datetime.combine(trading_date, time(8, 30)))
        candle_end = candle_start + timedelta(minutes=30)
        
        # Find candle in data
        mask = (es_data.index >= candle_start) & (es_data.index < candle_end)
        candle_data = es_data[mask]
        
        if candle_data.empty:
            return {
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "complete": False
            }
        
        # Get OHLC
        candle = candle_data.iloc[0]
        
        # Check if candle is complete (current time >= 9:00 AM)
        now = get_now_ct()
        is_complete = now >= CT.localize(datetime.combine(trading_date, time(9, 0)))
        
        return {
            "open": round(candle['Open'], 2),
            "high": round(candle['High'], 2),
            "low": round(candle['Low'], 2),
            "close": round(candle['Close'], 2),
            "complete": is_complete
        }
    except Exception:
        return {
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "complete": False
        }

def calculate_es_spx_offset(es_price: float, spx_price: float) -> float:
    """
    Calculate the ES-SPX offset.
    SPX is always LOWER than ES, so: offset = ES - SPX
    """
    return round(es_price - spx_price, 2)

# ═══════════════════════════════════════════════════════════════════════════════════════
# CHANNEL SELECTION - Sydney vs Tokyo Analysis
# ═══════════════════════════════════════════════════════════════════════════════════════

def determine_channel(
    sydney: SessionLevels,
    tokyo: SessionLevels
) -> Tuple[Channel, str]:
    """
    Determine the active channel for the day based on Sydney vs Tokyo session behavior.
    
    Rules:
    - RISING CHANNEL: Tokyo High > Sydney High (bullish overnight, use rising edges)
    - FALLING CHANNEL: Tokyo Low < Sydney Low (bearish overnight, use falling edges)
    - If both conditions met: Use the larger expansion to determine bias
    - If neither: UNDETERMINED
    
    Returns:
        Tuple of (Channel enum, reasoning string)
    """
    # Validate we have all required data
    if not all([sydney.high, sydney.low, tokyo.high, tokyo.low]):
        return Channel.UNDETERMINED, "Insufficient session data - enter manually"
    
    # Check conditions
    tokyo_high_above = tokyo.high > sydney.high
    tokyo_low_below = tokyo.low < sydney.low
    
    # Calculate expansions for tie-breaking
    high_expansion = tokyo.high - sydney.high if tokyo_high_above else 0
    low_expansion = sydney.low - tokyo.low if tokyo_low_below else 0
    
    if tokyo_high_above and not tokyo_low_below:
        # Clear RISING signal
        return Channel.RISING, f"Tokyo High ({tokyo.high:.2f}) > Sydney High ({sydney.high:.2f}) → RISING"
    
    elif tokyo_low_below and not tokyo_high_above:
        # Clear FALLING signal
        return Channel.FALLING, f"Tokyo Low ({tokyo.low:.2f}) < Sydney Low ({sydney.low:.2f}) → FALLING"
    
    elif tokyo_high_above and tokyo_low_below:
        # Both conditions - use larger expansion
        if high_expansion > low_expansion:
            return Channel.RISING, f"Range expanded both ways, upside dominates (+{high_expansion:.1f} vs -{low_expansion:.1f})"
        elif low_expansion > high_expansion:
            return Channel.FALLING, f"Range expanded both ways, downside dominates (-{low_expansion:.1f} vs +{high_expansion:.1f})"
        else:
            return Channel.UNDETERMINED, "Equal expansion both directions - wait for clarity"
    
    else:
        # Neither condition - inside day
        return Channel.UNDETERMINED, "Tokyo contained within Sydney range - no clear bias"


# ═══════════════════════════════════════════════════════════════════════════════════════
# CHANNEL EDGE CALCULATIONS - The 4 Structure Lines
# ═══════════════════════════════════════════════════════════════════════════════════════

def calculate_structure_lines(
    on_high: float,
    on_high_time: datetime,
    on_low: float,
    on_low_time: datetime,
    reference_time: datetime
) -> Dict[str, ChannelEdge]:
    """
    Calculate all 4 structure lines from overnight high/low.
    
    The lines expand/contract from their anchors at 0.48 points per 30-min block:
    - Ceiling Rising: O/N High + expansion (entry type: PUTS)
    - Ceiling Falling: O/N High - expansion (entry type: CALLS) 
    - Floor Rising: O/N Low + expansion (entry type: PUTS)
    - Floor Falling: O/N Low - expansion (entry type: CALLS)
    
    Args:
        on_high: Overnight high price (ES)
        on_high_time: Time of overnight high
        on_low: Overnight low price (ES)
        on_low_time: Time of overnight low
        reference_time: Time to calculate levels for (typically 9:00 AM CT)
    
    Returns:
        Dictionary of all 4 ChannelEdge objects
    """
    # Count 30-min blocks from anchor times to reference time
    blocks_from_high = count_30min_blocks(on_high_time, reference_time)
    blocks_from_low = count_30min_blocks(on_low_time, reference_time)
    
    # Calculate expansions
    expansion_high = SLOPE * blocks_from_high
    expansion_low = SLOPE * blocks_from_low
    
    return {
        "ceiling_rising": ChannelEdge(
            name="Ceiling Rising",
            level=round(on_high + expansion_high, 2),
            anchor=on_high,
            blocks=blocks_from_high,
            expansion=round(expansion_high, 2),
            entry_type=Direction.PUTS
        ),
        "ceiling_falling": ChannelEdge(
            name="Ceiling Falling",
            level=round(on_high - expansion_high, 2),
            anchor=on_high,
            blocks=blocks_from_high,
            expansion=round(expansion_high, 2),
            entry_type=Direction.CALLS
        ),
        "floor_rising": ChannelEdge(
            name="Floor Rising",
            level=round(on_low + expansion_low, 2),
            anchor=on_low,
            blocks=blocks_from_low,
            expansion=round(expansion_low, 2),
            entry_type=Direction.PUTS
        ),
        "floor_falling": ChannelEdge(
            name="Floor Falling",
            level=round(on_low - expansion_low, 2),
            anchor=on_low,
            blocks=blocks_from_low,
            expansion=round(expansion_low, 2),
            entry_type=Direction.CALLS
        )
    }


def get_active_channel_edges(
    all_lines: Dict[str, ChannelEdge],
    channel: Channel
) -> Tuple[ChannelEdge, ChannelEdge]:
    """
    Get the ceiling and floor edges for the active channel.
    
    RISING CHANNEL: Ceiling Rising + Floor Rising
    FALLING CHANNEL: Ceiling Falling + Floor Falling
    UNDETERMINED: Default to Ceiling Rising + Floor Falling (widest range)
    
    Returns:
        Tuple of (ceiling_edge, floor_edge)
    """
    if channel == Channel.RISING:
        return all_lines["ceiling_rising"], all_lines["floor_rising"]
    elif channel == Channel.FALLING:
        return all_lines["ceiling_falling"], all_lines["floor_falling"]
    else:
        # Undetermined - use widest channel for safety
        return all_lines["ceiling_rising"], all_lines["floor_falling"]


# ═══════════════════════════════════════════════════════════════════════════════════════
# PRE-OPEN POSITION ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════════════════

def assess_pre_open_position(
    current_price: float,
    ceiling: ChannelEdge,
    floor: ChannelEdge
) -> Tuple[PreOpenPosition, float, str]:
    """
    Determine where price is relative to the active channel before 8:30 AM.
    
    Rules for "broken":
    - Greater than 6 points outside the channel edge, OR
    - A 30-min close outside (handled separately by candle analysis)
    
    Args:
        current_price: Current ES or SPX price
        ceiling: The active ceiling edge
        floor: The active floor edge
    
    Returns:
        Tuple of (PreOpenPosition enum, distance from edge, description)
    """
    ceiling_level = ceiling.level
    floor_level = floor.level
    
    # Calculate distances
    dist_above_ceiling = current_price - ceiling_level
    dist_below_floor = floor_level - current_price
    
    # Check if above channel
    if dist_above_ceiling > CHANNEL_BREAK_THRESHOLD:
        return (
            PreOpenPosition.ABOVE,
            round(dist_above_ceiling, 1),
            f"Broken ABOVE by {dist_above_ceiling:.1f} pts"
        )
    elif dist_above_ceiling > 0:
        return (
            PreOpenPosition.ABOVE,
            round(dist_above_ceiling, 1),
            f"Above ceiling by {dist_above_ceiling:.1f} pts (marginal)"
        )
    
    # Check if below channel
    if dist_below_floor > CHANNEL_BREAK_THRESHOLD:
        return (
            PreOpenPosition.BELOW,
            round(dist_below_floor, 1),
            f"Broken BELOW by {dist_below_floor:.1f} pts"
        )
    elif dist_below_floor > 0:
        return (
            PreOpenPosition.BELOW,
            round(dist_below_floor, 1),
            f"Below floor by {dist_below_floor:.1f} pts (marginal)"
        )
    
    # Inside channel
    channel_width = ceiling_level - floor_level
    if channel_width > 0:
        position_pct = ((current_price - floor_level) / channel_width) * 100
    else:
        position_pct = 50.0
    
    return (
        PreOpenPosition.INSIDE,
        round(position_pct, 1),
        f"Inside channel at {position_pct:.0f}%"
    )


# ═══════════════════════════════════════════════════════════════════════════════════════
# 8:30 CANDLE VALIDATION - The Core Decision Engine
# ═══════════════════════════════════════════════════════════════════════════════════════

def validate_830_candle(
    candle: Dict[str, Any],
    pre_open_position: PreOpenPosition,
    ceiling: ChannelEdge,
    floor: ChannelEdge,
    offset: float
) -> Tuple[SetupStatus, str, Dict[str, Any]]:
    """
    Validate the 8:30 AM candle against channel edges to determine trade setup.
    
    This is the core decision engine implementing David's strategy:
    
    IF BELOW CHANNEL at open:
        - 8:30 candle should RISE to touch floor, then CLOSE BELOW it
        - VALID: Touch floor + close below → PUTS at 9:00-9:10 AM
        - INVALIDATED: Close above floor → Price rallies to ceiling, wait for PUTS there
        - TREND DAY: Touch floor + close INSIDE channel → Trade the range
    
    IF ABOVE CHANNEL at open:
        - 8:30 candle should DROP to touch ceiling, then CLOSE ABOVE it
        - VALID: Touch ceiling + close above → CALLS at 9:00-9:10 AM
        - INVALIDATED: Close below ceiling → Price drops to floor, wait for CALLS there
        - TREND DAY: Touch ceiling + close INSIDE channel → Trade the range
    
    IF INSIDE CHANNEL at open:
        - Wait for 8:30 candle to break an edge
        - Entry at 9:00-9:30 AM when price returns to broken edge
    
    Args:
        candle: Dict with open, high, low, close, complete keys (ES prices)
        pre_open_position: Where price was before 8:30
        ceiling: Active ceiling edge (SPX price)
        floor: Active floor edge (SPX price)
        offset: ES-SPX offset for conversion
    
    Returns:
        Tuple of (SetupStatus, reason_string, trade_plan_dict)
    """
    # Check if candle data is available
    if not candle.get("complete") or candle.get("close") is None:
        return (
            SetupStatus.AWAITING_830,
            "Waiting for 8:30 candle to complete at 9:00 AM",
            {}
        )
    
    # Convert channel edges to ES for comparison with candle
    ceiling_es = spx_to_es(ceiling.level, offset)
    floor_es = spx_to_es(floor.level, offset)
    
    # Extract candle values
    candle_open = candle["open"]
    candle_high = candle["high"]
    candle_low = candle["low"]
    candle_close = candle["close"]
    
    # Define touch tolerance (within 2 points = touched)
    TOUCH_TOLERANCE = 2.0
    
    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 1: Price BELOW channel at open
    # ─────────────────────────────────────────────────────────────────────────────
    if pre_open_position == PreOpenPosition.BELOW:
        touched_floor = candle_high >= (floor_es - TOUCH_TOLERANCE)
        closed_below_floor = candle_close < floor_es
        closed_above_ceiling = candle_close > ceiling_es
        closed_inside = (floor_es <= candle_close <= ceiling_es)
        
        if touched_floor and closed_below_floor:
            # ✅ VALID SETUP - PUTS
            return (
                SetupStatus.VALID,
                f"8:30 touched Floor ({floor_es:.2f}) and closed below → VALID PUT SETUP",
                {
                    "direction": Direction.PUTS,
                    "entry_edge": "floor",
                    "entry_level_spx": floor.level,
                    "entry_level_es": floor_es,
                    "entry_window": "9:00-9:10 AM CT",
                    "invalidation_spx": ceiling.level,
                }
            )
        
        elif touched_floor and closed_inside:
            # 📊 TREND DAY - Touched and closed inside
            return (
                SetupStatus.TREND_DAY,
                f"8:30 touched Floor and closed INSIDE channel → TREND DAY",
                {
                    "mode": "trend_day",
                    "buy_level_spx": floor.level,
                    "sell_level_spx": ceiling.level,
                }
            )
        
        elif closed_above_ceiling:
            # ❌ INVALIDATED - Strong rally, wait for ceiling
            return (
                SetupStatus.INVALIDATED,
                f"8:30 closed above Ceiling ({ceiling_es:.2f}) → Wait for PUTS at Ceiling",
                {
                    "direction": Direction.PUTS,
                    "entry_edge": "ceiling",
                    "entry_level_spx": ceiling.level,
                    "entry_level_es": ceiling_es,
                    "entry_window": "When price reaches ceiling",
                    "invalidation_spx": ceiling.level + 10,  # Above ceiling invalidates
                }
            )
        
        elif closed_inside:
            # ❌ INVALIDATED - Closed inside without touching floor
            return (
                SetupStatus.INVALIDATED,
                f"8:30 closed inside channel without touching Floor → Wait for Ceiling",
                {
                    "direction": Direction.PUTS,
                    "entry_edge": "ceiling", 
                    "entry_level_spx": ceiling.level,
                    "entry_level_es": ceiling_es,
                    "entry_window": "When price reaches ceiling",
                    "invalidation_spx": ceiling.level + 10,
                }
            )
        
        else:
            # Still watching
            return (
                SetupStatus.AWAITING_830,
                "8:30 candle didn't reach Floor - monitoring",
                {}
            )
    
    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 2: Price ABOVE channel at open
    # ─────────────────────────────────────────────────────────────────────────────
    elif pre_open_position == PreOpenPosition.ABOVE:
        touched_ceiling = candle_low <= (ceiling_es + TOUCH_TOLERANCE)
        closed_above_ceiling = candle_close > ceiling_es
        closed_below_floor = candle_close < floor_es
        closed_inside = (floor_es <= candle_close <= ceiling_es)
        
        if touched_ceiling and closed_above_ceiling:
            # ✅ VALID SETUP - CALLS
            return (
                SetupStatus.VALID,
                f"8:30 touched Ceiling ({ceiling_es:.2f}) and closed above → VALID CALL SETUP",
                {
                    "direction": Direction.CALLS,
                    "entry_edge": "ceiling",
                    "entry_level_spx": ceiling.level,
                    "entry_level_es": ceiling_es,
                    "entry_window": "9:00-9:10 AM CT",
                    "invalidation_spx": floor.level,
                }
            )
        
        elif touched_ceiling and closed_inside:
            # 📊 TREND DAY - Touched and closed inside
            return (
                SetupStatus.TREND_DAY,
                f"8:30 touched Ceiling and closed INSIDE channel → TREND DAY",
                {
                    "mode": "trend_day",
                    "buy_level_spx": floor.level,
                    "sell_level_spx": ceiling.level,
                }
            )
        
        elif closed_below_floor:
            # ❌ INVALIDATED - Strong selloff, wait for floor
            return (
                SetupStatus.INVALIDATED,
                f"8:30 closed below Floor ({floor_es:.2f}) → Wait for CALLS at Floor",
                {
                    "direction": Direction.CALLS,
                    "entry_edge": "floor",
                    "entry_level_spx": floor.level,
                    "entry_level_es": floor_es,
                    "entry_window": "When price reaches floor",
                    "invalidation_spx": floor.level - 10,
                }
            )
        
        elif closed_inside:
            # ❌ INVALIDATED - Closed inside without touching ceiling
            return (
                SetupStatus.INVALIDATED,
                f"8:30 closed inside channel without touching Ceiling → Wait for Floor",
                {
                    "direction": Direction.CALLS,
                    "entry_edge": "floor",
                    "entry_level_spx": floor.level,
                    "entry_level_es": floor_es,
                    "entry_window": "When price reaches floor",
                    "invalidation_spx": floor.level - 10,
                }
            )
        
        else:
            return (
                SetupStatus.AWAITING_830,
                "8:30 candle didn't reach Ceiling - monitoring",
                {}
            )
    
    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 3: Price INSIDE channel at open
    # ─────────────────────────────────────────────────────────────────────────────
    else:  # PreOpenPosition.INSIDE
        broke_above = candle_close > ceiling_es
        broke_below = candle_close < floor_es
        
        if broke_above:
            # Broke above - wait for return to ceiling for PUTS
            return (
                SetupStatus.VALID,
                f"8:30 broke ABOVE Ceiling → Wait for return to Ceiling for PUTS",
                {
                    "direction": Direction.PUTS,
                    "entry_edge": "ceiling",
                    "entry_level_spx": ceiling.level,
                    "entry_level_es": ceiling_es,
                    "entry_window": "9:00-9:30 AM CT (return to edge)",
                    "invalidation_spx": ceiling.level + 15,
                }
            )
        
        elif broke_below:
            # Broke below - wait for return to floor for CALLS
            return (
                SetupStatus.VALID,
                f"8:30 broke BELOW Floor → Wait for return to Floor for CALLS",
                {
                    "direction": Direction.CALLS,
                    "entry_edge": "floor",
                    "entry_level_spx": floor.level,
                    "entry_level_es": floor_es,
                    "entry_window": "9:00-9:30 AM CT (return to edge)",
                    "invalidation_spx": floor.level - 15,
                }
            )
        
        else:
            # Still inside - likely trend day
            return (
                SetupStatus.TREND_DAY,
                "8:30 remained INSIDE channel → TREND DAY - Trade the range",
                {
                    "mode": "trend_day",
                    "buy_level_spx": floor.level,
                    "sell_level_spx": ceiling.level,
                }
            )


# ═══════════════════════════════════════════════════════════════════════════════════════
# CONE RAIL CALCULATIONS - Prior Day Projections
# ═══════════════════════════════════════════════════════════════════════════════════════

def calculate_cone_rails(
    prior_high: float,
    prior_high_time: datetime,
    prior_low: float,
    prior_low_time: datetime,
    prior_close: float,
    prior_close_time: datetime,
    reference_time: datetime
) -> Dict[str, ConeRail]:
    """
    Calculate ascending and descending cone rails from prior day levels.
    
    Each prior day level (High, Low, Close) projects two lines:
    - Ascending: anchor + (slope × blocks) - potential resistance/target above
    - Descending: anchor - (slope × blocks) - potential support/target below
    
    Args:
        prior_high/low/close: Prior day price levels (SPX)
        prior_high_time/low_time/close_time: Times of those levels
        reference_time: Time to calculate projections for
    
    Returns:
        Dictionary with HIGH, LOW, CLOSE cone rails
    """
    cones = {}
    
    levels = [
        ("HIGH", prior_high, prior_high_time),
        ("LOW", prior_low, prior_low_time),
        ("CLOSE", prior_close, prior_close_time)
    ]
    
    for name, price, anchor_time in levels:
        blocks = count_30min_blocks(anchor_time, reference_time)
        expansion = SLOPE * blocks
        
        cones[name] = ConeRail(
            name=name,
            anchor=round(price, 2),
            ascending=round(price + expansion, 2),
            descending=round(price - expansion, 2),
            blocks=blocks,
            expansion=round(expansion, 2)
        )
    
    return cones


# ═══════════════════════════════════════════════════════════════════════════════════════
# TARGET FINDING - Cone Lines Above/Below Entry
# ═══════════════════════════════════════════════════════════════════════════════════════

def find_targets(
    entry_level: float,
    direction: Direction,
    cones: Dict[str, ConeRail],
    current_price: float
) -> List[Dict[str, Any]]:
    """
    Find cone rail targets above (for CALLS) or below (for PUTS) the entry level.
    
    Strategy Rules:
    - For CALLS: Look for ASCENDING lines ABOVE entry level
      - First target is the closest ascending line
      - Order: typically Close Asc, then High Asc
    
    - For PUTS: Look for DESCENDING lines BELOW entry level
      - First target is the closest descending line  
      - Order: typically Close Desc, then Low Desc
    
    Args:
        entry_level: The entry price level (SPX)
        direction: CALLS or PUTS
        cones: Dictionary of cone rails
        current_price: Current SPX price (for distance calculation)
    
    Returns:
        List of target dictionaries sorted by distance (closest first)
        First target marked as "primary": True
    """
    targets = []
    
    if direction == Direction.CALLS:
        # Look for ASCENDING lines ABOVE entry
        for cone_name in ["CLOSE", "HIGH", "LOW"]:
            cone = cones.get(cone_name)
            if cone and cone.ascending > entry_level:
                distance = cone.ascending - entry_level
                targets.append({
                    "name": f"{cone_name} Asc",
                    "level": cone.ascending,
                    "type": "ascending",
                    "distance": round(distance, 1),
                    "distance_from_current": round(cone.ascending - current_price, 1),
                    "primary": False
                })
    
    elif direction == Direction.PUTS:
        # Look for DESCENDING lines BELOW entry
        for cone_name in ["CLOSE", "LOW", "HIGH"]:
            cone = cones.get(cone_name)
            if cone and cone.descending < entry_level:
                distance = entry_level - cone.descending
                targets.append({
                    "name": f"{cone_name} Desc",
                    "level": cone.descending,
                    "type": "descending", 
                    "distance": round(distance, 1),
                    "distance_from_current": round(current_price - cone.descending, 1),
                    "primary": False
                })
    
    # Sort by distance (closest first)
    targets.sort(key=lambda x: x["distance"])
    
    # Mark the first (closest) as primary target
    if targets:
        targets[0]["primary"] = True
    
    return targets


def check_confluence(
    structure_level: float,
    cones: Dict[str, ConeRail],
    threshold: float = CONFLUENCE_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Check if a structure level has confluence with any cone rails.
    
    Confluence occurs when a structure line (ceiling/floor) is within
    the threshold distance of a cone rail. This increases confidence.
    
    Returns:
        List of confluence matches with cone name and distance
    """
    confluences = []
    
    for cone_name, cone in cones.items():
        # Check ascending
        dist_asc = abs(structure_level - cone.ascending)
        if dist_asc <= threshold:
            confluences.append({
                "cone": f"{cone_name} Asc",
                "level": cone.ascending,
                "distance": round(dist_asc, 1)
            })
        
        # Check descending
        dist_desc = abs(structure_level - cone.descending)
        if dist_desc <= threshold:
            confluences.append({
                "cone": f"{cone_name} Desc", 
                "level": cone.descending,
                "distance": round(dist_desc, 1)
            })
    
    return confluences


# ═══════════════════════════════════════════════════════════════════════════════════════
# OPTION PRICE ESTIMATION - Black-Scholes Projections
# ═══════════════════════════════════════════════════════════════════════════════════════

def estimate_option_prices(
    current_spx: float,
    entry_level: float,
    target_level: float,
    strike: int,
    direction: Direction,
    vix: float,
    hours_to_expiry: float
) -> Dict[str, Any]:
    """
    Estimate option prices at current, entry, and target levels using Black-Scholes.
    
    Args:
        current_spx: Current SPX price
        entry_level: Entry price level (SPX)
        target_level: Target price level (SPX)
        strike: Option strike price
        direction: CALLS or PUTS
        vix: Current VIX (used as IV proxy)
        hours_to_expiry: Hours until option expiration
    
    Returns:
        Dictionary with current, entry, target prices and profit percentage
    """
    # Convert VIX to decimal IV
    iv = vix / 100.0
    
    # Risk-free rate
    r = 0.05
    
    # Option type
    opt_type = "CALL" if direction == Direction.CALLS else "PUT"
    
    # Time to expiry in years at different points
    T_current = hours_to_expiry / (365 * 24)
    T_entry = max(0.001, (hours_to_expiry - 0.5) / (365 * 24))  # Assume 30 min to entry
    T_target = max(0.001, (hours_to_expiry - 2.0) / (365 * 24))  # Assume 2 hrs to target
    
    # Calculate prices
    price_current = black_scholes(current_spx, strike, T_current, r, iv, opt_type)
    price_entry = black_scholes(entry_level, strike, T_entry, r, iv, opt_type)
    price_target = black_scholes(target_level, strike, T_target, r, iv, opt_type)
    
    # Calculate profit percentage
    if price_entry > 0:
        profit_pct = ((price_target - price_entry) / price_entry) * 100
    else:
        profit_pct = 0
    
    # Calculate delta at entry
    delta = calculate_delta(entry_level, strike, T_entry, r, iv, opt_type)
    
    return {
        "current_price": round(price_current, 2),
        "entry_price": round(price_entry, 2),
        "target_price": round(price_target, 2),
        "profit_pct": round(profit_pct, 1),
        "delta": round(delta, 3),
        "iv_used": round(vix, 1),
        "is_estimated": True
    }


# ═══════════════════════════════════════════════════════════════════════════════════════
# FLOW BIAS - Multi-Signal Retail Positioning Detection
# ═══════════════════════════════════════════════════════════════════════════════════════

def calculate_flow_bias(
    current_price: float,
    on_high: float,
    on_low: float,
    vix_current: float,
    vix_on_high: float,
    vix_on_low: float,
    prior_close: float,
    es_data: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Multi-signal flow bias detection to identify retail positioning.
    
    This REPLACES unreliable Put/Call Ratio APIs with observable signals:
    
    SIGNALS (weighted scoring):
    1. Price Position vs O/N Range (30%) - Where is price in the overnight range?
    2. VIX Momentum (25%) - Is VIX rising (put buying) or falling (call buying)?
    3. Gap Direction (25%) - Gap up = overnight call buying, Gap down = put buying
    4. Intraday Velocity (20%) - Fast moves indicate aggressive positioning
    
    INTERPRETATION:
    - HEAVY_CALLS (score >= 30): Retail aggressively long → MM hunts stops below
    - HEAVY_PUTS (score <= -30): Retail aggressively short → MM hunts stops above
    - NEUTRAL: Mixed signals → Play structure levels as they come
    
    Returns:
        Dictionary with bias, score, signals breakdown, and MM play
    """
    signals = []
    score = 0
    
    # Calculate range metrics
    on_range = on_high - on_low
    on_mid = (on_high + on_low) / 2
    
    # ─────────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Price Position vs O/N Range (Weight: 30%)
    # ─────────────────────────────────────────────────────────────────────────────
    if on_range > 0:
        price_position = ((current_price - on_low) / on_range) * 100
    else:
        price_position = 50
    
    if current_price > on_high:
        score += 30
        signals.append(("Price Position", "CALLS", f"Above O/N High (+{current_price - on_high:.0f} pts)", 30))
    elif current_price < on_low:
        score -= 30
        signals.append(("Price Position", "PUTS", f"Below O/N Low ({current_price - on_low:.0f} pts)", -30))
    elif price_position > 75:
        score += 15
        signals.append(("Price Position", "CALLS", f"Upper quartile ({price_position:.0f}%)", 15))
    elif price_position < 25:
        score -= 15
        signals.append(("Price Position", "PUTS", f"Lower quartile ({price_position:.0f}%)", -15))
    else:
        signals.append(("Price Position", "NEUTRAL", f"Mid-range ({price_position:.0f}%)", 0))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: VIX Momentum (Weight: 25%)
    # ─────────────────────────────────────────────────────────────────────────────
    vix_range = vix_on_high - vix_on_low
    if vix_range > 0:
        vix_position = ((vix_current - vix_on_low) / vix_range) * 100
    else:
        vix_position = 50
    
    if vix_current > vix_on_high:
        score -= 25
        signals.append(("VIX Momentum", "PUTS", f"VIX breakout ({vix_current:.1f})", -25))
    elif vix_current < vix_on_low:
        score += 25
        signals.append(("VIX Momentum", "CALLS", f"VIX breakdown ({vix_current:.1f})", 25))
    elif vix_position > 70:
        score -= 12
        signals.append(("VIX Momentum", "PUTS", f"VIX elevated ({vix_position:.0f}%)", -12))
    elif vix_position < 30:
        score += 12
        signals.append(("VIX Momentum", "CALLS", f"VIX depressed ({vix_position:.0f}%)", 12))
    else:
        signals.append(("VIX Momentum", "NEUTRAL", f"VIX mid-range ({vix_position:.0f}%)", 0))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Gap Direction (Weight: 25%)
    # ─────────────────────────────────────────────────────────────────────────────
    gap = current_price - prior_close
    gap_pct = (gap / prior_close) * 100 if prior_close > 0 else 0
    
    if gap > 10:
        score += 25
        signals.append(("Gap Direction", "CALLS", f"Gap UP +{gap:.0f} pts ({gap_pct:+.2f}%)", 25))
    elif gap < -10:
        score -= 25
        signals.append(("Gap Direction", "PUTS", f"Gap DOWN {gap:.0f} pts ({gap_pct:+.2f}%)", -25))
    elif gap > 5:
        score += 12
        signals.append(("Gap Direction", "CALLS", f"Small gap up +{gap:.0f} pts", 12))
    elif gap < -5:
        score -= 12
        signals.append(("Gap Direction", "PUTS", f"Small gap down {gap:.0f} pts", -12))
    else:
        signals.append(("Gap Direction", "NEUTRAL", f"Flat open ({gap:+.0f} pts)", 0))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: Intraday Velocity (Weight: 20%)
    # ─────────────────────────────────────────────────────────────────────────────
    if es_data is not None and len(es_data) >= 6:
        try:
            recent = es_data.tail(6)
            move = recent['Close'].iloc[-1] - recent['Open'].iloc[0]
            avg_range = (recent['High'] - recent['Low']).mean()
            
            if move > avg_range * 2:
                score += 20
                signals.append(("Velocity", "CALLS", f"Strong rally +{move:.0f} pts", 20))
            elif move < -avg_range * 2:
                score -= 20
                signals.append(("Velocity", "PUTS", f"Strong selloff {move:.0f} pts", -20))
            elif move > avg_range:
                score += 10
                signals.append(("Velocity", "CALLS", f"Mild rally +{move:.0f} pts", 10))
            elif move < -avg_range:
                score -= 10
                signals.append(("Velocity", "PUTS", f"Mild selloff {move:.0f} pts", -10))
            else:
                signals.append(("Velocity", "NEUTRAL", "Choppy/range-bound", 0))
        except:
            signals.append(("Velocity", "N/A", "Insufficient data", 0))
    else:
        signals.append(("Velocity", "N/A", "Insufficient data", 0))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # FINAL DETERMINATION
    # ─────────────────────────────────────────────────────────────────────────────
    if score >= 30:
        bias = "HEAVY_CALLS"
        bias_direction = Direction.CALLS
        mm_play = "MM will hunt call buyers → Expect fake breakdowns before rally"
    elif score <= -30:
        bias = "HEAVY_PUTS"
        bias_direction = Direction.PUTS
        mm_play = "MM will hunt put buyers → Expect fake breakouts before selloff"
    else:
        bias = "NEUTRAL"
        bias_direction = Direction.NEUTRAL
        mm_play = "Mixed positioning → Play structure levels as they come"
    
    # Calculate signal agreement for confidence
    call_signals = sum(1 for s in signals if s[1] == "CALLS")
    put_signals = sum(1 for s in signals if s[1] == "PUTS")
    total_directional = call_signals + put_signals
    
    if total_directional > 0:
        agreement_pct = (max(call_signals, put_signals) / total_directional) * 100
    else:
        agreement_pct = 50
    
    if agreement_pct >= 75:
        confidence = "HIGH"
    elif agreement_pct >= 50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    return {
        "bias": bias,
        "bias_direction": bias_direction,
        "score": score,
        "mm_play": mm_play,
        "confidence": confidence,
        "agreement_pct": round(agreement_pct, 0),
        "signals": signals,
        "price_position": round(price_position, 1),
        "vix_position": round(vix_position, 1),
        "gap": round(gap, 1)
    }


# ═══════════════════════════════════════════════════════════════════════════════════════
# VIX ANALYSIS - Volatility Regime Classification
# ═══════════════════════════════════════════════════════════════════════════════════════

def analyze_vix(
    vix_current: float,
    vix_on_high: float,
    vix_on_low: float
) -> Dict[str, Any]:
    """
    Analyze VIX to determine volatility regime and trading bias.
    
    VIX Zones:
    - EXTREME_LOW (0-12): Complacency, reversals likely
    - LOW (12-16): Calm, good for directional trades
    - NORMAL (16-20): Standard conditions
    - ELEVATED (20-25): Caution, wider stops needed
    - HIGH (25-35): Fear, premium expensive
    - EXTREME (35+): Panic, mean reversion plays
    
    Returns:
        Dictionary with zone, description, color, and positioning bias
    """
    # Find current zone
    zone_name = "NORMAL"
    zone_info = VIX_ZONES["NORMAL"]
    
    for name, info in VIX_ZONES.items():
        low, high = info["range"]
        if low <= vix_current < high:
            zone_name = name
            zone_info = info
            break
    
    # Calculate position within overnight range
    vix_range = vix_on_high - vix_on_low
    if vix_range > 0:
        position_pct = ((vix_current - vix_on_low) / vix_range) * 100
    else:
        position_pct = 50
    
    # Determine directional bias from VIX
    if vix_current > vix_on_high:
        bias = Direction.PUTS
        bias_reason = "VIX above O/N high - fear increasing"
    elif vix_current < vix_on_low:
        bias = Direction.CALLS
        bias_reason = "VIX below O/N low - complacency"
    elif position_pct > 70:
        bias = Direction.PUTS
        bias_reason = "VIX in upper range"
    elif position_pct < 30:
        bias = Direction.CALLS
        bias_reason = "VIX in lower range"
    else:
        bias = Direction.NEUTRAL
        bias_reason = "VIX neutral"
    
    return {
        "current": vix_current,
        "zone": zone_name,
        "zone_desc": zone_info["desc"],
        "zone_color": zone_info["color"],
        "zone_bias": zone_info["bias"],
        "on_high": vix_on_high,
        "on_low": vix_on_low,
        "position_pct": round(position_pct, 1),
        "bias": bias,
        "bias_reason": bias_reason
    }


# ═══════════════════════════════════════════════════════════════════════════════════════
# MA BIAS & MOMENTUM - Trend Direction Filters
# ═══════════════════════════════════════════════════════════════════════════════════════

def calculate_ma_bias(es_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Calculate Moving Average bias for trend direction.
    
    Uses 50 EMA vs 200 SMA on 30-min ES candles:
    - LONG: 50 EMA > 200 SMA (uptrend)
    - SHORT: 50 EMA < 200 SMA (downtrend)
    - NEUTRAL: Insufficient data or flat
    """
    if es_data is None or len(es_data) < 50:
        return {
            "signal": Direction.NEUTRAL,
            "ema_50": None,
            "sma_200": None,
            "diff_pct": 0,
            "score": 0,
            "reason": "Insufficient data"
        }
    
    close = es_data['Close']
    
    # Calculate MAs
    ema_50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    sma_200 = close.rolling(window=min(200, len(close))).mean().iloc[-1]
    
    # Calculate difference
    diff_pct = ((ema_50 - sma_200) / sma_200) * 100 if sma_200 > 0 else 0
    
    if ema_50 > sma_200:
        signal = Direction.CALLS
        score = min(30, int(abs(diff_pct) * 15))
        reason = f"Uptrend: 50 EMA ({ema_50:.2f}) > 200 SMA ({sma_200:.2f})"
    elif ema_50 < sma_200:
        signal = Direction.PUTS
        score = min(30, int(abs(diff_pct) * 15))
        reason = f"Downtrend: 50 EMA ({ema_50:.2f}) < 200 SMA ({sma_200:.2f})"
    else:
        signal = Direction.NEUTRAL
        score = 0
        reason = "MAs converged - no clear trend"
    
    return {
        "signal": signal,
        "ema_50": round(ema_50, 2),
        "sma_200": round(sma_200, 2),
        "diff_pct": round(diff_pct, 2),
        "score": score,
        "reason": reason
    }


def calculate_momentum(es_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Calculate momentum indicators (RSI + MACD) for entry timing.
    
    RSI Midline Reversion Strategy:
    - In uptrends: RSI oscillates 50-80, buy pullbacks to 50-60
    - In downtrends: RSI oscillates 20-50, sell bounces to 40-50
    
    MACD Histogram confirms momentum direction.
    """
    if es_data is None or len(es_data) < 26:
        return {
            "signal": Direction.NEUTRAL,
            "rsi": 50,
            "rsi_zone": "MID",
            "macd_hist": 0,
            "macd_direction": "FLAT",
            "score": 0,
            "reason": "Insufficient data"
        }
    
    close = es_data['Close']
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RSI Calculation (14-period)
    # ─────────────────────────────────────────────────────────────────────────────
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = round(rsi.iloc[-1], 1) if not pd.isna(rsi.iloc[-1]) else 50
    
    # RSI Zone
    if rsi_val > 80:
        rsi_zone = "OVERBOUGHT"
    elif rsi_val < 20:
        rsi_zone = "OVERSOLD"
    elif 50 <= rsi_val <= 60:
        rsi_zone = "PULLBACK"
    elif 40 <= rsi_val < 50:
        rsi_zone = "BOUNCE"
    elif rsi_val > 60:
        rsi_zone = "BULLISH"
    elif rsi_val < 40:
        rsi_zone = "BEARISH"
    else:
        rsi_zone = "MID"
    
    # ─────────────────────────────────────────────────────────────────────────────
    # MACD Calculation (12/26/9)
    # ─────────────────────────────────────────────────────────────────────────────
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    
    macd_hist = round(histogram.iloc[-1], 2)
    macd_direction = "GREEN" if macd_hist > 0 else "RED" if macd_hist < 0 else "FLAT"
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Combined Signal
    # ─────────────────────────────────────────────────────────────────────────────
    if rsi_val > 50 and macd_hist > 0:
        signal = Direction.CALLS
        score = 25
        reason = "Bullish: RSI > 50, MACD green"
    elif rsi_val < 50 and macd_hist < 0:
        signal = Direction.PUTS
        score = 25
        reason = "Bearish: RSI < 50, MACD red"
    elif rsi_zone == "OVERBOUGHT":
        signal = Direction.PUTS
        score = 15
        reason = "Overbought: RSI > 80"
    elif rsi_zone == "OVERSOLD":
        signal = Direction.CALLS
        score = 15
        reason = "Oversold: RSI < 20"
    else:
        signal = Direction.NEUTRAL
        score = 10
        reason = "Mixed momentum signals"
    
    return {
        "signal": signal,
        "rsi": rsi_val,
        "rsi_zone": rsi_zone,
        "macd_hist": macd_hist,
        "macd_direction": macd_direction,
        "score": score,
        "reason": reason
    }


# ═══════════════════════════════════════════════════════════════════════════════════════
# CONFIDENCE SCORING - Weighted Factor Analysis
# ═══════════════════════════════════════════════════════════════════════════════════════

def calculate_confidence(
    channel: Channel,
    pre_open_position: PreOpenPosition,
    setup_status: SetupStatus,
    trade_direction: Optional[Direction],
    flow_bias: Dict[str, Any],
    vix_analysis: Dict[str, Any],
    ma_bias: Dict[str, Any],
    momentum: Dict[str, Any],
    has_confluence: bool,
    targets: List[Dict]
) -> Dict[str, Any]:
    """
    Calculate overall trade confidence score based on multiple factors.
    
    FACTOR WEIGHTS (totaling 100%):
    ─────────────────────────────────────────────────────────────────────────────
    1. Channel Clarity (20%): Is the channel clearly RISING or FALLING?
    2. Setup Status (25%): Is the 8:30 setup VALID, INVALIDATED, or TREND?
    3. Flow Bias Alignment (20%): Does retail positioning align with our direction?
    4. VIX Regime (15%): Is VIX in a favorable zone?
    5. Trend Alignment (10%): Does MA bias support our direction?
    6. Confluence (10%): Do structure and cone lines align?
    
    CONFIDENCE LEVELS:
    - HIGH: 70-100 (Green light - execute with full size)
    - MEDIUM: 45-69 (Proceed with caution - reduce size)
    - LOW: 0-44 (Reconsider - wait for better setup)
    
    Returns:
        Dictionary with score, level, factors breakdown
    """
    factors = []
    total_score = 0
    
    # ─────────────────────────────────────────────────────────────────────────────
    # FACTOR 1: Channel Clarity (20 points max)
    # ─────────────────────────────────────────────────────────────────────────────
    if channel == Channel.RISING:
        channel_score = 20
        channel_note = "Clear RISING channel"
    elif channel == Channel.FALLING:
        channel_score = 20
        channel_note = "Clear FALLING channel"
    else:
        channel_score = 5
        channel_note = "Channel undetermined"
    
    total_score += channel_score
    factors.append(("Channel Clarity", channel_score, 20, channel_note))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # FACTOR 2: Setup Status (25 points max)
    # ─────────────────────────────────────────────────────────────────────────────
    if setup_status == SetupStatus.VALID:
        setup_score = 25
        setup_note = "8:30 candle VALIDATED setup"
    elif setup_status == SetupStatus.TREND_DAY:
        setup_score = 20
        setup_note = "Trend day - range trading mode"
    elif setup_status == SetupStatus.INVALIDATED:
        setup_score = 12
        setup_note = "Setup invalidated - alternate plan"
    else:
        setup_score = 8
        setup_note = "Awaiting 8:30 confirmation"
    
    total_score += setup_score
    factors.append(("Setup Status", setup_score, 25, setup_note))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # FACTOR 3: Flow Bias Alignment (20 points max)
    # ─────────────────────────────────────────────────────────────────────────────
    flow_direction = flow_bias.get("bias_direction", Direction.NEUTRAL)
    flow_score_raw = abs(flow_bias.get("score", 0))
    
    if trade_direction and flow_direction != Direction.NEUTRAL:
        # Check if flow aligns with trade direction
        if flow_direction == trade_direction:
            # Aligned - retail agrees with us (contrarian concern)
            flow_score = 10
            flow_note = f"Flow aligned - watch for MM reversal"
        else:
            # Opposite - retail disagrees (contrarian bullish)
            flow_score = 20
            flow_note = f"Contrarian setup - flow opposite our trade"
    elif flow_direction == Direction.NEUTRAL:
        flow_score = 15
        flow_note = "Neutral flow - no strong retail bias"
    else:
        flow_score = 12
        flow_note = "No trade direction to compare"
    
    total_score += flow_score
    factors.append(("Flow Bias", flow_score, 20, flow_note))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # FACTOR 4: VIX Regime (15 points max)
    # ─────────────────────────────────────────────────────────────────────────────
    vix_zone = vix_analysis.get("zone", "NORMAL")
    
    if vix_zone in ["LOW", "NORMAL"]:
        vix_score = 15
        vix_note = f"Favorable VIX zone ({vix_zone})"
    elif vix_zone == "ELEVATED":
        vix_score = 10
        vix_note = "Elevated VIX - wider stops needed"
    elif vix_zone in ["HIGH", "EXTREME"]:
        vix_score = 5
        vix_note = f"Caution: {vix_zone} VIX regime"
    else:  # EXTREME_LOW
        vix_score = 8
        vix_note = "Extreme low VIX - reversal risk"
    
    total_score += vix_score
    factors.append(("VIX Regime", vix_score, 15, vix_note))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # FACTOR 5: Trend Alignment (10 points max)
    # ─────────────────────────────────────────────────────────────────────────────
    ma_signal = ma_bias.get("signal", Direction.NEUTRAL)
    mom_signal = momentum.get("signal", Direction.NEUTRAL)
    
    if trade_direction:
        ma_aligned = ma_signal == trade_direction
        mom_aligned = mom_signal == trade_direction
        
        if ma_aligned and mom_aligned:
            trend_score = 10
            trend_note = "MA + Momentum aligned with trade"
        elif ma_aligned or mom_aligned:
            trend_score = 6
            trend_note = "Partial trend alignment"
        else:
            trend_score = 2
            trend_note = "Trading against trend"
    else:
        trend_score = 5
        trend_note = "No trade direction set"
    
    total_score += trend_score
    factors.append(("Trend Alignment", trend_score, 10, trend_note))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # FACTOR 6: Confluence (10 points max)
    # ─────────────────────────────────────────────────────────────────────────────
    if has_confluence:
        confluence_score = 10
        confluence_note = "Structure + Cone confluence detected"
    elif len(targets) >= 2:
        confluence_score = 6
        confluence_note = "Multiple targets available"
    elif len(targets) == 1:
        confluence_score = 4
        confluence_note = "Single target identified"
    else:
        confluence_score = 2
        confluence_note = "No clear targets"
    
    total_score += confluence_score
    factors.append(("Confluence", confluence_score, 10, confluence_note))
    
    # ─────────────────────────────────────────────────────────────────────────────
    # FINAL SCORING
    # ─────────────────────────────────────────────────────────────────────────────
    if total_score >= 70:
        level = "HIGH"
        recommendation = "Execute with full position size"
    elif total_score >= 45:
        level = "MEDIUM"
        recommendation = "Proceed with reduced size"
    else:
        level = "LOW"
        recommendation = "Wait for better setup"
    
    return {
        "score": total_score,
        "level": level,
        "recommendation": recommendation,
        "factors": factors,
        "max_score": 100
    }


# ═══════════════════════════════════════════════════════════════════════════════════════
# SIDEBAR - User Input Controls
# ═══════════════════════════════════════════════════════════════════════════════════════

def render_sidebar() -> Dict[str, Any]:
    """
    Render the sidebar with all user input controls.
    Organized into logical sections with auto-detect options.
    
    Returns:
        Dictionary of all input values
    """
    # Load saved inputs
    saved = load_inputs()
    
    with st.sidebar:
        # ─────────────────────────────────────────────────────────────────────────
        # HEADER
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("""
        <div style="text-align:center;padding:16px 0 24px 0;border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:20px;">
            <div style="font-family:'Outfit',sans-serif;font-size:22px;font-weight:700;
                        background:linear-gradient(135deg,#8b5cf6,#06b6d4);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                🔮 SPX PROPHET
            </div>
            <div style="font-size:10px;color:rgba(255,255,255,0.4);letter-spacing:2px;margin-top:4px;">
                VERSION 6.0 UNIFIED
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # TRADING DATE
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### 📅 Trading Date")
        trading_date = st.date_input(
            "Date",
            value=date.today(),
            label_visibility="collapsed"
        )
        
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # ES-SPX OFFSET
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### 📊 ES-SPX Offset")
        
        offset_mode = st.radio(
            "Offset Mode",
            options=["Auto-Calculate", "Manual Entry"],
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )
        
        manual_offset = None
        if offset_mode == "Manual Entry":
            manual_offset = st.number_input(
                "Manual Offset (ES - SPX)",
                value=float(saved.get("manual_offset", 18.0)),
                min_value=0.0,
                max_value=50.0,
                step=0.25,
                format="%.2f"
            )
        
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # SESSION LEVELS
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### 🌏 Session Levels")
        
        auto_session = st.checkbox(
            "Auto-detect from ES data",
            value=saved.get("auto_session", True),
            help="Automatically extract Sydney/Tokyo levels from ES candles"
        )
        
        sydney_high = sydney_low = tokyo_high = tokyo_low = None
        
        if not auto_session:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<span style='font-size:11px;color:rgba(255,255,255,0.5)'>SYDNEY</span>", unsafe_allow_html=True)
                sydney_high = st.number_input("Syd High", value=float(saved.get("sydney_high", 6070.0)), format="%.2f", label_visibility="collapsed")
                sydney_low = st.number_input("Syd Low", value=float(saved.get("sydney_low", 6050.0)), format="%.2f", label_visibility="collapsed")
            with col2:
                st.markdown("<span style='font-size:11px;color:rgba(255,255,255,0.5)'>TOKYO</span>", unsafe_allow_html=True)
                tokyo_high = st.number_input("Tok High", value=float(saved.get("tokyo_high", 6075.0)), format="%.2f", label_visibility="collapsed")
                tokyo_low = st.number_input("Tok Low", value=float(saved.get("tokyo_low", 6045.0)), format="%.2f", label_visibility="collapsed")
        
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # OVERNIGHT STRUCTURE
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### 🌙 Overnight Structure")
        
        auto_on = st.checkbox(
            "Auto-detect O/N High & Low",
            value=saved.get("auto_on", True),
            help="Automatically extract overnight high/low from ES data"
        )
        
        on_high_price = on_low_price = None
        on_high_time = on_low_time = None
        
        if not auto_on:
            on_high_price = st.number_input(
                "O/N High (ES)",
                value=float(saved.get("on_high_price", 6075.0)),
                format="%.2f"
            )
            on_low_price = st.number_input(
                "O/N Low (ES)",
                value=float(saved.get("on_low_price", 6045.0)),
                format="%.2f"
            )
            
            # Time inputs for anchor times
            col1, col2 = st.columns(2)
            with col1:
                on_high_hour = st.number_input("High Hour (CT)", value=int(saved.get("on_high_hour", 2)), min_value=0, max_value=23)
                on_high_min = st.number_input("High Min", value=int(saved.get("on_high_min", 30)), min_value=0, max_value=59)
            with col2:
                on_low_hour = st.number_input("Low Hour (CT)", value=int(saved.get("on_low_hour", 5)), min_value=0, max_value=23)
                on_low_min = st.number_input("Low Min", value=int(saved.get("on_low_min", 0)), min_value=0, max_value=59)
            
            # Build datetime objects
            prev_date = trading_date - timedelta(days=1)
            
            # Determine if time is before or after midnight
            if on_high_hour >= 17:
                on_high_time = CT.localize(datetime.combine(prev_date, time(on_high_hour, on_high_min)))
            else:
                on_high_time = CT.localize(datetime.combine(trading_date, time(on_high_hour, on_high_min)))
            
            if on_low_hour >= 17:
                on_low_time = CT.localize(datetime.combine(prev_date, time(on_low_hour, on_low_min)))
            else:
                on_low_time = CT.localize(datetime.combine(trading_date, time(on_low_hour, on_low_min)))
        
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # 8:30 CANDLE OVERRIDE
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### 📊 8:30 AM Candle")
        
        manual_candle_enabled = st.checkbox(
            "Manual entry (override auto)",
            value=saved.get("manual_candle_enabled", False),
            help="Enter 8:30 candle OHLC manually instead of auto-detecting"
        )
        
        manual_candle = None
        if manual_candle_enabled:
            col1, col2 = st.columns(2)
            with col1:
                candle_open = st.number_input("Open", value=float(saved.get("candle_open", 6060.0)), format="%.2f")
                candle_low = st.number_input("Low", value=float(saved.get("candle_low", 6055.0)), format="%.2f")
            with col2:
                candle_high = st.number_input("High", value=float(saved.get("candle_high", 6070.0)), format="%.2f")
                candle_close = st.number_input("Close", value=float(saved.get("candle_close", 6065.0)), format="%.2f")
            
            manual_candle = {
                "open": candle_open,
                "high": candle_high,
                "low": candle_low,
                "close": candle_close,
                "complete": True
            }
        
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # VIX DATA
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### ⚡ VIX Data")
        
        col1, col2 = st.columns(2)
        with col1:
            vix_on_high = st.number_input(
                "VIX O/N High",
                value=float(saved.get("vix_on_high", 18.0)),
                min_value=5.0,
                max_value=80.0,
                step=0.1,
                format="%.1f"
            )
        with col2:
            vix_on_low = st.number_input(
                "VIX O/N Low",
                value=float(saved.get("vix_on_low", 15.0)),
                min_value=5.0,
                max_value=80.0,
                step=0.1,
                format="%.1f"
            )
        
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # PRIOR DAY LEVELS (for Cone Rails)
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### 📐 Prior Day Levels")
        st.caption("For cone rail projections (ES prices)")
        
        prior_high = st.number_input(
            "Prior Day High",
            value=float(saved.get("prior_high", 6080.0)),
            format="%.2f"
        )
        prior_low = st.number_input(
            "Prior Day Low",
            value=float(saved.get("prior_low", 6040.0)),
            format="%.2f"
        )
        prior_close = st.number_input(
            "Prior Day Close",
            value=float(saved.get("prior_close", 6065.0)),
            format="%.2f"
        )
        
        # Prior day anchor times (simplified - use RTH close)
        prev_date = trading_date - timedelta(days=1)
        prior_close_time = CT.localize(datetime.combine(prev_date, time(15, 0)))
        prior_high_time = CT.localize(datetime.combine(prev_date, time(12, 0)))  # Approximate
        prior_low_time = CT.localize(datetime.combine(prev_date, time(10, 0)))   # Approximate
        
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # DISPLAY OPTIONS
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### ⚙️ Display Options")
        
        show_all_trades = st.checkbox(
            "Show all 4 structure lines",
            value=saved.get("show_all_trades", False)
        )
        
        show_debug = st.checkbox(
            "Show debug information",
            value=saved.get("show_debug", False)
        )
        
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # AUTO-REFRESH
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("##### 🔄 Auto-Refresh")
        
        auto_refresh = st.checkbox(
            "Enable auto-refresh",
            value=saved.get("auto_refresh", False)
        )
        
        refresh_seconds = 30
        if auto_refresh:
            refresh_seconds = st.slider(
                "Refresh interval (seconds)",
                min_value=10,
                max_value=120,
                value=int(saved.get("refresh_seconds", 30)),
                step=10
            )
        
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        
        # ─────────────────────────────────────────────────────────────────────────
        # SAVE BUTTON
        # ─────────────────────────────────────────────────────────────────────────
        if st.button("💾 Save Settings", use_container_width=True):
            inputs_to_save = {
                "manual_offset": manual_offset,
                "auto_session": auto_session,
                "sydney_high": sydney_high,
                "sydney_low": sydney_low,
                "tokyo_high": tokyo_high,
                "tokyo_low": tokyo_low,
                "auto_on": auto_on,
                "on_high_price": on_high_price,
                "on_low_price": on_low_price,
                "manual_candle_enabled": manual_candle_enabled,
                "vix_on_high": vix_on_high,
                "vix_on_low": vix_on_low,
                "prior_high": prior_high,
                "prior_low": prior_low,
                "prior_close": prior_close,
                "show_all_trades": show_all_trades,
                "show_debug": show_debug,
                "auto_refresh": auto_refresh,
                "refresh_seconds": refresh_seconds,
            }
            if manual_candle_enabled:
                inputs_to_save.update({
                    "candle_open": manual_candle["open"],
                    "candle_high": manual_candle["high"],
                    "candle_low": manual_candle["low"],
                    "candle_close": manual_candle["close"],
                })
            if not auto_on:
                inputs_to_save.update({
                    "on_high_hour": on_high_hour,
                    "on_high_min": on_high_min,
                    "on_low_hour": on_low_hour,
                    "on_low_min": on_low_min,
                })
            
            if save_inputs(inputs_to_save):
                st.success("✓ Saved!", icon="✅")
            else:
                st.error("Failed to save")
        
        # ─────────────────────────────────────────────────────────────────────────
        # FOOTER
        # ─────────────────────────────────────────────────────────────────────────
        st.markdown("""
        <div style="text-align:center;padding-top:20px;margin-top:20px;border-top:1px solid rgba(255,255,255,0.1);">
            <div style="font-size:10px;color:rgba(255,255,255,0.3);">
                SPX Prophet V6.0<br/>
                Built for 0DTE Excellence
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RETURN ALL INPUTS
    # ─────────────────────────────────────────────────────────────────────────────
    return {
        "trading_date": trading_date,
        "offset_mode": offset_mode,
        "manual_offset": manual_offset,
        "auto_session": auto_session,
        "sydney_high": sydney_high,
        "sydney_low": sydney_low,
        "tokyo_high": tokyo_high,
        "tokyo_low": tokyo_low,
        "auto_on": auto_on,
        "on_high_price": on_high_price,
        "on_low_price": on_low_price,
        "on_high_time": on_high_time,
        "on_low_time": on_low_time,
        "manual_candle": manual_candle,
        "vix_on_high": vix_on_high,
        "vix_on_low": vix_on_low,
        "prior_high": prior_high,
        "prior_low": prior_low,
        "prior_close": prior_close,
        "prior_high_time": prior_high_time,
        "prior_low_time": prior_low_time,
        "prior_close_time": prior_close_time,
        "show_all_trades": show_all_trades,
        "show_debug": show_debug,
        "auto_refresh": auto_refresh,
        "refresh_seconds": refresh_seconds,
    }


# ═══════════════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════════════

def main():
    """Main application entry point"""
    
    # Apply custom styles
    st.markdown(STYLES, unsafe_allow_html=True)
    
    # Render sidebar and get inputs
    inputs = render_sidebar()
    
    # Get current time
    now_ct = get_now_ct()
    trading_date = inputs["trading_date"]
    
    # Determine trading phase
    trading_phase = get_trading_phase(now_ct, trading_date)
    
    # Reference time for structure calculations (9:00 AM CT on trading date)
    reference_time = CT.localize(datetime.combine(trading_date, time(9, 0)))
    
    # Expiration time for options (3:00 PM CT)
    expiry_time = CT.localize(datetime.combine(trading_date, time(15, 0)))
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # DATA LOADING
    # ═══════════════════════════════════════════════════════════════════════════════
    
    with st.spinner("Loading market data..."):
        
        # ─────────────────────────────────────────────────────────────────────────
        # Fetch ES Data from Yahoo Finance
        # ─────────────────────────────────────────────────────────────────────────
        es_data = fetch_es_data(days=5)
        current_es = get_current_es_price(es_data) if es_data is not None else None
        
        # ─────────────────────────────────────────────────────────────────────────
        # Fetch SPX from Polygon
        # ─────────────────────────────────────────────────────────────────────────
        current_spx = fetch_spx_from_polygon()
        
        # ─────────────────────────────────────────────────────────────────────────
        # Calculate ES-SPX Offset
        # ─────────────────────────────────────────────────────────────────────────
        if inputs["offset_mode"] == "Auto-Calculate" and current_es and current_spx:
            offset = calculate_es_spx_offset(current_es, current_spx)
        elif inputs["manual_offset"]:
            offset = inputs["manual_offset"]
        else:
            offset = 18.0  # Default fallback
        
        # If we only have one price, calculate the other
        if not current_spx and current_es:
            current_spx = es_to_spx(current_es, offset)
        elif not current_es and current_spx:
            current_es = spx_to_es(current_spx, offset)
        
        # ─────────────────────────────────────────────────────────────────────────
        # Fetch VIX
        # ─────────────────────────────────────────────────────────────────────────
        vix_current = fetch_vix_from_polygon()
        if vix_current is None:
            vix_current = 16.0  # Default fallback
        
        # ─────────────────────────────────────────────────────────────────────────
        # Get Session Levels (Sydney, Tokyo, Overnight)
        # ─────────────────────────────────────────────────────────────────────────
        if inputs["auto_session"] and es_data is not None:
            sydney = get_session_levels(es_data, trading_date, "SYDNEY")
            tokyo = get_session_levels(es_data, trading_date, "TOKYO")
            overnight = get_session_levels(es_data, trading_date, "OVERNIGHT")
        else:
            # Manual session levels
            sydney = SessionLevels(
                high=inputs["sydney_high"],
                low=inputs["sydney_low"]
            )
            tokyo = SessionLevels(
                high=inputs["tokyo_high"],
                low=inputs["tokyo_low"]
            )
            overnight = SessionLevels()
        
        # ─────────────────────────────────────────────────────────────────────────
        # Get Overnight High/Low for Structure
        # ─────────────────────────────────────────────────────────────────────────
        if inputs["auto_on"] and overnight.high:
            on_high_es = overnight.high
            on_low_es = overnight.low
            on_high_time = overnight.high_time or CT.localize(datetime.combine(trading_date, time(2, 0)))
            on_low_time = overnight.low_time or CT.localize(datetime.combine(trading_date, time(5, 0)))
        else:
            on_high_es = inputs["on_high_price"] or 6075.0
            on_low_es = inputs["on_low_price"] or 6045.0
            on_high_time = inputs["on_high_time"] or CT.localize(datetime.combine(trading_date, time(2, 0)))
            on_low_time = inputs["on_low_time"] or CT.localize(datetime.combine(trading_date, time(5, 0)))
        
        # ─────────────────────────────────────────────────────────────────────────
        # Get 8:30 Candle
        # ─────────────────────────────────────────────────────────────────────────
        if inputs["manual_candle"]:
            candle_830 = inputs["manual_candle"]
        elif es_data is not None:
            candle_830 = get_830_candle(es_data, trading_date)
        else:
            candle_830 = {"open": None, "high": None, "low": None, "close": None, "complete": False}
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # VALIDATION - Ensure we have minimum required data
    # ═══════════════════════════════════════════════════════════════════════════════
    
    if not current_es and not current_spx:
        st.error("❌ Unable to fetch market data. Please check your connection or enter prices manually in the sidebar.")
        st.stop()
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # CORE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 1. Determine Channel (Rising or Falling)
    # ─────────────────────────────────────────────────────────────────────────────
    channel, channel_reason = determine_channel(sydney, tokyo)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 2. Calculate All Structure Lines (in SPX)
    # ─────────────────────────────────────────────────────────────────────────────
    on_high_spx = es_to_spx(on_high_es, offset)
    on_low_spx = es_to_spx(on_low_es, offset)
    
    all_structure_lines = calculate_structure_lines(
        on_high=on_high_spx,
        on_high_time=on_high_time,
        on_low=on_low_spx,
        on_low_time=on_low_time,
        reference_time=reference_time
    )
    
    # Get active ceiling and floor for the determined channel
    ceiling, floor = get_active_channel_edges(all_structure_lines, channel)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 3. Assess Pre-Open Position
    # ─────────────────────────────────────────────────────────────────────────────
    pre_open_position, position_distance, position_desc = assess_pre_open_position(
        current_price=current_spx,
        ceiling=ceiling,
        floor=floor
    )
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 4. Validate 8:30 Candle
    # ─────────────────────────────────────────────────────────────────────────────
    setup_status, setup_reason, trade_plan = validate_830_candle(
        candle=candle_830,
        pre_open_position=pre_open_position,
        ceiling=ceiling,
        floor=floor,
        offset=offset
    )
    
    # Extract trade direction from plan
    trade_direction = trade_plan.get("direction")
    entry_level_spx = trade_plan.get("entry_level_spx")
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 5. Calculate Cone Rails (Prior Day Projections)
    # ─────────────────────────────────────────────────────────────────────────────
    prior_high_spx = es_to_spx(inputs["prior_high"], offset)
    prior_low_spx = es_to_spx(inputs["prior_low"], offset)
    prior_close_spx = es_to_spx(inputs["prior_close"], offset)
    
    cones = calculate_cone_rails(
        prior_high=prior_high_spx,
        prior_high_time=inputs["prior_high_time"],
        prior_low=prior_low_spx,
        prior_low_time=inputs["prior_low_time"],
        prior_close=prior_close_spx,
        prior_close_time=inputs["prior_close_time"],
        reference_time=reference_time
    )
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 6. Find Targets
    # ─────────────────────────────────────────────────────────────────────────────
    if trade_direction and entry_level_spx:
        targets = find_targets(
            entry_level=entry_level_spx,
            direction=trade_direction,
            cones=cones,
            current_price=current_spx
        )
    else:
        targets = []
    
    # Check for confluence
    ceiling_confluence = check_confluence(ceiling.level, cones)
    floor_confluence = check_confluence(floor.level, cones)
    has_confluence = len(ceiling_confluence) > 0 or len(floor_confluence) > 0
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 7. Flow Bias Analysis
    # ─────────────────────────────────────────────────────────────────────────────
    flow_bias = calculate_flow_bias(
        current_price=current_spx,
        on_high=on_high_spx,
        on_low=on_low_spx,
        vix_current=vix_current,
        vix_on_high=inputs["vix_on_high"],
        vix_on_low=inputs["vix_on_low"],
        prior_close=prior_close_spx,
        es_data=es_data
    )
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 8. VIX Analysis
    # ─────────────────────────────────────────────────────────────────────────────
    vix_analysis = analyze_vix(
        vix_current=vix_current,
        vix_on_high=inputs["vix_on_high"],
        vix_on_low=inputs["vix_on_low"]
    )
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 9. MA Bias & Momentum
    # ─────────────────────────────────────────────────────────────────────────────
    ma_bias = calculate_ma_bias(es_data)
    momentum = calculate_momentum(es_data)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 10. Calculate Confidence Score
    # ─────────────────────────────────────────────────────────────────────────────
    confidence = calculate_confidence(
        channel=channel,
        pre_open_position=pre_open_position,
        setup_status=setup_status,
        trade_direction=trade_direction,
        flow_bias=flow_bias,
        vix_analysis=vix_analysis,
        ma_bias=ma_bias,
        momentum=momentum,
        has_confluence=has_confluence,
        targets=targets
    )
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 11. Calculate Option Prices (if we have a valid setup)
    # ─────────────────────────────────────────────────────────────────────────────
    option_estimates = None
    strike = None
    
    if trade_direction and entry_level_spx and targets:
        strike = select_strike(entry_level_spx, trade_direction)
        hours_to_expiry = max(0.1, (expiry_time - now_ct).total_seconds() / 3600)
        
        option_estimates = estimate_option_prices(
            current_spx=current_spx,
            entry_level=entry_level_spx,
            target_level=targets[0]["level"] if targets else entry_level_spx,
            strike=strike,
            direction=trade_direction,
            vix=vix_current,
            hours_to_expiry=hours_to_expiry
        )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # HERO HEADER
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Determine phase styling
    phase_class_map = {
        TradingPhase.PRE_MARKET: "phase-pre-market",
        TradingPhase.VALIDATING: "phase-validating",
        TradingPhase.ENTRY_WINDOW: "phase-entry-window",
        TradingPhase.SECONDARY_ENTRY: "phase-entry-window",
        TradingPhase.IN_TRADE: "phase-in-trade",
        TradingPhase.MARKET_CLOSED: "phase-closed"
    }
    phase_class = phase_class_map.get(trading_phase, "phase-pre-market")
    
    phase_text_map = {
        TradingPhase.PRE_MARKET: "📋 PRE-MARKET PLANNING",
        TradingPhase.VALIDATING: "⏳ VALIDATING 8:30 CANDLE",
        TradingPhase.ENTRY_WINDOW: "🎯 ENTRY WINDOW OPEN",
        TradingPhase.SECONDARY_ENTRY: "🎯 SECONDARY ENTRY",
        TradingPhase.IN_TRADE: "📈 TRADE ACTIVE",
        TradingPhase.MARKET_CLOSED: "🔒 MARKET CLOSED"
    }
    phase_text = phase_text_map.get(trading_phase, "PRE-MARKET")
    
    st.markdown(f'''
    <div class="hero-container">
        <div class="hero-grid">
            <!-- Left: Branding -->
            <div class="hero-left">
                <div class="hero-brand">🔮 SPX PROPHET</div>
                <div class="hero-version">VERSION 6.0 • UNIFIED SYSTEM</div>
                <div class="hero-offset-badge">
                    <span class="hero-offset-label">ES-SPX Offset</span>
                    <span class="hero-offset-value">{offset:+.2f}</span>
                </div>
            </div>
            
            <!-- Center: Price Display -->
            <div class="hero-center">
                <div class="hero-price-container">
                    <div class="hero-price">{current_spx:,.2f}</div>
                </div>
                <div class="hero-price-label">SPX Index</div>
                <div class="hero-es-price">ES Futures: <span>{current_es:,.2f}</span></div>
            </div>
            
            <!-- Right: Time & Phase -->
            <div class="hero-right">
                <div class="hero-time">
                    {now_ct.strftime("%I:%M:%S")}<span class="hero-timezone"> CT</span>
                </div>
                <div class="hero-date">{trading_date.strftime("%A, %B %d, %Y")}</div>
                <div class="phase-badge {phase_class}">{phase_text}</div>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # COMMAND CENTER
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Confidence color
    conf_color_map = {
        "HIGH": "confidence-high",
        "MEDIUM": "confidence-medium",
        "LOW": "confidence-low"
    }
    conf_color_class = conf_color_map.get(confidence["level"], "confidence-medium")
    
    st.markdown(f'''
    <div class="command-center">
        <!-- Header -->
        <div class="command-header">
            <div class="command-header-left">
                <div class="command-icon">🎯</div>
                <div>
                    <div class="command-title">Today's Trading Plan</div>
                    <div class="command-subtitle">{channel_reason}</div>
                </div>
            </div>
            <div class="confidence-display">
                <div class="confidence-label">Confidence</div>
                <div class="confidence-value {conf_color_class}">{confidence["score"]}%</div>
            </div>
        </div>
        
        <div class="command-body">
    ''', unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Channel Display
    # ─────────────────────────────────────────────────────────────────────────────
    
    # Channel styling
    if channel == Channel.RISING:
        channel_badge_class = "rising"
        channel_arrow = "↗"
        channel_arrow_class = "rising"
    elif channel == Channel.FALLING:
        channel_badge_class = "falling"
        channel_arrow = "↘"
        channel_arrow_class = "falling"
    else:
        channel_badge_class = "undetermined"
        channel_arrow = "↔"
        channel_arrow_class = ""
    
    channel_width = ceiling.level - floor.level
    
    st.markdown(f'''
        <!-- Channel Visual -->
        <div class="channel-container">
            <div class="channel-visual">
                <!-- Ceiling -->
                <div class="channel-edge ceiling">
                    <div class="channel-edge-name">{ceiling.name}</div>
                    <div class="channel-edge-price bullish">{ceiling.level:,.2f}</div>
                    <div class="channel-edge-es">ES: {spx_to_es(ceiling.level, offset):,.2f}</div>
                </div>
                
                <!-- Middle -->
                <div class="channel-middle">
                    <div class="channel-type-badge {channel_badge_class}">{channel.value}</div>
                    <div class="channel-arrow {channel_arrow_class}">{channel_arrow}</div>
                    <div class="channel-width">Width: {channel_width:.1f} pts</div>
                </div>
                
                <!-- Floor -->
                <div class="channel-edge floor">
                    <div class="channel-edge-name">{floor.name}</div>
                    <div class="channel-edge-price bearish">{floor.level:,.2f}</div>
                    <div class="channel-edge-es">ES: {spx_to_es(floor.level, offset):,.2f}</div>
                </div>
            </div>
        </div>
    ''', unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Position Indicator
    # ─────────────────────────────────────────────────────────────────────────────
    
    position_class_map = {
        PreOpenPosition.ABOVE: "above",
        PreOpenPosition.BELOW: "below",
        PreOpenPosition.INSIDE: "inside"
    }
    position_class = position_class_map.get(pre_open_position, "inside")
    
    st.markdown(f'''
        <!-- Position Indicator -->
        <div class="position-indicator {position_class}">
            <span class="position-label">Pre-Open Position</span>
            <span class="position-value {position_class}">{position_desc}</span>
        </div>
    ''', unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # 8:30 Candle Display
    # ─────────────────────────────────────────────────────────────────────────────
    
    # Candle status
    if candle_830.get("complete"):
        candle_status_class = "complete"
        candle_status_text = "✓ Complete"
    elif candle_830.get("open"):
        candle_status_class = "forming"
        candle_status_text = "◉ Forming"
    else:
        candle_status_class = "awaiting"
        candle_status_text = "○ Awaiting"
    
    # Candle values
    c_open = f"{candle_830['open']:.2f}" if candle_830.get("open") else "—"
    c_high = f"{candle_830['high']:.2f}" if candle_830.get("high") else "—"
    c_low = f"{candle_830['low']:.2f}" if candle_830.get("low") else "—"
    c_close = f"{candle_830['close']:.2f}" if candle_830.get("close") else "—"
    
    st.markdown(f'''
        <!-- 8:30 Candle -->
        <div class="candle-830-container">
            <div class="candle-830-header">
                <span class="candle-830-title">📊 8:30 AM Candle (ES)</span>
                <span class="candle-830-status {candle_status_class}">{candle_status_text}</span>
            </div>
            <div class="candle-830-grid">
                <div class="candle-830-item">
                    <div class="candle-830-item-label">Open</div>
                    <div class="candle-830-item-value">{c_open}</div>
                </div>
                <div class="candle-830-item">
                    <div class="candle-830-item-label">High</div>
                    <div class="candle-830-item-value high">{c_high}</div>
                </div>
                <div class="candle-830-item">
                    <div class="candle-830-item-label">Low</div>
                    <div class="candle-830-item-value low">{c_low}</div>
                </div>
                <div class="candle-830-item">
                    <div class="candle-830-item-label">Close</div>
                    <div class="candle-830-item-value">{c_close}</div>
                </div>
            </div>
        </div>
    ''', unsafe_allow_html=True)



# ═══════════════════════════════════════════════════════════════════════════════
    # TRADE SETUP / SCENARIO DISPLAY
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # ─────────────────────────────────────────────────────────────────────────────
    # TREND DAY MODE
    # ─────────────────────────────────────────────────────────────────────────────
    if setup_status == SetupStatus.TREND_DAY:
        buy_strike = select_strike(floor.level, Direction.CALLS)
        sell_strike = select_strike(ceiling.level, Direction.PUTS)
        
        st.markdown(f'''
            <!-- Trend Day Banner -->
            <div class="trend-day-banner">
                <div class="trend-day-icon">📊</div>
                <div class="trend-day-title">TREND DAY DETECTED</div>
                <div class="trend-day-description">
                    8:30 candle touched edge and closed inside channel — Trade the range, edge to edge
                </div>
            </div>
            
            <!-- Trend Day Trades -->
            <div class="trend-trades-grid">
                <div class="trend-trade-card buy">
                    <div class="trend-trade-label">Buy at Floor</div>
                    <div class="trend-trade-level">{floor.level:,.2f}</div>
                    <div class="trend-trade-target">Target: {ceiling.level:,.2f}</div>
                    <div class="trend-trade-strike">CALLS • {buy_strike} Strike</div>
                </div>
                <div class="trend-trade-card sell">
                    <div class="trend-trade-label">Sell at Ceiling</div>
                    <div class="trend-trade-level">{ceiling.level:,.2f}</div>
                    <div class="trend-trade-target">Target: {floor.level:,.2f}</div>
                    <div class="trend-trade-strike">PUTS • {sell_strike} Strike</div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # VALID SETUP - Show Primary Trade
    # ─────────────────────────────────────────────────────────────────────────────
    elif setup_status == SetupStatus.VALID and trade_direction:
        direction_class = "calls" if trade_direction == Direction.CALLS else "puts"
        direction_text = "CALLS" if trade_direction == Direction.CALLS else "PUTS"
        
        # Option price estimates
        entry_price = option_estimates["entry_price"] if option_estimates else 0
        target_price = option_estimates["target_price"] if option_estimates else 0
        profit_pct = option_estimates["profit_pct"] if option_estimates else 0
        
        # Distance from current
        dist_from_current = current_spx - entry_level_spx if entry_level_spx else 0
        
        st.markdown(f'''
            <!-- Valid Trade Setup -->
            <div class="trade-setup-card {direction_class}">
                <div class="trade-setup-header">
                    <div class="trade-direction-container">
                        <div class="trade-direction-badge {direction_class}">{direction_text}</div>
                        <div class="trade-setup-reason">{setup_reason}</div>
                    </div>
                    <div class="trade-entry-window">
                        <div class="trade-entry-window-label">Entry Window</div>
                        <div class="trade-entry-window-value">{trade_plan.get("entry_window", "9:00-9:10 AM CT")}</div>
                    </div>
                </div>
                
                <!-- Trade Metrics -->
                <div class="trade-metrics-grid">
                    <div class="trade-metric">
                        <div class="trade-metric-label">Entry Level</div>
                        <div class="trade-metric-value highlight">{entry_level_spx:,.2f}</div>
                        <div class="trade-metric-subtitle">SPX</div>
                    </div>
                    <div class="trade-metric">
                        <div class="trade-metric-label">Strike</div>
                        <div class="trade-metric-value">{strike}</div>
                        <div class="trade-metric-subtitle">{direction_text[:-1]}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="trade-metric-label">Est. Entry</div>
                        <div class="trade-metric-value">${entry_price:.2f}</div>
                        <div class="trade-metric-subtitle">Per Contract</div>
                    </div>
                    <div class="trade-metric">
                        <div class="trade-metric-label">Distance</div>
                        <div class="trade-metric-value {"bullish" if dist_from_current > 0 else "bearish"}">{dist_from_current:+.1f}</div>
                        <div class="trade-metric-subtitle">From Current</div>
                    </div>
                </div>
        ''', unsafe_allow_html=True)
        
        # Targets Section
        if targets:
            st.markdown('''
                <!-- Targets -->
                <div class="targets-section">
                    <div class="targets-header">
                        <span class="targets-title">🎯 Profit Targets (Cone Rails)</span>
                        <span class="targets-subtitle">Closest target is primary</span>
                    </div>
            ''', unsafe_allow_html=True)
            
            for i, target in enumerate(targets[:4]):
                is_primary = target.get("primary", False)
                primary_class = "primary" if is_primary else ""
                
                # Estimate profit at this target
                if option_estimates:
                    tgt_est = estimate_option_prices(
                        current_spx=current_spx,
                        entry_level=entry_level_spx,
                        target_level=target["level"],
                        strike=strike,
                        direction=trade_direction,
                        vix=vix_current,
                        hours_to_expiry=max(0.1, (expiry_time - now_ct).total_seconds() / 3600)
                    )
                    tgt_profit = f"+{tgt_est['profit_pct']:.0f}%"
                else:
                    tgt_profit = "—"
                
                st.markdown(f'''
                    <div class="target-row {primary_class}">
                        <div class="target-info">
                            <div class="target-rank">{i + 1}</div>
                            <div class="target-name">{target["name"]}{"  ★ PRIMARY" if is_primary else ""}</div>
                        </div>
                        <div class="target-data">
                            <span class="target-price">{target["level"]:,.2f}</span>
                            <span class="target-distance">{target["distance"]:.0f} pts</span>
                            <span class="target-profit">{tgt_profit}</span>
                        </div>
                    </div>
                ''', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # INVALIDATED - Show Alternate Plan
    # ─────────────────────────────────────────────────────────────────────────────
    elif setup_status == SetupStatus.INVALIDATED and trade_direction:
        direction_class = "calls" if trade_direction == Direction.CALLS else "puts"
        direction_text = "CALLS" if trade_direction == Direction.CALLS else "PUTS"
        
        st.markdown(f'''
            <!-- Invalidated Setup -->
            <div class="scenario-card invalid" style="margin-top:20px;">
                <div class="scenario-header">
                    <div class="scenario-icon">⚠️</div>
                    <div>
                        <div class="scenario-title">Setup Invalidated — Alternate Plan Active</div>
                        <div class="scenario-condition">{setup_reason}</div>
                    </div>
                </div>
                <div class="scenario-details">
                    <div class="scenario-detail-item">
                        <span class="scenario-detail-label">New Entry Edge</span>
                        <span class="scenario-detail-value">{trade_plan.get("entry_edge", "").upper()}</span>
                    </div>
                    <div class="scenario-detail-item">
                        <span class="scenario-detail-label">Entry Level</span>
                        <span class="scenario-detail-value">{entry_level_spx:,.2f}</span>
                    </div>
                    <div class="scenario-detail-item">
                        <span class="scenario-detail-label">Direction</span>
                        <span class="scenario-detail-value {direction_class.rstrip('s')}">{direction_text}</span>
                    </div>
                    <div class="scenario-detail-item">
                        <span class="scenario-detail-label">Strike</span>
                        <span class="scenario-detail-value">{select_strike(entry_level_spx, trade_direction)}</span>
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # AWAITING 8:30 - Show Scenario Planning
    # ─────────────────────────────────────────────────────────────────────────────
    elif setup_status == SetupStatus.AWAITING_830:
        st.markdown(f'''
            <div style="text-align:center;padding:24px;color:var(--text-secondary);">
                <div style="font-size:32px;margin-bottom:12px;">⏳</div>
                <div style="font-size:14px;font-weight:500;">Waiting for 8:30 AM Candle</div>
                <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">
                    Setup will be validated when candle completes at 9:00 AM CT
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        # Show both scenarios
        if pre_open_position == PreOpenPosition.BELOW:
            valid_dir = "PUTS"
            valid_entry = floor.level
            invalid_entry = ceiling.level
            valid_cond = f"8:30 touches Floor ({floor.level:.2f}) and closes below"
            invalid_cond = f"8:30 closes above Floor → Rally to Ceiling"
        elif pre_open_position == PreOpenPosition.ABOVE:
            valid_dir = "CALLS"
            valid_entry = ceiling.level
            invalid_entry = floor.level
            valid_cond = f"8:30 touches Ceiling ({ceiling.level:.2f}) and closes above"
            invalid_cond = f"8:30 closes below Ceiling → Drop to Floor"
        else:
            valid_dir = "TBD"
            valid_entry = current_spx
            invalid_entry = current_spx
            valid_cond = "8:30 breaks above Ceiling"
            invalid_cond = "8:30 breaks below Floor"
        
        valid_strike = select_strike(valid_entry, Direction.PUTS if valid_dir == "PUTS" else Direction.CALLS)
        invalid_strike = select_strike(invalid_entry, Direction.PUTS if valid_dir == "PUTS" else Direction.CALLS)
        
        st.markdown(f'''
            <div class="scenarios-container">
                <!-- Valid Scenario -->
                <div class="scenario-card valid">
                    <div class="scenario-header">
                        <div class="scenario-icon">✓</div>
                        <div>
                            <div class="scenario-title">IF Valid: {valid_dir} at Entry</div>
                            <div class="scenario-condition">{valid_cond}</div>
                        </div>
                    </div>
                    <div class="scenario-details">
                        <div class="scenario-detail-item">
                            <span class="scenario-detail-label">Entry</span>
                            <span class="scenario-detail-value">{valid_entry:,.2f}</span>
                        </div>
                        <div class="scenario-detail-item">
                            <span class="scenario-detail-label">Strike</span>
                            <span class="scenario-detail-value {valid_dir.lower()}">{valid_strike} {valid_dir[:-1]}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Invalid Scenario -->
                <div class="scenario-card invalid">
                    <div class="scenario-header">
                        <div class="scenario-icon">✗</div>
                        <div>
                            <div class="scenario-title">IF Invalidated: Wait for Alternate</div>
                            <div class="scenario-condition">{invalid_cond}</div>
                        </div>
                    </div>
                    <div class="scenario-details">
                        <div class="scenario-detail-item">
                            <span class="scenario-detail-label">Wait For</span>
                            <span class="scenario-detail-value">{invalid_entry:,.2f}</span>
                        </div>
                        <div class="scenario-detail-item">
                            <span class="scenario-detail-label">Strike</span>
                            <span class="scenario-detail-value">{invalid_strike}</span>
                        </div>
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # CONFIDENCE BREAKDOWN
    # ─────────────────────────────────────────────────────────────────────────────
    
    conf_fill_class = conf_color_class.replace("confidence-", "")
    
    st.markdown(f'''
        <!-- Confidence Section -->
        <div class="confidence-section">
            <div class="confidence-header">
                <span class="confidence-title">📊 Confidence Breakdown</span>
                <span class="confidence-score-large {conf_color_class}">{confidence["score"]}%</span>
            </div>
            
            <div class="confidence-bar-container">
                <div class="confidence-bar">
                    <div class="confidence-bar-fill {conf_fill_class}" style="width:{confidence["score"]}%"></div>
                </div>
                <div class="confidence-bar-markers">
                    <span>0</span>
                    <span>LOW</span>
                    <span>45</span>
                    <span>MEDIUM</span>
                    <span>70</span>
                    <span>HIGH</span>
                    <span>100</span>
                </div>
            </div>
            
            <div class="confidence-factors-grid">
    ''', unsafe_allow_html=True)
    
    for factor_name, score, max_score, note in confidence["factors"]:
        if score >= max_score * 0.7:
            factor_class = "positive"
        elif score >= max_score * 0.4:
            factor_class = "neutral"
        else:
            factor_class = "negative"
        
        st.markdown(f'''
            <div class="confidence-factor">
                <span class="confidence-factor-name">{factor_name}</span>
                <span class="confidence-factor-value {factor_class}">+{score}/{max_score}</span>
            </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('''
            </div>
        </div>
    ''', unsafe_allow_html=True)
    
    # Close command center body and container
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SUPPORTING ANALYSIS CARDS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown("### 📈 Market Analysis")
    
    # Flow Bias color
    flow_score = flow_bias["score"]
    if flow_score >= 30:
        flow_color = "var(--green-400)"
        flow_badge_class = "bullish"
    elif flow_score <= -30:
        flow_color = "var(--red-400)"
        flow_badge_class = "bearish"
    else:
        flow_color = "var(--text-secondary)"
        flow_badge_class = "neutral"
    
    flow_meter_pos = (flow_score + 100) / 2  # Convert -100 to 100 → 0 to 100
    
    # VIX color
    vix_color = vix_analysis["zone_color"]
    vix_badge = vix_analysis["zone_bias"]
    vix_badge_class = "bullish" if vix_badge in ["BULLISH"] else "bearish" if vix_badge in ["BEARISH", "REVERSAL"] else "neutral"
    
    # Momentum
    mom_signal = momentum["signal"]
    mom_badge_class = "bullish" if mom_signal == Direction.CALLS else "bearish" if mom_signal == Direction.PUTS else "neutral"
    mom_badge_text = "BULLISH" if mom_signal == Direction.CALLS else "BEARISH" if mom_signal == Direction.PUTS else "NEUTRAL"
    
    ma_signal = ma_bias["signal"]
    ma_badge_class = "bullish" if ma_signal == Direction.CALLS else "bearish" if ma_signal == Direction.PUTS else "neutral"
    ma_badge_text = "LONG" if ma_signal == Direction.CALLS else "SHORT" if ma_signal == Direction.PUTS else "NEUTRAL"
    
    st.markdown(f'''
    <div class="analysis-grid">
        <!-- Flow Bias Card -->
        <div class="analysis-card flow">
            <div class="analysis-card-header">
                <div class="analysis-card-icon">🌊</div>
                <div>
                    <div class="analysis-card-title">Flow Bias</div>
                    <div class="analysis-card-subtitle">Retail Positioning</div>
                </div>
            </div>
            <div class="analysis-value" style="color:{flow_color}">{flow_score:+d}</div>
            <div class="analysis-badge {flow_badge_class}">{flow_bias["bias"].replace("_", " ")}</div>
            
            <div class="flow-meter-container">
                <div class="flow-meter">
                    <div class="flow-meter-marker" style="left:{flow_meter_pos}%"></div>
                </div>
                <div class="flow-meter-labels">
                    <span>Heavy Puts</span>
                    <span>Neutral</span>
                    <span>Heavy Calls</span>
                </div>
            </div>
            
            <div class="analysis-details">
                <div class="analysis-detail-row">
                    <span class="analysis-detail-label">MM Play</span>
                    <span class="analysis-detail-value" style="font-size:10px;max-width:150px;text-align:right;">{flow_bias["mm_play"][:50]}...</span>
                </div>
            </div>
        </div>
        
        <!-- VIX Card -->
        <div class="analysis-card vix">
            <div class="analysis-card-header">
                <div class="analysis-card-icon">⚡</div>
                <div>
                    <div class="analysis-card-title">VIX Analysis</div>
                    <div class="analysis-card-subtitle">{vix_analysis["zone"]} Zone</div>
                </div>
            </div>
            <div class="analysis-value" style="color:{vix_color}">{vix_current:.2f}</div>
            <div class="analysis-badge {vix_badge_class}">{vix_badge}</div>
            
            <div class="analysis-details">
                <div class="analysis-detail-row">
                    <span class="analysis-detail-label">O/N Range</span>
                    <span class="analysis-detail-value">{inputs["vix_on_low"]:.1f} - {inputs["vix_on_high"]:.1f}</span>
                </div>
                <div class="analysis-detail-row">
                    <span class="analysis-detail-label">Position</span>
                    <span class="analysis-detail-value">{vix_analysis["position_pct"]:.0f}%</span>
                </div>
                <div class="analysis-detail-row">
                    <span class="analysis-detail-label">Regime</span>
                    <span class="analysis-detail-value">{vix_analysis["zone_desc"][:25]}</span>
                </div>
            </div>
        </div>
        
        <!-- Momentum Card -->
        <div class="analysis-card momentum">
            <div class="analysis-card-header">
                <div class="analysis-card-icon">📊</div>
                <div>
                    <div class="analysis-card-title">Trend & Momentum</div>
                    <div class="analysis-card-subtitle">MA + RSI/MACD</div>
                </div>
            </div>
            <div style="display:flex;gap:12px;margin-bottom:12px;">
                <div class="analysis-badge {ma_badge_class}">{ma_badge_text}</div>
                <div class="analysis-badge {mom_badge_class}">{mom_badge_text}</div>
            </div>
            
            <div class="analysis-details">
                <div class="analysis-detail-row">
                    <span class="analysis-detail-label">RSI (14)</span>
                    <span class="analysis-detail-value" style="color:{"var(--green-400)" if momentum["rsi"] > 50 else "var(--red-400)"}">{momentum["rsi"]:.1f}</span>
                </div>
                <div class="analysis-detail-row">
                    <span class="analysis-detail-label">MACD Hist</span>
                    <span class="analysis-detail-value" style="color:{"var(--green-400)" if momentum["macd_hist"] > 0 else "var(--red-400)"}">{momentum["macd_hist"]:+.2f}</span>
                </div>
                <div class="analysis-detail-row">
                    <span class="analysis-detail-label">50 EMA</span>
                    <span class="analysis-detail-value">{ma_bias["ema_50"] or "—"}</span>
                </div>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # EXPANDABLE SECTIONS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Session Levels
    with st.expander("🌏 Session Levels", expanded=False):
        st.markdown(f'''
        <div class="session-table-container">
            <table class="session-table">
                <thead>
                    <tr>
                        <th>Session</th>
                        <th>High (ES)</th>
                        <th>High (SPX)</th>
                        <th>Low (ES)</th>
                        <th>Low (SPX)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="session-name">Sydney</td>
                        <td class="value-high">{sydney.high or "—"}</td>
                        <td class="value-high">{es_to_spx(sydney.high, offset) if sydney.high else "—"}</td>
                        <td class="value-low">{sydney.low or "—"}</td>
                        <td class="value-low">{es_to_spx(sydney.low, offset) if sydney.low else "—"}</td>
                    </tr>
                    <tr>
                        <td class="session-name">Tokyo</td>
                        <td class="value-high">{tokyo.high or "—"}</td>
                        <td class="value-high">{es_to_spx(tokyo.high, offset) if tokyo.high else "—"}</td>
                        <td class="value-low">{tokyo.low or "—"}</td>
                        <td class="value-low">{es_to_spx(tokyo.low, offset) if tokyo.low else "—"}</td>
                    </tr>
                    <tr class="highlight-row">
                        <td class="session-name"><strong>Overnight</strong></td>
                        <td class="value-high"><strong>{on_high_es}</strong></td>
                        <td class="value-high"><strong>{on_high_spx}</strong></td>
                        <td class="value-low"><strong>{on_low_es}</strong></td>
                        <td class="value-low"><strong>{on_low_spx}</strong></td>
                    </tr>
                </tbody>
            </table>
        </div>
        ''', unsafe_allow_html=True)
    
    # Cone Rails
    with st.expander("📐 Cone Rails (Prior Day Projections)", expanded=False):
        st.markdown('<div class="cones-container"><div class="cones-grid">', unsafe_allow_html=True)
        
        for cone_name, cone in cones.items():
            st.markdown(f'''
            <div class="cone-card">
                <div class="cone-card-name">{cone_name}</div>
                <div class="cone-card-anchor"><span>Anchor:</span> {cone.anchor:,.2f}</div>
                <div class="cone-card-levels">
                    <div class="cone-level asc">
                        <div class="cone-level-label">↗ Asc</div>
                        <div class="cone-level-value">{cone.ascending:,.2f}</div>
                    </div>
                    <div class="cone-level desc">
                        <div class="cone-level-label">↘ Desc</div>
                        <div class="cone-level-value">{cone.descending:,.2f}</div>
                    </div>
                </div>
                <div class="cone-card-meta">
                    <span>{cone.blocks}</span> blocks • ±<span>{cone.expansion:.1f}</span> pts
                </div>
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown('</div></div>', unsafe_allow_html=True)
    
    # All 4 Structure Lines
    if inputs["show_all_trades"]:
        with st.expander("📊 All Structure Lines", expanded=False):
            st.markdown('<div class="all-trades-container"><div class="all-trades-grid">', unsafe_allow_html=True)
            
            for line_key, line in all_structure_lines.items():
                # Check if this line is active
                is_active = (line_key in ["ceiling_rising", "floor_rising"] and channel == Channel.RISING) or \
                           (line_key in ["ceiling_falling", "floor_falling"] and channel == Channel.FALLING)
                active_class = "active" if is_active else ""
                
                # Entry type
                entry_type = "CALLS" if line.entry_type == Direction.CALLS else "PUTS"
                entry_class = "calls" if entry_type == "CALLS" else "puts"
                
                # Distance from current
                distance = current_spx - line.level
                dist_class = "above" if distance > 0 else "below"
                
                st.markdown(f'''
                <div class="structure-line-card {active_class}">
                    <div class="structure-line-header">
                        <span class="structure-line-name">{line.name}</span>
                        <span class="structure-line-type {entry_class}">{entry_type}</span>
                    </div>
                    <div class="structure-line-level">{line.level:,.2f}</div>
                    <div class="structure-line-distance {dist_class}">{distance:+.1f} pts from current</div>
                    <div class="structure-line-meta">
                        <span>Anchor: <span class="structure-line-meta-value">{line.anchor:,.2f}</span></span>
                        <span>Blocks: <span class="structure-line-meta-value">{line.blocks}</span></span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            
            st.markdown('</div></div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # DEBUG SECTION
    # ═══════════════════════════════════════════════════════════════════════════════
    
    if inputs["show_debug"]:
        with st.expander("🔧 Debug Information", expanded=True):
            st.markdown('<div class="debug-container">', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**⏱️ Timing**")
                st.write(f"Current Time: {now_ct.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                st.write(f"Reference Time: {reference_time.strftime('%H:%M:%S %Z')}")
                st.write(f"Trading Phase: {trading_phase.value}")
                st.write(f"Hours to Expiry: {max(0, (expiry_time - now_ct).total_seconds() / 3600):.2f}")
            
            with col2:
                st.markdown("**📊 Prices & Offset**")
                st.write(f"ES Price: {current_es}")
                st.write(f"SPX Price: {current_spx}")
                st.write(f"Offset: {offset}")
                st.write(f"VIX: {vix_current}")
            
            with col3:
                st.markdown("**🎯 Setup**")
                st.write(f"Channel: {channel.value}")
                st.write(f"Position: {pre_open_position.value}")
                st.write(f"Status: {setup_status.value}")
                st.write(f"Direction: {trade_direction.value if trade_direction else 'None'}")
            
            st.markdown("**📋 8:30 Candle**")
            st.json(candle_830)
            
            st.markdown("**📋 Trade Plan**")
            st.json(trade_plan)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════════════
    
    st.markdown(f'''
    <div class="app-footer">
        <div class="footer-brand">
            <span>🔮 SPX PROPHET</span> V6.0 — Unified Institutional Trading System
        </div>
        <div class="footer-meta">
            Slope: {SLOPE}<span>•</span>
            Threshold: {CHANNEL_BREAK_THRESHOLD} pts<span>•</span>
            {now_ct.strftime("%I:%M:%S %p CT")}
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # AUTO-REFRESH
    # ═══════════════════════════════════════════════════════════════════════════════
    
    if inputs["auto_refresh"]:
        time_module.sleep(inputs["refresh_seconds"])
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
