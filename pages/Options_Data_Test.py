import datetime as dt
import streamlit as st

# alpaca-py (make sure it's in requirements.txt)
from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionContractsRequest, OptionSnapshotsRequest

st.title("Alpaca Options Data Test (AAPL)")

# 1) Read secrets (supports either flat or nested style)
api_key = st.secrets.get("ALPACA_API_KEY") or st.secrets.get("alpaca", {}).get("api_key")
api_secret = st.secrets.get("ALPACA_API_SECRET") or st.secrets.get("alpaca", {}).get("api_secret")

if not api_key or not api_secret:
    st.error("Missing ALPACA_API_KEY / ALPACA_API_SECRET in Streamlit secrets.")
    st.stop()

client = OptionHistoricalDataClient(api_key=api_key, secret_key=api_secret)

# 2) Choose the nearest Friday expiry (if today is Fri, take next Fri)
today = dt.date.today()
days_ahead = (4 - today.weekday()) % 7
expiry = today + dt.timedelta(days=days_ahead or 7)

st.write(f"Testing AAPL weekly options for expiry: **{expiry}**")

# 3) Try to fetch contracts, then a snapshot for a near-ATM call
try:
    resp = client.get_option_contracts(
        OptionContractsRequest(underlying_symbol="AAPL", expiration_date=expiry)
    )
    contracts = resp.option_contracts or []
    if not contracts:
        st.error("No contracts returned (could be entitlement issue or no contracts for that date).")
        st.stop()

    # near-the-money CALL
    calls = [c for c in contracts if getattr(c, "type", "").lower() == "call"]
    if not calls:
        st.error("Contracts returned, but no CALLs found.")
        st.stop()

    # Prefer one closest to underlying price if available
    def underlying_or_zero(c): 
        try:
            return float(c.underlying_price or 0.0)
        except Exception:
            return 0.0

    u0 = underlying_or_zero(calls[0]) or 200.0  # fallback
    calls.sort(key=lambda c: abs(float(c.strike_price) - u0))
    symbol = calls[0].symbol
    st.write("Selected OCC symbol:", f"**{symbol}**")

    snaps = client.get_option_snapshots(OptionSnapshotsRequest(symbol_or_symbols=[symbol]))
    snap = snaps.get(symbol)

    if snap:
        st.success("✅ Options snapshot OK — you have options data access.")
        # Show the most useful bits if present:
        st.subheader("Latest Quote")
        st.json(getattr(snap, "latest_quote", None), expanded=False)

        st.subheader("Greeks")
        st.json(getattr(snap, "greeks", None), expanded=False)

        st.caption("If you see quote/greeks above, we can integrate live options into your Apple page.")
    else:
        st.error("❌ Snapshot returned empty. Likely no options entitlement.")
except Exception as e:
    st.error(f"❌ Error: {e}")
    st.caption("If this says 'permission/entitlement', your Alpaca account doesn’t have options data yet.")