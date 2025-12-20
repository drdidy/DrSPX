"""
SPX PROPHET - Institutional Grade 0DTE SPX Options Decision Support System
Version 2.0

A systematic approach to 0DTE SPX options trading using VIX zone analysis
and structural cone methodology.
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
# CONFIGURATION & CONSTANTS
# =============================================================================

class TradingConstants:
    """Core trading system constants"""
    SLOPE_PER_30MIN = 0.45
    MIN_CONE_WIDTH = 18.0
    STOP_LOSS_PTS = 6.0
    STRIKE_OTM_DISTANCE = 17.5
    DELTA = 0.33
    CONTRACT_MULTIPLIER = 100
    
    # VIX Zone thresholds
    VIX_ZONE_LOW = 0.20      # Low potential
    VIX_ZONE_NORMAL = 0.30   # Normal potential
    VIX_ZONE_HIGH = 0.45     # High potential
    
    # Zone position thresholds
    ZONE_TOP_THRESHOLD = 0.75    # 75% = at top
    ZONE_BOTTOM_THRESHOLD = 0.25  # 25% = at bottom


class TradingPhase(Enum):
    """Trading day phases"""
    OVERNIGHT = "Overnight Prep"
    ZONE_LOCK = "Zone Lock & Analysis"
    DANGER_ZONE = "Danger Zone"
    RTH = "Regular Trading Hours"
    POST_SESSION = "Post-Session Review"
    MARKET_CLOSED = "Market Closed"


class Bias(Enum):
    """Trading bias"""
    CALLS = "CALLS"
    PUTS = "PUTS"
    WAIT = "WAIT"


class Confidence(Enum):
    """Bias confidence level"""
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NO_TRADE = "NO TRADE"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VIXZone:
    """VIX Zone data structure"""
    bottom: float
    top: float
    current: float
    
    @property
    def size(self) -> float:
        return self.top - self.bottom
    
    @property
    def position_pct(self) -> float:
        """Current VIX position as percentage within zone (0-100)"""
        if self.size == 0:
            return 50.0
        return ((self.current - self.bottom) / self.size) * 100
    
    @property
    def potential(self) -> str:
        """Move potential based on zone size"""
        if self.size < TradingConstants.VIX_ZONE_LOW:
            return "LOW"
        elif self.size < TradingConstants.VIX_ZONE_HIGH:
            return "NORMAL"
        else:
            return "HIGH"
    
    def get_extension(self, level: int) -> float:
        """Get extension level price"""
        if level > 0:
            return self.top + (level * self.size)
        else:
            return self.bottom + (level * self.size)


@dataclass
class Pivot:
    """Price pivot data structure"""
    name: str
    price: float
    timestamp: datetime
    is_secondary: bool = False
    enabled: bool = True


@dataclass
class ConeRails:
    """Cone projection data structure"""
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
    """Complete trade setup"""
    direction: Bias
    cone: ConeRails
    entry: float
    stop: float
    target_50: float
    target_75: float
    target_100: float
    strike: int
    risk_pts: float
    reward_50_pts: float
    reward_75_pts: float
    reward_100_pts: float


# =============================================================================
# CORE CALCULATION ENGINE
# =============================================================================

class SPXProphetEngine:
    """Core calculation engine for SPX Prophet"""
    
    def __init__(self):
        self.ct_tz = pytz.timezone('America/Chicago')
    
    def get_current_phase(self, current_time: datetime) -> TradingPhase:
        """Determine current trading phase based on time"""
        ct_time = current_time.astimezone(self.ct_tz)
        t = ct_time.time()
        weekday = ct_time.weekday()
        
        # Weekend check
        if weekday >= 5:  # Saturday or Sunday
            return TradingPhase.MARKET_CLOSED
        
        # Phase determination (all times in CT)
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
        else:
            return TradingPhase.MARKET_CLOSED
    
    def determine_bias(self, zone: VIXZone) -> Tuple[Bias, Confidence, str]:
        """Determine trading bias from VIX zone position"""
        pos = zone.position_pct
        
        if pos >= TradingConstants.ZONE_TOP_THRESHOLD * 100:
            bias = Bias.CALLS
            explanation = f"VIX at zone TOP ({pos:.0f}%) → Expect VIX to fall → SPX UP"
            if pos >= 85:
                confidence = Confidence.STRONG
            elif pos >= 75:
                confidence = Confidence.MODERATE
            else:
                confidence = Confidence.WEAK
        elif pos <= TradingConstants.ZONE_BOTTOM_THRESHOLD * 100:
            bias = Bias.PUTS
            explanation = f"VIX at zone BOTTOM ({pos:.0f}%) → Expect VIX to rise → SPX DOWN"
            if pos <= 15:
                confidence = Confidence.STRONG
            elif pos <= 25:
                confidence = Confidence.MODERATE
            else:
                confidence = Confidence.WEAK
        else:
            bias = Bias.WAIT
            confidence = Confidence.NO_TRADE
            explanation = f"VIX mid-zone ({pos:.0f}%) → No directional edge → WAIT"
        
        return bias, confidence, explanation
    
    def calculate_blocks(self, pivot_time: datetime, eval_time: datetime) -> int:
        """Calculate number of 30-minute blocks between pivot and evaluation time"""
        # Convert both to CT
        pivot_ct = pivot_time.astimezone(self.ct_tz)
        eval_ct = eval_time.astimezone(self.ct_tz)
        
        # Calculate time difference
        diff = eval_ct - pivot_ct
        total_minutes = diff.total_seconds() / 60
        blocks = int(total_minutes / 30)
        
        return max(blocks, 1)  # Minimum 1 block
    
    def calculate_cone(self, pivot: Pivot, eval_time: datetime) -> ConeRails:
        """Calculate cone rails from a pivot"""
        blocks = self.calculate_blocks(pivot.timestamp, eval_time)
        expansion = blocks * TradingConstants.SLOPE_PER_30MIN
        
        ascending = pivot.price + expansion
        descending = pivot.price - expansion
        width = ascending - descending
        
        return ConeRails(
            pivot=pivot,
            ascending=round(ascending, 2),
            descending=round(descending, 2),
            width=round(width, 2),
            blocks=blocks,
            is_valid=pivot.enabled
        )
    
    def generate_trade_setup(self, cone: ConeRails, direction: Bias, current_price: float) -> Optional[TradeSetup]:
        """Generate complete trade setup from cone"""
        if not cone.is_tradeable or direction == Bias.WAIT:
            return None
        
        if direction == Bias.CALLS:
            # CALLS: Enter at descending rail (support), target ascending
            entry = cone.descending
            target_100 = cone.ascending
        else:
            # PUTS: Enter at ascending rail (resistance), target descending
            entry = cone.ascending
            target_100 = cone.descending
        
        # Calculate targets
        move_distance = abs(target_100 - entry)
        
        if direction == Bias.CALLS:
            stop = entry - TradingConstants.STOP_LOSS_PTS
            target_50 = entry + (move_distance * 0.50)
            target_75 = entry + (move_distance * 0.75)
            strike = int(round((entry - TradingConstants.STRIKE_OTM_DISTANCE) / 5) * 5)
        else:
            stop = entry + TradingConstants.STOP_LOSS_PTS
            target_50 = entry - (move_distance * 0.50)
            target_75 = entry - (move_distance * 0.75)
            strike = int(round((entry + TradingConstants.STRIKE_OTM_DISTANCE) / 5) * 5)
        
        return TradeSetup(
            direction=direction,
            cone=cone,
            entry=round(entry, 2),
            stop=round(stop, 2),
            target_50=round(target_50, 2),
            target_75=round(target_75, 2),
            target_100=round(target_100, 2),
            strike=strike,
            risk_pts=TradingConstants.STOP_LOSS_PTS,
            reward_50_pts=round(move_distance * 0.50, 2),
            reward_75_pts=round(move_distance * 0.75, 2),
            reward_100_pts=round(move_distance, 2)
        )
    
    def calculate_profit(self, points: float, contracts: int = 1) -> float:
        """Calculate dollar profit from point movement"""
        return points * TradingConstants.DELTA * TradingConstants.CONTRACT_MULTIPLIER * contracts
    
    def calculate_max_contracts(self, risk_budget: float) -> int:
        """Calculate maximum contracts based on risk budget"""
        risk_per_contract = self.calculate_profit(TradingConstants.STOP_LOSS_PTS, 1)
        return int(risk_budget / risk_per_contract)


# =============================================================================
# DATA FETCHING
# =============================================================================

@st.cache_data(ttl=30)
def fetch_market_data() -> Tuple[Optional[float], Optional[float], Optional[Dict]]:
    """Fetch current SPX and VIX data"""
    try:
        spx = yf.Ticker("^GSPC")
        vix = yf.Ticker("^VIX")
        
        spx_data = spx.history(period="1d")
        vix_data = vix.history(period="1d")
        
        spx_price = spx_data['Close'].iloc[-1] if not spx_data.empty else None
        vix_price = vix_data['Close'].iloc[-1] if not vix_data.empty else None
        
        # Get prior day data
        spx_hist = spx.history(period="5d")
        if len(spx_hist) >= 2:
            prior_day = spx_hist.iloc[-2]
            prior_data = {
                'high': prior_day['High'],
                'low': prior_day['Low'],
                'close': prior_day['Close'],
                'date': spx_hist.index[-2]
            }
        else:
            prior_data = None
        
        return spx_price, vix_price, prior_data
    except Exception as e:
        st.error(f"Error fetching market data: {e}")
        return None, None, None


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_header(spx_price: float, vix_price: float, phase: TradingPhase):
    """Render the main header"""
    ct_tz = pytz.timezone('America/Chicago')
    current_time = datetime.now(ct_tz)
    
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');
    
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        border: 1px solid #334155;
    }
    
    .header-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 28px;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        letter-spacing: -0.5px;
    }
    
    .header-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        color: #64748b;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .price-display {
        font-family: 'JetBrains Mono', monospace;
        font-size: 32px;
        font-weight: 700;
        color: #f8fafc;
    }
    
    .price-label {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }
    
    .phase-badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 6px;
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .phase-overnight { background: #1e3a5f; color: #60a5fa; }
    .phase-zonelock { background: #164e63; color: #22d3ee; }
    .phase-danger { background: #713f12; color: #fbbf24; }
    .phase-rth { background: #14532d; color: #4ade80; }
    .phase-post { background: #3f3f46; color: #a1a1aa; }
    .phase-closed { background: #27272a; color: #71717a; }
    </style>
    """, unsafe_allow_html=True)
    
    phase_class = {
        TradingPhase.OVERNIGHT: "phase-overnight",
        TradingPhase.ZONE_LOCK: "phase-zonelock",
        TradingPhase.DANGER_ZONE: "phase-danger",
        TradingPhase.RTH: "phase-rth",
        TradingPhase.POST_SESSION: "phase-post",
        TradingPhase.MARKET_CLOSED: "phase-closed"
    }.get(phase, "phase-closed")
    
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1.5])
    
    with col1:
        st.markdown(f"""
        <div>
            <p class="header-title">SPX PROPHET</p>
            <p class="header-subtitle">Institutional Grade 0DTE System</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div>
            <p class="price-label">SPX</p>
            <p class="price-display">{spx_price:,.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div>
            <p class="price-label">VIX</p>
            <p class="price-display">{vix_price:.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div>
            <p class="price-label">{current_time.strftime('%I:%M %p CT')}</p>
            <span class="phase-badge {phase_class}">{phase.value}</span>
        </div>
        """, unsafe_allow_html=True)


def render_bias_card(bias: Bias, confidence: Confidence, explanation: str):
    """Render the bias determination card"""
    
    bias_colors = {
        Bias.CALLS: ("#10b981", "#064e3b", "#d1fae5"),
        Bias.PUTS: ("#ef4444", "#7f1d1d", "#fee2e2"),
        Bias.WAIT: ("#f59e0b", "#78350f", "#fef3c7")
    }
    
    accent, bg_dark, bg_light = bias_colors[bias]
    
    confidence_display = {
        Confidence.STRONG: ("●●●●", "#10b981"),
        Confidence.MODERATE: ("●●●○", "#f59e0b"),
        Confidence.WEAK: ("●●○○", "#ef4444"),
        Confidence.NO_TRADE: ("○○○○", "#6b7280")
    }
    
    conf_dots, conf_color = confidence_display[confidence]
    
    st.markdown(f"""
    <style>
    .bias-card {{
        background: linear-gradient(135deg, {bg_dark} 0%, #1e293b 100%);
        border: 2px solid {accent};
        border-radius: 16px;
        padding: 32px;
        text-align: center;
        margin-bottom: 24px;
    }}
    
    .bias-label {{
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 8px;
    }}
    
    .bias-value {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 48px;
        font-weight: 700;
        color: {accent};
        margin: 0;
        letter-spacing: 2px;
    }}
    
    .confidence-row {{
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 12px;
        margin-top: 16px;
    }}
    
    .confidence-label {{
        font-family: 'Inter', sans-serif;
        font-size: 14px;
        color: #94a3b8;
    }}
    
    .confidence-dots {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 18px;
        color: {conf_color};
        letter-spacing: 2px;
    }}
    
    .bias-explanation {{
        font-family: 'Inter', sans-serif;
        font-size: 14px;
        color: #cbd5e1;
        margin-top: 20px;
        padding: 16px;
        background: rgba(0,0,0,0.2);
        border-radius: 8px;
    }}
    </style>
    
    <div class="bias-card">
        <p class="bias-label">Today's Bias</p>
        <p class="bias-value">{bias.value}</p>
        <div class="confidence-row">
            <span class="confidence-label">Confidence:</span>
            <span class="confidence-dots">{conf_dots}</span>
            <span class="confidence-label">{confidence.value}</span>
        </div>
        <p class="bias-explanation">{explanation}</p>
    </div>
    """, unsafe_allow_html=True)


def render_vix_zone_ladder(zone: VIXZone):
    """Render VIX zone visualization"""
    
    st.markdown("""
    <style>
    .zone-container {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
    }
    
    .zone-title {
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 16px;
    }
    
    .zone-level {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 14px;
    }
    
    .zone-extension { background: #1e293b; color: #64748b; }
    .zone-top { background: #065f46; color: #10b981; border: 1px solid #10b981; }
    .zone-bottom { background: #7f1d1d; color: #ef4444; border: 1px solid #ef4444; }
    .zone-current { background: #1e40af; color: #60a5fa; border: 2px solid #60a5fa; }
    
    .zone-stats {
        display: flex;
        justify-content: space-between;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid #334155;
    }
    
    .zone-stat {
        text-align: center;
    }
    
    .zone-stat-label {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
    }
    
    .zone-stat-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 18px;
        font-weight: 600;
        color: #f8fafc;
    }
    
    .potential-high { color: #10b981; }
    .potential-normal { color: #60a5fa; }
    .potential-low { color: #f59e0b; }
    </style>
    """, unsafe_allow_html=True)
    
    potential_class = {
        "HIGH": "potential-high",
        "NORMAL": "potential-normal",
        "LOW": "potential-low"
    }.get(zone.potential, "potential-normal")
    
    potential_icon = {
        "HIGH": "🔥",
        "NORMAL": "✓",
        "LOW": "⚠️"
    }.get(zone.potential, "")
    
    # Build zone levels
    levels_html = ""
    for ext in [2, 1]:
        levels_html += f'<div class="zone-level zone-extension"><span>+{ext}</span><span>{zone.get_extension(ext):.2f}</span></div>'
    
    levels_html += f'<div class="zone-level zone-top"><span>TOP</span><span>{zone.top:.2f}</span></div>'
    levels_html += f'<div class="zone-level zone-current"><span>VIX NOW</span><span>{zone.current:.2f}</span></div>'
    levels_html += f'<div class="zone-level zone-bottom"><span>BOTTOM</span><span>{zone.bottom:.2f}</span></div>'
    
    for ext in [-1, -2]:
        levels_html += f'<div class="zone-level zone-extension"><span>{ext}</span><span>{zone.get_extension(ext):.2f}</span></div>'
    
    st.markdown(f"""
    <div class="zone-container">
        <p class="zone-title">VIX Zone Ladder</p>
        {levels_html}
        <div class="zone-stats">
            <div class="zone-stat">
                <p class="zone-stat-label">Zone Size</p>
                <p class="zone-stat-value">{zone.size:.2f}</p>
            </div>
            <div class="zone-stat">
                <p class="zone-stat-label">Position</p>
                <p class="zone-stat-value">{zone.position_pct:.0f}%</p>
            </div>
            <div class="zone-stat">
                <p class="zone-stat-label">Potential</p>
                <p class="zone-stat-value {potential_class}">{potential_icon} {zone.potential}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_entry_checklist(zone: VIXZone, phase: TradingPhase, bias: Bias, 
                          current_price: float, best_setup: Optional[TradeSetup]):
    """Render the entry checklist"""
    
    # Determine checklist status
    checks = {
        "VIX at zone edge": zone.position_pct >= 75 or zone.position_pct <= 25,
        "Reliable timing window": phase in [TradingPhase.ZONE_LOCK, TradingPhase.RTH],
        "30-min candle closed": True,  # Would need real candle data
        "Price at rail entry": False,
        "Cone width ≥ 18 pts": False
    }
    
    # Check price at rail and cone width
    if best_setup:
        distance = abs(current_price - best_setup.entry)
        checks["Price at rail entry"] = distance <= 5.0
        checks["Cone width ≥ 18 pts"] = best_setup.cone.is_tradeable
    
    all_green = all(checks.values())
    
    st.markdown("""
    <style>
    .checklist-container {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
    }
    
    .checklist-title {
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 16px;
    }
    
    .checklist-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid #1e293b;
        font-family: 'Inter', sans-serif;
        font-size: 14px;
    }
    
    .checklist-item:last-child { border-bottom: none; }
    
    .check-icon { font-size: 18px; }
    .check-pass { color: #10b981; }
    .check-fail { color: #64748b; }
    .check-text-pass { color: #e2e8f0; }
    .check-text-fail { color: #64748b; }
    
    .checklist-status {
        margin-top: 16px;
        padding: 12px 16px;
        border-radius: 8px;
        text-align: center;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .status-ready { background: #064e3b; color: #10b981; border: 1px solid #10b981; }
    .status-waiting { background: #1e293b; color: #64748b; border: 1px solid #334155; }
    </style>
    """, unsafe_allow_html=True)
    
    items_html = ""
    for label, passed in checks.items():
        icon = "✓" if passed else "○"
        icon_class = "check-pass" if passed else "check-fail"
        text_class = "check-text-pass" if passed else "check-text-fail"
        items_html += f'<div class="checklist-item"><span class="check-icon {icon_class}">{icon}</span><span class="{text_class}">{label}</span></div>'
    
    status_class = "status-ready" if all_green else "status-waiting"
    status_text = "READY TO ENTER" if all_green else "WAITING FOR CONDITIONS"
    
    st.markdown(f"""
    <div class="checklist-container">
        <p class="checklist-title">Entry Checklist</p>
        {items_html}
        <div class="checklist-status {status_class}">{status_text}</div>
    </div>
    """, unsafe_allow_html=True)


def render_cone_table(cones: List[ConeRails], best_cone_name: str = ""):
    """Render the cone rails table"""
    
    st.markdown("""
    <style>
    .cone-table-container {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 24px;
    }
    
    .cone-table-title {
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 16px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="cone-table-container"><p class="cone-table-title">Cone Rails</p>', unsafe_allow_html=True)
    
    # Build dataframe
    data = []
    for cone in cones:
        if not cone.is_valid:
            continue
        status = "⭐ BEST" if cone.pivot.name == best_cone_name else ("✓ Valid" if cone.is_tradeable else "✗ Too Narrow")
        data.append({
            "Pivot": cone.pivot.name,
            "Ascending": f"{cone.ascending:,.2f}",
            "Descending": f"{cone.descending:,.2f}",
            "Width": f"{cone.width:.1f}",
            "Blocks": cone.blocks,
            "Status": status
        })
    
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No valid cones configured")
    
    st.markdown('</div>', unsafe_allow_html=True)


def render_trade_setup_card(setup: TradeSetup, current_price: float, engine: SPXProphetEngine):
    """Render a trade setup card"""
    
    if setup is None:
        return
    
    direction_color = "#10b981" if setup.direction == Bias.CALLS else "#ef4444"
    direction_bg = "#064e3b" if setup.direction == Bias.CALLS else "#7f1d1d"
    
    distance = current_price - setup.entry
    distance_str = f"{'+' if distance > 0 else ''}{distance:.2f}"
    
    # Calculate profits for 1 contract
    profit_50 = engine.calculate_profit(setup.reward_50_pts, 1)
    profit_75 = engine.calculate_profit(setup.reward_75_pts, 1)
    profit_100 = engine.calculate_profit(setup.reward_100_pts, 1)
    risk_dollars = engine.calculate_profit(setup.risk_pts, 1)
    
    rr_50 = profit_50 / risk_dollars if risk_dollars > 0 else 0
    
    st.markdown(f"""
    <style>
    .setup-card {{
        background: linear-gradient(135deg, {direction_bg} 0%, #1e293b 100%);
        border: 2px solid {direction_color};
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
    }}
    
    .setup-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }}
    
    .setup-title {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 20px;
        font-weight: 700;
        color: {direction_color};
    }}
    
    .setup-cone {{
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        color: #94a3b8;
    }}
    
    .setup-levels {{
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 12px;
        margin-bottom: 20px;
    }}
    
    .level-box {{
        background: rgba(0,0,0,0.3);
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }}
    
    .level-label {{
        font-family: 'Inter', sans-serif;
        font-size: 10px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }}
    
    .level-value {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 16px;
        font-weight: 600;
        color: #f8fafc;
    }}
    
    .level-entry {{ border: 1px solid {direction_color}; }}
    .level-stop {{ border: 1px solid #ef4444; }}
    
    .setup-meta {{
        display: flex;
        justify-content: space-between;
        padding-top: 16px;
        border-top: 1px solid #334155;
    }}
    
    .meta-item {{
        text-align: center;
    }}
    
    .meta-label {{
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
    }}
    
    .meta-value {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 14px;
        color: #f8fafc;
    }}
    </style>
    
    <div class="setup-card">
        <div class="setup-header">
            <span class="setup-title">{setup.direction.value} SETUP</span>
            <span class="setup-cone">{setup.cone.pivot.name} Cone</span>
        </div>
        
        <div class="setup-levels">
            <div class="level-box level-entry">
                <p class="level-label">Entry</p>
                <p class="level-value">{setup.entry:,.2f}</p>
            </div>
            <div class="level-box level-stop">
                <p class="level-label">Stop</p>
                <p class="level-value">{setup.stop:,.2f}</p>
            </div>
            <div class="level-box">
                <p class="level-label">50%</p>
                <p class="level-value">{setup.target_50:,.2f}</p>
            </div>
            <div class="level-box">
                <p class="level-label">75%</p>
                <p class="level-value">{setup.target_75:,.2f}</p>
            </div>
            <div class="level-box">
                <p class="level-label">100%</p>
                <p class="level-value">{setup.target_100:,.2f}</p>
            </div>
        </div>
        
        <div class="setup-meta">
            <div class="meta-item">
                <p class="meta-label">Distance</p>
                <p class="meta-value">{distance_str} pts</p>
            </div>
            <div class="meta-item">
                <p class="meta-label">Strike</p>
                <p class="meta-value">{setup.strike}</p>
            </div>
            <div class="meta-item">
                <p class="meta-label">Width</p>
                <p class="meta-value">{setup.cone.width:.1f} pts</p>
            </div>
            <div class="meta-item">
                <p class="meta-label">R:R @ 50%</p>
                <p class="meta-value">{rr_50:.1f}:1</p>
            </div>
            <div class="meta-item">
                <p class="meta-label">Profit @ 50%</p>
                <p class="meta-value">${profit_50:,.0f}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_position_calculator(engine: SPXProphetEngine, setup: Optional[TradeSetup]):
    """Render position sizing calculator"""
    
    st.markdown("""
    <style>
    .calc-container {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
    }
    
    .calc-title {
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 16px;
    }
    
    .calc-result {
        background: #1e293b;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        margin-top: 16px;
    }
    
    .calc-result-label {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
    }
    
    .calc-result-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 32px;
        font-weight: 700;
        color: #10b981;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="calc-container"><p class="calc-title">Position Calculator</p>', unsafe_allow_html=True)
    
    risk_budget = st.number_input("Risk Budget ($)", min_value=100, max_value=100000, value=1000, step=100)
    
    if setup:
        max_contracts = engine.calculate_max_contracts(risk_budget)
        risk_at_stop = engine.calculate_profit(setup.risk_pts, max_contracts)
        profit_50 = engine.calculate_profit(setup.reward_50_pts, max_contracts)
        profit_75 = engine.calculate_profit(setup.reward_75_pts, max_contracts)
        profit_100 = engine.calculate_profit(setup.reward_100_pts, max_contracts)
        
        st.markdown(f"""
        <div class="calc-result">
            <p class="calc-result-label">Maximum Contracts</p>
            <p class="calc-result-value">{max_contracts}</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Risk at Stop", f"${risk_at_stop:,.0f}")
            st.metric("Reward @ 75%", f"${profit_75:,.0f}")
        with col2:
            st.metric("Reward @ 50%", f"${profit_50:,.0f}")
            st.metric("Reward @ 100%", f"${profit_100:,.0f}")
    else:
        st.info("Configure a valid trade setup to calculate position size")
    
    st.markdown('</div>', unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(prior_data: Optional[Dict]) -> Tuple[VIXZone, List[Pivot]]:
    """Render sidebar inputs and return configuration"""
    
    st.sidebar.markdown("""
    <style>
    .sidebar-section {
        background: #1e293b;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }
    
    .sidebar-title {
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 12px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.sidebar.title("⚙️ Configuration")
    
    # VIX Zone Section
    st.sidebar.markdown("### VIX Zone (5pm-2am CT)")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        vix_bottom = st.number_input("Bottom", min_value=5.0, max_value=100.0, value=16.50, step=0.01, format="%.2f")
    with col2:
        vix_top = st.number_input("Top", min_value=5.0, max_value=100.0, value=16.65, step=0.01, format="%.2f")
    
    vix_current = st.sidebar.number_input("Current VIX", min_value=5.0, max_value=100.0, value=16.55, step=0.01, format="%.2f")
    
    zone = VIXZone(bottom=vix_bottom, top=vix_top, current=vix_current)
    
    # Prior Day Pivots Section
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Prior Day Pivots")
    
    use_manual = st.sidebar.checkbox("Manual Input", value=False)
    
    ct_tz = pytz.timezone('America/Chicago')
    
    if use_manual or prior_data is None:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            prior_high = st.number_input("High", min_value=1000.0, max_value=10000.0, value=6050.0, step=1.0)
        with col2:
            prior_high_time = st.time_input("High Time", value=time(11, 30))
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            prior_low = st.number_input("Low", min_value=1000.0, max_value=10000.0, value=6020.0, step=1.0)
        with col2:
            prior_low_time = st.time_input("Low Time", value=time(14, 0))
        
        prior_close = st.sidebar.number_input("Close", min_value=1000.0, max_value=10000.0, value=6035.0, step=1.0)
        
        # Create pivot timestamps (assume prior day)
        prior_date = datetime.now(ct_tz).date() - timedelta(days=1)
    else:
        prior_high = prior_data['high']
        prior_low = prior_data['low']
        prior_close = prior_data['close']
        prior_date = prior_data['date'].date() if hasattr(prior_data['date'], 'date') else prior_data['date']
        prior_high_time = time(11, 30)
        prior_low_time = time(14, 0)
        
        st.sidebar.info(f"Auto-loaded: {prior_date}")
        st.sidebar.write(f"High: {prior_high:,.2f}")
        st.sidebar.write(f"Low: {prior_low:,.2f}")
        st.sidebar.write(f"Close: {prior_close:,.2f}")
    
    # Create pivot objects
    pivots = [
        Pivot("Prior High", prior_high, ct_tz.localize(datetime.combine(prior_date, prior_high_time))),
        Pivot("Prior Low", prior_low, ct_tz.localize(datetime.combine(prior_date, prior_low_time))),
        Pivot("Prior Close", prior_close, ct_tz.localize(datetime.combine(prior_date, time(16, 0))))
    ]
    
    # Secondary Pivots Section
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Secondary Pivots (Optional)")
    
    enable_high2 = st.sidebar.checkbox("Enable High²")
    if enable_high2:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            high2_price = st.number_input("High² Price", min_value=1000.0, max_value=10000.0, value=6045.0, step=1.0)
        with col2:
            high2_time = st.time_input("High² Time", value=time(10, 0))
        pivots.append(Pivot("High²", high2_price, ct_tz.localize(datetime.combine(prior_date, high2_time)), is_secondary=True))
    
    enable_low2 = st.sidebar.checkbox("Enable Low²")
    if enable_low2:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            low2_price = st.number_input("Low² Price", min_value=1000.0, max_value=10000.0, value=6025.0, step=1.0)
        with col2:
            low2_time = st.time_input("Low² Time", value=time(13, 0))
        pivots.append(Pivot("Low²", low2_price, ct_tz.localize(datetime.combine(prior_date, low2_time)), is_secondary=True))
    
    return zone, pivots


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    """Main application entry point"""
    
    # Page config
    st.set_page_config(
        page_title="SPX Prophet",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Global styles
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        background: #0f172a;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif !important;
        color: #f8fafc !important;
    }
    
    p, span, div {
        font-family: 'Inter', sans-serif;
    }
    
    .stMetric {
        background: #1e293b;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #334155;
    }
    
    .stMetric label {
        color: #64748b !important;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        color: #f8fafc !important;
    }
    
    .stDataFrame {
        background: #1e293b;
        border-radius: 8px;
    }
    
    .stNumberInput input, .stTimeInput input {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
    }
    
    .stCheckbox label {
        color: #cbd5e1 !important;
    }
    
    div[data-testid="stSidebar"] {
        background: #1e293b;
    }
    
    div[data-testid="stSidebar"] .stMarkdown {
        color: #cbd5e1;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize engine
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    current_time = datetime.now(ct_tz)
    
    # Fetch market data
    spx_price, vix_price, prior_data = fetch_market_data()
    
    # Handle missing data
    if spx_price is None:
        spx_price = 6050.0
        st.warning("⚠️ Unable to fetch live SPX data. Using placeholder.")
    
    if vix_price is None:
        vix_price = 16.55
        st.warning("⚠️ Unable to fetch live VIX data. Using placeholder.")
    
    # Render sidebar and get config
    zone, pivots = render_sidebar(prior_data)
    
    # Update zone with live VIX if available
    if vix_price:
        zone = VIXZone(bottom=zone.bottom, top=zone.top, current=vix_price)
    
    # Calculate current phase
    phase = engine.get_current_phase(current_time)
    
    # Determine bias
    bias, confidence, explanation = engine.determine_bias(zone)
    
    # Calculate cones
    eval_time = ct_tz.localize(datetime.combine(current_time.date(), time(10, 0)))
    if current_time.time() > time(10, 0):
        eval_time = current_time
    
    cones = [engine.calculate_cone(pivot, eval_time) for pivot in pivots]
    
    # Find best cone (widest tradeable cone)
    valid_cones = [c for c in cones if c.is_valid and c.is_tradeable]
    best_cone = max(valid_cones, key=lambda x: x.width) if valid_cones else None
    best_cone_name = best_cone.pivot.name if best_cone else ""
    
    # Generate trade setups
    best_setup = None
    if best_cone and bias != Bias.WAIT:
        best_setup = engine.generate_trade_setup(best_cone, bias, spx_price)
    
    # ==========================================================================
    # RENDER UI
    # ==========================================================================
    
    # Header
    render_header(spx_price, vix_price, phase)
    
    # Bias Card
    render_bias_card(bias, confidence, explanation)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_vix_zone_ladder(zone)
    
    with col2:
        render_entry_checklist(zone, phase, bias, spx_price, best_setup)
    
    # Cone table
    st.markdown("---")
    render_cone_table(cones, best_cone_name)
    
    # Trade setups
    if bias != Bias.WAIT:
        st.markdown(f"### {bias.value} Setups")
        
        setup_cols = st.columns(2)
        setup_idx = 0
        
        for cone in cones:
            if cone.is_valid and cone.is_tradeable:
                setup = engine.generate_trade_setup(cone, bias, spx_price)
                if setup:
                    with setup_cols[setup_idx % 2]:
                        render_trade_setup_card(setup, spx_price, engine)
                    setup_idx += 1
    else:
        st.info("📊 VIX is mid-zone. No directional edge. Waiting for VIX to reach zone edge before displaying trade setups.")
    
    # Position Calculator
    st.markdown("---")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        render_position_calculator(engine, best_setup)
    
    with col2:
        st.markdown("### Trade Rules Reminder")
        st.markdown("""
        <div style="background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155;">
            <p style="color: #94a3b8; font-size: 14px; line-height: 1.8;">
                <strong style="color: #f8fafc;">Entry Logic:</strong> CALLS enter at descending rail (support). PUTS enter at ascending rail (resistance).<br><br>
                <strong style="color: #f8fafc;">Stop Loss:</strong> Fixed 6 points from entry.<br><br>
                <strong style="color: #f8fafc;">Targets:</strong> 50%, 75%, 100% of cone width to opposite rail.<br><br>
                <strong style="color: #f8fafc;">30-Min Close Rule:</strong> Wicks don't count. Wait for candle to CLOSE at/beyond level.<br><br>
                <strong style="color: #f8fafc;">Danger Zone (6:30-9:30 AM CT):</strong> VIX can reverse. Use extra caution.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px; color: #64748b; font-size: 12px;">
        <p>SPX PROPHET v2.0 | Institutional Grade 0DTE Decision Support System</p>
        <p>Data provided by Yahoo Finance. Not financial advice. Trade at your own risk.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
