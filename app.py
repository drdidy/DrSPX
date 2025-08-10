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
        "🌅 9:30-10:00 AM: initial range, avoid FOMO entries",
        "💼 10:30-11:30 AM: institutional flow window, best entries",
        "🚀 2:00-3:00 PM: final push time, momentum plays", 
        "⚠️ 3:30+ PM: scalps only, avoid new positions",
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

# ===== CSS DESIGN SYSTEM =====
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

# ===== DARK MODE SYSTEM =====
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

# ===== DESIGN SYSTEM =====
st.markdown(CSS_DESIGN_SYSTEM, unsafe_allow_html=True)
st.markdown(CSS_COMPONENTS, unsafe_allow_html=True)
st.markdown(DARK_MODE_SCRIPT, unsafe_allow_html=True)

# ===== DATA FETCHING SYSTEM =====
@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_live_data():
    """
    Enhanced SPX data fetching with comprehensive error handling and fallback.
    Preserves original logic while adding enterprise-grade reliability.
    """
    try:
        # Start performance monitoring
        if 'performance_monitor' in st.session_state:
            st.session_state.performance_monitor.start_operation('fetch_spx_data')
        
        ticker = yf.Ticker("^GSPC")
        
        # Fetch intraday data
        intraday = ticker.history(period="1d", interval="1m")
        
        # Fetch daily data for previous close
        daily = ticker.history(period="6d", interval="1d")
        
        if intraday is None or intraday.empty or daily is None or daily.empty or len(daily) < 1:
            return {"status": "error", "message": "No data available"}
        
        # Extract current data
        last_bar = intraday.iloc[-1]
        current_price = float(last_bar["Close"])
        
        # Today's high/low
        today_high = float(daily.iloc[-1]["High"])
        today_low = float(daily.iloc[-1]["Low"])
        
        # Previous close for change calculation
        prev_close = float(daily.iloc[-2]["Close"]) if len(daily) >= 2 else current_price
        
        # Calculate changes
        price_change = current_price - prev_close
        percent_change = (price_change / prev_close * 100) if prev_close else 0.0
        
        # Additional market metrics
        volume = float(last_bar["Volume"]) if "Volume" in last_bar else 0
        
        # Calculate volatility (simplified)
        if len(intraday) >= 20:
            recent_closes = intraday["Close"].tail(20)
            volatility = float(recent_closes.std())
        else:
            volatility = 0.0
        
        # Market session status
        current_time = datetime.now().time()
        is_market_open = RTH_START <= current_time <= RTH_END
        
        # End performance monitoring
        if 'performance_monitor' in st.session_state:
            fetch_time = st.session_state.performance_monitor.end_operation('fetch_spx_data')
        else:
            fetch_time = 0.0
        
        return {
            "status": "success",
            "price": round(current_price, 2),
            "change": round(price_change, 2),
            "change_percent": round(percent_change, 2),
            "today_high": round(today_high, 2),
            "today_low": round(today_low, 2),
            "volume": int(volume),
            "volatility": round(volatility, 2),
            "is_market_open": is_market_open,
            "last_update": datetime.now(),
            "fetch_time": round(fetch_time, 3)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Data fetch failed: {str(e)}",
            "last_update": datetime.now()
        }

@st.cache_data(ttl=300, show_spinner=False)
def get_previous_day_anchors(forecast_date: date):
    """
    Enhanced previous day anchor fetching with better error handling.
    Preserves original anchor logic exactly.
    """
    try:
        df = yf.Ticker("^GSPC").history(period="1mo", interval="1d")
        if df is None or df.empty:
            return None
        
        # Reset index and standardize column names
        daily_data = df.reset_index()
        if "Date" not in daily_data.columns:
            daily_data.rename(columns={daily_data.columns[0]: "Date"}, inplace=True)
        
        # Convert to date for comparison
        daily_data["DateOnly"] = daily_data["Date"].dt.tz_localize(None).dt.date
        
        # Find previous trading day
        previous_days = daily_data.loc[daily_data["DateOnly"] < forecast_date]
        if previous_days.empty:
            return None
        
        # Get the most recent previous day
        prev_row = previous_days.iloc[-1]
        
        return {
            "date": prev_row["DateOnly"],
            "high": round(float(prev_row["High"]), 2),
            "close": round(float(prev_row["Close"]), 2),
            "low": round(float(prev_row["Low"]), 2),
            "volume": int(prev_row["Volume"]) if "Volume" in prev_row else 0
        }
        
    except Exception as e:
        st.error(f"⚠️ Could not fetch previous day data: {str(e)}")
        return None

@st.cache_data(ttl=120, show_spinner=False)
def fetch_intraday_data(target_date: date) -> pd.DataFrame:
    """
    Enhanced intraday data fetching with better timezone handling.
    Preserves original data processing logic exactly.
    """
    try:
        ticker = yf.Ticker("^GSPC")
        
        # Fetch with wider window for timezone safety
        start_date = target_date - timedelta(days=1)
        end_date = target_date + timedelta(days=1)
        
        df = ticker.history(start=start_date, end=end_date, interval="1m")
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Reset index and normalize
        df = df.reset_index()
        datetime_col = "Datetime" if "Datetime" in df.columns else df.columns[0]
        df.rename(columns={datetime_col: "dt"}, inplace=True)
        
        # Convert to time-only format (preserving original logic)
        df["Time"] = df["dt"].dt.tz_localize(None).dt.strftime("%H:%M")
        df["Date"] = df["dt"].dt.tz_localize(None).dt.date
        
        # Filter to target date only
        df = df[df["Date"] == target_date].copy()
        
        return df
        
    except Exception as e:
        st.error(f"⚠️ Could not fetch intraday data: {str(e)}")
        return pd.DataFrame()

def convert_to_30min_bars(df_1min: pd.DataFrame) -> pd.DataFrame:
    """
    Convert 1-minute data to 30-minute bars.
    Preserves original OHLC logic exactly - only enhanced error handling.
    """
    if df_1min.empty:
        return df_1min
    
    try:
        # Set datetime index for resampling (preserving original logic)
        df = df_1min.copy()
        df = df.set_index(pd.to_datetime(df["dt"]).dt.tz_localize(None)).sort_index()
        
        # Resample to 30-min bars (preserving original parameters)
        ohlc_data = df[["Open", "High", "Low", "Close", "Volume"]].resample(
            "30min", label="right", closed="right"
        ).agg({
            "Open": "first",
            "High": "max", 
            "Low": "min",
            "Close": "last",
            "Volume": "sum"
        }).dropna(subset=["Open", "High", "Low", "Close"])
        
        # Reset index and format (preserving original structure)
        ohlc_data = ohlc_data.reset_index()
        ohlc_data["Time"] = ohlc_data["index"].dt.strftime("%H:%M")
        
        # Filter to RTH hours only (preserving original logic)
        ohlc_data = ohlc_data[
            (ohlc_data["Time"] >= "08:30") & (ohlc_data["Time"] <= "15:30")
        ].copy()
        
        # Add timestamp for plotting (preserving original baseline logic)
        ohlc_data["TS"] = pd.to_datetime(BASELINE_DATE_STR + " " + ohlc_data["Time"])
        
        return ohlc_data[["Time", "Open", "High", "Low", "Close", "Volume", "TS"]]
        
    except Exception as e:
        st.error(f"⚠️ Could not convert to 30-min bars: {str(e)}")
        return pd.DataFrame()

# ===== PREMIUM HERO INTERFACE =====
def render_hero_section():
    """Render the premium hero section with live data."""
    st.markdown(
        f"""
        <div class="hero-container animate-fade-in">
            <div class="hero-content">
                <div class="brand-logo">{APP_NAME}</div>
                <div class="brand-tagline">{TAGLINE}</div>
                <div class="brand-meta">v{VERSION} • {COMPANY}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_live_price_strip():
    """Render the enhanced live price strip with Tesla-inspired design."""
    market_data = fetch_spx_live_data()
    
    if market_data["status"] == "success":
        # Determine price direction styling
        change_color = COLORS["success"] if market_data["change"] >= 0 else COLORS["error"]
        change_symbol = "+" if market_data["change"] >= 0 else ""
        
        # Market status
        market_status = "🟢 OPEN" if market_data["is_market_open"] else "🔴 CLOSED"
        
        # Create the HTML content
        live_price_html = f"""
        <div class="live-price-container animate-slide-up">
            <div class="live-indicator">
                <div class="live-dot"></div>
                <span>SPX LIVE</span>
            </div>
            <div class="price-main">
                ${market_data['price']:,.2f}
            </div>
            <div class="price-change" style="color: {change_color};">
                {change_symbol}{market_data['change']:,.2f} ({change_symbol}{market_data['change_percent']:.2f}%)
            </div>
            <div class="price-meta">
                H: ${market_data['today_high']:,.2f} • L: ${market_data['today_low']:,.2f}
            </div>
            <div class="price-meta">
                {market_status} • Vol: {market_data['volume']:,}
            </div>
            <div class="price-meta">
                Updated: {market_data['last_update'].strftime('%H:%M:%S')} • Fetch: {market_data['fetch_time']}s
            </div>
        </div>
        """
        
        st.markdown(live_price_html, unsafe_allow_html=True)
    else:
        # Error state HTML
        error_html = f"""
        <div class="live-price-container">
            <div class="live-indicator">
                <div style="width: 8px; height: 8px; background: #666; border-radius: 50%;"></div>
                <span>SPX DATA</span>
            </div>
            <div style="color: #999; font-size: var(--text-lg);">
                ⚠️ {market_data.get('message', 'Data unavailable')}
            </div>
        </div>
        """
        
        st.markdown(error_html, unsafe_allow_html=True)

def render_metrics_dashboard(forecast_date: date):
    """Render enhanced metrics dashboard with previous day anchors."""
    anchors = get_previous_day_anchors(forecast_date)
    
    if anchors:
        st.markdown('<div class="metrics-grid animate-slide-up">', unsafe_allow_html=True)
        
        # High Anchor Tile
        st.markdown(
            f"""
            <div class="metric-tile">
                <div class="metric-icon">{ICONS["high"]}</div>
                <div class="metric-value" style="color: {COLORS['success']};">
                    ${anchors['high']:,.2f}
                </div>
                <div class="metric-label">Previous Day High</div>
                <div class="metric-change positive">
                    Session: {anchors['date']}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Close Anchor Tile  
        st.markdown(
            f"""
            <div class="metric-tile">
                <div class="metric-icon">{ICONS["close"]}</div>
                <div class="metric-value" style="color: {COLORS['primary']};">
                    ${anchors['close']:,.2f}
                </div>
                <div class="metric-label">Previous Day Close</div>
                <div class="metric-change">
                    Session: {anchors['date']}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Low Anchor Tile
        st.markdown(
            f"""
            <div class="metric-tile">
                <div class="metric-icon">{ICONS["low"]}</div>
                <div class="metric-value" style="color: {COLORS['error']};">
                    ${anchors['low']:,.2f}
                </div>
                <div class="metric-label">Previous Day Low</div>
                <div class="metric-change negative">
                    Session: {anchors['date']}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        return anchors
    else:
        st.markdown(
            """
            <div class="premium-card">
                <div style="text-align: center; color: var(--warning); padding: var(--space-4);">
                    ⚠️ Could not determine previous trading day anchors for the selected forecast date.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return None

# ===== ENHANCED SIDEBAR =====
def render_enhanced_sidebar():
    """Render the enhanced sidebar with premium styling."""
    with st.sidebar:
        # Theme Control Section
        st.markdown('<div class="section-header">🎨 Appearance</div>', unsafe_allow_html=True)
        
        # Theme Toggle
        current_theme = st.session_state.get('theme', 'light')
        theme_options = ['light', 'dark']
        theme_index = theme_options.index(current_theme)
        
        new_theme = st.radio(
            "Theme Mode",
            options=theme_options,
            index=theme_index,
            format_func=lambda x: f"☀️ Light Mode" if x == 'light' else f"🌙 Dark Mode",
            horizontal=True
        )
        
        if new_theme != current_theme:
            st.session_state.theme = new_theme
            st.markdown(f"<script>window.setMarketLensTheme('{new_theme}')</script>", unsafe_allow_html=True)
            st.rerun()
        
        # Print Mode Toggle
        st.session_state.print_mode = st.toggle(
            "📄 Print-friendly mode", 
            value=st.session_state.get('print_mode', False),
            help="Optimize layout for printing"
        )
        
        st.divider()
        
        # Forecast Configuration
        st.markdown('<div class="section-header">📅 Forecast Setup</div>', unsafe_allow_html=True)
        
        forecast_date = st.date_input(
            "Target Trading Session",
            value=date.today() + timedelta(days=1),
            help="Select the date you want to forecast"
        )
        
        # Validate forecast date
        is_valid, validation_msg = validator.validate_date_input(forecast_date)
        if not is_valid:
            st.warning(f"⚠️ {validation_msg}")
        
        # Day of week indicator
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = day_names[forecast_date.weekday()]
        
        st.info(f"📆 **{day_name}** session • Anchors reference the previous trading day")
        
        st.divider()
        
        # Entry Detection Settings
        st.markdown('<div class="section-header">🎯 Entry Detection</div>', unsafe_allow_html=True)
        
        tolerance = st.slider(
            "Touch Tolerance ($)",
            min_value=0.00,
            max_value=5.00,
            value=st.session_state.get('default_tolerance', 0.50),
            step=0.05,
            help="Price tolerance for line touches"
        )
        
        rule_type = st.radio(
            "Detection Rule",
            options=["Close above Exit / below Entry", "Near line (±tol) only"],
            index=0,
            help="Choose how strict the entry detection should be"
        )
        
        st.divider()
        
        # Performance Metrics
        if 'performance_monitor' in st.session_state:
            monitor = st.session_state.performance_monitor
            session_time = monitor.get_session_duration()
            
            st.markdown('<div class="section-header">📊 Session Stats</div>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Page Loads", st.session_state.get('page_loads', 0))
            with col2:
                st.metric("Session Time", f"{session_time/60:.1f}m")
        
        return forecast_date, tolerance, rule_type

# ===== MAIN INTERFACE RENDERING =====
# Render hero section
render_hero_section()

# Render live price strip
render_live_price_strip()

# Render enhanced sidebar and get configuration
forecast_date, tolerance, rule_requirement = render_enhanced_sidebar()

# Render metrics dashboard with anchors
previous_anchors = render_metrics_dashboard(forecast_date)

# ===== ANCHOR INPUT SYSTEM =====

def render_anchor_input_header(forecast_date: date, previous_anchors: dict = None):
    """Render premium header for anchor configuration section."""
    st.markdown(
        """
        <div class="section-header animate-fade-in">🔧 SPX Anchor Configuration</div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown(
        f"""
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);line-height:1.6;">
            Configure your SPX anchors from the previous trading day. These will be used to generate
            precise entry and exit projections for <strong>{forecast_date.strftime('%A, %B %d, %Y')}</strong>.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Auto-population status
    if previous_anchors:
        prev_date = previous_anchors.get('date', 'Unknown')
        st.markdown(
            f"""
            <div class="glass-card animate-slide-up">
                <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3);">
                    <span style="font-size:1.2rem;">📅</span>
                    <span style="font-weight:600;color:var(--success);">Auto-populated from {prev_date}</span>
                </div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                    Values below are automatically loaded from the previous trading day.
                    You can modify them if needed before generating forecasts.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        return {
            'high_default': previous_anchors.get('high', 6185.80),
            'close_default': previous_anchors.get('close', 6170.20),
            'low_default': previous_anchors.get('low', 6130.40)
        }
    else:
        st.markdown(
            """
            <div class="premium-card animate-slide-up" style="background:rgba(255,149,0,0.1);border-color:#FF9500;">
                <div style="display:flex;align-items:center;gap:var(--space-3);">
                    <span style="font-size:1.2rem;">⚠️</span>
                    <div>
                        <div style="color:#FF9500;font-weight:600;">Manual Input Required</div>
                        <div style="color:var(--text-secondary);margin-top:var(--space-2);">
                            Previous day data not available. Please enter anchors manually.
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        return {
            'high_default': 6185.80,
            'close_default': 6170.20,
            'low_default': 6130.40
        }

def create_premium_anchor_input(anchor_type: str, default_price: float, default_time: time, 
                               icon: str, color: str, description: str):
    """Create a premium individual anchor input component."""
    st.markdown(
        f"""
        <div class="premium-card animate-slide-up">
            <div class="subsection-header">
                <span style="font-size:1.5rem;">{icon}</span>
                <span style="color:{color};font-weight:700;font-size:var(--text-2xl);">{anchor_type} Anchor</span>
            </div>
            <div style="color:var(--text-tertiary);margin-bottom:var(--space-4);font-size:var(--text-sm);line-height:1.5;">
                {description}
            </div>
        """,
        unsafe_allow_html=True
    )
    
    # Enhanced input layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        price = st.number_input(
            "Price ($)",
            value=float(default_price),
            min_value=0.0,
            max_value=10000.0,
            step=0.1,
            format="%.2f",
            key=f"anchor_{anchor_type.lower()}_price_input",
            help=f"Enter the {anchor_type.lower()} price from the previous trading day"
        )
        
        # Real-time price validation with premium styling
        is_valid_price = True
        if price <= 0:
            st.markdown(
                """
                <div style="background:rgba(255,59,48,0.1);color:#FF3B30;padding:var(--space-2) var(--space-3);
                     border-radius:var(--radius-md);font-size:var(--text-sm);margin-top:var(--space-2);">
                    ⚠️ Price must be greater than 0
                </div>
                """,
                unsafe_allow_html=True
            )
            is_valid_price = False
        elif price > 10000:
            st.markdown(
                """
                <div style="background:rgba(255,59,48,0.1);color:#FF3B30;padding:var(--space-2) var(--space-3);
                     border-radius:var(--radius-md);font-size:var(--text-sm);margin-top:var(--space-2);">
                    ⚠️ Price seems unreasonably high for SPX
                </div>
                """,
                unsafe_allow_html=True
            )
            is_valid_price = False
        elif price < 1000:
            st.markdown(
                """
                <div style="background:rgba(255,149,0,0.1);color:#FF9500;padding:var(--space-2) var(--space-3);
                     border-radius:var(--radius-md);font-size:var(--text-sm);margin-top:var(--space-2);">
                    💡 Price seems low for SPX - please verify
                </div>
                """,
                unsafe_allow_html=True
            )
    
    with col2:
        anchor_time = st.time_input(
            "Time",
            value=default_time,
            step=300,
            key=f"anchor_{anchor_type.lower()}_time_input",
            help=f"Time when the {anchor_type.lower()} occurred"
        )
        
        # Real-time time validation
        is_valid_time = True
        if not (time(6, 0) <= anchor_time <= time(20, 0)):
            st.markdown(
                """
                <div style="background:rgba(255,149,0,0.1);color:#FF9500;padding:var(--space-2) var(--space-3);
                     border-radius:var(--radius-md);font-size:var(--text-sm);margin-top:var(--space-2);">
                    ⚠️ Time outside extended hours (06:00-20:00)
                </div>
                """,
                unsafe_allow_html=True
            )
            is_valid_time = False
    
    # Success indicator
    if is_valid_price and is_valid_time:
        st.markdown(
            f"""
            <div style="background:rgba(52,199,89,0.1);color:#34C759;padding:var(--space-2) var(--space-3);
                 border-radius:var(--radius-md);font-size:var(--text-sm);font-weight:500;margin-top:var(--space-2);">
                ✅ {anchor_type} anchor: ${price:.2f} at {anchor_time.strftime('%H:%M')}
            </div>
            """,
            unsafe_allow_html=True
        )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return price, anchor_time, (is_valid_price and is_valid_time)

def render_enhanced_anchor_inputs(defaults: dict):
    """Render all three anchor inputs with premium styling."""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        high_price, high_time, high_valid = create_premium_anchor_input(
            "HIGH",
            defaults['high_default'],
            time(11, 30),
            "📈",
            COLORS['success'],
            "Previous day's highest price point - typically your strongest resistance level."
        )
    
    with col2:
        close_price, close_time, close_valid = create_premium_anchor_input(
            "CLOSE",
            defaults['close_default'],
            time(15, 0),
            "⚡",
            COLORS['primary'],
            "Previous day's closing price - the market's final consensus value."
        )
    
    with col3:
        low_price, low_time, low_valid = create_premium_anchor_input(
            "LOW",
            defaults['low_default'],
            time(13, 30),
            "📉",
            COLORS['error'],
            "Previous day's lowest price point - typically your strongest support level."
        )
    
    return {
        'high_price': high_price,
        'high_time': high_time,
        'high_valid': high_valid,
        'close_price': close_price,
        'close_time': close_time,
        'close_valid': close_valid,
        'low_price': low_price,
        'low_time': low_time,
        'low_valid': low_valid,
        'all_valid': high_valid and close_valid and low_valid
    }

def render_validation_status_card(anchor_data: dict):
    """Render premium validation status card."""
    all_valid = anchor_data['all_valid']
    
    if all_valid:
        st.markdown(
            """
            <div class="glass-card animate-fade-in" style="background:rgba(52,199,89,0.1);border-color:#34C759;">
                <div style="display:flex;align-items:center;gap:var(--space-3);">
                    <span style="font-size:1.5rem;">✅</span>
                    <div>
                        <div style="font-weight:700;color:#34C759;">All Anchors Valid</div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            All three anchors are properly configured and ready to lock
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        invalid_anchors = []
        if not anchor_data['high_valid']:
            invalid_anchors.append("HIGH")
        if not anchor_data['close_valid']:
            invalid_anchors.append("CLOSE")
        if not anchor_data['low_valid']:
            invalid_anchors.append("LOW")
        
        st.markdown(
            f"""
            <div class="glass-card animate-fade-in" style="background:rgba(255,149,0,0.1);border-color:#FF9500;">
                <div style="display:flex;align-items:center;gap:var(--space-3);">
                    <span style="font-size:1.5rem;">⚠️</span>
                    <div>
                        <div style="font-weight:700;color:#FF9500;">Validation Issues</div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Fix issues with: {', '.join(invalid_anchors)} anchor(s)
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    return all_valid

def render_lock_unlock_controls(anchor_data: dict):
    """Render premium lock/unlock controls with enhanced styling."""
    is_locked = st.session_state.get('anchors_locked', False)
    all_valid = anchor_data['all_valid']
    
    col_action, col_generate = st.columns([1, 1])
    
    with col_action:
        if not is_locked and all_valid:
            if st.button("🔒 Lock Anchors", use_container_width=True, type="primary"):
                st.session_state.anchors_locked = True
                st.session_state.locked_anchor_data = {
                    'high': {'price': anchor_data['high_price'], 'time': anchor_data['high_time']},
                    'close': {'price': anchor_data['close_price'], 'time': anchor_data['close_time']},
                    'low': {'price': anchor_data['low_price'], 'time': anchor_data['low_time']},
                    'locked_at': datetime.now()
                }
                st.success("🎯 Anchors locked successfully!")
                st.rerun()
        elif is_locked:
            if st.button("🔓 Unlock Anchors", use_container_width=True):
                st.session_state.anchors_locked = False
                st.session_state.locked_anchor_data = None
                st.info("🔄 Anchors unlocked for editing")
                st.rerun()
        else:
            st.button("🔒 Fix Validation Issues", use_container_width=True, disabled=True)
    
    with col_generate:
        can_generate = is_locked and all_valid
        if can_generate:
            if st.button("🚀 Generate Forecast", use_container_width=True, type="primary"):
                st.session_state.forecasts_generated = True
                st.success("📊 Forecast generation initiated!")
                st.rerun()
        else:
            reason = "Lock Anchors First" if not is_locked else "Fix Validation Issues"
            st.button(f"🚀 {reason}", use_container_width=True, disabled=True)
    
    return is_locked, can_generate

def render_locked_anchor_summary():
    """Render premium locked anchor summary with enhanced styling."""
    if not st.session_state.get('anchors_locked', False):
        return None
    
    if 'locked_anchor_data' not in st.session_state:
        return None
    
    locked_data = st.session_state.locked_anchor_data
    locked_time = locked_data['locked_at'].strftime('%H:%M:%S')
    
    st.markdown(
        f"""
        <div class="premium-card animate-slide-up" style="background:rgba(0,122,255,0.05);border-color:#007AFF;">
            <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4);">
                <span style="font-size:1.5rem;">🔒</span>
                <div>
                    <div style="font-weight:700;color:#007AFF;">Anchors Locked & Ready</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                        Locked at {locked_time} • Configuration protected from changes
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Create the grid layout using Streamlit columns instead of CSS grid
    col1, col2, col3 = st.columns(3)
    
    # HIGH Anchor
    with col1:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:rgba(52,199,89,0.05);
                 border-radius:var(--radius-lg);border:1px solid rgba(52,199,89,0.2);">
                <div style="font-size:1.2rem;margin-bottom:var(--space-1);">📈</div>
                <div style="color:#34C759;font-weight:700;font-size:var(--text-xl);font-family:'JetBrains Mono',monospace;">
                    ${locked_data['high']['price']:.2f}
                </div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);margin-top:var(--space-1);">
                    HIGH @ {locked_data['high']['time'].strftime('%H:%M')}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # CLOSE Anchor
    with col2:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:rgba(0,122,255,0.05);
                 border-radius:var(--radius-lg);border:1px solid rgba(0,122,255,0.2);">
                <div style="font-size:1.2rem;margin-bottom:var(--space-1);">⚡</div>
                <div style="color:#007AFF;font-weight:700;font-size:var(--text-xl);font-family:'JetBrains Mono',monospace;">
                    ${locked_data['close']['price']:.2f}
                </div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);margin-top:var(--space-1);">
                    CLOSE @ {locked_data['close']['time'].strftime('%H:%M')}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # LOW Anchor
    with col3:
        low_info = locked_data.get("low", {})
        price = low_info.get("price")
        time_val = low_info.get("time")
        price_str = f"{price:.2f}" if isinstance(price, (int, float)) else "--"
        time_str = time_val.strftime("%H:%M") if hasattr(time_val, "strftime") else (str(time_val) if time_val else "--")
        
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:rgba(255,59,48,0.05);
                 border-radius:var(--radius-lg);border:1px solid rgba(255,59,48,0.2);">
                <div style="font-size:1.2rem;margin-bottom:var(--space-1);">📉</div>
                <div style="color:#FF3B30;font-weight:700;font-size:var(--text-xl);font-family:'JetBrains Mono',monospace;">
                    ${price_str}
                </div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);margin-top:var(--space-1);">
                    LOW @ {time_str}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

def handle_complete_anchor_management(anchor_data: dict):
    """Handle the complete anchor management flow with premium styling."""
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    
    # Validation Status
    col_status, col_controls = st.columns([2, 2])
    
    with col_status:
        all_valid = render_validation_status_card(anchor_data)
    
    with col_controls:
        is_locked, can_generate = render_lock_unlock_controls(anchor_data)
    
    # Locked Summary (if locked)
    if is_locked:
        st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
        render_locked_anchor_summary()
    
    return {
        'is_locked': is_locked,
        'can_generate': can_generate,
        'all_valid': all_valid
    }

def get_locked_anchor_configuration():
    """Get the locked anchor configuration for forecast generation."""
    if st.session_state.get('anchors_locked', False) and 'locked_anchor_data' in st.session_state:
        locked_data = st.session_state.locked_anchor_data
        return {
            'high_price': locked_data['high']['price'],
            'high_time': locked_data['high']['time'],
            'close_price': locked_data['close']['price'],
            'close_time': locked_data['close']['time'],
            'low_price': locked_data['low']['price'],
            'low_time': locked_data['low']['time'],
            'is_locked': True,
            'locked_at': locked_data['locked_at']
        }
    else:
        return {
            'is_locked': False,
            'error': 'Anchors must be locked before generating forecasts'
        }

# ===== MAIN ANCHOR SECTION INTEGRATION =====
def render_complete_anchor_section(forecast_date: date, previous_anchors: dict = None):
    """Main function to render the complete enhanced anchor section."""
    
    # Header with auto-population status
    defaults = render_anchor_input_header(forecast_date, previous_anchors)
    
    # Enhanced anchor inputs
    anchor_inputs_data = render_enhanced_anchor_inputs(defaults)
    
    # Management controls and validation
    control_status = handle_complete_anchor_management(anchor_inputs_data)
    
    # Get locked configuration if available
    anchor_config = get_locked_anchor_configuration() if control_status['can_generate'] else None
    
    return {
        'anchor_data': anchor_inputs_data,
        'control_status': control_status,
        'anchor_config': anchor_config,
        'ready_for_forecast': control_status['can_generate']
    }

# ===== INTEGRATION INTO MAIN FLOW =====
# Add this after the metrics dashboard in your main application

# Render the complete enhanced anchor section
anchor_section_results = render_complete_anchor_section(forecast_date, previous_anchors)

# ===== FAN DATA GENERATION SYSTEM =====

def build_fan_dataframe(anchor_type: str, anchor_price: float, anchor_time: time, forecast_date: date) -> pd.DataFrame:
    """
    Build fan forecast dataframe for a specific anchor type with TP1/TP2 system.
    Preserves original calculation logic with enhanced profit target calculations.
    """
    try:
        # Create anchor datetime (preserving original logic)
        anchor_datetime = datetime.combine(forecast_date - timedelta(days=1), anchor_time)
        
        rows = []
        for time_slot in SPX_SLOTS:
            try:
                hour, minute = map(int, time_slot.split(":"))
                target_datetime = datetime.combine(forecast_date, time(hour, minute))
                
                # Calculate SPX blocks (preserving original logic)
                blocks = spx_blocks_between(anchor_datetime, target_datetime)
                
                # Project prices using original slopes
                entry_price = project_price(anchor_price, SPX_SLOPES_DOWN[anchor_type], blocks)
                exit_price = project_price(anchor_price, SPX_SLOPES_UP[anchor_type], blocks)
                
                # Calculate TP1/TP2 system
                total_spread = exit_price - entry_price
                tp1_price = entry_price + (total_spread * 0.5)  # 50% profit target
                tp2_price = exit_price  # Full profit target
                
                rows.append({
                    'Time': time_slot,
                    'Entry': round(entry_price, 2),
                    'TP1': round(tp1_price, 2),
                    'TP2': round(tp2_price, 2),
                    'Blocks': blocks,
                    'Anchor_Price': anchor_price,
                    'Anchor_Type': anchor_type,
                    'Total_Spread': round(total_spread, 2),
                    'TP1_Distance': round(tp1_price - entry_price, 2),
                    'TP2_Distance': round(tp2_price - entry_price, 2)
                })
            except Exception:
                # Skip invalid time slots
                continue
        
        if not rows:
            raise CalculationError(f"No valid fan data generated for {anchor_type}")
        
        # Create DataFrame with metadata (preserving original structure)
        fan_df = pd.DataFrame(rows)
        fan_df['TS'] = pd.to_datetime(BASELINE_DATE_STR + " " + fan_df['Time'])
        
        # Add rich metadata for tracking
        fan_df.attrs.update({
            'anchor_type': anchor_type,
            'anchor_price': anchor_price,
            'anchor_time': anchor_time,
            'forecast_date': forecast_date,
            'generated_at': datetime.now(),
            'slopes_down': SPX_SLOPES_DOWN[anchor_type],
            'slopes_up': SPX_SLOPES_UP[anchor_type],
            'tp_system': 'TP1_50_TP2_100'
        })
        
        return fan_df
        
    except Exception as e:
        st.error(f"⚠️ Error generating {anchor_type} fan data: {str(e)}")
        return pd.DataFrame()

def generate_all_fans(anchor_config: dict, forecast_date: date) -> dict:
    """
    Generate all three fan datasets with progress tracking.
    """
    if not anchor_config.get('is_locked', False):
        st.error("🔒 Anchors must be locked before generating fan data")
        return {}
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    fan_datasets = {}
    
    # Generate HIGH fan
    status_text.text("🔄 Generating HIGH anchor fan...")
    progress_bar.progress(10)
    fan_datasets['high'] = build_fan_dataframe(
        'HIGH', 
        anchor_config['high_price'], 
        anchor_config['high_time'], 
        forecast_date
    )
    progress_bar.progress(35)
    
    # Generate CLOSE fan
    status_text.text("🔄 Generating CLOSE anchor fan...")
    progress_bar.progress(40)
    fan_datasets['close'] = build_fan_dataframe(
        'CLOSE', 
        anchor_config['close_price'], 
        anchor_config['close_time'], 
        forecast_date
    )
    progress_bar.progress(70)
    
    # Generate LOW fan
    status_text.text("🔄 Generating LOW anchor fan...")
    progress_bar.progress(75)
    fan_datasets['low'] = build_fan_dataframe(
        'LOW', 
        anchor_config['low_price'], 
        anchor_config['low_time'], 
        forecast_date
    )
    progress_bar.progress(100)
    
    # Calculate summary statistics
    total_rows = sum(len(df) for df in fan_datasets.values() if isinstance(df, pd.DataFrame) and not df.empty)
    
    if total_rows > 0:
        status_text.markdown(
            f"""
            <div style="color:#34C759;font-weight:600;">
                ✅ Generated {total_rows} forecast data points with TP1/TP2 targets
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Store in session state for persistence
        st.session_state.fan_data = fan_datasets
        st.session_state.fan_data_generated_at = datetime.now()
        st.session_state.fan_forecast_date = forecast_date
    else:
        status_text.markdown(
            """
            <div style="color:#FF3B30;font-weight:600;">
                ❌ Failed to generate fan data - please check anchor configuration
            </div>
            """,
            unsafe_allow_html=True
        )
    
    return fan_datasets

# ===== TRADING-FOCUSED DATA DISPLAY =====

def display_trading_tables(fan_datasets: dict):
    """Display fan data in trading-focused tables with TP1/TP2."""
    if not fan_datasets:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">📊</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">No Trading Data Available</div>
                <div style="color:var(--text-tertiary);">Generate forecasts first to view trading tables</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return
    
    st.markdown(
        """
        <div class="section-header">📋 Trading Tables (Entry → TP1 → TP2)</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Professional trading tables with dual profit targets for optimal position scaling.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Create premium tabs
    tab_high, tab_close, tab_low = st.tabs(["📈 HIGH Anchor", "⚡ CLOSE Anchor", "📉 LOW Anchor"])
    
    def render_trading_tab(df: pd.DataFrame, color_name: str, label: str, icon: str):
        """Render individual trading table with TP1/TP2 system."""
        if df is None or df.empty:
            st.markdown(
                f"""
                <div style="text-align:center;padding:var(--space-6);color:var(--error);">
                    <div style="font-size:2rem;margin-bottom:var(--space-2);">❌</div>
                    <div>{label} trading data not available</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            return
        
        # Trading summary card
        anchor_price = df.attrs.get('anchor_price', 0)
        anchor_time = df.attrs.get('anchor_time', time())
        generated_at = df.attrs.get('generated_at', datetime.now())
        
        # Calculate key metrics
        min_entry = df['Entry'].min()
        max_tp2 = df['TP2'].max()
        avg_tp1_distance = df['TP1_Distance'].mean()
        avg_tp2_distance = df['TP2_Distance'].mean()
        
        st.markdown(
            f"""
            <div class="premium-card" style="margin-bottom:var(--space-4);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-2);">
                            <span style="font-size:1.5rem;">{icon}</span>
                            <span style="font-weight:700;color:{COLORS[color_name]};font-size:var(--text-xl);">{label} Trading Levels</span>
                        </div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Anchor: ${anchor_price:.2f} @ {anchor_time.strftime('%H:%M')} • Generated: {generated_at.strftime('%H:%M:%S')}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:600;font-size:var(--text-lg);">{len(df)} time slots</div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Range: ${min_entry:.2f} - ${max_tp2:.2f}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Trading metrics using Streamlit columns
        col_met1, col_met2, col_met3, col_met4 = st.columns(4)
        
        with col_met1:
            st.markdown(
                f"""
                <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                    <div style="font-weight:700;color:{COLORS['error']};font-size:var(--text-lg);">${min_entry:.2f}</div>
                    <div style="font-size:var(--text-xs);color:var(--text-tertiary);">MIN ENTRY</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        with col_met2:
            st.markdown(
                f"""
                <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                    <div style="font-weight:700;color:{COLORS['warning']};font-size:var(--text-lg);">${avg_tp1_distance:.2f}</div>
                    <div style="font-size:var(--text-xs);color:var(--text-tertiary);">AVG TP1 DIST</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        with col_met3:
            st.markdown(
                f"""
                <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                    <div style="font-weight:700;color:{COLORS['success']};font-size:var(--text-lg);">${avg_tp2_distance:.2f}</div>
                    <div style="font-size:var(--text-xs);color:var(--text-tertiary);">AVG TP2 DIST</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        with col_met4:
            st.markdown(
                f"""
                <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                    <div style="font-weight:700;color:{COLORS['success']};font-size:var(--text-lg);">${max_tp2:.2f}</div>
                    <div style="font-size:var(--text-xs);color:var(--text-tertiary);">MAX TP2</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        # Trading table with TP1/TP2 columns
        st.markdown("### 📊 Trading Levels")
        
        display_columns = ['Time', 'Entry', 'TP1', 'TP2', 'Blocks', 'Total_Spread']
        st.dataframe(
            df[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                'Time': st.column_config.TextColumn('Time', width='small'),
                'Entry': st.column_config.NumberColumn('Entry ($)', format='$%.2f'),
                'TP1': st.column_config.NumberColumn('TP1 ($)', format='$%.2f', help='50% profit target'),
                'TP2': st.column_config.NumberColumn('TP2 ($)', format='$%.2f', help='Full profit target'),
                'Blocks': st.column_config.NumberColumn('Blocks', width='small'),
                'Total_Spread': st.column_config.NumberColumn('Total Spread ($)', format='$%.2f')
            }
        )
        
        # Trading strategy note
        st.markdown(
            f"""
            <div style="background:rgba(0,122,255,0.1);padding:var(--space-3);border-radius:var(--radius-lg);margin-top:var(--space-3);">
                <div style="font-weight:600;color:{COLORS['primary']};margin-bottom:var(--space-2);">💡 Trading Strategy</div>
                <div style="color:var(--text-secondary);font-size:var(--text-sm);line-height:1.5;">
                    <strong>Entry:</strong> Wait for price to reach Entry level<br>
                    <strong>TP1:</strong> Take 50% profit at TP1 (50% of total move)<br>
                    <strong>TP2:</strong> Take remaining 50% profit at TP2 (full move)<br>
                    <strong>Risk Management:</strong> Use appropriate position sizing and stop losses
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Render each trading tab
    with tab_high:
        render_trading_tab(fan_datasets.get('high'), 'success', 'HIGH', '📈')
    
    with tab_close:
        render_trading_tab(fan_datasets.get('close'), 'primary', 'CLOSE', '⚡')
    
    with tab_low:
        render_trading_tab(fan_datasets.get('low'), 'error', 'LOW', '📉')

# ===== TRADING ANALYTICS SYSTEM =====

def display_trading_analytics(fan_datasets: dict):
    """Display comprehensive trading analytics across all fans."""
    if not fan_datasets:
        return
    
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="section-header">📈 Trading Analytics</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Cross-anchor analysis and optimal timing insights for trading decisions.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Collect analytics from all fans
    all_data = []
    for anchor_name, df in fan_datasets.items():
        if df is not None and not df.empty:
            anchor_type = df.attrs.get('anchor_type', anchor_name.upper())
            all_data.append({
                'anchor': anchor_type,
                'min_entry': df['Entry'].min(),
                'max_tp2': df['TP2'].max(),
                'avg_tp1_dist': df['TP1_Distance'].mean(),
                'avg_tp2_dist': df['TP2_Distance'].mean(),
                'best_spread': df['Total_Spread'].max(),
                'worst_spread': df['Total_Spread'].min(),
                'time_slots': len(df)
            })
    
    if not all_data:
        st.warning("No data available for analytics")
        return
    
    analytics_df = pd.DataFrame(all_data)
    
    # Key metrics grid
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_setups = analytics_df['time_slots'].sum()
        st.metric("📊 Total Setups", f"{total_setups}", "Across all anchors")
    
    with col2:
        best_spread = analytics_df['best_spread'].max()
        best_anchor = analytics_df.loc[analytics_df['best_spread'].idxmax(), 'anchor']
        st.metric("🎯 Best Spread", f"${best_spread:.2f}", f"{best_anchor} anchor")
    
    with col3:
        avg_tp1_overall = analytics_df['avg_tp1_dist'].mean()
        st.metric("📈 Avg TP1 Distance", f"${avg_tp1_overall:.2f}", "50% target")
    
    with col4:
        avg_tp2_overall = analytics_df['avg_tp2_dist'].mean()
        st.metric("🏆 Avg TP2 Distance", f"${avg_tp2_overall:.2f}", "Full target")
    
    # Anchor comparison table
    st.markdown("### 📋 Anchor Comparison")
    
    comparison_df = analytics_df.copy()
    comparison_df.columns = [
        'Anchor', 'Min Entry ($)', 'Max TP2 ($)', 'Avg TP1 Dist ($)', 
        'Avg TP2 Dist ($)', 'Best Spread ($)', 'Worst Spread ($)', 'Time Slots'
    ]
    
    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Anchor': st.column_config.TextColumn('Anchor', width='small'),
            'Min Entry ($)': st.column_config.NumberColumn('Min Entry', format='$%.2f'),
            'Max TP2 ($)': st.column_config.NumberColumn('Max TP2', format='$%.2f'),
            'Avg TP1 Dist ($)': st.column_config.NumberColumn('Avg TP1 Dist', format='$%.2f'),
            'Avg TP2 Dist ($)': st.column_config.NumberColumn('Avg TP2 Dist', format='$%.2f'),
            'Best Spread ($)': st.column_config.NumberColumn('Best Spread', format='$%.2f'),
            'Worst Spread ($)': st.column_config.NumberColumn('Worst Spread', format='$%.2f'),
            'Time Slots': st.column_config.NumberColumn('Setups', width='small')
        }
    )
    
    # Trading recommendations
    best_tp1_anchor = analytics_df.loc[analytics_df['avg_tp1_dist'].idxmax(), 'anchor']
    best_tp2_anchor = analytics_df.loc[analytics_df['avg_tp2_dist'].idxmax(), 'anchor']
    most_consistent = analytics_df.loc[(analytics_df['best_spread'] - analytics_df['worst_spread']).idxmin(), 'anchor']
    
    st.markdown(
        f"""
        <div class="glass-card" style="margin-top:var(--space-6);">
            <div style="font-weight:700;margin-bottom:var(--space-4);color:var(--primary);">🎯 Trading Recommendations</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Create recommendations using Streamlit columns
    col_rec1, col_rec2, col_rec3 = st.columns(3)
    
    with col_rec1:
        st.markdown(
            f"""
            <div style="padding:var(--space-3);background:rgba(255,149,0,0.1);border-radius:var(--radius-lg);">
                <div style="font-weight:600;color:{COLORS['warning']};">Best for Quick TP1</div>
                <div style="color:var(--text-secondary);">{best_tp1_anchor} anchor offers the best TP1 distances</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col_rec2:
        st.markdown(
            f"""
            <div style="padding:var(--space-3);background:rgba(52,199,89,0.1);border-radius:var(--radius-lg);">
                <div style="font-weight:600;color:{COLORS['success']};">Best for Full TP2</div>
                <div style="color:var(--text-secondary);">{best_tp2_anchor} anchor offers the best TP2 distances</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col_rec3:
        st.markdown(
            f"""
            <div style="padding:var(--space-3);background:rgba(0,122,255,0.1);border-radius:var(--radius-lg);">
                <div style="font-weight:600;color:{COLORS['primary']};">Most Consistent</div>
                <div style="color:var(--text-secondary);">{most_consistent} anchor has the most consistent spreads</div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ===== MAIN INTEGRATION FUNCTION =====

def handle_trading_data_generation(anchor_config: dict, forecast_date: date):
    """Main function to handle trading-focused fan generation and display."""
    if not anchor_config or not anchor_config.get('is_locked', False):
        return {}
    
    # Generate fan data with TP1/TP2
    fan_data = generate_all_fans(anchor_config, forecast_date)
    
    if fan_data:
        st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
        
        # Display trading tables
        display_trading_tables(fan_data)
        
        # Display trading analytics
        display_trading_analytics(fan_data)
        
        return {
            'fan_data': fan_data,
            'trading_tables_displayed': True,
            'analytics_displayed': True,
            'tp_system_enabled': True
        }
    
    return {}

# ===== INTEGRATION INTO MAIN FLOW =====
# Add this after the anchor section when forecasts are generated

if st.session_state.get("forecasts_generated", False) and anchor_section_results.get('ready_for_forecast', False):
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    
    # Handle trading data generation and display
    trading_results = handle_trading_data_generation(
        anchor_section_results['anchor_config'], 
        forecast_date
    )

