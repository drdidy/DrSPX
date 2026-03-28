"""
SPX Prophet — Data Fetcher Module
yfinance for prices → manual override available
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz
import streamlit as st

CT = pytz.timezone("America/Chicago")


# ═══════════════════════════════════════════════════════════════════════════════
# PRICE FETCHING (TT → YF → 0)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def fetch_es_price() -> tuple:
    """Returns (price, source)."""
    try:
        es = yf.Ticker("ES=F")
        data = es.history(period="2d", interval="1m")
        if not data.empty:
            return float(data["Close"].iloc[-1]), "yfinance"
        data = es.history(period="5d")
        if not data.empty:
            return float(data["Close"].iloc[-1]), "yfinance"
    except Exception:
        pass
    return 0.0, "none"


@st.cache_data(ttl=30)
def fetch_spx_price() -> tuple:
    """Returns (price, source)."""
    try:
        spx = yf.Ticker("^GSPC")
        data = spx.history(period="2d", interval="1m")
        if not data.empty:
            return float(data["Close"].iloc[-1]), "yfinance"
        data = spx.history(period="5d")
        if not data.empty:
            return float(data["Close"].iloc[-1]), "yfinance"
    except Exception:
        pass
    return 0.0, "none"


# ═══════════════════════════════════════════════════════════════════════════════
# 1-MIN ES DATA (for 8/50 EMA cross detection)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def fetch_es_1min() -> pd.DataFrame:
    """Fetch ES 1-min bars with EMAs calculated."""
    try:
        es = yf.Ticker("ES=F")
        df = es.history(period="2d", interval="1m")
        if df.empty:
            return pd.DataFrame()
        df.index = df.index.tz_convert(CT)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df["EMA_8"] = df["Close"].ewm(span=8, adjust=False).mean()
        df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
        df["Spread"] = df["EMA_8"] - df["EMA_50"]
        return df
    except Exception:
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
# AFTERNOON DATA (for auto-detection of bounces/rejections)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def fetch_afternoon_1min(trading_date: date) -> tuple:
    """
    Fetch 1-min ES data for the day BEFORE trading_date, 12-3 PM CT.
    Returns (DataFrame, actual_date_used) or (empty_df, None).
    """
    try:
        es = yf.Ticker("ES=F")
        df = es.history(period="7d", interval="1m")
        if df.empty:
            return pd.DataFrame(), None
        df.index = df.index.tz_convert(CT)

        # Find prior trading day
        prior = trading_date - timedelta(days=1)
        while prior.weekday() >= 5:
            prior -= timedelta(days=1)

        for attempt in range(3):
            day_data = df[df.index.date == prior]
            if not day_data.empty:
                afternoon = day_data.between_time(dtime(11, 25), dtime(15, 5))
                if not afternoon.empty:
                    return afternoon[["Open", "High", "Low", "Close", "Volume"]], prior
            prior -= timedelta(days=1)
            while prior.weekday() >= 5:
                prior -= timedelta(days=1)

        return pd.DataFrame(), None
    except Exception:
        return pd.DataFrame(), None


@st.cache_data(ttl=300)
def fetch_afternoon_30min(trading_date: date) -> tuple:
    """
    Fetch 30-min ES data for the day BEFORE trading_date, 11:30 AM - 3:05 PM CT.
    Includes 11:30 for context before 12:00 and 3:00 for context after 2:30.
    Returns (DataFrame, actual_date_used).
    """
    try:
        es = yf.Ticker("ES=F")
        df = es.history(period="7d", interval="30m")
        if df.empty:
            return pd.DataFrame(), None
        df.index = df.index.tz_convert(CT)

        prior = trading_date - timedelta(days=1)
        while prior.weekday() >= 5:
            prior -= timedelta(days=1)

        for attempt in range(3):
            day_data = df[df.index.date == prior]
            if not day_data.empty:
                afternoon = day_data.between_time(dtime(11, 25), dtime(15, 5))
                if not afternoon.empty:
                    return afternoon[["Open", "High", "Low", "Close", "Volume"]], prior
            prior -= timedelta(days=1)
            while prior.weekday() >= 5:
                prior -= timedelta(days=1)

        return pd.DataFrame(), None
    except Exception:
        return pd.DataFrame(), None
