from __future__ import annotations
import io, zipfile
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# ===== APPLICATION METADATA =====
APP_NAME = "MarketLens Pro"
VERSION = "4.0.0"
COMPANY = "Quantum Trading Systems"
TAGLINE = "Advanced SPX Forecasting & Analytics Platform"

# ===== STRATEGY CONSTANTS =====
SPX_SLOPES_DOWN = {"HIGH": -0.2792, "CLOSE": -0.2792, "LOW": -0.2792}
SPX_SLOPES_UP   = {"HIGH": +0.3171, "CLOSE": +0.3171, "LOW": +0.3171}
TICK = 0.25
BASELINE_DATE_STR = "2000-01-01"

# ===== DESIGN SYSTEM CONSTANTS =====
# Apple-Tesla inspired color palette
COLORS = {
    # Primary brand colors
    "primary": "#007AFF",      # Apple blue
    "primary_dark": "#0056CC", # Darker blue
    "secondary": "#5AC8FA",    # Light blue
    "accent": "#FF3B30",       # Apple red
    
    # Tesla-inspired gradients
    "tesla_red": "#E31937",
    "tesla_black": "#171A20",
    "tesla_white": "#FFFFFF",
    "tesla_gray": "#393C41",
    
    # Status colors
    "success": "#34C759",      # Apple green
    "warning": "#FF9500",      # Apple orange
    "error": "#FF3B30",        # Apple red
    "info": "#007AFF",         # Apple blue
    
    # Neutral colors
    "gray_50": "#F9FAFB",
    "gray_100": "#F3F4F6", 
    "gray_200": "#E5E7EB",
    "gray_300": "#D1D5DB",
    "gray_400": "#9CA3AF",
    "gray_500": "#6B7280",
    "gray_600": "#4B5563",
    "gray_700": "#374151",
    "gray_800": "#1F2937",
    "gray_900": "#111827",
    
    # Market colors
    "bull": "#00D4AA",         # Vibrant green
    "bear": "#FF6B6B",         # Vibrant red
    "neutral": "#8B5CF6",      # Purple
}

# Icons with modern Unicode symbols
ICONS = {
    "high": "📈",
    "close": "⚡",
    "low": "📉",
    "trending_up": "↗️",
    "trending_down": "↘️",
    "analytics": "🔍",
    "settings": "⚙️",
    "export": "📊",
    "fibonacci": "🌀",
    "contract": "📋",
    "live": "🔴"
}

# Typography scale
FONT_SIZES = {
    "xs": "0.75rem",
    "sm": "0.875rem", 
    "base": "1rem",
    "lg": "1.125rem",
    "xl": "1.25rem",
    "2xl": "1.5rem",
    "3xl": "1.875rem",
    "4xl": "2.25rem"
}

# ===== TRADING RULES & STRATEGIES =====
SPX_GOLDEN_RULES = [
    "🎯 Exit levels are exits - never entries",
    "🧲 Anchors are magnets, not timing signals - let price come to you", 
    "⏰ The market will give you your entry - don't force it",
    "📊 Consistency in process trumps perfection in prediction",
    "🤔 When in doubt, stay out - there's always another trade",
    "🚫 SPX ignores the full 16:00-17:00 maintenance block",
]

SPX_ANCHOR_RULES = {
    "rth_breaks": [
        "📉 30-min close below RTH entry anchor: price may retrace above anchor line but will fall below again shortly after",
        "🚀 Don't chase the bounce: prepare for the inevitable breakdown", 
        "✅ Wait for confirmation: let the market give you the entry",
    ],
    "extended_hours": [
        "🌙 Extended session weakness + recovery: use recovered anchor as buy signal in RTH",
        "⚡ Extended session anchors carry forward momentum into regular trading hours",
        "📈 Extended bounce of anchors carry forward momentum into regular trading hours", 
        "🌅 Overnight anchor recovery: strong setup for next day strength",
    ],
    "mon_wed_fri": [
        "📅 No touch of high, close, or low anchors on Mon/Wed/Fri = potential sell day later",
        "🎯 Don't trade TO the anchor: let the market give you the entry",
        "⏳ Wait for price action confirmation rather than anticipating touches",
    ],
    "fibonacci_bounce": [
        "🎯 SPX Line Touch + Bounce: when SPX price touches line and bounces, contract follows the same pattern",
        "📐 0.786 Fibonacci Entry: contract retraces to 0.786 fib level (low to high of bounce) = major algo entry point",
        "⏰ Next Hour Candle: the 0.786 retracement typically occurs in the NEXT hour candle, not the same one", 
        "🎪 High Probability: algos consistently enter at 0.786 level for profitable runs",
        "✨ Setup Requirements: clear bounce off SPX line + identifiable low-to-high swing for fib calculation",
    ],
}

CONTRACT_STRATEGIES = {
    "tuesday_play": [
        "🔍 Identify two overnight option low points that rise $400-$500",
        "📈 Use them to set Tuesday contract slope",
        "⚡ Tuesday contract setups often provide best mid-week momentum",
    ],
    "thursday_play": [
        "💰 If Wednesday's low premium was cheap: Thursday low ≈ Wed low (buy-day)",
        "📉 If Wednesday stayed pricey: Thursday likely a put-day (avoid longs)",
        "📊 Wednesday pricing telegraphs Thursday direction",
    ],
}

TIME_RULES = {
    "market_sessions": [
        "🌅 8:30 - 9:30 AM: initial range, avoid FOMO entries",
        "💼 10:30 - 12:30 AM: institutional flow window, best entries",
        "🚀 2:00 - 3:00 PM: final push time, momentum plays", 
    ],
    "volume_patterns": [
        "📊 Entry volume > 20-day average: strong conviction signal",
        "📉 Declining volume on bounces: fade the move",
        "💥 Volume spike + anchor break: high probability setup",
    ],
    "multi_timeframe": [
        "🎯 5-min + 15-min + 1-hour all pointing same direction = high conviction",
        "⚖️ Conflicting timeframes = wait for resolution",
        "🏆 Daily anchor + intraday setup = strongest edge",
    ],
}

RISK_RULES = {
    "position_sizing": [
        "🛡️ Never risk more than 2% per trade: consistency beats home runs",
        "📊 Scale into positions: 1/3 initial, 1/3 confirmation, 1/3 momentum",
        "📅 Reduce size on Fridays: weekend risk isn't worth it",
    ],
    "stop_strategy": [
        "🚨 Hard stops at -15% for options: no exceptions",
        "📈 Trailing stops after +25%: protect profits aggressively", 
        "⏰ Time stops at 3:45 PM: avoid close volatility",
    ],
    "market_context": [
        "📊 VIX above 25: reduce position sizes by 50%",
        "📈 Major earnings week: avoid unrelated tickers",
        "📰 FOMC/CPI days: trade post-announcement only (10:30+ AM)",
    ],
    "psychological": [
        "😤 3 losses in a row: step away for 1 hour minimum",
        "🎉 Big win euphoria: reduce next position size by 50%",
        "😡 Revenge trading: automatic day-end (no exceptions)",
    ],
    "performance_targets": [
        "🎯 Win rate target: 55%+",
        "💰 Risk/reward minimum: 1:1.5", 
        "📊 Weekly P&L cap: stop after +20% or -10% weekly moves",
    ],
}
# ===== REVOLUTIONARY CSS DESIGN SYSTEM =====
# Apple-Tesla inspired premium interface with glassmorphism and micro-interactions

CSS_DESIGN_SYSTEM = """
<style>
/* === FONT IMPORTS === */
@import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@100;200;300;400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@100;200;300;400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@100;200;300;400;500;600;700;800&display=swap');

/* === CSS VARIABLES - APPLE-TESLA DESIGN SYSTEM === */
:root {
  /* Primary Brand Colors */
  --primary: #007AFF;
  --primary-dark: #0056CC;
  --primary-light: #5AC8FA;
  --secondary: #5856D6;
  --accent: #FF3B30;
  
  /* Tesla Inspired */
  --tesla-red: #E31937;
  --tesla-black: #171A20;
  --tesla-white: #FFFFFF;
  --tesla-gray: #393C41;
  --tesla-silver: #F4F4F4;
  
  /* Status Colors */
  --success: #34C759;
  --warning: #FF9500;
  --error: #FF3B30;
  --info: #007AFF;
  
  /* Market Colors */
  --bull: #00D4AA;
  --bear: #FF6B6B;
  --neutral: #8B5CF6;
  
  /* Light Theme */
  --bg-primary: #FFFFFF;
  --bg-secondary: #F2F2F7;
  --bg-tertiary: #FFFFFF;
  --surface: #FFFFFF;
  --surface-elevated: #FFFFFF;
  --border: rgba(0,0,0,0.08);
  --border-strong: rgba(0,0,0,0.15);
  --text-primary: #000000;
  --text-secondary: #3C3C43;
  --text-tertiary: #8E8E93;
  --text-quaternary: #C7C7CC;
  
  /* Shadows */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.06);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.08), 0 4px 6px rgba(0,0,0,0.05);
  --shadow-xl: 0 20px 25px rgba(0,0,0,0.1), 0 10px 10px rgba(0,0,0,0.04);
  --shadow-2xl: 0 25px 50px rgba(0,0,0,0.15);
  
  /* Glassmorphism */
  --glass-bg: rgba(255,255,255,0.25);
  --glass-border: rgba(255,255,255,0.18);
  --backdrop-blur: blur(20px);
  
  /* Spacing Scale */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-10: 2.5rem;
  --space-12: 3rem;
  --space-16: 4rem;
  --space-20: 5rem;
  
  /* Border Radius */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-2xl: 1.5rem;
  --radius-3xl: 2rem;
  
  /* Typography Scale */
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
  --text-2xl: 1.5rem;
  --text-3xl: 1.875rem;
  --text-4xl: 2.25rem;
  --text-5xl: 3rem;
  
  /* Transitions */
  --transition-fast: 150ms ease-in-out;
  --transition-normal: 250ms ease-in-out;
  --transition-slow: 350ms ease-in-out;
}

/* === DARK THEME === */
[data-theme="dark"] {
  --bg-primary: #000000;
  --bg-secondary: #1C1C1E;
  --bg-tertiary: #2C2C2E;
  --surface: #1C1C1E;
  --surface-elevated: #2C2C2E;
  --border: rgba(255,255,255,0.1);
  --border-strong: rgba(255,255,255,0.2);
  --text-primary: #FFFFFF;
  --text-secondary: #EBEBF5;
  --text-tertiary: #EBEBF5;
  --text-quaternary: #48484A;
  
  --glass-bg: rgba(0,0,0,0.25);
  --glass-border: rgba(255,255,255,0.1);
  
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.4);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.3), 0 2px 4px rgba(0,0,0,0.4);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.4), 0 4px 6px rgba(0,0,0,0.3);
  --shadow-xl: 0 20px 25px rgba(0,0,0,0.5), 0 10px 10px rgba(0,0,0,0.3);
  --shadow-2xl: 0 25px 50px rgba(0,0,0,0.7);
}

/* === BASE STYLES === */
* {
  box-sizing: border-box;
}

html, body, .stApp {
  font-family: 'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  transition: background-color var(--transition-normal), color var(--transition-normal);
}

.stApp {
  background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  min-height: 100vh;
}

/* === HIDE STREAMLIT ELEMENTS === */
#MainMenu, footer, .stDeployButton, header[data-testid="stHeader"] {
  display: none !important;
}

.stAppViewContainer > .main > div:first-child {
  padding-top: var(--space-8);
}

/* === HERO SECTION === */
.hero-container {
  background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
  border-radius: var(--radius-3xl);
  padding: var(--space-12) var(--space-8);
  text-align: center;
  margin-bottom: var(--space-8);
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-2xl);
  border: 1px solid var(--glass-border);
}

.hero-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(45deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
  backdrop-filter: var(--backdrop-blur);
}

.hero-content {
  position: relative;
  z-index: 2;
}

.brand-logo {
  font-size: var(--text-5xl);
  font-weight: 800;
  color: white;
  margin-bottom: var(--space-3);
  letter-spacing: -0.02em;
  text-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.brand-tagline {
  font-size: var(--text-xl);
  color: rgba(255,255,255,0.9);
  margin-bottom: var(--space-2);
  font-weight: 400;
}

.brand-meta {
  font-size: var(--text-sm);
  color: rgba(255,255,255,0.7);
  font-weight: 300;
}

/* === GLASSMORPHISM CARDS === */
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: var(--backdrop-blur);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-2xl);
  padding: var(--space-6);
  margin: var(--space-4) 0;
  box-shadow: var(--shadow-lg);
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
}

.glass-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.2) 50%, transparent 100%);
}

.glass-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-xl);
  border-color: var(--primary);
}

.premium-card {
  background: linear-gradient(135deg, var(--surface) 0%, rgba(255,255,255,0.8) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  padding: var(--space-6);
  margin: var(--space-4) 0;
  box-shadow: var(--shadow-lg);
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
}

[data-theme="dark"] .premium-card {
  background: linear-gradient(135deg, var(--surface) 0%, rgba(44,44,46,0.8) 100%);
}

.premium-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-xl);
}

/* === SECTION HEADERS === */
.section-header {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 2px solid var(--primary);
  position: relative;
}

.section-header::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 60px;
  height: 2px;
  background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
}

.subsection-header {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-secondary);
  margin: var(--space-4) 0 var(--space-2) 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* === METRIC TILES === */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--space-6);
  margin: var(--space-6) 0;
}

.metric-tile {
  background: linear-gradient(135deg, var(--surface) 0%, rgba(255,255,255,0.5) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  text-align: center;
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-md);
}

[data-theme="dark"] .metric-tile {
  background: linear-gradient(135deg, var(--surface) 0%, rgba(44,44,46,0.5) 100%);
}

.metric-tile:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: var(--shadow-xl);
  border-color: var(--primary);
}

.metric-icon {
  font-size: var(--text-3xl);
  margin-bottom: var(--space-3);
  display: block;
}

.metric-value {
  font-size: var(--text-4xl);
  font-weight: 800;
  margin-bottom: var(--space-2);
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: -0.02em;
}

.metric-label {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-change {
  font-size: var(--text-sm);
  font-weight: 600;
  margin-top: var(--space-2);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-md);
  display: inline-block;
}

.metric-change.positive {
  background: rgba(52, 199, 89, 0.1);
  color: var(--success);
}

.metric-change.negative {
  background: rgba(255, 59, 48, 0.1);
  color: var(--error);
}

/* === LIVE PRICE STRIP === */
.live-price-container {
  background: linear-gradient(90deg, var(--tesla-black) 0%, var(--tesla-gray) 100%);
  border-radius: var(--radius-xl);
  padding: var(--space-4) var(--space-6);
  margin: var(--space-4) 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-4);
  box-shadow: var(--shadow-lg);
  border: 1px solid rgba(255,255,255,0.1);
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: white;
  font-weight: 600;
}

.live-dot {
  width: 8px;
  height: 8px;
  background: var(--tesla-red);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite alternate;
}

@keyframes pulse {
  0% { opacity: 1; }
  100% { opacity: 0.4; }
}

.price-main {
  font-size: var(--text-3xl);
  font-weight: 800;
  color: white;
  font-family: 'JetBrains Mono', monospace;
}

.price-change {
  font-size: var(--text-lg);
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
}

.price-meta {
  color: rgba(255,255,255,0.7);
  font-size: var(--text-sm);
}
</style>
"""

# ===== ENHANCED CSS UTILITIES =====
CSS_COMPONENTS = """
<style>
/* === ENHANCED BUTTONS === */
.stButton > button, .stDownloadButton > button {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%) !important;
  color: white !important;
  border: none !important;
  border-radius: var(--radius-xl) !important;
  padding: var(--space-3) var(--space-6) !important;
  font-weight: 600 !important;
  font-size: var(--text-base) !important;
  transition: all var(--transition-normal) !important;
  box-shadow: var(--shadow-md) !important;
  position: relative !important;
  overflow: hidden !important;
}

.stButton > button:hover, .stDownloadButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: var(--shadow-xl) !important;
  background: linear-gradient(135deg, var(--primary-dark) 0%, var(--secondary) 100%) !important;
}

.stButton > button:active, .stDownloadButton > button:active {
  transform: translateY(0px) !important;
}

.stButton > button::before, .stDownloadButton > button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
  transition: left 0.5s;
}

.stButton > button:hover::before, .stDownloadButton > button:hover::before {
  left: 100%;
}

/* === ENHANCED INPUTS === */
.stSelectbox > div > div, .stNumberInput > div > div > input, .stTimeInput > div > div > input {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-lg) !important;
  padding: var(--space-3) var(--space-4) !important;
  font-size: var(--text-base) !important;
  transition: all var(--transition-normal) !important;
  box-shadow: var(--shadow-sm) !important;
}

.stSelectbox > div > div:focus-within, 
.stNumberInput > div > div > input:focus, 
.stTimeInput > div > div > input:focus {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1) !important;
  outline: none !important;
}

/* === ENHANCED DATAFRAMES === */
.stDataFrame {
  border-radius: var(--radius-xl) !important;
  overflow: hidden !important;
  box-shadow: var(--shadow-lg) !important;
  border: 1px solid var(--border) !important;
}

.stDataFrame > div {
  background: var(--surface) !important;
}

/* === ENHANCED SLIDERS === */
.stSlider > div > div > div > div {
  background: var(--primary) !important;
}

.stSlider > div > div > div > div > div {
  background: white !important;
  box-shadow: var(--shadow-md) !important;
}

/* === ENHANCED RADIO BUTTONS === */
.stRadio > div {
  background: var(--surface) !important;
  border-radius: var(--radius-lg) !important;
  padding: var(--space-3) !important;
  border: 1px solid var(--border) !important;
}

/* === ENHANCED TOGGLES === */
.stCheckbox > label {
  background: var(--surface) !important;
  border-radius: var(--radius-lg) !important;
  padding: var(--space-3) var(--space-4) !important;
  border: 1px solid var(--border) !important;
  transition: all var(--transition-normal) !important;
}

.stCheckbox > label:hover {
  background: var(--bg-secondary) !important;
  border-color: var(--primary) !important;
}

/* === ENHANCED EXPANDERS === */
.streamlit-expanderHeader {
  background: var(--surface) !important;
  border-radius: var(--radius-lg) !important;
  border: 1px solid var(--border) !important;
  font-weight: 600 !important;
  transition: all var(--transition-normal) !important;
}

.streamlit-expanderHeader:hover {
  background: var(--bg-secondary) !important;
  border-color: var(--primary) !important;
}

.streamlit-expanderContent {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-top: none !important;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg) !important;
}

/* === ENHANCED SIDEBAR === */
.css-1d391kg {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}

.css-1d391kg .css-1v0mbdj {
  background: var(--surface) !important;
}

/* === SCROLLBAR STYLING === */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: var(--radius-md);
  transition: background var(--transition-normal);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-tertiary);
}

/* === ANIMATIONS === */
@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes shimmer {
  0% { background-position: -468px 0; }
  100% { background-position: 468px 0; }
}

.animate-slide-up {
  animation: slideInUp 0.6s ease-out;
}

.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}

/* === RESPONSIVE DESIGN === */
@media (max-width: 768px) {
  .hero-container {
    padding: var(--space-8) var(--space-4);
  }
  
  .brand-logo {
    font-size: var(--text-4xl);
  }
  
  .metrics-grid {
    grid-template-columns: 1fr;
  }
  
  .live-price-container {
    flex-direction: column;
    text-align: center;
  }
}

@media (max-width: 480px) {
  .brand-logo {
    font-size: var(--text-3xl);
  }
  
  .metric-value {
    font-size: var(--text-3xl);
  }
}
</style>
"""
# ===== ADVANCED DARK MODE SYSTEM =====
DARK_MODE_SCRIPT = """
<script>
// Advanced Theme Management System
class ThemeManager {
    constructor() {
        this.theme = localStorage.getItem('marketlens-theme') || 'light';
        this.init();
    }
    
    init() {
        this.applyTheme(this.theme);
        this.setupEventListeners();
    }
    
    applyTheme(theme) {
        const body = window.parent.document.body;
        const root = window.parent.document.documentElement;
        
        if (theme === 'dark') {
            body.setAttribute('data-theme', 'dark');
            root.setAttribute('data-theme', 'dark');
            body.classList.add('dark-mode');
        } else {
            body.setAttribute('data-theme', 'light');
            root.setAttribute('data-theme', 'light');
            body.classList.remove('dark-mode');
        }
        
        // Smooth transition effect
        body.style.transition = 'background-color 0.3s ease, color 0.3s ease';
        setTimeout(() => {
            body.style.transition = '';
        }, 300);
    }
    
    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('marketlens-theme', this.theme);
        this.applyTheme(this.theme);
        return this.theme;
    }
    
    setTheme(theme) {
        this.theme = theme;
        localStorage.setItem('marketlens-theme', theme);
        this.applyTheme(theme);
    }
    
    setupEventListeners() {
        // Listen for system theme changes
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addListener((e) => {
            if (!localStorage.getItem('marketlens-theme')) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    }
}

// Initialize theme manager
window.themeManager = new ThemeManager();

// Global functions for Streamlit
window.setMarketLensTheme = (theme) => {
    window.themeManager.setTheme(theme);
};

window.toggleMarketLensTheme = () => {
    return window.themeManager.toggleTheme();
};

// Auto-detect system preference if no saved preference
if (!localStorage.getItem('marketlens-theme')) {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    window.themeManager.setTheme(prefersDark ? 'dark' : 'light');
}
</script>
"""

# ===== ENHANCED UTILITY FUNCTIONS =====
RTH_START, RTH_END = time(8, 30), time(15, 30)

def spx_blocks_between(t1: datetime, t2: datetime) -> int:
    """
    Calculate SPX blocks between two datetimes, excluding 16:00-16:59 maintenance window.
    Enhanced with error handling and validation.
    """
    if not isinstance(t1, datetime) or not isinstance(t2, datetime):
        raise ValueError("Both arguments must be datetime objects")
    
    if t2 < t1:
        t1, t2 = t2, t1
    
    blocks = 0
    current = t1
    
    while current < t2:
        # Skip the 16:00-16:59 maintenance block
        if current.hour != 16:
            blocks += 1
        current += timedelta(minutes=30)
    
    return blocks

def make_time_slots(start: time, end: time, step_minutes: int = 30) -> List[str]:
    """
    Generate time slots between start and end times.
    Enhanced with validation and flexible step sizes.
    """
    if not isinstance(start, time) or not isinstance(end, time):
        raise ValueError("Start and end must be time objects")
    
    if step_minutes <= 0:
        raise ValueError("Step minutes must be positive")
    
    slots = []
    current = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    
    # Handle next-day scenarios
    if end_dt < current:
        end_dt += timedelta(days=1)
    
    while current <= end_dt:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=step_minutes)
    
    return slots

def round_to_tick(value: float, tick: float = TICK) -> float:
    """
    Round value to nearest tick size with enhanced precision handling.
    """
    if tick <= 0:
        return float(value)
    
    rounded = round(value / tick) * tick
    return round(rounded, 4)  # Enhanced precision

def project_price(anchor_price: float, slope_per_block: float, blocks: int) -> float:
    """
    Project price based on anchor, slope, and block count.
    Enhanced with validation and precision handling.
    """
    if not isinstance(anchor_price, (int, float)) or anchor_price <= 0:
        raise ValueError("Anchor price must be a positive number")
    
    if not isinstance(blocks, int) or blocks < 0:
        raise ValueError("Blocks must be a non-negative integer")
    
    projected = anchor_price + (slope_per_block * blocks)
    return round_to_tick(projected)

# ===== ENHANCED TIME UTILITIES =====
SPX_SLOTS = make_time_slots(RTH_START, RTH_END)
EXTENDED_SLOTS = make_time_slots(time(7, 30), RTH_END)

def is_trading_hours(dt: datetime) -> bool:
    """Check if datetime falls within regular trading hours."""
    time_only = dt.time()
    return RTH_START <= time_only <= RTH_END

def is_maintenance_hour(dt: datetime) -> bool:
    """Check if datetime falls within maintenance window."""
    return dt.hour == 16

def get_next_trading_slot(current_time: time) -> Optional[str]:
    """Get the next available trading slot after current time."""
    current_str = current_time.strftime("%H:%M")
    
    for slot in SPX_SLOTS:
        if slot > current_str:
            return slot
    
    return None

def calculate_trading_minutes_remaining(current_time: time) -> int:
    """Calculate minutes remaining in trading session."""
    if current_time >= RTH_END:
        return 0
    
    current_dt = datetime.combine(date.today(), current_time)
    end_dt = datetime.combine(date.today(), RTH_END)
    
    return int((end_dt - current_dt).total_seconds() / 60)

# ===== STATE MANAGEMENT SYSTEM =====
class MarketLensState:
    """Enhanced state management for MarketLens Pro."""
    
    def __init__(self):
        self.initialize_state()
    
    def initialize_state(self):
        """Initialize all session state variables with defaults."""
        defaults = {
            # Core application state
            'initialized': True,
            'theme': 'light',
            'print_mode': False,
            
            # Anchor state
            'anchors_locked': False,
            'forecasts_generated': False,
            
            # Contract state
            'contract': {
                'anchor_time': None,
                'anchor_price': None,
                'slope': None,
                'label': 'Manual'
            },
            
            # UI state
            'sidebar_expanded': True,
            'auto_refresh': False,
            'refresh_interval': 60,
            
            # Advanced features
            'risk_alerts_enabled': True,
            'sound_notifications': False,
            'advanced_charts': True,
            
            # User preferences
            'default_tolerance': 0.50,
            'preferred_timeframe': '30min',
            'chart_theme': 'professional',
            
            # Performance tracking
            'session_start_time': datetime.now(),
            'page_loads': 0,
            'last_data_refresh': None,
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
        
        # Increment page loads
        st.session_state.page_loads += 1
    
    def reset_forecasts(self):
        """Reset forecast-related state."""
        st.session_state.forecasts_generated = False
        st.session_state.anchors_locked = False
    
    def save_user_preferences(self):
        """Save user preferences to browser storage."""
        preferences = {
            'theme': st.session_state.theme,
            'default_tolerance': st.session_state.default_tolerance,
            'auto_refresh': st.session_state.auto_refresh,
            'advanced_charts': st.session_state.advanced_charts,
        }
        
        # This would typically save to a database or local storage
        # For now, we'll just update session state
        st.session_state.user_preferences = preferences

# ===== ENHANCED DATA VALIDATION =====
class DataValidator:
    """Comprehensive data validation for trading inputs."""
    
    @staticmethod
    def validate_price(price: float, min_price: float = 0.01, max_price: float = 10000.0) -> bool:
        """Validate price input with reasonable bounds."""
        try:
            price = float(price)
            return min_price <= price <= max_price
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_time_input(time_input: time) -> bool:
        """Validate time input for trading hours."""
        if not isinstance(time_input, time):
            return False
        
        # Allow extended hours for flexibility
        extended_start = time(6, 0)
        extended_end = time(20, 0)
        
        return extended_start <= time_input <= extended_end
    
    @staticmethod
    def validate_date_input(date_input: date) -> Tuple[bool, str]:
        """Validate date input with helpful error messages."""
        if not isinstance(date_input, date):
            return False, "Invalid date format"
        
        today = date.today()
        
        if date_input < today - timedelta(days=7):
            return False, "Date cannot be more than 7 days in the past"
        
        if date_input > today + timedelta(days=30):
            return False, "Date cannot be more than 30 days in the future"
        
        # Check if it's a weekend
        if date_input.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False, "Selected date falls on a weekend"
        
        return True, "Valid date"
    
    @staticmethod
    def validate_slope(slope: float) -> Tuple[bool, str]:
        """Validate slope values for reasonableness."""
        try:
            slope = float(slope)
            
            if abs(slope) > 10.0:
                return False, "Slope too extreme (max ±10.0)"
            
            if slope == 0:
                return False, "Slope cannot be zero"
            
            return True, "Valid slope"
        
        except (ValueError, TypeError):
            return False, "Invalid slope format"

# ===== ENHANCED ERROR HANDLING =====
class MarketLensError(Exception):
    """Base exception for MarketLens Pro."""
    pass

class DataFetchError(MarketLensError):
    """Raised when data fetching fails."""
    pass

class ValidationError(MarketLensError):
    """Raised when input validation fails."""
    pass

class CalculationError(MarketLensError):
    """Raised when calculations fail."""
    pass

def safe_execute(func, *args, default=None, error_msg="Operation failed", **kwargs):
    """
    Safely execute a function with comprehensive error handling.
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.error(f"{error_msg}: {str(e)}")
        if default is not None:
            return default
        raise MarketLensError(f"{error_msg}: {str(e)}")

# ===== PERFORMANCE MONITORING =====
class PerformanceMonitor:
    """Monitor application performance and user interactions."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.operation_times = {}
    
    def start_operation(self, operation_name: str):
        """Start timing an operation."""
        self.operation_times[operation_name] = datetime.now()
    
    def end_operation(self, operation_name: str) -> float:
        """End timing an operation and return duration."""
        if operation_name in self.operation_times:
            duration = (datetime.now() - self.operation_times[operation_name]).total_seconds()
            del self.operation_times[operation_name]
            return duration
        return 0.0
    
    def get_session_duration(self) -> float:
        """Get total session duration in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

# ===== INITIALIZE SYSTEMS =====
# Initialize state management
state_manager = MarketLensState()

# Initialize performance monitoring
if 'performance_monitor' not in st.session_state:
    st.session_state.performance_monitor = PerformanceMonitor()

# Initialize data validator
validator = DataValidator()

# ===== STREAMLIT PAGE CONFIGURATION =====
st.set_page_config(
    page_title=f"{APP_NAME} — Enterprise SPX Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-repo/marketlens-pro',
        'Report a bug': 'https://github.com/your-repo/marketlens-pro/issues',
        'About': f"{APP_NAME} v{VERSION} - Professional SPX Forecasting Platform"
    }
)


