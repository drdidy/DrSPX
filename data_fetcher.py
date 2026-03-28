"""
SPX Prophet — Data Fetcher Module
Tastytrade primary → yfinance fallback → manual override
"""

import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz
import streamlit as st

CT = pytz.timezone("America/Chicago")


# ═══════════════════════════════════════════════════════════════════════════════
# TASTYTRADE AUTH
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800)
def _get_tt_token() -> dict:
    """Authenticate with Tastytrade. Cached for 30 min."""
    try:
        tt = st.secrets.get("tastytrade", {})
        if not tt:
            return {'ok': False, 'error': "No [tastytrade] in secrets"}

        username = tt.get("username", "")
        password = tt.get("password", "")
        if username and password:
            resp = requests.post(
                "https://api.tastytrade.com/sessions",
                json={"login": username, "password": password, "remember-me": True},
                timeout=10
            )
            if resp.status_code == 201:
                token = resp.json().get('data', {}).get('session-token', '')
                if token:
                    return {'ok': True, 'token': token}
        return {'ok': False, 'error': "Auth failed"}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


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
                afternoon = day_data.between_time(dtime(12, 0), dtime(15, 5))
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
    Fetch 30-min ES data for the day BEFORE trading_date, 12-3 PM CT.
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
                afternoon = day_data.between_time(dtime(12, 0), dtime(15, 5))
                if not afternoon.empty:
                    return afternoon[["Open", "High", "Low", "Close", "Volume"]], prior
            prior -= timedelta(days=1)
            while prior.weekday() >= 5:
                prior -= timedelta(days=1)

        return pd.DataFrame(), None
    except Exception:
        return pd.DataFrame(), None
