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

# ===== CSS UTILITIES =====
CSS_COMPONENTS = """
<style>
/* === BUTTONS === */
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

/* === RADIO BUTTONS === */
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

/* === EXPANDERS === */
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

/* === SIDEBAR === */
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

# ===== APPLY DESIGN SYSTEM =====
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
            
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:var(--space-4);">
        """,
        unsafe_allow_html=True
    )
    
    # HIGH Anchor
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
    Build fan forecast dataframe for a specific anchor type.
    Preserves original calculation logic with premium error handling.
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
                
                rows.append({
                    'Time': time_slot,
                    'Entry': round(entry_price, 2),
                    'Exit': round(exit_price, 2),
                    'Blocks': blocks,
                    'Anchor_Price': anchor_price,
                    'Anchor_Type': anchor_type,
                    'Spread': round(exit_price - entry_price, 2)
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
            'slopes_up': SPX_SLOPES_UP[anchor_type]
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
                ✅ Generated {total_rows} forecast data points across all anchors
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

# ===== FAN DATA DISPLAY SYSTEM =====

def display_fan_data_tables(fan_datasets: dict):
    """Display fan data in premium tabbed interface."""
    if not fan_datasets:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">📊</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">No Fan Data Available</div>
                <div style="color:var(--text-tertiary);">Generate forecasts first to view data tables</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return
    
    st.markdown(
        """
        <div class="section-header">📋 Fan Forecast Tables</div>
        """,
        unsafe_allow_html=True
    )
    
    # Create premium tabs
    tab_high, tab_close, tab_low = st.tabs(["📈 HIGH Fan", "⚡ CLOSE Fan", "📉 LOW Fan"])
    
    def render_fan_tab(df: pd.DataFrame, color_name: str, label: str, icon: str):
        """Render individual fan data tab with premium styling."""
        if df is None or df.empty:
            st.markdown(
                f"""
                <div style="text-align:center;padding:var(--space-6);color:var(--error);">
                    <div style="font-size:2rem;margin-bottom:var(--space-2);">❌</div>
                    <div>{label} fan data not available</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            return
        
        # Fan summary card
        anchor_price = df.attrs.get('anchor_price', 0)
        anchor_time = df.attrs.get('anchor_time', time())
        generated_at = df.attrs.get('generated_at', datetime.now())
        min_entry = df['Entry'].min()
        max_exit = df['Exit'].max()
        avg_spread = df['Spread'].mean()
        
        st.markdown(
            f"""
            <div class="premium-card" style="margin-bottom:var(--space-4);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-2);">
                            <span style="font-size:1.5rem;">{icon}</span>
                            <span style="font-weight:700;color:{COLORS[color_name]};font-size:var(--text-xl);">{label} Anchor Fan</span>
                        </div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Anchor: ${anchor_price:.2f} @ {anchor_time.strftime('%H:%M')}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:600;font-size:var(--text-lg);">{len(df)} time slots</div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Generated: {generated_at.strftime('%H:%M:%S')}
                        </div>
                    </div>
                </div>
                
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:var(--space-4);
                     margin-top:var(--space-4);padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                    <div style="text-align:center;">
                        <div style="font-weight:700;color:{COLORS['error']};">${min_entry:.2f}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">MIN ENTRY</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-weight:700;color:{COLORS['success']};">${max_exit:.2f}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">MAX EXIT</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-weight:700;color:{COLORS['neutral']};">${avg_spread:.2f}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">AVG SPREAD</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Data table with custom column config
        display_columns = ['Time', 'Entry', 'Exit', 'Blocks', 'Spread']
        st.dataframe(
            df[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                'Time': st.column_config.TextColumn('Time', width='small'),
                'Entry': st.column_config.NumberColumn('Entry ($)', format='$%.2f'),
                'Exit': st.column_config.NumberColumn('Exit ($)', format='$%.2f'),
                'Blocks': st.column_config.NumberColumn('Blocks', width='small'),
                'Spread': st.column_config.NumberColumn('Spread ($)', format='$%.2f')
            }
        )
    
    # Render each tab
    with tab_high:
        render_fan_tab(fan_datasets.get('high'), 'success', 'HIGH', '📈')
    
    with tab_close:
        render_fan_tab(fan_datasets.get('close'), 'primary', 'CLOSE', '⚡')
    
    with tab_low:
        render_fan_tab(fan_datasets.get('low'), 'error', 'LOW', '📉')

# ===== PREMIUM CHARTING SYSTEM =====

def create_plotly_theme():
    """Create consistent Plotly theme based on current app theme."""
    current_theme = st.session_state.get('theme', 'light')
    
    if current_theme == 'dark':
        return {
            'bg_color': '#0F141B',
            'paper_color': '#1C1C1E',
            'text_color': '#FFFFFF',
            'grid_color': 'rgba(255,255,255,0.1)',
            'zero_line_color': 'rgba(255,255,255,0.2)',
            'font_family': 'SF Pro Display, Inter, -apple-system, sans-serif'
        }
    else:
        return {
            'bg_color': '#F2F2F7',
            'paper_color': '#FFFFFF',
            'text_color': '#000000',
            'grid_color': 'rgba(0,0,0,0.1)',
            'zero_line_color': 'rgba(0,0,0,0.2)',
            'font_family': 'SF Pro Display, Inter, -apple-system, sans-serif'
        }

def create_fan_chart(fan_df: pd.DataFrame, chart_title: str, intraday_data: pd.DataFrame = None):
    """Create premium fan chart with SPX overlay."""
    if fan_df.empty:
        return None
    
    theme = create_plotly_theme()
    fig = go.Figure()
    
    # Determine colors based on anchor type
    anchor_type = fan_df.attrs.get('anchor_type', 'UNKNOWN')
    
    if anchor_type == 'HIGH':
        entry_color = COLORS['bear']
        exit_color = COLORS['success']
        fill_color = 'rgba(52,199,89,0.08)'
    elif anchor_type == 'CLOSE':
        entry_color = COLORS['warning']
        exit_color = COLORS['primary']
        fill_color = 'rgba(0,122,255,0.08)'
    else:  # LOW
        entry_color = COLORS['error']
        exit_color = COLORS['bull']
        fill_color = 'rgba(0,212,170,0.08)'
    
    # Add Exit line (top)
    fig.add_trace(go.Scatter(
        x=fan_df['TS'],
        y=fan_df['Exit'],
        name='Exit Line (↗️)',
        line=dict(width=3, color=exit_color, shape='spline', smoothing=0.3),
        hovertemplate='<b>Exit Signal</b><br>Time: %{x|%H:%M}<br>Price: $%{y:,.2f}<br><extra></extra>'
    ))
    
    # Add Entry line (bottom) with fill
    fig.add_trace(go.Scatter(
        x=fan_df['TS'],
        y=fan_df['Entry'],
        name='Entry Line (↘️)',
        line=dict(width=3, color=entry_color, shape='spline', smoothing=0.3),
        fill='tonexty',
        fillcolor=fill_color,
        hovertemplate='<b>Entry Signal</b><br>Time: %{x|%H:%M}<br>Price: $%{y:,.2f}<br><extra></extra>'
    ))
    
    # Add SPX overlay if available
    if intraday_data is not None and not intraday_data.empty:
        fig.add_trace(go.Scatter(
            x=intraday_data['TS'],
            y=intraday_data['Close'],
            name='SPX (30m close)',
            line=dict(width=2, color=COLORS['neutral']),
            hovertemplate='<b>SPX Price</b><br>Time: %{x|%H:%M}<br>Price: $%{y:,.2f}<br><extra></extra>'
        ))
    
    # Apply premium styling
    fig.update_layout(
        title=dict(
            text=f'<b>{chart_title}</b>',
            font=dict(family=theme['font_family'], size=24, color=theme['text_color']),
            x=0.02
        ),
        height=450,
        margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor=theme['bg_color'],
        paper_bgcolor=theme['paper_color'],
        font=dict(family=theme['font_family'], color=theme['text_color'], size=12),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='left',
            x=0,
            bgcolor='rgba(0,0,0,0)'
        ),
        dragmode='pan',
        autosize=True
    )
    
    # Style axes
    fig.update_xaxes(
        title='<b>Trading Hours (RTH)</b>',
        showgrid=True,
        gridwidth=1,
        gridcolor=theme['grid_color'],
        zeroline=True,
        zerolinewidth=1,
        zerolinecolor=theme['zero_line_color'],
        tickformat='%H:%M',
        rangeslider=dict(visible=True, bgcolor=theme['paper_color'])
    )
    
    fig.update_yaxes(
        title='<b>SPX Price ($)</b>',
        showgrid=True,
        gridwidth=1,
        gridcolor=theme['grid_color'],
        zeroline=False,
        tickformat='$,.0f',
        side='left'
    )
    
    return fig

def create_combined_overview_chart(fan_datasets: dict, intraday_data: pd.DataFrame = None):
    """Create combined overview chart showing all fans."""
    if not fan_datasets:
        return None
    
    theme = create_plotly_theme()
    fig = go.Figure()
    
    # Color mapping for different anchor types
    colors = {
        'high': {'entry': COLORS['bear'], 'exit': COLORS['success']},
        'close': {'entry': COLORS['warning'], 'exit': COLORS['primary']},
        'low': {'entry': COLORS['error'], 'exit': COLORS['bull']}
    }
    
    # Add all fan lines
    for anchor_name, fan_df in fan_datasets.items():
        if fan_df is None or fan_df.empty:
            continue
        
        color_set = colors.get(anchor_name, colors['close'])
        anchor_type = fan_df.attrs.get('anchor_type', anchor_name.upper())
        
        # Exit lines
        fig.add_trace(go.Scatter(
            x=fan_df['TS'],
            y=fan_df['Exit'],
            name=f'{anchor_type} Exit',
            line=dict(width=2, color=color_set['exit']),
            hovertemplate=f'<b>{anchor_type} Exit</b><br>Time: %{{x|%H:%M}}<br>Price: $%{{y:,.2f}}<br><extra></extra>'
        ))
        
        # Entry lines
        fig.add_trace(go.Scatter(
            x=fan_df['TS'],
            y=fan_df['Entry'],
            name=f'{anchor_type} Entry',
            line=dict(width=2, color=color_set['entry'], dash='dot'),
            hovertemplate=f'<b>{anchor_type} Entry</b><br>Time: %{{x|%H:%M}}<br>Price: $%{{y:,.2f}}<br><extra></extra>'
        ))
    
    # Add SPX overlay
    if intraday_data is not None and not intraday_data.empty:
        fig.add_trace(go.Scatter(
            x=intraday_data['TS'],
            y=intraday_data['Close'],
            name='SPX (30m)',
            line=dict(width=3, color=COLORS['neutral']),
            hovertemplate='<b>SPX Price</b><br>Time: %{x|%H:%M}<br>Price: $%{y:,.2f}<br><extra></extra>'
        ))
    
    # Apply styling
    fig.update_layout(
        title=dict(
            text='<b>📊 All Anchor Fans Overview</b>',
            font=dict(family=theme['font_family'], size=24, color=theme['text_color']),
            x=0.02
        ),
        height=500,
        margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor=theme['bg_color'],
        paper_bgcolor=theme['paper_color'],
        font=dict(family=theme['font_family'], color=theme['text_color']),
        legend=dict(
            orientation='v',
            yanchor='top',
            y=0.98,
            xanchor='left',
            x=1.02,
            bgcolor='rgba(0,0,0,0)'
        ),
        dragmode='pan'
    )
    
    fig.update_xaxes(
        title='<b>Trading Hours</b>',
        showgrid=True,
        gridcolor=theme['grid_color'],
        rangeslider=dict(visible=True)
    )
    
    fig.update_yaxes(
        title='<b>SPX Price ($)</b>',
        showgrid=True,
        gridcolor=theme['grid_color'],
        tickformat='$,.0f'
    )
    
    return fig

def display_premium_charts(fan_datasets: dict, intraday_data: pd.DataFrame = None):
    """Display all charts with premium styling."""
    if not fan_datasets:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">📈</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">No Chart Data Available</div>
                <div style="color:var(--text-tertiary);">Generate forecasts first to view charts</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return
    
    st.markdown(
        """
        <div class="section-header">📈 Fan Charts</div>
        """,
        unsafe_allow_html=True
    )
    
    # Combined overview chart
    st.markdown("### 📊 Combined Overview")
    overview_chart = create_combined_overview_chart(fan_datasets, intraday_data)
    if overview_chart:
        st.plotly_chart(
            overview_chart,
            use_container_width=True,
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['select2d', 'lasso2d']
            }
        )
    
    # Individual charts in tabs
    st.markdown("### 📋 Individual Anchor Charts")
    tab_high, tab_close, tab_low = st.tabs(["📈 HIGH Anchor", "⚡ CLOSE Anchor", "📉 LOW Anchor"])
    
    with tab_high:
        df = fan_datasets.get('high')
        if df is not None and not df.empty:
            fig = create_fan_chart(df, "HIGH Anchor Fan — Resistance Levels", intraday_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
        else:
            st.error("❌ HIGH anchor data not available")
    
    with tab_close:
        df = fan_datasets.get('close')
        if df is not None and not df.empty:
            fig = create_fan_chart(df, "CLOSE Anchor Fan — Consensus Levels", intraday_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
        else:
            st.error("❌ CLOSE anchor data not available")
    
    with tab_low:
        df = fan_datasets.get('low')
        if df is not None and not df.empty:
            fig = create_fan_chart(df, "LOW Anchor Fan — Support Levels", intraday_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
        else:
            st.error("❌ LOW anchor data not available")

# ===== MAIN INTEGRATION FUNCTION =====

def handle_fan_generation_and_display(anchor_config: dict, forecast_date: date):
    """Main function to handle fan generation and display."""
    if not anchor_config or not anchor_config.get('is_locked', False):
        return {}
    
    # Generate fan data
    fan_data = generate_all_fans(anchor_config, forecast_date)
    
    if fan_data:
        st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
        
        # Display data tables
        display_fan_data_tables(fan_data)
        
        st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
        
        # Fetch intraday data for charts
        intraday_1m = fetch_spx_intraday_1m(forecast_date)
        intraday_30m = to_30m(intraday_1m)
        
        # Display charts
        display_premium_charts(fan_data, intraday_30m)
        
        return {
            'fan_data': fan_data,
            'intraday_30m': intraday_30m,
            'charts_displayed': True,
            'intraday_available': not intraday_30m.empty
        }
    
    return {}

# ===== INTEGRATION INTO MAIN FLOW =====
# Add this after the anchor section when forecasts are generated

if st.session_state.get("forecasts_generated", False) and anchor_section_results.get('ready_for_forecast', False):
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    
    # Handle fan generation and display
    fan_results = handle_fan_generation_and_display(
        anchor_section_results['anchor_config'], 
        forecast_date
    )

# ===== ENTRY DETECTION SYSTEM =====

def detect_entry_signals(fan_df: pd.DataFrame, intraday_data: pd.DataFrame, tolerance: float, rule_type: str) -> dict:
    """
    Detect entry signals for a specific fan with premium analytics.
    Preserves original detection logic with enhanced reporting.
    """
    if fan_df.empty or intraday_data.empty:
        return {
            'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
            'signal_time': '—',
            'signal_type': '—',
            'spx_price': '—',
            'line_price': '—',
            'delta': '—',
            'status': 'No Data',
            'note': 'No intraday data available for detection',
            'confidence': 0
        }
    
    try:
        # Merge fan projections with intraday data (preserving original logic)
        merged = pd.merge(
            fan_df[['Time', 'Entry', 'Exit']], 
            intraday_data[['Time', 'Close']], 
            on='Time', 
            how='inner'
        )
        
        if merged.empty:
            return {
                'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
                'signal_time': '—',
                'signal_type': '—',
                'spx_price': '—',
                'line_price': '—',
                'delta': '—',
                'status': 'No Match',
                'note': 'No time alignment between projections and market data',
                'confidence': 0
            }
        
        # Detection logic (preserving original algorithm)
        for _, row in merged.iterrows():
            spx_close = float(row['Close'])
            exit_level = float(row['Exit'])
            entry_level = float(row['Entry'])
            
            candidates = []
            
            # Exit signal detection
            if rule_type.startswith("Close"):
                exit_valid = (spx_close >= exit_level and (spx_close - exit_level) <= tolerance)
            else:
                exit_valid = abs(spx_close - exit_level) <= tolerance
            
            if exit_valid:
                delta = abs(spx_close - exit_level)
                confidence = max(0, 100 - (delta / tolerance * 100))
                candidates.append({
                    'type': 'Exit↑',
                    'line_price': exit_level,
                    'delta': delta,
                    'confidence': confidence
                })
            
            # Entry signal detection
            if rule_type.startswith("Close"):
                entry_valid = (spx_close <= entry_level and (entry_level - spx_close) <= tolerance)
            else:
                entry_valid = abs(spx_close - entry_level) <= tolerance
            
            if entry_valid:
                delta = abs(spx_close - entry_level)
                confidence = max(0, 100 - (delta / tolerance * 100))
                candidates.append({
                    'type': 'Entry↓',
                    'line_price': entry_level,
                    'delta': delta,
                    'confidence': confidence
                })
            
            # Return first (earliest) signal found
            if candidates:
                best = min(candidates, key=lambda x: x['delta'])
                return {
                    'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
                    'signal_time': row['Time'],
                    'signal_type': best['type'],
                    'spx_price': round(spx_close, 2),
                    'line_price': round(best['line_price'], 2),
                    'delta': round(best['delta'], 2),
                    'status': 'Signal Detected',
                    'note': f"Rule: {rule_type[:15]}...",
                    'confidence': round(best['confidence'], 1)
                }
        
        # No signals found
        return {
            'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
            'signal_time': '—',
            'signal_type': '—',
            'spx_price': '—',
            'line_price': '—',
            'delta': '—',
            'status': 'No Signal',
            'note': f'No touches within ${tolerance:.2f} tolerance',
            'confidence': 0
        }
        
    except Exception as e:
        return {
            'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
            'signal_time': '—',
            'signal_type': '—',
            'spx_price': '—',
            'line_price': '—',
            'delta': '—',
            'status': 'Error',
            'note': f'Detection error: {str(e)[:50]}...',
            'confidence': 0
        }

def run_detection_analysis(fan_datasets: dict, intraday_data: pd.DataFrame, tolerance: float, rule_type: str) -> pd.DataFrame:
    """
    Run comprehensive entry detection analysis across all fans.
    """
    results = []
    
    for _, fan_df in fan_datasets.items():
        if fan_df is None or fan_df.empty:
            continue
        
        result = detect_entry_signals(fan_df, intraday_data, tolerance, rule_type)
        results.append(result)
    
    if results:
        results_df = pd.DataFrame(results)
        
        # Add metadata for tracking
        results_df.attrs.update({
            'detection_timestamp': datetime.now(),
            'tolerance_used': tolerance,
            'rule_type_used': rule_type,
            'total_fans_analyzed': len(results)
        })
        
        return results_df
    
    return pd.DataFrame()

# ===== DETECTION RESULTS DISPLAY =====

def render_detection_header(tolerance: float, rule_type: str):
    """Render premium detection results header."""
    st.markdown(
        """
        <div class="section-header">🎯 Entry Detection Analysis</div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown(
        f"""
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);line-height:1.6;">
            Real-time analysis of fan projections against actual SPX price action. 
            Identifies optimal entry and exit points based on your configured parameters.
        </div>
        """,
        unsafe_allow_html=True
    )

def render_detection_configuration(results_df: pd.DataFrame, tolerance: float, rule_type: str):
    """Render detection configuration summary."""
    if results_df.empty:
        return
    
    detection_time = results_df.attrs.get('detection_timestamp', datetime.now())
    
    st.markdown(
        f"""
        <div class="glass-card animate-slide-up">
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:var(--space-4);">
                <div>
                    <div style="font-weight:600;color:var(--text-secondary);margin-bottom:var(--space-1);">Detection Rule</div>
                    <div style="font-family:'JetBrains Mono',monospace;color:var(--primary);">{rule_type}</div>
                </div>
                <div>
                    <div style="font-weight:600;color:var(--text-secondary);margin-bottom:var(--space-1);">Tolerance</div>
                    <div style="font-family:'JetBrains Mono',monospace;color:var(--warning);">${tolerance:.2f}</div>
                </div>
                <div>
                    <div style="font-weight:600;color:var(--text-secondary);margin-bottom:var(--space-1);">Analysis Time</div>
                    <div style="font-family:'JetBrains Mono',monospace;">{detection_time.strftime('%H:%M:%S')}</div>
                </div>
                <div>
                    <div style="font-weight:600;color:var(--text-secondary);margin-bottom:var(--space-1);">Fans Analyzed</div>
                    <div style="font-family:'JetBrains Mono',monospace;color:var(--success);">{len(results_df)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def create_status_indicator(status: str) -> str:
    """Create visual status indicator for detection results."""
    status_map = {
        'Signal Detected': '🎯',
        'No Signal': '⭕',
        'No Data': '📊',
        'No Match': '🔍',
        'Error': '⚠️'
    }
    
    icon = status_map.get(status, '❓')
    return f"{icon} {status}"

def render_detection_results_table(results_df: pd.DataFrame):
    """Render premium detection results table."""
    if results_df.empty:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">🎯</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">No Detection Results</div>
                <div style="color:var(--text-tertiary);">Generate fan data first to run entry detection</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return
    
    # Prepare display data
    display_df = results_df.copy()
    display_df['Status_Display'] = display_df['status'].apply(create_status_indicator)
    
    # Enhanced dataframe display
    st.dataframe(
        display_df[[
            'fan_type', 'signal_time', 'signal_type', 'spx_price', 
            'line_price', 'delta', 'confidence', 'Status_Display', 'note'
        ]],
        use_container_width=True,
        hide_index=True,
        column_config={
            'fan_type': st.column_config.TextColumn('Anchor', width='small'),
            'signal_time': st.column_config.TextColumn('Time', width='small'),
            'signal_type': st.column_config.TextColumn('Signal', width='small'),
            'spx_price': st.column_config.NumberColumn('SPX Price', format='$%.2f'),
            'line_price': st.column_config.NumberColumn('Line Price', format='$%.2f'),
            'delta': st.column_config.NumberColumn('Delta', format='$%.2f'),
            'confidence': st.column_config.ProgressColumn('Confidence', min_value=0, max_value=100, format='%.1f%%'),
            'Status_Display': st.column_config.TextColumn('Status'),
            'note': st.column_config.TextColumn('Note')
        }
    )

def render_detection_analytics(results_df: pd.DataFrame, tolerance: float):
    """Render advanced analytics for detection results."""
    if results_df.empty:
        return
    
    # Calculate analytics
    signals_detected = len(results_df[results_df['status'] == 'Signal Detected'])
    total_fans = len(results_df)
    detection_rate = (signals_detected / total_fans * 100) if total_fans > 0 else 0
    
    # Average confidence for detected signals
    detected_signals = results_df[results_df['status'] == 'Signal Detected']
    avg_confidence = detected_signals['confidence'].mean() if not detected_signals.empty else 0
    
    # Average delta for detected signals
    avg_delta = detected_signals['delta'].mean() if not detected_signals.empty else 0
    
    # First signal time
    first_signal_time = '—'
    if not detected_signals.empty:
        first_signal_time = detected_signals.iloc[0]['signal_time']
    
    # Signal type distribution
    signal_types = detected_signals['signal_type'].value_counts() if not detected_signals.empty else {}
    
    st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
    
    # Analytics grid
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_color = "success" if detection_rate >= 50 else ("warning" if detection_rate >= 25 else "error")
        st.metric(
            "🎯 Detection Rate",
            f"{detection_rate:.1f}%",
            delta=f"{signals_detected}/{total_fans} fans"
        )
    
    with col2:
        if avg_confidence > 0:
            confidence_color = "success" if avg_confidence >= 70 else ("warning" if avg_confidence >= 40 else "error")
            st.metric(
                "📊 Avg Confidence",
                f"{avg_confidence:.1f}%",
                delta="Signal quality"
            )
        else:
            st.metric("📊 Avg Confidence", "—")
    
    with col3:
        if avg_delta > 0:
            st.metric(
                "📏 Avg Delta",
                f"${avg_delta:.2f}",
                delta=f"±${tolerance:.2f} tolerance"
            )
        else:
            st.metric("📏 Avg Delta", "—")
    
    with col4:
        st.metric("⏰ First Signal", first_signal_time)
    
    # Signal breakdown if we have signals
    if not detected_signals.empty:
        st.markdown('<div style="margin:var(--space-4) 0;"></div>', unsafe_allow_html=True)
        
        st.markdown(
            """
            <div class="premium-card">
                <div style="font-weight:700;margin-bottom:var(--space-3);color:var(--primary);">
                    📈 Signal Breakdown
                </div>
            """,
            unsafe_allow_html=True
        )
        
        col_breakdown1, col_breakdown2 = st.columns(2)
        
        with col_breakdown1:
            # Signal type distribution
            entry_signals = len(detected_signals[detected_signals['signal_type'] == 'Entry↓'])
            exit_signals = len(detected_signals[detected_signals['signal_type'] == 'Exit↑'])
            
            st.markdown(
                f"""
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-3);">
                    <div style="text-align:center;padding:var(--space-3);background:rgba(255,59,48,0.1);border-radius:var(--radius-lg);">
                        <div style="font-size:var(--text-2xl);font-weight:700;color:#FF3B30;">{entry_signals}</div>
                        <div style="font-size:var(--text-sm);color:var(--text-tertiary);">Entry Signals</div>
                    </div>
                    <div style="text-align:center;padding:var(--space-3);background:rgba(52,199,89,0.1);border-radius:var(--radius-lg);">
                        <div style="font-size:var(--text-2xl);font-weight:700;color:#34C759;">{exit_signals}</div>
                        <div style="font-size:var(--text-sm);color:var(--text-tertiary);">Exit Signals</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        with col_breakdown2:
            # Confidence distribution
            high_conf = len(detected_signals[detected_signals['confidence'] >= 70])
            med_conf = len(detected_signals[(detected_signals['confidence'] >= 40) & (detected_signals['confidence'] < 70)])
            low_conf = len(detected_signals[detected_signals['confidence'] < 40])
            
            st.markdown(
                f"""
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:var(--space-2);">
                    <div style="text-align:center;padding:var(--space-2);background:rgba(52,199,89,0.1);border-radius:var(--radius-md);">
                        <div style="font-weight:700;color:#34C759;">{high_conf}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">High</div>
                    </div>
                    <div style="text-align:center;padding:var(--space-2);background:rgba(255,149,0,0.1);border-radius:var(--radius-md);">
                        <div style="font-weight:700;color:#FF9500;">{med_conf}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">Med</div>
                    </div>
                    <div style="text-align:center;padding:var(--space-2);background:rgba(255,59,48,0.1);border-radius:var(--radius-md);">
                        <div style="font-weight:700;color:#FF3B30;">{low_conf}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">Low</div>
                    </div>
                </div>
                <div style="text-align:center;margin-top:var(--space-2);font-size:var(--text-sm);color:var(--text-tertiary);">
                    Confidence Distribution
                </div>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown('</div>', unsafe_allow_html=True)

# ===== REAL-TIME MONITORING SYSTEM =====

def create_live_monitoring_panel(fan_datasets: dict, tolerance: float, rule_type: str):
    """Create live monitoring panel for continuous detection."""
    if not fan_datasets:
        return
    
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="section-header">📡 Live Monitoring</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Real-time monitoring of entry signals as market data updates. 
            Automatically refreshes every 60 seconds during market hours.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Auto-refresh control
    col_refresh, col_status = st.columns([1, 2])
    
    with col_refresh:
        auto_refresh = st.toggle(
            "🔄 Auto-refresh",
            value=st.session_state.get('auto_refresh_monitoring', False),
            help="Automatically refresh detection every 60 seconds"
        )
        st.session_state.auto_refresh_monitoring = auto_refresh
        
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()
    
    with col_status:
        current_time = datetime.now()
        market_open = RTH_START <= current_time.time() <= RTH_END
        market_status = "🟢 MARKET OPEN" if market_open else "🔴 MARKET CLOSED"
        
        last_refresh = st.session_state.get('last_detection_refresh', current_time)
        time_since = (current_time - last_refresh).total_seconds()
        
        st.markdown(
            f"""
            <div style="background:var(--surface);padding:var(--space-3);border-radius:var(--radius-lg);border:1px solid var(--border);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-weight:600;">{market_status}</div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Last update: {time_since:.0f}s ago
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-family:'JetBrains Mono',monospace;">{current_time.strftime('%H:%M:%S')}</div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Current time</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Auto-refresh logic
    if auto_refresh and market_open:
        time.sleep(1)  # Brief pause for UI
        st.rerun()

# ===== MAIN DETECTION INTEGRATION =====

def handle_detection_analysis(fan_datasets: dict, forecast_date: date, tolerance: float, rule_type: str):
    """Main function to handle complete detection analysis."""
    if not fan_datasets:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">🎯</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">Detection Analysis Unavailable</div>
                <div style="color:var(--text-tertiary);">Generate fan data first to run entry detection</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return {}
    
    # Fetch latest intraday data
    intraday_1m = fetch_spx_intraday_1m(forecast_date)
    intraday_30m = to_30m(intraday_1m)
    
    if intraday_30m.empty:
        st.warning("⚠️ No intraday data available for detection analysis")
        return {}
    
    # Render detection header
    render_detection_header(tolerance, rule_type)
    
    # Run detection analysis
    results = run_detection_analysis(fan_datasets, intraday_30m, tolerance, rule_type)
    
    # Display configuration
    render_detection_configuration(results, tolerance, rule_type)
    
    st.markdown('<div style="margin:var(--space-4) 0;"></div>', unsafe_allow_html=True)
    
    # Display results table
    render_detection_results_table(results)
    
    # Display analytics
    render_detection_analytics(results, tolerance)
    
    # Live monitoring panel
    create_live_monitoring_panel(fan_datasets, tolerance, rule_type)
    
    # Update session state
    st.session_state.last_detection_refresh = datetime.now()
    st.session_state.latest_detection_results = results
    
    return {
        'detection_results': results,
        'signals_found': len(results[results['status'] == 'Signal Detected']) if not results.empty else 0,
        'intraday_available': True,
        'analysis_completed': True
    }

# ===== INTEGRATION INTO MAIN FLOW =====
# Add this after the fan generation section

if fan_results.get('fan_data'):
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    
    # Handle detection analysis
    detection_results = handle_detection_analysis(
        fan_results['fan_data'],
        forecast_date,
        tolerance,
        rule_requirement
    )