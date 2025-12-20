"""
SPX PROPHET - Institutional Grade 0DTE SPX Options Decision Support System
Version 2.2

A systematic approach to 0DTE SPX options trading using VIX zone analysis
and structural cone methodology.

CHANGES in v2.2:
- Fixed HTML rendering issues by using native Streamlit components
- Updated targets to 12.5%, 25%, 50% (more realistic for 0DTE)
- Simplified UI components for reliability
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
    
    # Updated target percentages (more realistic for 0DTE)
    TARGET_1_PCT = 0.125  # 12.5%
    TARGET_2_PCT = 0.25   # 25%
    TARGET_3_PCT = 0.50   # 50%
    
    # VIX Zone thresholds
    VIX_ZONE_LOW = 0.20
    VIX_ZONE_NORMAL = 0.30
    VIX_ZONE_HIGH = 0.45
    
    # Zone position thresholds
    ZONE_TOP_THRESHOLD = 0.75
    ZONE_BOTTOM_THRESHOLD = 0.25


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
    """Complete trade setup with updated target percentages"""
    direction: Bias
    cone: ConeRails
    entry: float
    stop: float
    target_12_5: float  # 12.5%
    target_25: float    # 25%
    target_50: float    # 50%
    strike: int
    risk_pts: float
    reward_12_5_pts: float
    reward_25_pts: float
    reward_50_pts: float


# =============================================================================
# CORE CALCULATION ENGINE
# =============================================================================

class SPXProphetEngine:
    """Core calculation engine for SPX Prophet"""
    
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
        else:
            return TradingPhase.MARKET_CLOSED
    
    def determine_bias(self, zone: VIXZone) -> Tuple[Bias, Confidence, str]:
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
        pivot_ct = pivot_time.astimezone(self.ct_tz)
        eval_ct = eval_time.astimezone(self.ct_tz)
        diff = eval_ct - pivot_ct
        total_minutes = diff.total_seconds() / 60
        blocks = int(total_minutes / 30)
        return max(blocks, 1)
    
    def calculate_cone(self, pivot: Pivot, eval_time: datetime) -> ConeRails:
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
        """Generate trade setup with 12.5%, 25%, 50% targets"""
        if not cone.is_tradeable or direction == Bias.WAIT:
            return None
        
        if direction == Bias.CALLS:
            entry = cone.descending
            opposite_rail = cone.ascending
        else:
            entry = cone.ascending
            opposite_rail = cone.descending
        
        move_distance = abs(opposite_rail - entry)
        
        if direction == Bias.CALLS:
            stop = entry - TradingConstants.STOP_LOSS_PTS
            target_12_5 = entry + (move_distance * TradingConstants.TARGET_1_PCT)
            target_25 = entry + (move_distance * TradingConstants.TARGET_2_PCT)
            target_50 = entry + (move_distance * TradingConstants.TARGET_3_PCT)
            strike = int(round((entry - TradingConstants.STRIKE_OTM_DISTANCE) / 5) * 5)
        else:
            stop = entry + TradingConstants.STOP_LOSS_PTS
            target_12_5 = entry - (move_distance * TradingConstants.TARGET_1_PCT)
            target_25 = entry - (move_distance * TradingConstants.TARGET_2_PCT)
            target_50 = entry - (move_distance * TradingConstants.TARGET_3_PCT)
            strike = int(round((entry + TradingConstants.STRIKE_OTM_DISTANCE) / 5) * 5)
        
        return TradeSetup(
            direction=direction,
            cone=cone,
            entry=round(entry, 2),
            stop=round(stop, 2),
            target_12_5=round(target_12_5, 2),
            target_25=round(target_25, 2),
            target_50=round(target_50, 2),
            strike=strike,
            risk_pts=TradingConstants.STOP_LOSS_PTS,
            reward_12_5_pts=round(move_distance * TradingConstants.TARGET_1_PCT, 2),
            reward_25_pts=round(move_distance * TradingConstants.TARGET_2_PCT, 2),
            reward_50_pts=round(move_distance * TradingConstants.TARGET_3_PCT, 2)
        )
    
    def calculate_profit(self, points: float, contracts: int = 1) -> float:
        return points * TradingConstants.DELTA * TradingConstants.CONTRACT_MULTIPLIER * contracts
    
    def calculate_max_contracts(self, risk_budget: float) -> int:
        risk_per_contract = self.calculate_profit(TradingConstants.STOP_LOSS_PTS, 1)
        return int(risk_budget / risk_per_contract)


# =============================================================================
# DATA FETCHING
# =============================================================================

@st.cache_data(ttl=30)
def fetch_market_data() -> Tuple[Optional[float], Optional[float], Optional[Dict]]:
    try:
        spx = yf.Ticker("^GSPC")
        vix = yf.Ticker("^VIX")
        
        spx_data = spx.history(period="1d")
        vix_data = vix.history(period="1d")
        
        spx_price = spx_data['Close'].iloc[-1] if not spx_data.empty else None
        vix_price = vix_data['Close'].iloc[-1] if not vix_data.empty else None
        
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
# UI COMPONENTS (Using native Streamlit where possible)
# =============================================================================

def render_header(spx_price: float, vix_price: float, phase: TradingPhase):
    """Render the main header using native Streamlit"""
    ct_tz = pytz.timezone('America/Chicago')
    current_time = datetime.now(ct_tz)
    
    phase_colors = {
        TradingPhase.OVERNIGHT: "🔵",
        TradingPhase.ZONE_LOCK: "🟢",
        TradingPhase.DANGER_ZONE: "🟡",
        TradingPhase.RTH: "🟢",
        TradingPhase.POST_SESSION: "⚪",
        TradingPhase.MARKET_CLOSED: "⚫"
    }
    
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1.5])
    
    with col1:
        st.markdown("## SPX PROPHET")
        st.caption("Institutional Grade 0DTE System")
    
    with col2:
        st.metric("SPX", f"{spx_price:,.2f}")
    
    with col3:
        st.metric("VIX", f"{vix_price:.2f}")
    
    with col4:
        st.metric("Time (CT)", current_time.strftime('%I:%M %p'))
        st.caption(f"{phase_colors.get(phase, '⚪')} {phase.value}")


def render_bias_card(bias: Bias, confidence: Confidence, explanation: str):
    """Render the bias determination card"""
    
    bias_emoji = {
        Bias.CALLS: "📈",
        Bias.PUTS: "📉",
        Bias.WAIT: "⏸️"
    }
    
    conf_indicator = {
        Confidence.STRONG: "●●●●",
        Confidence.MODERATE: "●●●○",
        Confidence.WEAK: "●●○○",
        Confidence.NO_TRADE: "○○○○"
    }
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("---")
        st.markdown(f"### {bias_emoji.get(bias, '')} Today's Bias: **{bias.value}**")
        st.markdown(f"Confidence: `{conf_indicator.get(confidence, '')}` {confidence.value}")
        st.info(explanation)
        st.markdown("---")


def render_vix_zone_ladder(zone: VIXZone):
    """Render VIX zone visualization using native Streamlit"""
    
    st.markdown("#### VIX Zone Ladder")
    
    potential_emoji = {"HIGH": "🔥", "NORMAL": "✓", "LOW": "⚠️"}
    
    # Create zone data
    zone_data = []
    for ext in [2, 1]:
        zone_data.append({"Level": f"+{ext}", "Price": f"{zone.get_extension(ext):.2f}", "Type": "Extension"})
    zone_data.append({"Level": "TOP", "Price": f"{zone.top:.2f}", "Type": "Zone Edge"})
    zone_data.append({"Level": "VIX NOW", "Price": f"{zone.current:.2f}", "Type": "Current"})
    zone_data.append({"Level": "BOTTOM", "Price": f"{zone.bottom:.2f}", "Type": "Zone Edge"})
    for ext in [-1, -2]:
        zone_data.append({"Level": str(ext), "Price": f"{zone.get_extension(ext):.2f}", "Type": "Extension"})
    
    df = pd.DataFrame(zone_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Stats row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Zone Size", f"{zone.size:.2f}")
    with col2:
        st.metric("Position", f"{zone.position_pct:.0f}%")
    with col3:
        st.metric("Potential", f"{potential_emoji.get(zone.potential, '')} {zone.potential}")


def render_entry_checklist(zone: VIXZone, phase: TradingPhase, bias: Bias, 
                          current_price: float, best_setup: Optional[TradeSetup]):
    """Render the entry checklist using native Streamlit"""
    
    st.markdown("#### Entry Checklist")
    
    checks = {
        "VIX at zone edge (≤25% or ≥75%)": zone.position_pct >= 75 or zone.position_pct <= 25,
        "Reliable timing window": phase in [TradingPhase.ZONE_LOCK, TradingPhase.RTH],
        "30-min candle closed": True,
        "Price at rail entry (within 5 pts)": False,
        "Cone width ≥ 18 pts": False
    }
    
    if best_setup:
        distance = abs(current_price - best_setup.entry)
        checks["Price at rail entry (within 5 pts)"] = distance <= 5.0
        checks["Cone width ≥ 18 pts"] = best_setup.cone.is_tradeable
    
    for label, passed in checks.items():
        icon = "✅" if passed else "⬜"
        st.markdown(f"{icon} {label}")
    
    all_green = all(checks.values())
    if all_green:
        st.success("**READY TO ENTER**")
    else:
        st.warning("**WAITING FOR CONDITIONS**")


def render_cone_table(cones: List[ConeRails], best_cone_name: str = ""):
    """Render the cone rails table"""
    
    st.markdown("#### Cone Rails")
    
    data = []
    for cone in cones:
        if not cone.is_valid:
            continue
        status = "⭐ BEST" if cone.pivot.name == best_cone_name else ("✓ Valid" if cone.is_tradeable else "✗ Narrow")
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


def render_trade_setup_card(setup: TradeSetup, current_price: float, engine: SPXProphetEngine):
    """Render a trade setup card using native Streamlit components"""
    
    if setup is None:
        return
    
    direction_emoji = "📈" if setup.direction == Bias.CALLS else "📉"
    
    distance = current_price - setup.entry
    distance_str = f"{'+' if distance > 0 else ''}{distance:.2f}"
    
    # Calculate profits
    profit_12_5 = engine.calculate_profit(setup.reward_12_5_pts, 1)
    profit_25 = engine.calculate_profit(setup.reward_25_pts, 1)
    risk_dollars = engine.calculate_profit(setup.risk_pts, 1)
    rr_25 = profit_25 / risk_dollars if risk_dollars > 0 else 0
    
    # Card container
    with st.container():
        st.markdown(f"##### {direction_emoji} {setup.direction.value} Setup - {setup.cone.pivot.name} Cone")
        
        # Levels row
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Entry", f"{setup.entry:,.2f}")
        with col2:
            st.metric("Stop", f"{setup.stop:,.2f}")
        with col3:
            st.metric("12.5%", f"{setup.target_12_5:,.2f}")
        with col4:
            st.metric("25%", f"{setup.target_25:,.2f}")
        with col5:
            st.metric("50%", f"{setup.target_50:,.2f}")
        
        # Stats row
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.caption(f"Distance: **{distance_str}** pts")
        with col2:
            st.caption(f"Strike: **{setup.strike}**")
        with col3:
            st.caption(f"Width: **{setup.cone.width:.1f}** pts")
        with col4:
            st.caption(f"R:R @25%: **{rr_25:.1f}:1**")
        with col5:
            st.caption(f"Profit @25%: **${profit_25:,.0f}**")
        
        st.markdown("---")


def render_position_calculator(engine: SPXProphetEngine, setup: Optional[TradeSetup]):
    """Render position sizing calculator"""
    
    st.markdown("#### Position Calculator")
    
    risk_budget = st.number_input("Risk Budget ($)", min_value=100, max_value=100000, value=1000, step=100)
    
    if setup:
        max_contracts = engine.calculate_max_contracts(risk_budget)
        risk_at_stop = engine.calculate_profit(setup.risk_pts, max_contracts)
        profit_12_5 = engine.calculate_profit(setup.reward_12_5_pts, max_contracts)
        profit_25 = engine.calculate_profit(setup.reward_25_pts, max_contracts)
        profit_50 = engine.calculate_profit(setup.reward_50_pts, max_contracts)
        
        st.markdown(f"### Max Contracts: **{max_contracts}**")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Risk at Stop", f"${risk_at_stop:,.0f}", delta=None)
            st.metric("Profit @ 25%", f"${profit_25:,.0f}", delta=f"+{profit_25/risk_at_stop:.1f}x" if risk_at_stop > 0 else None)
        with col2:
            st.metric("Profit @ 12.5%", f"${profit_12_5:,.0f}", delta=f"+{profit_12_5/risk_at_stop:.1f}x" if risk_at_stop > 0 else None)
            st.metric("Profit @ 50%", f"${profit_50:,.0f}", delta=f"+{profit_50/risk_at_stop:.1f}x" if risk_at_stop > 0 else None)
    else:
        st.info("Configure a valid trade setup to calculate position size")


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(prior_data: Optional[Dict]) -> Tuple[VIXZone, List[Pivot]]:
    """Render sidebar inputs and return configuration"""
    
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
    
    st.set_page_config(
        page_title="SPX Prophet",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Simple dark theme styling
    st.markdown("""
    <style>
    .stApp {
        background-color: #0f172a;
    }
    .stMetric {
        background-color: #1e293b;
        padding: 10px;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize engine
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    current_time = datetime.now(ct_tz)
    
    # Fetch market data
    spx_price, vix_price, prior_data = fetch_market_data()
    
    if spx_price is None:
        spx_price = 6050.0
        st.warning("⚠️ Unable to fetch live SPX data. Using placeholder.")
    
    if vix_price is None:
        vix_price = 16.55
        st.warning("⚠️ Unable to fetch live VIX data. Using placeholder.")
    
    # Render sidebar and get config
    zone, pivots = render_sidebar(prior_data)
    
    if vix_price:
        zone = VIXZone(bottom=zone.bottom, top=zone.top, current=vix_price)
    
    phase = engine.get_current_phase(current_time)
    bias, confidence, explanation = engine.determine_bias(zone)
    
    # Calculate cones
    eval_time = ct_tz.localize(datetime.combine(current_time.date(), time(10, 0)))
    if current_time.time() > time(10, 0):
        eval_time = current_time
    
    cones = [engine.calculate_cone(pivot, eval_time) for pivot in pivots]
    
    valid_cones = [c for c in cones if c.is_valid and c.is_tradeable]
    best_cone = max(valid_cones, key=lambda x: x.width) if valid_cones else None
    best_cone_name = best_cone.pivot.name if best_cone else ""
    
    best_setup = None
    if best_cone and bias != Bias.WAIT:
        best_setup = engine.generate_trade_setup(best_cone, bias, spx_price)
    
    # ==========================================================================
    # RENDER UI
    # ==========================================================================
    
    render_header(spx_price, vix_price, phase)
    render_bias_card(bias, confidence, explanation)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_vix_zone_ladder(zone)
    
    with col2:
        render_entry_checklist(zone, phase, bias, spx_price, best_setup)
    
    st.markdown("---")
    render_cone_table(cones, best_cone_name)
    
    if bias != Bias.WAIT:
        st.markdown(f"### {bias.value} Setups")
        
        for cone in cones:
            if cone.is_valid and cone.is_tradeable:
                setup = engine.generate_trade_setup(cone, bias, spx_price)
                if setup:
                    render_trade_setup_card(setup, spx_price, engine)
    else:
        st.info("📊 VIX is mid-zone. No directional edge. Waiting for VIX to reach zone edge before displaying trade setups.")
    
    st.markdown("---")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        render_position_calculator(engine, best_setup)
    
    with col2:
        st.markdown("### Trade Rules Reminder")
        st.markdown("""
        **Entry Logic:** CALLS enter at descending rail (support). PUTS enter at ascending rail (resistance).
        
        **Stop Loss:** Fixed 6 points from entry.
        
        **Targets:** 12.5%, 25%, 50% of cone width toward opposite rail.
        
        **30-Min Close Rule:** Wicks don't count. Wait for candle to CLOSE at/beyond level.
        
        **Danger Zone (6:30-9:30 AM CT):** VIX can reverse. Use extra caution.
        """)
    
    st.markdown("---")
    st.caption("SPX PROPHET v2.2 | Institutional Grade 0DTE Decision Support System | Data: Yahoo Finance | Not financial advice")


if __name__ == "__main__":
    main()
