# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V5.2 - Institutional 0DTE Trading Analytics
# ALL 4 TRADES | Polygon Options Pricing | Entry/Exit Price Predictions
# ═══════════════════════════════════════════════════════════════════════════════

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
from typing import Dict, List, Optional, Tuple
# ═══════════════════════════════════════════════════════════════════════════════
# NORMAL DISTRIBUTION FUNCTIONS (replacing scipy.stats.norm)
# ═══════════════════════════════════════════════════════════════════════════════

def norm_cdf(x):
    """Cumulative distribution function for standard normal distribution"""
    # Approximation using error function
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def norm_pdf(x):
    """Probability density function for standard normal distribution"""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="SPX Prophet V5.2", page_icon="🔮", layout="wide", initial_sidebar_state="expanded")

CT = pytz.timezone("America/Chicago")
SLOPE = 0.48
GAP_THRESHOLD = 6.0
CONFLUENCE_THRESHOLD = 5.0
SAVE_FILE = "spx_prophet_v5_inputs.json"

# Polygon API
POLYGON_KEY = "DCWuTS1R_fukpfjgf7QnXrLTEOS_giq6"
POLYGON_BASE = "https://api.polygon.io"

VIX_ZONES = {
    "EXTREME_LOW": (0, 12), "LOW": (12, 16), "NORMAL": (16, 20),
    "ELEVATED": (20, 25), "HIGH": (25, 35), "EXTREME": (35, 100)
}

# ═══════════════════════════════════════════════════════════════════════════════
# CSS STYLES
# ═══════════════════════════════════════════════════════════════════════════════

STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&family=Geist+Sans:wght@300;400;500;600;700&display=swap');

:root {
    /* Color System - Institutional Grade */
    --bg-primary: #0B0D17;
    --bg-secondary: #0F111B;
    --bg-tertiary: #13151F;
    --bg-card: linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%);
    --bg-card-hover: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
    --border-primary: rgba(255,255,255,0.06);
    --border-secondary: rgba(255,255,255,0.03);
    --border-accent: rgba(168,85,247,0.2);
    
    /* Typography */
    --text-primary: #FFFFFF;
    --text-secondary: rgba(255,255,255,0.7);
    --text-tertiary: rgba(255,255,255,0.5);
    --text-quaternary: rgba(255,255,255,0.3);
    
    /* Semantic Colors */
    --success: #00F5A0;
    --success-bg: rgba(0,245,160,0.1);
    --success-border: rgba(0,245,160,0.2);
    
    --danger: #FF4B6A;
    --danger-bg: rgba(255,75,106,0.1);
    --danger-border: rgba(255,75,106,0.2);
    
    --warning: #FFB800;
    --warning-bg: rgba(255,184,0,0.1);
    --warning-border: rgba(255,184,0,0.2);
    
    --info: #00D9FF;
    --info-bg: rgba(0,217,255,0.1);
    --info-border: rgba(0,217,255,0.2);
    
    --purple: #8B5CF6;
    --purple-bg: rgba(139,92,246,0.1);
    --purple-border: rgba(139,92,246,0.2);
    
    /* Shadows & Effects */
    --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.15);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.2), 0 2px 4px -1px rgba(0,0,0,0.1);
    --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.25), 0 4px 6px -2px rgba(0,0,0,0.1);
    --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.3), 0 10px 10px -5px rgba(0,0,0,0.1);
    --glow-primary: 0 0 20px rgba(139,92,246,0.15);
    --glow-success: 0 0 20px rgba(0,245,160,0.15);
    --glow-danger: 0 0 20px rgba(255,75,106,0.15);
}

/* Base Application Styling */
.stApp {
    background: radial-gradient(circle at 20% 50%, rgba(139,92,246,0.05) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(0,217,255,0.05) 0%, transparent 50%),
                linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 50%, var(--bg-tertiary) 100%);
    font-family: 'Inter', sans-serif;
    color: var(--text-primary);
}

.stApp > header {
    background: transparent !important;
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background: rgba(11,13,23,0.95) !important;
    border-right: 1px solid var(--border-primary) !important;
    backdrop-filter: blur(20px) !important;
}

[data-testid="stSidebar"] * {
    color: var(--text-primary) !important;
}

/* Hero Header - Premium Design */
.hero-header {
    background: linear-gradient(135deg, 
        rgba(139,92,246,0.08) 0%, 
        rgba(0,217,255,0.08) 50%, 
        rgba(0,245,160,0.08) 100%
    );
    border: 1px solid var(--border-accent);
    border-radius: 24px;
    padding: 32px 40px;
    margin-bottom: 32px;
    text-align: center;
    backdrop-filter: blur(30px);
    box-shadow: var(--shadow-lg), var(--glow-primary);
    position: relative;
    overflow: hidden;
}

.hero-header::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, 
        transparent 0%, 
        rgba(139,92,246,0.3) 20%, 
        rgba(0,217,255,0.3) 50%, 
        rgba(0,245,160,0.3) 80%, 
        transparent 100%
    );
}

.hero-title {
    font-family: 'Inter', sans-serif;
    font-size: 36px;
    font-weight: 800;
    background: linear-gradient(135deg, #FFFFFF 0%, rgba(139,92,246,0.9) 50%, #00D9FF 100%);
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    letter-spacing: -0.02em;
}

.hero-subtitle {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-secondary);
    margin-top: 8px;
    letter-spacing: 0.02em;
}

.hero-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 52px;
    font-weight: 600;
    background: linear-gradient(135deg, var(--info) 0%, var(--success) 100%);
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 20px 0 12px 0;
    letter-spacing: -0.02em;
}

.hero-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-tertiary);
    letter-spacing: 0.03em;
}

/* Enhanced Card System */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border-primary);
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 20px;
    backdrop-filter: blur(20px);
    box-shadow: var(--shadow-md);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
}

.card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, 
        transparent 0%, 
        rgba(255,255,255,0.1) 50%, 
        transparent 100%
    );
}

.card:hover {
    background: var(--bg-card-hover);
    border-color: var(--border-accent);
    box-shadow: var(--shadow-lg), var(--glow-primary);
    transform: translateY(-2px);
}

.card-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 20px;
}

.card-icon {
    width: 48px;
    height: 48px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    border: 1px solid var(--border-primary);
    backdrop-filter: blur(10px);
}

.card-icon.green { background: var(--success-bg); border-color: var(--success-border); }
.card-icon.red { background: var(--danger-bg); border-color: var(--danger-border); }
.card-icon.amber { background: var(--warning-bg); border-color: var(--warning-border); }
.card-icon.purple { background: var(--purple-bg); border-color: var(--purple-border); }
.card-icon.cyan { background: var(--info-bg); border-color: var(--info-border); }
.card-icon.blue { background: var(--info-bg); border-color: var(--info-border); }

.card-title {
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: -0.01em;
}

.card-subtitle {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    margin: 2px 0 0 0;
}

/* Signal Badges - Premium Design */
.signal-badge {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 24px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border: 1px solid;
    backdrop-filter: blur(10px);
    transition: all 0.2s ease;
}

.signal-badge.calls {
    background: var(--success-bg);
    color: var(--success);
    border-color: var(--success-border);
    box-shadow: 0 0 10px rgba(0,245,160,0.1);
}

.signal-badge.puts {
    background: var(--danger-bg);
    color: var(--danger);
    border-color: var(--danger-border);
    box-shadow: 0 0 10px rgba(255,75,106,0.1);
}

.signal-badge.neutral {
    background: var(--warning-bg);
    color: var(--warning);
    border-color: var(--warning-border);
    box-shadow: 0 0 10px rgba(255,184,0,0.1);
}

/* Trade Cards - Institutional Grade */
.trade-card {
    background: var(--bg-card);
    border: 1px solid var(--border-primary);
    border-radius: 20px;
    padding: 20px;
    margin-bottom: 16px;
    backdrop-filter: blur(20px);
    box-shadow: var(--shadow-md);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
}

.trade-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, 
        transparent 0%, 
        rgba(255,255,255,0.08) 50%, 
        transparent 100%
    );
}

.trade-card.active {
    border-color: var(--info-border);
    box-shadow: var(--shadow-lg), 0 0 25px rgba(0,217,255,0.15);
    background: linear-gradient(135deg, 
        rgba(0,217,255,0.03) 0%, 
        rgba(255,255,255,0.01) 100%
    );
}

.trade-card.broken {
    border-color: var(--danger-border);
    opacity: 0.6;
    background: linear-gradient(135deg, 
        rgba(255,75,106,0.02) 0%, 
        rgba(255,255,255,0.01) 100%
    );
}

.trade-card.at-level {
    border-color: var(--success-border);
    box-shadow: var(--shadow-lg), var(--glow-success);
    background: linear-gradient(135deg, 
        rgba(0,245,160,0.03) 0%, 
        rgba(255,255,255,0.01) 100%
    );
    animation: pulse-success 2s infinite;
}

@keyframes pulse-success {
    0%, 100% {
        box-shadow: var(--shadow-lg), 0 0 20px rgba(0,245,160,0.15);
    }
    50% {
        box-shadow: var(--shadow-lg), 0 0 30px rgba(0,245,160,0.25);
    }
}

.trade-status {
    font-size: 10px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 16px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border: 1px solid;
    backdrop-filter: blur(10px);
}

.trade-status.watching {
    background: rgba(255,255,255,0.05);
    color: var(--text-tertiary);
    border-color: var(--border-primary);
}

.trade-status.approaching {
    background: var(--warning-bg);
    color: var(--warning);
    border-color: var(--warning-border);
}

.trade-status.at-level {
    background: var(--success-bg);
    color: var(--success);
    border-color: var(--success-border);
}

.trade-status.broken {
    background: var(--danger-bg);
    color: var(--danger);
    border-color: var(--danger-border);
}

/* Data Tables - Premium */
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    background: transparent;
}

.data-table th {
    text-align: left;
    padding: 12px 16px;
    color: var(--text-secondary);
    font-weight: 600;
    border-bottom: 1px solid var(--border-primary);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    background: rgba(255,255,255,0.01);
}

.data-table td {
    padding: 12px 16px;
    color: var(--text-primary);
    border-bottom: 1px solid var(--border-secondary);
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    transition: background 0.2s ease;
}

.data-table tr:hover td {
    background: rgba(255,255,255,0.02);
}

.table-up { color: var(--success) !important; }
.table-down { color: var(--danger) !important; }

/* Pillar Items */
.pillar-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid var(--border-secondary);
    transition: all 0.2s ease;
}

.pillar-item:hover {
    background: rgba(255,255,255,0.02);
    margin: 0 -12px;
    padding: 12px;
    border-radius: 8px;
}

.pillar-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
}

.pillar-value {
    font-size: 13px;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    color: var(--text-primary);
}

/* Metric Values */
.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.01em;
}

.metric-value.green { color: var(--success); }
.metric-value.red { color: var(--danger); }
.metric-value.amber { color: var(--warning); }
.metric-value.cyan { color: var(--info); }
.metric-value.purple { color: var(--purple); }

/* Footer */
.app-footer {
    text-align: center;
    padding: 24px;
    color: var(--text-tertiary);
    font-size: 12px;
    font-weight: 500;
    border-top: 1px solid var(--border-primary);
    margin-top: 32px;
    background: rgba(255,255,255,0.01);
    font-family: 'JetBrains Mono', monospace;
}

/* Scrollbar Styling */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-track {
    background: var(--bg-secondary);
}

::-webkit-scrollbar-thumb {
    background: var(--border-primary);
    border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--border-accent);
}

/* Loading States */
@keyframes shimmer {
    0% {
        background-position: -200px 0;
    }
    100% {
        background-position: calc(200px + 100%) 0;
    }
}

.loading {
    background: linear-gradient(90deg, 
        transparent, 
        rgba(255,255,255,0.1), 
        transparent
    );
    background-size: 200px 100%;
    animation: shimmer 1.5s infinite;
}
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_now_ct() -> datetime:
    return datetime.now(CT)

def count_30min_blocks(start_dt: datetime, end_dt: datetime) -> int:
    if start_dt >= end_dt:
        return 0
    diff = end_dt - start_dt
    return int(diff.total_seconds() / 60 // 30)

# ═══════════════════════════════════════════════════════════════════════════════
# BLACK-SCHOLES FOR OPTION PRICING
# ═══════════════════════════════════════════════════════════════════════════════

def black_scholes_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """
    Calculate Black-Scholes option price
    S = current stock price
    K = strike price
    T = time to expiration (in years)
    r = risk-free rate
    sigma = implied volatility
    """
    if T <= 0:
        # At expiration
        if option_type == "CALL":
            return max(0, S - K)
        else:
            return max(0, K - S)
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    if option_type == "CALL":
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    
    return max(0, price)

def calculate_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> Dict:
    """Calculate option Greeks"""
    if T <= 0:
        return {"delta": 1.0 if option_type == "CALL" else -1.0, "gamma": 0, "theta": 0, "vega": 0}
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    # Delta
    if option_type == "CALL":
        delta = norm_cdf(d1)
    else:
        delta = norm_cdf(d1) - 1
    
    # Gamma
    gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
    
    # Theta (per day)
    theta_part1 = -(S * norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
    if option_type == "CALL":
        theta = (theta_part1 - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365
    else:
        theta = (theta_part1 + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365
    
    # Vega (per 1% move in IV)
    vega = S * math.sqrt(T) * norm_pdf(d1) / 100
    
    return {"delta": round(delta, 4), "gamma": round(gamma, 6), "theta": round(theta, 4), "vega": round(vega, 4)}

def estimate_option_price_at_level(
    current_spx: float,
    target_spx: float,
    strike: float,
    option_type: str,
    current_option_price: float,
    iv: float,
    time_to_expiry_hours: float,
    risk_free_rate: float = 0.05
) -> Dict:
    """
    Estimate option price when SPX reaches target level
    Uses Black-Scholes with time decay adjustment
    """
    # Current time to expiry in years
    T_current = time_to_expiry_hours / (365 * 24)
    
    # Estimate time when price reaches target (assume 30 min to 2 hours)
    price_diff = abs(target_spx - current_spx)
    estimated_time_to_reach = min(2, max(0.5, price_diff / 10))  # hours
    T_at_target = max(0.001, (time_to_expiry_hours - estimated_time_to_reach) / (365 * 24))
    
    # Calculate price at target
    price_at_target = black_scholes_price(target_spx, strike, T_at_target, risk_free_rate, iv, option_type)
    
    # Calculate Greeks at current price
    greeks = calculate_greeks(current_spx, strike, T_current, risk_free_rate, iv, option_type)
    
    # Simple delta estimate for comparison
    delta_estimate = current_option_price + greeks["delta"] * (target_spx - current_spx)
    
    return {
        "price_at_target": round(price_at_target, 2),
        "delta_estimate": round(max(0.01, delta_estimate), 2),
        "current_price": current_option_price,
        "delta": greeks["delta"],
        "time_to_reach_est": round(estimated_time_to_reach, 1)
    }

# ═══════════════════════════════════════════════════════════════════════════════
# POLYGON API - OPTIONS DATA
# ═══════════════════════════════════════════════════════════════════════════════

def build_option_ticker(expiry_date: date, strike: float, option_type: str) -> str:
    """
    Build SPXW option ticker for Polygon
    Format: O:SPXW{YYMMDD}{C/P}{strike*1000 as 8 digits}
    Example: O:SPXW260113C06000000
    """
    date_str = expiry_date.strftime("%y%m%d")
    type_char = "C" if option_type == "CALL" else "P"
    strike_int = int(strike * 1000)
    strike_str = f"{strike_int:08d}"
    return f"O:SPXW{date_str}{type_char}{strike_str}"

@st.cache_data(ttl=30, show_spinner=False)
def fetch_option_quote(ticker: str) -> Optional[Dict]:
    """Fetch last quote for option from Polygon"""
    try:
        # Use the quotes endpoint
        url = f"{POLYGON_BASE}/v3/quotes/{ticker}?limit=1&apiKey={POLYGON_KEY}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                # Calculate midpoint from bid/ask
                bid = result.get("bid_price", 0)
                ask = result.get("ask_price", 0)
                midpoint = (bid + ask) / 2 if bid and ask else None
                
                return {
                    "last_price": midpoint,
                    "bid": bid,
                    "ask": ask,
                    "bid_size": result.get("bid_size"),
                    "ask_size": result.get("ask_size"),
                    "ticker": ticker
                }
        
        # Try snapshot as fallback
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
                    "volume": day_data.get("volume"),
                    "ticker": ticker
                }
                
    except Exception as e:
        pass  # Silent fail, will use estimation
    
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_from_polygon() -> Optional[float]:
    """Fetch SPX price from Polygon"""
    try:
        url = f"{POLYGON_BASE}/v3/snapshot?ticker.any_of=I:SPX&apiKey={POLYGON_KEY}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                # Try different price fields
                price = (result.get("value") or 
                        result.get("session", {}).get("close") or
                        result.get("session", {}).get("previous_close"))
                if price:
                    return round(float(price), 2)
    except Exception as e:
        pass
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_from_polygon() -> Optional[float]:
    """Fetch VIX price from Polygon"""
    try:
        url = f"{POLYGON_BASE}/v3/snapshot?ticker.any_of=I:VIX&apiKey={POLYGON_KEY}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                price = (result.get("value") or 
                        result.get("session", {}).get("close") or
                        result.get("session", {}).get("previous_close"))
                if price:
                    return round(float(price), 2)
    except Exception as e:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def fetch_es_30min_candles(days: int = 10) -> Optional[pd.DataFrame]:
    for attempt in range(3):
        try:
            es = yf.Ticker("ES=F")
            data = es.history(period=f"{days}d", interval="30m")
            if data is not None and not data.empty:
                return data
        except:
            time_module.sleep(1)
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_price() -> Tuple[Optional[float], str]:
    """Fetch SPX price - try Polygon first, then Yahoo"""
    # Try Polygon first
    polygon_price = fetch_spx_from_polygon()
    if polygon_price:
        return polygon_price, "POLYGON"
    
    # Fallback to Yahoo
    for attempt in range(2):
        try:
            spx = yf.Ticker("^GSPC")
            data = spx.history(period="1d", interval="1m")
            if data is not None and not data.empty:
                return round(float(data['Close'].iloc[-1]), 2), "YAHOO"
        except:
            time_module.sleep(0.5)
    return None, "FAILED"

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_price() -> Tuple[Optional[float], str]:
    """Fetch VIX price - try Polygon first, then Yahoo"""
    # Try Polygon first
    polygon_price = fetch_vix_from_polygon()
    if polygon_price:
        return polygon_price, "POLYGON"
    
    # Fallback to Yahoo
    for attempt in range(2):
        try:
            vix = yf.Ticker("^VIX")
            data = vix.history(period="1d", interval="1m")
            if data is not None and not data.empty:
                return round(float(data['Close'].iloc[-1]), 2), "YAHOO"
        except:
            time_module.sleep(0.5)
    return None, "FAILED"

def fetch_options_for_strikes(expiry_date: date, strikes: List[int]) -> Dict[str, Dict]:
    """Fetch option quotes for multiple strikes"""
    results = {}
    
    for strike in strikes:
        for opt_type in ["CALL", "PUT"]:
            ticker = build_option_ticker(expiry_date, float(strike), opt_type)
            quote = fetch_option_quote(ticker)
            key = f"{strike}_{opt_type}"
            
            if quote and quote.get("last_price"):
                results[key] = quote
            else:
                # Store ticker even if no quote (for display)
                results[key] = {"ticker": ticker, "last_price": None}
    
    return results

# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 1: MA BIAS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_ma_bias(es_candles: Optional[pd.DataFrame]) -> Dict:
    candle_count = len(es_candles) if es_candles is not None else 0
    if es_candles is None or candle_count < 50:
        return {"signal": "NEUTRAL", "reason": "Insufficient data", "ema_50": None, "sma_200": None, "score": 0, "candle_count": candle_count}
    
    close = es_candles['Close']
    ema_50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    sma_200 = close.rolling(window=min(200, candle_count)).mean().iloc[-1]
    diff_pct = ((ema_50 - sma_200) / sma_200) * 100
    
    if ema_50 > sma_200:
        signal, score = "LONG", min(30, int(abs(diff_pct) * 15))
    elif ema_50 < sma_200:
        signal, score = "SHORT", min(30, int(abs(diff_pct) * 15))
    else:
        signal, score = "NEUTRAL", 0
    
    return {"signal": signal, "reason": f"EMA vs SMA: {diff_pct:+.2f}%", "ema_50": round(ema_50, 2), "sma_200": round(sma_200, 2), "score": score, "candle_count": candle_count}

# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 2: DAY STRUCTURE - ALL 4 TRADES
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_all_trades(
    overnight_high: float, overnight_high_time: datetime,
    overnight_low: float, overnight_low_time: datetime,
    target_time: datetime, current_price: float, current_time: datetime,
    premarket_high: Optional[float] = None, premarket_low: Optional[float] = None
) -> Dict:
    """Calculate all 4 structure lines as potential trades"""
    
    effective_high = premarket_high if premarket_high and premarket_high > overnight_high else overnight_high
    effective_low = premarket_low if premarket_low and premarket_low < overnight_low else overnight_low
    
    blocks_high = count_30min_blocks(overnight_high_time, current_time)
    blocks_low = count_30min_blocks(overnight_low_time, current_time)
    
    high_exp = SLOPE * blocks_high
    low_exp = SLOPE * blocks_low
    
    trades = {
        "ceiling_rising": {
            "name": "Ceiling Rising",
            "short": "C↑",
            "anchor": effective_high,
            "level": round(effective_high + high_exp, 2),
            "direction": "rising",
            "entry_type": "PUTS",
            "blocks": blocks_high,
            "expansion": round(high_exp, 2)
        },
        "ceiling_falling": {
            "name": "Ceiling Falling", 
            "short": "C↓",
            "anchor": effective_high,
            "level": round(effective_high - high_exp, 2),
            "direction": "falling",
            "entry_type": "CALLS",
            "blocks": blocks_high,
            "expansion": round(high_exp, 2)
        },
        "floor_rising": {
            "name": "Floor Rising",
            "short": "F↑",
            "anchor": effective_low,
            "level": round(effective_low + low_exp, 2),
            "direction": "rising",
            "entry_type": "PUTS",
            "blocks": blocks_low,
            "expansion": round(low_exp, 2)
        },
        "floor_falling": {
            "name": "Floor Falling",
            "short": "F↓",
            "anchor": effective_low,
            "level": round(effective_low - low_exp, 2),
            "direction": "falling",
            "entry_type": "CALLS",
            "blocks": blocks_low,
            "expansion": round(low_exp, 2)
        }
    }
    
    # Calculate distance and status for each trade
    for key, trade in trades.items():
        distance = current_price - trade["level"]
        abs_distance = abs(distance)
        
        trade["distance"] = round(distance, 2)
        trade["abs_distance"] = round(abs_distance, 2)
        trade["price_above"] = distance > 0
        trade["price_below"] = distance < 0
        
        # Determine status
        if trade["direction"] == "rising":
            # For rising lines, price should approach from below
            if trade["price_above"] and abs_distance >= GAP_THRESHOLD:
                trade["status"] = "BROKEN"
            elif abs_distance <= 3:
                trade["status"] = "AT_LEVEL"
            elif abs_distance <= 15 and trade["price_below"]:
                trade["status"] = "APPROACHING"
            else:
                trade["status"] = "WATCHING"
        else:
            # For falling lines, price should approach from above
            if trade["price_below"] and abs_distance >= GAP_THRESHOLD:
                trade["status"] = "BROKEN"
            elif abs_distance <= 3:
                trade["status"] = "AT_LEVEL"
            elif abs_distance <= 15 and trade["price_above"]:
                trade["status"] = "APPROACHING"
            else:
                trade["status"] = "WATCHING"
        
        # Calculate strike based on ENTRY LEVEL (20 pts OTM from entry)
        if trade["entry_type"] == "CALLS":
            # For CALLS, strike should be above entry level (OTM)
            trade["strike"] = int(round((trade["level"] + 20) / 5) * 5)
        else:
            # For PUTS, strike should be below entry level (OTM)
            trade["strike"] = int(round((trade["level"] - 20) / 5) * 5)
    
    # Sort by level (highest to lowest)
    sorted_keys = sorted(trades.keys(), key=lambda k: trades[k]["level"], reverse=True)
    
    return {
        "trades": trades,
        "sorted_keys": sorted_keys,
        "effective_high": effective_high,
        "effective_low": effective_low
    }

# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 3: MOMENTUM - RSI Midline Reversion + MACD Confirmation
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_momentum(es_candles: Optional[pd.DataFrame], ma_bias: str = "NEUTRAL") -> Dict:
    """
    RSI Midline Reversion Strategy:
    - In uptrends (MA LONG): RSI oscillates 50-80, buy pullbacks to 50-60
    - In downtrends (MA SHORT): RSI oscillates 20-50, sell bounces to 40-50
    - MACD histogram confirms momentum direction
    
    Zones:
    - Overbought: RSI > 80
    - Oversold: RSI < 20
    - Bullish pullback zone: 50-60 (in uptrend)
    - Bearish bounce zone: 40-50 (in downtrend)
    """
    if es_candles is None or len(es_candles) < 26:
        return {
            "signal": "NEUTRAL", 
            "score": 0, 
            "rsi": 50, 
            "rsi_zone": "MID",
            "macd_histogram": 0,
            "macd_direction": "FLAT",
            "detail": "Insufficient data"
        }
    
    close = es_candles['Close']
    
    # RSI (14-period)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else 50
    
    # MACD (12/26/9)
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    macd_hist = round(histogram.iloc[-1], 2)
    macd_bull = macd_hist > 0
    
    # Determine RSI zone
    if rsi_val > 80:
        rsi_zone = "OVERBOUGHT"
    elif rsi_val < 20:
        rsi_zone = "OVERSOLD"
    elif 50 <= rsi_val <= 60:
        rsi_zone = "PULLBACK"  # Potential buy zone in uptrend
    elif 40 <= rsi_val < 50:
        rsi_zone = "BOUNCE"    # Potential sell zone in downtrend
    elif rsi_val > 60:
        rsi_zone = "BULLISH"
    elif rsi_val < 40:
        rsi_zone = "BEARISH"
    else:
        rsi_zone = "MID"
    
    # Generate signal based on MA Bias + RSI Zone + MACD Confirmation
    signal = "NEUTRAL"
    score = 15
    detail = ""
    
    if ma_bias == "LONG":
        # Uptrend: Look for pullbacks to 50-60
        if rsi_zone == "PULLBACK" and macd_bull:
            signal = "PULLBACK BUY"
            score = 35
            detail = "RSI pulled back to 50-60, MACD confirms"
        elif rsi_zone == "PULLBACK" and not macd_bull:
            signal = "WAIT"
            score = 10
            detail = "RSI in zone but MACD weak"
        elif rsi_zone == "OVERBOUGHT":
            signal = "OVERBOUGHT"
            score = 5
            detail = "RSI > 80, wait for pullback"
        elif rsi_zone == "BULLISH" and macd_bull:
            signal = "BULLISH"
            score = 25
            detail = "Trend intact"
        else:
            signal = "NEUTRAL"
            score = 15
            detail = "No clear setup"
            
    elif ma_bias == "SHORT":
        # Downtrend: Look for bounces to 40-50
        if rsi_zone == "BOUNCE" and not macd_bull:
            signal = "BOUNCE SELL"
            score = 35
            detail = "RSI bounced to 40-50, MACD confirms"
        elif rsi_zone == "BOUNCE" and macd_bull:
            signal = "WAIT"
            score = 10
            detail = "RSI in zone but MACD not confirming"
        elif rsi_zone == "OVERSOLD":
            signal = "OVERSOLD"
            score = 5
            detail = "RSI < 20, wait for bounce"
        elif rsi_zone == "BEARISH" and not macd_bull:
            signal = "BEARISH"
            score = 25
            detail = "Trend intact"
        else:
            signal = "NEUTRAL"
            score = 15
            detail = "No clear setup"
    
    else:
        # No MA Bias - use basic RSI/MACD
        if rsi_val > 50 and macd_bull:
            signal = "BULLISH"
            score = 25
            detail = "RSI > 50, MACD green"
        elif rsi_val < 50 and not macd_bull:
            signal = "BEARISH"
            score = 25
            detail = "RSI < 50, MACD red"
        elif rsi_zone == "OVERBOUGHT":
            signal = "OVERBOUGHT"
            score = 5
            detail = "RSI > 80"
        elif rsi_zone == "OVERSOLD":
            signal = "OVERSOLD"
            score = 5
            detail = "RSI < 20"
        else:
            signal = "NEUTRAL"
            score = 15
            detail = "Mixed signals"
    
    return {
        "signal": signal,
        "score": score,
        "rsi": rsi_val,
        "rsi_zone": rsi_zone,
        "macd_histogram": macd_hist,
        "macd_direction": "GREEN" if macd_bull else "RED",
        "detail": detail
    }

# ═══════════════════════════════════════════════════════════════════════════════
# VIX ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_vix(vix_current: float, vix_on_high: float, vix_on_low: float) -> Dict:
    zone = "NORMAL"
    for name, (lo, hi) in VIX_ZONES.items():
        if lo <= vix_current < hi:
            zone = name
            break
    
    vix_range = vix_on_high - vix_on_low
    position = (vix_current - vix_on_low) / vix_range * 100 if vix_range > 0 else 50
    
    if vix_current > vix_on_high:
        bias = "PUTS"
    elif vix_current < vix_on_low:
        bias = "CALLS"
    elif position > 70:
        bias = "PUTS"
    elif position < 30:
        bias = "CALLS"
    else:
        bias = "NEUTRAL"
    
    return {"current": vix_current, "overnight_high": vix_on_high, "overnight_low": vix_on_low, "zone": zone, "bias": bias, "position_pct": round(position, 1)}

# ═══════════════════════════════════════════════════════════════════════════════
# CONE RAILS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_cones(prior_high: float, prior_high_time: datetime, prior_low: float, prior_low_time: datetime, prior_close: float, prior_close_time: datetime, current_time: datetime) -> Dict:
    cones = {}
    for name, price, anchor_time in [("HIGH", prior_high, prior_high_time), ("LOW", prior_low, prior_low_time), ("CLOSE", prior_close, prior_close_time)]:
        blocks = count_30min_blocks(anchor_time, current_time)
        exp = SLOPE * blocks
        cones[name] = {"anchor": price, "asc": round(price + exp, 2), "desc": round(price - exp, 2), "blocks": blocks, "expansion": round(exp, 2)}
    return cones

def detect_confluence(trades: Dict, cones: Dict, current_price: float) -> List[Dict]:
    confluences = []
    for t_key, trade in trades["trades"].items():
        for c_name, cone in cones.items():
            for c_type, c_price in [("Asc", cone["asc"]), ("Desc", cone["desc"])]:
                dist = abs(trade["level"] - c_price)
                if dist <= CONFLUENCE_THRESHOLD:
                    confluences.append({
                        "trade": trade["name"],
                        "trade_key": t_key,
                        "cone": f"{c_name} {c_type}",
                        "avg_price": round((trade["level"] + c_price) / 2, 2),
                        "distance": round(dist, 2),
                        "dist_from_current": round(abs(current_price - (trade["level"] + c_price) / 2), 2)
                    })
    confluences.sort(key=lambda x: x["dist_from_current"])
    return confluences

# ═══════════════════════════════════════════════════════════════════════════════
# OPTION PRICE PREDICTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_trade_projections(
    trade: Dict,
    current_price: float,
    option_data: Optional[Dict],
    vix: float,
    expiry_time: datetime,
    current_time: datetime
) -> Dict:
    """
    Calculate entry and exit price predictions for a trade
    
    Exit targets:
    - Target 1: +10 pts move
    - Target 2: +20 pts move
    - Target 3: +30 pts move
    """
    
    strike = trade["strike"]
    entry_level = trade["level"]
    option_type = "CALL" if trade["entry_type"] == "CALLS" else "PUT"
    
    # Time to expiry in hours
    time_diff = expiry_time - current_time
    hours_to_expiry = max(0.1, time_diff.total_seconds() / 3600)
    
    # Use VIX as IV proxy (convert to decimal)
    iv = vix / 100
    
    # Track if price is from Polygon or estimated
    is_estimated = True
    
    # Get current option price from Polygon or estimate
    if option_data and option_data.get("last_price"):
        current_option_price = option_data["last_price"]
        iv = option_data.get("iv", iv) or iv
        is_estimated = False
    else:
        # Estimate current option price using Black-Scholes
        T = hours_to_expiry / (365 * 24)
        current_option_price = black_scholes_price(current_price, strike, T, 0.05, iv, option_type)
        is_estimated = True
    
    # Estimate option price at entry level
    entry_estimate = estimate_option_price_at_level(
        current_price, entry_level, strike, option_type,
        current_option_price, iv, hours_to_expiry
    )
    
    entry_price = entry_estimate["price_at_target"]
    
    # Calculate exit targets based on SPX movement
    # For CALLS: SPX goes up from entry → option value increases
    # For PUTS: SPX goes down from entry → option value increases
    
    if option_type == "CALL":
        # Exit targets when SPX rises
        target_moves = [10, 20, 30]  # SPX points up
        exit_prices = []
        for move in target_moves:
            target_spx = entry_level + move
            exit_est = estimate_option_price_at_level(
                entry_level, target_spx, strike, option_type,
                entry_price, iv, max(0.5, hours_to_expiry - 1)  # Ensure at least 0.5 hours
            )
            exit_prices.append({
                "spx_target": target_spx,
                "move": f"+{move}",
                "option_price": exit_est["price_at_target"],
                "profit_pct": round((exit_est["price_at_target"] - entry_price) / entry_price * 100, 1) if entry_price > 0 else 0
            })
    else:
        # Exit targets when SPX falls
        target_moves = [10, 20, 30]  # SPX points down
        exit_prices = []
        for move in target_moves:
            target_spx = entry_level - move
            exit_est = estimate_option_price_at_level(
                entry_level, target_spx, strike, option_type,
                entry_price, iv, max(0.5, hours_to_expiry - 1)  # Ensure at least 0.5 hours
            )
            exit_prices.append({
                "spx_target": target_spx,
                "move": f"-{move}",
                "option_price": exit_est["price_at_target"],
                "profit_pct": round((exit_est["price_at_target"] - entry_price) / entry_price * 100, 1) if entry_price > 0 else 0
            })
    
    return {
        "strike": strike,
        "option_type": option_type,
        "current_option_price": round(current_option_price, 2),
        "entry_price_est": round(entry_price, 2),
        "iv_used": round(iv * 100, 1),
        "is_estimated": is_estimated,
        "exit_targets": exit_prices,
        "delta_at_entry": entry_estimate.get("delta", 0)
    }

# ═══════════════════════════════════════════════════════════════════════════════
# PUT/CALL RATIO - Retail Bias Detection (Using Polygon)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def fetch_pcr_from_polygon(trading_date: date) -> Tuple[Optional[float], str]:
    """
    Fetch Put/Call Ratio using Polygon options data for SPY
    PCR < 0.7 = Heavy CALLS (retail bullish)
    PCR > 1.0 = Heavy PUTS (retail bearish)
    """
    try:
        # Format date for Polygon
        date_str = trading_date.strftime("%Y-%m-%d")
        
        # Get SPY options contracts for that date
        # Use the options chain snapshot endpoint
        url = f"{POLYGON_BASE}/v3/snapshot/options/SPY?apiKey={POLYGON_KEY}"
        resp = requests.get(url, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            
            if results:
                total_call_oi = 0
                total_put_oi = 0
                total_call_volume = 0
                total_put_volume = 0
                
                for option in results:
                    details = option.get("details", {})
                    day_data = option.get("day", {})
                    
                    contract_type = details.get("contract_type", "")
                    oi = option.get("open_interest", 0) or 0
                    volume = day_data.get("volume", 0) or 0
                    
                    if contract_type == "call":
                        total_call_oi += oi
                        total_call_volume += volume
                    elif contract_type == "put":
                        total_put_oi += oi
                        total_put_volume += volume
                
                # Calculate PCR from Open Interest (more reliable)
                if total_call_oi > 0:
                    pcr_oi = total_put_oi / total_call_oi
                    return round(pcr_oi, 2), "POLYGON_OI"
                
                # Fallback to volume-based PCR
                if total_call_volume > 0:
                    pcr_vol = total_put_volume / total_call_volume
                    return round(pcr_vol, 2), "POLYGON_VOL"
        
        # If snapshot doesn't work, try aggregates for a simpler approach
        # Get SPY price to estimate ATM strikes
        spy_url = f"{POLYGON_BASE}/v2/aggs/ticker/SPY/prev?adjusted=true&apiKey={POLYGON_KEY}"
        spy_resp = requests.get(spy_url, timeout=10)
        
        if spy_resp.status_code == 200:
            spy_data = spy_resp.json()
            if "results" in spy_data and len(spy_data["results"]) > 0:
                spy_close = spy_data["results"][0].get("c", 590)
                
                # Check a range of strikes around ATM for the nearest expiry
                atm_strike = round(spy_close / 5) * 5
                strikes_to_check = [atm_strike - 10, atm_strike - 5, atm_strike, atm_strike + 5, atm_strike + 10]
                
                # Find the next expiry (today or next trading day)
                expiry_date = trading_date
                expiry_str = expiry_date.strftime("%y%m%d")
                
                total_call_oi = 0
                total_put_oi = 0
                
                for strike in strikes_to_check:
                    strike_int = int(strike * 1000)
                    strike_str = f"{strike_int:08d}"
                    
                    # Check call
                    call_ticker = f"O:SPY{expiry_str}C{strike_str}"
                    call_url = f"{POLYGON_BASE}/v3/snapshot/options/{call_ticker}?apiKey={POLYGON_KEY}"
                    call_resp = requests.get(call_url, timeout=5)
                    if call_resp.status_code == 200:
                        call_data = call_resp.json()
                        if "results" in call_data:
                            total_call_oi += call_data["results"].get("open_interest", 0) or 0
                    
                    # Check put
                    put_ticker = f"O:SPY{expiry_str}P{strike_str}"
                    put_url = f"{POLYGON_BASE}/v3/snapshot/options/{put_ticker}?apiKey={POLYGON_KEY}"
                    put_resp = requests.get(put_url, timeout=5)
                    if put_resp.status_code == 200:
                        put_data = put_resp.json()
                        if "results" in put_data:
                            total_put_oi += put_data["results"].get("open_interest", 0) or 0
                
                if total_call_oi > 0:
                    pcr = total_put_oi / total_call_oi
                    return round(pcr, 2), "POLYGON_ATM"
        
        return None, "NO_DATA"
        
    except Exception as e:
        return None, f"ERROR: {str(e)[:50]}"

def get_retail_bias(pcr: Optional[float]) -> Tuple[str, str]:
    """
    Determine retail bias from PCR
    Returns: (bias, description)
    """
    if pcr is None:
        return "NEUTRAL", "No PCR data"
    
    if pcr < 0.7:
        return "HEAVY_CALLS", f"PCR {pcr:.2f} - Retail bullish"
    elif pcr > 1.0:
        return "HEAVY_PUTS", f"PCR {pcr:.2f} - Retail bearish"
    else:
        return "NEUTRAL", f"PCR {pcr:.2f} - Balanced"

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL ANALYSIS - MM Hunt Detection
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_channel(
    channel_type: str,  # "DESCENDING" or "ASCENDING"
    breakout_direction: str,  # "UP", "DOWN", or "NONE"
    retail_bias: str,  # "HEAVY_CALLS", "HEAVY_PUTS", or "NEUTRAL"
    trades: Dict,
    cones: Dict
) -> Dict:
    """
    Analyze channel breakout and determine MM targets
    
    DESCENDING CHANNEL (Ceiling Falling + Floor Falling):
    - Break UP: Return to Ceiling Falling (or Floor Falling if hunting calls)
    - Break DOWN: Find bottom at Low Cone Desc, then rally to Ceiling Falling
    
    ASCENDING CHANNEL (Floor Rising + Ceiling Rising):
    - Break DOWN: Return to Floor Rising (or Ceiling Rising if hunting puts)
    - Break UP: Find top at High Cone Asc, then sell to Floor Rising
    """
    
    result = {
        "channel": channel_type,
        "breakout": breakout_direction,
        "retail_bias": retail_bias,
        "primary_target": None,
        "primary_target_price": None,
        "primary_action": None,
        "secondary_target": None,
        "secondary_target_price": None,
        "secondary_action": None,
        "analysis": "",
        "trade_bias": "NEUTRAL"
    }
    
    if channel_type == "UNDETERMINED" or breakout_direction == "NONE":
        result["analysis"] = "Waiting for channel/breakout confirmation"
        return result
    
    # Get structure levels
    ceiling_falling = trades["trades"]["ceiling_falling"]["level"]
    floor_falling = trades["trades"]["floor_falling"]["level"]
    ceiling_rising = trades["trades"]["ceiling_rising"]["level"]
    floor_rising = trades["trades"]["floor_rising"]["level"]
    
    # Get cone levels
    high_cone_asc = cones["HIGH"]["asc"]
    low_cone_desc = cones["LOW"]["desc"]
    
    if channel_type == "DESCENDING":
        if breakout_direction == "UP":
            # Broke above descending channel
            if retail_bias == "HEAVY_CALLS":
                # MM will hunt calls - drop to floor first
                result["primary_target"] = "Floor Falling"
                result["primary_target_price"] = floor_falling
                result["primary_action"] = "WAIT for support"
                result["secondary_target"] = "Ceiling Falling"
                result["secondary_target_price"] = ceiling_falling
                result["secondary_action"] = "BUY to target"
                result["analysis"] = "Heavy calls → MM drops to Floor Falling first, then buys to Ceiling Falling"
                result["trade_bias"] = "CALLS"
            else:
                # Normal - return to top of channel
                result["primary_target"] = "Ceiling Falling"
                result["primary_target_price"] = ceiling_falling
                result["primary_action"] = "BUY to target"
                result["secondary_target"] = "Above channel"
                result["secondary_target_price"] = ceiling_falling + 10
                result["secondary_action"] = "Continuation"
                result["analysis"] = "Breakout UP → Return to Ceiling Falling, then higher"
                result["trade_bias"] = "CALLS"
                
        elif breakout_direction == "DOWN":
            # Broke below descending channel
            result["primary_target"] = "Low Cone Desc"
            result["primary_target_price"] = low_cone_desc
            result["primary_action"] = "WAIT for MM buy"
            result["secondary_target"] = "Ceiling Falling"
            result["secondary_target_price"] = ceiling_falling
            result["secondary_action"] = "BUY to target"
            result["analysis"] = "Break DOWN → MM buys at Low Cone, rallies to Ceiling Falling to destroy puts"
            result["trade_bias"] = "CALLS"
    
    elif channel_type == "ASCENDING":
        if breakout_direction == "DOWN":
            # Broke below ascending channel
            if retail_bias == "HEAVY_PUTS":
                # MM will hunt puts - push to ceiling first
                result["primary_target"] = "Ceiling Rising"
                result["primary_target_price"] = ceiling_rising
                result["primary_action"] = "WAIT for resistance"
                result["secondary_target"] = "Floor Rising"
                result["secondary_target_price"] = floor_rising
                result["secondary_action"] = "SELL to target"
                result["analysis"] = "Heavy puts → MM pushes to Ceiling Rising first, then sells to Floor Rising"
                result["trade_bias"] = "PUTS"
            else:
                # Normal - return to bottom of channel
                result["primary_target"] = "Floor Rising"
                result["primary_target_price"] = floor_rising
                result["primary_action"] = "SELL to target"
                result["secondary_target"] = "Below channel"
                result["secondary_target_price"] = floor_rising - 10
                result["secondary_action"] = "Continuation"
                result["analysis"] = "Breakout DOWN → Return to Floor Rising, then lower"
                result["trade_bias"] = "PUTS"
                
        elif breakout_direction == "UP":
            # Broke above ascending channel
            result["primary_target"] = "High Cone Asc"
            result["primary_target_price"] = high_cone_asc
            result["primary_action"] = "WAIT for MM sell"
            result["secondary_target"] = "Floor Rising"
            result["secondary_target_price"] = floor_rising
            result["secondary_action"] = "SELL to target"
            result["analysis"] = "Break UP → MM sells at High Cone, drops to Floor Rising to destroy calls"
            result["trade_bias"] = "PUTS"
    
    return result

def save_inputs(inputs: Dict):
    try:
        serializable = {k: v.isoformat() if isinstance(v, (datetime, date)) else v.strftime("%H:%M") if isinstance(v, time) else v for k, v in inputs.items()}
        with open(SAVE_FILE, 'w') as f:
            json.dump(serializable, f, indent=2)
    except:
        pass

def load_inputs() -> Dict:
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar() -> Dict:
    saved = load_inputs()
    
    with st.sidebar:
        st.markdown("## 🔮 SPX Prophet V5.2")
        st.markdown("*All Trades | Options Pricing*")
        
        trading_date = st.date_input("📅 Trading Date", value=date.today())
        
        st.markdown("---")
        st.markdown("### 📈 SPX Price")
        use_manual = st.checkbox("Manual SPX", value=False)
        spx_price = st.number_input("SPX", value=float(saved.get("spx_price", 6050.0)), step=1.0) if use_manual else None
        
        st.markdown("---")
        st.markdown("### 📊 MA Bias Override")
        ma_override = st.selectbox("Override", ["AUTO", "LONG", "SHORT", "NEUTRAL"], index=0)
        
        st.markdown("---")
        st.markdown("### 📐 Overnight Structure")
        
        # Reference time selection
        ref_time_options = ["9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM"]
        ref_time_selection = st.selectbox("Reference Time (CT)", ref_time_options, index=0)
        ref_time_map = {"9:00 AM": (9, 0), "9:30 AM": (9, 30), "10:00 AM": (10, 0), "10:30 AM": (10, 30)}
        ref_hour, ref_min = ref_time_map[ref_time_selection]
        
        HOURS, MINS = list(range(24)), [0, 15, 30, 45]
        
        st.markdown("**O/N HIGH**")
        c1, c2, c3 = st.columns([2, 1, 1])
        on_high_price = c1.number_input("Price", value=float(saved.get("on_high_price", 6070.0)), step=0.5, key="onh_p")
        on_high_hour = c2.selectbox("Hr", HOURS, index=int(saved.get("on_high_hour", 19)), key="onh_h")
        on_high_min = c3.selectbox("Mn", MINS, index=MINS.index(int(saved.get("on_high_min", 30))) if int(saved.get("on_high_min", 30)) in MINS else 0, key="onh_m")
        
        st.markdown("**O/N LOW**")
        c1, c2, c3 = st.columns([2, 1, 1])
        on_low_price = c1.number_input("Price", value=float(saved.get("on_low_price", 6020.0)), step=0.5, key="onl_p")
        on_low_hour = c2.selectbox("Hr", HOURS, index=int(saved.get("on_low_hour", 3)), key="onl_h")
        on_low_min = c3.selectbox("Mn", MINS, index=MINS.index(int(saved.get("on_low_min", 0))) if int(saved.get("on_low_min", 0)) in MINS else 0, key="onl_m")
        
        use_pm = st.checkbox("Pre-Market Override", value=False)
        pm_high = st.number_input("PM High", value=0.0, step=0.5) if use_pm else None
        pm_low = st.number_input("PM Low", value=0.0, step=0.5) if use_pm else None
        
        st.markdown("---")
        st.markdown("### ⚡ VIX")
        vix_on_high = st.number_input("VIX O/N High", value=float(saved.get("vix_on_high", 18.0)), step=0.1)
        vix_on_low = st.number_input("VIX O/N Low", value=float(saved.get("vix_on_low", 15.0)), step=0.1)
        use_manual_vix = st.checkbox("Manual VIX", value=False)
        vix_manual = st.number_input("VIX", value=16.5, step=0.1) if use_manual_vix else None
        
        st.markdown("---")
        st.markdown("### 📊 Prior Day (Cones)")
        c1, c2, c3 = st.columns([2, 1, 1])
        prior_high = c1.number_input("High", value=float(saved.get("prior_high", 6075.0)), step=0.5)
        prior_high_hour = c2.selectbox("Hr", HOURS, index=int(saved.get("prior_high_hour", 10)), key="ph_h")
        prior_high_min = c3.selectbox("Mn", MINS, index=0, key="ph_m")
        
        c1, c2, c3 = st.columns([2, 1, 1])
        prior_low = c1.number_input("Low", value=float(saved.get("prior_low", 6010.0)), step=0.5)
        prior_low_hour = c2.selectbox("Hr", HOURS, index=int(saved.get("prior_low_hour", 14)), key="pl_h")
        prior_low_min = c3.selectbox("Mn", MINS, index=0, key="pl_m")
        
        prior_close = st.number_input("Close", value=float(saved.get("prior_close", 6045.0)), step=0.5)
        
        st.markdown("---")
        st.markdown("### 🎯 Channel Analysis")
        
        # Channel type
        channel_type = st.radio(
            "O/N Channel",
            ["UNDETERMINED", "DESCENDING", "ASCENDING"],
            index=0,
            horizontal=True
        )
        
        # Breakout direction
        breakout_dir = st.radio(
            "8:30 AM Breakout",
            ["NONE", "UP", "DOWN"],
            index=0,
            horizontal=True
        )
        
        # Retail bias - auto or manual
        st.markdown("**Retail Bias**")
        use_auto_pcr = st.checkbox("Auto PCR", value=True)
        if not use_auto_pcr:
            retail_bias_override = st.radio(
                "Manual Bias",
                ["NEUTRAL", "HEAVY_CALLS", "HEAVY_PUTS"],
                index=0,
                horizontal=True
            )
        else:
            retail_bias_override = None
        
        st.markdown("---")
        auto_refresh = st.checkbox("Auto-Refresh", value=False)
        refresh_sec = st.slider("Seconds", 15, 120, 30) if auto_refresh else 30
        show_debug = st.checkbox("Debug", value=False)
        
        if st.button("💾 Save", use_container_width=True):
            save_inputs({"spx_price": spx_price, "on_high_price": on_high_price, "on_high_hour": on_high_hour, "on_high_min": on_high_min, "on_low_price": on_low_price, "on_low_hour": on_low_hour, "on_low_min": on_low_min, "vix_on_high": vix_on_high, "vix_on_low": vix_on_low, "prior_high": prior_high, "prior_high_hour": prior_high_hour, "prior_low": prior_low, "prior_low_hour": prior_low_hour, "prior_close": prior_close})
            st.success("✅")
    
    prev_day = trading_date - timedelta(days=1)
    
    def make_time(hour, minute):
        if hour >= 17:
            return CT.localize(datetime.combine(prev_day, time(hour, minute)))
        return CT.localize(datetime.combine(trading_date, time(hour, minute)))
    
    return {
        "trading_date": trading_date,
        "spx_price": spx_price,
        "ma_override": ma_override,
        "ref_hour": ref_hour,
        "ref_min": ref_min,
        "on_high_price": on_high_price,
        "on_high_time": make_time(on_high_hour, on_high_min),
        "on_low_price": on_low_price,
        "on_low_time": make_time(on_low_hour, on_low_min),
        "pm_high": pm_high if use_pm and pm_high else None,
        "pm_low": pm_low if use_pm and pm_low else None,
        "vix_on_high": vix_on_high,
        "vix_on_low": vix_on_low,
        "vix_manual": vix_manual,
        "prior_high": prior_high,
        "prior_high_time": CT.localize(datetime.combine(prev_day, time(prior_high_hour, prior_high_min))),
        "prior_low": prior_low,
        "prior_low_time": CT.localize(datetime.combine(prev_day, time(prior_low_hour, prior_low_min))),
        "prior_close": prior_close,
        "prior_close_time": CT.localize(datetime.combine(prev_day, time(15, 0))),
        "channel_type": channel_type,
        "breakout_dir": breakout_dir,
        "retail_bias_override": retail_bias_override,
        "use_auto_pcr": use_auto_pcr,
        "auto_refresh": auto_refresh,
        "refresh_sec": refresh_sec,
        "show_debug": show_debug
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown(STYLES, unsafe_allow_html=True)
    inputs = render_sidebar()
    now_ct = get_now_ct()
    
    # Expiry time (3:00 PM CT for 0DTE)
    expiry_time = CT.localize(datetime.combine(inputs["trading_date"], time(15, 0)))
    
    # Data Loading
    with st.spinner("Loading..."):
        if inputs["spx_price"]:
            current_price, spx_source = inputs["spx_price"], "MANUAL"
        else:
            current_price, spx_source = fetch_spx_price()
        
        if inputs["vix_manual"]:
            vix_current, vix_source = inputs["vix_manual"], "MANUAL"
        else:
            vix_current, vix_source = fetch_vix_price()
            if vix_current is None:
                vix_current, vix_source = 16.0, "DEFAULT"
        
        es_candles = fetch_es_30min_candles()
    
    if current_price is None:
        st.error("❌ SPX PRICE UNAVAILABLE")
        st.stop()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # MA Bias
    if inputs["ma_override"] != "AUTO":
        ma_bias = {"signal": inputs["ma_override"], "score": 25 if inputs["ma_override"] != "NEUTRAL" else 0, "ema_50": None, "sma_200": None}
    else:
        ma_bias = calculate_ma_bias(es_candles)
    
    # Reference time for structure calculation
    reference_time = CT.localize(datetime.combine(inputs["trading_date"], time(inputs["ref_hour"], inputs["ref_min"])))
    
    # All 4 Trades - calculated to REFERENCE TIME (not current time)
    all_trades = calculate_all_trades(
        inputs["on_high_price"], inputs["on_high_time"],
        inputs["on_low_price"], inputs["on_low_time"],
        reference_time, current_price, reference_time,
        inputs["pm_high"], inputs["pm_low"]
    )
    
    # Momentum - pass MA bias for midline reversion strategy
    momentum = calculate_momentum(es_candles, ma_bias["signal"])
    
    # VIX
    vix = analyze_vix(vix_current, inputs["vix_on_high"], inputs["vix_on_low"])
    
    # Cones - also use reference time for consistency
    cones = calculate_cones(
        inputs["prior_high"], inputs["prior_high_time"],
        inputs["prior_low"], inputs["prior_low_time"],
        inputs["prior_close"], inputs["prior_close_time"],
        reference_time
    )
    
    # Confluence
    confluences = detect_confluence(all_trades, cones, current_price)
    
    # Fetch option prices from Polygon
    strikes_needed = list(set([t["strike"] for t in all_trades["trades"].values()]))
    option_data = fetch_options_for_strikes(inputs["trading_date"], strikes_needed)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HERO HEADER
    # ═══════════════════════════════════════════════════════════════════════════
    
    ref_time_str = f"{inputs['ref_hour']}:{inputs['ref_min']:02d} AM CT"
    
    # Determine market status and color
    market_hour = now_ct.hour
    market_status = "🟢 LIVE" if 8 <= market_hour < 15 else "🟡 PRE" if market_hour < 8 else "🔴 CLOSED"
    status_color = "var(--success)" if "LIVE" in market_status else "var(--warning)" if "PRE" in market_status else "var(--danger)"
    
    st.markdown(f'''
    <div class="hero-header">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
            <div class="hero-title">🔮 SPX PROPHET V5.2</div>
            <div style="background:rgba(255,255,255,0.05);padding:6px 12px;border-radius:20px;border:1px solid var(--border-primary)">
                <span style="font-size:11px;font-weight:600;color:{status_color}">{market_status}</span>
            </div>
        </div>
        <div class="hero-subtitle">Institutional 0DTE Analytics | Structure @ {ref_time_str} | Slope: {SLOPE}</div>
        <div class="hero-price">{current_price:,.2f}</div>
        <div class="hero-time">{now_ct.strftime("%I:%M:%S %p CT")} | {inputs["trading_date"].strftime("%A, %B %d, %Y")}</div>
        <div style="position:absolute;bottom:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent 0%,var(--info) 50%,transparent 100%);animation:pulse-bar 3s infinite"></div>
    </div>
    <style>
    @keyframes pulse-bar {{
        0%, 100% {{ opacity: 0.3; }}
        50% {{ opacity: 1; }}
    }}
    </style>
    ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PILLARS ROW
    # ═══════════════════════════════════════════════════════════════════════════
    
    p1, p2, p3 = st.columns(3)
    
    with p1:
        ma_class = "calls" if ma_bias["signal"] == "LONG" else "puts" if ma_bias["signal"] == "SHORT" else "neutral"
        st.markdown(f'''
        <div class="card">
            <div class="card-header">
                <div class="card-icon blue">📊</div>
                <div><div class="card-title">MA Bias</div><div class="card-subtitle">Direction Filter</div></div>
            </div>
            <span class="signal-badge {ma_class}">{ma_bias["signal"]}</span>
            <div class="pillar-item" style="margin-top:12px"><span class="pillar-name">50 EMA</span><span class="pillar-value">{ma_bias.get("ema_50") or "—"}</span></div>
            <div class="pillar-item"><span class="pillar-name">200 SMA</span><span class="pillar-value">{ma_bias.get("sma_200") or "—"}</span></div>
        </div>
        ''', unsafe_allow_html=True)
    
    with p2:
        # Momentum signal colors
        if momentum["signal"] in ["PULLBACK BUY", "BULLISH"]:
            mom_class = "calls"
        elif momentum["signal"] in ["BOUNCE SELL", "BEARISH"]:
            mom_class = "puts"
        elif momentum["signal"] in ["OVERBOUGHT", "OVERSOLD", "WAIT"]:
            mom_class = "neutral"
        else:
            mom_class = "neutral"
        
        st.markdown(f'''
        <div class="card">
            <div class="card-header">
                <div class="card-icon green">📈</div>
                <div><div class="card-title">Momentum</div><div class="card-subtitle">RSI Midline + MACD</div></div>
            </div>
            <span class="signal-badge {mom_class}">{momentum["signal"]}</span>
            <div class="pillar-item" style="margin-top:12px"><span class="pillar-name">RSI (14)</span><span class="pillar-value">{momentum["rsi"]} <span style="font-size:10px;color:rgba(255,255,255,0.5)">({momentum["rsi_zone"]})</span></span></div>
            <div class="pillar-item"><span class="pillar-name">MACD Hist</span><span class="pillar-value" style="color:{var(--success) if momentum["macd_direction"] == "GREEN" else var(--danger)}">{momentum["macd_histogram"]:+.2f}</span></div>
            <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05)">{momentum["detail"]}</div>
        </div>
        ''', unsafe_allow_html=True)
    
    with p3:
        vix_class = "calls" if vix["bias"] == "CALLS" else "puts" if vix["bias"] == "PUTS" else "neutral"
        st.markdown(f'''
        <div class="card">
            <div class="card-header">
                <div class="card-icon red">⚡</div>
                <div><div class="card-title">VIX</div><div class="card-subtitle">{vix["zone"]}</div></div>
            </div>
            <span class="signal-badge {vix_class}">{vix["bias"]}</span>
            <div class="pillar-item" style="margin-top:12px"><span class="pillar-name">Current</span><span class="pillar-value">{vix["current"]:.2f}</span></div>
            <div class="pillar-item"><span class="pillar-name">Position</span><span class="pillar-value">{vix["position_pct"]:.0f}%</span></div>
        </div>
        ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CHANNEL ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Get PCR and retail bias
    if inputs["use_auto_pcr"]:
        pcr, pcr_status = fetch_pcr_from_polygon(inputs["trading_date"])
        retail_bias, bias_desc = get_retail_bias(pcr)
    else:
        pcr, pcr_status = None, "MANUAL"
        retail_bias = inputs["retail_bias_override"] or "NEUTRAL"
        bias_desc = f"Manual: {retail_bias}"
    
    # Run channel analysis
    channel_analysis = analyze_channel(
        inputs["channel_type"],
        inputs["breakout_dir"],
        retail_bias,
        all_trades,
        cones
    )
    
    # Display Channel Analysis Card (only when both channel and breakout are selected)
    if inputs["channel_type"] != "UNDETERMINED" and inputs["breakout_dir"] != "NONE":
        st.markdown("### 🎯 Channel Analysis")
        
        # Determine colors using new design system
        if channel_analysis["trade_bias"] == "CALLS":
            bias_color = "var(--success)"
            bias_icon = "📈"
        elif channel_analysis["trade_bias"] == "PUTS":
            bias_color = "var(--danger)"
            bias_icon = "📉"
        else:
            bias_color = "var(--warning)"
            bias_icon = "⏳"
        
        # PCR display
        pcr_display = f"{pcr:.2f}" if pcr else "N/A"
        pcr_color = "var(--success)" if retail_bias == "HEAVY_CALLS" else "var(--danger)" if retail_bias == "HEAVY_PUTS" else "var(--warning)"
        
        # Format prices safely
        primary_price_str = f"{channel_analysis['primary_target_price']:.2f}" if channel_analysis["primary_target_price"] else "—"
        secondary_price_str = f"{channel_analysis['secondary_target_price']:.2f}" if channel_analysis["secondary_target_price"] else "—"
        primary_target_name = channel_analysis["primary_target"] or "—"
        secondary_target_name = channel_analysis["secondary_target"] or "—"
        primary_action = channel_analysis["primary_action"] or ""
        secondary_action = channel_analysis["secondary_action"] or ""
        analysis_text = channel_analysis["analysis"]
        retail_bias_display = retail_bias.replace("_", " ")
        trade_bias_display = channel_analysis["trade_bias"]
        channel_display = inputs["channel_type"]
        breakout_display = inputs["breakout_dir"]
        
        # Build enhanced channel card HTML
        channel_html = f'''
        <div class="card" style="border-left:4px solid {bias_color}">
            <div class="card-header">
                <div class="card-icon purple">{bias_icon}</div>
                <div>
                    <div class="card-title">MM Hunt Analysis</div>
                    <div class="card-subtitle">{channel_display} Channel | Break {breakout_display}</div>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:20px">
                <div style="text-align:center;padding:12px;background:rgba(255,255,255,0.02);border:1px solid var(--border-secondary);border-radius:12px">
                    <div style="font-size:10px;color:var(--text-tertiary);font-weight:500;margin-bottom:4px">PCR</div>
                    <div style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:600;color:{pcr_color}">{pcr_display}</div>
                </div>
                <div style="text-align:center;padding:12px;background:rgba(255,255,255,0.02);border:1px solid var(--border-secondary);border-radius:12px">
                    <div style="font-size:10px;color:var(--text-tertiary);font-weight:500;margin-bottom:4px">RETAIL BIAS</div>
                    <div style="font-size:12px;font-weight:600;color:{pcr_color}">{retail_bias_display}</div>
                </div>
                <div style="text-align:center;padding:12px;background:rgba(255,255,255,0.02);border:1px solid var(--border-secondary);border-radius:12px">
                    <div style="font-size:10px;color:var(--text-tertiary);font-weight:500;margin-bottom:4px">TRADE BIAS</div>
                    <div style="font-size:14px;font-weight:600;color:{bias_color}">{trade_bias_display}</div>
                </div>
            </div>
            <div style="background:var(--purple-bg);border:1px solid var(--purple-border);border-radius:16px;padding:16px;margin-bottom:12px">
                <div style="font-size:12px;color:var(--purple);font-weight:600;margin-bottom:8px">🎯 PRIMARY TARGET</div>
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-size:14px;font-weight:500;color:var(--text-primary)">{primary_target_name}</span>
                    <span style="font-family:JetBrains Mono,monospace;font-size:20px;font-weight:600;color:{bias_color}">{primary_price_str}</span>
                </div>
                <div style="font-size:11px;color:var(--text-tertiary);margin-top:4px">{primary_action}</div>
            </div>
            <div style="background:var(--success-bg);border:1px solid var(--success-border);border-radius:16px;padding:16px;margin-bottom:12px">
                <div style="font-size:12px;color:var(--success);font-weight:600;margin-bottom:8px">📈 THEN TARGET</div>
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-size:14px;font-weight:500;color:var(--text-primary)">{secondary_target_name}</span>
                    <span style="font-family:JetBrains Mono,monospace;font-size:20px;font-weight:600;color:var(--text-primary)">{secondary_price_str}</span>
                </div>
                <div style="font-size:11px;color:var(--text-tertiary);margin-top:4px">{secondary_action}</div>
            </div>
            <div style="font-size:12px;color:var(--text-secondary);margin-top:16px;padding:12px;background:rgba(255,255,255,0.02);border-radius:12px;border:1px solid var(--border-secondary)">
                💡 {analysis_text}
            </div>
        </div>
        '''
        
        st.markdown(channel_html, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ALL 4 TRADES
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.markdown("### 📊 All Trade Setups")
    
    # Display in 2 columns
    col1, col2 = st.columns(2)
    
    for idx, key in enumerate(all_trades["sorted_keys"]):
        trade = all_trades["trades"][key]
        
        # Get option data from Polygon
        opt_key = f"{trade['strike']}_{trade['entry_type'][:-1]}"  # Remove 'S' from CALLS/PUTS
        opt_quote = option_data.get(opt_key, {})
        
        # Calculate projections
        projections = calculate_trade_projections(
            trade, current_price, opt_quote,
            vix_current, expiry_time, now_ct
        )
        
        # Check for confluence
        has_confluence = any(c["trade_key"] == key for c in confluences)
        
        # Determine card class
        if trade["status"] == "AT_LEVEL":
            card_class = "at-level"
        elif trade["status"] == "BROKEN":
            card_class = "broken"
        elif trade["status"] == "APPROACHING":
            card_class = "active"
        else:
            card_class = ""
        
        status_class = trade["status"].lower().replace("_", "-")
        entry_color = "#00d4aa" if trade["entry_type"] == "CALLS" else "#ff4757"
        
        # Build exit targets HTML with enhanced styling
        exit_rows = ""
        for et in projections["exit_targets"]:
            profit_color = "var(--success)" if et["profit_pct"] > 0 else "var(--danger)"
            exit_rows += f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.02)"><span style="color:var(--text-secondary);font-weight:500">SPX {et["spx_target"]:.0f} ({et["move"]})</span><span style="color:{profit_color};font-weight:600;font-family:JetBrains Mono,monospace">${et["option_price"]:.2f} ({et["profit_pct"]:+.0f}%)</span></div>'
        
        # Confluence badge with enhanced styling
        conf_badge = '<span style="margin-left:8px;background:var(--purple);color:white;padding:4px 10px;border-radius:12px;font-size:9px;font-weight:600;letter-spacing:0.05em">CONFLUENCE</span>' if has_confluence else ""
        
        # Est. label if prices are estimated
        est_label = " (Est.)" if projections["is_estimated"] else ""
        
        # Updated color variables for new design system
        entry_color = "var(--success)" if trade["entry_type"] == "CALLS" else "var(--danger)"
        
        # Build the complete trade card HTML with enhanced design
        html = f'''<div class="trade-card {card_class}">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
<div><span style="font-family:Inter,sans-serif;font-size:20px;font-weight:700;color:{entry_color}">{trade["name"]}</span>{conf_badge}</div>
<span class="trade-status {status_class}">{trade["status"].replace("_", " ")}</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;font-size:13px"><span style="color:var(--text-secondary);font-weight:500">Entry Level</span><span style="font-family:JetBrains Mono,monospace;font-weight:600;color:var(--text-primary)">{trade["level"]:.2f}</span></div>
<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;font-size:13px"><span style="color:var(--text-secondary);font-weight:500">Distance</span><span style="font-family:JetBrains Mono,monospace;font-weight:600;color:var(--text-primary)">{trade["distance"]:+.1f} pts</span></div>
<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;font-size:13px"><span style="color:var(--text-secondary);font-weight:500">Strike</span><span style="font-family:JetBrains Mono,monospace;font-weight:600;color:{entry_color}">{trade["strike"]} {trade["entry_type"][:-1]}</span></div>
<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;font-size:13px"><span style="color:var(--text-secondary);font-weight:500">Anchor</span><span style="font-family:JetBrains Mono,monospace;font-weight:600;color:var(--text-primary)">{trade["anchor"]:.2f}</span></div>
</div>
<div style="background:var(--purple-bg);border:1px solid var(--purple-border);border-radius:16px;padding:16px;margin-bottom:12px">
<div style="font-size:12px;color:var(--purple);font-weight:600;margin-bottom:12px">💰 Option Pricing{est_label}</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:12px;text-align:center">
<div style="background:rgba(255,255,255,0.02);padding:10px;border-radius:8px"><div style="color:var(--text-tertiary);font-size:10px;font-weight:500;margin-bottom:4px">CURRENT</div><div style="font-family:JetBrains Mono,monospace;font-weight:600;color:var(--text-primary)">${projections["current_option_price"]:.2f}</div></div>
<div style="background:rgba(255,255,255,0.02);padding:10px;border-radius:8px"><div style="color:var(--text-tertiary);font-size:10px;font-weight:500;margin-bottom:4px">@ ENTRY</div><div style="font-family:JetBrains Mono,monospace;font-weight:600;color:var(--info)">${projections["entry_price_est"]:.2f}</div></div>
</div>
</div>
<div style="background:var(--success-bg);border:1px solid var(--success-border);border-radius:16px;padding:16px">
<div style="font-size:11px;color:var(--success);font-weight:600;margin-bottom:8px">📈 EXIT TARGETS</div>
{exit_rows}
</div>
</div>'''
        
        if idx % 2 == 0:
            col1.markdown(html, unsafe_allow_html=True)
        else:
            col2.markdown(html, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONFLUENCE ZONES
    # ═══════════════════════════════════════════════════════════════════════════
    
    if confluences:
        st.markdown("### 🟣 Confluence Zones")
        conf_html = ""
        for c in confluences[:5]:
            conf_html += f'<tr><td>{c["trade"]}</td><td>{c["cone"]}</td><td>{c["avg_price"]:.2f}</td><td>{c["dist_from_current"]:.1f}</td></tr>'
        
        st.markdown(f'''
        <div class="card">
            <table class="data-table">
                <thead><tr><th>Structure</th><th>Cone</th><th>Level</th><th>Distance</th></tr></thead>
                <tbody>{conf_html}</tbody>
            </table>
        </div>
        ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONE RAILS
    # ═══════════════════════════════════════════════════════════════════════════
    
    with st.expander("📊 Cone Rails"):
        cone_rows = "".join([f'<tr><td>{n}</td><td>{c["anchor"]:.2f}</td><td class="table-up">{c["asc"]:.2f}</td><td class="table-down">{c["desc"]:.2f}</td><td>{c["blocks"]}</td></tr>' for n, c in cones.items()])
        st.markdown(f'<div class="card"><table class="data-table"><thead><tr><th>Cone</th><th>Anchor</th><th>Asc</th><th>Desc</th><th>Blocks</th></tr></thead><tbody>{cone_rows}</tbody></table></div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DEBUG
    # ═══════════════════════════════════════════════════════════════════════════
    
    if inputs["show_debug"]:
        st.markdown("### 🔧 Debug")
        
        st.markdown(f"**Reference Time:** {reference_time.strftime('%Y-%m-%d %I:%M %p %Z')}")
        st.markdown(f"**Current Time:** {now_ct.strftime('%Y-%m-%d %I:%M %p %Z')}")
        st.markdown(f"**O/N High Time:** {inputs['on_high_time'].strftime('%Y-%m-%d %I:%M %p %Z')}")
        st.markdown(f"**O/N Low Time:** {inputs['on_low_time'].strftime('%Y-%m-%d %I:%M %p %Z')}")
        
        st.markdown("**Block Calculations:**")
        for key, trade in all_trades["trades"].items():
            st.markdown(f"**{trade['name']}**: Anchor {trade['anchor']:.2f} | Blocks: {trade['blocks']} | Exp: ±{trade['expansion']:.2f} | Level: {trade['level']:.2f}")
        
        st.markdown("**Option Data from Polygon:**")
        if option_data:
            st.json(option_data)
        else:
            st.warning("No option data received from Polygon")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.markdown(f'<div class="app-footer">SPX PROPHET V5.2 | Slope: {SLOPE} | {now_ct.strftime("%H:%M:%S CT")}</div>', unsafe_allow_html=True)
    
    if inputs["auto_refresh"]:
        time_module.sleep(inputs["refresh_sec"])
        st.rerun()

if __name__ == "__main__":
    main()
