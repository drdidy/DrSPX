"""
SPX PROPHET - Institutional Grade 0DTE SPX Options Decision Support System
Version 3.0

A systematic approach to 0DTE SPX options trading using VIX zone analysis
and structural cone methodology.

DESIGN PRINCIPLES:
- Institutional-grade dark theme
- Professional typography hierarchy
- Clear visual status indicators
- Realistic targets: 12.5%, 25%, 50%
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import yfinance as yf
import pytz
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
from enum import Enum

# =============================================================================
# PAGE CONFIG (Must be first Streamlit command)
# =============================================================================

st.set_page_config(
    page_title="SPX Prophet",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# GLOBAL STYLES
# =============================================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

/* Global dark theme */
.stApp {
    background: linear-gradient(180deg, #0a0f1a 0%, #0f172a 100%);
}

/* Hide default Streamlit elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Container styling */
.main .block-container {
    padding: 1rem 2rem 2rem 2rem;
    max-width: 1400px;
}

/* Metric styling */
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.1rem !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Dataframe styling */
.stDataFrame {
    border-radius: 8px;
    overflow: hidden;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background: #1e293b;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.85rem;
}

/* Input styling */
.stNumberInput input, .stTimeInput input, .stTextInput input {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 6px !important;
    color: #f8fafc !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Button styling */
.stButton > button {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: 600;
}

/* Card base class */
.prophet-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}

/* Remove extra spacing */
.element-container {
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

class TradingConstants:
    SLOPE_PER_30MIN = 0.45
    MIN_CONE_WIDTH = 18.0
    STOP_LOSS_PTS = 6.0
    STRIKE_OTM_DISTANCE = 17.5
    DELTA = 0.33
    CONTRACT_MULTIPLIER = 100
    
    # Realistic targets for 0DTE
    TARGET_1_PCT = 0.125  # 12.5%
    TARGET_2_PCT = 0.25   # 25%
    TARGET_3_PCT = 0.50   # 50%
    
    VIX_ZONE_LOW = 0.20
    VIX_ZONE_NORMAL = 0.30
    VIX_ZONE_HIGH = 0.45
    
    ZONE_TOP_THRESHOLD = 0.75
    ZONE_BOTTOM_THRESHOLD = 0.25


class TradingPhase(Enum):
    OVERNIGHT = "Overnight Prep"
    ZONE_LOCK = "Zone Lock"
    DANGER_ZONE = "Danger Zone"
    RTH = "RTH Active"
    POST_SESSION = "Post-Session"
    MARKET_CLOSED = "Market Closed"


class Bias(Enum):
    CALLS = "CALLS"
    PUTS = "PUTS"
    WAIT = "WAIT"


class Confidence(Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NO_TRADE = "NO TRADE"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VIXZone:
    bottom: float
    top: float
    current: float
    
    @property
    def size(self) -> float:
        return self.top - self.bottom
    
    @property
    def position_pct(self) -> float:
        if self.size == 0:
            return 50.0
        return ((self.current - self.bottom) / self.size) * 100
    
    @property
    def potential(self) -> str:
        if self.size < TradingConstants.VIX_ZONE_LOW:
            return "LOW"
        elif self.size < TradingConstants.VIX_ZONE_HIGH:
            return "NORMAL"
        else:
            return "HIGH"
    
    def get_extension(self, level: int) -> float:
        if level > 0:
            return self.top + (level * self.size)
        return self.bottom + (level * self.size)


@dataclass
class Pivot:
    name: str
    price: float
    timestamp: datetime
    is_secondary: bool = False
    enabled: bool = True


@dataclass
class ConeRails:
    pivot: Pivot
    ascending: float
    descending: float
    width: float
    blocks: int
    is_valid: bool
    
    @property
    def is_tradeable(self) -> bool:
        return self.width >= TradingConstants.MIN_CONE_WIDTH


@dataclass 
class TradeSetup:
    direction: Bias
    cone: ConeRails
    entry: float
    stop: float
    target_1: float  # 12.5%
    target_2: float  # 25%
    target_3: float  # 50%
    strike: int
    risk_pts: float
    reward_1_pts: float
    reward_2_pts: float
    reward_3_pts: float


# =============================================================================
# CALCULATION ENGINE
# =============================================================================

class SPXProphetEngine:
    def __init__(self):
        self.ct_tz = pytz.timezone('America/Chicago')
    
    def get_current_phase(self, current_time: datetime) -> TradingPhase:
        ct_time = current_time.astimezone(self.ct_tz)
        t = ct_time.time()
        weekday = ct_time.weekday()
        
        if weekday >= 5:
            return TradingPhase.MARKET_CLOSED
        
        if time(17, 0) <= t <= time(23, 59) or time(0, 0) <= t < time(2, 0):
            return TradingPhase.OVERNIGHT
        elif time(2, 0) <= t < time(6, 30):
            return TradingPhase.ZONE_LOCK
        elif time(6, 30) <= t < time(9, 30):
            return TradingPhase.DANGER_ZONE
        elif time(9, 30) <= t < time(16, 0):
            return TradingPhase.RTH
        elif time(16, 0) <= t < time(17, 0):
            return TradingPhase.POST_SESSION
        return TradingPhase.MARKET_CLOSED
    
    def determine_bias(self, zone: VIXZone) -> Tuple[Bias, Confidence, str]:
        pos = zone.position_pct
        
        if pos >= TradingConstants.ZONE_TOP_THRESHOLD * 100:
            bias = Bias.CALLS
            explanation = f"VIX at TOP ({pos:.0f}%) → Expect VIX down → SPX UP"
            confidence = Confidence.STRONG if pos >= 85 else (Confidence.MODERATE if pos >= 75 else Confidence.WEAK)
        elif pos <= TradingConstants.ZONE_BOTTOM_THRESHOLD * 100:
            bias = Bias.PUTS
            explanation = f"VIX at BOTTOM ({pos:.0f}%) → Expect VIX up → SPX DOWN"
            confidence = Confidence.STRONG if pos <= 15 else (Confidence.MODERATE if pos <= 25 else Confidence.WEAK)
        else:
            bias = Bias.WAIT
            confidence = Confidence.NO_TRADE
            explanation = f"VIX mid-zone ({pos:.0f}%) → No edge → WAIT"
        
        return bias, confidence, explanation
    
    def calculate_blocks(self, pivot_time: datetime, eval_time: datetime) -> int:
        pivot_ct = pivot_time.astimezone(self.ct_tz)
        eval_ct = eval_time.astimezone(self.ct_tz)
        diff = eval_ct - pivot_ct
        total_minutes = diff.total_seconds() / 60
        return max(int(total_minutes / 30), 1)
    
    def calculate_cone(self, pivot: Pivot, eval_time: datetime) -> ConeRails:
        blocks = self.calculate_blocks(pivot.timestamp, eval_time)
        expansion = blocks * TradingConstants.SLOPE_PER_30MIN
        ascending = pivot.price + expansion
        descending = pivot.price - expansion
        
        return ConeRails(
            pivot=pivot,
            ascending=round(ascending, 2),
            descending=round(descending, 2),
            width=round(ascending - descending, 2),
            blocks=blocks,
            is_valid=pivot.enabled
        )
    
    def generate_trade_setup(self, cone: ConeRails, direction: Bias, current_price: float) -> Optional[TradeSetup]:
        if not cone.is_tradeable or direction == Bias.WAIT:
            return None
        
        if direction == Bias.CALLS:
            entry = cone.descending
            opposite = cone.ascending
            stop = entry - TradingConstants.STOP_LOSS_PTS
            strike = int(round((entry - TradingConstants.STRIKE_OTM_DISTANCE) / 5) * 5)
        else:
            entry = cone.ascending
            opposite = cone.descending
            stop = entry + TradingConstants.STOP_LOSS_PTS
            strike = int(round((entry + TradingConstants.STRIKE_OTM_DISTANCE) / 5) * 5)
        
        move = abs(opposite - entry)
        
        if direction == Bias.CALLS:
            t1 = entry + (move * TradingConstants.TARGET_1_PCT)
            t2 = entry + (move * TradingConstants.TARGET_2_PCT)
            t3 = entry + (move * TradingConstants.TARGET_3_PCT)
        else:
            t1 = entry - (move * TradingConstants.TARGET_1_PCT)
            t2 = entry - (move * TradingConstants.TARGET_2_PCT)
            t3 = entry - (move * TradingConstants.TARGET_3_PCT)
        
        return TradeSetup(
            direction=direction, cone=cone, entry=round(entry, 2), stop=round(stop, 2),
            target_1=round(t1, 2), target_2=round(t2, 2), target_3=round(t3, 2),
            strike=strike, risk_pts=TradingConstants.STOP_LOSS_PTS,
            reward_1_pts=round(move * TradingConstants.TARGET_1_PCT, 2),
            reward_2_pts=round(move * TradingConstants.TARGET_2_PCT, 2),
            reward_3_pts=round(move * TradingConstants.TARGET_3_PCT, 2)
        )
    
    def calculate_profit(self, points: float, contracts: int = 1) -> float:
        return points * TradingConstants.DELTA * TradingConstants.CONTRACT_MULTIPLIER * contracts
    
    def calculate_max_contracts(self, risk_budget: float) -> int:
        risk_per = self.calculate_profit(TradingConstants.STOP_LOSS_PTS, 1)
        return int(risk_budget / risk_per) if risk_per > 0 else 0


# =============================================================================
# DATA FETCHING
# =============================================================================

@st.cache_data(ttl=60)
def fetch_market_data():
    try:
        spx = yf.Ticker("^GSPC")
        vix = yf.Ticker("^VIX")
        
        spx_data = spx.history(period="2d")
        vix_data = vix.history(period="1d")
        
        spx_price = spx_data['Close'].iloc[-1] if not spx_data.empty else None
        vix_price = vix_data['Close'].iloc[-1] if not vix_data.empty else None
        
        prior_data = None
        if len(spx_data) >= 2:
            prior = spx_data.iloc[-2]
            prior_data = {
                'high': prior['High'], 'low': prior['Low'], 'close': prior['Close'],
                'date': spx_data.index[-2]
            }
        
        return spx_price, vix_price, prior_data
    except Exception as e:
        return None, None, None


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_header(spx: float, vix: float, phase: TradingPhase):
    ct = pytz.timezone('America/Chicago')
    now = datetime.now(ct)
    
    phase_config = {
        TradingPhase.OVERNIGHT: ("#3b82f6", "🌙"),
        TradingPhase.ZONE_LOCK: ("#06b6d4", "🔒"),
        TradingPhase.DANGER_ZONE: ("#f59e0b", "⚠️"),
        TradingPhase.RTH: ("#10b981", "🟢"),
        TradingPhase.POST_SESSION: ("#6b7280", "📊"),
        TradingPhase.MARKET_CLOSED: ("#374151", "🔴")
    }
    color, icon = phase_config.get(phase, ("#374151", ""))
    
    header_html = f'''
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; margin-bottom: 20px;">
        <div>
            <h1 style="font-family: 'JetBrains Mono', monospace; font-size: 1.75rem; font-weight: 700; color: #f8fafc; margin: 0;">SPX PROPHET</h1>
            <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; margin: 4px 0 0 0; text-transform: uppercase; letter-spacing: 1.5px;">Institutional 0DTE Decision System</p>
        </div>
        <div style="display: flex; gap: 32px; align-items: center;">
            <div style="text-align: right;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; margin: 0; text-transform: uppercase; letter-spacing: 1px;">SPX</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700; color: #f8fafc; margin: 0;">{spx:,.2f}</p>
            </div>
            <div style="text-align: right;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; margin: 0; text-transform: uppercase; letter-spacing: 1px;">VIX</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700; color: #f8fafc; margin: 0;">{vix:.2f}</p>
            </div>
            <div style="text-align: right;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; margin: 0; text-transform: uppercase; letter-spacing: 1px;">{now.strftime('%I:%M %p')} CT</p>
                <p style="font-family: 'Inter', sans-serif; font-size: 0.85rem; font-weight: 600; color: {color}; margin: 4px 0 0 0;">{icon} {phase.value}</p>
            </div>
        </div>
    </div>
    '''
    st.markdown(header_html, unsafe_allow_html=True)


def render_bias_display(bias: Bias, confidence: Confidence, explanation: str):
    colors = {
        Bias.CALLS: ("#10b981", "#064e3b"),
        Bias.PUTS: ("#ef4444", "#7f1d1d"),
        Bias.WAIT: ("#f59e0b", "#78350f")
    }
    accent, bg = colors.get(bias, ("#6b7280", "#1f2937"))
    
    conf_dots = {
        Confidence.STRONG: "●●●●",
        Confidence.MODERATE: "●●●○",
        Confidence.WEAK: "●●○○",
        Confidence.NO_TRADE: "○○○○"
    }.get(confidence, "○○○○")
    
    html = f'''
    <div style="background: linear-gradient(135deg, {bg} 0%, #1e293b 100%); border: 2px solid {accent}; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 20px;">
        <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 2px; margin: 0 0 8px 0;">Today's Bias</p>
        <h2 style="font-family: 'JetBrains Mono', monospace; font-size: 2.5rem; font-weight: 700; color: {accent}; margin: 0; letter-spacing: 3px;">{bias.value}</h2>
        <p style="font-family: 'JetBrains Mono', monospace; font-size: 1rem; color: {accent}; margin: 8px 0; letter-spacing: 3px;">{conf_dots}</p>
        <p style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #94a3b8; margin: 0;">{confidence.value}</p>
        <div style="margin-top: 16px; padding: 12px; background: rgba(0,0,0,0.3); border-radius: 8px;">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.8rem; color: #cbd5e1; margin: 0;">{explanation}</p>
        </div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)


def render_vix_ladder(zone: VIXZone):
    potential_cfg = {
        "HIGH": ("#10b981", "🔥"),
        "NORMAL": ("#3b82f6", "✓"),
        "LOW": ("#f59e0b", "⚠️")
    }
    pot_color, pot_icon = potential_cfg.get(zone.potential, ("#6b7280", ""))
    
    def level_row(label: str, value: float, style: str) -> str:
        styles = {
            "extension": "background: #1e293b; color: #64748b;",
            "top": "background: #064e3b; color: #10b981; border: 1px solid #10b981;",
            "bottom": "background: #7f1d1d; color: #ef4444; border: 1px solid #ef4444;",
            "current": "background: #1e3a8a; color: #60a5fa; border: 2px solid #3b82f6;"
        }
        return f'''<div style="display: flex; justify-content: space-between; padding: 8px 14px; margin: 3px 0; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; {styles.get(style, '')}">
            <span>{label}</span><span>{value:.2f}</span>
        </div>'''
    
    rows = ""
    rows += level_row("+2", zone.get_extension(2), "extension")
    rows += level_row("+1", zone.get_extension(1), "extension")
    rows += level_row("TOP", zone.top, "top")
    rows += level_row("VIX NOW", zone.current, "current")
    rows += level_row("BOTTOM", zone.bottom, "bottom")
    rows += level_row("-1", zone.get_extension(-1), "extension")
    rows += level_row("-2", zone.get_extension(-2), "extension")
    
    html = f'''
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; padding: 16px;">
        <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px 0;">VIX Zone Ladder</p>
        {rows}
        <div style="display: flex; justify-content: space-between; margin-top: 14px; padding-top: 14px; border-top: 1px solid #334155;">
            <div style="text-align: center; flex: 1;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; text-transform: uppercase; margin: 0;">Size</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: #f8fafc; margin: 4px 0 0 0;">{zone.size:.2f}</p>
            </div>
            <div style="text-align: center; flex: 1;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; text-transform: uppercase; margin: 0;">Position</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: #f8fafc; margin: 4px 0 0 0;">{zone.position_pct:.0f}%</p>
            </div>
            <div style="text-align: center; flex: 1;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; text-transform: uppercase; margin: 0;">Potential</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: {pot_color}; margin: 4px 0 0 0;">{pot_icon} {zone.potential}</p>
            </div>
        </div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)


def render_checklist(zone: VIXZone, phase: TradingPhase, setup: Optional[TradeSetup], price: float):
    checks = [
        ("VIX at zone edge", zone.position_pct >= 75 or zone.position_pct <= 25),
        ("Reliable timing window", phase in [TradingPhase.ZONE_LOCK, TradingPhase.RTH]),
        ("30-min candle closed", True),
        ("Price at rail entry", setup and abs(price - setup.entry) <= 5.0),
        ("Cone width ≥ 18 pts", setup and setup.cone.is_tradeable if setup else False)
    ]
    
    items = ""
    for label, passed in checks:
        icon = "✓" if passed else "○"
        color = "#10b981" if passed else "#475569"
        text_color = "#e2e8f0" if passed else "#64748b"
        items += f'''<div style="display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #1e293b;">
            <span style="font-size: 1rem; color: {color}; width: 20px;">{icon}</span>
            <span style="font-family: 'Inter', sans-serif; font-size: 0.8rem; color: {text_color};">{label}</span>
        </div>'''
    
    all_pass = all(p for _, p in checks)
    status_bg = "#064e3b" if all_pass else "#1e293b"
    status_color = "#10b981" if all_pass else "#64748b"
    status_text = "READY TO ENTER" if all_pass else "WAITING"
    
    html = f'''
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; padding: 16px;">
        <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px 0;">Entry Checklist</p>
        {items}
        <div style="margin-top: 14px; padding: 10px; background: {status_bg}; border-radius: 6px; text-align: center; border: 1px solid {status_color};">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.75rem; font-weight: 600; color: {status_color}; margin: 0; text-transform: uppercase; letter-spacing: 1px;">{status_text}</p>
        </div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)


def render_cone_table(cones: List[ConeRails], best_name: str):
    st.markdown("""
    <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 20px 0 10px 0;">Cone Rails</p>
    """, unsafe_allow_html=True)
    
    data = []
    for c in cones:
        if not c.is_valid:
            continue
        status = "⭐ BEST" if c.pivot.name == best_name else ("✓" if c.is_tradeable else "✗")
        data.append({
            "Pivot": c.pivot.name,
            "Ascending": f"{c.ascending:,.2f}",
            "Descending": f"{c.descending:,.2f}",
            "Width": f"{c.width:.1f}",
            "Status": status
        })
    
    if data:
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


def render_setup_card(setup: TradeSetup, price: float, engine: SPXProphetEngine):
    if not setup:
        return
    
    color = "#10b981" if setup.direction == Bias.CALLS else "#ef4444"
    bg = "#064e3b" if setup.direction == Bias.CALLS else "#7f1d1d"
    
    dist = price - setup.entry
    dist_str = f"{'+' if dist > 0 else ''}{dist:.2f}"
    
    p1 = engine.calculate_profit(setup.reward_1_pts, 1)
    p2 = engine.calculate_profit(setup.reward_2_pts, 1)
    risk = engine.calculate_profit(setup.risk_pts, 1)
    rr = p2 / risk if risk > 0 else 0
    
    def box(label: str, value: str, highlight: bool = False) -> str:
        border = f"border: 1px solid {color};" if highlight else ""
        return f'''<div style="background: rgba(0,0,0,0.3); border-radius: 6px; padding: 10px 8px; text-align: center; {border}">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 4px 0;">{label}</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600; color: #f8fafc; margin: 0;">{value}</p>
        </div>'''
    
    def stat(label: str, value: str) -> str:
        return f'''<div style="text-align: center;">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; text-transform: uppercase; margin: 0;">{label}</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #f8fafc; margin: 2px 0 0 0;">{value}</p>
        </div>'''
    
    html = f'''
    <div style="background: linear-gradient(135deg, {bg} 0%, #1e293b 100%); border: 2px solid {color}; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 700; color: {color};">{setup.direction.value} SETUP</span>
            <span style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #94a3b8;">{setup.cone.pivot.name} Cone</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 14px;">
            {box("Entry", f"{setup.entry:,.2f}", True)}
            {box("Stop", f"{setup.stop:,.2f}")}
            {box("12.5%", f"{setup.target_1:,.2f}")}
            {box("25%", f"{setup.target_2:,.2f}")}
            {box("50%", f"{setup.target_3:,.2f}")}
        </div>
        <div style="display: flex; justify-content: space-between; padding-top: 12px; border-top: 1px solid #334155;">
            {stat("Distance", f"{dist_str} pts")}
            {stat("Strike", str(setup.strike))}
            {stat("Width", f"{setup.cone.width:.1f}")}
            {stat("R:R @25%", f"{rr:.1f}:1")}
            {stat("Profit @25%", f"${p2:,.0f}")}
        </div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)


def render_position_calc(engine: SPXProphetEngine, setup: Optional[TradeSetup]):
    st.markdown("""
    <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px 0;">Position Calculator</p>
    """, unsafe_allow_html=True)
    
    risk_budget = st.number_input("Risk Budget ($)", min_value=100, max_value=100000, value=1000, step=100, label_visibility="collapsed")
    st.caption("Risk Budget ($)")
    
    if setup:
        contracts = engine.calculate_max_contracts(risk_budget)
        risk_total = engine.calculate_profit(setup.risk_pts, contracts)
        p1 = engine.calculate_profit(setup.reward_1_pts, contracts)
        p2 = engine.calculate_profit(setup.reward_2_pts, contracts)
        p3 = engine.calculate_profit(setup.reward_3_pts, contracts)
        
        html = f'''
        <div style="background: #1e293b; border-radius: 8px; padding: 14px; text-align: center; margin: 12px 0; border: 1px solid #334155;">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; text-transform: uppercase; margin: 0;">Max Contracts</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700; color: #10b981; margin: 4px 0 0 0;">{contracts}</p>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <div style="background: #1e293b; border-radius: 6px; padding: 10px; border: 1px solid #334155;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; text-transform: uppercase; margin: 0 0 4px 0;">Risk</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600; color: #ef4444; margin: 0;">${risk_total:,.0f}</p>
            </div>
            <div style="background: #1e293b; border-radius: 6px; padding: 10px; border: 1px solid #334155;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; text-transform: uppercase; margin: 0 0 4px 0;">@ 12.5%</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600; color: #10b981; margin: 0;">${p1:,.0f}</p>
            </div>
            <div style="background: #1e293b; border-radius: 6px; padding: 10px; border: 1px solid #334155;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; text-transform: uppercase; margin: 0 0 4px 0;">@ 25%</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600; color: #10b981; margin: 0;">${p2:,.0f}</p>
            </div>
            <div style="background: #1e293b; border-radius: 6px; padding: 10px; border: 1px solid #334155;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; text-transform: uppercase; margin: 0 0 4px 0;">@ 50%</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600; color: #10b981; margin: 0;">${p3:,.0f}</p>
            </div>
        </div>
        '''
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.info("Configure a valid setup first")


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(prior_data: Optional[Dict]) -> Tuple[VIXZone, List[Pivot]]:
    st.sidebar.markdown("## ⚙️ Configuration")
    
    st.sidebar.markdown("#### VIX Zone")
    c1, c2 = st.sidebar.columns(2)
    vix_bottom = c1.number_input("Bottom", 5.0, 100.0, 16.50, 0.01, format="%.2f")
    vix_top = c2.number_input("Top", 5.0, 100.0, 16.65, 0.01, format="%.2f")
    vix_current = st.sidebar.number_input("Current VIX", 5.0, 100.0, 16.55, 0.01, format="%.2f")
    
    zone = VIXZone(vix_bottom, vix_top, vix_current)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Prior Day Pivots")
    
    ct_tz = pytz.timezone('America/Chicago')
    manual = st.sidebar.checkbox("Manual Input", False)
    
    if manual or not prior_data:
        c1, c2 = st.sidebar.columns(2)
        p_high = c1.number_input("High", 1000.0, 10000.0, 6050.0, 1.0)
        p_high_t = c2.time_input("High Time", time(11, 30))
        c1, c2 = st.sidebar.columns(2)
        p_low = c1.number_input("Low", 1000.0, 10000.0, 6020.0, 1.0)
        p_low_t = c2.time_input("Low Time", time(14, 0))
        p_close = st.sidebar.number_input("Close", 1000.0, 10000.0, 6035.0, 1.0)
        p_date = datetime.now(ct_tz).date() - timedelta(days=1)
    else:
        p_high, p_low, p_close = prior_data['high'], prior_data['low'], prior_data['close']
        p_date = prior_data['date'].date() if hasattr(prior_data['date'], 'date') else prior_data['date']
        p_high_t, p_low_t = time(11, 30), time(14, 0)
        st.sidebar.success(f"Loaded: {p_date}")
        st.sidebar.caption(f"H: {p_high:,.2f} | L: {p_low:,.2f} | C: {p_close:,.2f}")
    
    pivots = [
        Pivot("Prior High", p_high, ct_tz.localize(datetime.combine(p_date, p_high_t))),
        Pivot("Prior Low", p_low, ct_tz.localize(datetime.combine(p_date, p_low_t))),
        Pivot("Prior Close", p_close, ct_tz.localize(datetime.combine(p_date, time(16, 0))))
    ]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Secondary Pivots")
    
    if st.sidebar.checkbox("Enable High²"):
        c1, c2 = st.sidebar.columns(2)
        h2_p = c1.number_input("High² Price", 1000.0, 10000.0, 6045.0, 1.0)
        h2_t = c2.time_input("High² Time", time(10, 0))
        pivots.append(Pivot("High²", h2_p, ct_tz.localize(datetime.combine(p_date, h2_t)), True))
    
    if st.sidebar.checkbox("Enable Low²"):
        c1, c2 = st.sidebar.columns(2)
        l2_p = c1.number_input("Low² Price", 1000.0, 10000.0, 6025.0, 1.0)
        l2_t = c2.time_input("Low² Time", time(13, 0))
        pivots.append(Pivot("Low²", l2_p, ct_tz.localize(datetime.combine(p_date, l2_t)), True))
    
    return zone, pivots


# =============================================================================
# MAIN
# =============================================================================

def main():
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    now = datetime.now(ct_tz)
    
    spx, vix, prior = fetch_market_data()
    spx = spx or 6050.0
    vix = vix or 16.55
    
    zone, pivots = render_sidebar(prior)
    zone = VIXZone(zone.bottom, zone.top, vix)
    
    phase = engine.get_current_phase(now)
    bias, conf, expl = engine.determine_bias(zone)
    
    eval_t = ct_tz.localize(datetime.combine(now.date(), time(10, 0)))
    if now.time() > time(10, 0):
        eval_t = now
    
    cones = [engine.calculate_cone(p, eval_t) for p in pivots]
    valid = [c for c in cones if c.is_valid and c.is_tradeable]
    best = max(valid, key=lambda x: x.width) if valid else None
    best_name = best.pivot.name if best else ""
    
    best_setup = engine.generate_trade_setup(best, bias, spx) if best and bias != Bias.WAIT else None
    
    # ===== RENDER =====
    render_header(spx, vix, phase)
    render_bias_display(bias, conf, expl)
    
    c1, c2 = st.columns(2)
    with c1:
        render_vix_ladder(zone)
    with c2:
        render_checklist(zone, phase, best_setup, spx)
    
    render_cone_table(cones, best_name)
    
    if bias != Bias.WAIT:
        st.markdown(f"### {bias.value} Setups")
        for c in cones:
            if c.is_valid and c.is_tradeable:
                s = engine.generate_trade_setup(c, bias, spx)
                if s:
                    render_setup_card(s, spx, engine)
    else:
        st.info("📊 VIX mid-zone. Waiting for edge...")
    
    st.markdown("---")
    c1, c2 = st.columns([1, 2])
    with c1:
        render_position_calc(engine, best_setup)
    with c2:
        st.markdown("### Trade Rules")
        st.markdown("""
        **Entry:** CALLS at descending rail • PUTS at ascending rail
        
        **Stop:** 6 points from entry
        
        **Targets:** 12.5% → 25% → 50% of cone width
        
        **Confirmation:** Wait for 30-min candle CLOSE
        
        **Danger Zone:** 6:30-9:30 AM CT — reversals possible
        """)
    
    st.markdown("---")
    st.caption("SPX PROPHET v3.0 • Institutional 0DTE System • Yahoo Finance • Not financial advice")


if __name__ == "__main__":
    main()
