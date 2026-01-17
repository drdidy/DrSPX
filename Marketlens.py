# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V6.0 - UNIFIED INSTITUTIONAL TRADING SYSTEM
# ES-Native | Auto Session Detection | Channel Strategy | Multi-Signal Flow
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

def norm_pdf(x):
    return math.exp(-0.5*x*x)/math.sqrt(2*math.pi)

def black_scholes(S,K,T,r,sigma,opt_type):
    if T<=0:return max(0,S-K) if opt_type=="CALL" else max(0,K-S)
    d1=(math.log(S/K)+(r+0.5*sigma**2)*T)/(sigma*math.sqrt(T))
    d2=d1-sigma*math.sqrt(T)
    if opt_type=="CALL":return S*norm_cdf(d1)-K*math.exp(-r*T)*norm_cdf(d2)
    return K*math.exp(-r*T)*norm_cdf(-d2)-S*norm_cdf(-d1)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet V6",page_icon="🔮",layout="wide",initial_sidebar_state="expanded")
CT=pytz.timezone("America/Chicago")
SLOPE=0.48
BREAK_THRESHOLD=6.0
POLYGON_KEY="DCWuTS1R_fukpfjgf7QnXrLTEOS_giq6"
POLYGON_BASE="https://api.polygon.io"
SAVE_FILE="spx_prophet_v6_inputs.json"

# Session times (CT) - Previous day for Sydney/Tokyo
SESSIONS={
    "SYDNEY":{"start":(17,0),"end":(20,30)},  # 5:00 PM - 8:30 PM CT
    "TOKYO":{"start":(21,0),"end":(1,30)},    # 9:00 PM - 1:30 AM CT (next day)
}

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
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:16px;margin-bottom:14px;backdrop-filter:blur(10px)}
.card-h{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.card-icon{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.card-title{font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:600}
.card-sub{font-size:11px;color:var(--text2)}
.badge{display:inline-block;padding:5px 12px;border-radius:16px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px}
.badge-g{background:rgba(0,212,170,0.2);color:var(--green);border:1px solid var(--green)}
.badge-r{background:rgba(255,71,87,0.2);color:var(--red);border:1px solid var(--red)}
.badge-a{background:rgba(255,165,2,0.2);color:var(--amber);border:1px solid var(--amber)}
.badge-p{background:rgba(168,85,247,0.2);color:var(--purple);border:1px solid var(--purple)}
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
.conf-bar{height:8px;background:rgba(255,255,255,0.1);border-radius:4px;overflow:hidden;margin:6px 0}
.conf-fill{height:100%;border-radius:4px}
.pillar{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-size:12px}
.trade-card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:14px;margin-bottom:10px}
.trade-card.active{border-color:var(--cyan);box-shadow:0 0 15px rgba(34,211,238,0.2)}
.trade-card.entry{border-color:var(--green);box-shadow:0 0 20px rgba(0,212,170,0.3);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 20px rgba(0,212,170,0.3)}50%{box-shadow:0 0 30px rgba(0,212,170,0.5)}}
.flow-meter{height:6px;background:linear-gradient(90deg,#ff4757,#ffa502 50%,#00d4aa);border-radius:3px;position:relative;margin:8px 0}
.flow-marker{position:absolute;top:-3px;width:4px;height:12px;background:#fff;border-radius:2px;transform:translateX(-50%);box-shadow:0 0 6px rgba(255,255,255,0.5)}
.footer{text-align:center;padding:16px;color:var(--text2);font-size:11px;border-top:1px solid var(--border);margin-top:20px}
</style>"""

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def now_ct():return datetime.now(CT)
def blocks_between(start,end):return max(0,int((end-start).total_seconds()/60//30)) if end>start else 0

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
@st.cache_data(ttl=120,show_spinner=False)
def fetch_es_candles(days=5):
    for _ in range(3):
        try:
            es=yf.Ticker("ES=F")
            data=es.history(period=f"{days}d",interval="30m")
            if data is not None and not data.empty:return data
        except:time_module.sleep(1)
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
# SESSION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
def get_session_levels(es_candles,trading_date):
    """Extract Sydney and Tokyo highs/lows from ES candles"""
    if es_candles is None or es_candles.empty:
        return None
    
    prev_day=trading_date-timedelta(days=1)
    results={}
    
    # Sydney: 5:00 PM - 8:30 PM CT previous day
    syd_start=CT.localize(datetime.combine(prev_day,time(17,0)))
    syd_end=CT.localize(datetime.combine(prev_day,time(20,30)))
    
    # Tokyo: 9:00 PM prev day - 1:30 AM trading day
    tok_start=CT.localize(datetime.combine(prev_day,time(21,0)))
    tok_end=CT.localize(datetime.combine(trading_date,time(1,30)))
    
    try:
        # Filter candles for each session
        es_candles_ct=es_candles.copy()
        if es_candles_ct.index.tz is None:
            es_candles_ct.index=es_candles_ct.index.tz_localize('UTC').tz_convert(CT)
        else:
            es_candles_ct.index=es_candles_ct.index.tz_convert(CT)
        
        # Sydney
        syd_mask=(es_candles_ct.index>=syd_start)&(es_candles_ct.index<=syd_end)
        syd_data=es_candles_ct[syd_mask]
        if not syd_data.empty:
            results["sydney_high"]=round(syd_data['High'].max(),2)
            results["sydney_low"]=round(syd_data['Low'].min(),2)
            results["sydney_high_time"]=syd_data['High'].idxmax()
            results["sydney_low_time"]=syd_data['Low'].idxmin()
        
        # Tokyo
        tok_mask=(es_candles_ct.index>=tok_start)&(es_candles_ct.index<=tok_end)
        tok_data=es_candles_ct[tok_mask]
        if not tok_data.empty:
            results["tokyo_high"]=round(tok_data['High'].max(),2)
            results["tokyo_low"]=round(tok_data['Low'].min(),2)
            results["tokyo_high_time"]=tok_data['High'].idxmax()
            results["tokyo_low_time"]=tok_data['Low'].idxmin()
    except Exception as e:
        st.warning(f"Session detection error: {e}")
    
    return results if results else None

def determine_channel(sydney_high,sydney_low,tokyo_high,tokyo_low):
    """Determine active channel based on Tokyo vs Sydney"""
    if tokyo_high>sydney_high:
        return "RISING","Tokyo High > Sydney High"
    elif tokyo_low<sydney_low:
        return "FALLING","Tokyo Low < Sydney Low"
    else:
        return "UNDETERMINED","No clear channel signal"

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_channel_levels(on_high,on_high_time,on_low,on_low_time,ref_time,pm_high=None,pm_low=None):
    """Calculate channel edges (ceiling/floor) at reference time"""
    eff_high=pm_high if pm_high and pm_high>on_high else on_high
    eff_low=pm_low if pm_low and pm_low<on_low else on_low
    
    blocks_high=blocks_between(on_high_time,ref_time)
    blocks_low=blocks_between(on_low_time,ref_time)
    
    exp_high=SLOPE*blocks_high
    exp_low=SLOPE*blocks_low
    
    return {
        "ceiling_rising":{"level":round(eff_high+exp_high,2),"anchor":eff_high,"blocks":blocks_high,"exp":round(exp_high,2)},
        "ceiling_falling":{"level":round(eff_high-exp_high,2),"anchor":eff_high,"blocks":blocks_high,"exp":round(exp_high,2)},
        "floor_rising":{"level":round(eff_low+exp_low,2),"anchor":eff_low,"blocks":blocks_low,"exp":round(exp_low,2)},
        "floor_falling":{"level":round(eff_low-exp_low,2),"anchor":eff_low,"blocks":blocks_low,"exp":round(exp_low,2)},
        "effective_high":eff_high,
        "effective_low":eff_low
    }

def get_channel_edges(levels,channel_type):
    """Get ceiling and floor for the active channel"""
    if channel_type=="RISING":
        return levels["ceiling_rising"]["level"],levels["floor_rising"]["level"],"ceiling_rising","floor_rising"
    elif channel_type=="FALLING":
        return levels["ceiling_falling"]["level"],levels["floor_falling"]["level"],"ceiling_falling","floor_falling"
    return None,None,None,None

def assess_position(price,ceiling,floor):
    """Determine position relative to channel"""
    if price>ceiling+BREAK_THRESHOLD:
        return "ABOVE","broken above",price-ceiling
    elif price<floor-BREAK_THRESHOLD:
        return "BELOW","broken below",floor-price
    elif price>ceiling:
        return "MARGINAL_ABOVE","marginally above",price-ceiling
    elif price<floor:
        return "MARGINAL_BELOW","marginally below",floor-price
    else:
        return "INSIDE","inside channel",min(price-floor,ceiling-price)

# ═══════════════════════════════════════════════════════════════════════════════
# CONE RAILS
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_cones(prior_high,prior_high_time,prior_low,prior_low_time,prior_close,prior_close_time,ref_time):
    cones={}
    for name,price,anchor_time in [("HIGH",prior_high,prior_high_time),("LOW",prior_low,prior_low_time),("CLOSE",prior_close,prior_close_time)]:
        blocks=blocks_between(anchor_time,ref_time)
        exp=SLOPE*blocks
        cones[name]={"anchor":price,"asc":round(price+exp,2),"desc":round(price-exp,2),"blocks":blocks,"exp":round(exp,2)}
    return cones

def find_targets(entry_level,cones,direction):
    """Find cone targets above (CALLS) or below (PUTS) entry"""
    targets=[]
    if direction=="CALLS":
        # Find ascending cones above entry
        for name in ["CLOSE","HIGH","LOW"]:
            asc=cones[name]["asc"]
            if asc>entry_level:
                targets.append({"name":f"{name} Asc","level":asc,"distance":round(asc-entry_level,2)})
        targets.sort(key=lambda x:x["level"])
    else:
        # Find descending cones below entry
        for name in ["CLOSE","LOW","HIGH"]:
            desc=cones[name]["desc"]
            if desc<entry_level:
                targets.append({"name":f"{name} Desc","level":desc,"distance":round(entry_level-desc,2)})
        targets.sort(key=lambda x:x["level"],reverse=True)
    return targets

# ═══════════════════════════════════════════════════════════════════════════════
# 8:30 CANDLE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
def validate_830_candle(candle_ohlc,ceiling,floor,position):
    """
    Validate 8:30 candle behavior:
    - If broken below: candle should touch floor and close below it
    - If broken above: candle should drop to ceiling and close above it
    - If inside: wait for breakout then retest
    """
    if candle_ohlc is None:
        return {"status":"AWAITING","message":"Waiting for 8:30 candle data"}
    
    o,h,l,c=candle_ohlc["open"],candle_ohlc["high"],candle_ohlc["low"],candle_ohlc["close"]
    
    if position in ["BELOW","MARGINAL_BELOW"]:
        # Expecting candle to rise to floor and close below
        touched_floor=h>=floor-2  # Within 2 pts
        closed_below=c<floor
        closed_inside=c>=floor and c<=ceiling
        
        if touched_floor and closed_below:
            return {"status":"VALID","message":"✅ Touched floor, closed below","setup":"PUTS","entry_edge":"floor"}
        elif touched_floor and closed_inside:
            return {"status":"TREND_DAY","message":"⚡ Touched floor, closed inside - TREND DAY","setup":"BOTH"}
        elif c>floor:
            return {"status":"INVALIDATED","message":"❌ Closed above floor - expect rally to ceiling","setup":"WAIT_CEILING"}
        else:
            return {"status":"PARTIAL","message":"⏳ Didn't touch floor yet","setup":"WAIT"}
    
    elif position in ["ABOVE","MARGINAL_ABOVE"]:
        # Expecting candle to drop to ceiling and close above
        touched_ceiling=l<=ceiling+2
        closed_above=c>ceiling
        closed_inside=c>=floor and c<=ceiling
        
        if touched_ceiling and closed_above:
            return {"status":"VALID","message":"✅ Touched ceiling, closed above","setup":"CALLS","entry_edge":"ceiling"}
        elif touched_ceiling and closed_inside:
            return {"status":"TREND_DAY","message":"⚡ Touched ceiling, closed inside - TREND DAY","setup":"BOTH"}
        elif c<ceiling:
            return {"status":"INVALIDATED","message":"❌ Closed below ceiling - expect drop to floor","setup":"WAIT_FLOOR"}
        else:
            return {"status":"PARTIAL","message":"⏳ Didn't touch ceiling yet","setup":"WAIT"}
    
    else:  # INSIDE
        # Wait for breakout
        if c>ceiling:
            return {"status":"BREAKOUT_UP","message":"📈 Broke above channel - wait for retest of ceiling","setup":"CALLS_RETEST"}
        elif c<floor:
            return {"status":"BREAKOUT_DOWN","message":"📉 Broke below channel - wait for retest of floor","setup":"PUTS_RETEST"}
        else:
            return {"status":"INSIDE","message":"⏸️ Still inside channel - wait for breakout","setup":"WAIT"}
    
    return {"status":"UNKNOWN","message":"Unable to determine","setup":"WAIT"}

# ═══════════════════════════════════════════════════════════════════════════════
# FLOW BIAS (Multi-Signal)
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_flow_bias(price,on_high,on_low,vix,vix_high,vix_low,prior_close,es_candles=None):
    signals=[]
    score=0
    on_range=on_high-on_low
    on_mid=(on_high+on_low)/2
    
    # Signal 1: Price Position (30%)
    price_pos=(price-on_low)/on_range*100 if on_range>0 else 50
    if price>on_high:score+=30;signals.append(("Price","CALLS",f"Above O/N High (+{price-on_high:.0f})"))
    elif price<on_low:score-=30;signals.append(("Price","PUTS",f"Below O/N Low ({price-on_low:.0f})"))
    elif price_pos>75:score+=15;signals.append(("Price","CALLS",f"Near High ({price_pos:.0f}%)"))
    elif price_pos<25:score-=15;signals.append(("Price","PUTS",f"Near Low ({price_pos:.0f}%)"))
    else:signals.append(("Price","NEUTRAL",f"Mid ({price_pos:.0f}%)"))
    
    # Signal 2: VIX (25%)
    vix_range=vix_high-vix_low
    vix_pos=(vix-vix_low)/vix_range*100 if vix_range>0 else 50
    if vix>vix_high:score-=25;signals.append(("VIX","PUTS",f"Breakout ({vix:.1f})"))
    elif vix<vix_low:score+=25;signals.append(("VIX","CALLS",f"Breakdown ({vix:.1f})"))
    elif vix_pos>70:score-=12;signals.append(("VIX","PUTS",f"Elevated ({vix_pos:.0f}%)"))
    elif vix_pos<30:score+=12;signals.append(("VIX","CALLS",f"Low ({vix_pos:.0f}%)"))
    else:signals.append(("VIX","NEUTRAL",f"Mid ({vix_pos:.0f}%)"))
    
    # Signal 3: Gap (25%)
    gap=price-prior_close
    if gap>10:score+=25;signals.append(("Gap","CALLS",f"+{gap:.0f} pts"))
    elif gap<-10:score-=25;signals.append(("Gap","PUTS",f"{gap:.0f} pts"))
    elif gap>5:score+=12;signals.append(("Gap","CALLS",f"+{gap:.0f} pts"))
    elif gap<-5:score-=12;signals.append(("Gap","PUTS",f"{gap:.0f} pts"))
    else:signals.append(("Gap","NEUTRAL",f"{gap:+.0f} pts"))
    
    # Signal 4: Velocity (20%)
    if es_candles is not None and len(es_candles)>=6:
        recent=es_candles.tail(6)
        move=recent['Close'].iloc[-1]-recent['Open'].iloc[0]
        avg_range=(recent['High']-recent['Low']).mean()
        if move>avg_range*2:score+=20;signals.append(("Velocity","CALLS",f"+{move:.0f}"))
        elif move<-avg_range*2:score-=20;signals.append(("Velocity","PUTS",f"{move:.0f}"))
        elif move>avg_range:score+=10;signals.append(("Velocity","CALLS",f"+{move:.0f}"))
        elif move<-avg_range:score-=10;signals.append(("Velocity","PUTS",f"{move:.0f}"))
        else:signals.append(("Velocity","NEUTRAL","Choppy"))
    
    # Determine bias
    if score>=30:bias="HEAVY_CALLS"
    elif score<=-30:bias="HEAVY_PUTS"
    else:bias="NEUTRAL"
    
    return {"bias":bias,"score":score,"signals":signals,"price_pos":round(price_pos,1),"vix_pos":round(vix_pos,1)}

# ═══════════════════════════════════════════════════════════════════════════════
# MOMENTUM
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_momentum(es_candles,ma_bias="NEUTRAL"):
    if es_candles is None or len(es_candles)<26:
        return {"signal":"NEUTRAL","rsi":50,"macd":0,"detail":"Insufficient data"}
    
    close=es_candles['Close']
    
    # RSI
    delta=close.diff()
    gain=(delta.where(delta>0,0)).rolling(14).mean()
    loss=(-delta.where(delta<0,0)).rolling(14).mean()
    rs=gain/loss
    rsi=100-(100/(1+rs))
    rsi_val=round(rsi.iloc[-1],1) if not pd.isna(rsi.iloc[-1]) else 50
    
    # MACD
    ema12=close.ewm(span=12).mean()
    ema26=close.ewm(span=26).mean()
    macd_hist=round((ema12-ema26-(ema12-ema26).ewm(span=9).mean()).iloc[-1],2)
    
    # Signal
    if ma_bias=="LONG" and 50<=rsi_val<=60 and macd_hist>0:
        signal,detail="PULLBACK BUY","RSI pullback + MACD green"
    elif ma_bias=="SHORT" and 40<=rsi_val<=50 and macd_hist<0:
        signal,detail="BOUNCE SELL","RSI bounce + MACD red"
    elif rsi_val>50 and macd_hist>0:
        signal,detail="BULLISH","RSI>50, MACD green"
    elif rsi_val<50 and macd_hist<0:
        signal,detail="BEARISH","RSI<50, MACD red"
    else:
        signal,detail="NEUTRAL","Mixed"
    
    return {"signal":signal,"rsi":rsi_val,"macd":macd_hist,"detail":detail}

# ═══════════════════════════════════════════════════════════════════════════════
# MA BIAS
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_ma_bias(es_candles):
    if es_candles is None or len(es_candles)<50:
        return {"signal":"NEUTRAL","ema50":None,"sma200":None}
    close=es_candles['Close']
    ema50=close.ewm(span=50).mean().iloc[-1]
    sma200=close.rolling(min(200,len(close))).mean().iloc[-1]
    if ema50>sma200:signal="LONG"
    elif ema50<sma200:signal="SHORT"
    else:signal="NEUTRAL"
    return {"signal":signal,"ema50":round(ema50,2),"sma200":round(sma200,2)}

# ═══════════════════════════════════════════════════════════════════════════════
# OPTION PRICING
# ═══════════════════════════════════════════════════════════════════════════════
def get_strike(entry_level,option_type):
    """20 pts OTM from entry level"""
    if option_type=="CALL":
        return int(round((entry_level+20)/5)*5)
    return int(round((entry_level-20)/5)*5)

def estimate_prices(spx,entry_level,strike,opt_type,vix,hours_to_expiry):
    iv=vix/100
    T=hours_to_expiry/(365*24)
    
    # Current price
    curr=black_scholes(spx,strike,T,0.05,iv,opt_type)
    
    # Entry price (at entry level, ~30min later)
    T_entry=max(0.001,(hours_to_expiry-0.5)/(365*24))
    entry=black_scholes(entry_level,strike,T_entry,0.05,iv,opt_type)
    
    return {"current":round(curr,2),"entry":round(entry,2)}

def estimate_exit_prices(entry_level,strike,opt_type,vix,hours_to_expiry,targets):
    """Estimate option price at each target"""
    iv=vix/100
    results=[]
    entry_T=max(0.001,(hours_to_expiry-0.5)/(365*24))
    entry_price=black_scholes(entry_level,strike,entry_T,0.05,iv,opt_type)
    
    for i,tgt in enumerate(targets[:3]):
        # Estimate time to reach target (~1-2 hours)
        est_hours=1+i*0.5
        T_exit=max(0.001,(hours_to_expiry-est_hours)/(365*24))
        exit_price=black_scholes(tgt["level"],strike,T_exit,0.05,iv,opt_type)
        pct=(exit_price-entry_price)/entry_price*100 if entry_price>0 else 0
        results.append({"target":tgt["name"],"level":tgt["level"],"price":round(exit_price,2),"pct":round(pct,0)})
    
    return results,round(entry_price,2)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE SCORE
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_confidence(channel_type,position,flow_bias,vix_zone,momentum,has_confluence):
    score=0
    factors=[]
    
    # Channel clarity (25%)
    if channel_type!="UNDETERMINED":
        score+=25
        factors.append(("Channel",25,"Clear"))
    else:
        factors.append(("Channel",0,"Unclear"))
    
    # Position clarity (25%)
    if position in ["ABOVE","BELOW"]:
        score+=25
        factors.append(("Position",25,"Clean break"))
    elif position in ["MARGINAL_ABOVE","MARGINAL_BELOW"]:
        score+=15
        factors.append(("Position",15,"Marginal"))
    else:
        score+=5
        factors.append(("Position",5,"Inside"))
    
    # Flow alignment (20%)
    if flow_bias["bias"]!="NEUTRAL":
        score+=20
        factors.append(("Flow",20,flow_bias["bias"]))
    else:
        score+=10
        factors.append(("Flow",10,"Neutral"))
    
    # VIX regime (15%)
    if vix_zone in ["LOW","NORMAL"]:
        score+=15
        factors.append(("VIX",15,vix_zone))
    elif vix_zone in ["ELEVATED"]:
        score+=10
        factors.append(("VIX",10,vix_zone))
    else:
        score+=5
        factors.append(("VIX",5,vix_zone))
    
    # Confluence (15%)
    if has_confluence:
        score+=15
        factors.append(("Confluence",15,"Yes"))
    else:
        factors.append(("Confluence",0,"No"))
    
    return score,factors

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    saved=load_inputs()
    
    with st.sidebar:
        st.markdown("## 🔮 SPX Prophet V6.0")
        st.markdown("*Unified Trading System*")
        
        trading_date=st.date_input("📅 Trading Date",value=date.today())
        
        st.markdown("---")
        st.markdown("### ⚙️ ES/SPX Offset")
        offset_mode=st.radio("Offset Mode",["Auto","Manual"],horizontal=True)
        if offset_mode=="Manual":
            offset=st.number_input("SPX = ES - Offset",value=float(saved.get("offset",18.0)),step=0.5)
        else:
            offset=None
        
        st.markdown("---")
        st.markdown("### 🌏 Session Data")
        session_mode=st.radio("Session Detection",["Auto","Manual"],horizontal=True)
        
        if session_mode=="Manual":
            st.markdown("**Sydney (ES)**")
            c1,c2=st.columns(2)
            sydney_high=c1.number_input("High",value=float(saved.get("sydney_high",6070)),step=0.5,key="sh")
            sydney_low=c2.number_input("Low",value=float(saved.get("sydney_low",6050)),step=0.5,key="sl")
            
            st.markdown("**Tokyo (ES)**")
            c1,c2=st.columns(2)
            tokyo_high=c1.number_input("High",value=float(saved.get("tokyo_high",6075)),step=0.5,key="th")
            tokyo_low=c2.number_input("Low",value=float(saved.get("tokyo_low",6045)),step=0.5,key="tl")
        else:
            sydney_high=sydney_low=tokyo_high=tokyo_low=None
        
        st.markdown("---")
        st.markdown("### 📐 O/N Structure (ES)")
        HOURS=list(range(24))
        MINS=[0,15,30,45]
        
        c1,c2,c3=st.columns([2,1,1])
        on_high=c1.number_input("O/N High",value=float(saved.get("on_high",6075)),step=0.5)
        on_high_hr=c2.selectbox("Hr",HOURS,index=int(saved.get("on_high_hr",22)),key="ohh")
        on_high_mn=c3.selectbox("Mn",MINS,index=0,key="ohm")
        
        c1,c2,c3=st.columns([2,1,1])
        on_low=c1.number_input("O/N Low",value=float(saved.get("on_low",6040)),step=0.5)
        on_low_hr=c2.selectbox("Hr",HOURS,index=int(saved.get("on_low_hr",3)),key="olh")
        on_low_mn=c3.selectbox("Mn",MINS,index=0,key="olm")
        
        st.markdown("---")
        st.markdown("### ⚡ VIX")
        c1,c2=st.columns(2)
        vix_high=c1.number_input("O/N High",value=float(saved.get("vix_high",18)),step=0.1,key="vh")
        vix_low=c2.number_input("O/N Low",value=float(saved.get("vix_low",15)),step=0.1,key="vl")
        
        st.markdown("---")
        st.markdown("### 📊 Prior Day (ES)")
        c1,c2=st.columns(2)
        prior_high=c1.number_input("High",value=float(saved.get("prior_high",6080)),step=0.5,key="ph")
        prior_low=c2.number_input("Low",value=float(saved.get("prior_low",6030)),step=0.5,key="pl")
        prior_close=st.number_input("Close",value=float(saved.get("prior_close",6055)),step=0.5)
        
        st.markdown("---")
        st.markdown("### 📊 8:30 Candle (ES)")
        candle_mode=st.radio("Source",["Auto","Manual"],horizontal=True,key="cm")
        if candle_mode=="Manual":
            c1,c2=st.columns(2)
            c830_o=c1.number_input("Open",value=0.0,step=0.5,key="c8o")
            c830_h=c2.number_input("High",value=0.0,step=0.5,key="c8h")
            c1,c2=st.columns(2)
            c830_l=c1.number_input("Low",value=0.0,step=0.5,key="c8l")
            c830_c=c2.number_input("Close",value=0.0,step=0.5,key="c8c")
            candle_830={"open":c830_o,"high":c830_h,"low":c830_l,"close":c830_c} if c830_o>0 else None
        else:
            candle_830=None
        
        st.markdown("---")
        ref_time_sel=st.selectbox("Reference Time",["8:30 AM","9:00 AM","9:30 AM"],index=1)
        ref_map={"8:30 AM":(8,30),"9:00 AM":(9,0),"9:30 AM":(9,30)}
        ref_hr,ref_mn=ref_map[ref_time_sel]
        
        st.markdown("---")
        auto_refresh=st.checkbox("Auto Refresh",value=False)
        refresh_sec=st.slider("Seconds",15,120,30) if auto_refresh else 30
        debug=st.checkbox("Debug",value=False)
        
        if st.button("💾 Save",use_container_width=True):
            save_inputs({"offset":offset,"sydney_high":sydney_high,"sydney_low":sydney_low,"tokyo_high":tokyo_high,"tokyo_low":tokyo_low,"on_high":on_high,"on_high_hr":on_high_hr,"on_low":on_low,"on_low_hr":on_low_hr,"vix_high":vix_high,"vix_low":vix_low,"prior_high":prior_high,"prior_low":prior_low,"prior_close":prior_close})
            st.success("✅ Saved")
    
    prev_day=trading_date-timedelta(days=1)
    
    def make_time(hr,mn):
        if hr>=17:return CT.localize(datetime.combine(prev_day,time(hr,mn)))
        return CT.localize(datetime.combine(trading_date,time(hr,mn)))
    
    return {
        "trading_date":trading_date,
        "offset_mode":offset_mode,
        "offset":offset,
        "session_mode":session_mode,
        "sydney_high":sydney_high,"sydney_low":sydney_low,
        "tokyo_high":tokyo_high,"tokyo_low":tokyo_low,
        "on_high":on_high,"on_high_time":make_time(on_high_hr,on_high_mn),
        "on_low":on_low,"on_low_time":make_time(on_low_hr,on_low_mn),
        "vix_high":vix_high,"vix_low":vix_low,
        "prior_high":prior_high,"prior_low":prior_low,"prior_close":prior_close,
        "prior_high_time":CT.localize(datetime.combine(prev_day,time(10,0))),
        "prior_low_time":CT.localize(datetime.combine(prev_day,time(14,0))),
        "prior_close_time":CT.localize(datetime.combine(prev_day,time(15,0))),
        "candle_830":candle_830,"candle_mode":candle_mode,
        "ref_hr":ref_hr,"ref_mn":ref_mn,
        "auto_refresh":auto_refresh,"refresh_sec":refresh_sec,"debug":debug
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(STYLES,unsafe_allow_html=True)
    inputs=render_sidebar()
    now=now_ct()
    
    # Fetch data
    with st.spinner("Loading..."):
        es_candles=fetch_es_candles()
        es_price=fetch_es_current()
        spx_price=fetch_spx_polygon()
        vix=fetch_vix_polygon() or 16.0
    
    # Calculate offset
    if inputs["offset_mode"]=="Auto" and es_price and spx_price:
        offset=round(es_price-spx_price,2)
    elif inputs["offset"]:
        offset=inputs["offset"]
    else:
        offset=18.0
    
    # Convert ES inputs to SPX equivalent
    if es_price:
        spx_est=round(es_price-offset,2)
    else:
        spx_est=spx_price or 6050.0
    
    current_spx=spx_price or spx_est
    current_es=es_price or (current_spx+offset)
    
    # Session detection
    if inputs["session_mode"]=="Auto":
        session_data=get_session_levels(es_candles,inputs["trading_date"])
        if session_data:
            syd_h,syd_l=session_data.get("sydney_high",inputs["on_high"]),session_data.get("sydney_low",inputs["on_low"])
            tok_h,tok_l=session_data.get("tokyo_high",inputs["on_high"]),session_data.get("tokyo_low",inputs["on_low"])
        else:
            syd_h,syd_l,tok_h,tok_l=inputs["on_high"],inputs["on_low"],inputs["on_high"],inputs["on_low"]
    else:
        syd_h,syd_l=inputs["sydney_high"] or inputs["on_high"],inputs["sydney_low"] or inputs["on_low"]
        tok_h,tok_l=inputs["tokyo_high"] or inputs["on_high"],inputs["tokyo_low"] or inputs["on_low"]
    
    # Determine channel
    channel_type,channel_reason=determine_channel(syd_h,syd_l,tok_h,tok_l)
    
    # Reference time
    ref_time=CT.localize(datetime.combine(inputs["trading_date"],time(inputs["ref_hr"],inputs["ref_mn"])))
    expiry_time=CT.localize(datetime.combine(inputs["trading_date"],time(15,0)))
    hours_to_expiry=max(0.1,(expiry_time-now).total_seconds()/3600)
    
    # Calculate channel levels (ES)
    levels_es=calculate_channel_levels(inputs["on_high"],inputs["on_high_time"],inputs["on_low"],inputs["on_low_time"],ref_time)
    
    # Get active channel edges (ES)
    ceiling_es,floor_es,ceil_key,floor_key=get_channel_edges(levels_es,channel_type)
    
    # Convert to SPX
    ceiling_spx=round(ceiling_es-offset,2) if ceiling_es else None
    floor_spx=round(floor_es-offset,2) if floor_es else None
    
    # Assess position
    if ceiling_es and floor_es:
        position,pos_desc,pos_dist=assess_position(current_es,ceiling_es,floor_es)
    else:
        position,pos_desc,pos_dist="UNKNOWN","undetermined",0
    
    # Cones (ES then convert)
    cones_es=calculate_cones(inputs["prior_high"],inputs["prior_high_time"],inputs["prior_low"],inputs["prior_low_time"],inputs["prior_close"],inputs["prior_close_time"],ref_time)
    cones_spx={k:{"anchor":round(v["anchor"]-offset,2),"asc":round(v["asc"]-offset,2),"desc":round(v["desc"]-offset,2)} for k,v in cones_es.items()}
    
    # 8:30 candle validation
    candle_830=inputs["candle_830"]
    if candle_830 and ceiling_es and floor_es:
        validation=validate_830_candle(candle_830,ceiling_es,floor_es,position)
    else:
        validation={"status":"AWAITING","message":"Waiting for 8:30 candle","setup":"WAIT"}
    
    # Flow bias
    flow=calculate_flow_bias(current_es,inputs["on_high"],inputs["on_low"],vix,inputs["vix_high"],inputs["vix_low"],inputs["prior_close"],es_candles)
    
    # MA Bias & Momentum
    ma_bias=calculate_ma_bias(es_candles)
    momentum=calculate_momentum(es_candles,ma_bias["signal"])
    
    # VIX zone
    vix_zone=get_vix_zone(vix)
    
    # Determine trading phase
    market_open=CT.localize(datetime.combine(inputs["trading_date"],time(8,30)))
    entry_start=CT.localize(datetime.combine(inputs["trading_date"],time(9,0)))
    entry_end=CT.localize(datetime.combine(inputs["trading_date"],time(9,10)))
    
    if now<market_open:
        phase="PRE_MARKET"
        phase_label="Pre-Market Planning"
    elif now<entry_start:
        phase="VALIDATING"
        phase_label="8:30 Candle Validation"
    elif now<=entry_end:
        phase="ENTRY_WINDOW"
        phase_label="Entry Window (9:00-9:10)"
    else:
        phase="ACTIVE"
        phase_label="Active Trading"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HERO
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(f'''<div class="hero">
<div class="hero-title">🔮 SPX PROPHET V6.0</div>
<div class="hero-sub">ES: {current_es:,.2f} | Offset: {offset:+.2f} | {channel_type} Channel</div>
<div class="hero-price">{current_spx:,.2f}</div>
<div style="font-family:IBM Plex Mono;font-size:13px;color:rgba(255,255,255,0.5)">{now.strftime("%I:%M:%S %p CT")} | {inputs["trading_date"].strftime("%A, %B %d")}</div>
</div>''',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMMAND CENTER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🎯 Trade Command Center")
    
    # Channel info
    ch_color="#00d4aa" if channel_type=="RISING" else "#ff4757" if channel_type=="FALLING" else "#ffa502"
    ch_icon="▲" if channel_type=="RISING" else "▼" if channel_type=="FALLING" else "◆"
    
    # Position color
    pos_color="#ff4757" if "BELOW" in position else "#00d4aa" if "ABOVE" in position else "#ffa502"
    
    # Build command card
    cmd_html=f'''<div class="cmd-card">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
<div><div class="cmd-title">Today's Trading Plan</div><div style="font-size:12px;color:rgba(255,255,255,0.6)">{channel_reason}</div></div>
<span class="phase-badge">{phase_label}</span>
</div>

<div class="channel-box">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
<span style="font-size:14px;font-weight:600;color:{ch_color}">{ch_icon} {channel_type} CHANNEL</span>
<span style="font-size:12px;color:rgba(255,255,255,0.5)">Width: {round((ceiling_es or 0)-(floor_es or 0),1)} pts</span>
</div>
<div class="level-row"><span class="level-name">Ceiling ({ceil_key or "N/A"})</span><span class="level-val" style="color:#00d4aa">ES {ceiling_es or "—"} → SPX {ceiling_spx or "—"}</span></div>
<div class="level-row"><span class="level-name">Floor ({floor_key or "N/A"})</span><span class="level-val" style="color:#ff4757">ES {floor_es or "—"} → SPX {floor_spx or "—"}</span></div>
<div class="level-row" style="border:none"><span class="level-name">Current Position</span><span class="level-val" style="color:{pos_color}">{position} ({pos_desc}, {pos_dist:.1f} pts)</span></div>
</div>'''
    
    # 8:30 Candle Status
    val_color="#00d4aa" if validation["status"]=="VALID" else "#ff4757" if validation["status"]=="INVALIDATED" else "#ffa502"
    cmd_html+=f'''<div style="background:rgba(255,255,255,0.02);border-radius:10px;padding:12px;margin:12px 0">
<div style="font-size:12px;color:rgba(255,255,255,0.5);margin-bottom:6px">8:30 AM Candle Status</div>
<div style="font-size:14px;font-weight:600;color:{val_color}">{validation["message"]}</div>
</div>'''
    
    # Scenario Planning
    if position in ["BELOW","MARGINAL_BELOW"] and floor_spx:
        # Setup for PUTS
        entry_edge_spx=floor_spx
        targets_puts=find_targets(entry_edge_spx,cones_spx,"PUTS")
        strike_put=get_strike(entry_edge_spx,"PUT")
        
        exits_puts,entry_price_put=estimate_exit_prices(entry_edge_spx,strike_put,"PUT",vix,hours_to_expiry,targets_puts)
        
        targets_html=""
        for i,t in enumerate(exits_puts):
            highlight="border:1px solid #00d4aa;background:rgba(0,212,170,0.1)" if i==0 else ""
            targets_html+=f'<div style="display:flex;justify-content:space-between;padding:6px 8px;border-radius:6px;margin:4px 0;{highlight}"><span>{t["target"]} @ {t["level"]}</span><span style="color:{"#00d4aa" if t["pct"]>0 else "#ff4757"}">${t["price"]} ({t["pct"]:+.0f}%)</span></div>'
        
        cmd_html+=f'''<div class="scenario valid">
<div class="scenario-h" style="color:#00d4aa">✅ IF VALID: 8:30 touches floor ({floor_spx}), closes below</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
<div><div style="font-size:11px;color:rgba(255,255,255,0.5)">Entry</div><div style="font-size:14px;font-weight:600">9:00-9:10 AM</div></div>
<div><div style="font-size:11px;color:rgba(255,255,255,0.5)">Direction</div><div style="font-size:14px;font-weight:600;color:#ff4757">🔴 PUTS</div></div>
<div><div style="font-size:11px;color:rgba(255,255,255,0.5)">Strike</div><div style="font-size:14px;font-weight:600">{strike_put} PUT</div></div>
<div><div style="font-size:11px;color:rgba(255,255,255,0.5)">Entry Est</div><div style="font-size:14px;font-weight:600">${entry_price_put}</div></div>
</div>
<div class="target-box"><div class="target-h">📍 Targets (Descending Cones)</div>{targets_html if targets_html else "<div style='color:rgba(255,255,255,0.5)'>No targets found below</div>"}</div>
</div>'''
        
        # Invalidation scenario
        cmd_html+=f'''<div class="scenario invalid">
<div class="scenario-h" style="color:#ff4757">❌ IF INVALID: Closes above floor ({floor_spx})</div>
<div style="font-size:13px;color:rgba(255,255,255,0.7)">Price likely rallies to Ceiling ({ceiling_spx}) → Wait for PUT setup there</div>
</div>'''
    
    elif position in ["ABOVE","MARGINAL_ABOVE"] and ceiling_spx:
        # Setup for CALLS
        entry_edge_spx=ceiling_spx
        targets_calls=find_targets(entry_edge_spx,cones_spx,"CALLS")
        strike_call=get_strike(entry_edge_spx,"CALL")
        
        exits_calls,entry_price_call=estimate_exit_prices(entry_edge_spx,strike_call,"CALL",vix,hours_to_expiry,targets_calls)
        
        targets_html=""
        for i,t in enumerate(exits_calls):
            highlight="border:1px solid #00d4aa;background:rgba(0,212,170,0.1)" if i==0 else ""
            targets_html+=f'<div style="display:flex;justify-content:space-between;padding:6px 8px;border-radius:6px;margin:4px 0;{highlight}"><span>{t["target"]} @ {t["level"]}</span><span style="color:{"#00d4aa" if t["pct"]>0 else "#ff4757"}">${t["price"]} ({t["pct"]:+.0f}%)</span></div>'
        
        cmd_html+=f'''<div class="scenario valid">
<div class="scenario-h" style="color:#00d4aa">✅ IF VALID: 8:30 touches ceiling ({ceiling_spx}), closes above</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
<div><div style="font-size:11px;color:rgba(255,255,255,0.5)">Entry</div><div style="font-size:14px;font-weight:600">9:00-9:10 AM</div></div>
<div><div style="font-size:11px;color:rgba(255,255,255,0.5)">Direction</div><div style="font-size:14px;font-weight:600;color:#00d4aa">🟢 CALLS</div></div>
<div><div style="font-size:11px;color:rgba(255,255,255,0.5)">Strike</div><div style="font-size:14px;font-weight:600">{strike_call} CALL</div></div>
<div><div style="font-size:11px;color:rgba(255,255,255,0.5)">Entry Est</div><div style="font-size:14px;font-weight:600">${entry_price_call}</div></div>
</div>
<div class="target-box"><div class="target-h">📍 Targets (Ascending Cones)</div>{targets_html if targets_html else "<div style='color:rgba(255,255,255,0.5)'>No targets found above</div>"}</div>
</div>'''
        
        cmd_html+=f'''<div class="scenario invalid">
<div class="scenario-h" style="color:#ff4757">❌ IF INVALID: Closes below ceiling ({ceiling_spx})</div>
<div style="font-size:13px;color:rgba(255,255,255,0.7)">Price likely drops to Floor ({floor_spx}) → Wait for CALL setup there</div>
</div>'''
    
    elif position=="INSIDE" and ceiling_spx and floor_spx:
        # Inside channel - show both edges
        cmd_html+=f'''<div class="scenario" style="border-left-color:#ffa502">
<div class="scenario-h" style="color:#ffa502">⏸️ INSIDE CHANNEL - Wait for 8:30 breakout</div>
<div style="font-size:13px;color:rgba(255,255,255,0.7);margin-bottom:10px">Price is inside channel. Wait for 8:30 candle to break one edge, then trade the retest.</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
<div style="background:rgba(0,212,170,0.1);border-radius:8px;padding:10px">
<div style="font-size:11px;color:#00d4aa;font-weight:600">IF BREAKS UP</div>
<div style="font-size:12px">Wait for retest of {ceiling_spx}</div>
<div style="font-size:12px">Entry: CALLS at 9:00-9:30</div>
</div>
<div style="background:rgba(255,71,87,0.1);border-radius:8px;padding:10px">
<div style="font-size:11px;color:#ff4757;font-weight:600">IF BREAKS DOWN</div>
<div style="font-size:12px">Wait for retest of {floor_spx}</div>
<div style="font-size:12px">Entry: PUTS at 9:00-9:30</div>
</div>
</div>
</div>'''
    
    # Trend Day detection
    if validation["status"]=="TREND_DAY" and ceiling_spx and floor_spx:
        # Show both trades
        strike_call=get_strike(floor_spx,"CALL")
        strike_put=get_strike(ceiling_spx,"PUT")
        
        cmd_html+=f'''<div class="scenario" style="border-left-color:#a855f7;background:rgba(168,85,247,0.1)">
<div class="scenario-h" style="color:#a855f7">⚡ TREND DAY DETECTED - Trade the Range</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px">
<div style="background:rgba(0,212,170,0.1);border-radius:8px;padding:10px">
<div style="font-size:12px;color:#00d4aa;font-weight:600">🟢 BUY at Floor ({floor_spx})</div>
<div style="font-size:12px">Strike: {strike_call} CALL</div>
<div style="font-size:12px">Target: Ceiling ({ceiling_spx})</div>
</div>
<div style="background:rgba(255,71,87,0.1);border-radius:8px;padding:10px">
<div style="font-size:12px;color:#ff4757;font-weight:600">🔴 SELL at Ceiling ({ceiling_spx})</div>
<div style="font-size:12px">Strike: {strike_put} PUT</div>
<div style="font-size:12px">Target: Floor ({floor_spx})</div>
</div>
</div>
</div>'''
    
    cmd_html+="</div>"
    st.markdown(cmd_html,unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONFIDENCE & SUPPORTING FACTORS
    # ═══════════════════════════════════════════════════════════════════════════
    has_confluence=False  # Simplified for now
    confidence,conf_factors=calculate_confidence(channel_type,position,flow,vix_zone,momentum,has_confluence)
    
    col1,col2,col3=st.columns(3)
    
    with col1:
        # Confidence
        conf_color="#00d4aa" if confidence>=70 else "#ffa502" if confidence>=50 else "#ff4757"
        factors_html="".join([f'<div class="pillar"><span style="color:rgba(255,255,255,0.6)">{f[0]}</span><span style="color:{"#00d4aa" if f[1]>10 else "rgba(255,255,255,0.7)"}">{f[2]} (+{f[1]})</span></div>' for f in conf_factors])
        
        st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(168,85,247,0.15)">📊</div><div><div class="card-title">Confidence</div><div class="card-sub">Pre-Market Score</div></div></div>
<div class="metric" style="color:{conf_color}">{confidence}%</div>
<div class="conf-bar"><div class="conf-fill" style="width:{confidence}%;background:{conf_color}"></div></div>
{factors_html}
</div>''',unsafe_allow_html=True)
    
    with col2:
        # Flow Bias
        flow_color="#00d4aa" if flow["bias"]=="HEAVY_CALLS" else "#ff4757" if flow["bias"]=="HEAVY_PUTS" else "#ffa502"
        meter_pos=(flow["score"]+100)/2
        
        signals_html="".join([f'<div class="pillar"><span>{s[0]}</span><span style="color:{"#00d4aa" if s[1]=="CALLS" else "#ff4757" if s[1]=="PUTS" else "rgba(255,255,255,0.5)"}">{s[2]}</span></div>' for s in flow["signals"]])
        
        st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(34,211,238,0.15)">🌊</div><div><div class="card-title">Flow Bias</div><div class="card-sub">{flow["bias"].replace("_"," ")}</div></div></div>
<div class="metric" style="color:{flow_color}">{flow["score"]:+d}</div>
<div class="flow-meter"><div class="flow-marker" style="left:{meter_pos}%"></div></div>
{signals_html}
</div>''',unsafe_allow_html=True)
    
    with col3:
        # Market Context
        ma_color="#00d4aa" if ma_bias["signal"]=="LONG" else "#ff4757" if ma_bias["signal"]=="SHORT" else "#ffa502"
        mom_color="#00d4aa" if "BULL" in momentum["signal"] or "BUY" in momentum["signal"] else "#ff4757" if "BEAR" in momentum["signal"] or "SELL" in momentum["signal"] else "#ffa502"
        
        st.markdown(f'''<div class="card">
<div class="card-h"><div class="card-icon" style="background:rgba(59,130,246,0.15)">📈</div><div><div class="card-title">Market Context</div><div class="card-sub">Trend & Momentum</div></div></div>
<div class="pillar"><span>MA Bias</span><span style="color:{ma_color}">{ma_bias["signal"]}</span></div>
<div class="pillar"><span>Momentum</span><span style="color:{mom_color}">{momentum["signal"]}</span></div>
<div class="pillar"><span>RSI</span><span>{momentum["rsi"]}</span></div>
<div class="pillar"><span>MACD</span><span style="color:{"#00d4aa" if momentum["macd"]>0 else "#ff4757"}">{momentum["macd"]:+.2f}</span></div>
<div class="pillar"><span>VIX</span><span>{vix:.1f} ({vix_zone})</span></div>
</div>''',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONE RAILS
    # ═══════════════════════════════════════════════════════════════════════════
    with st.expander("📊 Cone Rails (SPX)"):
        cone_html="".join([f'<div class="pillar"><span>{n}</span><span>Anchor: {c["anchor"]} | <span style="color:#00d4aa">Asc: {c["asc"]}</span> | <span style="color:#ff4757">Desc: {c["desc"]}</span></span></div>' for n,c in cones_spx.items()])
        st.markdown(f'<div class="card">{cone_html}</div>',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ALL 4 STRUCTURE LEVELS
    # ═══════════════════════════════════════════════════════════════════════════
    with st.expander("📐 All Structure Levels"):
        all_levels=[
            ("Ceiling Rising",levels_es["ceiling_rising"]["level"],round(levels_es["ceiling_rising"]["level"]-offset,2),"PUTS"),
            ("Ceiling Falling",levels_es["ceiling_falling"]["level"],round(levels_es["ceiling_falling"]["level"]-offset,2),"CALLS"),
            ("Floor Rising",levels_es["floor_rising"]["level"],round(levels_es["floor_rising"]["level"]-offset,2),"PUTS"),
            ("Floor Falling",levels_es["floor_falling"]["level"],round(levels_es["floor_falling"]["level"]-offset,2),"CALLS"),
        ]
        all_levels.sort(key=lambda x:x[1],reverse=True)
        
        levels_html=""
        for name,es_lvl,spx_lvl,entry_type in all_levels:
            dist=current_es-es_lvl
            active=" (ACTIVE)" if name.lower().replace(" ","_")==ceil_key or name.lower().replace(" ","_")==floor_key else ""
            color="#a855f7" if active else "rgba(255,255,255,0.7)"
            levels_html+=f'<div class="pillar"><span style="color:{color}">{name}{active}</span><span>ES {es_lvl} → SPX {spx_lvl} | {entry_type} | Dist: {dist:+.1f}</span></div>'
        
        st.markdown(f'<div class="card">{levels_html}</div>',unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DEBUG
    # ═══════════════════════════════════════════════════════════════════════════
    if inputs["debug"]:
        st.markdown("### 🔧 Debug")
        st.json({
            "es_price":es_price,"spx_price":spx_price,"offset":offset,
            "sydney":(syd_h,syd_l),"tokyo":(tok_h,tok_l),
            "channel":channel_type,"position":position,
            "levels_es":levels_es,"validation":validation,
            "flow":flow,"momentum":momentum
        })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(f'<div class="footer">SPX PROPHET V6.0 | Unified Trading System | Slope: {SLOPE} | {now.strftime("%H:%M:%S CT")}</div>',unsafe_allow_html=True)
    
    if inputs["auto_refresh"]:
        time_module.sleep(inputs["refresh_sec"])
        st.rerun()

if __name__=="__main__":
    main()
