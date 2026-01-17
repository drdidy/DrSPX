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
# CSS
# ═══════════════════════════════════════════════════════════════════════════════
STYLES="""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{--bg:#0a0a0f;--bg2:#12121a;--card:rgba(255,255,255,0.03);--border:rgba(255,255,255,0.08);--text:#fff;--text2:rgba(255,255,255,0.6);--green:#00d4aa;--red:#ff4757;--amber:#ffa502;--purple:#a855f7;--cyan:#22d3ee;--blue:#3b82f6}
.stApp{background:linear-gradient(135deg,var(--bg),var(--bg2));font-family:'DM Sans',sans-serif}
.stApp>header{background:transparent!important}
[data-testid="stSidebar"]{background:rgba(10,10,15,0.95)!important;border-right:1px solid var(--border)}
[data-testid="stSidebar"] *{color:var(--text)!important}
.hero{background:linear-gradient(135deg,rgba(168,85,247,0.15),rgba(34,211,238,0.15));border:1px solid var(--border);border-radius:20px;padding:20px 28px;margin-bottom:20px;text-align:center;backdrop-filter:blur(20px)}
.hero-title{font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:700;margin:0}
.hero-sub{font-size:13px;color:var(--text2);margin-top:4px}
.hero-price{font-family:'IBM Plex Mono',monospace;font-size:42px;font-weight:700;color:var(--cyan);margin-top:10px}
.hist-badge{background:linear-gradient(90deg,#a855f7,#3b82f6);color:white;padding:6px 16px;border-radius:20px;font-size:12px;font-weight:600;display:inline-block;margin-top:8px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:16px;margin-bottom:14px;backdrop-filter:blur(10px)}
.card-h{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.card-icon{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.card-title{font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:600}
.card-sub{font-size:11px;color:var(--text2)}
.badge{display:inline-block;padding:5px 12px;border-radius:16px;font-size:11px;font-weight:600;text-transform:uppercase}
.metric{font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:600}
.cmd-card{background:linear-gradient(135deg,rgba(168,85,247,0.1),rgba(34,211,238,0.1));border:2px solid var(--purple);border-radius:20px;padding:20px;margin-bottom:16px}
.cmd-title{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:700;color:var(--purple);margin-bottom:4px}
.phase-badge{background:var(--purple);color:white;padding:4px 12px;border-radius:12px;font-size:11px;font-weight:600}
.channel-box{background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:12px;padding:12px;margin:12px 0}
.level-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.03)}
.level-name{font-size:13px;color:var(--text2)}
.level-val{font-family:'IBM Plex Mono',monospace;font-weight:500}
.scenario{background:rgba(255,255,255,0.02);border-radius:12px;padding:14px;margin:10px 0;border-left:3px solid var(--border)}
.scenario.valid{border-left-color:var(--green)}
.scenario.invalid{border-left-color:var(--red)}
.scenario-h{font-size:12px;font-weight:600;margin-bottom:8px}
.target-box{background:rgba(0,212,170,0.1);border:1px solid rgba(0,212,170,0.3);border-radius:10px;padding:10px;margin-top:10px}
.target-h{font-size:11px;color:var(--green);font-weight:600;margin-bottom:6px}
.result-box{border-radius:12px;padding:14px;margin:12px 0}
.result-box.win{background:rgba(0,212,170,0.15);border:1px solid var(--green)}
.result-box.loss{background:rgba(255,71,87,0.15);border:1px solid var(--red)}
.result-box.neutral{background:rgba(255,165,2,0.15);border:1px solid var(--amber)}
.conf-bar{height:8px;background:rgba(255,255,255,0.1);border-radius:4px;overflow:hidden;margin:6px 0}
.conf-fill{height:100%;border-radius:4px}
.pillar{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-size:12px}
.flow-meter{height:6px;background:linear-gradient(90deg,#ff4757,#ffa502 50%,#00d4aa);border-radius:3px;position:relative;margin:8px 0}
.flow-marker{position:absolute;top:-3px;width:4px;height:12px;background:#fff;border-radius:2px;transform:translateX(-50%);box-shadow:0 0 6px rgba(255,255,255,0.5)}
.candle-display{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0}
.candle-item{text-align:center;padding:8px;background:rgba(255,255,255,0.03);border-radius:8px}
.candle-label{font-size:10px;color:var(--text2)}
.candle-val{font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:600}
.timeline{position:relative;padding-left:20px;margin:12px 0}
.timeline-item{position:relative;padding:10px 0 10px 20px;border-left:2px solid var(--border)}
.timeline-item:last-child{border-left:2px solid transparent}
.timeline-dot{position:absolute;left:-7px;top:12px;width:12px;height:12px;border-radius:50%;background:var(--border)}
.timeline-dot.active{background:var(--green)}
.timeline-dot.hit{background:var(--green)}
.timeline-dot.miss{background:var(--red)}
.footer{text-align:center;padding:16px;color:var(--text2);font-size:11px;border-top:1px solid var(--border);margin-top:20px}
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
# DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300,show_spinner=False)
def fetch_es_candles_range(start_date,end_date,interval="30m"):
    """Fetch ES candles for a specific date range"""
    for attempt in range(3):
        try:
            es=yf.Ticker("ES=F")
            data=es.history(start=start_date,end=end_date+timedelta(days=1),interval=interval)
            if data is not None and not data.empty:
                return data
        except Exception as e:
            time_module.sleep(1)
    return None

@st.cache_data(ttl=120,show_spinner=False)
def fetch_es_candles(days=7):
    """Fetch recent ES candles"""
    for attempt in range(3):
        try:
            es=yf.Ticker("ES=F")
            data=es.history(period=f"{days}d",interval="30m")
            if data is not None and not data.empty:
                return data
        except:
            time_module.sleep(1)
    return None

@st.cache_data(ttl=60,show_spinner=False)
def fetch_spx_polygon():
    try:
        url=f"{POLYGON_BASE}/v3/snapshot?ticker.any_of=I:SPX&apiKey={POLYGON_KEY}"
        r=requests.get(url,timeout=10)
        if r.status_code==200:
            d=r.json()
            if "results" in d and len(d["results"])>0:
                res=d["results"][0]
                p=res.get("value") or res.get("session",{}).get("close") or res.get("session",{}).get("previous_close")
                if p:return round(float(p),2)
    except:pass
    return None

@st.cache_data(ttl=60,show_spinner=False)
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
    return None

@st.cache_data(ttl=60,show_spinner=False)
def fetch_es_current():
    try:
        es=yf.Ticker("ES=F")
        d=es.history(period="1d",interval="1m")
        if d is not None and not d.empty:return round(float(d['Close'].iloc[-1]),2)
    except:pass
    return None

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
    # If Monday, overnight starts Sunday 5 PM (not Friday)
    overnight_day=trading_date-timedelta(days=1)  # This is the day overnight STARTS
    # Note: For Monday, overnight_day is Sunday, which is correct (futures open Sunday 5 PM)
    
    # Convert index to CT
    # Yahoo Finance returns data in ET (Eastern Time), not UTC
    df=es_candles.copy()
    ET=pytz.timezone("America/New_York")
    if df.index.tz is None:
        df.index=df.index.tz_localize(ET).tz_convert(CT)
    else:
        df.index=df.index.tz_convert(CT)
    
    # ─────────────────────────────────────────────────────────────────────────
    # SESSION TIMES (CT)
    # For Monday: overnight starts Sunday 5 PM, but prior RTH is Friday
    # ─────────────────────────────────────────────────────────────────────────
    sydney_start=CT.localize(datetime.combine(overnight_day,time(17,0)))
    sydney_end=CT.localize(datetime.combine(overnight_day,time(20,30)))
    tokyo_start=CT.localize(datetime.combine(overnight_day,time(21,0)))
    tokyo_end=CT.localize(datetime.combine(trading_date,time(1,30)))
    overnight_start=CT.localize(datetime.combine(overnight_day,time(17,0)))
    overnight_end=CT.localize(datetime.combine(trading_date,time(3,0)))  # Sydney + Tokyo + London 1st hour
    market_open=CT.localize(datetime.combine(trading_date,time(8,30)))
    market_close=CT.localize(datetime.combine(trading_date,time(15,0)))
    
    # Prior day RTH (for cones) - uses prior_rth_day which handles Monday→Friday
    prior_rth_start=CT.localize(datetime.combine(prior_rth_day,time(8,30)))
    prior_rth_end=CT.localize(datetime.combine(prior_rth_day,time(15,0)))
    
    try:
        # ─────────────────────────────────────────────────────────────────────
        # SYDNEY SESSION
        # ─────────────────────────────────────────────────────────────────────
        syd_mask=(df.index>=sydney_start)&(df.index<=sydney_end)
        syd_data=df[syd_mask]
        if not syd_data.empty:
            result["sydney_high"]=round(syd_data['High'].max(),2)
            result["sydney_low"]=round(syd_data['Low'].min(),2)
            result["sydney_high_time"]=syd_data['High'].idxmax()
            result["sydney_low_time"]=syd_data['Low'].idxmin()
        
        # ─────────────────────────────────────────────────────────────────────
        # TOKYO SESSION
        # ─────────────────────────────────────────────────────────────────────
        tok_mask=(df.index>=tokyo_start)&(df.index<=tokyo_end)
        tok_data=df[tok_mask]
        if not tok_data.empty:
            result["tokyo_high"]=round(tok_data['High'].max(),2)
            result["tokyo_low"]=round(tok_data['Low'].min(),2)
            result["tokyo_high_time"]=tok_data['High'].idxmax()
            result["tokyo_low_time"]=tok_data['Low'].idxmin()
        
        # ─────────────────────────────────────────────────────────────────────
        # LONDON SESSION (First hour only: 2AM - 3AM CT)
        # ─────────────────────────────────────────────────────────────────────
        london_start=CT.localize(datetime.combine(trading_date,time(2,0)))
        london_end=CT.localize(datetime.combine(trading_date,time(3,0)))
        lon_mask=(df.index>=london_start)&(df.index<=london_end)
        lon_data=df[lon_mask]
        if not lon_data.empty:
            result["london_high"]=round(lon_data['High'].max(),2)
            result["london_low"]=round(lon_data['Low'].min(),2)
        
        # ─────────────────────────────────────────────────────────────────────
        # OVERNIGHT SESSION (5PM prev to 3AM trading day)
        # ─────────────────────────────────────────────────────────────────────
        on_mask=(df.index>=overnight_start)&(df.index<=overnight_end)
        on_data=df[on_mask]
        if not on_data.empty:
            result["on_high"]=round(on_data['High'].max(),2)
            result["on_low"]=round(on_data['Low'].min(),2)
            result["on_high_time"]=on_data['High'].idxmax()
            result["on_low_time"]=on_data['Low'].idxmin()
        
        # ─────────────────────────────────────────────────────────────────────
        # PRIOR DAY RTH
        # For cones:
        # - HIGH cone: Ascending uses highest wick, Descending uses highest close
        # - LOW cone: Both use lowest close (not lowest wick)
        # - CLOSE cone: Both use last RTH close
        # ─────────────────────────────────────────────────────────────────────
        prior_mask=(df.index>=prior_rth_start)&(df.index<=prior_rth_end)
        prior_data=df[prior_mask]
        if not prior_data.empty:
            # HIGH - wick for ascending, close for descending
            result["prior_high_wick"]=round(prior_data['High'].max(),2)
            result["prior_high_wick_time"]=prior_data['High'].idxmax()
            result["prior_high_close"]=round(prior_data['Close'].max(),2)
            result["prior_high_close_time"]=prior_data['Close'].idxmax()
            
            # LOW - lowest close for both (not lowest wick)
            result["prior_low_close"]=round(prior_data['Close'].min(),2)
            result["prior_low_close_time"]=prior_data['Close'].idxmin()
            
            # CLOSE - last RTH close
            result["prior_close"]=round(prior_data['Close'].iloc[-1],2)
            result["prior_close_time"]=prior_data.index[-1]
            
            # Legacy fields for backward compatibility
            result["prior_high"]=result["prior_high_wick"]
            result["prior_low"]=result["prior_low_close"]
            result["prior_high_time"]=result["prior_high_wick_time"]
            result["prior_low_time"]=result["prior_low_close_time"]
        
        # ─────────────────────────────────────────────────────────────────────
        # 8:30 AM CANDLE
        # ─────────────────────────────────────────────────────────────────────
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
        
        # ─────────────────────────────────────────────────────────────────────
        # PRE-8:30 PRICE (last price before market open - for position assessment)
        # ─────────────────────────────────────────────────────────────────────
        pre830_mask=(df.index>=overnight_start)&(df.index<market_open)
        pre830_data=df[pre830_mask]
        if not pre830_data.empty:
            result["pre_830_price"]=round(pre830_data['Close'].iloc[-1],2)
            result["pre_830_time"]=pre830_data.index[-1]
        
        # ─────────────────────────────────────────────────────────────────────
        # TRADING DAY DATA (for analysis)
        # ─────────────────────────────────────────────────────────────────────
        day_mask=(df.index>=market_open)&(df.index<=market_close)
        day_data=df[day_mask]
        if not day_data.empty:
            result["day_high"]=round(day_data['High'].max(),2)
            result["day_low"]=round(day_data['Low'].min(),2)
            result["day_open"]=round(day_data['Open'].iloc[0],2)
            result["day_close"]=round(day_data['Close'].iloc[-1],2)
            result["day_candles"]=day_data
        
        # ─────────────────────────────────────────────────────────────────────
        # KEY TIMESTAMPS FOR ANALYSIS
        # ─────────────────────────────────────────────────────────────────────
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
    if tokyo_high>sydney_high:
        return "RISING","Tokyo High > Sydney High"
    elif tokyo_low<sydney_low:
        return "FALLING","Tokyo Low < Sydney Low"
    return "UNDETERMINED","No clear signal"

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
    if channel_type=="RISING":
        return levels["ceiling_rising"]["level"],levels["floor_rising"]["level"],"ceiling_rising","floor_rising"
    elif channel_type=="FALLING":
        return levels["ceiling_falling"]["level"],levels["floor_falling"]["level"],"ceiling_falling","floor_falling"
    return None,None,None,None

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
    Calculate cone rails with correct anchors:
    - HIGH: Ascending from highest wick, Descending from highest close
    - LOW: Both from lowest close
    - CLOSE: Both from last RTH close
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
    Validate the 8:30 candle based on:
    1. Did it break above ceiling or below floor? (using High/Low)
    2. Where did it close?
    
    Returns position, validation status, and setup direction
    """
    if candle is None:
        return {"status":"AWAITING","message":"Waiting for 8:30 candle","setup":"WAIT","position":"UNKNOWN"}
    
    o,h,l,c=candle["open"],candle["high"],candle["low"],candle["close"]
    
    broke_above=h>ceiling  # High exceeded ceiling
    broke_below=l<floor    # Low exceeded floor
    closed_above=c>ceiling
    closed_below=c<floor
    closed_inside=floor<=c<=ceiling
    
    # Determine what happened during the 8:30 candle
    if broke_below and not broke_above:
        # Candle broke below floor
        if closed_below:
            return {"status":"VALID","message":"✅ Broke below floor, closed below","setup":"PUTS","position":"BELOW","edge":floor}
        elif closed_inside:
            return {"status":"TREND_DAY","message":"⚡ Broke below floor, closed inside - TREND DAY","setup":"BOTH","position":"INSIDE"}
        else:  # closed_above - very wide range candle
            return {"status":"INVALIDATED","message":"❌ Broke below but closed above ceiling","setup":"WAIT","position":"ABOVE"}
    
    elif broke_above and not broke_below:
        # Candle broke above ceiling
        if closed_above:
            return {"status":"VALID","message":"✅ Broke above ceiling, closed above","setup":"CALLS","position":"ABOVE","edge":ceiling}
        elif closed_inside:
            return {"status":"TREND_DAY","message":"⚡ Broke above ceiling, closed inside - TREND DAY","setup":"BOTH","position":"INSIDE"}
        else:  # closed_below - very wide range candle
            return {"status":"INVALIDATED","message":"❌ Broke above but closed below floor","setup":"WAIT","position":"BELOW"}
    
    elif broke_above and broke_below:
        # Very wide range candle - broke both sides
        if closed_above:
            return {"status":"VALID","message":"✅ Wide range, closed above ceiling","setup":"CALLS","position":"ABOVE","edge":ceiling}
        elif closed_below:
            return {"status":"VALID","message":"✅ Wide range, closed below floor","setup":"PUTS","position":"BELOW","edge":floor}
        else:
            return {"status":"TREND_DAY","message":"⚡ Wide range, closed inside - TREND DAY","setup":"BOTH","position":"INSIDE"}
    
    else:
        # Candle stayed inside channel
        return {"status":"INSIDE","message":"⏸️ 8:30 candle stayed inside channel","setup":"WAIT","position":"INSIDE"}

# ═══════════════════════════════════════════════════════════════════════════════
# HISTORICAL OUTCOME ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
def analyze_historical_outcome(hist_data,validation,ceiling,floor,targets,direction,entry_level_es,offset):
    """
    Analyze what actually happened on a historical date
    All prices displayed in SPX (converted from ES candles)
    """
    if "day_candles" not in hist_data:
        return None
    
    day_candles=hist_data["day_candles"]
    entry_level_spx=round(entry_level_es-offset,2)
    
    result={
        "setup_valid":validation["status"] in ["VALID","TREND_DAY"],
        "direction":direction,
        "entry_level_es":entry_level_es,
        "entry_level_spx":entry_level_spx,
        "targets_hit":[],
        "max_favorable":0,
        "max_adverse":0,
        "final_price":round(hist_data.get("day_close",0)-offset,2),
        "timeline":[]
    }
    
    if not result["setup_valid"]:
        result["outcome"]="NO_SETUP"
        result["message"]="Setup was not valid"
        return result
    
    # Track price movement after 9:00 AM
    # Convert all ES candle prices to SPX for comparison
    entered=False
    entry_price_spx=None
    
    for idx,row in day_candles.iterrows():
        candle_time=idx.strftime("%H:%M")
        
        # Convert ES candle to SPX
        candle_high_spx=row['High']-offset
        candle_low_spx=row['Low']-offset
        
        # Entry window: 9:00-9:10
        if not entered and candle_time>="09:00":
            # Check if price returned to entry level (in SPX terms)
            if direction=="PUTS":
                if candle_high_spx>=entry_level_spx-3:  # Within 3 pts of floor
                    entered=True
                    entry_price_spx=min(candle_high_spx,entry_level_spx)
                    result["timeline"].append({"time":candle_time,"event":"ENTRY","price":round(entry_price_spx,2)})
            else:  # CALLS
                if candle_low_spx<=entry_level_spx+3:  # Within 3 pts of ceiling
                    entered=True
                    entry_price_spx=max(candle_low_spx,entry_level_spx)
                    result["timeline"].append({"time":candle_time,"event":"ENTRY","price":round(entry_price_spx,2)})
        
        if entered and entry_price_spx:
            # Track movement (in SPX terms)
            if direction=="PUTS":
                favorable=entry_price_spx-candle_low_spx
                adverse=candle_high_spx-entry_price_spx
            else:
                favorable=candle_high_spx-entry_price_spx
                adverse=entry_price_spx-candle_low_spx
            
            result["max_favorable"]=max(result["max_favorable"],favorable)
            result["max_adverse"]=max(result["max_adverse"],adverse)
            
            # Check targets (targets are already in SPX)
            for tgt in targets:
                if tgt["name"] not in [t["name"] for t in result["targets_hit"]]:
                    if direction=="PUTS" and candle_low_spx<=tgt["level"]:
                        result["targets_hit"].append({"name":tgt["name"],"level":tgt["level"],"time":candle_time})
                        result["timeline"].append({"time":candle_time,"event":f"TARGET: {tgt['name']}","price":tgt["level"]})
                    elif direction=="CALLS" and candle_high_spx>=tgt["level"]:
                        result["targets_hit"].append({"name":tgt["name"],"level":tgt["level"],"time":candle_time})
                        result["timeline"].append({"time":candle_time,"event":f"TARGET: {tgt['name']}","price":tgt["level"]})
    
    # Determine outcome
    if not entered:
        result["outcome"]="NO_ENTRY"
        result["message"]="Price never returned to entry level"
    elif len(result["targets_hit"])>0:
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
# FLOW BIAS
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_flow_bias(price,on_high,on_low,vix,vix_high,vix_low,prior_close,es_candles=None):
    signals=[]
    score=0
    on_range=on_high-on_low
    
    price_pos=(price-on_low)/on_range*100 if on_range>0 else 50
    if price>on_high:score+=30;signals.append(("Price","CALLS",f"+{price-on_high:.0f}"))
    elif price<on_low:score-=30;signals.append(("Price","PUTS",f"{price-on_low:.0f}"))
    elif price_pos>75:score+=15;signals.append(("Price","CALLS",f"{price_pos:.0f}%"))
    elif price_pos<25:score-=15;signals.append(("Price","PUTS",f"{price_pos:.0f}%"))
    else:signals.append(("Price","NEUTRAL",f"{price_pos:.0f}%"))
    
    vix_range=vix_high-vix_low
    vix_pos=(vix-vix_low)/vix_range*100 if vix_range>0 else 50
    if vix>vix_high:score-=25;signals.append(("VIX","PUTS",f"{vix:.1f}"))
    elif vix<vix_low:score+=25;signals.append(("VIX","CALLS",f"{vix:.1f}"))
    elif vix_pos>70:score-=12;signals.append(("VIX","PUTS",f"{vix_pos:.0f}%"))
    elif vix_pos<30:score+=12;signals.append(("VIX","CALLS",f"{vix_pos:.0f}%"))
    else:signals.append(("VIX","NEUTRAL",f"{vix_pos:.0f}%"))
    
    gap=price-prior_close
    if gap>10:score+=25;signals.append(("Gap","CALLS",f"+{gap:.0f}"))
    elif gap<-10:score-=25;signals.append(("Gap","PUTS",f"{gap:.0f}"))
    elif gap>5:score+=12;signals.append(("Gap","CALLS",f"+{gap:.0f}"))
    elif gap<-5:score-=12;signals.append(("Gap","PUTS",f"{gap:.0f}"))
    else:signals.append(("Gap","NEUTRAL",f"{gap:+.0f}"))
    
    if score>=30:bias="HEAVY_CALLS"
    elif score<=-30:bias="HEAVY_PUTS"
    else:bias="NEUTRAL"
    
    return {"bias":bias,"score":score,"signals":signals}

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

def calculate_ma_bias(es_candles):
    if es_candles is None or len(es_candles)<50:
        return {"signal":"NEUTRAL"}
    close=es_candles['Close']
    ema50=close.ewm(span=50).mean().iloc[-1]
    sma200=close.rolling(min(200,len(close))).mean().iloc[-1]
    if ema50>sma200:return {"signal":"LONG","ema50":round(ema50,2),"sma200":round(sma200,2)}
    elif ema50<sma200:return {"signal":"SHORT","ema50":round(ema50,2),"sma200":round(sma200,2)}
    return {"signal":"NEUTRAL","ema50":round(ema50,2),"sma200":round(sma200,2)}

# ═══════════════════════════════════════════════════════════════════════════════
# OPTION PRICING
# ═══════════════════════════════════════════════════════════════════════════════
def get_strike(entry_level,opt_type):
    if opt_type=="CALL":return int(round((entry_level+20)/5)*5)
    return int(round((entry_level-20)/5)*5)

def estimate_prices(entry_level,strike,opt_type,vix,hours):
    iv=vix/100
    T=max(0.001,hours/(365*24))
    entry=black_scholes(entry_level,strike,T,0.05,iv,opt_type)
    return round(entry,2)

def estimate_exit_prices(entry_level,strike,opt_type,vix,hours,targets):
    iv=vix/100
    entry_T=max(0.001,hours/(365*24))
    entry_price=black_scholes(entry_level,strike,entry_T,0.05,iv,opt_type)
    results=[]
    for i,tgt in enumerate(targets[:3]):
        exit_T=max(0.001,(hours-1-i*0.5)/(365*24))
        exit_price=black_scholes(tgt["level"],strike,exit_T,0.05,iv,opt_type)
        pct=(exit_price-entry_price)/entry_price*100 if entry_price>0 else 0
        results.append({"target":tgt["name"],"level":tgt["level"],"price":round(exit_price,2),"pct":round(pct,0)})
    return results,round(entry_price,2)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_confidence(channel_type,position,flow,vix_zone):
    score=0
    if channel_type!="UNDETERMINED":score+=25
    if position in ["ABOVE","BELOW"]:score+=25
    elif position in ["MARGINAL_ABOVE","MARGINAL_BELOW"]:score+=15
    if flow["bias"]!="NEUTRAL":score+=20
    else:score+=10
    if vix_zone in ["LOW","NORMAL"]:score+=15
    elif vix_zone=="ELEVATED":score+=10
    else:score+=5
    return score

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def safe_float(value,default):
    """Safely convert to float, returning default if None or invalid"""
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError,ValueError):
        return float(default)

def render_sidebar():
    saved=load_inputs()
    
    with st.sidebar:
        st.markdown("## 🔮 SPX Prophet V6.1")
        st.markdown("*Historical Analysis Mode*")
        
        trading_date=st.date_input("📅 Date",value=date.today())
        is_historical=trading_date<date.today()
        
        if is_historical:
            st.info(f"📜 Historical Mode: {trading_date.strftime('%A, %b %d, %Y')}")
        
        st.markdown("---")
        st.markdown("### ⚙️ ES/SPX Offset")
        offset=st.number_input("SPX = ES - Offset",value=safe_float(saved.get("offset"),18.0),step=0.5)
        
        st.markdown("---")
        st.markdown("### 📊 Data Mode")
        if is_historical:
            data_mode=st.radio("Source",["Auto (from ES candles)","Manual Override"],index=0)
        else:
            data_mode=st.radio("Source",["Auto","Manual"],index=0,horizontal=True)
        
        # Manual overrides (collapsed for historical auto mode)
        if data_mode.startswith("Manual") or not is_historical:
            with st.expander("Manual Inputs",expanded=not is_historical):
                st.markdown("**O/N Structure (ES)**")
                c1,c2=st.columns(2)
                on_high=c1.number_input("O/N High",value=safe_float(saved.get("on_high"),6075.0),step=0.5)
                on_low=c2.number_input("O/N Low",value=safe_float(saved.get("on_low"),6040.0),step=0.5)
                
                st.markdown("**VIX**")
                c1,c2=st.columns(2)
                vix_high=c1.number_input("VIX High",value=safe_float(saved.get("vix_high"),18.0),step=0.1)
                vix_low=c2.number_input("VIX Low",value=safe_float(saved.get("vix_low"),15.0),step=0.1)
                
                st.markdown("**Prior Day (ES)**")
                c1,c2=st.columns(2)
                prior_high=c1.number_input("Prior High",value=safe_float(saved.get("prior_high"),6080.0),step=0.5)
                prior_low=c2.number_input("Prior Low",value=safe_float(saved.get("prior_low"),6030.0),step=0.5)
                prior_close=st.number_input("Prior Close",value=safe_float(saved.get("prior_close"),6055.0),step=0.5)
        else:
            on_high=on_low=vix_high=vix_low=prior_high=prior_low=prior_close=None
        
        st.markdown("---")
        ref_time_sel=st.selectbox("Reference Time",["8:30 AM","9:00 AM","9:30 AM"],index=1)
        ref_map={"8:30 AM":(8,30),"9:00 AM":(9,0),"9:30 AM":(9,30)}
        ref_hr,ref_mn=ref_map[ref_time_sel]
        
        st.markdown("---")
        auto_refresh=st.checkbox("Auto Refresh",value=False) if not is_historical else False
        debug=st.checkbox("Debug",value=False)
        
        if st.button("💾 Save",use_container_width=True):
            save_inputs({"offset":offset,"on_high":on_high,"on_low":on_low,"vix_high":vix_high,"vix_low":vix_low,"prior_high":prior_high,"prior_low":prior_low,"prior_close":prior_close})
            st.success("✅")
    
    return {
        "trading_date":trading_date,
        "is_historical":is_historical,
        "data_mode":data_mode,
        "offset":offset,
        "on_high":on_high,"on_low":on_low,
        "vix_high":vix_high,"vix_low":vix_low,
        "prior_high":prior_high,"prior_low":prior_low,"prior_close":prior_close,
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
    
    # ─────────────────────────────────────────────────────────────────────────
    # FETCH DATA
    # ─────────────────────────────────────────────────────────────────────────
    with st.spinner("Loading data..."):
        if inputs["is_historical"]:
            # Historical mode - fetch candles for that date range
            # Need extra days to handle weekends (if trading_date is Monday/Tuesday)
            start=inputs["trading_date"]-timedelta(days=7)  # Go back a full week
            end=inputs["trading_date"]+timedelta(days=1)
            es_candles=fetch_es_candles_range(start,end)
            
            if es_candles is not None and not es_candles.empty:
                hist_data=extract_historical_data(es_candles,inputs["trading_date"],inputs["offset"])
            else:
                hist_data=None
                st.error("❌ Could not fetch historical data for this date. Try a date within the last 60 days.")
            
            es_price=hist_data.get("day_open") if hist_data else None
            spx_price=round(es_price-inputs["offset"],2) if es_price else None
            vix=16.0  # Default for historical
        else:
            # Live mode
            es_candles=fetch_es_candles(7)
            es_price=fetch_es_current()
            spx_price=fetch_spx_polygon()
            vix=fetch_vix_polygon() or 16.0
            hist_data=None
    
    offset=inputs["offset"]
    
    # ─────────────────────────────────────────────────────────────────────────
    # POPULATE DATA (Auto or Manual)
    # ─────────────────────────────────────────────────────────────────────────
    if inputs["is_historical"] and hist_data and inputs["data_mode"].startswith("Auto"):
        # Use extracted historical data
        syd_h=hist_data.get("sydney_high",6070)
        syd_l=hist_data.get("sydney_low",6050)
        tok_h=hist_data.get("tokyo_high",6075)
        tok_l=hist_data.get("tokyo_low",6045)
        on_high=hist_data.get("on_high",6075)
        on_low=hist_data.get("on_low",6040)
        
        # Prior day data for cones
        prior_high_wick=hist_data.get("prior_high_wick",6080)
        prior_high_close=hist_data.get("prior_high_close",6075)
        prior_low_close=hist_data.get("prior_low_close",6030)
        prior_close=hist_data.get("prior_close",6055)
        
        candle_830=hist_data.get("candle_830")
        current_es=hist_data.get("day_open",es_price or 6050)
        vix_high=inputs["vix_high"] or 18
        vix_low=inputs["vix_low"] or 15
        
        # Get times with fallbacks - separate overnight_day from prior_rth_day
        # For PRIOR RTH (cones): Monday uses Friday
        prior_rth_day=inputs["trading_date"]-timedelta(days=1)
        if prior_rth_day.weekday()==6:prior_rth_day=prior_rth_day-timedelta(days=2)
        elif prior_rth_day.weekday()==5:prior_rth_day=prior_rth_day-timedelta(days=1)
        
        # For OVERNIGHT: Day before trading date (Sunday for Monday)
        overnight_day=inputs["trading_date"]-timedelta(days=1)
        
        # O/N times use overnight_day
        on_high_time=hist_data.get("on_high_time") or CT.localize(datetime.combine(overnight_day,time(22,0)))
        on_low_time=hist_data.get("on_low_time") or CT.localize(datetime.combine(inputs["trading_date"],time(2,0)))
        
        # Prior RTH times use prior_rth_day
        prior_high_wick_time=hist_data.get("prior_high_wick_time") or CT.localize(datetime.combine(prior_rth_day,time(10,0)))
        prior_high_close_time=hist_data.get("prior_high_close_time") or CT.localize(datetime.combine(prior_rth_day,time(10,0)))
        prior_low_close_time=hist_data.get("prior_low_close_time") or CT.localize(datetime.combine(prior_rth_day,time(14,0)))
        prior_close_time=hist_data.get("prior_close_time") or CT.localize(datetime.combine(prior_rth_day,time(15,0)))
    else:
        # Manual or live
        syd_h=inputs.get("on_high") or 6070
        syd_l=inputs.get("on_low") or 6050
        tok_h=inputs.get("on_high") or 6075
        tok_l=inputs.get("on_low") or 6045
        on_high=inputs["on_high"] or 6075
        on_low=inputs["on_low"] or 6040
        
        # Prior day data for cones (manual mode uses same value for wick and close)
        prior_high_wick=inputs["prior_high"] or 6080
        prior_high_close=inputs["prior_high"] or 6080  # In manual mode, same as wick
        prior_low_close=inputs["prior_low"] or 6030
        prior_close=inputs["prior_close"] or 6055
        
        vix_high=inputs["vix_high"] or 18
        vix_low=inputs["vix_low"] or 15
        candle_830=None
        current_es=es_price or 6050
        
        # Default times - handle weekends
        # For PRIOR RTH (cones): Monday uses Friday
        prior_rth_day=inputs["trading_date"]-timedelta(days=1)
        if prior_rth_day.weekday()==6:prior_rth_day=prior_rth_day-timedelta(days=2)  # Sunday→Friday
        elif prior_rth_day.weekday()==5:prior_rth_day=prior_rth_day-timedelta(days=1)  # Saturday→Friday
        
        # For OVERNIGHT: Day before trading date (Sunday for Monday)
        overnight_day=inputs["trading_date"]-timedelta(days=1)
        
        # O/N times use overnight_day (Sunday for Monday)
        on_high_time=CT.localize(datetime.combine(overnight_day,time(22,0)))
        on_low_time=CT.localize(datetime.combine(inputs["trading_date"],time(3,0)))
        
        # Prior RTH times use prior_rth_day (Friday for Monday)
        prior_high_wick_time=CT.localize(datetime.combine(prior_rth_day,time(10,0)))
        prior_high_close_time=CT.localize(datetime.combine(prior_rth_day,time(10,0)))
        prior_low_close_time=CT.localize(datetime.combine(prior_rth_day,time(14,0)))
        prior_close_time=CT.localize(datetime.combine(prior_rth_day,time(15,0)))
    
    current_spx=round(current_es-offset,2)
    
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
    
    # Cones - using correct anchors for each line
    cones_es=calculate_cones(prior_high_wick,prior_high_wick_time,prior_high_close,prior_high_close_time,
                             prior_low_close,prior_low_close_time,prior_close,prior_close_time,ref_time)
    # Convert to SPX
    cones_spx={}
    for k,v in cones_es.items():
        cones_spx[k]={
            "anchor_asc":round(v["anchor_asc"]-offset,2),
            "anchor_desc":round(v["anchor_desc"]-offset,2),
            "asc":round(v["asc"]-offset,2),
            "desc":round(v["desc"]-offset,2)
        }
    
    # Validation - 8:30 candle determines position by breaking ceiling/floor
    if candle_830 and ceiling_es and floor_es:
        validation=validate_830_candle(candle_830,ceiling_es,floor_es)
        position=validation.get("position","UNKNOWN")
    else:
        validation={"status":"AWAITING","message":"Waiting for data","setup":"WAIT","position":"UNKNOWN"}
        position="UNKNOWN"
    
    # Calculate distance from edges for display
    if candle_830 and ceiling_es and floor_es:
        c830_close=candle_830["close"]
        if position=="ABOVE":
            pos_desc="above ceiling"
            pos_dist=c830_close-ceiling_es
        elif position=="BELOW":
            pos_desc="below floor"
            pos_dist=floor_es-c830_close
        else:
            pos_desc="inside channel"
            pos_dist=min(c830_close-floor_es,ceiling_es-c830_close) if c830_close else 0
    else:
        pos_desc="unknown"
        pos_dist=0
    
    # Direction & targets based on validation
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
    elif validation["setup"]=="BOTH":
        # Trend day - could go either direction
        direction="TREND_DAY"
        entry_edge_es=None
        targets=[]
    else:
        direction="WAIT"
        entry_edge_es=None
        targets=[]
    
    # Flow & momentum - use 8:30 candle open for flow bias calculation
    flow_price=candle_830["open"] if candle_830 else current_es
    flow=calculate_flow_bias(flow_price,on_high,on_low,vix,vix_high,vix_low,prior_close)
    momentum=calculate_momentum(es_candles)
    ma_bias=calculate_ma_bias(es_candles)
    vix_zone=get_vix_zone(vix)
    confidence=calculate_confidence(channel_type,position,flow,vix_zone)
    
    # Historical outcome
    if inputs["is_historical"] and hist_data and entry_edge_es:
        outcome=analyze_historical_outcome(hist_data,validation,ceiling_es,floor_es,targets,direction,entry_edge_es,offset)
    else:
        outcome=None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HERO
    # ═══════════════════════════════════════════════════════════════════════════
    hist_badge=f'<div class="hist-badge">📜 HISTORICAL ANALYSIS</div>' if inputs["is_historical"] else ""
    
    st.markdown(f'''<div class="hero">
<div class="hero-title">🔮 SPX PROPHET V6.1</div>
<div class="hero-sub">ES: {current_es:,.2f} | Offset: {offset:+.2f} | {channel_type} Channel</div>
<div class="hero-price">{current_spx:,.2f}</div>
{hist_badge}
<div style="font-family:IBM Plex Mono;font-size:13px;color:rgba(255,255,255,0.5);margin-top:8px">{inputs["trading_date"].strftime("%A, %B %d, %Y")}</div>
</div>''',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORICAL OUTCOME CARD (if applicable)
    # ═══════════════════════════════════════════════════════════════════════════
    if outcome:
        if outcome["outcome"]=="WIN":
            box_class="win"
            icon="✅"
        elif outcome["outcome"]=="LOSS":
            box_class="loss"
            icon="❌"
        else:
            box_class="neutral"
            icon="⚠️"
        
        timeline_html=""
        for evt in outcome.get("timeline",[]):
            dot_class="hit" if "TARGET" in evt["event"] else "active"
            timeline_html+=f'<div class="timeline-item"><div class="timeline-dot {dot_class}"></div><div style="font-size:12px"><span style="color:rgba(255,255,255,0.5)">{evt["time"]}</span> <span style="font-weight:600">{evt["event"]}</span> @ {evt["price"]:.2f}</div></div>'
        
        targets_hit_str=", ".join([f"{t['name']} @ {t['time']}" for t in outcome.get("targets_hit",[])]) or "None"
        
        st.markdown(f'''<div class="result-box {box_class}">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
<div style="font-size:18px;font-weight:700">{icon} HISTORICAL RESULT</div>
<div style="font-size:14px;font-weight:600">{outcome["outcome"]}</div>
</div>
<div style="font-size:14px;margin-bottom:12px">{outcome["message"]}</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px">
<div style="text-align:center"><div style="font-size:10px;color:rgba(255,255,255,0.5)">Direction</div><div style="font-weight:600">{outcome["direction"]}</div></div>
<div style="text-align:center"><div style="font-size:10px;color:rgba(255,255,255,0.5)">Entry Level</div><div style="font-weight:600">{outcome["entry_level_spx"]}</div></div>
<div style="text-align:center"><div style="font-size:10px;color:rgba(255,255,255,0.5)">Max Favorable</div><div style="font-weight:600;color:#00d4aa">+{outcome["max_favorable"]:.1f}</div></div>
<div style="text-align:center"><div style="font-size:10px;color:rgba(255,255,255,0.5)">Max Adverse</div><div style="font-weight:600;color:#ff4757">-{outcome["max_adverse"]:.1f}</div></div>
</div>
<div style="font-size:12px;color:rgba(255,255,255,0.6)"><strong>Targets Hit:</strong> {targets_hit_str}</div>
{f'<div class="timeline" style="margin-top:12px">{timeline_html}</div>' if timeline_html else ""}
</div>''',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTO-POPULATED DATA (Historical)
    # ═══════════════════════════════════════════════════════════════════════════
    if inputs["is_historical"] and hist_data:
        st.markdown("### 📊 Auto-Populated Session Data")
        
        col1,col2,col3,col4=st.columns(4)
        
        with col1:
            st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(59,130,246,0.15)">🌏</div><div><div class="card-title">Sydney</div><div class="card-sub">5PM-8:30PM</div></div></div>
<div class="pillar"><span>High</span><span style="color:#00d4aa">{syd_h}</span></div>
<div class="pillar"><span>Low</span><span style="color:#ff4757">{syd_l}</span></div>
</div>''',unsafe_allow_html=True)
        
        with col2:
            st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(255,71,87,0.15)">🗼</div><div><div class="card-title">Tokyo</div><div class="card-sub">9PM-1:30AM</div></div></div>
<div class="pillar"><span>High</span><span style="color:#00d4aa">{tok_h}</span></div>
<div class="pillar"><span>Low</span><span style="color:#ff4757">{tok_l}</span></div>
</div>''',unsafe_allow_html=True)
        
        with col3:
            lon_h=hist_data.get("london_high","—")
            lon_l=hist_data.get("london_low","—")
            st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(0,212,170,0.15)">🏛️</div><div><div class="card-title">London</div><div class="card-sub">2AM-3AM</div></div></div>
<div class="pillar"><span>High</span><span style="color:#00d4aa">{lon_h}</span></div>
<div class="pillar"><span>Low</span><span style="color:#ff4757">{lon_l}</span></div>
</div>''',unsafe_allow_html=True)
        
        with col4:
            st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(168,85,247,0.15)">🌙</div><div><div class="card-title">O/N Total</div><div class="card-sub">5PM-3AM</div></div></div>
<div class="pillar"><span>High</span><span style="color:#00d4aa">{on_high}</span></div>
<div class="pillar"><span>Low</span><span style="color:#ff4757">{on_low}</span></div>
</div>''',unsafe_allow_html=True)
        
        # 8:30 Candle
        if candle_830:
            c=candle_830
            candle_color="#00d4aa" if c["close"]>=c["open"] else "#ff4757"
            st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(34,211,238,0.15)">🕣</div><div><div class="card-title">8:30 AM Candle (ES)</div><div class="card-sub">First 30-min candle</div></div></div>
<div class="candle-display">
<div class="candle-item"><div class="candle-label">Open</div><div class="candle-val">{c["open"]}</div></div>
<div class="candle-item"><div class="candle-label">High</div><div class="candle-val" style="color:#00d4aa">{c["high"]}</div></div>
<div class="candle-item"><div class="candle-label">Low</div><div class="candle-val" style="color:#ff4757">{c["low"]}</div></div>
<div class="candle-item"><div class="candle-label">Close</div><div class="candle-val" style="color:{candle_color}">{c["close"]}</div></div>
</div>
</div>''',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMMAND CENTER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🎯 Trade Command Center")
    
    ch_color="#00d4aa" if channel_type=="RISING" else "#ff4757" if channel_type=="FALLING" else "#ffa502"
    ch_icon="▲" if channel_type=="RISING" else "▼" if channel_type=="FALLING" else "◆"
    pos_color="#ff4757" if "BELOW" in position else "#00d4aa" if "ABOVE" in position else "#ffa502"
    val_color="#00d4aa" if validation["status"]=="VALID" else "#ff4757" if validation["status"]=="INVALIDATED" else "#ffa502"
    
    cmd_html=f'''<div class="cmd-card">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
<div><div class="cmd-title">{"Historical " if inputs["is_historical"] else ""}Trading Plan</div><div style="font-size:12px;color:rgba(255,255,255,0.6)">{channel_reason}</div></div>
<span style="background:{ch_color};color:white;padding:4px 12px;border-radius:12px;font-size:11px;font-weight:600">{channel_type}</span>
</div>

<div class="channel-box">
<div class="level-row"><span class="level-name">Ceiling ({ceil_key or "N/A"})</span><span class="level-val" style="color:#00d4aa">ES {ceiling_es or "—"} → SPX {ceiling_spx or "—"}</span></div>
<div class="level-row"><span class="level-name">Floor ({floor_key or "N/A"})</span><span class="level-val" style="color:#ff4757">ES {floor_es or "—"} → SPX {floor_spx or "—"}</span></div>
<div class="level-row" style="border:none"><span class="level-name">Pre-Open Position</span><span class="level-val" style="color:{pos_color}">{position} ({pos_dist:.1f} pts)</span></div>
</div>

<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:12px;margin:12px 0">
<div style="font-size:12px;color:rgba(255,255,255,0.5);margin-bottom:6px">8:30 AM Candle Validation</div>
<div style="font-size:14px;font-weight:600;color:{val_color}">{validation["message"]}</div>
</div>'''
    
    # Trade setup
    if direction in ["PUTS","CALLS"] and entry_edge_es:
        entry_spx=round(entry_edge_es-offset,2)
        strike=get_strike(entry_spx,"PUT" if direction=="PUTS" else "CALL")
        entry_price=estimate_prices(entry_spx,strike,"PUT" if direction=="PUTS" else "CALL",vix,hours_to_expiry)
        exits,_=estimate_exit_prices(entry_spx,strike,"PUT" if direction=="PUTS" else "CALL",vix,hours_to_expiry,targets)
        
        dir_color="#ff4757" if direction=="PUTS" else "#00d4aa"
        targets_html=""
        for i,t in enumerate(exits):
            hl="border:1px solid #00d4aa;background:rgba(0,212,170,0.1)" if i==0 else ""
            targets_html+=f'<div style="display:flex;justify-content:space-between;padding:6px 8px;border-radius:6px;margin:4px 0;{hl}"><span>{t["target"]} @ {t["level"]}</span><span style="color:{"#00d4aa" if t["pct"]>0 else "#ff4757"}">${t["price"]} ({t["pct"]:+.0f}%)</span></div>'
        
        cmd_html+=f'''<div class="scenario valid">
<div class="scenario-h" style="color:{dir_color}">{"🔴" if direction=="PUTS" else "🟢"} {direction} SETUP</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
<div><div style="font-size:10px;color:rgba(255,255,255,0.5)">Entry</div><div style="font-weight:600">9:00-9:10</div></div>
<div><div style="font-size:10px;color:rgba(255,255,255,0.5)">Level</div><div style="font-weight:600">{entry_spx}</div></div>
<div><div style="font-size:10px;color:rgba(255,255,255,0.5)">Strike</div><div style="font-weight:600;color:{dir_color}">{strike}</div></div>
<div><div style="font-size:10px;color:rgba(255,255,255,0.5)">Entry $</div><div style="font-weight:600">${entry_price}</div></div>
</div>
<div class="target-box"><div class="target-h">📍 Targets</div>{targets_html if targets_html else "<div style='color:rgba(255,255,255,0.5)'>No targets found</div>"}</div>
</div>'''
    
    cmd_html+="</div>"
    st.markdown(cmd_html,unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SUPPORTING ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    col1,col2,col3=st.columns(3)
    
    with col1:
        conf_color="#00d4aa" if confidence>=70 else "#ffa502" if confidence>=50 else "#ff4757"
        st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(168,85,247,0.15)">📊</div><div><div class="card-title">Confidence</div></div></div>
<div class="metric" style="color:{conf_color}">{confidence}%</div>
<div class="conf-bar"><div class="conf-fill" style="width:{confidence}%;background:{conf_color}"></div></div>
</div>''',unsafe_allow_html=True)
    
    with col2:
        flow_color="#00d4aa" if flow["bias"]=="HEAVY_CALLS" else "#ff4757" if flow["bias"]=="HEAVY_PUTS" else "#ffa502"
        meter_pos=(flow["score"]+100)/2
        st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(34,211,238,0.15)">🌊</div><div><div class="card-title">Flow Bias</div><div class="card-sub">{flow["bias"].replace("_"," ")}</div></div></div>
<div class="metric" style="color:{flow_color}">{flow["score"]:+d}</div>
<div class="flow-meter"><div class="flow-marker" style="left:{meter_pos}%"></div></div>
</div>''',unsafe_allow_html=True)
    
    with col3:
        ma_color="#00d4aa" if ma_bias["signal"]=="LONG" else "#ff4757" if ma_bias["signal"]=="SHORT" else "#ffa502"
        mom_color="#00d4aa" if "BULL" in momentum["signal"] else "#ff4757" if "BEAR" in momentum["signal"] else "#ffa502"
        st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(59,130,246,0.15)">📈</div><div><div class="card-title">Context</div></div></div>
<div class="pillar"><span>MA Bias</span><span style="color:{ma_color}">{ma_bias["signal"]}</span></div>
<div class="pillar"><span>Momentum</span><span style="color:{mom_color}">{momentum["signal"]}</span></div>
<div class="pillar"><span>VIX</span><span>{vix:.1f} ({vix_zone})</span></div>
</div>''',unsafe_allow_html=True)
    
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
    st.markdown(f'<div class="footer">SPX PROPHET V6.1 | Historical Analysis Mode | Slope: {SLOPE}</div>',unsafe_allow_html=True)
    
    if inputs["auto_refresh"] and not inputs["is_historical"]:
        time_module.sleep(30)
        st.rerun()

if __name__=="__main__":
    main()