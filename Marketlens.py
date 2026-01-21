
# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V6.1 - UNIFIED TRADING SYSTEM + HISTORICAL ANALYSIS
# ES-Native | Auto Session Detection | Historical Replay | Channel Strategy
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
# MATH FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def norm_cdf(x):
    a1,a2,a3,a4,a5=0.254829592,-0.284496736,1.421413741,-1.453152027,1.061405429
    p,sign=0.3275911,1 if x>=0 else -1
    x=abs(x)/math.sqrt(2)
    t=1.0/(1.0+p*x)
    y=1.0-(((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*math.exp(-x*x)
    return 0.5*(1.0+sign*y)

def black_scholes(S,K,T,r,sigma,opt_type):
    if T<=0:return max(0,S-K) if opt_type=="CALL" else max(0,K-S)
    d1=(math.log(S/K)+(r+0.5*sigma**2)*T)/(sigma*math.sqrt(T))
    d2=d1-sigma*math.sqrt(T)
    if opt_type=="CALL":return S*norm_cdf(d1)-K*math.exp(-r*T)*norm_cdf(d2)
    return K*math.exp(-r*T)*norm_cdf(-d2)-S*norm_cdf(-d1)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet V6.1",page_icon="🔮",layout="wide",initial_sidebar_state="expanded")
CT=pytz.timezone("America/Chicago")
ET=pytz.timezone("America/New_York")
SLOPE=0.48
BREAK_THRESHOLD=6.0
POLYGON_KEY="DCWuTS1R_fukpfjgf7QnXrLTEOS_giq6"
POLYGON_BASE="https://api.polygon.io"
SAVE_FILE="spx_prophet_v6_inputs.json"

VIX_ZONES={"EXTREME_LOW":(0,12),"LOW":(12,16),"NORMAL":(16,20),"ELEVATED":(20,25),"HIGH":(25,35),"EXTREME":(35,100)}

# ═══════════════════════════════════════════════════════════════════════════════
# CSS - PREMIUM TRADING TERMINAL UI
# Bloomberg meets Apple - Professional Beauty
# ═══════════════════════════════════════════════════════════════════════════════
STYLES="""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
    --bg-deep: #000000;
    --bg-main: #0a0a0a;
    --bg-card: #111111;
    --bg-card-alt: #0d0d0d;
    --bg-elevated: #1a1a1a;
    
    --border-dim: rgba(255,255,255,0.06);
    --border-normal: rgba(255,255,255,0.1);
    --border-bright: rgba(255,255,255,0.2);
    
    --green: #00ff88;
    --green-dim: #10b981;
    --green-bg: rgba(0,255,136,0.08);
    --green-border: rgba(0,255,136,0.3);
    --green-glow: 0 0 30px rgba(0,255,136,0.3);
    
    --purple: #a855f7;
    --purple-dim: #9333ea;
    --purple-bg: rgba(168,85,247,0.08);
    --purple-border: rgba(168,85,247,0.3);
    
    --cyan: #22d3ee;
    --cyan-bg: rgba(34,211,238,0.08);
    
    --red: #ff4757;
    --red-dim: #ef4444;
    --red-bg: rgba(255,71,87,0.08);
    --red-border: rgba(255,71,87,0.3);
    
    --amber: #fbbf24;
    --amber-bg: rgba(251,191,36,0.08);
    --amber-border: rgba(251,191,36,0.3);
    
    --text-white: #ffffff;
    --text-primary: rgba(255,255,255,0.92);
    --text-secondary: rgba(255,255,255,0.6);
    --text-muted: rgba(255,255,255,0.4);
    --text-dim: rgba(255,255,255,0.2);
}

/* ═══════════════════════════════════════════════════════════════════════════
   ANIMATIONS - Premium Institutional-Grade Motion Design
   ═══════════════════════════════════════════════════════════════════════════ */

/* Fade in and slide up on load */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(30px); filter: blur(4px); }
    to { opacity: 1; transform: translateY(0); filter: blur(0); }
}

/* Fade in from left */
@keyframes fadeInLeft {
    from { opacity: 0; transform: translateX(-30px); filter: blur(4px); }
    to { opacity: 1; transform: translateX(0); filter: blur(0); }
}

/* Fade in from right */
@keyframes fadeInRight {
    from { opacity: 0; transform: translateX(30px); filter: blur(4px); }
    to { opacity: 1; transform: translateX(0); filter: blur(0); }
}

/* Fade in and scale with blur */
@keyframes fadeInScale {
    from { opacity: 0; transform: scale(0.9); filter: blur(8px); }
    to { opacity: 1; transform: scale(1); filter: blur(0); }
}

/* Epic reveal - scale up with glow */
@keyframes epicReveal {
    0% { opacity: 0; transform: scale(0.8) translateY(20px); filter: blur(10px); }
    50% { opacity: 1; transform: scale(1.02) translateY(-5px); filter: blur(0); }
    100% { opacity: 1; transform: scale(1) translateY(0); filter: blur(0); }
}

/* Pulse glow for active elements */
@keyframes pulseGlow {
    0%, 100% { box-shadow: 0 0 20px rgba(0,255,136,0.3); }
    50% { box-shadow: 0 0 40px rgba(0,255,136,0.6), 0 0 80px rgba(0,255,136,0.3), 0 0 120px rgba(0,255,136,0.1); }
}

/* Intense pulse glow for critical elements */
@keyframes intensePulse {
    0%, 100% { 
        box-shadow: 0 0 20px rgba(0,255,136,0.4), inset 0 0 20px rgba(0,255,136,0.1);
        border-color: rgba(0,255,136,0.4);
    }
    50% { 
        box-shadow: 0 0 40px rgba(0,255,136,0.7), 0 0 80px rgba(0,255,136,0.4), inset 0 0 30px rgba(0,255,136,0.2);
        border-color: rgba(0,255,136,0.8);
    }
}

/* Red pulse for PUTS */
@keyframes pulseRed {
    0%, 100% { box-shadow: 0 0 20px rgba(255,71,87,0.3); }
    50% { box-shadow: 0 0 40px rgba(255,71,87,0.6), 0 0 80px rgba(255,71,87,0.3); }
}

/* Subtle float */
@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
}

/* Float with rotation */
@keyframes floatRotate {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    25% { transform: translateY(-4px) rotate(1deg); }
    50% { transform: translateY(-8px) rotate(0deg); }
    75% { transform: translateY(-4px) rotate(-1deg); }
}

/* Shimmer effect for loading and highlights */
@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

/* Scanning shimmer across element */
@keyframes scanShimmer {
    0% { left: -100%; }
    100% { left: 200%; }
}

/* Border glow pulse */
@keyframes borderPulse {
    0%, 100% { border-color: rgba(0,255,136,0.3); box-shadow: 0 0 10px rgba(0,255,136,0.1); }
    50% { border-color: rgba(0,255,136,0.7); box-shadow: 0 0 25px rgba(0,255,136,0.3); }
}

/* Number reveal - typewriter style */
@keyframes countUp {
    0% { opacity: 0; transform: translateY(15px) scale(0.9); filter: blur(4px); }
    60% { opacity: 1; transform: translateY(-3px) scale(1.02); filter: blur(0); }
    100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}

/* Rotate for loading */
@keyframes rotate {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

/* Smooth rotate with glow */
@keyframes rotateGlow {
    from { transform: rotate(0deg); filter: drop-shadow(0 0 5px rgba(0,255,136,0.5)); }
    to { transform: rotate(360deg); filter: drop-shadow(0 0 15px rgba(0,255,136,0.8)); }
}

/* Scan line effect - terminal style */
@keyframes scanLine {
    0% { top: -10%; opacity: 0; }
    10% { opacity: 1; }
    90% { opacity: 1; }
    100% { top: 110%; opacity: 0; }
}

/* Horizontal scan */
@keyframes scanHorizontal {
    0% { left: -10%; opacity: 0; }
    10% { opacity: 1; }
    90% { opacity: 1; }
    100% { left: 110%; opacity: 0; }
}

/* Draw line animation for SVG */
@keyframes drawLine {
    from { stroke-dashoffset: 100; }
    to { stroke-dashoffset: 0; }
}

/* Draw line with glow */
@keyframes drawLineGlow {
    from { stroke-dashoffset: 100; filter: drop-shadow(0 0 2px currentColor); }
    to { stroke-dashoffset: 0; filter: drop-shadow(0 0 8px currentColor); }
}

/* Blink for live indicators */
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* Heartbeat pulse */
@keyframes heartbeat {
    0%, 100% { transform: scale(1); }
    10% { transform: scale(1.15); }
    20% { transform: scale(1); }
    30% { transform: scale(1.1); }
    40% { transform: scale(1); }
}

/* Gradient shift - animated backgrounds */
@keyframes gradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* Rainbow border */
@keyframes rainbowBorder {
    0% { border-color: #00ff88; }
    25% { border-color: #22d3ee; }
    50% { border-color: #a855f7; }
    75% { border-color: #fbbf24; }
    100% { border-color: #00ff88; }
}

/* Value change flash */
@keyframes valueFlash {
    0% { background-color: rgba(0,255,136,0.4); transform: scale(1.05); }
    100% { background-color: transparent; transform: scale(1); }
}

/* Slide in from bottom with bounce */
@keyframes slideInBounce {
    0% { opacity: 0; transform: translateY(50px); }
    60% { opacity: 1; transform: translateY(-10px); }
    80% { transform: translateY(5px); }
    100% { transform: translateY(0); }
}

/* Pop in with elastic */
@keyframes popIn {
    0% { opacity: 0; transform: scale(0.5); }
    70% { transform: scale(1.1); }
    100% { opacity: 1; transform: scale(1); }
}

/* Ripple effect */
@keyframes ripple {
    0% { transform: scale(0.8); opacity: 1; }
    100% { transform: scale(2.5); opacity: 0; }
}

/* Typing cursor */
@keyframes cursorBlink {
    0%, 100% { border-right-color: var(--green); }
    50% { border-right-color: transparent; }
}

/* Data stream - matrix style */
@keyframes dataStream {
    0% { background-position: 0% 0%; }
    100% { background-position: 0% 100%; }
}

/* Glow text */
@keyframes glowText {
    0%, 100% { text-shadow: 0 0 10px currentColor, 0 0 20px currentColor; }
    50% { text-shadow: 0 0 20px currentColor, 0 0 40px currentColor, 0 0 60px currentColor; }
}

/* Status indicator breathing */
@keyframes breathe {
    0%, 100% { opacity: 0.6; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.1); }
}
}

/* ═══════════════════════════════════════════════════════════════════════════
   BASE
   ═══════════════════════════════════════════════════════════════════════════ */
.stApp {
    background: var(--bg-deep);
    font-family: 'Inter', -apple-system, sans-serif;
    color: var(--text-primary);
}
.stApp > header { background: transparent !important; }
[data-testid="stSidebar"] {
    background: var(--bg-card) !important;
    border-right: 1px solid var(--border-dim) !important;
}
[data-testid="stSidebar"] * { color: var(--text-primary) !important; }

h3 {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: var(--text-muted) !important;
    text-transform: uppercase !important;
    letter-spacing: 2px !important;
    margin: 32px 0 16px 0 !important;
}

.stExpander {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-dim) !important;
    border-radius: 12px !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   BRAND HEADER - Animated
   ═══════════════════════════════════════════════════════════════════════════ */
.brand-header {
    text-align: center;
    padding: 48px 20px 40px 20px;
    position: relative;
    animation: fadeInUp 0.8s ease-out;
}
.brand-logo-box {
    width: 80px; height: 80px;
    background: linear-gradient(135deg, #0d3320, #0a2818, #061510);
    border-radius: 20px;
    display: inline-flex; align-items: center; justify-content: center;
    margin-bottom: 24px;
    box-shadow: 
        0 0 40px rgba(0,255,136,0.3),
        0 0 80px rgba(0,255,136,0.15),
        inset 0 1px 0 rgba(255,255,255,0.1),
        0 10px 40px rgba(0,0,0,0.5);
    position: relative;
    animation: float 4s ease-in-out infinite;
    border: 1px solid rgba(0,255,136,0.3);
}
.brand-logo-box::before {
    content: '';
    position: absolute;
    top: -2px; left: -2px; right: -2px; bottom: -2px;
    background: linear-gradient(135deg, var(--green), transparent, var(--green));
    border-radius: 22px;
    z-index: -1;
    opacity: 0.5;
    animation: rotate 8s linear infinite;
}
.brand-logo-box svg {
    width: 48px;
    height: 48px;
    fill: none;
    stroke: var(--green);
    stroke-linecap: round;
    stroke-linejoin: round;
    filter: drop-shadow(0 0 8px rgba(0,255,136,0.5));
}
/* Pyramid outline */
.brand-logo-box svg path:first-of-type {
    stroke-dasharray: 120;
    stroke-dashoffset: 120;
    animation: drawPyramid 1.5s ease-out 0.3s forwards;
}
/* Three pillars with staggered animation */
.brand-logo-box svg line:nth-of-type(1) {
    stroke-dasharray: 20;
    stroke-dashoffset: 20;
    animation: drawPillar 0.6s ease-out 1s forwards;
}
.brand-logo-box svg line:nth-of-type(2) {
    stroke-dasharray: 30;
    stroke-dashoffset: 30;
    animation: drawPillar 0.6s ease-out 1.2s forwards;
}
.brand-logo-box svg line:nth-of-type(3) {
    stroke-dasharray: 20;
    stroke-dashoffset: 20;
    animation: drawPillar 0.6s ease-out 1.4s forwards;
}
/* Eye at apex - pulse */
.brand-logo-box svg circle:first-of-type {
    animation: eyePulse 2s ease-in-out 1.8s infinite;
    fill: rgba(0,255,136,0.2);
}
.brand-logo-box svg circle:nth-of-type(2) {
    fill: var(--green);
    animation: eyeGlow 2s ease-in-out 1.8s infinite;
}
/* Connection beam */
.brand-logo-box svg line:nth-of-type(4) {
    stroke-dasharray: 30;
    stroke-dashoffset: 30;
    animation: drawPillar 0.4s ease-out 1.6s forwards;
}

@keyframes drawPyramid {
    to { stroke-dashoffset: 0; }
}
@keyframes drawPillar {
    to { stroke-dashoffset: 0; }
}
@keyframes eyePulse {
    0%, 100% { transform: scale(1); opacity: 0.8; }
    50% { transform: scale(1.1); opacity: 1; }
}
@keyframes eyeGlow {
    0%, 100% { filter: drop-shadow(0 0 4px var(--green)); }
    50% { filter: drop-shadow(0 0 12px var(--green)) drop-shadow(0 0 20px var(--green)); }
}

.brand-name {
    font-size: 38px;
    font-weight: 800;
    letter-spacing: -1px;
    margin: 0;
    animation: fadeInUp 0.8s ease-out 0.2s both;
}
.brand-name span:first-child { color: var(--green); }
.brand-name span:last-child { color: var(--text-white); }
.brand-tagline {
    font-size: 14px;
    color: var(--text-secondary);
    margin-top: 12px;
    letter-spacing: 0.5px;
    animation: fadeInUp 0.8s ease-out 0.4s both;
}
.brand-live {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--green-bg);
    border: 1px solid var(--green-border);
    padding: 8px 20px;
    border-radius: 24px;
    font-size: 12px;
    font-weight: 600;
    color: var(--green);
    margin-top: 20px;
    animation: fadeInUp 0.8s ease-out 0.6s both, borderPulse 2s ease-in-out infinite;
}
.brand-live::before {
    content: '';
    width: 8px; height: 8px;
    background: var(--green);
    border-radius: 50%;
    animation: blink 1.5s ease-in-out infinite;
    box-shadow: 0 0 10px var(--green);
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.9); }
}

/* ═══════════════════════════════════════════════════════════════════════════
   STATUS BANNER - Hero Element with DRAMATIC Animations
   ═══════════════════════════════════════════════════════════════════════════ */
.mega-status {
    background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-card-alt) 100%);
    border: 1px solid var(--border-dim);
    border-radius: 20px;
    padding: 32px 36px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    animation: epicReveal 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    overflow: hidden;
}
/* Animated gradient border */
.mega-status::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    border-radius: 20px;
    padding: 2px;
    background: linear-gradient(135deg, transparent, rgba(255,255,255,0.1), transparent);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    opacity: 0;
    transition: opacity 0.3s ease;
}
.mega-status:hover::before {
    opacity: 1;
}
/* Animated scan line for active status */
.mega-status.go::after {
    content: '';
    position: absolute;
    left: -100%; right: -100%;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--green), var(--green), transparent);
    animation: scanHorizontal 2s ease-in-out infinite;
    opacity: 0.8;
    filter: blur(1px);
    box-shadow: 0 0 20px var(--green);
}
.mega-status.go {
    border-color: var(--green-border);
    background: linear-gradient(135deg, rgba(0,255,136,0.03) 0%, var(--bg-card) 50%, rgba(0,255,136,0.02) 100%);
    animation: epicReveal 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards, intensePulse 3s ease-in-out infinite;
}
.mega-status.wait {
    border-color: var(--amber-border);
    box-shadow: 0 0 40px rgba(251,191,36,0.2), inset 0 0 60px rgba(251,191,36,0.03);
    background: linear-gradient(135deg, rgba(251,191,36,0.03) 0%, var(--bg-card) 100%);
}
.mega-status.stop {
    border-color: var(--border-dim);
}
.mega-status.hist {
    border-color: var(--purple-border);
    box-shadow: 0 0 40px rgba(168,85,247,0.25), inset 0 0 60px rgba(168,85,247,0.03);
    background: linear-gradient(135deg, rgba(168,85,247,0.03) 0%, var(--bg-card) 100%);
}

.mega-left { display: flex; align-items: center; gap: 24px; }
.mega-icon {
    width: 64px; height: 64px;
    border-radius: 16px;
    display: flex; align-items: center; justify-content: center;
    font-size: 28px;
    animation: popIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
}
.mega-icon::after {
    content: '';
    position: absolute;
    inset: -4px;
    border-radius: 20px;
    background: inherit;
    opacity: 0.4;
    filter: blur(10px);
    z-index: -1;
}
.mega-icon:hover {
    transform: scale(1.15) rotate(5deg);
}
.mega-status.go .mega-icon {
    background: linear-gradient(135deg, var(--green-dim), var(--green));
    color: var(--bg-deep);
    box-shadow: 0 8px 32px rgba(0,255,136,0.5), inset 0 1px 0 rgba(255,255,255,0.2);
    animation: popIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both, float 3s ease-in-out infinite;
}
.mega-status.wait .mega-icon {
    background: linear-gradient(135deg, #f59e0b, var(--amber));
    color: var(--bg-deep);
    box-shadow: 0 8px 32px rgba(251,191,36,0.4);
}
.mega-status.stop .mega-icon {
    background: var(--bg-elevated);
    color: var(--text-muted);
}
.mega-status.hist .mega-icon {
    background: linear-gradient(135deg, var(--purple-dim), var(--purple));
    color: white;
    box-shadow: 0 8px 32px rgba(168,85,247,0.4);
}

.mega-title {
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -0.5px;
    animation: fadeInLeft 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both;
}
.mega-status.go .mega-title { 
    color: var(--green); 
    text-shadow: 0 0 30px rgba(0,255,136,0.5);
    animation: fadeInLeft 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both, glowText 3s ease-in-out infinite;
}
.mega-status.wait .mega-title { color: var(--amber); }
.mega-status.stop .mega-title { color: var(--text-muted); }
.mega-status.hist .mega-title { color: var(--purple); }

.mega-sub { 
    font-size: 14px; 
    color: var(--text-secondary); 
    margin-top: 6px; 
    animation: fadeInLeft 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.4s both;
}

.mega-right { text-align: right; animation: fadeInRight 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both; }
.mega-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 36px;
    font-weight: 700;
    color: var(--text-white);
    animation: countUp 0.8s ease-out 0.3s both;
}
.mega-meta {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
    font-family: 'JetBrains Mono', monospace;
    animation: fadeInUp 0.5s ease-out 0.5s both;
}

/* ═══════════════════════════════════════════════════════════════════════════
   VALIDATION ROW - Dramatic Animated Pills
   ═══════════════════════════════════════════════════════════════════════════ */
.valid-row {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 14px;
    margin-bottom: 28px;
}
.valid-card {
    background: linear-gradient(145deg, var(--bg-card) 0%, var(--bg-card-alt) 100%);
    border: 1px solid var(--border-dim);
    border-radius: 16px;
    padding: 20px 16px;
    text-align: center;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    animation: slideInBounce 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    position: relative;
    overflow: hidden;
}
/* Shimmer overlay */
.valid-card::before {
    content: '';
    position: absolute;
    top: 0; left: -100%; right: 0; bottom: 0;
    width: 50%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
    transform: skewX(-20deg);
    transition: left 0.6s ease;
}
.valid-card:hover::before {
    left: 150%;
}
.valid-card:nth-child(1) { animation-delay: 0.05s; }
.valid-card:nth-child(2) { animation-delay: 0.1s; }
.valid-card:nth-child(3) { animation-delay: 0.15s; }
.valid-card:nth-child(4) { animation-delay: 0.2s; }
.valid-card:nth-child(5) { animation-delay: 0.25s; }

.valid-card:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 0 20px 40px rgba(0,0,0,0.4);
}
.valid-card.pass {
    background: linear-gradient(145deg, var(--green-bg) 0%, rgba(0,255,136,0.05) 100%);
    border-color: var(--green-border);
}
.valid-card.pass:hover {
    box-shadow: 0 20px 50px rgba(0,255,136,0.25), inset 0 0 30px rgba(0,255,136,0.05);
    border-color: var(--green);
}
.valid-card.fail {
    background: linear-gradient(145deg, var(--red-bg) 0%, rgba(255,71,87,0.05) 100%);
    border-color: var(--red-border);
}
.valid-card.fail:hover {
    box-shadow: 0 20px 50px rgba(255,71,87,0.25), inset 0 0 30px rgba(255,71,87,0.05);
    border-color: var(--red);
}
.valid-card.neutral {
    background: linear-gradient(145deg, var(--amber-bg) 0%, rgba(251,191,36,0.05) 100%);
    border-color: var(--amber-border);
}
.valid-card.neutral:hover {
    box-shadow: 0 20px 50px rgba(251,191,36,0.2);
}

.valid-icon { 
    font-size: 28px; 
    margin-bottom: 10px;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    display: inline-block;
}
.valid-card:hover .valid-icon {
    transform: scale(1.3) rotate(10deg);
    filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));
}
.valid-card.pass:hover .valid-icon {
    filter: drop-shadow(0 0 15px rgba(0,255,136,0.6));
}
.valid-card.fail:hover .valid-icon {
    filter: drop-shadow(0 0 15px rgba(255,71,87,0.6));
}
.valid-label { 
    font-size: 10px; 
    color: var(--text-muted); 
    text-transform: uppercase; 
    letter-spacing: 1.5px; 
    margin-bottom: 8px;
    font-weight: 600;
}
.valid-val { 
    font-family: 'JetBrains Mono', monospace; 
    font-size: 18px; 
    font-weight: 700;
    transition: all 0.3s ease;
    animation: countUp 0.6s ease-out 0.5s both;
}
.valid-card.pass .valid-val { color: var(--green); }
.valid-card.fail .valid-val { color: var(--red); }
.valid-card.neutral .valid-val { color: var(--amber); }

/* ═══════════════════════════════════════════════════════════════════════════
   FEATURE CARDS - Animated
   ═══════════════════════════════════════════════════════════════════════════ */
.feature-card {
    background: var(--bg-card);
    border: 1px solid var(--border-dim);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: all 0.3s ease;
    animation: fadeInUp 0.5s ease-out both;
}
.feature-card:hover {
    border-color: var(--border-normal);
    background: var(--bg-elevated);
    transform: translateX(8px);
    box-shadow: -8px 0 30px rgba(0,0,0,0.2);
}
.feature-icon {
    width: 48px; height: 48px;
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
    transition: all 0.3s ease;
}
.feature-card:hover .feature-icon {
    transform: scale(1.15) rotate(5deg);
}
.feature-icon.green { background: var(--green-bg); color: var(--green); }
.feature-icon.purple { background: var(--purple-bg); color: var(--purple); }
.feature-icon.cyan { background: var(--cyan-bg); color: var(--cyan); }
.feature-icon.red { background: var(--red-bg); color: var(--red); }
.feature-icon.amber { background: var(--amber-bg); color: var(--amber); }

.feature-content { flex: 1; }
.feature-title { font-size: 15px; font-weight: 600; color: var(--text-white); margin-bottom: 4px; }
.feature-subtitle { font-size: 13px; color: var(--text-secondary); }
.feature-value { 
    font-family: 'JetBrains Mono', monospace; 
    font-size: 18px; 
    font-weight: 700;
    transition: all 0.3s ease;
}
.feature-card:hover .feature-value {
    transform: scale(1.05);
}
.feature-value.green { color: var(--green); }
.feature-value.red { color: var(--red); }
.feature-value.amber { color: var(--amber); }

/* ═══════════════════════════════════════════════════════════════════════════
   SESSION CARDS - Animated
   ═══════════════════════════════════════════════════════════════════════════ */
.session-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 28px;
}
.session-card {
    background: linear-gradient(145deg, var(--bg-card) 0%, var(--bg-card-alt) 100%);
    border: 1px solid var(--border-dim);
    border-radius: 16px;
    padding: 20px;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    position: relative;
    overflow: hidden;
}
/* Animated border gradient */
.session-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 3px;
    background: linear-gradient(90deg, transparent, var(--border-bright), transparent);
    transform: translateX(-100%);
    transition: transform 0.5s ease;
}
.session-card:hover::before {
    transform: translateX(100%);
}
.session-card:nth-child(1) { animation-delay: 0.1s; }
.session-card:nth-child(2) { animation-delay: 0.15s; }
.session-card:nth-child(3) { animation-delay: 0.2s; }
.session-card:nth-child(4) { animation-delay: 0.25s; }

.session-card:hover {
    transform: translateY(-8px) scale(1.02);
    border-color: var(--border-normal);
    box-shadow: 0 25px 50px rgba(0,0,0,0.5);
}
.session-head { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
.session-icon {
    width: 44px; height: 44px;
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
}
.session-icon::after {
    content: '';
    position: absolute;
    inset: -3px;
    border-radius: 14px;
    background: inherit;
    opacity: 0.4;
    filter: blur(8px);
    z-index: -1;
    transition: all 0.3s ease;
}
.session-card:hover .session-icon {
    transform: scale(1.2) rotate(10deg);
}
.session-card:hover .session-icon::after {
    opacity: 0.6;
    filter: blur(12px);
}
.session-card.sydney .session-icon { background: linear-gradient(135deg, #3b82f6, #60a5fa); box-shadow: 0 4px 20px rgba(59,130,246,0.4); }
.session-card.tokyo .session-icon { background: linear-gradient(135deg, #ef4444, #f87171); box-shadow: 0 4px 20px rgba(239,68,68,0.4); }
.session-card.london .session-icon { background: linear-gradient(135deg, var(--green-dim), var(--green)); box-shadow: 0 4px 20px rgba(0,255,136,0.4); }
.session-card.overnight .session-icon { background: linear-gradient(135deg, var(--purple-dim), var(--purple)); box-shadow: 0 4px 20px rgba(168,85,247,0.4); }

.session-name { font-size: 15px; font-weight: 700; color: var(--text-white); }
.session-data { display: flex; flex-direction: column; gap: 10px; }
.session-line {
    display: flex; justify-content: space-between;
    font-size: 13px;
    transition: all 0.3s ease;
    padding: 6px 8px;
    margin: 0 -8px;
    border-radius: 6px;
}
.session-line:hover {
    background: rgba(255,255,255,0.04);
    transform: translateX(4px);
}
.session-line .label { color: var(--text-muted); }
.session-line .value { font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.session-line .value.high { color: var(--green); text-shadow: 0 0 20px rgba(0,255,136,0.4); }
.session-line .value.low { color: var(--red); text-shadow: 0 0 20px rgba(255,71,87,0.4); }

/* ═══════════════════════════════════════════════════════════════════════════
   COMMAND CENTER - Premium Card with DRAMATIC Animations
   ═══════════════════════════════════════════════════════════════════════════ */
.cmd-card {
    background: linear-gradient(145deg, var(--bg-card) 0%, rgba(17,17,17,0.95) 50%, var(--bg-card-alt) 100%);
    border: 1px solid var(--border-dim);
    border-radius: 20px;
    padding: 28px;
    margin-bottom: 28px;
    animation: epicReveal 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    overflow: hidden;
}
/* Animated corner accents */
.cmd-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 60px; height: 60px;
    background: linear-gradient(135deg, rgba(0,255,136,0.15), transparent);
    border-radius: 20px 0 0 0;
}
.cmd-card::after {
    content: '';
    position: absolute;
    bottom: 0; right: 0;
    width: 60px; height: 60px;
    background: linear-gradient(315deg, rgba(0,255,136,0.1), transparent);
    border-radius: 0 0 20px 0;
}
.cmd-card:hover {
    border-color: var(--border-normal);
    box-shadow: 0 30px 60px rgba(0,0,0,0.4);
    transform: translateY(-4px);
}
.cmd-header {
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border-dim);
    position: relative;
}
/* Animated underline */
.cmd-header::after {
    content: '';
    position: absolute;
    bottom: -1px; left: 0;
    width: 0; height: 2px;
    background: linear-gradient(90deg, var(--green), var(--cyan));
    transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.cmd-card:hover .cmd-header::after {
    width: 100%;
}
.cmd-title { font-size: 20px; font-weight: 800; color: var(--text-white); animation: fadeInLeft 0.5s ease-out 0.2s both; }
.cmd-subtitle { font-size: 13px; color: var(--text-muted); margin-top: 4px; animation: fadeInLeft 0.5s ease-out 0.3s both; }
.cmd-badge {
    padding: 8px 16px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    animation: popIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) 0.4s both;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.cmd-badge::before {
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    transition: left 0.5s ease;
}
.cmd-badge:hover::before {
    left: 100%;
}
.cmd-badge:hover {
    transform: scale(1.08);
}
.cmd-badge.rising { 
    background: linear-gradient(135deg, var(--green-bg), rgba(0,255,136,0.15)); 
    color: var(--green); 
    border: 1px solid var(--green-border);
    box-shadow: 0 4px 20px rgba(0,255,136,0.2);
}
.cmd-badge.falling { 
    background: linear-gradient(135deg, var(--red-bg), rgba(255,71,87,0.15)); 
    color: var(--red); 
    border: 1px solid var(--red-border);
    box-shadow: 0 4px 20px rgba(255,71,87,0.2);
}

.channel-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 24px;
}
.channel-item {
    background: linear-gradient(145deg, var(--bg-card-alt) 0%, var(--bg-card) 100%);
    border: 1px solid var(--border-dim);
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    animation: slideInBounce 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    overflow: hidden;
}
/* Glow effect at border */
.channel-item::before {
    content: '';
    position: absolute;
    top: 0; left: 0; bottom: 0;
    width: 4px;
    transition: all 0.3s ease;
}
.channel-item.ceiling::before { 
    background: linear-gradient(180deg, var(--green), rgba(0,255,136,0.3));
    box-shadow: 0 0 20px rgba(0,255,136,0.5);
}
.channel-item.floor::before { 
    background: linear-gradient(180deg, var(--red), rgba(255,71,87,0.3));
    box-shadow: 0 0 20px rgba(255,71,87,0.5);
}
.channel-item:first-child { animation-delay: 0.15s; }
.channel-item:last-child { animation-delay: 0.25s; }
.channel-item:hover {
    transform: translateY(-6px) scale(1.02);
    box-shadow: 0 20px 40px rgba(0,0,0,0.4);
}
.channel-item.ceiling:hover { border-color: var(--green-border); }
.channel-item.floor:hover { border-color: var(--red-border); }
.channel-item.ceiling { border-left: none; border-radius: 14px; }
.channel-item.floor { border-left: none; border-radius: 14px; }
.channel-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px; font-weight: 600; }
.channel-value { 
    font-family: 'JetBrains Mono', monospace; 
    font-size: 28px; 
    font-weight: 700; 
    color: var(--text-white);
    transition: all 0.3s ease;
    animation: countUp 0.7s ease-out 0.5s both;
}
.channel-item:hover .channel-value {
    transform: scale(1.08);
}
.channel-item.ceiling:hover .channel-value { text-shadow: 0 0 30px rgba(0,255,136,0.5); }
.channel-item.floor:hover .channel-value { text-shadow: 0 0 30px rgba(255,71,87,0.5); }
.channel-es { font-size: 12px; color: var(--text-muted); margin-top: 6px; }

.setup-box {
    background: linear-gradient(145deg, var(--bg-elevated) 0%, var(--bg-card) 100%);
    border-radius: 20px;
    padding: 24px;
    margin-top: 20px;
    animation: epicReveal 0.7s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both;
    position: relative;
    overflow: hidden;
}
/* Animated gradient border */
.setup-box::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 20px;
    padding: 2px;
    background: linear-gradient(135deg, transparent 30%, var(--green) 50%, transparent 70%);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    background-size: 200% 200%;
    animation: gradientShift 3s ease-in-out infinite;
    opacity: 0.5;
}
.setup-box.puts::before {
    background: linear-gradient(135deg, transparent 30%, var(--red) 50%, transparent 70%);
    background-size: 200% 200%;
}
.setup-box.puts { 
    border: 1px solid var(--red-border);
    box-shadow: 0 10px 40px rgba(255,71,87,0.15), inset 0 0 60px rgba(255,71,87,0.03);
}
.setup-box.calls { 
    border: 1px solid var(--green-border);
    box-shadow: 0 10px 40px rgba(0,255,136,0.15), inset 0 0 60px rgba(0,255,136,0.03);
}

.setup-header { display: flex; align-items: center; gap: 20px; margin-bottom: 20px; }
.setup-icon {
    width: 56px; height: 56px;
    border-radius: 16px;
    display: flex; align-items: center; justify-content: center;
    font-size: 28px; font-weight: 700;
    animation: floatRotate 4s ease-in-out infinite;
    position: relative;
}
.setup-icon::after {
    content: '';
    position: absolute;
    inset: -4px;
    border-radius: 20px;
    background: inherit;
    opacity: 0.4;
    filter: blur(12px);
    z-index: -1;
}
.setup-box.puts .setup-icon { 
    background: linear-gradient(135deg, rgba(255,71,87,0.2), rgba(255,71,87,0.1)); 
    color: var(--red);
    box-shadow: 0 8px 30px rgba(255,71,87,0.3);
}
.setup-box.calls .setup-icon { 
    background: linear-gradient(135deg, rgba(0,255,136,0.2), rgba(0,255,136,0.1)); 
    color: var(--green);
    box-shadow: 0 8px 30px rgba(0,255,136,0.3);
}
.setup-title { font-size: 24px; font-weight: 800; animation: fadeInLeft 0.5s ease-out 0.4s both; }
.setup-box.puts .setup-title { color: var(--red); text-shadow: 0 0 30px rgba(255,71,87,0.4); }
.setup-box.calls .setup-title { color: var(--green); text-shadow: 0 0 30px rgba(0,255,136,0.4); }

.setup-metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 20px;
}
.setup-metric {
    background: linear-gradient(145deg, var(--bg-card) 0%, var(--bg-card-alt) 100%);
    border: 1px solid var(--border-dim);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    animation: slideInBounce 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.setup-metric:nth-child(1) { animation-delay: 0.1s; }
.setup-metric:nth-child(2) { animation-delay: 0.15s; }
.setup-metric:nth-child(3) { animation-delay: 0.2s; }
.setup-metric:nth-child(4) { animation-delay: 0.25s; }
.setup-metric:hover {
    background: var(--bg-elevated);
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 15px 30px rgba(0,0,0,0.3);
    border-color: var(--border-normal);
}
.setup-metric-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; font-weight: 600; }
.setup-metric-value { 
    font-family: 'JetBrains Mono', monospace; 
    font-size: 18px; 
    font-weight: 700; 
    color: var(--text-white);
    animation: countUp 0.6s ease-out 0.5s both;
}

.entry-rule {
    background: linear-gradient(145deg, var(--amber-bg) 0%, rgba(251,191,36,0.05) 100%);
    border: 1px solid var(--amber-border);
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 20px;
    animation: fadeInUp 0.5s ease-out 0.4s both;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.entry-rule::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
    background: linear-gradient(180deg, var(--amber), rgba(251,191,36,0.3));
    border-radius: 4px 0 0 4px;
}
}
.entry-rule:hover {
    background: rgba(251,191,36,0.12);
}
.entry-rule-title { font-size: 12px; font-weight: 600; color: var(--amber); margin-bottom: 6px; }
.entry-rule-text { font-size: 13px; color: var(--text-primary); }
.entry-rule-warning { font-size: 11px; color: var(--text-muted); margin-top: 8px; }

.targets-box {
    background: var(--bg-card);
    border-radius: 10px;
    padding: 14px;
    animation: fadeInUp 0.5s ease-out 0.5s both;
}
.targets-title { font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
.target-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-dim);
    font-size: 13px;
    transition: all 0.2s ease;
}
.target-row:hover {
    background: rgba(255,255,255,0.02);
    margin: 0 -14px;
    padding: 8px 14px;
}
.target-row:last-child { border-bottom: none; }
.target-row:first-of-type {
    background: var(--green-bg);
    margin: 0 -14px;
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid var(--green-border);
    animation: pulseGlow 3s ease-in-out infinite;
}
.target-name { color: var(--text-secondary); }
.target-level { font-family: 'JetBrains Mono', monospace; color: var(--text-white); }
.target-price { font-family: 'JetBrains Mono', monospace; color: var(--green); }

/* ═══════════════════════════════════════════════════════════════════════════
   ANALYSIS GRID - 2x2 Layout with Animations
   ═══════════════════════════════════════════════════════════════════════════ */
.analysis-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 24px;
}
.analysis-card {
    background: var(--bg-card);
    border: 1px solid var(--border-dim);
    border-radius: 12px;
    padding: 20px;
    animation: fadeInUp 0.5s ease-out both;
    transition: all 0.3s ease;
}
.analysis-card:nth-child(1) { animation-delay: 0.1s; }
.analysis-card:nth-child(2) { animation-delay: 0.2s; }
.analysis-card:nth-child(3) { animation-delay: 0.3s; }
.analysis-card:nth-child(4) { animation-delay: 0.4s; }

.analysis-card:hover {
    border-color: var(--border-normal);
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.3);
}
.analysis-header {
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 16px;
}
.analysis-left { display: flex; align-items: center; gap: 12px; }
.analysis-icon {
    width: 40px; height: 40px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
    transition: all 0.3s ease;
}
.analysis-card:hover .analysis-icon {
    transform: scale(1.1) rotate(5deg);
}
.analysis-title { font-size: 14px; font-weight: 600; color: var(--text-white); }
.analysis-subtitle { font-size: 12px; color: var(--text-muted); }
.analysis-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 700;
    animation: countUp 0.6s ease-out both;
}
.analysis-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }

/* Flow meter with animation */
.flow-meter {
    height: 8px;
    background: linear-gradient(90deg, var(--red), var(--amber) 50%, var(--green));
    border-radius: 4px;
    position: relative;
    margin: 12px 0;
    overflow: hidden;
}
.flow-meter::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    animation: shimmer 2s infinite;
    background-size: 200% 100%;
}
.flow-marker {
    position: absolute;
    top: -3px;
    width: 6px; height: 14px;
    background: white;
    border-radius: 3px;
    transform: translateX(-50%);
    box-shadow: 0 2px 8px rgba(0,0,0,0.5), 0 0 10px rgba(255,255,255,0.3);
    transition: left 0.5s ease-out;
    animation: float 2s ease-in-out infinite;
}

/* Confidence bar with animation */
.conf-bar {
    height: 6px;
    background: var(--bg-elevated);
    border-radius: 3px;
    overflow: hidden;
    margin: 8px 0;
}
.conf-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.8s ease-out;
    position: relative;
    overflow: hidden;
}
.conf-fill::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
    animation: shimmer 1.5s infinite;
    background-size: 200% 100%;
}

/* ═══════════════════════════════════════════════════════════════════════════
   8:30 CANDLE - Animated
   ═══════════════════════════════════════════════════════════════════════════ */
.candle-card {
    background: var(--bg-card);
    border: 1px solid var(--border-dim);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
    animation: fadeInUp 0.5s ease-out;
    transition: all 0.3s ease;
}
.candle-card:hover {
    border-color: var(--border-normal);
}
.candle-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.candle-left { display: flex; align-items: center; gap: 12px; }
.candle-icon {
    width: 44px; height: 44px;
    background: var(--cyan-bg);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
    transition: all 0.3s ease;
}
.candle-card:hover .candle-icon {
    transform: scale(1.1);
    box-shadow: 0 4px 20px rgba(34,211,238,0.3);
}
.candle-title { font-size: 15px; font-weight: 600; color: var(--text-white); }
.candle-subtitle { font-size: 12px; color: var(--text-muted); }
.candle-type {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
    animation: fadeInScale 0.4s ease-out 0.2s both;
    transition: all 0.3s ease;
}
.candle-type:hover {
    transform: scale(1.05);
}
.candle-type.bullish { background: var(--green-bg); color: var(--green); border: 1px solid var(--green-border); }
.candle-type.bearish { background: var(--red-bg); color: var(--red); border: 1px solid var(--red-border); }
.candle-type.neutral { background: var(--amber-bg); color: var(--amber); border: 1px solid var(--amber-border); }

.candle-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}
.candle-item {
    background: var(--bg-card-alt);
    border-radius: 8px;
    padding: 12px;
    text-align: center;
    animation: fadeInUp 0.4s ease-out both;
    transition: all 0.3s ease;
}
.candle-item:nth-child(1) { animation-delay: 0.1s; }
.candle-item:nth-child(2) { animation-delay: 0.15s; }
.candle-item:nth-child(3) { animation-delay: 0.2s; }
.candle-item:nth-child(4) { animation-delay: 0.25s; }
.candle-item:hover {
    background: var(--bg-elevated);
    transform: translateY(-2px);
}
.candle-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.candle-value { font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 600; color: var(--text-white); }
.candle-value.high { color: var(--green); }
.candle-value.low { color: var(--red); }

/* ═══════════════════════════════════════════════════════════════════════════
   FOOTER
   ═══════════════════════════════════════════════════════════════════════════ */
.footer {
    text-align: center;
    padding: 32px;
    color: var(--text-muted);
    font-size: 12px;
    border-top: 1px solid var(--border-dim);
    margin-top: 40px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   MISC
   ═══════════════════════════════════════════════════════════════════════════ */
.card { background: var(--bg-card); border: 1px solid var(--border-dim); border-radius: 12px; padding: 16px; }
.pillar { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-dim); font-size: 13px; }
.pillar:last-child { border-bottom: none; }
.pillar span:first-child { color: var(--text-muted); }
.pillar span:last-child { font-family: 'JetBrains Mono', monospace; }

/* Live indicator */
.live-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: var(--green-bg);
    border: 1px solid var(--green-border);
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    color: var(--green);
}
.live-dot {
    width: 6px; height: 6px;
    background: var(--green);
    border-radius: 50%;
    animation: pulse 2s infinite;
}
</style>"""

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def now_ct():return datetime.now(CT)

def blocks_between(start,end):
    """
    Count 30-min blocks between two times, excluding maintenance breaks.
    ALL maintenance breaks = 2 blocks (1 hour equivalent):
    - Mon-Thu: 4:00 PM - 5:00 PM CT = 2 blocks
    - Weekend: Fri 4:00 PM - Sun 5:00 PM CT = 2 blocks (whole weekend = 1 maintenance break)
    """
    if end<=start:
        return 0
    
    # Count total raw blocks
    total_seconds=(end-start).total_seconds()
    raw_blocks=int(total_seconds/60//30)
    
    # Count maintenance breaks crossed (each = 2 blocks)
    maintenance_count=0
    current_date=start.date()
    end_date=end.date()
    
    while current_date<=end_date:
        weekday=current_date.weekday()
        
        if weekday==4:  # Friday - weekend break
            break_start=CT.localize(datetime.combine(current_date,time(16,0)))
            break_end=CT.localize(datetime.combine(current_date+timedelta(days=2),time(17,0)))  # Sunday 5 PM
            
            # If our range crosses this break, count it as 1 maintenance (2 blocks)
            if start<break_end and end>break_start:
                maintenance_count+=1
            
            current_date+=timedelta(days=3)  # Skip to Monday
            
        elif weekday in [5,6]:  # Saturday/Sunday - handled by Friday
            current_date+=timedelta(days=1)
            
        else:  # Mon-Thu: regular 4-5 PM maintenance
            break_start=CT.localize(datetime.combine(current_date,time(16,0)))
            break_end=CT.localize(datetime.combine(current_date,time(17,0)))
            
            if start<break_end and end>break_start:
                maintenance_count+=1
            
            current_date+=timedelta(days=1)
    
    # Each maintenance break = 2 blocks
    maintenance_blocks=maintenance_count*2
    
    # Also subtract the actual time of weekend (since raw_blocks includes it)
    # Weekend = Fri 4 PM to Sun 5 PM = 49 hours, but we only want to count 2 blocks
    # So subtract (49 hours worth of blocks - 2)
    weekend_adjustment=0
    current_date=start.date()
    while current_date<=end_date:
        if current_date.weekday()==4:  # Friday
            wknd_start=CT.localize(datetime.combine(current_date,time(16,0)))
            wknd_end=CT.localize(datetime.combine(current_date+timedelta(days=2),time(17,0)))
            
            if start<wknd_end and end>wknd_start:
                overlap_start=max(start,wknd_start)
                overlap_end=min(end,wknd_end)
                if overlap_end>overlap_start:
                    overlap_blocks=int((overlap_end-overlap_start).total_seconds()/60//30)
                    # We already counted 2 blocks for this, so subtract the excess
                    weekend_adjustment+=max(0,overlap_blocks-2)
        current_date+=timedelta(days=1)
    
    return max(0,raw_blocks-maintenance_blocks-weekend_adjustment)

def get_vix_zone(vix):
    for z,(lo,hi) in VIX_ZONES.items():
        if lo<=vix<hi:return z
    return "NORMAL"

def save_inputs(d):
    try:
        s={k:(v.isoformat() if isinstance(v,(datetime,date)) else v) for k,v in d.items()}
        with open(SAVE_FILE,'w') as f:json.dump(s,f)
    except:pass

def load_inputs():
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE,'r') as f:return json.load(f)
    except:pass
    return {}

# ═══════════════════════════════════════════════════════════════════════════════
# ROBUST DATA FETCHING FUNCTIONS - FIXED VERSION
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def robust_fetch_es_current():
    """
    Robust ES futures price fetching with multiple fallbacks
    """
    sources = []
    debug_info = []
    
    # Try 1: yfinance ES futures (most reliable)
    for ticker in ["ES=F", "MES=F"]:
        try:
            data = yf.Ticker(ticker).history(period="1d", interval="5m")
            if not data.empty and len(data) > 0:
                price = round(float(data['Close'].iloc[-1]), 2)
                reliability = 0.95 if ticker == "ES=F" else 0.90
                sources.append((price, f"yfinance_{ticker}", reliability))
                debug_info.append(f"{ticker}: {price}")
        except Exception as e:
            debug_info.append(f"{ticker} failed: {str(e)[:50]}")
    
    # Try 2: Polygon.io ES futures
    try:
        url = f"{POLYGON_BASE}/v2/aggs/ticker/ES/range/1/minute/1?adjusted=true&sort=desc&limit=1&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "results" in data and len(data["results"]) > 0:
                price = round(data["results"][0]['c'], 2)
                sources.append((price, "polygon_ES", 0.85))
                debug_info.append(f"Polygon ES: {price}")
    except Exception as e:
        debug_info.append(f"Polygon ES failed: {str(e)[:50]}")
    
    # Try 3: SPY as proxy (SPY * 10 ≈ ES)
    try:
        spy = yf.Ticker("SPY").history(period="1d", interval="5m")
        if not spy.empty:
            spy_price = float(spy['Close'].iloc[-1])
            es_price = round(spy_price * 10, 2)  # Approximate conversion
            sources.append((es_price, "SPY_proxy", 0.75))
            debug_info.append(f"SPY proxy: {es_price}")
    except Exception as e:
        debug_info.append(f"SPY proxy failed: {str(e)[:50]}")
    
    # Try 4: Direct download
    try:
        data = yf.download("ES=F", period="1d", interval="1m", progress=False)
        if not data.empty:
            price = round(float(data['Close'].iloc[-1]), 2)
            sources.append((price, "yfinance_download", 0.80))
            debug_info.append(f"Download: {price}")
    except Exception as e:
        debug_info.append(f"Download failed: {str(e)[:50]}")
    
    # Select best source
    if sources:
        # Sort by reliability
        sources.sort(key=lambda x: x[2], reverse=True)
        best_price, best_source, reliability = sources[0]
        
        # Log for debugging
        print(f"ES sources: {debug_info}")
        print(f"Selected: {best_source} @ {best_price}")
        
        return best_price
    else:
        print("All ES sources failed")
        return None

@st.cache_data(ttl=60, show_spinner=False)
def robust_fetch_spx_data():
    """Fetch SPX data with multiple fallbacks"""
    sources = []
    
    # Try 1: Polygon SPX
    try:
        url = f"{POLYGON_BASE}/v2/aggs/ticker/SPX/range/1/minute/1?adjusted=true&sort=desc&limit=1&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "results" in data and len(data["results"]) > 0:
                price = round(data["results"][0]['c'], 2)
                sources.append((price, "polygon_SPX", 0.95))
    except Exception as e:
        print(f"Polygon SPX failed: {e}")
    
    # Try 2: Yahoo Finance ^GSPC
    try:
        spx = yf.Ticker("^GSPC").history(period="1d", interval="5m")
        if not spx.empty:
            price = round(float(spx['Close'].iloc[-1]), 2)
            sources.append((price, "yfinance_GSPC", 0.90))
    except Exception as e:
        print(f"yfinance SPX failed: {e}")
    
    # Try 3: SPY proxy
    try:
        spy = yf.Ticker("SPY").history(period="1d", interval="5m")
        if not spy.empty:
            spy_price = float(spy['Close'].iloc[-1])
            spx_price = round(spy_price * (5000 / 450), 2)  # Rough ratio
            sources.append((spx_price, "SPY_to_SPX", 0.80))
    except:
        pass
    
    if sources:
        sources.sort(key=lambda x: x[2], reverse=True)
        return sources[0][0]
    
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_polygon():
    try:
        url=f"{POLYGON_BASE}/v3/snapshot?ticker.any_of=I:VIX&apiKey={POLYGON_KEY}"
        r=requests.get(url,timeout=10)
        if r.status_code==200:
            d=r.json()
            if "results" in d and len(d["results"])>0:
                res=d["results"][0]
                p=res.get("value") or res.get("session",{}).get("close")
                if p:return round(float(p),2)
    except:pass
    
    # Fallback to yfinance
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period="1d", interval="5m")
        if not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except:
        pass
    
    return 16.0  # Default fallback

@st.cache_data(ttl=300,show_spinner=False)
def fetch_spx_candles_polygon(start_date, end_date, interval="30m"):
    """Fetch SPX candles from Polygon and convert to ES equivalent"""
    try:
        # Convert interval to Polygon format
        timespan = "minute"
        multiplier = 30
        if interval == "1h":
            timespan = "hour"
            multiplier = 1
        elif interval == "30m":
            timespan = "minute"
            multiplier = 30
        
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        url = f"{POLYGON_BASE}/v2/aggs/ticker/I:SPX/range/{multiplier}/{timespan}/{start_str}/{end_str}?adjusted=true&sort=asc&limit=5000&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=15)
        
        if r.status_code == 200:
            d = r.json()
            if "results" in d and len(d["results"]) > 0:
                import pandas as pd
                df = pd.DataFrame(d["results"])
                df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
                df.set_index('timestamp', inplace=True)
                df.rename(columns={'o':'Open','h':'High','l':'Low','c':'Close','v':'Volume'}, inplace=True)
                df.index = df.index.tz_localize('UTC').tz_convert('America/Chicago')
                return df[['Open','High','Low','Close','Volume']]
    except Exception as e:
        print(f"Polygon SPX candles error: {e}")
    return None

@st.cache_data(ttl=300,show_spinner=False)
def fetch_es_candles_range(start_date, end_date, interval="30m", offset=18.0):
    """Fetch ES candles for a specific date range"""
    # Try yfinance first for actual ES data
    for attempt in range(2):
        try:
            es=yf.Ticker("ES=F")
            data=es.history(start=start_date,end=end_date+timedelta(days=1),interval=interval)
            if data is not None and not data.empty and len(data) > 10:
                return data
        except Exception as e:
            time_module.sleep(0.5)
    
    # Backup: Use SPX from Polygon and add offset to convert to ES
    spx_data = fetch_spx_candles_polygon(start_date, end_date, interval)
    if spx_data is not None and not spx_data.empty:
        # Convert SPX to ES by adding offset
        es_data = spx_data.copy()
        es_data['Open'] = es_data['Open'] + offset
        es_data['High'] = es_data['High'] + offset
        es_data['Low'] = es_data['Low'] + offset
        es_data['Close'] = es_data['Close'] + offset
        return es_data
    
    return None

@st.cache_data(ttl=120,show_spinner=False)
def fetch_es_candles(days=7, offset=18.0):
    """Fetch recent ES candles"""
    # Try yfinance first
    for attempt in range(2):
        try:
            es=yf.Ticker("ES=F")
            data=es.history(period=f"{days}d",interval="30m")
            if data is not None and not data.empty and len(data) > 10:
                return data
        except:
            time_module.sleep(0.5)
    
    # Backup: Use SPX from Polygon
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    spx_data = fetch_spx_candles_polygon(start_date, end_date, "30m")
    if spx_data is not None and not spx_data.empty:
        es_data = spx_data.copy()
        es_data['Open'] = es_data['Open'] + offset
        es_data['High'] = es_data['High'] + offset
        es_data['Low'] = es_data['Low'] + offset
        es_data['Close'] = es_data['Close'] + offset
        return es_data
    
    return None

def get_market_data_with_retry(max_retries=3):
    """Get all market data with retry logic"""
    for attempt in range(max_retries):
        try:
            es_price = robust_fetch_es_current()
            spx_price = robust_fetch_spx_data()
            vix_price = fetch_vix_polygon()
            
            if es_price and spx_price:
                # Calculate dynamic offset if both available
                offset = round(es_price - spx_price, 2)
                return {
                    'es': es_price,
                    'spx': spx_price,
                    'vix': vix_price or 16.0,
                    'offset': offset,
                    'source': 'live',
                    'success': True
                }
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time_module.sleep(2)  # Wait before retry
    
    # Fallback to manual mode
    return {
        'es': None,
        'spx': None,
        'vix': 16.0,
        'offset': 18.0,
        'source': 'manual',
        'success': False
    }

# ═══════════════════════════════════════════════════════════════════════════════
# SPX PUT/CALL RATIO FUNCTIONS - FIXED
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_spx_put_call_ratio():
    """
    Fetch real-time SPX put/call ratio from multiple sources
    """
    try:
        # Method 1: Polygon SPX options (most accurate)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # First get SPX options contracts for today
        url = f"{POLYGON_BASE}/v3/reference/options/contracts?underlying_ticker=SPX&expiration_date={today}&limit=200&apiKey={POLYGON_KEY}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            contracts = response.json().get("results", [])
            
            if contracts:
                # Separate puts and calls
                put_contracts = [c for c in contracts if c.get('contract_type', '').lower() == 'put']
                call_contracts = [c for c in contracts if c.get('contract_type', '').lower() == 'call']
                
                # Get tickers for puts and calls
                put_tickers = [c['ticker'] for c in put_contracts[:20]]  # Limit to 20
                call_tickers = [c['ticker'] for c in call_contracts[:20]]
                
                # Function to get volume for tickers
                def get_volume(tickers):
                    if not tickers:
                        return 0
                    
                    # Polygon snapshot for multiple tickers
                    tickers_str = ','.join(tickers)
                    url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/options/tickers/{tickers_str}?apiKey={POLYGON_KEY}"
                    resp = requests.get(url, timeout=10)
                    
                    if resp.status_code == 200:
                        data = resp.json().get("tickers", [])
                        total_volume = 0
                        for ticker in data:
                            volume = ticker.get('day', {}).get('v', 0)
                            total_volume += volume
                        return total_volume
                    return 0
                
                put_volume = get_volume(put_tickers)
                call_volume = get_volume(call_tickers)
                
                if call_volume > 0:
                    ratio = round(put_volume / call_volume, 2)
                    return {
                        "put_volume": put_volume,
                        "call_volume": call_volume,
                        "ratio": ratio,
                        "interpretation": interpret_pc_ratio(ratio),
                        "source": "Polygon SPX Options"
                    }
    
    except Exception as e:
        print(f"Polygon SPX P/C error: {e}")
    
    # Method 2: CBOE data via Yahoo (fallback)
    try:
        # Get SPY options as proxy
        spy = yf.Ticker("SPY")
        opt_chain = spy.options
        if len(opt_chain) > 0:
            nearest_exp = opt_chain[0]
            calls = spy.option_chain(nearest_exp).calls
            puts = spy.option_chain(nearest_exp).puts
            
            call_vol = calls['volume'].sum() if 'volume' in calls.columns else 0
            put_vol = puts['volume'].sum() if 'volume' in puts.columns else 0
            
            if call_vol > 0:
                ratio = round(put_vol / call_vol, 2)
                return {
                    "put_volume": put_vol,
                    "call_volume": call_vol,
                    "ratio": ratio,
                    "interpretation": interpret_pc_ratio(ratio),
                    "source": "SPY Options Proxy"
                }
    except Exception as e:
        print(f"SPY proxy P/C error: {e}")
    
    # Method 3: VIX data includes P/C ratio
    try:
        vix = yf.Ticker("^VIX")
        vix_info = vix.info
        if 'putCallRatio' in vix_info:
            ratio = vix_info['putCallRatio']
            return {
                "put_volume": None,
                "call_volume": None,
                "ratio": ratio,
                "interpretation": interpret_pc_ratio(ratio),
                "source": "CBOE via Yahoo"
            }
    except:
        pass
    
    # Ultimate fallback
    return {
        "put_volume": None,
        "call_volume": None,
        "ratio": 1.0,
        "interpretation": "Neutral (fallback)",
        "source": "Fallback"
    }

def interpret_pc_ratio(ratio):
    """Interpret put/call ratio for trading signals"""
    if ratio > 1.5:
        return "EXTREME FEAR - Contrarian bullish signal"
    elif ratio > 1.2:
        return "HIGH FEAR - Usually bullish"
    elif ratio > 0.9:
        return "NORMAL - Slight bearish bias"
    elif ratio > 0.7:
        return "COMPLACENT - Neutral"
    elif ratio > 0.5:
        return "LOW FEAR - Usually bearish"
    else:
        return "EXTREME COMPLACENCY - Contrarian bearish signal"

# ═══════════════════════════════════════════════════════════════════════════════
# HISTORICAL DATA EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def extract_historical_data(es_candles,trading_date,offset=18.0):
    """Extract all relevant data for a historical date"""
    if es_candles is None or es_candles.empty:
        return None
    
    result={}
    
    # For PRIOR DAY RTH (cones): If Monday, use Friday
    prior_rth_day=trading_date-timedelta(days=1)
    if prior_rth_day.weekday()==6:  # Sunday
        prior_rth_day=prior_rth_day-timedelta(days=2)  # Go to Friday
    elif prior_rth_day.weekday()==5:  # Saturday
        prior_rth_day=prior_rth_day-timedelta(days=1)  # Go to Friday
    
    # For OVERNIGHT SESSION: The day before trading_date
    overnight_day=trading_date-timedelta(days=1)  # This is the day overnight STARTS
    
    # Convert index to CT
    df=es_candles.copy()
    ET=pytz.timezone("America/New_York")
    if df.index.tz is None:
        df.index=df.index.tz_localize(ET).tz_convert(CT)
    else:
        df.index=df.index.tz_convert(CT)
    
    # SESSION TIMES (CT)
    sydney_start=CT.localize(datetime.combine(overnight_day,time(17,0)))
    sydney_end=CT.localize(datetime.combine(overnight_day,time(20,30)))
    tokyo_start=CT.localize(datetime.combine(overnight_day,time(21,0)))
    tokyo_end=CT.localize(datetime.combine(trading_date,time(1,30)))
    overnight_start=CT.localize(datetime.combine(overnight_day,time(17,0)))
    overnight_end=CT.localize(datetime.combine(trading_date,time(3,0)))
    market_open=CT.localize(datetime.combine(trading_date,time(8,0)))
    market_close=CT.localize(datetime.combine(trading_date,time(15,0)))
    
    # Prior day RTH (for cones)
    prior_rth_start=CT.localize(datetime.combine(prior_rth_day,time(8,30)))
    prior_rth_end=CT.localize(datetime.combine(prior_rth_day,time(15,0)))
    
    try:
        # SYDNEY SESSION
        syd_mask=(df.index>=sydney_start)&(df.index<=sydney_end)
        syd_data=df[syd_mask]
        if not syd_data.empty:
            result["sydney_high"]=round(syd_data['High'].max(),2)
            result["sydney_low"]=round(syd_data['Low'].min(),2)
            result["sydney_high_time"]=syd_data['High'].idxmax()
            result["sydney_low_time"]=syd_data['Low'].idxmin()
        
        # TOKYO SESSION
        tok_mask=(df.index>=tokyo_start)&(df.index<=tokyo_end)
        tok_data=df[tok_mask]
        if not tok_data.empty:
            result["tokyo_high"]=round(tok_data['High'].max(),2)
            result["tokyo_low"]=round(tok_data['Low'].min(),2)
            result["tokyo_high_time"]=tok_data['High'].idxmax()
            result["tokyo_low_time"]=tok_data['Low'].idxmin()
        
        # LONDON SESSION
        london_start=CT.localize(datetime.combine(trading_date,time(2,0)))
        london_end=CT.localize(datetime.combine(trading_date,time(3,0)))
        lon_mask=(df.index>=london_start)&(df.index<=london_end)
        lon_data=df[lon_mask]
        if not lon_data.empty:
            result["london_high"]=round(lon_data['High'].max(),2)
            result["london_low"]=round(lon_data['Low'].min(),2)
        
        # OVERNIGHT SESSION
        on_mask=(df.index>=overnight_start)&(df.index<=overnight_end)
        on_data=df[on_mask]
        if not on_data.empty:
            result["on_high"]=round(on_data['High'].max(),2)
            result["on_low"]=round(on_data['Low'].min(),2)
            result["on_high_time"]=on_data['High'].idxmax()
            result["on_low_time"]=on_data['Low'].idxmin()
        
        # PRIOR DAY RTH
        prior_mask=(df.index>=prior_rth_start)&(df.index<=prior_rth_end)
        prior_data=df[prior_mask]
        if not prior_data.empty:
            # HIGH - wick for ascending, close for descending
            result["prior_high_wick"]=round(prior_data['High'].max(),2)
            result["prior_high_wick_time"]=prior_data['High'].idxmax()
            result["prior_high_close"]=round(prior_data['Close'].max(),2)
            result["prior_high_close_time"]=prior_data['Close'].idxmax()
            
            # LOW - lowest close for both
            result["prior_low_close"]=round(prior_data['Close'].min(),2)
            result["prior_low_close_time"]=prior_data['Close'].idxmin()
            
            # CLOSE - last RTH close
            result["prior_close"]=round(prior_data['Close'].iloc[-1],2)
            result["prior_close_time"]=prior_data.index[-1]
            
            # Legacy fields
            result["prior_high"]=result["prior_high_wick"]
            result["prior_low"]=result["prior_low_close"]
            result["prior_high_time"]=result["prior_high_wick_time"]
            result["prior_low_time"]=result["prior_low_close_time"]
            result["prior_date"]=prior_rth_day
        
        # 8:30 AM CANDLE
        candle_830_start=market_open
        candle_830_end=CT.localize(datetime.combine(trading_date,time(9,0)))
        c830_mask=(df.index>=candle_830_start)&(df.index<candle_830_end)
        c830_data=df[c830_mask]
        if not c830_data.empty:
            result["candle_830"]={
                "open":round(c830_data['Open'].iloc[0],2),
                "high":round(c830_data['High'].max(),2),
                "low":round(c830_data['Low'].min(),2),
                "close":round(c830_data['Close'].iloc[-1],2)
            }
        
        # PRE-8:30 PRICE
        pre830_mask=(df.index>=overnight_start)&(df.index<market_open)
        pre830_data=df[pre830_mask]
        if not pre830_data.empty:
            result["pre_830_price"]=round(pre830_data['Close'].iloc[-1],2)
            result["pre_830_time"]=pre830_data.index[-1]
        
        # TRADING DAY DATA
        day_mask=(df.index>=market_open)&(df.index<=market_close)
        day_data=df[day_mask]
        if not day_data.empty:
            result["day_high"]=round(day_data['High'].max(),2)
            result["day_low"]=round(day_data['Low'].min(),2)
            result["day_open"]=round(day_data['Open'].iloc[0],2)
            result["day_close"]=round(day_data['Close'].iloc[-1],2)
            result["day_candles"]=day_data
        
        # 9:00 AM candle
        c900_start=CT.localize(datetime.combine(trading_date,time(9,0)))
        c900_end=CT.localize(datetime.combine(trading_date,time(9,30)))
        c900_mask=(df.index>=c900_start)&(df.index<c900_end)
        c900_data=df[c900_mask]
        if not c900_data.empty:
            result["candle_900"]={
                "open":round(c900_data['Open'].iloc[0],2),
                "high":round(c900_data['High'].max(),2),
                "low":round(c900_data['Low'].min(),2),
                "close":round(c900_data['Close'].iloc[-1],2)
            }
        
        # 9:30 AM candle
        c930_start=CT.localize(datetime.combine(trading_date,time(9,30)))
        c930_end=CT.localize(datetime.combine(trading_date,time(10,0)))
        c930_mask=(df.index>=c930_start)&(df.index<c930_end)
        c930_data=df[c930_mask]
        if not c930_data.empty:
            result["candle_930"]={
                "open":round(c930_data['Open'].iloc[0],2),
                "high":round(c930_data['High'].max(),2),
                "low":round(c930_data['Low'].min(),2),
                "close":round(c930_data['Close'].iloc[-1],2)
            }
            
    except Exception as e:
        st.warning(f"Historical extraction error: {e}")
    
    return result if result else None

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL LOGIC
# ═══════════════════════════════════════════════════════════════════════════════
def determine_channel(sydney_high,sydney_low,tokyo_high,tokyo_low):
    """
    Determine channel direction based on Sydney vs Tokyo session.
    """
    # Primary comparison: Highs
    if tokyo_high>sydney_high:
        return "RISING","Tokyo High > Sydney High"
    elif tokyo_high<sydney_high:
        return "FALLING","Tokyo High < Sydney High"
    
    # Tiebreaker: If highs are equal, use lows
    if tokyo_low>sydney_low:
        return "RISING","Highs equal, Tokyo Low > Sydney Low (higher lows)"
    elif tokyo_low<sydney_low:
        return "FALLING","Highs equal, Tokyo Low < Sydney Low (lower lows)"
    
    # Both highs and lows equal = truly flat, default to FALLING
    return "FALLING","Flat overnight - defaulting to FALLING (conservative)"

def calculate_channel_levels(on_high,on_high_time,on_low,on_low_time,ref_time):
    blocks_high=blocks_between(on_high_time,ref_time)
    blocks_low=blocks_between(on_low_time,ref_time)
    exp_high=SLOPE*blocks_high
    exp_low=SLOPE*blocks_low
    
    return {
        "ceiling_rising":{"level":round(on_high+exp_high,2),"anchor":on_high,"blocks":blocks_high},
        "ceiling_falling":{"level":round(on_high-exp_high,2),"anchor":on_high,"blocks":blocks_high},
        "floor_rising":{"level":round(on_low+exp_low,2),"anchor":on_low,"blocks":blocks_low},
        "floor_falling":{"level":round(on_low-exp_low,2),"anchor":on_low,"blocks":blocks_low},
    }

def get_channel_edges(levels,channel_type):
    """
    Get the active ceiling and floor based on channel type.
    """
    if channel_type=="RISING":
        return levels["ceiling_rising"]["level"],levels["floor_rising"]["level"],"Rising","Rising"
    elif channel_type=="FALLING":
        return levels["ceiling_falling"]["level"],levels["floor_falling"]["level"],"Falling","Falling"
    else:
        # UNDETERMINED: Default to FALLING
        return levels["ceiling_falling"]["level"],levels["floor_falling"]["level"],"Falling*","Falling*"

def assess_position(price,ceiling,floor):
    if price>ceiling+BREAK_THRESHOLD:
        return "ABOVE","broken above",price-ceiling
    elif price<floor-BREAK_THRESHOLD:
        return "BELOW","broken below",floor-price
    elif price>ceiling:
        return "MARGINAL_ABOVE","marginally above",price-ceiling
    elif price<floor:
        return "MARGINAL_BELOW","marginally below",floor-price
    return "INSIDE","inside channel",min(price-floor,ceiling-price)

# ═══════════════════════════════════════════════════════════════════════════════
# CONES
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_cones(prior_high_wick,prior_high_wick_time,prior_high_close,prior_high_close_time,
                   prior_low_close,prior_low_close_time,prior_close,prior_close_time,ref_time):
    """
    Calculate cone rails with correct anchors.
    """
    cones={}
    
    # HIGH cone - different anchors for asc vs desc
    blocks_high_wick=blocks_between(prior_high_wick_time,ref_time)
    blocks_high_close=blocks_between(prior_high_close_time,ref_time)
    exp_high_wick=SLOPE*blocks_high_wick
    exp_high_close=SLOPE*blocks_high_close
    cones["HIGH"]={
        "anchor_asc":prior_high_wick,
        "anchor_desc":prior_high_close,
        "asc":round(prior_high_wick+exp_high_wick,2),
        "desc":round(prior_high_close-exp_high_close,2),
        "blocks_asc":blocks_high_wick,
        "blocks_desc":blocks_high_close
    }
    
    # LOW cone - both from lowest close
    blocks_low=blocks_between(prior_low_close_time,ref_time)
    exp_low=SLOPE*blocks_low
    cones["LOW"]={
        "anchor_asc":prior_low_close,
        "anchor_desc":prior_low_close,
        "asc":round(prior_low_close+exp_low,2),
        "desc":round(prior_low_close-exp_low,2),
        "blocks_asc":blocks_low,
        "blocks_desc":blocks_low
    }
    
    # CLOSE cone - both from last RTH close
    blocks_close=blocks_between(prior_close_time,ref_time)
    exp_close=SLOPE*blocks_close
    cones["CLOSE"]={
        "anchor_asc":prior_close,
        "anchor_desc":prior_close,
        "asc":round(prior_close+exp_close,2),
        "desc":round(prior_close-exp_close,2),
        "blocks_asc":blocks_close,
        "blocks_desc":blocks_close
    }
    
    return cones

def find_targets(entry_level,cones,direction):
    targets=[]
    if direction=="CALLS":
        for name in ["CLOSE","HIGH","LOW"]:
            asc=cones[name]["asc"]
            if asc>entry_level:
                targets.append({"name":f"{name} Asc","level":asc,"distance":round(asc-entry_level,2)})
        targets.sort(key=lambda x:x["level"])
    else:
        for name in ["CLOSE","LOW","HIGH"]:
            desc=cones[name]["desc"]
            if desc<entry_level:
                targets.append({"name":f"{name} Desc","level":desc,"distance":round(entry_level-desc,2)})
        targets.sort(key=lambda x:x["level"],reverse=True)
    return targets

# ═══════════════════════════════════════════════════════════════════════════════
# 8:30 VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
def validate_830_candle(candle,ceiling,floor):
    """
    Validate the 8:30 candle.
    """
    if candle is None:
        return {"status":"AWAITING","message":"Waiting for 8:30 candle","setup":"WAIT","position":"UNKNOWN"}
    
    o,h,l,c=candle["open"],candle["high"],candle["low"],candle["close"]
    
    broke_above=h>ceiling
    broke_below=l<floor
    closed_above=c>ceiling
    closed_below=c<floor
    closed_inside=floor<=c<=ceiling
    is_bullish=c>o
    is_bearish=c<o
    
    if broke_below and not broke_above:
        if closed_below:
            return {"status":"VALID","message":"✅ Broke below floor, closed below","setup":"PUTS","position":"BELOW","edge":floor}
        elif closed_inside:
            if is_bearish:
                return {"status":"TREND_DAY","message":"⚡ TREND DAY: Broke below, rejected, expect rise to ceiling","setup":"CALLS","position":"INSIDE","edge":ceiling}
            else:
                return {"status":"WAIT_9AM","message":"⏸️ Broke below, closed inside, BULLISH candle - wait for 9 AM","setup":"WAIT","position":"INSIDE"}
        else:
            return {"status":"INVALIDATED","message":"❌ Broke below but closed above ceiling","setup":"WAIT","position":"ABOVE"}
    
    elif broke_above and not broke_below:
        if closed_above:
            return {"status":"VALID","message":"✅ Broke above ceiling, closed above","setup":"CALLS","position":"ABOVE","edge":ceiling}
        elif closed_inside:
            if is_bullish:
                return {"status":"TREND_DAY","message":"⚡ TREND DAY: Broke above, rejected, expect drop to floor","setup":"PUTS","position":"INSIDE","edge":floor}
            else:
                return {"status":"WAIT_9AM","message":"⏸️ Broke above, closed inside, BEARISH candle - wait for 9 AM","setup":"WAIT","position":"INSIDE"}
        else:
            return {"status":"INVALIDATED","message":"❌ Broke above but closed below floor","setup":"WAIT","position":"BELOW"}
    
    elif broke_above and broke_below:
        if closed_above:
            return {"status":"VALID","message":"✅ Wide range, closed above ceiling","setup":"CALLS","position":"ABOVE","edge":ceiling}
        elif closed_below:
            return {"status":"VALID","message":"✅ Wide range, closed below floor","setup":"PUTS","position":"BELOW","edge":floor}
        else:
            if is_bullish:
                return {"status":"TREND_DAY","message":"⚡ TREND DAY: Wide range, expect drop to floor","setup":"PUTS","position":"INSIDE","edge":floor}
            elif is_bearish:
                return {"status":"TREND_DAY","message":"⚡ TREND DAY: Wide range, expect rise to ceiling","setup":"CALLS","position":"INSIDE","edge":ceiling}
            else:
                return {"status":"WAIT_9AM","message":"⏸️ Wide range DOJI, closed inside - wait for 9 AM","setup":"WAIT","position":"INSIDE"}
    
    else:
        return {"status":"INSIDE","message":"⏸️ 8:30 candle stayed inside channel","setup":"WAIT","position":"INSIDE"}

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO ANALYSIS - NEW FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════
def analyze_all_scenarios(es_price, ceiling_es, floor_es, cones_spx, vix, hours_to_expiry, offset, channel_type):
    """
    Analyze ALL possible scenarios for pre-market planning.
    Returns dictionary with all scenarios and their probabilities.
    """
    scenarios = {}
    current_spx = round(es_price - offset, 2) if es_price else None
    
    # SCENARIO 1: BREAK ABOVE CEILING (CALLS)
    if es_price and ceiling_es:
        distance_to_ceiling = es_price - ceiling_es
        if distance_to_ceiling > BREAK_THRESHOLD:
            prob = 0.7  # Already broken
        elif distance_to_ceiling > 0:
            prob = 0.6  # Testing ceiling
        else:
            # Further away = lower probability
            prob = max(0.2, 0.4 - (abs(distance_to_ceiling) / 100))
        
        # Get targets for calls
        entry_spx = round(ceiling_es - offset, 2)
        targets = find_targets(entry_spx, cones_spx, "CALLS") if entry_spx else []
        
        # Estimate option prices
        strike = get_strike(entry_spx, "CALL")
        premium = estimate_prices(entry_spx, strike, "CALL", vix, hours_to_expiry)
        
        scenarios["CALLS_BREAKOUT"] = {
            "direction": "CALLS",
            "trigger": f"ES breaks above {ceiling_es:.2f} (currently {distance_to_ceiling:+.2f})",
            "probability": round(prob, 2),
            "entry_level_spx": entry_spx,
            "strike": strike,
            "premium": premium,
            "targets": targets[:3],
            "condition": "ES > Ceiling + 6pts" if distance_to_ceiling > BREAK_THRESHOLD else "ES tests ceiling"
        }
    
    # SCENARIO 2: BREAK BELOW FLOOR (PUTS)
    if es_price and floor_es:
        distance_to_floor = floor_es - es_price
        if distance_to_floor > BREAK_THRESHOLD:
            prob = 0.7  # Already broken
        elif distance_to_floor > 0:
            prob = 0.6  # Testing floor
        else:
            prob = max(0.2, 0.4 - (abs(distance_to_floor) / 100))
        
        entry_spx = round(floor_es - offset, 2)
        targets = find_targets(entry_spx, cones_spx, "PUTS") if entry_spx else []
        
        strike = get_strike(entry_spx, "PUT")
        premium = estimate_prices(entry_spx, strike, "PUT", vix, hours_to_expiry)
        
        scenarios["PUTS_BREAKOUT"] = {
            "direction": "PUTS",
            "trigger": f"ES breaks below {floor_es:.2f} (currently {distance_to_floor:+.2f})",
            "probability": round(prob, 2),
            "entry_level_spx": entry_spx,
            "strike": strike,
            "premium": premium,
            "targets": targets[:3],
            "condition": "ES < Floor - 6pts" if distance_to_floor > BREAK_THRESHOLD else "ES tests floor"
        }
    
    # SCENARIO 3: INSIDE CHANNEL (BOTH POSSIBLE)
    if es_price and ceiling_es and floor_es:
        channel_width = ceiling_es - floor_es
        if channel_width > 0 and floor_es <= es_price <= ceiling_es:
            # Position in channel (0 = at floor, 100 = at ceiling)
            position_pct = ((es_price - floor_es) / channel_width) * 100
            
            # Adjust probabilities based on channel type
            if channel_type == "RISING":
                calls_prob = (position_pct / 100 * 0.6) + 0.3  # Higher probability for calls in rising channel
                puts_prob = ((100 - position_pct) / 100 * 0.4) + 0.2
            elif channel_type == "FALLING":
                puts_prob = ((100 - position_pct) / 100 * 0.6) + 0.3  # Higher probability for puts in falling channel
                calls_prob = (position_pct / 100 * 0.4) + 0.2
            else:
                calls_prob = position_pct / 100 * 0.5 + 0.25
                puts_prob = (100 - position_pct) / 100 * 0.5 + 0.25
            
            scenarios["INSIDE_CHANNEL"] = {
                "position": f"{position_pct:.0f}% from floor",
                "calls_probability": round(calls_prob, 2),
                "puts_probability": round(puts_prob, 2),
                "channel_width": round(channel_width, 2),
                "recommendation": "Wait for break or fade extremes"
            }
    
    return scenarios

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY CONFIRMATION
# ═══════════════════════════════════════════════════════════════════════════════
def check_entry_confirmation(candle, entry_level, direction, break_threshold=6.0):
    """
    Check if a candle is a valid SETUP candle for entry.
    """
    if candle is None or entry_level is None:
        return {"confirmed": False, "message": "Waiting for candle data", "reason": "NO_DATA"}
    
    o, h, l, c = candle["open"], candle["high"], candle["low"], candle["close"]
    is_bullish = c > o
    is_bearish = c < o
    
    if direction == "PUTS":
        touched_entry = h >= entry_level - 2
        closed_below = c < entry_level
        break_beyond = h - entry_level if h > entry_level else 0
        
        if not touched_entry:
            return {"confirmed": False, "message": "Candle did not reach entry level", "reason": "NO_TOUCH"}
        
        if not is_bullish:
            return {"confirmed": False, "message": "Waiting for bullish setup candle", "reason": "WRONG_COLOR"}
        
        if not closed_below:
            return {"confirmed": False, "message": "Candle closed above entry - no rejection", "reason": "NO_REJECTION"}
        
        if break_beyond > break_threshold:
            return {"confirmed": False, "message": f"⚠️ Momentum probe - broke {break_beyond:.1f} pts through", "reason": "MOMENTUM_PROBE"}
        
        return {"confirmed": True, "message": "✅ SETUP CONFIRMED - Bullish rejection", "reason": "CONFIRMED", "candle_color": "BULLISH"}
    
    elif direction == "CALLS":
        touched_entry = l <= entry_level + 2
        closed_above = c > entry_level
        break_beyond = entry_level - l if l < entry_level else 0
        
        if not touched_entry:
            return {"confirmed": False, "message": "Candle did not reach entry level", "reason": "NO_TOUCH"}
        
        if not is_bearish:
            return {"confirmed": False, "message": "Waiting for bearish setup candle", "reason": "WRONG_COLOR"}
        
        if not closed_above:
            return {"confirmed": False, "message": "Candle closed below entry - no rejection", "reason": "NO_REJECTION"}
        
        if break_beyond > break_threshold:
            return {"confirmed": False, "message": f"⚠️ Momentum probe - broke {break_beyond:.1f} pts through", "reason": "MOMENTUM_PROBE"}
        
        return {"confirmed": True, "message": "✅ SETUP CONFIRMED - Bearish rejection", "reason": "CONFIRMED", "candle_color": "BEARISH"}
    
    return {"confirmed": False, "message": "No direction set", "reason": "NO_DIRECTION"}

def get_next_candle_time(current_time):
    """Get the next 30-min candle time"""
    time_sequence = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]
    try:
        idx = time_sequence.index(current_time)
        if idx < len(time_sequence) - 1:
            return time_sequence[idx + 1]
    except ValueError:
        pass
    return None

def find_entry_confirmation(day_candles, entry_level, direction, offset, break_threshold=6.0, start_time="08:00", slope=0.48):
    """
    Scan through candles to find the setup candle.
    """
    if day_candles is None or day_candles.empty:
        return {"confirmed": False, "message": "No candle data available", "reason": "NO_DATA"}
    
    base_entry_level_spx = entry_level - offset
    ref_time_str = "09:00"
    
    time_to_blocks = {
        "08:00": -2, "08:30": -1, "09:00": 0, "09:30": 1,
        "10:00": 2, "10:30": 3, "11:00": 4
    }
    
    for idx, row in day_candles.iterrows():
        candle_time = idx.strftime("%H:%M")
        
        if candle_time < start_time:
            continue
        if candle_time > "10:30":
            break
        
        candle = {
            "open": row["Open"] - offset,
            "high": row["High"] - offset,
            "low": row["Low"] - offset,
            "close": row["Close"] - offset
        }
        
        blocks_from_ref = time_to_blocks.get(candle_time, 0)
        entry_level_at_time = base_entry_level_spx + (blocks_from_ref * slope)
        
        confirmation = check_entry_confirmation(candle, entry_level_at_time, direction, break_threshold)
        
        if confirmation["confirmed"]:
            entry_time = get_next_candle_time(candle_time)
            confirmation["setup_time"] = candle_time
            confirmation["entry_time"] = entry_time
            confirmation["time"] = entry_time
            confirmation["candle"] = candle
            confirmation["entry_level_at_time"] = round(entry_level_at_time, 2)
            confirmation["message"] = f"✅ {candle_time} setup → Enter at {entry_time}"
            return confirmation
        
        if confirmation.get("reason") == "MOMENTUM_PROBE":
            confirmation["setup_time"] = candle_time
            confirmation["time"] = candle_time
            return confirmation
    
    return {"confirmed": False, "message": "No setup candle found by 10:30 AM", "reason": "NOT_FOUND"}

# ═══════════════════════════════════════════════════════════════════════════════
# HISTORICAL OUTCOME ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
def analyze_historical_outcome(hist_data, validation, ceiling_es, floor_es, targets, direction, entry_level_es, offset):
    """
    Analyze what actually happened on a historical date.
    """
    if "day_candles" not in hist_data:
        return None
    
    day_candles = hist_data["day_candles"]
    entry_level_spx = round(entry_level_es - offset, 2)
    ceiling_spx = round(ceiling_es - offset, 2) if ceiling_es else None
    floor_spx = round(floor_es - offset, 2) if floor_es else None
    
    result = {
        "setup_valid": validation["status"] in ["VALID", "TREND_DAY"],
        "direction": direction,
        "entry_level_es": entry_level_es,
        "entry_level_spx": entry_level_spx,
        "targets_hit": [],
        "max_favorable": 0,
        "max_adverse": 0,
        "final_price": round(hist_data.get("day_close", 0) - offset, 2),
        "timeline": [],
        "entry_confirmation": None
    }
    
    if not result["setup_valid"]:
        result["outcome"] = "NO_SETUP"
        result["message"] = "Setup was not valid"
        return result
    
    entry_conf = find_entry_confirmation(
        day_candles, entry_level_es, direction, offset, BREAK_THRESHOLD, "08:00", SLOPE
    )
    result["entry_confirmation"] = entry_conf
    
    if not entry_conf.get("confirmed"):
        if entry_conf.get("reason") == "MOMENTUM_PROBE":
            result["outcome"] = "MOMENTUM_PROBE"
            result["message"] = entry_conf.get("message", "Momentum probe detected - no entry")
        else:
            result["outcome"] = "NO_ENTRY"
            result["message"] = entry_conf.get("message", "No valid entry confirmation")
        return result
    
    entry_time = entry_conf.get("time", "08:30")
    time_to_blocks = {
        "08:00": -2, "08:30": -1, "09:00": 0, "09:30": 1,
        "10:00": 2, "10:30": 3, "11:00": 4
    }
    blocks_from_ref = time_to_blocks.get(entry_time, 0)
    entry_price_spx = entry_level_spx + (blocks_from_ref * SLOPE)
    
    result["entry_level_at_time"] = round(entry_price_spx, 2)
    result["timeline"].append({
        "time": entry_time,
        "event": f"ENTRY ({entry_conf.get('candle_color', '')})",
        "price": round(entry_price_spx, 2)
    })
    
    tracking_started=False
    for idx,row in day_candles.iterrows():
        candle_time=idx.strftime("%H:%M")
        
        if candle_time<entry_time:
            continue
        if candle_time==entry_time:
            tracking_started=True
            continue
        if not tracking_started:
            continue
        
        candle_high_spx=row['High']-offset
        candle_low_spx=row['Low']-offset
        
        if direction=="PUTS":
            favorable=entry_price_spx-candle_low_spx
            adverse=candle_high_spx-entry_price_spx
        else:
            favorable=candle_high_spx-entry_price_spx
            adverse=entry_price_spx-candle_low_spx
        
        result["max_favorable"]=max(result["max_favorable"],favorable)
        result["max_adverse"]=max(result["max_adverse"],adverse)
        
        for tgt in targets:
            if tgt["name"] not in [t["name"] for t in result["targets_hit"]]:
                if direction=="PUTS" and candle_low_spx<=tgt["level"]:
                    result["targets_hit"].append({"name":tgt["name"],"level":tgt["level"],"time":candle_time})
                    result["timeline"].append({"time":candle_time,"event":f"TARGET: {tgt['name']}","price":tgt["level"]})
                elif direction=="CALLS" and candle_high_spx>=tgt["level"]:
                    result["targets_hit"].append({"name":tgt["name"],"level":tgt["level"],"time":candle_time})
                    result["timeline"].append({"time":candle_time,"event":f"TARGET: {tgt['name']}","price":tgt["level"]})
    
    if len(result["targets_hit"])>0:
        result["outcome"]="WIN"
        result["message"]=f"Hit {len(result['targets_hit'])} target(s): {', '.join([t['name'] for t in result['targets_hit']])}"
    elif result["max_favorable"]>10:
        result["outcome"]="PARTIAL"
        result["message"]=f"Moved {result['max_favorable']:.0f} pts favorable but missed targets"
    else:
        result["outcome"]="LOSS"
        result["message"]=f"Max adverse: {result['max_adverse']:.0f} pts"
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED FLOW BIAS - With Put/Call Ratio Integration
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_market_flow_data():
    """
    Fetch real market flow data from free sources.
    """
    flow_data = {
        "vvix": None,
        "vvix_change": None,
        "vix_term_structure": None,
        "put_call_ratio": None,
        "breadth_ratio": None,
        "risk_on_off": None,
        "data_fresh": False
    }
    
    try:
        # 1. VVIX - Volatility of Volatility
        try:
            vvix = yf.Ticker("^VVIX")
            vvix_hist = vvix.history(period="5d")
            if len(vvix_hist) >= 2:
                flow_data["vvix"] = round(vvix_hist['Close'].iloc[-1], 2)
                flow_data["vvix_change"] = round(vvix_hist['Close'].iloc[-1] - vvix_hist['Close'].iloc[-2], 2)
        except:
            pass
        
        # 2. VIX Term Structure
        try:
            vix = yf.Ticker("^VIX")
            vix3m = yf.Ticker("^VIX3M")
            vix_hist = vix.history(period="2d")
            vix3m_hist = vix3m.history(period="2d")
            if len(vix_hist) > 0 and len(vix3m_hist) > 0:
                vix_val = vix_hist['Close'].iloc[-1]
                vix3m_val = vix3m_hist['Close'].iloc[-1]
                flow_data["vix_term_structure"] = round(vix3m_val - vix_val, 2)
        except:
            pass
        
        # 3. Market Breadth - RSP/SPY Ratio
        try:
            spy = yf.Ticker("SPY")
            rsp = yf.Ticker("RSP")
            spy_hist = spy.history(period="5d")
            rsp_hist = rsp.history(period="5d")
            if len(spy_hist) >= 2 and len(rsp_hist) >= 2:
                current_ratio = rsp_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-1]
                prev_ratio = rsp_hist['Close'].iloc[-2] / spy_hist['Close'].iloc[-2]
                flow_data["breadth_ratio"] = round((current_ratio / prev_ratio - 1) * 100, 3)
        except:
            pass
        
        # 4. Risk On/Off - XLK vs XLU
        try:
            xlk = yf.Ticker("XLK")
            xlu = yf.Ticker("XLU")
            xlk_hist = xlk.history(period="2d")
            xlu_hist = xlu.history(period="2d")
            if len(xlk_hist) >= 2 and len(xlu_hist) >= 2:
                xlk_ret = (xlk_hist['Close'].iloc[-1] / xlk_hist['Close'].iloc[-2] - 1) * 100
                xlu_ret = (xlu_hist['Close'].iloc[-1] / xlu_hist['Close'].iloc[-2] - 1) * 100
                flow_data["risk_on_off"] = round(xlk_ret - xlu_ret, 2)
        except:
            pass
        
        # 5. Put/Call Ratio from SPX
        pc_data = fetch_spx_put_call_ratio()
        if pc_data:
            flow_data["put_call_ratio"] = pc_data.get("ratio")
            flow_data["put_call_interpretation"] = pc_data.get("interpretation")
            flow_data["put_volume"] = pc_data.get("put_volume")
            flow_data["call_volume"] = pc_data.get("call_volume")
        
        real_data_count = sum(1 for v in [flow_data["vvix"], flow_data["vix_term_structure"], 
                                           flow_data["breadth_ratio"], flow_data["risk_on_off"], 
                                           flow_data["put_call_ratio"]] if v is not None)
        flow_data["data_fresh"] = real_data_count >= 2
        
    except Exception as e:
        print(f"Flow data error: {e}")
    
    return flow_data

def calculate_flow_bias(price, on_high, on_low, vix, vix_high, vix_low, prior_close):
    """
    Enhanced Flow Bias calculation with put/call ratio.
    """
    signals = []
    score = 0
    details = {}
    
    flow_data = fetch_market_flow_data()
    
    # PILLAR 1: Price Position in Overnight Range (±20 pts)
    on_range = on_high - on_low
    if on_range > 0:
        price_pos = (price - on_low) / on_range * 100
        details["price_pos"] = f"{price_pos:.0f}%"
        
        if price > on_high:
            pts = 20
            score += pts
            signals.append(("O/N Position", "CALLS", f"Above High (+{price-on_high:.0f})", pts))
        elif price < on_low:
            pts = -20
            score += pts
            signals.append(("O/N Position", "PUTS", f"Below Low ({price-on_low:.0f})", pts))
        elif price_pos > 75:
            pts = 12
            score += pts
            signals.append(("O/N Position", "CALLS", f"Upper 25% ({price_pos:.0f}%)", pts))
        elif price_pos < 25:
            pts = -12
            score += pts
            signals.append(("O/N Position", "PUTS", f"Lower 25% ({price_pos:.0f}%)", pts))
        else:
            signals.append(("O/N Position", "NEUTRAL", f"Mid-Range ({price_pos:.0f}%)", 0))
    
    # PILLAR 2: VIX Level (±15 pts)
    vix_range = vix_high - vix_low if vix_high and vix_low else 0
    if vix_range > 0:
        vix_pos = (vix - vix_low) / vix_range * 100
        details["vix_pos"] = f"{vix_pos:.0f}%"
        
        if vix > vix_high:
            pts = -15
            score += pts
            signals.append(("VIX Level", "PUTS", f"Elevated ({vix:.1f})", pts))
        elif vix < vix_low:
            pts = 15
            score += pts
            signals.append(("VIX Level", "CALLS", f"Compressed ({vix:.1f})", pts))
        elif vix_pos > 70:
            pts = -8
            score += pts
            signals.append(("VIX Level", "PUTS", f"High ({vix:.1f})", pts))
        elif vix_pos < 30:
            pts = 8
            score += pts
            signals.append(("VIX Level", "CALLS", f"Low ({vix:.1f})", pts))
        else:
            signals.append(("VIX Level", "NEUTRAL", f"Normal ({vix:.1f})", 0))
    
    # PILLAR 3: Gap from Prior Close (±15 pts)
    gap = price - prior_close if prior_close else 0
    details["gap"] = f"{gap:+.1f}"
    
    if gap > 20:
        pts = 15
        score += pts
        signals.append(("Gap", "CALLS", f"Large Gap Up (+{gap:.0f})", pts))
    elif gap > 10:
        pts = 10
        score += pts
        signals.append(("Gap", "CALLS", f"Gap Up (+{gap:.0f})", pts))
    elif gap > 5:
        pts = 5
        score += pts
        signals.append(("Gap", "CALLS", f"Small Gap Up (+{gap:.0f})", pts))
    elif gap < -20:
        pts = -15
        score += pts
        signals.append(("Gap", "PUTS", f"Large Gap Down ({gap:.0f})", pts))
    elif gap < -10:
        pts = -10
        score += pts
        signals.append(("Gap", "PUTS", f"Gap Down ({gap:.0f})", pts))
    elif gap < -5:
        pts = -5
        score += pts
        signals.append(("Gap", "PUTS", f"Small Gap Down ({gap:.0f})", pts))
    else:
        signals.append(("Gap", "NEUTRAL", f"Flat ({gap:+.0f})", 0))
    
    # PILLAR 4: VVIX (±10 pts)
    if flow_data["vvix"] is not None:
        vvix = flow_data["vvix"]
        vvix_chg = flow_data["vvix_change"] or 0
        details["vvix"] = f"{vvix:.1f}"
        
        if vvix > 110 and vvix_chg > 3:
            pts = -10
            score += pts
            signals.append(("VVIX", "PUTS", f"Spiking ({vvix:.0f}, +{vvix_chg:.1f})", pts))
        elif vvix > 100:
            pts = -5
            score += pts
            signals.append(("VVIX", "PUTS", f"Elevated ({vvix:.0f})", pts))
        elif vvix < 85 and vvix_chg < -2:
            pts = 8
            score += pts
            signals.append(("VVIX", "CALLS", f"Calm ({vvix:.0f}, {vvix_chg:.1f})", pts))
        elif vvix < 90:
            pts = 5
            score += pts
            signals.append(("VVIX", "CALLS", f"Low ({vvix:.0f})", pts))
        else:
            signals.append(("VVIX", "NEUTRAL", f"Normal ({vvix:.0f})", 0))
    
    # PILLAR 5: VIX Term Structure (±15 pts)
    if flow_data["vix_term_structure"] is not None:
        term = flow_data["vix_term_structure"]
        details["term_structure"] = f"{term:+.2f}"
        
        if term > 3:
            pts = 15
            score += pts
            signals.append(("Term Structure", "CALLS", f"Steep Contango (+{term:.1f})", pts))
        elif term > 0:
            pts = 8
            score += pts
            signals.append(("Term Structure", "CALLS", f"Contango (+{term:.1f})", pts))
        elif term < -2:
            pts = -15
            score += pts
            signals.append(("Term Structure", "PUTS", f"Backwardation ({term:.1f})", pts))
        elif term < 0:
            pts = -8
            score += pts
            signals.append(("Term Structure", "PUTS", f"Slight Inversion ({term:.1f})", pts))
        else:
            signals.append(("Term Structure", "NEUTRAL", f"Flat ({term:.1f})", 0))
    
    # PILLAR 6: Market Breadth (±10 pts)
    if flow_data["breadth_ratio"] is not None:
        breadth = flow_data["breadth_ratio"]
        details["breadth"] = f"{breadth:+.2f}%"
        
        if breadth > 0.3:
            pts = 10
            score += pts
            signals.append(("Breadth", "CALLS", f"Improving (+{breadth:.2f}%)", pts))
        elif breadth > 0.1:
            pts = 5
            score += pts
            signals.append(("Breadth", "CALLS", f"Positive (+{breadth:.2f}%)", pts))
        elif breadth < -0.3:
            pts = -10
            score += pts
            signals.append(("Breadth", "PUTS", f"Deteriorating ({breadth:.2f}%)", pts))
        elif breadth < -0.1:
            pts = -5
            score += pts
            signals.append(("Breadth", "PUTS", f"Negative ({breadth:.2f}%)", pts))
        else:
            signals.append(("Breadth", "NEUTRAL", f"Flat ({breadth:+.2f}%)", 0))
    
    # PILLAR 7: Risk On/Off Rotation (±10 pts)
    if flow_data["risk_on_off"] is not None:
        risk = flow_data["risk_on_off"]
        details["risk_rotation"] = f"{risk:+.2f}%"
        
        if risk > 1.0:
            pts = 10
            score += pts
            signals.append(("Risk Rotation", "CALLS", f"Risk ON (+{risk:.1f}%)", pts))
        elif risk > 0.3:
            pts = 5
            score += pts
            signals.append(("Risk Rotation", "CALLS", f"Slight Risk ON (+{risk:.1f}%)", pts))
        elif risk < -1.0:
            pts = -10
            score += pts
            signals.append(("Risk Rotation", "PUTS", f"Risk OFF ({risk:.1f}%)", pts))
        elif risk < -0.3:
            pts = -5
            score += pts
            signals.append(("Risk Rotation", "PUTS", f"Slight Risk OFF ({risk:.1f}%)", pts))
        else:
            signals.append(("Risk Rotation", "NEUTRAL", f"Balanced ({risk:+.1f}%)", 0))
    
    # PILLAR 8: Put/Call Ratio - CONTRARIAN (±10 pts)
    if flow_data["put_call_ratio"] is not None:
        pc = flow_data["put_call_ratio"]
        details["put_call"] = f"{pc:.2f}"
        
        if pc > 1.2:
            pts = 10  # Contrarian bullish
            score += pts
            signals.append(("Put/Call", "CALLS", f"High Fear ({pc:.2f}) - Contrarian Bull", pts))
        elif pc > 1.0:
            pts = 5
            score += pts
            signals.append(("Put/Call", "CALLS", f"Elevated ({pc:.2f})", pts))
        elif pc < 0.6:
            pts = -10  # Contrarian bearish
            score += pts
            signals.append(("Put/Call", "PUTS", f"Complacency ({pc:.2f}) - Contrarian Bear", pts))
        elif pc < 0.75:
            pts = -5
            score += pts
            signals.append(("Put/Call", "PUTS", f"Low ({pc:.2f})", pts))
        else:
            signals.append(("Put/Call", "NEUTRAL", f"Normal ({pc:.2f})", 0))
    
    # FINAL BIAS DETERMINATION
    score = max(-100, min(100, score))
    
    if score >= 40:
        bias = "STRONG_CALLS"
    elif score >= 20:
        bias = "CALLS"
    elif score <= -40:
        bias = "STRONG_PUTS"
    elif score <= -20:
        bias = "PUTS"
    else:
        bias = "NEUTRAL"
    
    real_sources = sum(1 for k in ["vvix", "vix_term_structure", "breadth_ratio", "risk_on_off", "put_call_ratio"] 
                       if flow_data.get(k) is not None)
    
    return {
        "bias": bias,
        "score": score,
        "signals": signals,
        "details": details,
        "real_data_sources": real_sources,
        "data_fresh": flow_data["data_fresh"],
        "put_call_ratio": flow_data.get("put_call_ratio"),
        "put_call_interpretation": flow_data.get("put_call_interpretation")
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MOMENTUM & MA
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_momentum(es_candles):
    if es_candles is None or len(es_candles)<26:
        return {"signal":"NEUTRAL","rsi":50,"macd":0}
    close=es_candles['Close']
    delta=close.diff()
    gain=(delta.where(delta>0,0)).rolling(14).mean()
    loss=(-delta.where(delta<0,0)).rolling(14).mean()
    rs=gain/loss
    rsi=100-(100/(1+rs))
    rsi_val=round(rsi.iloc[-1],1) if not pd.isna(rsi.iloc[-1]) else 50
    ema12=close.ewm(span=12).mean()
    ema26=close.ewm(span=26).mean()
    macd_hist=round((ema12-ema26-(ema12-ema26).ewm(span=9).mean()).iloc[-1],2)
    if rsi_val>50 and macd_hist>0:signal="BULLISH"
    elif rsi_val<50 and macd_hist<0:signal="BEARISH"
    else:signal="NEUTRAL"
    return {"signal":signal,"rsi":rsi_val,"macd":macd_hist}

def calculate_ema_signals(es_candles,current_price):
    """
    8/21 EMA Cross + 200 EMA Filter
    """
    result={
        "cross_signal":"NEUTRAL",
        "filter_signal":"NEUTRAL",
        "ema8":None,"ema21":None,"ema200":None,
        "cross_bullish":False,"cross_bearish":False,
        "above_200":False,"below_200":False,
        "aligned_calls":False,"aligned_puts":False
    }
    
    if es_candles is None or len(es_candles)<21:
        return result
    
    close=es_candles['Close']
    
    ema8=close.ewm(span=8).mean()
    ema21=close.ewm(span=21).mean()
    ema200=close.ewm(span=min(200,len(close))).mean()
    
    ema8_val=round(ema8.iloc[-1],2)
    ema21_val=round(ema21.iloc[-1],2)
    ema200_val=round(ema200.iloc[-1],2)
    
    result["ema8"]=ema8_val
    result["ema21"]=ema21_val
    result["ema200"]=ema200_val
    
    if ema8_val>ema21_val:
        result["cross_signal"]="BULLISH"
        result["cross_bullish"]=True
    elif ema8_val<ema21_val:
        result["cross_signal"]="BEARISH"
        result["cross_bearish"]=True
    
    if current_price and current_price>ema200_val:
        result["filter_signal"]="ABOVE_200"
        result["above_200"]=True
    elif current_price and current_price<ema200_val:
        result["filter_signal"]="BELOW_200"
        result["below_200"]=True
    
    result["aligned_calls"]=result["cross_bullish"] and result["above_200"]
    result["aligned_puts"]=result["cross_bearish"] and result["below_200"]
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# OPTION PRICING
# ═══════════════════════════════════════════════════════════════════════════════
def get_strike(entry_level,opt_type):
    if opt_type=="CALL":return int(round((entry_level+20)/5)*5)
    return int(round((entry_level-20)/5)*5)

def estimate_prices(entry_level,strike,opt_type,vix,hours):
    """
    Estimate 0DTE option premium.
    """
    iv_multiplier = 2.0 if hours < 3 else 1.8 if hours < 5 else 1.5
    iv = (vix / 100) * iv_multiplier
    iv = max(iv, 0.20)
    
    T = max(0.0001, hours / (365 * 24))
    r = 0.05
    
    entry = black_scholes(entry_level, strike, T, r, iv, opt_type)
    entry = max(entry, 0.05)
    
    return round(entry, 2)

def estimate_exit_prices(entry_level,strike,opt_type,vix,hours,targets):
    """
    Estimate exit prices at each target level.
    """
    iv_multiplier = 2.0 if hours < 3 else 1.8 if hours < 5 else 1.5
    iv = (vix / 100) * iv_multiplier
    iv = max(iv, 0.20)
    
    r = 0.05
    entry_T = max(0.0001, hours / (365 * 24))
    entry_price = black_scholes(entry_level, strike, entry_T, r, iv, opt_type)
    entry_price = max(entry_price, 0.05)
    
    results = []
    for i, tgt in enumerate(targets[:3]):
        hours_elapsed = 0.5 + (i * 0.5)
        exit_hours = max(0.1, hours - hours_elapsed)
        exit_T = max(0.0001, exit_hours / (365 * 24))
        
        exit_price = black_scholes(tgt["level"], strike, exit_T, r, iv, opt_type)
        exit_price = max(exit_price, 0.05)
        
        pct = (exit_price - entry_price) / entry_price * 100 if entry_price > 0.05 else 0
        results.append({
            "target": tgt["name"],
            "level": tgt["level"],
            "price": round(exit_price, 2),
            "pct": round(pct, 0)
        })
    
    return results, round(entry_price, 2)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_confidence(channel_type,validation,direction,ema_signals,flow,vix_zone):
    """
    Confidence scoring.
    """
    score=0
    breakdown=[]
    
    # Channel determination (+25)
    if channel_type!="UNDETERMINED":
        score+=25
        breakdown.append(("Channel","+25"))
    else:
        breakdown.append(("Channel","0"))
    
    # 8:30 validation (+25)
    if validation["status"] in ["VALID","TREND_DAY"]:
        score+=25
        breakdown.append(("8:30 Valid","+25"))
    elif validation["status"]=="INSIDE":
        score+=10
        breakdown.append(("8:30 Inside","+10"))
    else:
        breakdown.append(("8:30 Wait","0"))
    
    # 200 EMA filter (+15)
    if direction=="PUTS" and ema_signals["below_200"]:
        score+=15
        breakdown.append(("Below 200","+15"))
    elif direction=="CALLS" and ema_signals["above_200"]:
        score+=15
        breakdown.append(("Above 200","+15"))
    elif direction in ["PUTS","CALLS"]:
        breakdown.append(("200 EMA","0 ⚠️"))
    else:
        breakdown.append(("200 EMA","N/A"))
    
    # 8/21 cross (+15)
    if direction=="PUTS" and ema_signals["cross_bearish"]:
        score+=15
        breakdown.append(("8/21 Bear","+15"))
    elif direction=="CALLS" and ema_signals["cross_bullish"]:
        score+=15
        breakdown.append(("8/21 Bull","+15"))
    elif direction in ["PUTS","CALLS"]:
        breakdown.append(("8/21 Cross","0 ⚠️"))
    else:
        breakdown.append(("8/21 Cross","N/A"))
    
    # Flow bias (+10)
    if direction=="PUTS" and flow["bias"] in ["STRONG_PUTS","PUTS"]:
        score+=10
        breakdown.append(("Flow","+10"))
    elif direction=="CALLS" and flow["bias"] in ["STRONG_CALLS","CALLS"]:
        score+=10
        breakdown.append(("Flow","+10"))
    elif flow["bias"]=="NEUTRAL":
        score+=5
        breakdown.append(("Flow","+5"))
    else:
        breakdown.append(("Flow","0"))
    
    # VIX zone (+10)
    if vix_zone in ["LOW","NORMAL"]:
        score+=10
        breakdown.append(("VIX","+10"))
    elif vix_zone=="ELEVATED":
        score+=5
        breakdown.append(("VIX","+5"))
    else:
        breakdown.append(("VIX","0"))
    
    return {"score":score,"breakdown":breakdown}

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def safe_float(value,default):
    """Safely convert to float"""
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError,ValueError):
        return float(default)

def render_sidebar():
    saved=load_inputs()
    
    # Generate time options for 30-min chart (:00 and :30 only)
    time_options=[]
    for h in range(24):
        time_options.append(f"{h:02d}:00")
        time_options.append(f"{h:02d}:30")
    
    with st.sidebar:
        st.markdown("## 🔮 SPX Prophet V6.1")
        st.markdown("*Structural 0DTE Strategy*")
        
        trading_date=st.date_input("📅 Trading Date",value=date.today())
        is_historical=trading_date<date.today()
        is_future=trading_date>date.today()
        is_planning=is_future
        
        if is_historical:
            st.info(f"📜 Historical: {trading_date.strftime('%A, %b %d')}")
        elif is_planning:
            st.info(f"📋 Planning: {trading_date.strftime('%A, %b %d')}")
        
        st.markdown("---")
        
        # ES/SPX OFFSET
        default_offset = safe_float(saved.get("offset"), 18.0)
        offset = st.number_input("⚙️ ES→SPX Offset", value=default_offset, step=0.5,
                               help="SPX = ES - Offset")
        
        if offset != default_offset:
            saved["offset"] = offset
            save_inputs(saved)
        
        st.markdown("---")
        
        # MODULAR OVERRIDE SECTIONS
        st.markdown("### 📝 Manual Overrides")
        st.caption("Enable sections to override auto-fetched data")
        
        # Current ES Override
        override_es=st.checkbox("Override Current ES",value=False,key="oes")
        if override_es:
            manual_es=st.number_input("Current ES Price",value=safe_float(saved.get("manual_es"),6900.0),step=0.25,
                                      help="Enter current ES futures price")
        else:
            manual_es=None
        
        st.markdown("")
        
        # VIX Override
        override_vix=st.checkbox("Override VIX",value=False,key="ovix")
        if override_vix:
            st.markdown("**VIX Range** *(for flow bias)*")
            c1,c2=st.columns(2)
            vix_high=c1.number_input("VIX High",value=safe_float(saved.get("vix_high"),18.0),step=0.1)
            vix_low=c2.number_input("VIX Low",value=safe_float(saved.get("vix_low"),15.0),step=0.1)
            st.markdown("**Current VIX** *(for premium calculation)*")
            manual_vix=st.number_input("VIX Level",value=safe_float(saved.get("manual_vix"),16.0),step=0.1,key="mvix")
        else:
            vix_high=vix_low=None
            manual_vix=None
        
        st.markdown("")
        
        # O/N Pivots Override
        override_on=st.checkbox("Override O/N Pivots",value=False,key="oon")
        if override_on:
            st.markdown("**Overnight High**")
            c1,c2=st.columns([2,1])
            on_high=c1.number_input("O/N High (ES)",value=safe_float(saved.get("on_high"),6075.0),step=0.5,label_visibility="collapsed")
            on_high_time_str=c2.selectbox("Time",time_options,index=time_options.index("22:00") if "22:00" in time_options else 0,key="onht",label_visibility="collapsed")
            
            st.markdown("**Overnight Low**")
            c1,c2=st.columns([2,1])
            on_low=c1.number_input("O/N Low (ES)",value=safe_float(saved.get("on_low"),6040.0),step=0.5,label_visibility="collapsed")
            on_low_time_str=c2.selectbox("Time",time_options,index=time_options.index("02:00") if "02:00" in time_options else 0,key="onlt",label_visibility="collapsed")
            
            st.markdown("**Prior RTH Close**")
            on_prior_close=st.number_input("Prior Close (ES)",value=safe_float(saved.get("on_prior_close"),6040.0),step=0.5,key="onpc",label_visibility="collapsed")
            
            # Parse times
            on_high_hr,on_high_mn=int(on_high_time_str.split(":")[0]),int(on_high_time_str.split(":")[1])
            on_low_hr,on_low_mn=int(on_low_time_str.split(":")[0]),int(on_low_time_str.split(":")[1])
        else:
            on_high=on_low=on_prior_close=None
            on_high_hr=on_high_mn=on_low_hr=on_low_mn=None
        
        st.markdown("")
        
        # Prior RTH Override
        override_prior=st.checkbox("Override Prior RTH",value=False,key="oprior")
        if override_prior:
            st.markdown("**Prior High (highest wick)**")
            c1,c2=st.columns([2,1])
            prior_high=c1.number_input("Price (ES)",value=safe_float(saved.get("prior_high"),6080.0),step=0.5,key="ph",label_visibility="collapsed")
            prior_high_time_str=c2.selectbox("Time",time_options,index=time_options.index("10:00") if "10:00" in time_options else 0,key="pht",label_visibility="collapsed")
            
            st.markdown("**Prior Low (lowest close)**")
            c1,c2=st.columns([2,1])
            prior_low=c1.number_input("Price (ES)",value=safe_float(saved.get("prior_low"),6030.0),step=0.5,key="pl",label_visibility="collapsed")
            prior_low_time_str=c2.selectbox("Time",time_options,index=time_options.index("14:00") if "14:00" in time_options else 0,key="plt",label_visibility="collapsed")
            
            st.markdown("**Prior Close**")
            c1,c2=st.columns([2,1])
            prior_close=c1.number_input("Price (ES)",value=safe_float(saved.get("prior_close"),6055.0),step=0.5,key="pc",label_visibility="collapsed")
            prior_close_time_str=c2.selectbox("Time",time_options,index=time_options.index("15:00") if "15:00" in time_options else 0,key="pct",label_visibility="collapsed")
            
            # Parse times
            prior_high_hr,prior_high_mn=int(prior_high_time_str.split(":")[0]),int(prior_high_time_str.split(":")[1])
            prior_low_hr,prior_low_mn=int(prior_low_time_str.split(":")[0]),int(prior_low_time_str.split(":")[1])
            prior_close_hr,prior_close_mn=int(prior_close_time_str.split(":")[0]),int(prior_close_time_str.split(":")[1])
        else:
            prior_high=prior_low=prior_close=None
            prior_high_hr=prior_high_mn=prior_low_hr=prior_low_mn=prior_close_hr=prior_close_mn=None
        
        st.markdown("---")
        
        # REFERENCE TIME
        ref_time_sel=st.selectbox("⏰ Reference Time",["8:30 AM","9:00 AM","9:30 AM"],index=1)
        ref_map={"8:30 AM":(8,30),"9:00 AM":(9,0),"9:30 AM":(9,30)}
        ref_hr,ref_mn=ref_map[ref_time_sel]
        
        st.markdown("---")
        
        # OPTIONS
        auto_refresh=st.checkbox("🔄 Auto Refresh (30s)",value=False) if not (is_historical or is_planning) else False
        debug=st.checkbox("🔧 Debug Mode",value=False)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Inputs",use_container_width=True):
                save_inputs({
                    "offset":offset,
                    "manual_es":manual_es,
                    "on_high":on_high,"on_low":on_low,
                    "on_prior_close":on_prior_close,
                    "vix_high":vix_high,"vix_low":vix_low,
                    "manual_vix":manual_vix,
                    "prior_high":prior_high,"prior_low":prior_low,"prior_close":prior_close
                })
                st.success("✅ Saved")
        with col2:
            if st.button("🔄 Refresh Data",use_container_width=True):
                st.cache_data.clear()
                st.rerun()
    
    return {
        "trading_date":trading_date,
        "is_historical":is_historical,
        "is_planning":is_planning,
        "offset":offset,
        # ES override
        "override_es":override_es,
        "manual_es":manual_es,
        # VIX overrides
        "override_vix":override_vix,
        "vix_high":vix_high,"vix_low":vix_low,
        "manual_vix":manual_vix,
        # O/N overrides
        "override_on":override_on,
        "on_high":on_high,"on_low":on_low,
        "on_prior_close":on_prior_close if override_on else None,
        "on_high_time":(on_high_hr,on_high_mn) if override_on else None,
        "on_low_time":(on_low_hr,on_low_mn) if override_on else None,
        # Prior RTH overrides
        "override_prior":override_prior,
        "prior_high":prior_high,"prior_low":prior_low,"prior_close":prior_close,
        "prior_high_time":(prior_high_hr,prior_high_mn) if override_prior else None,
        "prior_low_time":(prior_low_hr,prior_low_mn) if override_prior else None,
        "prior_close_time":(prior_close_hr,prior_close_mn) if override_prior else None,
        # Other
        "ref_hr":ref_hr,"ref_mn":ref_mn,
        "auto_refresh":auto_refresh,"debug":debug
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(STYLES,unsafe_allow_html=True)
    inputs=render_sidebar()
    now=now_ct()
    
    # Check for future date in historical mode
    if inputs["is_historical"]:
        today = now.date()
        selected_date = inputs["trading_date"]
        if selected_date > today:
            st.error(f"⚠️ **Cannot analyze {selected_date.strftime('%A, %B %d, %Y')}** - this date hasn't occurred yet!")
            st.info("💡 Switch to **Planning Mode** to prepare for a future trading day, or select a past date for historical analysis.")
            return
        elif selected_date == today:
            market_open_time = now.replace(hour=8, minute=30, second=0, microsecond=0)
            if now < market_open_time:
                st.warning(f"⚠️ **Today's session hasn't started yet.** Market opens at 8:30 AM CT.")
                st.info("💡 Switch to **Planning Mode** to prepare for today, or wait until after market open for historical analysis.")
                return
    
    # ─────────────────────────────────────────────────────────────────────────
    # FETCH DATA WITH ROBUST SYSTEM
    # ─────────────────────────────────────────────────────────────────────────
    with st.spinner("📡 Loading market data..."):
        data_quality = "⚠️"
        
        # Get market data with retry
        market_data = get_market_data_with_retry()
        
        if market_data['success']:
            es_price = market_data['es']
            spx_price = market_data['spx']
            vix = market_data['vix']
            dynamic_offset = market_data['offset']
            data_quality = "✅"
            
            # Use dynamic offset if available, otherwise use user input
            if dynamic_offset and abs(dynamic_offset - inputs["offset"]) > 2:
                st.info(f"📊 Using dynamic offset: {dynamic_offset:.2f} (calculated from ES/SPX)")
                offset = dynamic_offset
            else:
                offset = inputs["offset"]
        else:
            # Fallback to manual overrides or defaults
            es_price = None
            spx_price = None
            vix = 16.0
            offset = inputs["offset"]
            data_quality = "❌"
            st.warning("⚠️ **Could not fetch live market data.** Using manual inputs or defaults.")
        
        # Fetch historical candles if needed
        if inputs["is_historical"] or inputs["is_planning"]:
            start=inputs["trading_date"]-timedelta(days=7)
            end=inputs["trading_date"]+timedelta(days=1)
            es_candles=fetch_es_candles_range(start, end, "30m", offset)
            
            if es_candles is not None and not es_candles.empty:
                hist_data=extract_historical_data(es_candles,inputs["trading_date"],offset)
            else:
                hist_data=None
                if inputs["is_planning"]:
                    st.warning("⚠️ Could not fetch prior RTH data. Using manual inputs.")
            
            if inputs["is_historical"]:
                es_price=hist_data.get("day_open") if hist_data else None
            else:
                # Planning mode - try to get live ES price
                live_es = robust_fetch_es_current()
                if live_es:
                    es_price = live_es
                elif hist_data:
                    es_price = hist_data.get("prior_close")
        else:
            # Live mode
            es_candles=fetch_es_candles(7, offset)
            if es_candles is not None and not es_candles.empty:
                hist_data = extract_historical_data(es_candles, inputs["trading_date"], offset)
            else:
                hist_data = None
        
        # Check if manual ES override is enabled
        if inputs.get("override_es") and inputs.get("manual_es"):
            es_price = inputs["manual_es"]
            st.success(f"✅ Using manual ES: {es_price}")
        
        # Derive SPX from ES if needed
        if es_price and not spx_price:
            spx_price = round(es_price - offset, 2)
        
        # Get put/call ratio
        pc_data = fetch_spx_put_call_ratio()
    
    # ─────────────────────────────────────────────────────────────────────────
    # DETERMINE BASE DATES
    # ─────────────────────────────────────────────────────────────────────────
    prior_rth_day=inputs["trading_date"]-timedelta(days=1)
    if prior_rth_day.weekday()==6:prior_rth_day=prior_rth_day-timedelta(days=2)
    elif prior_rth_day.weekday()==5:prior_rth_day=prior_rth_day-timedelta(days=1)
    
    overnight_day=inputs["trading_date"]-timedelta(days=1)
    
    # ─────────────────────────────────────────────────────────────────────────
    # POPULATE DATA (Auto-fetch + Modular Overrides)
    # ─────────────────────────────────────────────────────────────────────────
    if hist_data:
        syd_h=hist_data.get("sydney_high")
        syd_l=hist_data.get("sydney_low")
        tok_h=hist_data.get("tokyo_high")
        tok_l=hist_data.get("tokyo_low")
        on_high=hist_data.get("on_high")
        on_low=hist_data.get("on_low")
        on_high_time=hist_data.get("on_high_time")
        on_low_time=hist_data.get("on_low_time")
        
        prior_high_wick=hist_data.get("prior_high_wick",6080)
        prior_high_close=hist_data.get("prior_high_close",6075)
        prior_low_close=hist_data.get("prior_low_close",6030)
        prior_close=hist_data.get("prior_close",6055)
        prior_high_wick_time=hist_data.get("prior_high_wick_time")
        prior_high_close_time=hist_data.get("prior_high_close_time")
        prior_low_close_time=hist_data.get("prior_low_close_time")
        prior_close_time=hist_data.get("prior_close_time")
        
        candle_830=hist_data.get("candle_830") if hist_data else None
        current_es=hist_data.get("day_open",es_price) if inputs["is_historical"] else (es_price or (hist_data.get("prior_close",6050) if hist_data else 6050))
    else:
        syd_h=syd_l=tok_h=tok_l=on_high=on_low=None
        on_high_time=on_low_time=None
        prior_high_wick=prior_high_close=6080
        prior_low_close=6030
        prior_close=6055
        prior_high_wick_time=prior_high_close_time=prior_low_close_time=prior_close_time=None
        candle_830=None
        current_es=es_price or 6050
    
    # ─────────────────────────────────────────────────────────────────────────
    # APPLY MANUAL OVERRIDES
    # ─────────────────────────────────────────────────────────────────────────
    
    # VIX Override
    if inputs["override_vix"] and inputs["vix_high"] is not None:
        vix_high=inputs["vix_high"]
        vix_low=inputs["vix_low"]
    else:
        vix_high=18
        vix_low=15
    
    # O/N Pivots Override
    if inputs["override_on"] and inputs["on_high"] is not None:
        on_high=inputs["on_high"]
        on_low=inputs["on_low"]
        on_h_hr,on_h_mn=inputs["on_high_time"]
        on_l_hr,on_l_mn=inputs["on_low_time"]
        
        if on_h_hr>=17:
            on_high_time=CT.localize(datetime.combine(overnight_day,time(on_h_hr,on_h_mn)))
        else:
            on_high_time=CT.localize(datetime.combine(inputs["trading_date"],time(on_h_hr,on_h_mn)))
        if on_l_hr>=17:
            on_low_time=CT.localize(datetime.combine(overnight_day,time(on_l_hr,on_l_mn)))
        else:
            on_low_time=CT.localize(datetime.combine(inputs["trading_date"],time(on_l_hr,on_l_mn)))
        
        syd_h=on_high
        syd_l=on_low
        tok_h=on_high-1
        tok_l=on_low
    
    # Prior RTH Override
    if inputs["override_prior"] and inputs["prior_high"] is not None:
        prior_high_wick=inputs["prior_high"]
        prior_high_close=inputs["prior_high"]
        prior_low_close=inputs["prior_low"]
        prior_close=inputs["prior_close"]
        ph_hr,ph_mn=inputs["prior_high_time"]
        pl_hr,pl_mn=inputs["prior_low_time"]
        pc_hr,pc_mn=inputs["prior_close_time"]
        prior_high_wick_time=CT.localize(datetime.combine(prior_rth_day,time(ph_hr,ph_mn)))
        prior_high_close_time=prior_high_wick_time
        prior_low_close_time=CT.localize(datetime.combine(prior_rth_day,time(pl_hr,pl_mn)))
        prior_close_time=CT.localize(datetime.combine(prior_rth_day,time(pc_hr,pc_mn)))
    
    # on_prior_close from O/N Override takes FINAL precedence
    if inputs.get("override_on") and inputs.get("on_prior_close"):
        prior_close = inputs["on_prior_close"]
    
    # FALLBACKS
    if on_high is None:on_high=prior_high_wick or 6075
    if on_low is None:on_low=prior_low_close or 6040
    if on_high_time is None:on_high_time=CT.localize(datetime.combine(overnight_day,time(22,0)))
    if on_low_time is None:on_low_time=CT.localize(datetime.combine(inputs["trading_date"],time(2,0)))
    
    if syd_h is None:syd_h=on_high
    if syd_l is None:syd_l=on_low
    if tok_h is None:tok_h=on_high-1
    if tok_l is None:tok_l=on_low
    
    if prior_high_wick_time is None:prior_high_wick_time=CT.localize(datetime.combine(prior_rth_day,time(10,0)))
    if prior_high_close_time is None:prior_high_close_time=CT.localize(datetime.combine(prior_rth_day,time(10,0)))
    if prior_low_close_time is None:prior_low_close_time=CT.localize(datetime.combine(prior_rth_day,time(14,0)))
    if prior_close_time is None:prior_close_time=CT.localize(datetime.combine(prior_rth_day,time(15,0)))
    
    # Manual VIX override
    if inputs.get("override_vix") and inputs.get("manual_vix"):
        vix = float(inputs["manual_vix"])
        vix_source = "manual"
    else:
        vix_source = "fetched"
    
    current_spx=round(current_es-offset,2) if current_es else None
    
    # ─────────────────────────────────────────────────────────────────────────
    # CALCULATIONS
    # ─────────────────────────────────────────────────────────────────────────
    channel_type,channel_reason=determine_channel(syd_h,syd_l,tok_h,tok_l)
    
    ref_time=CT.localize(datetime.combine(inputs["trading_date"],time(inputs["ref_hr"],inputs["ref_mn"])))
    expiry_time=CT.localize(datetime.combine(inputs["trading_date"],time(15,0)))
    hours_to_expiry=6.5 if inputs["is_historical"] else max(0.1,(expiry_time-now).total_seconds()/3600)
    
    levels=calculate_channel_levels(on_high,on_high_time,on_low,on_low_time,ref_time)
    ceiling_es,floor_es,ceil_key,floor_key=get_channel_edges(levels,channel_type)
    ceiling_spx=round(ceiling_es-offset,2) if ceiling_es else None
    floor_spx=round(floor_es-offset,2) if floor_es else None
    
    cones_es=calculate_cones(prior_high_wick,prior_high_wick_time,prior_high_close,prior_high_close_time,
                             prior_low_close,prior_low_close_time,prior_close,prior_close_time,ref_time)
    cones_spx={}
    for k,v in cones_es.items():
        cones_spx[k]={
            "anchor_asc":round(v["anchor_asc"]-offset,2),
            "anchor_desc":round(v["anchor_desc"]-offset,2),
            "asc":round(v["asc"]-offset,2),
            "desc":round(v["desc"]-offset,2)
        }
    
    # Validation
    if candle_830 and ceiling_es and floor_es:
        validation=validate_830_candle(candle_830,ceiling_es,floor_es)
        position=validation.get("position","UNKNOWN")
    elif inputs.get("is_planning") and ceiling_es and floor_es and on_high and on_low:
        # PLANNING MODE: Project setup
        on_mid = (on_high + on_low) / 2
        pc = prior_close or ceiling_es
        gap_down = on_mid < pc - 20
        gap_up = on_mid > pc + 20
        
        if gap_down:
            validation = {
                "status": "PROJECTED",
                "message": f"📊 PROJECTED: Gap down inside channel - lean PUTS",
                "setup": "PUTS",
                "position": "INSIDE",
                "edge": floor_es,
                "projected": True
            }
            position = "INSIDE"
        elif gap_up:
            validation = {
                "status": "PROJECTED",
                "message": f"📊 PROJECTED: Gap up inside channel - lean CALLS",
                "setup": "CALLS",
                "position": "INSIDE",
                "edge": ceiling_es,
                "projected": True
            }
            position = "INSIDE"
        else:
            validation = {
                "status": "PROJECTED",
                "message": f"📊 PROJECTED: O/N inside channel - wait for 8:30 break",
                "setup": "NEUTRAL",
                "position": "INSIDE",
                "projected": True
            }
            position = "INSIDE"
    else:
        validation={"status":"AWAITING","message":"Waiting for data","setup":"WAIT","position":"UNKNOWN"}
        position="UNKNOWN"
    
    # Direction & targets
    is_projected = validation.get("projected", False)
    
    if validation["setup"]=="PUTS":
        direction="PUTS"
        entry_edge_es=validation.get("edge",floor_es)
        entry_edge_spx=round(entry_edge_es-offset,2) if entry_edge_es else floor_spx
        targets=find_targets(entry_edge_spx,cones_spx,"PUTS") if entry_edge_spx else []
            
    elif validation["setup"]=="CALLS":
        direction="CALLS"
        entry_edge_es=validation.get("edge",ceiling_es)
        entry_edge_spx=round(entry_edge_es-offset,2) if entry_edge_es else ceiling_spx
        targets=find_targets(entry_edge_spx,cones_spx,"CALLS") if entry_edge_spx else []
            
    elif validation["setup"]=="NEUTRAL" and is_projected:
        direction="NEUTRAL"
        entry_edge_es=None
        targets=[]
    else:
        direction="WAIT"
        entry_edge_es=None
        targets=[]
    
    is_trend_day=validation["status"]=="TREND_DAY"
    
    # Flow & momentum
    if candle_830:
        flow_price = candle_830["open"]
    elif inputs.get("is_planning") and inputs.get("override_on"):
        flow_price = (on_high + on_low) / 2
    else:
        flow_price = current_es
    
    flow=calculate_flow_bias(flow_price,on_high,on_low,vix,vix_high,vix_low,prior_close)
    momentum=calculate_momentum(es_candles)
    ema_signals=calculate_ema_signals(es_candles,current_es)
    vix_zone=get_vix_zone(vix)
    
    # EMA CONFLICT CHECK
    ema_favors_calls = ema_signals.get("aligned_calls", False) or ema_signals.get("cross") == "BULLISH"
    ema_favors_puts = ema_signals.get("aligned_puts", False) or ema_signals.get("cross") == "BEARISH"
    
    if is_projected and direction in ["CALLS", "PUTS"]:
        if direction == "CALLS" and ema_favors_puts and not ema_favors_calls:
            original_direction = direction
            direction = "NEUTRAL"
            validation["original_setup"] = original_direction
            validation["setup"] = "NEUTRAL"
            validation["message"] = f"⚠️ CONFLICT: Structure suggests CALLS but EMA favors PUTS"
            validation["conflict"] = True
        elif direction == "PUTS" and ema_favors_calls and not ema_favors_puts:
            original_direction = direction
            direction = "NEUTRAL"
            validation["original_setup"] = original_direction
            validation["setup"] = "NEUTRAL"
            validation["message"] = f"⚠️ CONFLICT: Structure suggests PUTS but EMA favors CALLS"
            validation["conflict"] = True
    
    confidence=calculate_confidence(channel_type,validation,direction,ema_signals,flow,vix_zone)
    
    # Scenario Analysis - NEW
    scenarios = analyze_all_scenarios(current_es, ceiling_es, floor_es, cones_spx, vix, hours_to_expiry, offset, channel_type)
    
    # Historical outcome
    if inputs["is_historical"] and hist_data and entry_edge_es:
        outcome=analyze_historical_outcome(hist_data,validation,ceiling_es,floor_es,targets,direction,entry_edge_es,offset)
    else:
        outcome=None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BRAND HEADER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(f'''<div class="brand-header">
<div class="brand-logo-box">
<svg viewBox="0 0 40 40">
<path d="M20 4 L36 34 L4 34 Z" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="11" y1="34" x2="11" y2="22" stroke-width="2.5" stroke-linecap="round"/>
<line x1="20" y1="34" x2="20" y2="14" stroke-width="2.5" stroke-linecap="round"/>
<line x1="29" y1="34" x2="29" y2="22" stroke-width="2.5" stroke-linecap="round"/>
<circle cx="20" cy="11" r="3.5" fill="#0a0a0a" stroke-width="1.5"/>
<circle cx="20" cy="11" r="1.5" fill="#0a0a0a" stroke-width="2"/>
<line x1="11" y1="22" x2="29" y2="22" stroke-width="1.5" stroke-linecap="round" opacity="0.6"/>
</svg>
</div>
<h1 class="brand-name"><span>SPX</span> <span>Prophet</span></h1>
<div class="brand-tagline">Three Pillars. One Vision. Total Clarity.</div>
<div class="brand-live"><span>STRUCTURE-BASED 0DTE FORECASTING • Data: {data_quality}</span></div>
</div>''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PUT/CALL RATIO DISPLAY - NEW SECTION
    # ═══════════════════════════════════════════════════════════════════════════
    if pc_data and pc_data.get("ratio"):
        pc_ratio = pc_data["ratio"]
        pc_interpretation = pc_data.get("interpretation", "")
        pc_source = pc_data.get("source", "")
        
        # Determine color based on ratio
        if pc_ratio > 1.2:
            pc_color = "var(--green)"  # Contrarian bullish
            pc_icon = "📈"
        elif pc_ratio > 0.9:
            pc_color = "var(--amber)"
            pc_icon = "⚖️"
        else:
            pc_color = "var(--red)"  # Contrarian bearish
            pc_icon = "📉"
        
        st.markdown(f'''
        <div style="background: linear-gradient(145deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%); 
                    border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 16px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 44px; height: 44px; background: rgba(168,85,247,0.15); border-radius: 12px; 
                                display: flex; align-items: center; justify-content: center; font-size: 20px;">
                        {pc_icon}
                    </div>
                    <div>
                        <div style="font-size: 14px; font-weight: 600; color: var(--text-white);">SPX Put/Call Ratio</div>
                        <div style="font-size: 11px; color: var(--text-muted);">{pc_source} • Retail Sentiment Indicator</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 32px; font-weight: 700; color: {pc_color};">
                        {pc_ratio:.2f}
                    </div>
                    <div style="font-size: 11px; color: {pc_color}; font-weight: 600;">{pc_interpretation}</div>
                </div>
            </div>
            <div style="margin-top: 12px; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted);">
                    <span>Puts Volume: {pc_data.get('put_volume', 'N/A'):,}</span>
                    <span>Calls Volume: {pc_data.get('call_volume', 'N/A'):,}</span>
                </div>
                <div style="margin-top: 8px; font-size: 10px; color: var(--text-dim);">
                    <strong>Interpretation:</strong> Ratio > 1.2 = Excessive fear (contrarian bullish) • Ratio < 0.7 = Complacency (contrarian bearish)
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MEGA STATUS BANNER
    # ═══════════════════════════════════════════════════════════════════════════
    
    if inputs["is_historical"]:
        status_class = "mega-status hist"
        status_icon = "📜"
        status_title = "HISTORICAL ANALYSIS"
        status_sub = f"Reviewing {inputs['trading_date'].strftime('%A, %B %d, %Y')}"
    elif inputs["is_planning"] and is_projected:
        if direction == "PUTS":
            status_class = "mega-status go"
            status_icon = "▼"
            status_title = "PROJECTED PUTS"
            status_sub = validation["message"]
        elif direction == "CALLS":
            status_class = "mega-status go"
            status_icon = "▲"
            status_title = "PROJECTED CALLS"
            status_sub = validation["message"]
        elif direction == "NEUTRAL":
            status_class = "mega-status wait"
            status_icon = "⚖️"
            status_title = "NEUTRAL - WATCH BOTH"
            status_sub = "O/N inside channel - direction at 8:30"
        else:
            status_class = "mega-status hist"
            status_icon = "📋"
            status_title = "PLANNING MODE"
            status_sub = f"Preparing for {inputs['trading_date'].strftime('%A, %B %d, %Y')}"
    elif inputs["is_planning"]:
        status_class = "mega-status hist"
        status_icon = "📋"
        status_title = "PLANNING MODE"
        status_sub = f"Preparing for {inputs['trading_date'].strftime('%A, %B %d, %Y')}"
    elif validation["setup"] == "PUTS":
        status_class = "mega-status go"
        status_icon = "▼"
        status_title = "PUTS SETUP"
        status_sub = validation["message"]
    elif validation["setup"] == "CALLS":
        status_class = "mega-status go"
        status_icon = "▲"
        status_title = "CALLS SETUP"
        status_sub = validation["message"]
    elif validation["status"] == "INSIDE":
        status_class = "mega-status wait"
        status_icon = "⏸"
        status_title = "WAITING"
        status_sub = "8:30 candle inside channel - awaiting break"
    elif validation["status"] == "AWAITING":
        status_class = "mega-status wait"
        status_icon = "⏳"
        status_title = "AWAITING 8:30"
        status_sub = "Market not yet open"
    else:
        status_class = "mega-status stop"
        status_icon = "—"
        status_title = "NO TRADE"
        status_sub = validation.get("message", "Setup conditions not met")
    
    st.markdown(f'''<div class="{status_class}">
<div class="mega-left">
<div class="mega-icon">{status_icon}</div>
<div>
<div class="mega-title">{status_title}</div>
<div class="mega-sub">{status_sub}</div>
</div>
</div>
<div class="mega-right">
<div class="mega-price">{current_spx:,.2f}</div>
<div class="mega-meta">SPX • ES {current_es:,.2f} • {channel_type}</div>
</div>
</div>''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO ANALYSIS - NEW SECTION
    # ═══════════════════════════════════════════════════════════════════════════
    if scenarios and (inputs["is_planning"] or validation["status"] in ["INSIDE", "AWAITING"]):
        st.markdown("### 🎯 Scenario Analysis")
        
        scenario_html = '''<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">'''
        
        for scenario_key, scenario in scenarios.items():
            if scenario_key == "INSIDE_CHANNEL":
                scenario_html += f'''
                <div style="grid-column: span 2; background: linear-gradient(145deg, rgba(251,191,36,0.08) 0%, rgba(251,191,36,0.03) 100%); 
                            border: 1px solid rgba(251,191,36,0.3); border-radius: 16px; padding: 20px;">
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                        <div style="width: 44px; height: 44px; background: rgba(251,191,36,0.15); border-radius: 12px; 
                                    display: flex; align-items: center; justify-content: center; font-size: 20px;">⚖️</div>
                        <div>
                            <div style="font-size: 16px; font-weight: 700; color: var(--amber);">Inside Channel</div>
                            <div style="font-size: 12px; color: rgba(255,255,255,0.6);">{scenario['position']} • Width: {scenario['channel_width']} pts</div>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px;">
                        <div style="text-align: center; padding: 12px; background: rgba(0,255,136,0.05); border-radius: 10px;">
                            <div style="font-size: 11px; color: rgba(255,255,255,0.5);">CALLS Probability</div>
                            <div style="font-size: 24px; font-weight: 700; color: var(--green);">{scenario['calls_probability']*100:.0f}%</div>
                        </div>
                        <div style="text-align: center; padding: 12px; background: rgba(255,71,87,0.05); border-radius: 10px;">
                            <div style="font-size: 11px; color: rgba(255,255,255,0.5);">PUTS Probability</div>
                            <div style="font-size: 24px; font-weight: 700; color: var(--red);">{scenario['puts_probability']*100:.0f}%</div>
                        </div>
                    </div>
                    <div style="margin-top: 12px; font-size: 12px; color: var(--amber); font-weight: 500;">{scenario['recommendation']}</div>
                </div>'''
            else:
                scenario_color = "var(--green)" if "CALLS" in scenario_key else "var(--red)"
                scenario_bg = "rgba(0,255,136,0.05)" if "CALLS" in scenario_key else "rgba(255,71,87,0.05)"
                scenario_icon = "▲" if "CALLS" in scenario_key else "▼"
                
                scenario_html += f'''
                <div style="background: linear-gradient(145deg, {scenario_bg} 0%, rgba(255,255,255,0.01) 100%); 
                            border: 1px solid {scenario_color}30; border-radius: 16px; padding: 20px;">
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                        <div style="width: 44px; height: 44px; background: {scenario_color}15; border-radius: 12px; 
                                    display: flex; align-items: center; justify-content: center; font-size: 20px; color: {scenario_color};">
                            {scenario_icon}
                        </div>
                        <div>
                            <div style="font-size: 16px; font-weight: 700; color: {scenario_color};">{scenario['direction']} Setup</div>
                            <div style="font-size: 11px; color: rgba(255,255,255,0.6);">Probability: {scenario['probability']*100:.0f}%</div>
                        </div>
                    </div>
                    <div style="font-size: 12px; color: rgba(255,255,255,0.7); margin-bottom: 12px;">{scenario['trigger']}</div>
                    <div style="background: rgba(255,255,255,0.02); border-radius: 10px; padding: 12px; margin-top: 12px;">
                        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 8px;">
                            <span style="color: rgba(255,255,255,0.5);">Entry Level</span>
                            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">{scenario['entry_level_spx']}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 8px;">
                            <span style="color: rgba(255,255,255,0.5);">Strike</span>
                            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600; color: {scenario_color};">{scenario['strike']}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 11px;">
                            <span style="color: rgba(255,255,255,0.5);">Est. Premium</span>
                            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">${scenario['premium']:.2f}</span>
                        </div>
                    </div>
                </div>'''
        
        scenario_html += "</div>"
        st.markdown(scenario_html, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VALIDATION GRID
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Channel validation
    if channel_type in ["RISING", "FALLING"]:
        ch_status = "pass"
        ch_icon = "✓"
        ch_val = channel_type
    else:
        ch_status = "neutral"
        ch_icon = "?"
        ch_val = "UNDETERMINED"
    
    # 8:30 Break validation
    if validation["status"] in ["VALID", "TREND_DAY"]:
        break_status = "pass"
        break_icon = "✓"
        break_val = validation["status"]
    elif validation["status"] == "INSIDE":
        break_status = "neutral"
        break_icon = "—"
        break_val = "INSIDE"
    else:
        break_status = "fail"
        break_icon = "✗"
        break_val = "NO BREAK"
    
    # EMA validation
    ema8_val = ema_signals.get("ema8", "—")
    ema21_val = ema_signals.get("ema21", "—")
    ema200_val = ema_signals.get("ema200", "—")
    if direction == "CALLS" and ema_signals.get("aligned_calls"):
        ema_status = "pass"
        ema_icon = "✓"
        ema_val = f"BULL ({ema_signals.get('cross_signal', '')})"
    elif direction == "PUTS" and ema_signals.get("aligned_puts"):
        ema_status = "pass"
        ema_icon = "✓"
        ema_val = f"BEAR ({ema_signals.get('cross_signal', '')})"
    elif direction in ["CALLS", "PUTS"]:
        ema_status = "fail"
        ema_icon = "✗"
        ema_val = f"CONFLICT"
    else:
        ema_status = "neutral"
        ema_icon = "—"
        ema_val = ema_signals.get("cross_signal", "N/A")
    
    # Flow validation
    flow_score = flow.get("score", 0)
    flow_bias = flow.get("bias", "NEUTRAL")
    if direction == "CALLS" and "CALLS" in flow_bias:
        flow_status = "pass"
        flow_icon = "✓"
        flow_val = f"+{flow_score}"
    elif direction == "PUTS" and "PUTS" in flow_bias:
        flow_status = "pass"
        flow_icon = "✓"
        flow_val = f"{flow_score}"
    elif flow_bias == "NEUTRAL":
        flow_status = "neutral"
        flow_icon = "—"
        flow_val = f"{flow_score}"
    elif direction in ["CALLS", "PUTS"]:
        flow_status = "fail"
        flow_icon = "✗"
        flow_val = f"{flow_score}"
    else:
        flow_status = "neutral"
        flow_icon = "—"
        flow_val = f"{flow_score}"
    
    # VIX validation
    if vix_zone in ["LOW", "NORMAL"]:
        vix_status = "pass"
        vix_icon = "✓"
        vix_val = f"{vix:.1f}"
    elif vix_zone == "ELEVATED":
        vix_status = "neutral"
        vix_icon = "—"
        vix_val = f"{vix:.1f}"
    else:
        vix_status = "fail"
        vix_icon = "✗"
        vix_val = f"{vix:.1f}"
    
    st.markdown(f'''<div class="valid-row">
<div class="valid-card {ch_status}">
<div class="valid-icon">{ch_icon}</div>
<div class="valid-label">Channel</div>
<div class="valid-val">{ch_val}</div>
</div>
<div class="valid-card {break_status}">
<div class="valid-icon">{break_icon}</div>
<div class="valid-label">8:30 Break</div>
<div class="valid-val">{break_val}</div>
</div>
<div class="valid-card {ema_status}">
<div class="valid-icon">{ema_icon}</div>
<div class="valid-label">EMA</div>
<div class="valid-val">{ema_val}</div>
</div>
<div class="valid-card {flow_status}">
<div class="valid-icon">{flow_icon}</div>
<div class="valid-label">Flow</div>
<div class="valid-val">{flow_val}</div>
</div>
<div class="valid-card {vix_status}">
<div class="valid-icon">{vix_icon}</div>
<div class="valid-label">VIX</div>
<div class="valid-val">{vix_val}</div>
</div>
</div>''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORICAL OUTCOME CARD
    # ═══════════════════════════════════════════════════════════════════════════
    if outcome:
        if outcome["outcome"]=="WIN":
            box_class="win"
            icon="✅"
        elif outcome["outcome"]=="LOSS":
            box_class="loss"
            icon="❌"
        elif outcome["outcome"]=="MOMENTUM_PROBE":
            box_class="neutral"
            icon="⚡"
        else:
            box_class="neutral"
            icon="⚠️"
        
        timeline_html=""
        for evt in outcome.get("timeline",[]):
            dot_class="hit" if "TARGET" in evt["event"] else "active"
            timeline_html+=f'<div class="timeline-item"><div class="timeline-dot {dot_class}"></div><div style="font-size:12px"><span style="color:rgba(255,255,255,0.5)">{evt["time"]}</span> <span style="font-weight:600">{evt["event"]}</span> @ {evt["price"]:.2f}</div></div>'
        
        targets_hit_str=", ".join([f"{t['name']} @ {t['time']}" for t in outcome.get("targets_hit",[])]) or "None"
        
        entry_conf=outcome.get("entry_confirmation",{})
        if entry_conf.get("confirmed"):
            setup_time = entry_conf.get("setup_time", "")
            entry_time = entry_conf.get("entry_time", entry_conf.get("time", ""))
            entry_conf_html=f'''<div style="background:rgba(0,212,170,0.1);border:1px solid rgba(0,212,170,0.3);border-radius:10px;padding:12px;margin-bottom:12px">
<div style="font-size:12px;font-weight:600;color:#00d4aa;margin-bottom:6px">✅ {setup_time} Setup → {entry_time} Entry</div>
<div style="font-size:11px;color:rgba(255,255,255,0.7)">{entry_conf.get("candle_color","")} rejection — {entry_conf.get("detail","")}</div>
</div>'''
        elif outcome["outcome"]=="MOMENTUM_PROBE":
            setup_time = entry_conf.get("setup_time", entry_conf.get("time", ""))
            entry_conf_html=f'''<div style="background:rgba(255,71,87,0.1);border:1px solid rgba(255,71,87,0.3);border-radius:10px;padding:12px;margin-bottom:12px">
<div style="font-size:12px;font-weight:600;color:#ff4757;margin-bottom:4px">⚡ Momentum Probe @ {setup_time}</div>
<div style="font-size:11px;color:rgba(255,255,255,0.7)">{entry_conf.get("detail","Broke through by >6 pts - next candle continued in breakout direction")}</div>
<div style="font-size:10px;color:#ff4757;margin-top:6px;font-weight:500">❌ NO ENTRY - Fade would have failed</div>
</div>'''
        elif outcome["outcome"]=="NO_ENTRY":
            entry_conf_html=f'''<div style="background:rgba(255,165,2,0.1);border:1px solid rgba(255,165,2,0.3);border-radius:10px;padding:12px;margin-bottom:12px">
<div style="font-size:12px;font-weight:600;color:#ffa502;margin-bottom:4px">⚠️ No Setup Found</div>
<div style="font-size:11px;color:rgba(255,255,255,0.7)">{entry_conf.get("message","No valid setup candle found by 10:30 AM")}</div>
</div>'''
        else:
            entry_conf_html=""
        
        st.markdown(f'''<div class="result-box {box_class}">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
<div style="font-size:18px;font-weight:700">{icon} HISTORICAL RESULT</div>
<div style="font-size:14px;font-weight:600">{outcome["outcome"].replace("_"," ")}</div>
</div>
<div style="font-size:14px;margin-bottom:12px">{outcome["message"]}</div>
{entry_conf_html}
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px">
<div style="text-align:center"><div style="font-size:10px;color:rgba(255,255,255,0.5)">Direction</div><div style="font-weight:600">{outcome["direction"]}</div></div>
<div style="text-align:center"><div style="font-size:10px;color:rgba(255,255,255,0.5)">Entry Level</div><div style="font-weight:600">{outcome.get("entry_level_at_time", outcome["entry_level_spx"])}</div></div>
<div style="text-align:center"><div style="font-size:10px;color:rgba(255,255,255,0.5)">Max Favorable</div><div style="font-weight:600;color:#00d4aa">+{outcome["max_favorable"]:.1f}</div></div>
<div style="text-align:center"><div style="font-size:10px;color:rgba(255,255,255,0.5)">Max Adverse</div><div style="font-weight:600;color:#ff4757">-{outcome["max_adverse"]:.1f}</div></div>
</div>
<div style="font-size:12px;color:rgba(255,255,255,0.6)"><strong>Targets Hit:</strong> {targets_hit_str}</div>
{f'<div class="timeline" style="margin-top:12px">{timeline_html}</div>' if timeline_html else ""}
</div>''',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SESSION CARDS
    # ═══════════════════════════════════════════════════════════════════════════
    if inputs["is_historical"] and hist_data:
        st.markdown("### 📊 Session Data")
        
        lon_h=hist_data.get("london_high","—")
        lon_l=hist_data.get("london_low","—")
        
        session_html=f'''<div class="session-row">
<div class="session-card sydney">
<div class="session-head">
<div class="session-icon">🌏</div>
<div class="session-info">
<div class="session-name">Sydney</div>
<div class="session-time">5:00 PM - 8:30 PM CT</div>
</div>
</div>
<div class="session-data">
<div class="session-line"><span class="session-label">High</span><span class="session-value high">{syd_h}</span></div>
<div class="session-line"><span class="session-label">Low</span><span class="session-value low">{syd_l}</span></div>
</div>
</div>

<div class="session-card tokyo">
<div class="session-head">
<div class="session-icon">🗼</div>
<div class="session-info">
<div class="session-name">Tokyo</div>
<div class="session-time">9:00 PM - 1:30 AM CT</div>
</div>
</div>
<div class="session-data">
<div class="session-line"><span class="session-label">High</span><span class="session-value high">{tok_h}</span></div>
<div class="session-line"><span class="session-label">Low</span><span class="session-value low">{tok_l}</span></div>
</div>
</div>

<div class="session-card london">
<div class="session-head">
<div class="session-icon">🏛️</div>
<div class="session-info">
<div class="session-name">London</div>
<div class="session-time">2:00 AM - 3:00 AM CT</div>
</div>
</div>
<div class="session-data">
<div class="session-line"><span class="session-label">High</span><span class="session-value high">{lon_h}</span></div>
<div class="session-line"><span class="session-label">Low</span><span class="session-value low">{lon_l}</span></div>
</div>
</div>

<div class="session-card overnight">
<div class="session-head">
<div class="session-icon">🌙</div>
<div class="session-info">
<div class="session-name">Overnight</div>
<div class="session-time">5:00 PM - 3:00 AM CT</div>
</div>
</div>
<div class="session-data">
<div class="session-line"><span class="session-label">High</span><span class="session-value high">{on_high}</span></div>
<div class="session-line"><span class="session-label">Low</span><span class="session-value low">{on_low}</span></div>
</div>
</div>
</div>'''
        
        st.markdown(session_html,unsafe_allow_html=True)
        
        # 8:30 Candle Card
        if candle_830:
            c=candle_830
            candle_color="bullish" if c["close"]>=c["open"] else "bearish"
            candle_type="BULLISH" if c["close"]>=c["open"] else "BEARISH"
            st.markdown(f'''<div class="candle-card">
<div class="candle-header">
<div class="candle-info">
<div class="candle-icon">🕣</div>
<div>
<div class="candle-title">8:30 AM Candle (ES)</div>
<div class="candle-subtitle">First 30-minute candle of RTH</div>
</div>
</div>
<div class="candle-type {candle_color}">{candle_type}</div>
</div>
<div class="candle-grid">
<div class="candle-item"><div class="candle-label">Open</div><div class="candle-value">{c["open"]:.2f}</div></div>
<div class="candle-item"><div class="candle-label">High</div><div class="candle-value high">{c["high"]:.2f}</div></div>
<div class="candle-item"><div class="candle-label">Low</div><div class="candle-value low">{c["low"]:.2f}</div></div>
<div class="candle-item"><div class="candle-label">Close</div><div class="candle-value">{c["close"]:.2f}</div></div>
</div>
</div>''',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRADE COMMAND CENTER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🎯 Trade Command Center")
    
    ch_badge_class = "rising" if channel_type == "RISING" else "falling"
    ch_icon = "▲" if channel_type == "RISING" else "▼"
    
    # Start building the command card HTML
    cmd_html = f'''<div class="cmd-card">
<div class="cmd-header">
<div>
<div class="cmd-title">{"📜 Historical " if inputs["is_historical"] else ""}Trading Plan</div>
<div class="cmd-subtitle">{channel_reason}</div>
</div>
<div class="cmd-badge {ch_badge_class}">{ch_icon} {channel_type}</div>
</div>
<div class="cmd-body">
<div class="channel-grid">
<div class="channel-item ceiling">
<div class="channel-label">Ceiling ({ceil_key or "N/A"})</div>
<div class="channel-value">{ceiling_spx or "—"}</div>
<div class="channel-es">ES {ceiling_es or "—"}</div>
</div>
<div class="channel-item floor">
<div class="channel-label">Floor ({floor_key or "N/A"})</div>
<div class="channel-value">{floor_spx or "—"}</div>
<div class="channel-es">ES {floor_es or "—"}</div>
</div>
</div>'''
    
    # Add trade setup if we have a direction
    if direction in ["PUTS", "CALLS"]:
        if entry_edge_es is None and is_projected:
            entry_edge_es = floor_es if direction == "PUTS" else ceiling_es
            
        if entry_edge_es:
            entry_spx = round(entry_edge_es - offset, 2)
            strike = get_strike(entry_spx, "PUT" if direction == "PUTS" else "CALL")
            entry_price = estimate_prices(entry_spx, strike, "PUT" if direction == "PUTS" else "CALL", vix, hours_to_expiry)
            
            if not targets:
                targets = find_targets(entry_spx, cones_spx, direction) if entry_spx else []
            exits, _ = estimate_exit_prices(entry_spx, strike, "PUT" if direction == "PUTS" else "CALL", vix, hours_to_expiry, targets)
            
            setup_class = "puts" if direction == "PUTS" else "calls"
            setup_icon = "▼" if direction == "PUTS" else "▲"
            
            if is_projected:
                setup_label = f"PROJECTED {direction}"
                setup_status = "📊 PLANNING MODE"
            else:
                setup_label = f"{direction} SETUP"
                setup_status = "✅ CONFIRMED"
            
            if direction == "PUTS":
                entry_rule = "BULLISH candle touches entry level, then closes BELOW it"
                rule_warning = "If candle breaks >6 pts ABOVE entry but closes below → NO ENTRY (momentum probe)"
            else:
                entry_rule = "BEARISH candle touches entry level, then closes ABOVE it"
                rule_warning = "If candle breaks >6 pts BELOW entry but closes above → NO ENTRY (momentum probe)"
            
            # Build targets HTML
            targets_html = ""
            for i, t in enumerate(exits):
                targets_html += f'''<div class="target-row">
<span class="target-name">{t["target"]}</span>
<span class="target-level">@ {t["level"]}</span>
<span class="target-price">${t["price"]} ({t["pct"]:+.0f}%)</span>
</div>'''
            
            projected_badge = f'<div style="font-size:10px;color:var(--amber);margin-top:4px;font-weight:600">{setup_status}</div>' if is_projected else ''
            
            cmd_html += f'''
<div class="setup-box {setup_class}">
<div class="setup-header">
<div class="setup-icon">{setup_icon}</div>
<div>
<div class="setup-title">{setup_label}</div>
{projected_badge}
</div>
</div>
<div class="setup-metrics">
<div class="setup-metric">
<div class="setup-metric-label">Entry Window</div>
<div class="setup-metric-value">8:30 - 11:00</div>
</div>
<div class="setup-metric">
<div class="setup-metric-label">Entry Level</div>
<div class="setup-metric-value">{entry_spx}</div>
</div>
<div class="setup-metric">
<div class="setup-metric-label">Strike</div>
<div class="setup-metric-value">{strike}</div>
</div>
<div class="setup-metric">
<div class="setup-metric-label">Est. Premium</div>
<div class="setup-metric-value">${entry_price:.2f}</div>
</div>
</div>
<div class="entry-rule">
<div class="entry-rule-title">📋 Entry Confirmation {"(Projected)" if is_projected else ""}</div>
<div class="entry-rule-text">{entry_rule}</div>
<div class="entry-rule-warning">⚠️ {rule_warning}</div>
</div>
<div class="targets-box">
<div class="targets-title">📍 Profit Targets</div>
{targets_html if targets_html else '<div style="color:var(--text-muted)">No targets in range</div>'}
</div>
</div>'''
        else:
            cmd_html += '''
<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:32px;text-align:center;margin-top:20px">
<div style="font-size:48px;margin-bottom:16px;opacity:0.3">⚠️</div>
<div style="font-size:18px;font-weight:600;color:rgba(255,255,255,0.4);margin-bottom:8px">Setup Incomplete</div>
<div style="font-size:13px;color:rgba(255,255,255,0.3)">Missing entry edge data</div>
</div>'''
    elif direction == "NEUTRAL" and is_projected:
        # Neutral in planning mode
        ema_info = ""
        if ema_signals.get("aligned_puts") or ema_signals.get("cross") == "BEARISH":
            ema_info = "EMA favors PUTS (bearish cross, below 200)"
        elif ema_signals.get("aligned_calls") or ema_signals.get("cross") == "BULLISH":
            ema_info = "EMA favors CALLS (bullish cross, above 200)"
        
        conflict_msg = validation.get("message", "O/N trading inside channel")
        
        # Calculate strikes and premiums for both setups
        puts_strike = get_strike(floor_spx, "PUT") if floor_spx else 0
        puts_premium = estimate_prices(floor_spx, puts_strike, "PUT", vix, hours_to_expiry) if floor_spx else 0
        
        calls_strike = get_strike(ceiling_spx, "CALL") if ceiling_spx else 0
        calls_premium = estimate_prices(ceiling_spx, calls_strike, "CALL", vix, hours_to_expiry) if ceiling_spx else 0
        
        cmd_html += f'''
<div style="margin-top:16px">
<div style="background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.4);border-radius:16px;padding:20px;margin-bottom:16px">
<div style="font-size:16px;color:var(--amber);font-weight:700;margin-bottom:10px">⚠️ CONFLICTING SIGNALS - WATCH BOTH SETUPS</div>
<div style="font-size:13px;color:rgba(255,255,255,0.7);margin-bottom:8px">{conflict_msg}</div>
<div style="font-size:12px;color:rgba(255,255,255,0.5)">{ema_info}</div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
<div style="background:linear-gradient(145deg, rgba(255,71,87,0.1), rgba(255,71,87,0.05));border:1px solid rgba(255,71,87,0.4);border-radius:16px;padding:20px">
<div style="font-size:18px;font-weight:800;color:var(--red);margin-bottom:12px">▼ PUTS SETUP</div>
<div style="font-size:13px;color:rgba(255,255,255,0.6);margin-bottom:12px">If 8:30 breaks below floor</div>
<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,0.1)">
<span style="color:rgba(255,255,255,0.5)">Entry Level</span>
<span style="font-family:monospace;font-weight:600">{floor_spx}</span>
</div>
<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,0.1)">
<span style="color:rgba(255,255,255,0.5)">Strike</span>
<span style="font-family:monospace;font-weight:600;color:var(--red)">{puts_strike}</span>
</div>
<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,0.1)">
<span style="color:rgba(255,255,255,0.5)">Est. Premium</span>
<span style="font-family:monospace;font-weight:600">${puts_premium:.2f}</span>
</div>
<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,0.1)">
<span style="color:rgba(255,255,255,0.5)">EMA Aligned?</span>
<span style="color:{'var(--green)' if ema_signals.get('aligned_puts') else 'var(--red)'};font-weight:600">{'✓ YES' if ema_signals.get('aligned_puts') else '✗ NO'}</span>
</div>
</div>
<div style="background:linear-gradient(145deg, rgba(0,255,136,0.1), rgba(0,255,136,0.05));border:1px solid rgba(0,255,136,0.4);border-radius:16px;padding:20px">
<div style="font-size:18px;font-weight:800;color:var(--green);margin-bottom:12px">▲ CALLS SETUP</div>
<div style="font-size:13px;color:rgba(255,255,255,0.6);margin-bottom:12px">If 8:30 breaks above ceiling</div>
<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,0.1)">
<span style="color:rgba(255,255,255,0.5)">Entry Level</span>
<span style="font-family:monospace;font-weight:600">{ceiling_spx}</span>
</div>
<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,0.1)">
<span style="color:rgba(255,255,255,0.5)">Strike</span>
<span style="font-family:monospace;font-weight:600;color:var(--green)">{calls_strike}</span>
</div>
<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,0.1)">
<span style="color:rgba(255,255,255,0.5)">Est. Premium</span>
<span style="font-family:monospace;font-weight:600">${calls_premium:.2f}</span>
</div>
<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,0.1)">
<span style="color:rgba(255,255,255,0.5)">EMA Aligned?</span>
<span style="color:{'var(--green)' if ema_signals.get('aligned_calls') else 'var(--red)'};font-weight:600">{'✓ YES' if ema_signals.get('aligned_calls') else '✗ NO'}</span>
</div>
</div>
</div>
</div>'''
    else:
        # No active setup
        cmd_html += '''
<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:32px;text-align:center;margin-top:20px">
<div style="font-size:48px;margin-bottom:16px;opacity:0.3">⏸</div>
<div style="font-size:18px;font-weight:600;color:rgba(255,255,255,0.4);margin-bottom:8px">No Active Setup</div>
<div style="font-size:13px;color:rgba(255,255,255,0.3)">Waiting for market data to determine setup</div>
</div>'''
    
    cmd_html += "</div></div>"
    st.markdown(cmd_html, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYSIS GRID
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### 📊 Analysis")
    
    # Calculate values for analysis cards
    conf_score=confidence["score"]
    conf_color="#00d4aa" if conf_score>=70 else "#ffa502" if conf_score>=50 else "#ff4757"
    conf_label="HIGH" if conf_score>=70 else "MEDIUM" if conf_score>=50 else "LOW"
    breakdown_html="".join([f'<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.04)"><span style="color:rgba(255,255,255,0.5)">{k}</span><span style="font-weight:500">{v}</span></div>' for k,v in confidence["breakdown"]])
    
    cross_color="#00d4aa" if ema_signals["cross_bullish"] else "#ff4757" if ema_signals["cross_bearish"] else "#ffa502"
    filter_color="#00d4aa" if ema_signals["above_200"] else "#ff4757" if ema_signals["below_200"] else "#ffa502"
    filter_text="ABOVE" if ema_signals["above_200"] else "BELOW" if ema_signals["below_200"] else "AT"
    
    # Determine EMA alignment status
    if direction=="CALLS" and ema_signals["aligned_calls"]:
        align_text="✅ ALIGNED FOR CALLS";align_color="#00d4aa";align_bg="rgba(0,212,170,0.12)"
    elif direction=="PUTS" and ema_signals["aligned_puts"]:
        align_text="✅ ALIGNED FOR PUTS";align_color="#ff4757";align_bg="rgba(255,71,87,0.12)"
    elif direction in ["CALLS","PUTS"]:
        align_text="⚠️ CONFLICT";align_color="#ffa502";align_bg="rgba(255,165,2,0.12)"
    elif ema_signals["aligned_calls"]:
        align_text="📈 FAVORS CALLS";align_color="#00d4aa";align_bg="rgba(0,212,170,0.08)"
    elif ema_signals["aligned_puts"]:
        align_text="📉 FAVORS PUTS";align_color="#ff4757";align_bg="rgba(255,71,87,0.08)"
    elif ema_signals["cross_bullish"]:
        align_text="📈 LEANS CALLS";align_color="#00d4aa";align_bg="rgba(0,212,170,0.05)"
    elif ema_signals["cross_bearish"]:
        align_text="📉 LEANS PUTS";align_color="#ff4757";align_bg="rgba(255,71,87,0.05)"
    else:
        align_text="— NEUTRAL";align_color="#666";align_bg="rgba(255,255,255,0.03)"
    
    flow_color="#00d4aa" if "CALLS" in flow["bias"] else "#ff4757" if "PUTS" in flow["bias"] else "#ffa502"
    meter_pos=(flow["score"]+100)/2
    flow_label=flow["bias"].replace("_"," ")
    
    # Build flow signals breakdown HTML
    flow_signals_html = ""
    for sig in flow.get("signals", []):
        if len(sig) >= 4:
            name, direction_sig, detail, pts = sig
            sig_color = "#00d4aa" if pts > 0 else "#ff4757" if pts < 0 else "#666"
            pts_str = f"+{pts}" if pts > 0 else str(pts)
            flow_signals_html += f'<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:11px;border-bottom:1px solid rgba(255,255,255,0.04)"><span style="color:rgba(255,255,255,0.6)">{name}</span><span style="color:{sig_color};font-weight:500">{pts_str}</span></div>'
        elif len(sig) == 3:
            name, direction_sig, detail = sig
            sig_color = "#00d4aa" if direction_sig == "CALLS" else "#ff4757" if direction_sig == "PUTS" else "#666"
            flow_signals_html += f'<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:11px;border-bottom:1px solid rgba(255,255,255,0.04)"><span style="color:rgba(255,255,255,0.6)">{name}</span><span style="color:{sig_color}">{detail}</span></div>'
    
    mom_color="#00d4aa" if "BULL" in momentum["signal"] else "#ff4757" if "BEAR" in momentum["signal"] else "#ffa502"
    vix_color="#00d4aa" if vix_zone in ["LOW","NORMAL"] else "#ffa502" if vix_zone=="ELEVATED" else "#ff4757"
    
    # Build the analysis grid
    analysis_html=f'''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">

<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:20px;min-height:280px;display:flex;flex-direction:column">
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px">
<div style="display:flex;align-items:center;gap:12px">
<div style="width:44px;height:44px;background:rgba(168,85,247,0.15);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px">📊</div>
<div><div style="font-size:15px;font-weight:600">Confidence Score</div>
<div style="font-size:11px;color:rgba(255,255,255,0.5)">Setup quality assessment</div></div>
</div>
<div style="text-align:right">
<div style="font-family:monospace;font-size:28px;font-weight:700;color:{conf_color}">{conf_score}%</div>
<div style="font-size:10px;font-weight:600;color:{conf_color}">{conf_label}</div>
</div>
</div>
<div style="height:8px;background:rgba(255,255,255,0.08);border-radius:4px;overflow:hidden;margin-bottom:16px">
<div style="height:100%;width:{conf_score}%;background:{conf_color};border-radius:4px"></div>
</div>
<div style="flex:1;background:rgba(255,255,255,0.02);border-radius:10px;padding:12px">{breakdown_html}</div>
</div>

<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:20px;min-height:280px;display:flex;flex-direction:column">
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
<div style="width:44px;height:44px;background:rgba(59,130,246,0.15);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px">📈</div>
<div><div style="font-size:15px;font-weight:600">EMA Confirmation</div>
<div style="font-size:11px;color:rgba(255,255,255,0.5)">8/21 Cross + 200 Filter</div></div>
</div>
<div style="background:{align_bg};border-radius:10px;padding:14px;text-align:center;margin-bottom:16px">
<div style="font-size:15px;font-weight:600;color:{align_color}">{align_text}</div>
</div>
<div style="flex:1;display:grid;grid-template-columns:1fr 1fr;gap:12px">
<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:16px;text-align:center;display:flex;flex-direction:column;justify-content:center">
<div style="font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:6px">8/21 CROSS</div>
<div style="font-size:20px;font-weight:600;color:{cross_color}">{ema_signals["cross_signal"]}</div>
<div style="font-size:10px;color:rgba(255,255,255,0.3);margin-top:6px">EMA8: {ema_signals["ema8"] or "—"}</div>
</div>
<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:16px;text-align:center;display:flex;flex-direction:column;justify-content:center">
<div style="font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:6px">200 EMA</div>
<div style="font-size:20px;font-weight:600;color:{filter_color}">{filter_text}</div>
<div style="font-size:10px;color:rgba(255,255,255,0.3);margin-top:6px">EMA200: {ema_signals["ema200"] or "—"}</div>
</div>
</div>
</div>

<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:20px;min-height:220px;display:flex;flex-direction:column">
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
<div style="display:flex;align-items:center;gap:12px">
<div style="width:44px;height:44px;background:rgba(34,211,238,0.15);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px">🌊</div>
<div><div style="font-size:15px;font-weight:600">Flow Bias</div>
<div style="font-size:11px;color:rgba(255,255,255,0.5)">{flow.get("real_data_sources", 0)} live sources</div></div>
</div>
<div style="text-align:right">
<div style="font-family:monospace;font-size:28px;font-weight:700;color:{flow_color}">{flow["score"]:+d}</div>
<div style="font-size:10px;font-weight:600;color:{flow_color}">{flow_label}</div>
</div>
</div>
<div style="display:flex;justify-content:space-between;font-size:9px;color:rgba(255,255,255,0.4);margin-bottom:4px">
<span>STRONG PUTS</span><span>NEUTRAL</span><span>STRONG CALLS</span>
</div>
<div style="height:10px;background:linear-gradient(90deg,#ff4757,#ffa502 50%,#00d4aa);border-radius:5px;position:relative;margin-bottom:12px">
<div style="position:absolute;top:-4px;left:{meter_pos}%;width:6px;height:18px;background:#fff;border-radius:3px;transform:translateX(-50%);box-shadow:0 0 8px rgba(255,255,255,0.5)"></div>
</div>
<div style="flex:1;overflow-y:auto;max-height:100px">
{flow_signals_html}
</div>
</div>

<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:20px;min-height:220px;display:flex;flex-direction:column">
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
<div style="width:44px;height:44px;background:rgba(255,165,2,0.15);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px">📉</div>
<div><div style="font-size:15px;font-weight:600">Market Context</div>
<div style="font-size:11px;color:rgba(255,255,255,0.5)">Momentum & volatility</div></div>
</div>
<div style="flex:1;display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:14px;text-align:center;display:flex;flex-direction:column;justify-content:center">
<div style="font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:6px">MOMENTUM</div>
<div style="font-size:16px;font-weight:600;color:{mom_color}">{momentum["signal"]}</div>
</div>
<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:14px;text-align:center;display:flex;flex-direction:column;justify-content:center">
<div style="font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:6px">RSI (14)</div>
<div style="font-size:18px;font-weight:600">{momentum["rsi"]}</div>
</div>
<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:14px;text-align:center;display:flex;flex-direction:column;justify-content:center">
<div style="font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:6px">VIX {'✓' if vix_source == 'manual' else '⚠️' if inputs.get('is_planning') else ''}</div>
<div style="font-size:18px;font-weight:600;color:{vix_color}">{vix:.1f}</div>
<div style="font-size:9px;color:{vix_color}">{vix_zone}{' (manual)' if vix_source == 'manual' else ' (stale?)' if inputs.get('is_planning') else ''}</div>
</div>
</div>
</div>

</div>'''
    
    st.markdown(analysis_html,unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONES & LEVELS
    # ═══════════════════════════════════════════════════════════════════════════
    with st.expander("📊 Cone Rails (SPX)"):
        cone_html="".join([f'<div class="pillar"><span>{n}</span><span><span style="color:#00d4aa">↑{c["asc"]}</span> | <span style="color:#ff4757">↓{c["desc"]}</span></span></div>' for n,c in cones_spx.items()])
        st.markdown(f'<div class="card">{cone_html}</div>',unsafe_allow_html=True)
    
    with st.expander("📐 All Structure Levels"):
        all_lvls=[("Ceiling Rising",levels["ceiling_rising"]["level"]),("Ceiling Falling",levels["ceiling_falling"]["level"]),("Floor Rising",levels["floor_rising"]["level"]),("Floor Falling",levels["floor_falling"]["level"])]
        all_lvls.sort(key=lambda x:x[1],reverse=True)
        lvl_html="".join([f'<div class="pillar"><span>{n}</span><span>ES {l} → SPX {round(l-offset,2)}</span></div>' for n,l in all_lvls])
        st.markdown(f'<div class="card">{lvl_html}</div>',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DEBUG
    # ═══════════════════════════════════════════════════════════════════════════
    if inputs["debug"]:
        st.markdown("### 🔧 Debug")
        
        # Show 8:30 candle vs channel
        st.markdown("**8:30 Candle vs Channel:**")
        if candle_830:
            st.write(f"- Candle: O={candle_830['open']}, H={candle_830['high']}, L={candle_830['low']}, C={candle_830['close']}")
        st.write(f"- Ceiling (ES): {ceiling_es}")
        st.write(f"- Floor (ES): {floor_es}")
        if candle_830 and ceiling_es and floor_es:
            st.write(f"- High vs Ceiling: {candle_830['high']} {'>' if candle_830['high']>ceiling_es else '<='} {ceiling_es} → {'BROKE ABOVE' if candle_830['high']>ceiling_es else 'did not break'}")
            st.write(f"- Low vs Floor: {candle_830['low']} {'<' if candle_830['low']<floor_es else '>='} {floor_es} → {'BROKE BELOW' if candle_830['low']<floor_es else 'did not break'}")
            st.write(f"- Close: {candle_830['close']} → {'ABOVE ceiling' if candle_830['close']>ceiling_es else 'BELOW floor' if candle_830['close']<floor_es else 'INSIDE channel'}")
        
        # Show validation result
        st.markdown("**Validation Result:**")
        st.write(f"- Status: {validation['status']}")
        st.write(f"- Message: {validation['message']}")
        st.write(f"- Setup: {validation['setup']}")
        st.write(f"- Position: {validation.get('position','N/A')}")
        
        # Show scenarios
        st.markdown("**Scenario Analysis:**")
        st.json(scenarios)
        
        # Show put/call ratio data
        st.markdown("**Put/Call Ratio Data:**")
        st.json(pc_data)
        
        # Show times
        st.markdown("**Anchor Times:**")
        st.write(f"- O/N High Time: {on_high_time}")
        st.write(f"- O/N Low Time: {on_low_time}")
        st.write(f"- Reference Time: {ref_time}")
        
        # Show block calculations
        st.markdown("**Block Calculations:**")
        blocks_high=blocks_between(on_high_time,ref_time)
        blocks_low=blocks_between(on_low_time,ref_time)
        st.write(f"- Blocks from O/N High to Ref: {blocks_high} (exp: {SLOPE*blocks_high:.2f})")
        st.write(f"- Blocks from O/N Low to Ref: {blocks_low} (exp: {SLOPE*blocks_low:.2f})")
        
        # Show raw values
        st.markdown("**Raw Values (ES):**")
        st.write(f"- O/N High: {on_high}, O/N Low: {on_low}")
        st.write(f"- Sydney H/L: {syd_h}/{syd_l}, Tokyo H/L: {tok_h}/{tok_l}")
        st.write(f"- Channel Type: {channel_type} ({channel_reason})")
        
        # Show calculated levels
        st.markdown("**Calculated Levels (ES):**")
        st.json(levels)
        
        # Show hist_data if available
        if hist_data:
            st.markdown("**Historical Data Extracted:**")
            hist_display={k:str(v) if isinstance(v,pd.DataFrame) else v for k,v in hist_data.items() if k!="day_candles"}
            st.json(hist_display)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(f'''<div class="footer">
<div style="margin-bottom:8px;font-weight:600;font-size:12px">🔮 SPX PROPHET V6.1</div>
<div style="font-size:10px;color:rgba(255,255,255,0.4)">
Sydney/Tokyo Channel • Scenario Analysis • Put/Call Ratio • Structural Cone Targets
</div>
<div style="margin-top:6px;font-size:10px;color:rgba(255,255,255,0.3)">
Setup Window: 8:00-10:30 AM | Entry Window: 8:30-11:00 AM | Slope: {SLOPE} pts/block | Break Threshold: {BREAK_THRESHOLD} pts
</div>
</div>''',unsafe_allow_html=True)
    
    if inputs["auto_refresh"] and not inputs["is_historical"]:
        time_module.sleep(30)
        st.rerun()

if __name__=="__main__":
    main()
```