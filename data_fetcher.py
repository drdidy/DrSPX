"""
SPX Prophet — Data Fetcher Module
Handles all market data retrieval via yfinance with smart caching.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime
import pytz
from functools import lru_cache
import streamlit as st

CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("US/Eastern")


@st.cache_data(ttl=30)
def fetch_es_1min(days_back: int = 2) -> pd.DataFrame:
    """Fetch ES futures 1-minute bars for 8/50 EMA cross detection."""
    try:
        es = yf.Ticker("ES=F")
        df = es.history(period=f"{days_back}d", interval="1m")
        if df.empty:
            return pd.DataFrame()
        df.index = df.index.tz_convert(CT)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        # Calculate EMAs
        df["EMA_8"] = df["Close"].ewm(span=8, adjust=False).mean()
        df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
        df["Spread"] = df["EMA_8"] - df["EMA_50"]
        return df
    except Exception as e:
        st.error(f"Error fetching ES 1-min data: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def fetch_es_30min(days_back: int = 5) -> pd.DataFrame:
    """Fetch ES futures 30-minute bars for channel construction."""
    try:
        es = yf.Ticker("ES=F")
        df = es.history(period=f"{days_back}d", interval="30m")
        if df.empty:
            return pd.DataFrame()
        df.index = df.index.tz_convert(CT)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        return df
    except Exception as e:
        st.error(f"Error fetching ES 30-min data: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=30)
def fetch_spx_price() -> float:
    """Fetch current SPX price."""
    try:
        spx = yf.Ticker("^GSPC")
        data = spx.history(period="1d", interval="1m")
        if data.empty:
            # Try daily if intraday not available
            data = spx.history(period="2d")
            if data.empty:
                return 0.0
            return float(data["Close"].iloc[-1])
        return float(data["Close"].iloc[-1])
    except Exception as e:
        st.error(f"Error fetching SPX price: {e}")
        return 0.0


@st.cache_data(ttl=30)
def fetch_es_price() -> float:
    """Fetch current ES futures price."""
    try:
        es = yf.Ticker("ES=F")
        data = es.history(period="1d", interval="1m")
        if data.empty:
            data = es.history(period="2d")
            if data.empty:
                return 0.0
            return float(data["Close"].iloc[-1])
        return float(data["Close"].iloc[-1])
    except Exception as e:
        st.error(f"Error fetching ES price: {e}")
        return 0.0


def get_es_spx_offset() -> float:
    """Calculate live ES - SPX offset."""
    es = fetch_es_price()
    spx = fetch_spx_price()
    if es > 0 and spx > 0:
        return es - spx
    return 0.0


def fetch_prior_day_afternoon(trading_date: datetime = None) -> pd.DataFrame:
    """
    Fetch 30-min bars for prior day's 12 PM - 3 PM CT window.
    This is the channel construction window.
    """
    df = fetch_es_30min(days_back=7)
    if df.empty:
        return pd.DataFrame()

    if trading_date is None:
        trading_date = datetime.now(CT).date()

    # Find prior trading day
    check_date = trading_date - timedelta(days=1)
    attempts = 0
    while attempts < 5:
        day_data = df[df.index.date == check_date]
        if not day_data.empty:
            break
        check_date -= timedelta(days=1)
        attempts += 1

    if day_data.empty:
        return pd.DataFrame()

    # Filter 12 PM - 3 PM CT (the candle at 2:30 PM covers 2:30-3:00)
    noon = dtime(12, 0)
    three_pm = dtime(15, 0)
    afternoon = day_data.between_time(noon, three_pm)

    return afternoon


def fetch_1min_for_afternoon(trading_date: datetime = None) -> pd.DataFrame:
    """
    Fetch 1-min bars for prior day 12 PM - 3 PM CT.
    Used for line chart bounce/rejection detection.
    """
    try:
        es = yf.Ticker("ES=F")
        df = es.history(period="5d", interval="1m")
        if df.empty:
            return pd.DataFrame()
        df.index = df.index.tz_convert(CT)

        if trading_date is None:
            trading_date = datetime.now(CT).date()

        # Find prior trading day
        check_date = trading_date - timedelta(days=1)
        attempts = 0
        while attempts < 5:
            day_data = df[df.index.date == check_date]
            if not day_data.empty:
                break
            check_date -= timedelta(days=1)
            attempts += 1

        if day_data.empty:
            return pd.DataFrame()

        noon = dtime(12, 0)
        three_pm = dtime(15, 0)
        afternoon = day_data.between_time(noon, three_pm)

        return afternoon[["Open", "High", "Low", "Close", "Volume"]]
    except Exception as e:
        st.error(f"Error fetching 1-min afternoon data: {e}")
        return pd.DataFrame()
