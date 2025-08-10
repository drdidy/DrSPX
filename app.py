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

# ===== APPLY DESIGN SYSTEM =====
st.markdown(CSS_DESIGN_SYSTEM, unsafe_allow_html=True)
st.markdown(CSS_COMPONENTS, unsafe_allow_html=True)
st.markdown(DARK_MODE_SCRIPT, unsafe_allow_html=True)

# ===== ENHANCED DATA FETCHING SYSTEM =====
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

# ===== ENHANCED ANCHOR INPUT SYSTEM =====

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

# ===== ENTRY DETECTION SYSTEM WITH TP1/TP2 =====

def detect_trading_signals(fan_df: pd.DataFrame, intraday_data: pd.DataFrame, tolerance: float, rule_type: str) -> dict:
    """
    Detect trading signals for Entry, TP1, and TP2 levels with premium analytics.
    Preserves original detection logic with enhanced TP1/TP2 reporting.
    """
    if fan_df.empty or intraday_data.empty:
        return {
            'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
            'signal_time': '—',
            'signal_type': '—',
            'spx_price': '—',
            'target_price': '—',
            'delta': '—',
            'status': 'No Data',
            'note': 'No intraday data available for detection',
            'confidence': 0,
            'tp1_available': '—',
            'tp2_available': '—'
        }
    
    try:
        # Merge fan projections with intraday data (preserving original logic)
        merged = pd.merge(
            fan_df[['Time', 'Entry', 'TP1', 'TP2']], 
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
                'target_price': '—',
                'delta': '—',
                'status': 'No Match',
                'note': 'No time alignment between projections and market data',
                'confidence': 0,
                'tp1_available': '—',
                'tp2_available': '—'
            }
        
        # Enhanced detection logic for Entry/TP1/TP2
        for _, row in merged.iterrows():
            spx_close = float(row['Close'])
            entry_level = float(row['Entry'])
            tp1_level = float(row['TP1'])
            tp2_level = float(row['TP2'])
            
            candidates = []
            
            # Entry signal detection (preserving original logic)
            if rule_type.startswith("Close"):
                entry_valid = (spx_close <= entry_level and (entry_level - spx_close) <= tolerance)
            else:
                entry_valid = abs(spx_close - entry_level) <= tolerance
            
            if entry_valid:
                delta = abs(spx_close - entry_level)
                confidence = max(0, 100 - (delta / tolerance * 100))
                candidates.append({
                    'type': 'Entry ↓',
                    'target_price': entry_level,
                    'delta': delta,
                    'confidence': confidence,
                    'priority': 1  # Highest priority
                })
            
            # TP1 signal detection
            if rule_type.startswith("Close"):
                tp1_valid = (spx_close >= tp1_level and (spx_close - tp1_level) <= tolerance)
            else:
                tp1_valid = abs(spx_close - tp1_level) <= tolerance
            
            if tp1_valid:
                delta = abs(spx_close - tp1_level)
                confidence = max(0, 100 - (delta / tolerance * 100))
                candidates.append({
                    'type': 'TP1 ↑',
                    'target_price': tp1_level,
                    'delta': delta,
                    'confidence': confidence,
                    'priority': 2
                })
            
            # TP2 signal detection
            if rule_type.startswith("Close"):
                tp2_valid = (spx_close >= tp2_level and (spx_close - tp2_level) <= tolerance)
            else:
                tp2_valid = abs(spx_close - tp2_level) <= tolerance
            
            if tp2_valid:
                delta = abs(spx_close - tp2_level)
                confidence = max(0, 100 - (delta / tolerance * 100))
                candidates.append({
                    'type': 'TP2 ↑',
                    'target_price': tp2_level,
                    'delta': delta,
                    'confidence': confidence,
                    'priority': 3
                })
            
            # Return first (earliest) signal found, prioritizing Entry
            if candidates:
                best = min(candidates, key=lambda x: (x['priority'], x['delta']))
                
                # Calculate TP availability
                tp1_dist = abs(spx_close - tp1_level)
                tp2_dist = abs(spx_close - tp2_level)
                tp1_available = "✅" if tp1_dist <= tolerance else f"${tp1_dist:.2f}"
                tp2_available = "✅" if tp2_dist <= tolerance else f"${tp2_dist:.2f}"
                
                return {
                    'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
                    'signal_time': row['Time'],
                    'signal_type': best['type'],
                    'spx_price': round(spx_close, 2),
                    'target_price': round(best['target_price'], 2),
                    'delta': round(best['delta'], 2),
                    'status': 'Signal Detected',
                    'note': f"Rule: {rule_type[:15]}...",
                    'confidence': round(best['confidence'], 1),
                    'tp1_available': tp1_available,
                    'tp2_available': tp2_available
                }
        
        # No signals found
        return {
            'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
            'signal_time': '—',
            'signal_type': '—',
            'spx_price': '—',
            'target_price': '—',
            'delta': '—',
            'status': 'No Signal',
            'note': f'No touches within ${tolerance:.2f} tolerance',
            'confidence': 0,
            'tp1_available': '—',
            'tp2_available': '—'
        }
        
    except Exception as e:
        return {
            'fan_type': fan_df.attrs.get('anchor_type', 'UNKNOWN'),
            'signal_time': '—',
            'signal_type': '—',
            'spx_price': '—',
            'target_price': '—',
            'delta': '—',
            'status': 'Error',
            'note': f'Detection error: {str(e)[:50]}...',
            'confidence': 0,
            'tp1_available': '—',
            'tp2_available': '—'
        }

def run_trading_detection_analysis(fan_datasets: dict, intraday_data: pd.DataFrame, tolerance: float, rule_type: str) -> pd.DataFrame:
    """
    Run comprehensive trading detection analysis across all fans with TP1/TP2.
    """
    results = []
    
    for _, fan_df in fan_datasets.items():
        if fan_df is None or fan_df.empty:
            continue
        
        result = detect_trading_signals(fan_df, intraday_data, tolerance, rule_type)
        results.append(result)
    
    if results:
        results_df = pd.DataFrame(results)
        
        # Add metadata for tracking
        results_df.attrs.update({
            'detection_timestamp': datetime.now(),
            'tolerance_used': tolerance,
            'rule_type_used': rule_type,
            'total_fans_analyzed': len(results),
            'tp_system_enabled': True
        })
        
        return results_df
    
    return pd.DataFrame()

# ===== TRADING DETECTION DISPLAY =====

def render_trading_detection_header(tolerance: float, rule_type: str):
    """Render premium trading detection header."""
    st.markdown(
        """
        <div class="section-header">🎯 Trading Signal Detection</div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown(
        f"""
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);line-height:1.6;">
            Real-time detection of Entry, TP1, and TP2 signals based on actual SPX price action. 
            Optimize your position entry and profit-taking with precision timing.
        </div>
        """,
        unsafe_allow_html=True
    )

def render_trading_configuration(results_df: pd.DataFrame, tolerance: float, rule_type: str):
    """Render trading detection configuration summary."""
    if results_df.empty:
        return
    
    detection_time = results_df.attrs.get('detection_timestamp', datetime.now())
    
    st.markdown(
        f"""
        <div class="glass-card animate-slide-up">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-4);">
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
                    <div style="font-weight:600;color:var(--text-secondary);margin-bottom:var(--space-1);">TP System</div>
                    <div style="font-family:'JetBrains Mono',monospace;color:var(--success);">TP1/TP2 Enabled</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def create_trading_status_indicator(status: str) -> str:
    """Create visual status indicator for trading detection results."""
    status_map = {
        'Signal Detected': '🎯',
        'No Signal': '⭕',
        'No Data': '📊',
        'No Match': '🔍',
        'Error': '⚠️'
    }
    
    icon = status_map.get(status, '❓')
    return f"{icon} {status}"

def render_trading_results_table(results_df: pd.DataFrame):
    """Render premium trading detection results table with TP1/TP2."""
    if results_df.empty:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">🎯</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">No Trading Signals</div>
                <div style="color:var(--text-tertiary);">Generate trading data first to run signal detection</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return
    
    # Prepare display data
    display_df = results_df.copy()
    display_df['Status_Display'] = display_df['status'].apply(create_trading_status_indicator)
    
    # Enhanced dataframe display with TP1/TP2 columns
    st.dataframe(
        display_df[[
            'fan_type', 'signal_time', 'signal_type', 'spx_price', 
            'target_price', 'delta', 'confidence', 'tp1_available', 
            'tp2_available', 'Status_Display', 'note'
        ]],
        use_container_width=True,
        hide_index=True,
        column_config={
            'fan_type': st.column_config.TextColumn('Anchor', width='small'),
            'signal_time': st.column_config.TextColumn('Time', width='small'),
            'signal_type': st.column_config.TextColumn('Signal', width='small'),
            'spx_price': st.column_config.NumberColumn('SPX Price', format='$%.2f'),
            'target_price': st.column_config.NumberColumn('Target Price', format='$%.2f'),
            'delta': st.column_config.NumberColumn('Delta', format='$%.2f'),
            'confidence': st.column_config.ProgressColumn('Confidence', min_value=0, max_value=100, format='%.1f%%'),
            'tp1_available': st.column_config.TextColumn('TP1 Status', help='TP1 target availability'),
            'tp2_available': st.column_config.TextColumn('TP2 Status', help='TP2 target availability'),
            'Status_Display': st.column_config.TextColumn('Status'),
            'note': st.column_config.TextColumn('Note')
        }
    )

def render_trading_analytics(results_df: pd.DataFrame, tolerance: float):
    """Render advanced trading analytics for detection results."""
    if results_df.empty:
        return
    
    # Calculate trading analytics
    signals_detected = len(results_df[results_df['status'] == 'Signal Detected'])
    total_anchors = len(results_df)
    detection_rate = (signals_detected / total_anchors * 100) if total_anchors > 0 else 0
    
    # Separate by signal type
    detected_signals = results_df[results_df['status'] == 'Signal Detected']
    entry_signals = len(detected_signals[detected_signals['signal_type'] == 'Entry ↓'])
    tp1_signals = len(detected_signals[detected_signals['signal_type'] == 'TP1 ↑'])
    tp2_signals = len(detected_signals[detected_signals['signal_type'] == 'TP2 ↑'])
    
    # Average metrics
    avg_confidence = detected_signals['confidence'].mean() if not detected_signals.empty else 0
    avg_delta = detected_signals['delta'].mean() if not detected_signals.empty else 0
    
    # First signal
    first_signal_time = '—'
    first_signal_type = '—'
    if not detected_signals.empty:
        first_signal_time = detected_signals.iloc[0]['signal_time']
        first_signal_type = detected_signals.iloc[0]['signal_type']
    
    st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
    
    # Analytics grid
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🎯 Detection Rate",
            f"{detection_rate:.1f}%",
            delta=f"{signals_detected}/{total_anchors} anchors"
        )
    
    with col2:
        if avg_confidence > 0:
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
        st.metric(
            "⏰ First Signal", 
            first_signal_time,
            delta=first_signal_type
        )
    
    # Trading signal breakdown
    if not detected_signals.empty:
        st.markdown('<div style="margin:var(--space-4) 0;"></div>', unsafe_allow_html=True)
        
        st.markdown(
            """
            <div class="premium-card">
                <div style="font-weight:700;margin-bottom:var(--space-3);color:var(--primary);">
                    📈 Trading Signal Breakdown
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        col_trading1, col_trading2 = st.columns(2)
        
        with col_trading1:
            # Signal type distribution using columns
            col_entry, col_tp1, col_tp2 = st.columns(3)
            
            with col_entry:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-3);background:rgba(255,59,48,0.1);border-radius:var(--radius-lg);">
                        <div style="font-size:var(--text-2xl);font-weight:700;color:#FF3B30;">{entry_signals}</div>
                        <div style="font-size:var(--text-sm);color:var(--text-tertiary);">Entry</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col_tp1:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-3);background:rgba(255,149,0,0.1);border-radius:var(--radius-lg);">
                        <div style="font-size:var(--text-2xl);font-weight:700;color:#FF9500;">{tp1_signals}</div>
                        <div style="font-size:var(--text-sm);color:var(--text-tertiary);">TP1</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col_tp2:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-3);background:rgba(52,199,89,0.1);border-radius:var(--radius-lg);">
                        <div style="font-size:var(--text-2xl);font-weight:700;color:#34C759;">{tp2_signals}</div>
                        <div style="font-size:var(--text-sm);color:var(--text-tertiary);">TP2</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        
        with col_trading2:
            # Confidence distribution
            high_conf = len(detected_signals[detected_signals['confidence'] >= 70])
            med_conf = len(detected_signals[(detected_signals['confidence'] >= 40) & (detected_signals['confidence'] < 70)])
            low_conf = len(detected_signals[detected_signals['confidence'] < 40])
            
            col_high, col_med, col_low = st.columns(3)
            
            with col_high:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-2);background:rgba(52,199,89,0.1);border-radius:var(--radius-md);">
                        <div style="font-weight:700;color:#34C759;">{high_conf}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">High</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col_med:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-2);background:rgba(255,149,0,0.1);border-radius:var(--radius-md);">
                        <div style="font-weight:700;color:#FF9500;">{med_conf}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">Med</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col_low:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-2);background:rgba(255,59,48,0.1);border-radius:var(--radius-md);">
                        <div style="font-weight:700;color:#FF3B30;">{low_conf}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">Low</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            st.markdown(
                """
                <div style="text-align:center;margin-top:var(--space-2);font-size:var(--text-sm);color:var(--text-tertiary);">
                    Confidence Distribution
                </div>
                """,
                unsafe_allow_html=True
            )

# ===== REAL-TIME TRADING MONITORING =====

def create_trading_monitoring_panel(fan_datasets: dict, tolerance: float, rule_type: str):
    """Create live trading monitoring panel for continuous signal detection."""
    if not fan_datasets:
        return
    
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="section-header">📡 Live Trading Monitor</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Real-time monitoring of Entry, TP1, and TP2 signals. 
            Automatically refreshes during market hours for active trading.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Enhanced monitoring controls
    col_refresh, col_alerts, col_status = st.columns([1, 1, 2])
    
    with col_refresh:
        auto_refresh = st.toggle(
            "🔄 Auto-refresh",
            value=st.session_state.get('auto_refresh_trading', False),
            help="Automatically refresh trading signals every 60 seconds"
        )
        st.session_state.auto_refresh_trading = auto_refresh
        
        if st.button("🔄 Refresh Signals", use_container_width=True):
            st.rerun()
    
    with col_alerts:
        alert_mode = st.selectbox(
            "🔔 Alert Mode",
            options=["All Signals", "Entry Only", "TP1/TP2 Only"],
            index=0,
            help="Choose which signals to highlight"
        )
        
        sound_alerts = st.toggle(
            "🔊 Sound Alerts",
            value=st.session_state.get('sound_alerts', False),
            help="Enable sound notifications (browser dependent)"
        )
        st.session_state.sound_alerts = sound_alerts
    
    with col_status:
        current_time = datetime.now()
        market_open = RTH_START <= current_time.time() <= RTH_END
        market_status = "🟢 MARKET OPEN" if market_open else "🔴 MARKET CLOSED"
        
        last_refresh = st.session_state.get('last_trading_refresh', current_time)
        time_since = (current_time - last_refresh).total_seconds()
        
        # Next refresh countdown
        next_refresh_in = 60 - (time_since % 60) if auto_refresh else 0
        
        st.markdown(
            f"""
            <div style="background:var(--surface);padding:var(--space-3);border-radius:var(--radius-lg);border:1px solid var(--border);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-2);">
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
                {"<div style='text-align:center;font-size:var(--text-sm);color:var(--warning);'>Next refresh in " + str(int(next_refresh_in)) + "s</div>" if auto_refresh and market_open else ""}
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Auto-refresh logic with market hours check
    if auto_refresh and market_open:
        time.sleep(1)  # Brief pause for UI
        st.rerun()

# ===== MAIN TRADING DETECTION INTEGRATION =====

def handle_trading_detection_analysis(fan_datasets: dict, forecast_date: date, tolerance: float, rule_type: str):
    """Main function to handle complete trading detection analysis with TP1/TP2."""
    if not fan_datasets:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">🎯</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">Trading Detection Unavailable</div>
                <div style="color:var(--text-tertiary);">Generate trading data first to run signal detection</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return {}
    
    # Fetch latest intraday data
    intraday_1m = fetch_intraday_data(forecast_date)
    intraday_30m = convert_to_30min_bars(intraday_1m)
    
    if intraday_30m.empty:
        st.warning("⚠️ No intraday data available for trading detection")
        return {}
    
    # Render detection header
    render_trading_detection_header(tolerance, rule_type)
    
    # Run trading detection analysis
    results = run_trading_detection_analysis(fan_datasets, intraday_30m, tolerance, rule_type)
    
    # Display configuration
    render_trading_configuration(results, tolerance, rule_type)
    
    st.markdown('<div style="margin:var(--space-4) 0;"></div>', unsafe_allow_html=True)
    
    # Display results table
    render_trading_results_table(results)
    
    # Display trading analytics
    render_trading_analytics(results, tolerance)
    
    # Live trading monitoring panel
    create_trading_monitoring_panel(fan_datasets, tolerance, rule_type)
    
    # Update session state
    st.session_state.last_trading_refresh = datetime.now()
    st.session_state.latest_trading_results = results
    
    return {
        'detection_results': results,
        'entry_signals': len(results[results['signal_type'] == 'Entry ↓']) if not results.empty else 0,
        'tp1_signals': len(results[results['signal_type'] == 'TP1 ↑']) if not results.empty else 0,
        'tp2_signals': len(results[results['signal_type'] == 'TP2 ↑']) if not results.empty else 0,
        'total_signals': len(results[results['status'] == 'Signal Detected']) if not results.empty else 0,
        'intraday_available': True,
        'trading_analysis_completed': True
    }

# ===== INTEGRATION INTO MAIN FLOW =====
# Add this after the trading data generation section

if 'trading_results' in locals() and trading_results.get('fan_data'):
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    
    # Handle trading detection analysis
    detection_results = handle_trading_detection_analysis(
        trading_results['fan_data'],
        forecast_date,
        tolerance,
        rule_requirement
    )

# ===== CONTRACT LINE SYSTEM =====

def render_contract_header():
    """Render professional header for contract line section."""
    st.markdown(
        """
        <div class="section-header">📋 Contract Line Generator</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);line-height:1.6;">
            Generate precise contract projections using two low points. This system calculates 
            the optimal slope for <strong>Tuesday</strong> and <strong>Thursday</strong> plays with 
            institutional-grade precision.
        </div>
        """,
        unsafe_allow_html=True
    )

def create_contract_inputs():
    """Create professional contract input components with real-time validation."""
    st.markdown(
        """
        <div class="premium-card animate-slide-up">
            <div class="subsection-header">
                <span style="font-size:1.5rem;">📊</span>
                <span style="color:var(--primary);font-weight:700;font-size:var(--text-2xl);">Contract Anchor Points</span>
            </div>
            <div style="color:var(--text-tertiary);margin-bottom:var(--space-4);font-size:var(--text-sm);">
                Configure two overnight option low points that typically rise $400-$500. 
                These points will establish your contract slope for precise projections.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Contract input layout with validation
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.markdown(
            """
            <div style="background:rgba(0,122,255,0.05);padding:var(--space-3);border-radius:var(--radius-lg);margin-bottom:var(--space-3);">
                <div style="font-weight:600;color:var(--primary);margin-bottom:var(--space-2);">📍 Low Point #1</div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);">First reference point</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        low1_time = st.time_input(
            "Time",
            value=time(2, 0),
            step=300,
            key="contract_low1_time",
            help="Time of first low point (typically early morning)"
        )
        
        low1_price = st.number_input(
            "Price ($)",
            value=10.00,
            step=TICK,
            min_value=0.01,
            max_value=1000.0,
            format="%.2f",
            key="contract_low1_price",
            help="Contract price at first low point"
        )
        
        # Real-time validation for Low Point 1
        low1_valid = True
        if low1_price <= 0:
            st.error("⚠️ Price must be positive")
            low1_valid = False
        elif low1_price > 500:
            st.warning("💡 Price seems high for options - verify")
        elif low1_price < 0.50:
            st.warning("💡 Price seems low - verify")
            
        if low1_valid:
            st.markdown(
                f"""
                <div style="background:rgba(52,199,89,0.1);color:#34C759;padding:var(--space-2);
                     border-radius:var(--radius-md);font-size:var(--text-sm);margin-top:var(--space-2);">
                    ✅ Low #1: ${low1_price:.2f} @ {low1_time.strftime('%H:%M')}
                </div>
                """,
                unsafe_allow_html=True
            )

    with col2:
        st.markdown(
            """
            <div style="background:rgba(52,199,89,0.05);padding:var(--space-3);border-radius:var(--radius-lg);margin-bottom:var(--space-3);">
                <div style="font-weight:600;color:var(--success);margin-bottom:var(--space-2);">📍 Low Point #2</div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Second reference point</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        low2_time = st.time_input(
            "Time ",
            value=time(3, 30),
            step=300,
            key="contract_low2_time",
            help="Time of second low point (must be after first)"
        )
        
        low2_price = st.number_input(
            "Price ($) ",
            value=12.00,
            step=TICK,
            min_value=0.01,
            max_value=1000.0,
            format="%.2f",
            key="contract_low2_price",
            help="Contract price at second low point"
        )
        
        # Real-time validation for Low Point 2
        low2_valid = True
        if low2_price <= 0:
            st.error("⚠️ Price must be positive")
            low2_valid = False
        elif low2_price > 500:
            st.warning("💡 Price seems high for options - verify")
        elif low2_price < 0.50:
            st.warning("💡 Price seems low - verify")
            
        # Time sequence validation
        if low2_time <= low1_time:
            st.error("⚠️ Low #2 time must be after Low #1")
            low2_valid = False
            
        if low2_valid and low1_valid:
            st.markdown(
                f"""
                <div style="background:rgba(52,199,89,0.1);color:#34C759;padding:var(--space-2);
                     border-radius:var(--radius-md);font-size:var(--text-sm);margin-top:var(--space-2);">
                    ✅ Low #2: ${low2_price:.2f} @ {low2_time.strftime('%H:%M')}
                </div>
                """,
                unsafe_allow_html=True
            )

    with col3:
        st.markdown(
            """
            <div style="background:rgba(139,92,246,0.05);padding:var(--space-3);border-radius:var(--radius-lg);margin-bottom:var(--space-3);">
                <div style="font-weight:600;color:var(--neutral);margin-bottom:var(--space-2);">⚙️ Configuration</div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Strategy & display options</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        strategy_label = st.selectbox(
            "Strategy Type",
            options=["Manual", "Tuesday Play", "Thursday Play"],
            index=0,
            help="Select the trading strategy for this contract line"
        )
        
        include_extended = st.toggle(
            "Include Extended Hours",
            value=False,
            help="Include pre-market hours (07:30-08:30) in projections"
        )
        
        rth_only = not include_extended
        
        # Strategy info display
        if strategy_label == "Tuesday Play":
            st.markdown(
                """
                <div style="background:rgba(139,92,246,0.1);padding:var(--space-2);border-radius:var(--radius-md);font-size:var(--text-sm);">
                    📈 Best mid-week momentum setups
                </div>
                """,
                unsafe_allow_html=True
            )
        elif strategy_label == "Thursday Play":
            st.markdown(
                """
                <div style="background:rgba(139,92,246,0.1);padding:var(--space-2);border-radius:var(--radius-md);font-size:var(--text-sm);">
                    📊 Wednesday pricing insights
                </div>
                """,
                unsafe_allow_html=True
            )
    
    return {
        'low1_time': low1_time,
        'low1_price': low1_price,
        'low1_valid': low1_valid,
        'low2_time': low2_time,
        'low2_price': low2_price,
        'low2_valid': low2_valid,
        'strategy_label': strategy_label,
        'rth_only': rth_only,
        'all_valid': low1_valid and low2_valid
    }

def render_contract_validation_and_generation(contract_inputs: dict, forecast_date: date):
    """Render validation status and generation controls for contract line."""
    all_valid = contract_inputs['all_valid']
    
    # Validation Status Card
    if all_valid:
        # Calculate preview metrics
        t1 = datetime.combine(forecast_date, contract_inputs['low1_time'])
        t2 = datetime.combine(forecast_date, contract_inputs['low2_time'])
        blocks = spx_blocks_between(t1, t2)
        
        if blocks > 0:
            slope = (contract_inputs['low2_price'] - contract_inputs['low1_price']) / blocks
            price_change = contract_inputs['low2_price'] - contract_inputs['low1_price']
            time_span = (t2 - t1).total_seconds() / 3600  # hours
            
            st.markdown(
                f"""
                <div class="glass-card" style="background:rgba(52,199,89,0.1);border-color:#34C759;">
                    <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4);">
                        <span style="font-size:1.5rem;">✅</span>
                        <div>
                            <div style="font-weight:700;color:#34C759;">Contract Line Ready</div>
                            <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                                All inputs validated • Ready to generate projections
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Preview metrics using columns
            col_slope, col_change, col_time, col_blocks = st.columns(4)
            
            with col_slope:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                        <div style="font-weight:700;font-family:'JetBrains Mono',monospace;">{slope:+.4f}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">SLOPE/BLOCK</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col_change:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                        <div style="font-weight:700;font-family:'JetBrains Mono',monospace;">${price_change:+.2f}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">PRICE CHANGE</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col_time:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                        <div style="font-weight:700;font-family:'JetBrains Mono',monospace;">{time_span:.1f}h</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">TIME SPAN</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col_blocks:
                st.markdown(
                    f"""
                    <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                        <div style="font-weight:700;font-family:'JetBrains Mono',monospace;">{blocks}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary);">SPX BLOCKS</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.error("⚠️ Invalid time span - Low #2 must be significantly after Low #1")
            all_valid = False
    else:
        issues = []
        if not contract_inputs['low1_valid']:
            issues.append("Low Point #1")
        if not contract_inputs['low2_valid']:
            issues.append("Low Point #2")
            
        st.markdown(
            f"""
            <div class="glass-card" style="background:rgba(255,149,0,0.1);border-color:#FF9500;">
                <div style="display:flex;align-items:center;gap:var(--space-3);">
                    <span style="font-size:1.5rem;">⚠️</span>
                    <div>
                        <div style="font-weight:700;color:#FF9500;">Validation Issues</div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Fix issues with: {', '.join(issues)}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Generation Controls
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if all_valid:
            if st.button("🚀 Generate Contract Line", use_container_width=True, type="primary"):
                return 'generate'
        else:
            st.button("🚀 Fix Issues First", use_container_width=True, disabled=True)
    
    with col2:
        if 'contract_data' in st.session_state:
            if st.button("🗑️ Clear Contract", use_container_width=True):
                del st.session_state.contract_data
                st.rerun()
        else:
            st.button("🗑️ No Contract Data", use_container_width=True, disabled=True)
    
    return 'wait' if all_valid else 'invalid'

def generate_contract_line(contract_inputs: dict, forecast_date: date):
    """Generate contract line with comprehensive data."""
    try:
        # Calculate base parameters (preserving original logic)
        t1 = datetime.combine(forecast_date, contract_inputs['low1_time'])
        t2 = datetime.combine(forecast_date, contract_inputs['low2_time'])
        blocks = spx_blocks_between(t1, t2)
        
        if blocks <= 0:
            raise CalculationError("Invalid time span between contract points")
        
        slope = (contract_inputs['low2_price'] - contract_inputs['low1_price']) / blocks
        
        # Generate time slots based on RTH preference
        time_slots = SPX_SLOTS if contract_inputs['rth_only'] else EXTENDED_SLOTS
        
        # Build contract data
        contract_rows = []
        for time_slot in time_slots:
            try:
                hour, minute = map(int, time_slot.split(":"))
                target_datetime = datetime.combine(forecast_date, time(hour, minute))
                slot_blocks = spx_blocks_between(t1, target_datetime)
                
                projected_price = contract_inputs['low1_price'] + (slope * slot_blocks)
                tick_rounded = round_to_tick(projected_price)
                
                contract_rows.append({
                    'Time': time_slot,
                    'Projected': tick_rounded,
                    'Blocks': slot_blocks,
                    'Slope_Applied': slope * slot_blocks,
                    'Base_Price': contract_inputs['low1_price']
                })
            except Exception:
                continue
        
        if not contract_rows:
            raise CalculationError("No valid contract projections generated")
        
        # Create DataFrame
        contract_df = pd.DataFrame(contract_rows)
        contract_df['TS'] = pd.to_datetime(BASELINE_DATE_STR + " " + contract_df['Time'])
        
        # Add metadata
        contract_df.attrs.update({
            'anchor_time': t1,
            'anchor_price': contract_inputs['low1_price'],
            'slope_per_block': slope,
            'strategy_label': contract_inputs['strategy_label'],
            'forecast_date': forecast_date,
            'generated_at': datetime.now(),
            'rth_only': contract_inputs['rth_only'],
            'low1_time': contract_inputs['low1_time'],
            'low1_price': contract_inputs['low1_price'],
            'low2_time': contract_inputs['low2_time'],
            'low2_price': contract_inputs['low2_price']
        })
        
        # Store in session state
        st.session_state.contract_data = {
            'dataframe': contract_df,
            'config': contract_inputs,
            'metadata': {
                'slope': slope,
                'blocks_span': blocks,
                'price_change': contract_inputs['low2_price'] - contract_inputs['low1_price'],
                'time_span_hours': (t2 - t1).total_seconds() / 3600
            }
        }
        
        return contract_df
        
    except Exception as e:
        st.error(f"⚠️ Contract generation failed: {str(e)}")
        return pd.DataFrame()

def display_contract_results():
    """Display contract line results with professional styling."""
    if 'contract_data' not in st.session_state:
        return
    
    contract_data = st.session_state.contract_data
    contract_df = contract_data['dataframe']
    metadata = contract_data['metadata']
    config = contract_data['config']
    
    st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
    
    # Results Header
    st.markdown(
        f"""
        <div class="premium-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-4);">
                <div>
                    <div style="font-weight:700;font-size:var(--text-2xl);color:var(--primary);">
                        📋 Contract Line Generated
                    </div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                        Strategy: {config['strategy_label']} • 
                        {len(contract_df)} projections • 
                        Generated: {contract_df.attrs['generated_at'].strftime('%H:%M:%S')}
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:var(--text-lg);font-weight:600;">${contract_df['Projected'].min():.2f} - ${contract_df['Projected'].max():.2f}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Price Range</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Contract metrics using columns
    col_slope, col_change, col_time, col_blocks = st.columns(4)
    
    with col_slope:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-size:var(--text-xl);font-weight:700;font-family:'JetBrains Mono',monospace;">
                    {metadata['slope']:+.4f}
                </div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">SLOPE/BLOCK</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col_change:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-size:var(--text-xl);font-weight:700;font-family:'JetBrains Mono',monospace;">
                    ${metadata['price_change']:+.2f}
                </div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">PRICE CHANGE</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col_time:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-size:var(--text-xl);font-weight:700;font-family:'JetBrains Mono',monospace;">
                    {metadata['time_span_hours']:.1f}h
                </div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">TIME SPAN</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col_blocks:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-size:var(--text-xl);font-weight:700;font-family:'JetBrains Mono',monospace;">
                    {metadata['blocks_span']}
                </div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">SPX BLOCKS</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Contract Data Table
    st.markdown("### 📊 Contract Projections")
    
    display_columns = ['Time', 'Projected', 'Blocks']
    st.dataframe(
        contract_df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            'Time': st.column_config.TextColumn('Time', width='small'),
            'Projected': st.column_config.NumberColumn('Projected ($)', format='$%.2f'),
            'Blocks': st.column_config.NumberColumn('Blocks', width='small')
        }
    )

def create_contract_lookup_tool():
    """Create real-time contract lookup tool."""
    if 'contract_data' not in st.session_state:
        return
    
    contract_data = st.session_state.contract_data
    contract_df = contract_data['dataframe']
    
    st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="glass-card">
            <div style="font-weight:700;margin-bottom:var(--space-3);color:var(--primary);">
                🔍 Real-time Contract Lookup
            </div>
            <div style="color:var(--text-tertiary);font-size:var(--text-sm);margin-bottom:var(--space-4);">
                Enter any time to get the projected contract price for that moment
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        lookup_time = st.time_input(
            "Lookup Time",
            value=time(9, 30),
            step=300,
            key="contract_lookup_time",
            help="Enter time to get contract projection"
        )
    
    with col2:
        # Calculate projection for lookup time
        forecast_date = contract_df.attrs.get('forecast_date', date.today())
        anchor_time = contract_df.attrs.get('anchor_time')
        slope = contract_df.attrs.get('slope_per_block', 0)
        base_price = contract_df.attrs.get('anchor_price', 0)
        
        lookup_datetime = datetime.combine(forecast_date, lookup_time)
        lookup_blocks = spx_blocks_between(anchor_time, lookup_datetime)
        lookup_projection = round_to_tick(base_price + (slope * lookup_blocks))
        
        # Display result with professional styling
        color = COLORS['success'] if slope >= 0 else COLORS['error']
        trend_icon = "📈" if slope >= 0 else "📉"
        
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg, rgba(0,122,255,0.1) 0%, rgba(139,92,246,0.1) 100%);
                 padding:var(--space-4);border-radius:var(--radius-xl);border:1px solid var(--primary);">
                <div style="display:flex;align-items:center;gap:var(--space-3);">
                    <span style="font-size:2rem;">{trend_icon}</span>
                    <div>
                        <div style="font-size:var(--text-2xl);font-weight:800;color:{color};font-family:'JetBrains Mono',monospace;">
                            ${lookup_projection:.2f}
                        </div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            @ {lookup_time.strftime('%H:%M')} • {lookup_blocks} blocks from anchor
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ===== FIBONACCI TOOLS SYSTEM =====

def render_fibonacci_header():
    """Render professional header for Fibonacci section."""
    st.markdown('<div style="margin:var(--space-12) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="section-header">🌀 Fibonacci Bounce Tools</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);line-height:1.6;">
            Professional Fibonacci retracement analysis for up-bounce scenarios. 
            Identifies key <strong>0.786 algorithm entry points</strong> and profit targets.
        </div>
        """,
        unsafe_allow_html=True
    )

def create_fibonacci_inputs():
    """Create professional Fibonacci input components."""
    st.markdown(
        """
        <div class="premium-card animate-slide-up">
            <div class="subsection-header">
                <span style="font-size:1.5rem;">🌀</span>
                <span style="color:var(--primary);font-weight:700;font-size:var(--text-2xl);">Bounce Configuration</span>
            </div>
            <div style="color:var(--text-tertiary);margin-bottom:var(--space-4);font-size:var(--text-sm);">
                Configure the contract bounce from low to high. The 0.786 retracement typically 
                occurs in the NEXT hour candle and represents a major algorithm entry point.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Fibonacci input layout
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        fib_low = st.number_input(
            "Bounce Low ($)",
            value=0.00,
            step=TICK,
            min_value=0.0,
            format="%.2f",
            key="fib_low_input",
            help="Lowest point of the contract bounce"
        )
    
    with col2:
        fib_high = st.number_input(
            "Bounce High ($)",
            value=0.00,
            step=TICK,
            min_value=0.0,
            format="%.2f",
            key="fib_high_input",
            help="Highest point of the contract bounce"
        )
    
    with col3:
        fib_low_time = st.time_input(
            "Bounce Low Time",
            value=time(9, 30),
            step=300,
            key="fib_low_time_input",
            help="Time when the bounce low occurred"
        )
    
    with col4:
        show_targets = st.toggle(
            "Show Extended Targets",
            value=True,
            help="Show 1.272 and 1.618 extension targets"
        )
    
    return {
        'fib_low': fib_low,
        'fib_high': fib_high,
        'fib_low_time': fib_low_time,
        'show_targets': show_targets,
        'valid': fib_high > fib_low > 0
    }

def calculate_fibonacci_levels(low: float, high: float) -> dict:
    """Calculate Fibonacci retracement and extension levels."""
    if high <= low:
        return {}
    
    range_value = high - low
    
    return {
        # Retracement levels
        "0.236": high - range_value * 0.236,
        "0.382": high - range_value * 0.382,
        "0.500": high - range_value * 0.500,
        "0.618": high - range_value * 0.618,
        "0.786": high - range_value * 0.786,  # Key algorithm level
        "1.000": low,
        
        # Extension targets
        "1.272": high + range_value * 0.272,
        "1.618": high + range_value * 0.618,
    }

def display_fibonacci_results(fib_inputs: dict):
    """Display Fibonacci results with professional styling."""
    if not fib_inputs['valid']:
        st.markdown(
            """
            <div style="text-align:center;padding:var(--space-6);color:var(--text-tertiary);">
                <div style="font-size:2rem;margin-bottom:var(--space-2);">🌀</div>
                <div>Enter bounce low < bounce high to compute Fibonacci levels</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return
    
    levels = calculate_fibonacci_levels(fib_inputs['fib_low'], fib_inputs['fib_high'])
    
    st.markdown('<div style="margin:var(--space-4) 0;"></div>', unsafe_allow_html=True)
    
    # Fibonacci levels header
    st.markdown(
        f"""
        <div class="premium-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-weight:700;font-size:var(--text-2xl);color:var(--primary);">
                        🌀 Fibonacci Levels
                    </div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                        Bounce: ${fib_inputs['fib_low']:.2f} → ${fib_inputs['fib_high']:.2f} • 
                        Range: ${fib_inputs['fib_high'] - fib_inputs['fib_low']:.2f}
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-weight:600;">Algorithm Entry</div>
                    <div style="font-size:var(--text-lg);color:var(--warning);">${levels['0.786']:.2f}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Retracement levels table
    retracement_data = []
    for level in ["0.236", "0.382", "0.500", "0.618", "0.786", "1.000"]:
        note = ""
        if level == "0.786":
            note = "🎯 ALGO ENTRY"
        elif level == "1.000":
            note = "Bounce Low"
        elif level == "0.500":
            note = "Mid-point"
        
        retracement_data.append({
            'Level': level,
            'Price': f"${round_to_tick(levels[level]):.2f}",
            'Note': note
        })
    
    # Extension targets if enabled
    if fib_inputs['show_targets']:
        for level in ["1.272", "1.618"]:
            retracement_data.append({
                'Level': level,
                'Price': f"${round_to_tick(levels[level]):.2f}",
                'Note': "🎯 Target"
            })
    
    # Display Fibonacci table
    fib_df = pd.DataFrame(retracement_data)
    
    st.markdown("### 📊 Fibonacci Levels")
    st.dataframe(
        fib_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Level': st.column_config.TextColumn('Fib Level', width='small'),
            'Price': st.column_config.TextColumn('Price', width='medium'),
            'Note': st.column_config.TextColumn('Note', width='medium')
        }
    )

def create_fibonacci_confluence_analysis(fib_inputs: dict, forecast_date: date):
    """Create confluence analysis between Fibonacci 0.786 and Contract Line."""
    if not fib_inputs['valid'] or 'contract_data' not in st.session_state:
        return
    
    st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="subsection-header">
            <span style="font-size:1.2rem;">📈</span>
            <span style="color:var(--success);font-weight:600;">Next-30-Min Confluence Analysis</span>
        </div>
        <div style="color:var(--text-tertiary);font-size:var(--text-sm);margin-bottom:var(--space-4);">
            Analyzing confluence between 0.786 Fibonacci level and Contract Line projection
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Calculate next 30-minute time slot
    bounce_time = fib_inputs['fib_low_time']
    next_30_dt = datetime.combine(date.today(), bounce_time) + timedelta(minutes=30)
    next_30_time = next_30_dt.time()
    
    # Get Fibonacci 0.786 level
    levels = calculate_fibonacci_levels(fib_inputs['fib_low'], fib_inputs['fib_high'])
    fib_0786 = round_to_tick(levels['0.786'])
    
    # Get Contract Line projection
    contract_data = st.session_state.contract_data
    contract_df = contract_data['dataframe']
    
    # Find contract projection for next 30-min slot
    anchor_time = contract_df.attrs.get('anchor_time')
    slope = contract_df.attrs.get('slope_per_block', 0)
    base_price = contract_df.attrs.get('anchor_price', 0)
    
    target_datetime = datetime.combine(forecast_date, next_30_time)
    blocks = spx_blocks_between(anchor_time, target_datetime)
    contract_projection = round_to_tick(base_price + (slope * blocks))
    
    # Calculate confluence
    delta = abs(contract_projection - fib_0786)
    percent_diff = (delta / fib_0786 * 100) if fib_0786 > 0 else float('inf')
    
    # Determine confluence grade
    if percent_diff < 0.50:
        grade = "STRONG"
        grade_color = COLORS['success']
    elif percent_diff <= 1.00:
        grade = "MODERATE"
        grade_color = COLORS['warning']
    else:
        grade = "WEAK"
        grade_color = COLORS['error']
    
    # Display confluence analysis
    st.markdown(
        f"""
        <div class="premium-card" style="background:rgba(0,122,255,0.05);border-color:#007AFF;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-4);">
                <div>
                    <div style="font-weight:700;color:var(--primary);margin-bottom:var(--space-2);">Confluence Analysis</div>
                    <div style="color:var(--text-secondary);font-size:var(--text-sm);">
                        Next 30-min slot: {next_30_time.strftime('%H:%M')}
                    </div>
                </div>
                <div style="text-align:center;">
                    <div style="font-weight:700;color:{grade_color};font-size:var(--text-xl);">{grade}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Confluence</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Detailed confluence metrics using columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-weight:700;color:{COLORS['warning']};font-family:'JetBrains Mono',monospace;">${fib_0786:.2f}</div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">FIB 0.786</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-weight:700;color:{COLORS['primary']};font-family:'JetBrains Mono',monospace;">${contract_projection:.2f}</div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">CONTRACT</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-weight:700;font-family:'JetBrains Mono',monospace;">${delta:.2f}</div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">DELTA</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col4:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-3);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-weight:700;font-family:'JetBrains Mono',monospace;">{percent_diff:.2f}%</div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">DIFFERENCE</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Trading insight
    st.markdown(
        f"""
        <div style="background:rgba({grade_color[1:]}, 0.1);padding:var(--space-3);border-radius:var(--radius-lg);margin-top:var(--space-4);">
            <div style="font-weight:600;color:{grade_color};margin-bottom:var(--space-2);">💡 Trading Insight</div>
            <div style="color:var(--text-secondary);font-size:var(--text-sm);">
                {grade} confluence suggests {"high probability" if grade == "STRONG" else ("moderate probability" if grade == "MODERATE" else "low probability")} 
                of algorithm entry at the 0.786 level in the next 30-minute candle.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ===== MAIN CONTRACT & FIBONACCI INTEGRATION =====

def render_contract_section(forecast_date: date):
    """Main function to render the complete contract section."""
    # Contract Header
    render_contract_header()
    
    # Contract Input Components
    contract_inputs = create_contract_inputs()
    
    # Validation and Generation
    action = render_contract_validation_and_generation(contract_inputs, forecast_date)
    
    # Generate if requested
    if action == 'generate':
        with st.spinner("🔄 Generating contract line..."):
            contract_df = generate_contract_line(contract_inputs, forecast_date)
            if not contract_df.empty:
                st.success("✅ Contract line generated successfully!")
                st.rerun()
    
    # Display results if available
    display_contract_results()
    
    # Real-time lookup tool
    create_contract_lookup_tool()
    
    return st.session_state.get('contract_data', {})

def render_fibonacci_section(forecast_date: date):
    """Main function to render the complete Fibonacci section."""
    # Fibonacci Header
    render_fibonacci_header()
    
    # Fibonacci Input Components
    fib_inputs = create_fibonacci_inputs()
    
    # Display Fibonacci Results
    display_fibonacci_results(fib_inputs)
    
    # Confluence Analysis (if contract data available)
    create_fibonacci_confluence_analysis(fib_inputs, forecast_date)
    
    return fib_inputs

# ===== INTEGRATION INTO MAIN FLOW =====
# Add this after the detection results section

if 'detection_results' in locals() and detection_results.get('detection_results') is not None:
    st.markdown('<div style="margin:var(--space-12) 0;"></div>', unsafe_allow_html=True)
    
    # Render Contract Section
    contract_results = render_contract_section(forecast_date)
    
    # Render Fibonacci Section
    fibonacci_results = render_fibonacci_section(forecast_date)

# ===== COMPREHENSIVE EXPORT SYSTEM =====

def create_exportable_datasets(
    fan_datasets: dict, 
    detection_results: pd.DataFrame, 
    contract_data: dict,
    fibonacci_data: dict,
    forecast_date: date, 
    anchor_config: dict
) -> dict:
    """
    Create comprehensive exportable datasets with all trading data.
    """
    export_data = {}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Fan data exports with TP1/TP2
    for fan_name, fan_df in fan_datasets.items():
        if fan_df is not None and not fan_df.empty:
            export_df = fan_df.copy()
            
            # Add metadata columns
            export_df['Forecast_Date'] = forecast_date
            export_df['Generated_At'] = datetime.now()
            export_df['Anchor_Price'] = fan_df.attrs.get('anchor_price', 0)
            export_df['Anchor_Time'] = fan_df.attrs.get('anchor_time', time()).strftime('%H:%M')
            export_df['Slopes_Down'] = fan_df.attrs.get('slopes_down', 0)
            export_df['Slopes_Up'] = fan_df.attrs.get('slopes_up', 0)
            
            # Enhanced filename with TP system indicator
            export_data[f'{fan_name.upper()}_Fan_TP1_TP2_{timestamp}.csv'] = export_df.to_csv(index=False).encode()
    
    # Trading detection results export
    if detection_results is not None and not detection_results.empty:
        detection_export = detection_results.copy()
        detection_export['Forecast_Date'] = forecast_date
        detection_export['Exported_At'] = datetime.now()
        detection_export['Tolerance_Used'] = detection_results.attrs.get('tolerance_used', 0)
        detection_export['Rule_Type'] = detection_results.attrs.get('rule_type_used', 'Unknown')
        
        export_data[f'Trading_Signals_Detection_{timestamp}.csv'] = detection_export.to_csv(index=False).encode()
    
    # Contract line export
    if contract_data and 'dataframe' in contract_data:
        contract_df = contract_data['dataframe'].copy()
        contract_metadata = contract_data.get('metadata', {})
        
        # Add comprehensive metadata
        contract_df['Forecast_Date'] = forecast_date
        contract_df['Strategy_Label'] = contract_data.get('config', {}).get('strategy_label', 'Manual')
        contract_df['Low1_Price'] = contract_df.attrs.get('low1_price', 0)
        contract_df['Low1_Time'] = contract_df.attrs.get('low1_time', time()).strftime('%H:%M')
        contract_df['Low2_Price'] = contract_df.attrs.get('low2_price', 0)
        contract_df['Low2_Time'] = contract_df.attrs.get('low2_time', time()).strftime('%H:%M')
        contract_df['Slope_Per_Block'] = contract_df.attrs.get('slope_per_block', 0)
        contract_df['Generated_At'] = datetime.now()
        
        export_data[f'Contract_Line_{timestamp}.csv'] = contract_df.to_csv(index=False).encode()
    
    # Fibonacci levels export
    if fibonacci_data and fibonacci_data.get('valid', False):
        fib_levels = calculate_fibonacci_levels(fibonacci_data['fib_low'], fibonacci_data['fib_high'])
        
        fib_export_data = []
        for level, price in fib_levels.items():
            note = ""
            if level == "0.786":
                note = "ALGORITHM_ENTRY_POINT"
            elif level == "1.000":
                note = "BOUNCE_LOW"
            elif float(level) > 1.0:
                note = "EXTENSION_TARGET"
            else:
                note = "RETRACEMENT_LEVEL"
            
            fib_export_data.append({
                'Fibonacci_Level': level,
                'Price': round_to_tick(price),
                'Bounce_Low': fibonacci_data['fib_low'],
                'Bounce_High': fibonacci_data['fib_high'],
                'Bounce_Range': fibonacci_data['fib_high'] - fibonacci_data['fib_low'],
                'Note': note,
                'Forecast_Date': forecast_date,
                'Generated_At': datetime.now()
            })
        
        fib_df = pd.DataFrame(fib_export_data)
        export_data[f'Fibonacci_Levels_{timestamp}.csv'] = fib_df.to_csv(index=False).encode()
    
    # Comprehensive summary export
    summary_data = {
        'Export_Timestamp': [datetime.now()],
        'Forecast_Date': [forecast_date],
        'MarketLens_Version': [VERSION],
        
        # Anchor configuration
        'High_Anchor': [f"${anchor_config.get('high_price', 0):.2f} @ {anchor_config.get('high_time', time()).strftime('%H:%M')}"],
        'Close_Anchor': [f"${anchor_config.get('close_price', 0):.2f} @ {anchor_config.get('close_time', time()).strftime('%H:%M')}"],
        'Low_Anchor': [f"${anchor_config.get('low_price', 0):.2f} @ {anchor_config.get('low_time', time()).strftime('%H:%M')}"],
        
        # Trading data summary
        'Total_Fans_Generated': [len([df for df in fan_datasets.values() if df is not None and not df.empty])],
        'Trading_Signals_Detected': [len(detection_results[detection_results['status'] == 'Signal Detected']) if detection_results is not None and not detection_results.empty else 0],
        'Entry_Signals': [len(detection_results[detection_results['signal_type'] == 'Entry ↓']) if detection_results is not None and not detection_results.empty else 0],
        'TP1_Signals': [len(detection_results[detection_results['signal_type'] == 'TP1 ↑']) if detection_results is not None and not detection_results.empty else 0],
        'TP2_Signals': [len(detection_results[detection_results['signal_type'] == 'TP2 ↑']) if detection_results is not None and not detection_results.empty else 0],
        
        # Contract data summary
        'Contract_Generated': [bool(contract_data and 'dataframe' in contract_data)],
        'Contract_Strategy': [contract_data.get('config', {}).get('strategy_label', 'None') if contract_data else 'None'],
        'Contract_Slope': [contract_data.get('metadata', {}).get('slope', 0) if contract_data else 0],
        
        # Fibonacci summary
        'Fibonacci_Generated': [bool(fibonacci_data and fibonacci_data.get('valid', False))],
        'Fibonacci_786_Level': [round_to_tick(calculate_fibonacci_levels(fibonacci_data['fib_low'], fibonacci_data['fib_high'])['0.786']) if fibonacci_data and fibonacci_data.get('valid') else 0],
        
        # System information
        'SPX_Slopes_Down_High': [SPX_SLOPES_DOWN['HIGH']],
        'SPX_Slopes_Up_High': [SPX_SLOPES_UP['HIGH']],
        'Tick_Size': [TICK],
        'RTH_Start': [RTH_START.strftime('%H:%M')],
        'RTH_End': [RTH_END.strftime('%H:%M')]
    }
    
    summary_df = pd.DataFrame(summary_data)
    export_data[f'MarketLens_Pro_Summary_{timestamp}.csv'] = summary_df.to_csv(index=False).encode()
    
    return export_data

def display_export_center(
    fan_datasets: dict, 
    detection_results: pd.DataFrame, 
    contract_data: dict,
    fibonacci_data: dict,
    forecast_date: date, 
    anchor_config: dict
):
    """Display comprehensive export center with advanced options."""
    st.markdown('<div style="margin:var(--space-12) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="section-header">📤 Export & Download Center</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);line-height:1.6;">
            Export all trading data, analysis results, and configurations for external use. 
            Professional CSV formats compatible with Excel, Python, and other trading platforms.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Check what data is available for export
    has_fan_data = bool(fan_datasets and any(df is not None and not df.empty for df in fan_datasets.values()))
    has_detection_data = bool(detection_results is not None and not detection_results.empty)
    has_contract_data = bool(contract_data and 'dataframe' in contract_data)
    has_fibonacci_data = bool(fibonacci_data and fibonacci_data.get('valid', False))
    
    if not any([has_fan_data, has_detection_data, has_contract_data, has_fibonacci_data]):
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">📊</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">No Data Available for Export</div>
                <div style="color:var(--text-tertiary);">Generate trading data first to enable exports</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return
    
    # Export options overview
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(
            """
            <div class="glass-card">
                <div style="font-weight:700;margin-bottom:var(--space-3);color:var(--primary);">📋 Available Exports</div>
                <div style="color:var(--text-secondary);font-size:var(--text-sm);line-height:1.8;">
            """,
            unsafe_allow_html=True
        )
        
        export_items = []
        if has_fan_data:
            export_items.append("• **Fan Forecast Data** with TP1/TP2 profit targets")
        if has_detection_data:
            export_items.append("• **Trading Signal Detection** results with confidence scores")
        if has_contract_data:
            export_items.append("• **Contract Line Projections** with strategy metadata")
        if has_fibonacci_data:
            export_items.append("• **Fibonacci Levels** with algorithm entry points")
        
        export_items.extend([
            "• **Comprehensive Summary** with all configurations",
            "• **Audit Trail** with timestamps and parameters",
            "• **Professional Formatting** ready for external platforms"
        ])
        
        for item in export_items:
            st.markdown(f"<div>{item}</div>", unsafe_allow_html=True)
        
        st.markdown(
            """
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        # Export statistics
        total_datasets = sum([has_fan_data, has_detection_data, has_contract_data, has_fibonacci_data])
        fan_count = len([df for df in (fan_datasets.values() if fan_datasets else []) if df is not None and not df.empty])
        
        st.markdown(
            f"""
            <div style="background:var(--surface);padding:var(--space-4);border-radius:var(--radius-lg);border:1px solid var(--border);">
                <div style="text-align:center;">
                    <div style="font-size:var(--text-3xl);font-weight:800;color:var(--primary);">{total_datasets + 1}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Total Files</div>
                </div>
                <div style="margin:var(--space-3) 0;">
                    <div style="font-size:var(--text-lg);font-weight:600;">{fan_count}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Fan Datasets</div>
                </div>
                <div>
                    <div style="font-size:var(--text-lg);font-weight:600;">{forecast_date.strftime('%Y-%m-%d')}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Forecast Date</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Export button
        st.markdown('<div style="margin:var(--space-4) 0;"></div>', unsafe_allow_html=True)
        
        if st.button("📦 Create Export Package", use_container_width=True, type="primary"):
            with st.spinner("🔄 Preparing comprehensive export package..."):
                export_datasets = create_exportable_datasets(
                    fan_datasets, 
                    detection_results, 
                    contract_data,
                    fibonacci_data,
                    forecast_date, 
                    anchor_config
                )
                
                if export_datasets:
                    # Create ZIP package
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for filename, data in export_datasets.items():
                            zip_file.writestr(filename, data)
                    
                    # Generate download
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    zip_filename = f"MarketLens_Pro_Complete_Export_{timestamp}.zip"
                    
                    st.download_button(
                        "⬇️ Download Complete Package",
                        data=zip_buffer.getvalue(),
                        file_name=zip_filename,
                        mime="application/zip",
                        use_container_width=True
                    )
                    
                    st.success(f"✅ Export package ready: {len(export_datasets)} files")
                    
                    # Display export summary
                    st.markdown('<div style="margin:var(--space-4) 0;"></div>', unsafe_allow_html=True)
                    
                    st.markdown(
                        f"""
                        <div style="background:rgba(52,199,89,0.1);padding:var(--space-3);border-radius:var(--radius-lg);">
                            <div style="font-weight:600;color:#34C759;margin-bottom:var(--space-2);">📦 Export Complete</div>
                            <div style="color:var(--text-secondary);font-size:var(--text-sm);">
                                Package: <strong>{zip_filename}</strong><br>
                                Files: <strong>{len(export_datasets)} CSV files</strong><br>
                                Generated: <strong>{datetime.now().strftime('%H:%M:%S')}</strong>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.error("❌ No data available for export")

# ===== ADVANCED DOCUMENTATION SYSTEM =====

def render_documentation_sidebar():
    """Render comprehensive documentation in sidebar."""
    with st.sidebar:
        st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
        
        st.markdown(
            """
            <div style="font-weight:700;color:var(--primary);margin-bottom:var(--space-4);">
                📚 Trading Documentation
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Golden Rules
        with st.expander("🎯 Golden Rules", expanded=False):
            for rule in SPX_GOLDEN_RULES:
                st.markdown(f"- {rule}")
        
        # Anchor Trading Rules
        with st.expander("⚓ Anchor Rules", expanded=False):
            st.markdown("**RTH Anchor Breaks**")
            for rule in SPX_ANCHOR_RULES["rth_breaks"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Extended Hours**")
            for rule in SPX_ANCHOR_RULES["extended_hours"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Mon/Wed/Fri Rules**")
            for rule in SPX_ANCHOR_RULES["mon_wed_fri"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Fibonacci Bounce**")
            for rule in SPX_ANCHOR_RULES["fibonacci_bounce"]:
                st.markdown(f"- {rule}")
        
        # Contract Strategies
        with st.expander("📋 Contract Strategies", expanded=False):
            st.markdown("**Tuesday Play**")
            for rule in CONTRACT_STRATEGIES["tuesday_play"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Thursday Play**")
            for rule in CONTRACT_STRATEGIES["thursday_play"]:
                st.markdown(f"- {rule}")
        
        # Time & Volume Rules
        with st.expander("⏰ Time & Volume", expanded=False):
            st.markdown("**Market Sessions**")
            for rule in TIME_RULES["market_sessions"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Volume Patterns**")
            for rule in TIME_RULES["volume_patterns"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Multi-Timeframe**")
            for rule in TIME_RULES["multi_timeframe"]:
                st.markdown(f"- {rule}")
        
        # Risk Management
        with st.expander("🛡️ Risk Management", expanded=False):
            st.markdown("**Position Sizing**")
            for rule in RISK_RULES["position_sizing"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Stop Strategy**")
            for rule in RISK_RULES["stop_strategy"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Market Context**")
            for rule in RISK_RULES["market_context"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Psychology**")
            for rule in RISK_RULES["psychological"]:
                st.markdown(f"- {rule}")
            
            st.markdown("**Performance Targets**")
            for rule in RISK_RULES["performance_targets"]:
                st.markdown(f"- {rule}")
        
        # Technical Information
        with st.expander("⚙️ Technical Info", expanded=False):
            st.markdown(f"**Version:** {VERSION}")
            st.markdown(f"**Tick Size:** ${TICK}")
            st.markdown(f"**RTH:** {RTH_START.strftime('%H:%M')} - {RTH_END.strftime('%H:%M')}")
            st.markdown(f"**Slopes Down:** {SPX_SLOPES_DOWN['HIGH']}")
            st.markdown(f"**Slopes Up:** {SPX_SLOPES_UP['HIGH']}")
            st.markdown(f"**Data Source:** Yahoo Finance")
            st.markdown(f"**Time Blocks:** 30-minute intervals")

def render_footer():
    """Render professional footer with branding and disclaimer."""
    st.markdown('<div style="margin:var(--space-16) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        f"""
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-xl);
             padding:var(--space-6);text-align:center;margin-top:var(--space-8);">
            <div style="font-weight:700;font-size:var(--text-2xl);color:var(--primary);margin-bottom:var(--space-2);">
                {APP_NAME}
            </div>
            <div style="color:var(--text-secondary);margin-bottom:var(--space-3);">
                {TAGLINE}
            </div>
            <div style="color:var(--text-tertiary);font-size:var(--text-sm);line-height:1.6;">
                <strong>Version {VERSION}</strong> • {COMPANY}<br>
                Professional SPX forecasting and analytics platform<br>
                <em>For educational and analysis purposes only</em>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Risk disclaimer in separate card
    st.markdown(
        """
        <div style="background:rgba(255,149,0,0.1);border:1px solid #FF9500;border-radius:var(--radius-lg);
             padding:var(--space-4);margin-top:var(--space-4);text-align:center;">
            <div style="color:#FF9500;font-weight:600;margin-bottom:var(--space-2);">⚠️ Risk Disclaimer</div>
            <div style="color:var(--text-secondary);font-size:var(--text-sm);line-height:1.5;">
                Trading involves substantial risk of loss. Past performance does not guarantee future results. 
                This software is for educational purposes only and should not be considered as investment advice.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ===== MAIN INTEGRATION FUNCTION =====

def render_export_and_documentation(
    fan_datasets: dict, 
    detection_results: pd.DataFrame, 
    contract_data: dict,
    fibonacci_data: dict,
    forecast_date: date, 
    anchor_config: dict
):
    """Main function to render export center and documentation."""
    
    # Export Center
    display_export_center(
        fan_datasets, 
        detection_results, 
        contract_data,
        fibonacci_data,
        forecast_date, 
        anchor_config
    )
    
    # Documentation in Sidebar
    render_documentation_sidebar()
    
    # Professional Footer
    render_footer()

# ===== INTEGRATION INTO MAIN FLOW =====
# Add this at the end of your main application

# Collect all available data for export
available_fan_data = locals().get('trading_results', {}).get('fan_data', {})
available_detection_data = locals().get('detection_results', {}).get('detection_results', pd.DataFrame())
available_contract_data = locals().get('contract_results', {})
available_fibonacci_data = locals().get('fibonacci_results', {})
available_anchor_config = anchor_section_results.get('anchor_config', {})

# Render export center and documentation
render_export_and_documentation(
    available_fan_data,
    available_detection_data, 
    available_contract_data,
    available_fibonacci_data,
    forecast_date,
    available_anchor_config
)
# ===== FINAL INTEGRATION & POLISH =====

# ===== PERFORMANCE OPTIMIZATIONS =====

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_market_status():
    """Cache market status to reduce API calls."""
    current_time = datetime.now().time()
    is_open = RTH_START <= current_time <= RTH_END
    return {
        'is_market_open': is_open,
        'current_time': current_time,
        'status_text': "🟢 MARKET OPEN" if is_open else "🔴 MARKET CLOSED",
        'cached_at': datetime.now()
    }

def optimize_session_state():
    """Optimize session state for better performance."""
    # Clean up old data to prevent memory bloat
    cleanup_keys = []
    max_age_minutes = 60
    current_time = datetime.now()
    
    for key in st.session_state.keys():
        if key.endswith('_generated_at') or key.endswith('_timestamp'):
            try:
                timestamp = st.session_state[key]
                if isinstance(timestamp, datetime):
                    age = (current_time - timestamp).total_seconds() / 60
                    if age > max_age_minutes:
                        cleanup_keys.append(key.replace('_generated_at', '').replace('_timestamp', ''))
            except:
                continue
    
    # Clean up old data
    for key in cleanup_keys:
        if key in st.session_state:
            del st.session_state[key]

# ===== ERROR HANDLING & RECOVERY =====

def handle_graceful_errors():
    """Provide graceful error handling and recovery options."""
    if 'error_count' not in st.session_state:
        st.session_state.error_count = 0
    
    # Reset button for problematic states
    if st.session_state.error_count > 3:
        st.sidebar.markdown(
            """
            <div style="background:rgba(255,59,48,0.1);border:1px solid #FF3B30;border-radius:var(--radius-lg);
                 padding:var(--space-3);margin:var(--space-4) 0;">
                <div style="color:#FF3B30;font-weight:600;margin-bottom:var(--space-2);">⚠️ Multiple Errors Detected</div>
                <div style="color:var(--text-secondary);font-size:var(--text-sm);">
                    Consider resetting the application state
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        if st.sidebar.button("🔄 Reset Application", use_container_width=True):
            # Clear problematic session state
            keys_to_clear = [
                'fan_data', 'contract_data', 'anchors_locked', 'forecasts_generated',
                'latest_detection_results', 'latest_trading_results'
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            st.session_state.error_count = 0
            st.success("✅ Application reset successfully")
            st.rerun()

# ===== ADVANCED KEYBOARD SHORTCUTS =====

def add_keyboard_shortcuts():
    """Add keyboard shortcuts for power users."""
    st.markdown(
        """
        <script>
        document.addEventListener('keydown', function(e) {
            // Ctrl + G: Generate forecast
            if (e.ctrlKey && e.key === 'g') {
                e.preventDefault();
                const generateBtn = document.querySelector('button[kind="primary"]');
                if (generateBtn && generateBtn.textContent.includes('Generate')) {
                    generateBtn.click();
                }
            }
            
            // Ctrl + E: Focus on export
            if (e.ctrlKey && e.key === 'e') {
                e.preventDefault();
                const exportSection = document.querySelector('[data-testid="stMarkdown"]');
                if (exportSection) {
                    exportSection.scrollIntoView({ behavior: 'smooth' });
                }
            }
            
            // Ctrl + R: Refresh data
            if (e.ctrlKey && e.key === 'r') {
                e.preventDefault();
                const refreshBtn = document.querySelector('button');
                if (refreshBtn && refreshBtn.textContent.includes('Refresh')) {
                    refreshBtn.click();
                }
            }
            
            // Escape: Close any open modals or reset focus
            if (e.key === 'Escape') {
                document.activeElement.blur();
            }
        });
        
        // Add keyboard shortcuts help
        console.log('MarketLens Pro Keyboard Shortcuts:');
        console.log('Ctrl + G: Generate forecast');
        console.log('Ctrl + E: Jump to export section');
        console.log('Ctrl + R: Refresh data');
        console.log('Escape: Reset focus');
        </script>
        """,
        unsafe_allow_html=True
    )

# ===== PROFESSIONAL LOADING STATES =====

def show_loading_animation(message: str = "Loading..."):
    """Show professional loading animation."""
    return st.markdown(
        f"""
        <div style="display:flex;align-items:center;justify-content:center;padding:var(--space-8);">
            <div style="margin-right:var(--space-3);">
                <div style="width:20px;height:20px;border:2px solid var(--border);border-top:2px solid var(--primary);
                     border-radius:50%;animation:spin 1s linear infinite;"></div>
            </div>
            <div style="color:var(--text-secondary);">{message}</div>
        </div>
        <style>
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# ===== DATA VALIDATION & INTEGRITY =====

def validate_data_integrity():
    """Validate data integrity and show warnings if needed."""
    issues = []
    
    # Check for required session state
    required_state = ['initialized', 'theme']
    for key in required_state:
        if key not in st.session_state:
            issues.append(f"Missing session state: {key}")
    
    # Check for data consistency
    if st.session_state.get('forecasts_generated', False):
        if 'fan_data' not in st.session_state or not st.session_state.fan_data:
            issues.append("Forecasts marked as generated but no fan data found")
    
    if st.session_state.get('anchors_locked', False):
        if 'locked_anchor_data' not in st.session_state:
            issues.append("Anchors marked as locked but no lock data found")
    
    # Show integrity warnings if needed
    if issues and len(issues) < 3:  # Don't spam if too many issues
        with st.sidebar:
            st.markdown(
                f"""
                <div style="background:rgba(255,149,0,0.1);border:1px solid #FF9500;border-radius:var(--radius-md);
                     padding:var(--space-2);margin:var(--space-2) 0;">
                    <div style="color:#FF9500;font-weight:600;font-size:var(--text-sm);">⚠️ Data Integrity</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-xs);">
                        {len(issues)} minor issue(s) detected
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# ===== RESPONSIVE DESIGN ENHANCEMENTS =====

def add_responsive_design():
    """Add responsive design enhancements for mobile devices."""
    st.markdown(
        """
        <style>
        /* Mobile optimizations */
        @media (max-width: 768px) {
            .metrics-grid {
                grid-template-columns: 1fr !important;
                gap: var(--space-3) !important;
            }
            
            .live-price-container {
                flex-direction: column !important;
                text-align: center !important;
                gap: var(--space-2) !important;
            }
            
            .hero-container {
                padding: var(--space-6) var(--space-3) !important;
            }
            
            .brand-logo {
                font-size: var(--text-4xl) !important;
            }
            
            .section-header {
                font-size: var(--text-xl) !important;
            }
            
            .premium-card, .glass-card {
                margin: var(--space-2) 0 !important;
                padding: var(--space-4) !important;
            }
        }
        
        @media (max-width: 480px) {
            .brand-logo {
                font-size: var(--text-3xl) !important;
            }
            
            .metric-value {
                font-size: var(--text-3xl) !important;
            }
            
            .price-main {
                font-size: var(--text-2xl) !important;
            }
        }
        
        /* Print optimizations */
        @media print {
            .stButton, .stSelectbox, .stSlider, .stToggle {
                display: none !important;
            }
            
            .hero-container {
                background: white !important;
                color: black !important;
                border: 1px solid #ccc !important;
            }
            
            .premium-card, .glass-card {
                background: white !important;
                border: 1px solid #ddd !important;
                box-shadow: none !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# ===== ACCESSIBILITY IMPROVEMENTS =====

def add_accessibility_features():
    """Add accessibility improvements for better usability."""
    st.markdown(
        """
        <style>
        /* High contrast mode support */
        @media (prefers-contrast: high) {
            :root {
                --text-primary: #000000 !important;
                --bg-primary: #ffffff !important;
                --border: #000000 !important;
            }
            
            [data-theme="dark"] {
                --text-primary: #ffffff !important;
                --bg-primary: #000000 !important;
                --border: #ffffff !important;
            }
        }
        
        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {
            .animate-slide-up, .animate-fade-in {
                animation: none !important;
            }
            
            .live-dot {
                animation: none !important;
            }
        }
        
        /* Focus indicators */
        button:focus, input:focus, select:focus {
            outline: 2px solid var(--primary) !important;
            outline-offset: 2px !important;
        }
        
        /* Skip links for screen readers */
        .skip-link {
            position: absolute;
            top: -40px;
            left: 6px;
            background: var(--primary);
            color: white;
            padding: 8px;
            text-decoration: none;
            border-radius: 4px;
            z-index: 1000;
        }
        
        .skip-link:focus {
            top: 6px;
        }
        </style>
        
        <a href="#main-content" class="skip-link">Skip to main content</a>
        """,
        unsafe_allow_html=True
    )

# ===== ANALYTICS & TELEMETRY =====

def track_usage_analytics():
    """Track basic usage analytics (privacy-friendly)."""
    if 'analytics' not in st.session_state:
        st.session_state.analytics = {
            'session_start': datetime.now(),
            'features_used': set(),
            'forecasts_generated': 0,
            'exports_created': 0
        }
    
    # Track feature usage
    if st.session_state.get('forecasts_generated', False):
        st.session_state.analytics['features_used'].add('forecasting')
        if 'fan_data' in st.session_state:
            st.session_state.analytics['forecasts_generated'] += 1
    
    if st.session_state.get('contract_data'):
        st.session_state.analytics['features_used'].add('contract_line')
    
    # Display usage summary in sidebar (for power users)
    if len(st.session_state.analytics['features_used']) > 0:
        with st.sidebar:
            session_duration = (datetime.now() - st.session_state.analytics['session_start']).total_seconds() / 60
            
            if st.checkbox("📊 Show Session Analytics", value=False):
                st.markdown(
                    f"""
                    <div style="background:var(--surface);padding:var(--space-3);border-radius:var(--radius-md);
                         font-size:var(--text-xs);color:var(--text-tertiary);">
                        <div><strong>Session:</strong> {session_duration:.1f} min</div>
                        <div><strong>Features:</strong> {len(st.session_state.analytics['features_used'])}</div>
                        <div><strong>Forecasts:</strong> {st.session_state.analytics['forecasts_generated']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# ===== POWER USER FEATURES =====

def add_power_user_features():
    """Add advanced features for power users."""
    with st.sidebar:
        st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
        
        if st.checkbox("🔧 Power User Mode", value=False, help="Enable advanced features"):
            st.markdown("**🚀 Advanced Options**")
            
            # Debug mode
            debug_mode = st.toggle("Debug Mode", value=False, help="Show technical information")
            if debug_mode:
                st.json({
                    'session_state_keys': list(st.session_state.keys()),
                    'app_version': VERSION,
                    'python_version': f"{sys.version_info.major}.{sys.version_info.minor}",
                    'streamlit_version': st.__version__ if hasattr(st, '__version__') else 'unknown'
                })
            
            # Performance mode
            performance_mode = st.toggle("Performance Mode", value=False, help="Optimize for speed")
            if performance_mode:
                st.session_state.performance_mode = True
                # Reduce cache TTL for faster updates
                st.markdown("⚡ Performance mode enabled")
            
            # Experimental features
            experimental = st.toggle("Experimental Features", value=False, help="Enable beta features")
            if experimental:
                st.warning("🧪 Experimental features enabled - use with caution")
                
                # Quick export feature
                if st.button("⚡ Quick Export (Beta)", help="Experimental quick export"):
                    st.info("🚧 Quick export feature coming soon")

# ===== FINAL APPLICATION ASSEMBLY =====

def initialize_marketlens_pro():
    """Initialize the complete MarketLens Pro application."""
    # Performance optimizations
    optimize_session_state()
    
    # Error handling
    handle_graceful_errors()
    
    # Enhanced UX features
    add_keyboard_shortcuts()
    add_responsive_design()
    add_accessibility_features()
    
    # Analytics and power user features
    track_usage_analytics()
    add_power_user_features()
    
    # Data integrity checks
    validate_data_integrity()

def create_main_content_wrapper():
    """Create main content wrapper with proper semantic structure."""
    st.markdown('<div id="main-content">', unsafe_allow_html=True)

def finalize_application():
    """Finalize the application with cleanup and optimization."""
    # Close main content wrapper
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Add final performance optimizations
    if st.session_state.get('performance_mode', False):
        st.markdown(
            """
            <script>
            // Performance optimizations for production
            document.addEventListener('DOMContentLoaded', function() {
                // Lazy load images
                const images = document.querySelectorAll('img[data-src]');
                const imageObserver = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const img = entry.target;
                            img.src = img.dataset.src;
                            imageObserver.unobserve(img);
                        }
                    });
                });
                images.forEach(img => imageObserver.observe(img));
                
                // Optimize animations
                const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
                if (prefersReducedMotion.matches) {
                    document.body.classList.add('reduced-motion');
                }
            });
            </script>
            """,
            unsafe_allow_html=True
        )

# ===== COMPLETE APPLICATION INTEGRATION =====

# Initialize the application
initialize_marketlens_pro()

# Create semantic main content wrapper
create_main_content_wrapper()

# ===== MAIN APPLICATION FLOW =====
# (All previous parts 1-9 code goes here in the actual implementation)

# Note: In the actual implementation, you would place all the code from Parts 1-9 here
# This creates the complete flow: Hero → Anchors → Fan Data → Detection → Contract → Fibonacci → Export

# Example integration points:
# 1. Hero and Live Price (Part 4)
# 2. Sidebar and Anchor Configuration (Part 5) 
# 3. Fan Data Generation and Trading Tables (Part 6)
# 4. Trading Signal Detection (Part 7)
# 5. Contract Line and Fibonacci Tools (Part 8)
# 6. Export System and Documentation (Part 9)

# ===== APPLICATION FINALIZATION =====

# Finalize the application
finalize_application()

# ===== SUCCESS MESSAGE =====
if st.session_state.get('show_success_message', True):
    st.session_state.show_success_message = False
    
    # Show professional welcome message for first-time users
    if st.session_state.get('page_loads', 0) == 1:
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
                 color:white;padding:var(--space-4);border-radius:var(--radius-xl);margin:var(--space-4) 0;
                 text-align:center;box-shadow:var(--shadow-lg);">
                <div style="font-size:var(--text-xl);font-weight:700;margin-bottom:var(--space-2);">
                    🎯 MarketLens Pro Initialized
                </div>
                <div style="opacity:0.9;">
                    Professional SPX forecasting platform ready for analysis
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ===== FINAL PERFORMANCE METRICS =====
if 'performance_monitor' in st.session_state:
    total_session_time = st.session_state.performance_monitor.get_session_duration()
    
    # Show performance metrics for power users
    if st.session_state.get('debug_mode', False):
        st.sidebar.markdown(
            f"""
            <div style="background:var(--surface);padding:var(--space-2);border-radius:var(--radius-md);
                 margin-top:var(--space-4);font-size:var(--text-xs);color:var(--text-tertiary);">
                <strong>Performance:</strong> {total_session_time:.1f}s session
            </div>
            """,
            unsafe_allow_html=True
        )

# Add missing import for sys if needed
import sys
