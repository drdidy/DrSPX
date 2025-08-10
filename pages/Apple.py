# pages/Apple.py - MarketLens Pro Apple Edition
from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import io, zipfile, textwrap
import pandas as pd
import streamlit as st

# ═══════════════════════════ APP CONFIGURATION ═══════════════════════════
APP_NAME = "MarketLens Pro"
PAGE_NAME = "Apple Intelligence"
COMPANY = "Quantum Trading Systems"
VERSION = "4.1.0"

# Timezone Configuration (preserving your original logic)
CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

# Trading Parameters (preserving your exact values)
SLOPE_PER_BLOCK = 0.03545  # fixed ascending slope per 30-min
RTH_START, RTH_END = time(8, 30), time(14, 30)  # CT trading window

# Apple-Tesla Inspired Color Palette
COLORS = {
    "primary": "#007AFF",      # Apple blue
    "primary_dark": "#0056CC", # Darker blue
    "secondary": "#5AC8FA",    # Light blue
    "accent": "#FF3B30",       # Apple red
    
    "tesla_red": "#E31937",
    "tesla_black": "#171A20",
    "tesla_white": "#FFFFFF",
    "tesla_gray": "#393C41",
    
    "success": "#34C759",      # Apple green
    "warning": "#FF9500",      # Apple orange
    "error": "#FF3B30",        # Apple red
    "info": "#007AFF",         # Apple blue
    
    "bull": "#00D4AA",         # Vibrant green
    "bear": "#FF6B6B",         # Vibrant red
    "neutral": "#8B5CF6",      # Purple
    
    "gray_100": "#F3F4F6",
    "gray_200": "#E5E7EB",
    "gray_500": "#6B7280",
    "gray_800": "#1F2937",
}

# ═══════════════════════════ PREMIUM CSS DESIGN SYSTEM ═══════════════════════════
APPLE_CSS = """
<style>
/* Apple-Tesla Design System */
@import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@100;200;300;400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@100;200;300;400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@100;200;300;400;500;600;700;800&display=swap');

:root {
  /* Apple-Tesla Color System */
  --primary: #007AFF;
  --primary-dark: #0056CC;
  --secondary: #5AC8FA;
  --accent: #FF3B30;
  
  --tesla-black: #171A20;
  --tesla-gray: #393C41;
  --tesla-white: #FFFFFF;
  
  --success: #34C759;
  --warning: #FF9500;
  --error: #FF3B30;
  --bull: #00D4AA;
  --bear: #FF6B6B;
  --neutral: #8B5CF6;
  
  /* Light Theme */
  --bg-primary: #FFFFFF;
  --bg-secondary: #F2F2F7;
  --surface: #FFFFFF;
  --border: rgba(0,0,0,0.08);
  --text-primary: #000000;
  --text-secondary: #3C3C43;
  --text-tertiary: #8E8E93;
  
  /* Spacing & Layout */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-12: 3rem;
  
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-2xl: 1.5rem;
  --radius-3xl: 2rem;
  
  /* Shadows */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.06);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.08), 0 4px 6px rgba(0,0,0,0.05);
  --shadow-xl: 0 20px 25px rgba(0,0,0,0.1), 0 10px 10px rgba(0,0,0,0.04);
  
  /* Typography */
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
  --text-2xl: 1.5rem;
  --text-3xl: 1.875rem;
  --text-4xl: 2.25rem;
  
  /* Transitions */
  --transition: 250ms ease-in-out;
}

/* Base Styles */
html, body, .stApp {
  font-family: 'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

.stApp {
  background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
}

/* Hide Streamlit Elements */
#MainMenu, footer, .stDeployButton, header[data-testid="stHeader"] {
  display: none !important;
}

/* Premium Hero Header */
.hero-header {
  background: linear-gradient(135deg, var(--tesla-black) 0%, var(--tesla-gray) 100%);
  border-radius: var(--radius-3xl);
  padding: var(--space-8) var(--space-6);
  margin-bottom: var(--space-8);
  text-align: center;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-xl);
  border: 1px solid rgba(255,255,255,0.1);
}

.hero-header::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(45deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%);
  backdrop-filter: blur(20px);
}

.hero-content {
  position: relative;
  z-index: 2;
}

.brand-title {
  font-size: var(--text-4xl);
  font-weight: 800;
  color: white;
  margin-bottom: var(--space-2);
  letter-spacing: -0.02em;
}

.brand-subtitle {
  font-size: var(--text-xl);
  color: rgba(255,255,255,0.8);
  margin-bottom: var(--space-3);
  font-weight: 400;
}

.brand-meta {
  font-size: var(--text-sm);
  color: rgba(255,255,255,0.6);
  font-weight: 300;
}

/* Premium Cards */
.premium-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  padding: var(--space-6);
  margin: var(--space-4) 0;
  box-shadow: var(--shadow-lg);
  transition: all var(--transition);
  position: relative;
  overflow: hidden;
}

.premium-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-xl);
}

.premium-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.2) 50%, transparent 100%);
}

/* Connection Status */
.connection-status {
  background: linear-gradient(90deg, var(--success) 0%, #2DD4BF 100%);
  border-radius: var(--radius-xl);
  padding: var(--space-4) var(--space-6);
  margin: var(--space-4) 0;
  color: white;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  box-shadow: var(--shadow-md);
}

.connection-status.error {
  background: linear-gradient(90deg, var(--error) 0%, #F87171 100%);
}

.connection-dot {
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite alternate;
}

@keyframes pulse {
  0% { opacity: 1; }
  100% { opacity: 0.6; }
}

/* Section Headers */
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

/* Anchor Tiles Grid */
.anchors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--space-6);
  margin: var(--space-6) 0;
}

.anchor-tile {
  background: linear-gradient(135deg, var(--surface) 0%, rgba(255,255,255,0.5) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  text-align: center;
  transition: all var(--transition);
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-md);
}

.anchor-tile:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: var(--shadow-xl);
  border-color: var(--primary);
}

.anchor-icon {
  font-size: var(--text-3xl);
  margin-bottom: var(--space-3);
  display: block;
}

.anchor-value {
  font-size: var(--text-4xl);
  font-weight: 800;
  margin-bottom: var(--space-2);
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: -0.02em;
}

.anchor-label {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-2);
}

.anchor-meta {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 400;
}

/* Status Badges */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-xl);
  font-weight: 600;
  font-size: var(--text-base);
  margin: var(--space-2);
  transition: all var(--transition);
}

.status-badge.strong {
  background: rgba(52, 199, 89, 0.1);
  color: var(--success);
  border: 1px solid rgba(52, 199, 89, 0.2);
}

.status-badge.weak {
  background: rgba(255, 59, 48, 0.1);
  color: var(--error);
  border: 1px solid rgba(255, 59, 48, 0.2);
}

.status-badge.neutral {
  background: rgba(139, 92, 246, 0.1);
  color: var(--neutral);
  border: 1px solid rgba(139, 92, 246, 0.2);
}

/* Next Slot Indicator */
.next-slot {
  background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
  color: white;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-xl);
  font-weight: 600;
  margin: var(--space-3) 0;
  display: inline-block;
  box-shadow: var(--shadow-md);
}

/* Alert Card */
.alert-card {
  background: rgba(255, 149, 0, 0.1);
  border: 1px solid rgba(255, 149, 0, 0.3);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  margin: var(--space-4) 0;
  color: var(--warning);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

/* Enhanced Buttons */
.stButton > button, .stDownloadButton > button {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%) !important;
  color: white !important;
  border: none !important;
  border-radius: var(--radius-xl) !important;
  padding: var(--space-3) var(--space-6) !important;
  font-weight: 600 !important;
  font-size: var(--text-base) !important;
  transition: all var(--transition) !important;
  box-shadow: var(--shadow-md) !important;
}

.stButton > button:hover, .stDownloadButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: var(--shadow-xl) !important;
}

/* Enhanced Sidebar */
.css-1d391kg {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}

/* Data Tables */
.stDataFrame {
  border-radius: var(--radius-xl) !important;
  overflow: hidden !important;
  box-shadow: var(--shadow-lg) !important;
  border: 1px solid var(--border) !important;
}

/* Responsive Design */
@media (max-width: 768px) {
  .anchors-grid {
    grid-template-columns: 1fr;
  }
  
  .hero-header {
    padding: var(--space-6) var(--space-4);
  }
  
  .brand-title {
    font-size: var(--text-3xl);
  }
}
</style>
"""

# ═══════════════════════════ ALPACA DATA ENGINE ═══════════════════════════
# (Preserving your exact Alpaca integration logic)

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

def _alpaca_client():
    """Create Alpaca client for live account (preserving your exact logic)"""
    try:
        return StockHistoricalDataClient(
            api_key=st.secrets["alpaca"]["key"],
            secret_key=st.secrets["alpaca"]["secret"],
            sandbox=False  # Live account = sandbox False
        )
    except Exception as e:
        st.error(f"Failed to create Alpaca client: {str(e)}")
        return None

def test_alpaca_connection():
    """Test if Alpaca connection is working (preserving your exact logic)"""
    try:
        client = _alpaca_client()
        if client is None:
            return False
            
        # Test with data from 1 hour ago (much more recent)
        end_dt = datetime.now(tz=ET) - timedelta(hours=1)
        start_dt = end_dt - timedelta(minutes=30)
        
        req = StockBarsRequest(
            symbol_or_symbols="AAPL",
            timeframe=TimeFrame.Minute,
            start=start_dt,
            end=end_dt,
            limit=5
        )
        bars = client.get_stock_bars(req)
        
        if hasattr(bars, 'df') and not bars.df.empty:
            return {"status": "success", "message": "Market data connection verified"}
        else:
            return {"status": "warning", "message": "Connection established but limited data access"}
            
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}

@st.cache_data(ttl=300)
def fetch_history_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Fetch 1-minute historical data with enhanced error handling (preserving your exact logic)"""
    try:
        client = _alpaca_client()
        if client is None:
            return pd.DataFrame()
        
        # Much smaller buffer - only avoid data from last 30 minutes
        now = datetime.now(tz=ET)
        if end_dt > now - timedelta(minutes=30):  # If requesting data less than 30 minutes old
            end_dt = now - timedelta(minutes=30)  # Push it back to 30 minutes ago
            
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start_dt.astimezone(ET),
            end=end_dt.astimezone(ET),
            limit=10_000
        )
        
        bars = client.get_stock_bars(req)
        
        if not hasattr(bars, 'df'):
            return pd.DataFrame()
            
        df = bars.df.reset_index()
        
        if df.empty:
            return pd.DataFrame()
            
        if "symbol" in df.columns:
            df = df[df["symbol"] == symbol]
            
        df.rename(columns={
            "timestamp": "dt",
            "open": "Open",
            "high": "High", 
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }, inplace=True)
        
        df["dt"] = pd.to_datetime(df["dt"], utc=True).dt.tz_convert(CT)
        result = df[["dt", "Open", "High", "Low", "Close", "Volume"]].sort_values("dt")
        
        return result
        
    except Exception as e:
        # Only show error if it's a real problem, not just empty data
        if "no data" not in str(e).lower():
            st.error(f"Data fetch error: {str(e)}")
        return pd.DataFrame()

def restrict_rth_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Convert 1m data to 30m bars during regular trading hours (preserving your exact logic)"""
    if df_1m.empty: 
        return df_1m
        
    try:
        df = df_1m.set_index("dt").sort_index()
        ohlc = df[["Open", "High", "Low", "Close", "Volume"]].resample("30min", label="right", closed="right").agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
        }).dropna(subset=["Open", "High", "Low", "Close"]).reset_index()
        
        ohlc["Time"] = ohlc["dt"].dt.strftime("%H:%M")
        ohlc = ohlc[(ohlc["Time"] >= "08:30") & (ohlc["Time"] <= "14:30")].copy()
        return ohlc
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=180)
def fetch_day_open(symbol: str, d: date) -> float | None:
    """Fetch opening price for a specific day (preserving your exact logic)"""
    try:
        start_dt = datetime.combine(d, time(7, 0), tzinfo=CT)
        end_dt = datetime.combine(d, time(15, 0), tzinfo=CT)
        df = fetch_history_1m(symbol, start_dt, end_dt)
        
        if df.empty: 
            return None
            
        df = df.set_index("dt").sort_index()
        
        try:
            bar = df.loc[df.index.indexer_between_time("08:30", "08:30")]
            if bar.empty: 
                return None
            return float(bar.iloc[0]["Open"])
        except Exception:
            return None
    except Exception:
        return None

# ═══════════════════════════ TRADING LOGIC HELPERS ═══════════════════════════
# (Preserving your exact calculation logic)

def make_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    """Generate time slots (preserving your exact logic)"""
    cur = datetime(2025, 1, 1, start.hour, start.minute)
    stop = datetime(2025, 1, 1, end.hour, end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

SLOTS = make_slots(RTH_START, RTH_END)

def blocks_between(t1: datetime, t2: datetime) -> int:
    """Calculate blocks between times (preserving your exact logic)"""
    if t2 < t1: 
        t1, t2 = t2, t1
    blocks, cur = 0, t1
    while cur < t2:
        if cur.hour != 16:
            blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def project_line(base_price: float, base_dt: datetime, target_dt: datetime) -> float:
    """Project line price (preserving your exact logic)"""
    return base_price + SLOPE_PER_BLOCK * blocks_between(base_dt, target_dt)

def week_mon_tue_fri_for(forecast: date) -> tuple[date, date, date]:
    """Get Monday, Tuesday, Friday for a forecast date (preserving your exact logic)"""
    mon = forecast - timedelta(days=forecast.weekday())
    tue = mon + timedelta(days=1)
    fri = mon + timedelta(days=4)
    if tue >= forecast:
        mon -= timedelta(days=7)
        tue -= timedelta(days=7) 
        fri -= timedelta(days=7)
    return mon, tue, fri

# ═══════════════════════════ STREAMLIT PAGE CONFIGURATION ═══════════════════════════

st.set_page_config(
    page_title=f"{APP_NAME} — {PAGE_NAME}",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply the premium CSS
st.markdown(APPLE_CSS, unsafe_allow_html=True)

# ═══════════════════════════ WEEKLY ANCHOR COMPUTATION ═══════════════════════════
# (Preserving your exact anchor calculation logic)

@st.cache_data(ttl=600)
def compute_weekly_anchors(forecast: date):
    """Upper = max(Mon High, Tue High). Lower = min(Mon Low, Tue Low). (preserving your exact logic)"""
    try:
        mon, tue, _ = week_mon_tue_fri_for(forecast)
        start_dt = datetime.combine(mon, time(7, 0), tzinfo=CT)
        end_dt = datetime.combine(tue + timedelta(days=1), time(7, 0), tzinfo=CT)
        raw = fetch_history_1m("AAPL", start_dt, end_dt)
        
        if raw.empty: 
            return None
            
        raw["D"] = raw["dt"].dt.date
        mon_df = restrict_rth_30m(raw[raw["D"] == mon])
        tue_df = restrict_rth_30m(raw[raw["D"] == tue])
        
        if mon_df.empty or tue_df.empty: 
            return None

        midx_hi = mon_df["High"].idxmax()
        midx_lo = mon_df["Low"].idxmin()
        MonHigh = float(mon_df.loc[midx_hi, "High"])
        MonLow = float(mon_df.loc[midx_lo, "Low"])
        MonHigh_t = mon_df.loc[midx_hi, "dt"].to_pydatetime()
        MonLow_t = mon_df.loc[midx_lo, "dt"].to_pydatetime()

        tidx_hi = tue_df["High"].idxmax()
        tidx_lo = tue_df["Low"].idxmin()
        TueHigh = float(tue_df.loc[tidx_hi, "High"])
        TueLow = float(tue_df.loc[tidx_lo, "Low"])
        TueHigh_t = tue_df.loc[tidx_hi, "dt"].to_pydatetime()
        TueLow_t = tue_df.loc[tidx_lo, "dt"].to_pydatetime()

        if TueHigh >= MonHigh:
            upper_price, upper_time = TueHigh, TueHigh_t
        else:
            upper_price, upper_time = MonHigh, MonHigh_t

        if TueLow <= MonLow:
            lower_price, lower_time = TueLow, TueLow_t
        else:
            lower_price, lower_time = MonLow, MonLow_t

        return {
            "mon_date": mon, "tue_date": tue,
            "MonHigh": MonHigh, "MonLow": MonLow, "TueHigh": TueHigh, "TueLow": TueLow,
            "upper_base_price": upper_price, "upper_base_time": upper_time,
            "lower_base_price": lower_price, "lower_base_time": lower_time,
        }
    except Exception:
        return None

def channel_for_day(day: date, anchors: dict) -> pd.DataFrame:
    """Generate channel lines for a specific day (preserving your exact logic)"""
    rows = []
    for slot in SLOTS:
        h, m = map(int, slot.split(":"))
        tdt = datetime.combine(day, time(h, m), tzinfo=CT)
        up = project_line(anchors["upper_base_price"], anchors["upper_base_time"], tdt)
        lo = project_line(anchors["lower_base_price"], anchors["lower_base_time"], tdt)
        rows.append({"Time": slot, "UpperLine": round(up, 2), "LowerLine": round(lo, 2)})
    return pd.DataFrame(rows)

@st.cache_data(ttl=180)
def fetch_intraday_day_30m(symbol: str, d: date) -> pd.DataFrame:
    """Fetch 30m intraday data for a specific day (preserving your exact logic)"""
    start_dt = datetime.combine(d, time(7, 0), tzinfo=CT)
    end_dt = datetime.combine(d, time(16, 0), tzinfo=CT)
    df1m = fetch_history_1m(symbol, start_dt, end_dt)
    if df1m.empty: 
        return pd.DataFrame()
    df30 = restrict_rth_30m(df1m)[["dt", "Open", "High", "Low", "Close", "Volume"]].copy()
    df30["Time"] = df30["dt"].dt.strftime("%H:%M")
    return df30

# ═══════════════════════════ PREMIUM INTERFACE COMPONENTS ═══════════════════════════

def render_hero_header():
    """Render premium hero header with Apple-Tesla styling"""
    st.markdown(
        f"""
        <div class="hero-header">
            <div class="hero-content">
                <div class="brand-title">🍎 {APP_NAME}</div>
                <div class="brand-subtitle">{PAGE_NAME}</div>
                <div class="brand-meta">v{VERSION} • Professional AAPL Channel Analysis</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_connection_status():
    """Render premium connection status with enhanced styling"""
    st.markdown('<div class="section-header">🔌 Market Data Connection</div>', unsafe_allow_html=True)
    
    connection_result = test_alpaca_connection()
    
    if connection_result["status"] == "success":
        st.markdown(
            f"""
            <div class="connection-status">
                <div class="connection-dot"></div>
                <div>
                    <div style="font-weight:700;font-size:var(--text-lg);">✅ {connection_result["message"]}</div>
                    <div style="opacity:0.9;font-size:var(--text-sm);">Live market data • Alpaca API • Real-time processing</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return True
    elif connection_result["status"] == "warning":
        st.markdown(
            f"""
            <div class="connection-status" style="background:linear-gradient(90deg, var(--warning) 0%, #F59E0B 100%);">
                <div class="connection-dot"></div>
                <div>
                    <div style="font-weight:700;font-size:var(--text-lg);">⚠️ {connection_result["message"]}</div>
                    <div style="opacity:0.9;font-size:var(--text-sm);">Limited data access • Some features may be restricted</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return True
    else:
        st.markdown(
            f"""
            <div class="connection-status error">
                <div class="connection-dot"></div>
                <div>
                    <div style="font-weight:700;font-size:var(--text-lg);">❌ {connection_result["message"]}</div>
                    <div style="opacity:0.9;font-size:var(--text-sm);">Check API credentials • Verify network connection</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return False

def render_premium_sidebar():
    """Render enhanced sidebar with Apple-Tesla styling"""
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center;padding:var(--space-4);margin-bottom:var(--space-4);
                 background:linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
                 border-radius:var(--radius-2xl);color:white;">
                <div style="font-size:var(--text-2xl);font-weight:800;margin-bottom:var(--space-1);">🍎</div>
                <div style="font-weight:600;">Apple Intelligence</div>
                <div style="opacity:0.8;font-size:var(--text-sm);">Channel Analysis</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown('<div class="section-header" style="font-size:var(--text-lg);">📅 Session Configuration</div>', unsafe_allow_html=True)
        
        forecast_date = st.date_input(
            "Target Trading Session", 
            value=date.today() + timedelta(days=1),
            help="Select the date for channel analysis"
        )
        
        # Quick date selection buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📅 Today", use_container_width=True):
                forecast_date = date.today()
                st.rerun()
        with col2:
            if st.button("➡️ Next Day", use_container_width=True):
                wd = date.today().weekday()
                delta = 1 if wd < 4 else (7 - wd)
                forecast_date = date.today() + timedelta(days=delta)
                st.rerun()
        
        st.markdown('<div style="margin:var(--space-4) 0;"></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="section-header" style="font-size:var(--text-lg);">🎯 Detection Parameters</div>', unsafe_allow_html=True)
        
        tolerance = st.slider(
            "Touch Tolerance ($)", 
            min_value=0.01, 
            max_value=0.60, 
            value=0.05, 
            step=0.01,
            help="Price tolerance for line touch detection"
        )
        
        st.markdown(
            f"""
            <div style="background:rgba(0,122,255,0.1);padding:var(--space-3);border-radius:var(--radius-lg);margin-top:var(--space-3);">
                <div style="font-weight:600;color:var(--primary);margin-bottom:var(--space-2);">💡 Strategy Notes</div>
                <div style="color:var(--text-secondary);font-size:var(--text-sm);line-height:1.5;">
                    • Touch: Low ≤ Line ≤ High ± ${tolerance:.2f}<br>
                    • Close Above: Close ≥ Line<br>
                    • Channel Slope: +{SLOPE_PER_BLOCK:.5f}/block
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        return forecast_date, tolerance

def render_weekly_anchors(anchors: dict):
    """Render premium weekly anchors display"""
    if not anchors:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">📊</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">Anchor Data Unavailable</div>
                <div style="color:var(--text-tertiary);">Could not compute Monday/Tuesday anchors for AAPL. Try another date or check market data availability.</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return False
    
    st.markdown('<div class="section-header">📊 Weekly Channel Anchors</div>', unsafe_allow_html=True)
    
    st.markdown(
        f"""
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Channel computation based on Monday/Tuesday extremes with ascending slope projection.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Anchor tiles grid
    st.markdown('<div class="anchors-grid">', unsafe_allow_html=True)
    
    # Monday Anchor Tile
    st.markdown(
        f"""
        <div class="anchor-tile">
            <div class="anchor-icon">📅</div>
            <div class="anchor-label">Monday Session</div>
            <div class="anchor-value" style="color:{COLORS['success']};">${anchors['MonHigh']:.2f}</div>
            <div class="anchor-meta">High: ${anchors['MonHigh']:.2f} • Low: ${anchors['MonLow']:.2f}</div>
            <div style="margin-top:var(--space-2);font-size:var(--text-sm);color:var(--text-tertiary);">
                {anchors['mon_date']}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Tuesday Anchor Tile
    st.markdown(
        f"""
        <div class="anchor-tile">
            <div class="anchor-icon">📈</div>
            <div class="anchor-label">Tuesday Session</div>
            <div class="anchor-value" style="color:{COLORS['primary']};">${anchors['TueHigh']:.2f}</div>
            <div class="anchor-meta">High: ${anchors['TueHigh']:.2f} • Low: ${anchors['TueLow']:.2f}</div>
            <div style="margin-top:var(--space-2);font-size:var(--text-sm);color:var(--text-tertiary);">
                {anchors['tue_date']}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Channel configuration summary
    upper_anchor = "Tuesday" if anchors['TueHigh'] >= anchors['MonHigh'] else "Monday"
    lower_anchor = "Tuesday" if anchors['TueLow'] <= anchors['MonLow'] else "Monday"
    
    st.markdown(
        f"""
        <div class="premium-card" style="background:rgba(0,122,255,0.05);border-color:var(--primary);">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-4);">
                <div>
                    <div style="font-weight:700;color:var(--primary);margin-bottom:var(--space-2);">📊 Channel Configuration</div>
                    <div style="color:var(--text-secondary);font-size:var(--text-sm);">
                        Upper Line: {upper_anchor} High (${anchors['upper_base_price']:.2f})<br>
                        Lower Line: {lower_anchor} Low (${anchors['lower_base_price']:.2f})
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-weight:600;">Slope: +{SLOPE_PER_BLOCK:.5f}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Per 30-min block</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    return True

def render_session_status(forecast_date: date, anchors: dict, channel_df: pd.DataFrame):
    """Render premium session status with open analysis"""
    st.markdown('<div class="section-header">📈 Session Status Analysis</div>', unsafe_allow_html=True)
    
    # Get opening price
    open_px = fetch_day_open("AAPL", forecast_date)
    
    # Determine session status
    if open_px is not None and "08:30" in set(channel_df["Time"]):
        lower0830 = float(channel_df.loc[channel_df["Time"] == "08:30", "LowerLine"].iloc[0])
        upper0830 = float(channel_df.loc[channel_df["Time"] == "08:30", "UpperLine"].iloc[0])
        
        if open_px < lower0830:
            status_type = "weak"
            status_text = "Weak Opening"
            status_desc = "Opened below channel - potential downside bias"
            status_color = COLORS['error']
        elif open_px > upper0830:
            status_type = "strong"
            status_text = "Strong Opening"
            status_desc = "Opened above channel - potential upside bias"
            status_color = COLORS['success']
        else:
            status_type = "neutral"
            status_text = "Neutral Opening"
            status_desc = "Opened inside channel - range-bound potential"
            status_color = COLORS['neutral']
    else:
        status_type = "neutral"
        status_text = "Opening Analysis Unavailable"
        status_desc = "No opening price data available for analysis"
        status_color = COLORS['neutral']
        open_px = None
    
    # Next slot calculation
    def get_next_slot():
        now = datetime.now(tz=CT).strftime("%H:%M")
        for slot in SLOTS:
            if slot >= now:
                return slot
        return SLOTS[0]
    
    next_slot = get_next_slot()
    next_row = channel_df.loc[channel_df["Time"] == next_slot].iloc[0] if next_slot in set(channel_df["Time"]) else None
    
    # Render status display
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown(
            f"""
            <div class="premium-card">
                <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4);">
                    <div style="width:12px;height:12px;background:{status_color};border-radius:50%;"></div>
                    <div style="font-weight:700;color:{status_color};font-size:var(--text-xl);">{status_text}</div>
                </div>
                <div style="color:var(--text-secondary);margin-bottom:var(--space-3);">{status_desc}</div>
                {"<div style='font-family:\"JetBrains Mono\",monospace;font-weight:600;'>Open: $" + f"{open_px:.2f}</div>" if open_px else ""}
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        if next_row is not None:
            st.markdown(
                f"""
                <div class="premium-card" style="background:rgba(0,122,255,0.05);">
                    <div style="font-weight:700;color:var(--primary);margin-bottom:var(--space-3);">🎯 Next Slot: {next_slot}</div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:var(--space-2);">
                        <span style="color:var(--text-secondary);">Upper Line:</span>
                        <span style="font-family:'JetBrains Mono',monospace;font-weight:600;">${next_row["UpperLine"]:.2f}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;">
                        <span style="color:var(--text-secondary);">Lower Line:</span>
                        <span style="font-family:'JetBrains Mono',monospace;font-weight:600;">${next_row["LowerLine"]:.2f}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    
    return open_px, status_type

# ═══════════════════════════ MAIN INTERFACE RENDERING ═══════════════════════════

# Render hero header
render_hero_header()

# Test connection and render status
connection_ok = render_connection_status()

if not connection_ok:
    st.stop()

# Render premium sidebar
forecast_date, tolerance = render_premium_sidebar()

# Compute weekly anchors
weekly_anchors = compute_weekly_anchors(forecast_date)

# Render weekly anchors
anchors_ok = render_weekly_anchors(weekly_anchors)

if not anchors_ok:
    st.stop()

# Generate channel data for the forecast date
channel_df = channel_for_day(forecast_date, weekly_anchors)

# Render session status
open_price, session_status = render_session_status(forecast_date, weekly_anchors, channel_df)

# ═══════════════════════════ ADVANCED ANALYTICS & SIGNALS ═══════════════════════════

def first_touch_close_above(day: date, anchors: dict, tolerance: float):
    """
    Return first event where bar touches a line AND closes above it.
    Touch: Low<=Line<=High ± tol. Close condition: Close>=Line.
    (Preserving your exact detection logic)
    """
    intr = fetch_intraday_day_30m("AAPL", day)
    if intr.empty:
        return {"Day": day, "Time": "—", "Line": "—", "Close": "—", "Line Px": "—", "Δ": "—"}

    ch = channel_for_day(day, anchors)
    merged = pd.merge(intr, ch, on="Time", how="inner")

    for _, r in merged.iterrows():
        lo_line = r["LowerLine"]
        hi_line = r["UpperLine"]
        lo, hi, close = r["Low"], r["High"], r["Close"]

        # Lower line: touch + close above
        if (lo - tolerance) <= lo_line <= (hi + tolerance) and close >= lo_line - 1e-9:
            delta = round(float(close - lo_line), 2)
            return {"Day": day, "Time": r["Time"], "Line": "Lower",
                    "Close": round(float(close), 2), "Line Px": round(float(lo_line), 2), "Δ": delta}

        # Upper line: touch + close above (breakout)
        if (lo - tolerance) <= hi_line <= (hi + tolerance) and close >= hi_line - 1e-9:
            delta = round(float(close - hi_line), 2)
            return {"Day": day, "Time": r["Time"], "Line": "Upper",
                    "Close": round(float(close), 2), "Line Px": round(float(hi_line), 2), "Δ": delta}

    return {"Day": day, "Time": "—", "Line": "—", "Close": "—", "Line Px": "—", "Δ": "—"}

def signals_mon_to_fri(forecast: date, anchors: dict, tolerance: float) -> pd.DataFrame:
    """Generate signals for Monday to Friday (preserving your exact logic)"""
    mon, _, _ = week_mon_tue_fri_for(forecast)
    days = [mon + timedelta(days=i) for i in range(5)]
    rows = [first_touch_close_above(d, anchors, tolerance) for d in days]
    df = pd.DataFrame(rows)
    df["Day"] = df["Day"].apply(lambda d: d.strftime("%a %Y-%m-%d") if isinstance(d, date) else d)
    return df

def render_signals_analysis(forecast_date: date, anchors: dict, tolerance: float):
    """Render premium signals analysis section"""
    st.markdown(
        """
        <div class="section-header">🎯 Signal Analysis (Mon–Fri)</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Professional detection of touch + close above signals across the trading week.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    with st.spinner("🔄 Analyzing signals across trading week..."):
        signals_df = signals_mon_to_fri(forecast_date, anchors, tolerance)
    
    # Enhanced signals display
    st.markdown(
        f"""
        <div class="premium-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-4);">
                <div>
                    <div style="font-weight:700;color:var(--primary);font-size:var(--text-xl);">
                        📊 Weekly Signal Detection
                    </div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                        Touch tolerance: ${tolerance:.2f} • Close above condition required
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-weight:600;">Detection Rule</div>
                    <div style="color:var(--text-secondary);font-size:var(--text-sm);">Touch + Close Above</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Style the dataframe with professional formatting
    def style_delta_column(s: pd.Series):
        styled = []
        for v in s:
            if isinstance(v, (int, float)) and v == v:  # not NaN
                styled.append("color:#34C759;font-weight:600")  # positive = green
            else:
                styled.append("color:var(--text-tertiary)")
        return styled
    
    # Apply styling to the signals dataframe
    styled_signals = signals_df.style.apply(style_delta_column, subset=["Δ"])
    
    st.dataframe(
        styled_signals,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Day': st.column_config.TextColumn('Trading Day', width='medium'),
            'Time': st.column_config.TextColumn('Time', width='small'),
            'Line': st.column_config.TextColumn('Line Type', width='small'),
            'Close': st.column_config.NumberColumn('Close Price', format='$%.2f'),
            'Line Px': st.column_config.NumberColumn('Line Price', format='$%.2f'),
            'Δ': st.column_config.NumberColumn('Delta', format='$%.2f', help='Close - Line Price')
        }
    )
    
    # Signal analytics summary
    valid_signals = signals_df[signals_df['Time'] != '—']
    total_signals = len(valid_signals)
    
    if total_signals > 0:
        avg_delta = valid_signals['Δ'].mean() if valid_signals['Δ'].notna().any() else 0
        upper_signals = len(valid_signals[valid_signals['Line'] == 'Upper'])
        lower_signals = len(valid_signals[valid_signals['Line'] == 'Lower'])
        
        # Analytics grid
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Total Signals", total_signals, delta=f"Out of 5 days")
        
        with col2:
            st.metric("📈 Upper Signals", upper_signals, delta="Breakout signals")
        
        with col3:
            st.metric("📉 Lower Signals", lower_signals, delta="Support signals")
        
        with col4:
            if avg_delta > 0:
                st.metric("💰 Avg Delta", f"${avg_delta:.2f}", delta="Above line")
            else:
                st.metric("💰 Avg Delta", "—")
    
    return signals_df

# ═══════════════════════════ APPROACHING ALERTS SYSTEM ═══════════════════════════

def approaching_alert_for_current_bar(d: date, anchors: dict, tolerance: float) -> str | None:
    """
    Soft pre-close alert: approaching a line (no streaming)
    (Preserving your exact alert logic)
    """
    try:
        now_ct = datetime.now(tz=CT)
        if now_ct.date() != d: 
            return None
        if not (RTH_START <= now_ct.time() <= RTH_END): 
            return None
        # in last ~3 minutes of the current 30-min bar
        if now_ct.minute % 30 < 27: 
            return None

        # Determine current slot end (the right-closed bar)
        minute_bucket = 30 if now_ct.minute >= 30 else 0
        slot_end = now_ct.replace(minute=30 if minute_bucket == 30 else 0, second=0, microsecond=0)
        # If we're in the last minutes leading to the *next* slot end, preview that slot's line values
        if now_ct.minute >= 27:
            # For preview, use the upcoming slot end (ceil to next :00/:30)
            add = 30 - (now_ct.minute % 30)
            slot_end = now_ct + timedelta(minutes=add)
            slot_end = slot_end.replace(second=0, microsecond=0)

        # Build line levels for that slot
        up = project_line(anchors["upper_base_price"], anchors["upper_base_time"], slot_end)
        lo = project_line(anchors["lower_base_price"], anchors["lower_base_time"], slot_end)

        # Use data from 30 minutes ago instead of 1 hour to be more current
        start_dt = now_ct - timedelta(minutes=45)
        end_dt = now_ct - timedelta(minutes=30)
        df = fetch_history_1m("AAPL", start_dt, end_dt)
        if df.empty: 
            return "warn|⚠️ Cannot get recent price data"
        px = float(df.iloc[-1]["Close"])

        note = []
        if abs(px - lo) <= tolerance:
            note.append(f"near Lower {lo:.2f} (Δ {px - lo:+.2f})")
        if abs(px - up) <= tolerance:
            note.append(f"near Upper {up:.2f} (Δ {px - up:+.2f})")
        if not note: 
            return None
        return f"approaching|Approaching: {' • '.join(note)} (~30min delay)"
    except Exception as e:
        return f"error|⚠️ Alert unavailable: {str(e)}"

def render_live_alerts(forecast_date: date, anchors: dict, tolerance: float):
    """Render live approaching alerts with premium styling"""
    alert_result = approaching_alert_for_current_bar(forecast_date, anchors, tolerance)
    
    if alert_result:
        alert_type, alert_message = alert_result.split("|", 1)
        
        if alert_type == "approaching":
            st.markdown(
                f"""
                <div class="alert-card">
                    <div style="font-size:1.2rem;">⚠️</div>
                    <div>
                        <div style="font-weight:700;margin-bottom:var(--space-1);">Price Alert</div>
                        <div style="font-size:var(--text-sm);">{alert_message}</div>
                        <div style="font-size:var(--text-xs);opacity:0.8;margin-top:var(--space-1);">
                            Provisional alert • Confirms on bar close
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        elif alert_type in ["warn", "error"]:
            st.markdown(
                f"""
                <div style="background:rgba(255,59,48,0.1);border:1px solid rgba(255,59,48,0.3);
                     border-radius:var(--radius-lg);padding:var(--space-3);margin:var(--space-4) 0;
                     color:var(--error);display:flex;align-items:center;gap:var(--space-2);">
                    <div>{alert_message}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

# ═══════════════════════════ DAILY LINE SCHEDULE ═══════════════════════════

def render_daily_schedule(channel_df: pd.DataFrame, forecast_date: date):
    """Render daily line schedule with premium formatting"""
    st.markdown(
        """
        <div class="section-header">📅 Daily Line Schedule</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Precise upper and lower channel lines for each 30-minute trading slot.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Schedule summary
    upper_range = f"${channel_df['UpperLine'].min():.2f} - ${channel_df['UpperLine'].max():.2f}"
    lower_range = f"${channel_df['LowerLine'].min():.2f} - ${channel_df['LowerLine'].max():.2f}"
    channel_width = channel_df['UpperLine'].iloc[0] - channel_df['LowerLine'].iloc[0]
    
    st.markdown(
        f"""
        <div class="premium-card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-4);">
                <div>
                    <div style="font-weight:700;color:var(--primary);font-size:var(--text-xl);">
                        📊 Channel Analysis
                    </div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                        {len(channel_df)} time slots • {forecast_date}
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-weight:600;">Channel Width</div>
                    <div style="color:var(--success);font-size:var(--text-lg);">${channel_width:.2f}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Enhanced schedule metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-weight:700;color:var(--success);font-size:var(--text-lg);">{upper_range}</div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">UPPER RANGE</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-weight:700;color:var(--error);font-size:var(--text-lg);">{lower_range}</div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">LOWER RANGE</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col3:
        slope_direction = "Ascending" if SLOPE_PER_BLOCK > 0 else "Descending"
        st.markdown(
            f"""
            <div style="text-align:center;padding:var(--space-4);background:var(--bg-secondary);border-radius:var(--radius-lg);">
                <div style="font-weight:700;color:var(--primary);font-size:var(--text-lg);">{SLOPE_PER_BLOCK:.5f}</div>
                <div style="font-size:var(--text-xs);color:var(--text-tertiary);">SLOPE/BLOCK</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Enhanced dataframe display
    st.dataframe(
        channel_df[["Time", "LowerLine", "UpperLine"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            'Time': st.column_config.TextColumn('Time Slot', width='small'),
            'LowerLine': st.column_config.NumberColumn('Lower Line', format='$%.2f'),
            'UpperLine': st.column_config.NumberColumn('Upper Line', format='$%.2f')
        }
    )

# ═══════════════════════════ PREMIUM EXPORT SYSTEM ═══════════════════════════

def create_comprehensive_export_package(channel_df: pd.DataFrame, signals_df: pd.DataFrame, 
                                       anchors: dict, forecast_date: date) -> dict:
    """Create comprehensive export package with all data"""
    export_data = {}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Channel schedule export
    channel_export = channel_df.copy()
    channel_export['Forecast_Date'] = forecast_date
    channel_export['Upper_Base_Price'] = anchors['upper_base_price']
    channel_export['Lower_Base_Price'] = anchors['lower_base_price']
    channel_export['Slope_Per_Block'] = SLOPE_PER_BLOCK
    channel_export['Generated_At'] = datetime.now()
    
    export_data[f'AAPL_Channel_{forecast_date}_{timestamp}.csv'] = channel_export.to_csv(index=False).encode()
    
    # Signals export
    signals_export = signals_df.copy()
    signals_export['Forecast_Date'] = forecast_date
    signals_export['Tolerance_Used'] = tolerance  # This will be passed from the calling function
    signals_export['Generated_At'] = datetime.now()
    
    mon, tue, _ = week_mon_tue_fri_for(forecast_date)
    export_data[f'AAPL_Signals_{mon}_{tue}_{timestamp}.csv'] = signals_export.to_csv(index=False).encode()
    
    # Intraday data if available
    intraday30 = fetch_intraday_day_30m("AAPL", forecast_date)
    if not intraday30.empty:
        intraday_export = intraday30.copy()
        intraday_export['Forecast_Date'] = forecast_date
        intraday_export['Generated_At'] = datetime.now()
        export_data[f'AAPL_Intraday30_{forecast_date}_{timestamp}.csv'] = intraday_export.to_csv(index=False).encode()
    
    # Summary export
    summary_data = {
        'Export_Timestamp': [datetime.now()],
        'Forecast_Date': [forecast_date],
        'Monday_Date': [anchors.get('mon_date', '')],
        'Tuesday_Date': [anchors.get('tue_date', '')],
        'Monday_High': [anchors.get('MonHigh', 0)],
        'Monday_Low': [anchors.get('MonLow', 0)],
        'Tuesday_High': [anchors.get('TueHigh', 0)],
        'Tuesday_Low': [anchors.get('TueLow', 0)],
        'Upper_Base_Price': [anchors['upper_base_price']],
        'Lower_Base_Price': [anchors['lower_base_price']],
        'Slope_Per_Block': [SLOPE_PER_BLOCK],
        'Channel_Width': [anchors['upper_base_price'] - anchors['lower_base_price']],
        'Total_Signals': [len(signals_df[signals_df['Time'] != '—'])],
        'RTH_Start': [RTH_START.strftime('%H:%M')],
        'RTH_End': [RTH_END.strftime('%H:%M')],
        'App_Version': [VERSION]
    }
    
    summary_df = pd.DataFrame(summary_data)
    export_data[f'AAPL_Summary_{timestamp}.csv'] = summary_df.to_csv(index=False).encode()
    
    return export_data

def render_premium_export_section(channel_df: pd.DataFrame, signals_df: pd.DataFrame, 
                                 anchors: dict, forecast_date: date, tolerance: float):
    """Render premium export section with advanced options"""
    st.markdown('<div style="margin:var(--space-12) 0;"></div>', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="section-header">📤 Professional Export Center</div>
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Export comprehensive trading data and analysis for external platforms and further analysis.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Export overview
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(
            """
            <div class="premium-card">
                <div style="font-weight:700;margin-bottom:var(--space-3);color:var(--primary);">📋 Export Package Contents</div>
                <div style="color:var(--text-secondary);font-size:var(--text-sm);line-height:1.8;">
                    • <strong>Channel Schedule</strong> - Complete daily line projections<br>
                    • <strong>Signal Analysis</strong> - Touch + close above detection results<br>
                    • <strong>Intraday Data</strong> - 30-minute OHLC bars (if available)<br>
                    • <strong>Configuration Summary</strong> - All parameters and metadata<br>
                    • <strong>Professional Formatting</strong> - Excel and Python compatible
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        # Export statistics
        total_files = 4  # Channel, Signals, Summary, plus potential Intraday
        signals_count = len(signals_df[signals_df['Time'] != '—'])
        
        st.markdown(
            f"""
            <div style="background:var(--surface);padding:var(--space-4);border-radius:var(--radius-lg);border:1px solid var(--border);">
                <div style="text-align:center;margin-bottom:var(--space-3);">
                    <div style="font-size:var(--text-3xl);font-weight:800;color:var(--primary);">{total_files}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Export Files</div>
                </div>
                <div style="margin-bottom:var(--space-2);">
                    <div style="font-weight:600;">{signals_count}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Valid Signals</div>
                </div>
                <div>
                    <div style="font-weight:600;">{forecast_date}</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">Target Date</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Export actions
    col_zip, col_md = st.columns(2)
    
    with col_zip:
        if st.button("📦 Download Complete Package", use_container_width=True, type="primary"):
            with st.spinner("🔄 Creating export package..."):
                # Set tolerance in the global scope for the export function
                global tolerance_for_export
                tolerance_for_export = tolerance
                
                export_datasets = create_comprehensive_export_package(
                    channel_df, signals_df, anchors, forecast_date
                )
                
                # Create ZIP package
                zipbuf = io.BytesIO()
                with zipfile.ZipFile(zipbuf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for filename, data in export_datasets.items():
                        zf.writestr(filename, data)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                zip_filename = f"AAPL_Complete_Export_{timestamp}.zip"
                
                st.download_button(
                    "⬇️ Download ZIP Package",
                    data=zipbuf.getvalue(),
                    file_name=zip_filename,
                    mime="application/zip",
                    use_container_width=True
                )
                
                st.success(f"✅ Export package ready: {len(export_datasets)} files")
    
    with col_md:
        # Daily note export (preserving your exact logic)
        def create_daily_note() -> str:
            lines = [f"# {APP_NAME} — {PAGE_NAME} ({forecast_date})", "",
                     f"- Monday High/Low: {anchors['MonHigh']:.2f} / {anchors['MonLow']:.2f}",
                     f"- Tuesday High/Low: {anchors['TueHigh']:.2f} / {anchors['TueLow']:.2f}", ""]
            
            lines.append("## Signals (Mon–Fri) — Touch + Close Above")
            for _, r in signals_df.iterrows():
                lines.append(f"- {r['Day']}: {r['Line']} @ {r['Time']} | Close={r['Close']} Line={r['Line Px']} Δ={r['Δ']}")
            
            return "\n".join(lines)
        
        st.download_button(
            "📝 Export Daily Note",
            data=create_daily_note(),
            file_name=f"MarketLens_Apple_{forecast_date}.md",
            mime="text/markdown",
            use_container_width=True
        )

# ═══════════════════════════ INDIVIDUAL CSV EXPORTS ═══════════════════════════

def render_individual_exports(channel_df: pd.DataFrame, signals_df: pd.DataFrame, anchors: dict):
    """Render individual file export options"""
    st.markdown("### 📁 Individual File Exports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Channel CSV
        channel_csv = channel_df.to_csv(index=False)
        st.download_button(
            "📊 Channel Schedule",
            data=channel_csv,
            file_name=f"AAPL_Channel_{forecast_date}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Signals CSV
        signals_csv = signals_df.to_csv(index=False)
        mon, tue, _ = week_mon_tue_fri_for(forecast_date)
        st.download_button(
            "🎯 Signal Analysis",
            data=signals_csv,
            file_name=f"AAPL_Signals_{mon}_{tue}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col3:
        # Intraday data if available
        intraday30 = fetch_intraday_day_30m("AAPL", forecast_date)
        if not intraday30.empty:
            intraday_csv = intraday30.to_csv(index=False)
            st.download_button(
                "📈 Intraday 30m",
                data=intraday_csv,
                file_name=f"AAPL_Intraday30_{forecast_date}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button(
                "📈 No Intraday Data",
                disabled=True,
                use_container_width=True
            )
