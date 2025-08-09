from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionSnapshotsRequest
import os

# Initialize client with your API credentials
client = OptionHistoricalDataClient(
    api_key=os.getenv("ALPACA_API_KEY"),
    secret_key=os.getenv("ALPACA_API_SECRET")
)

# Example OCC code for AAPL Sep 20 '24 210C — change if expired
symbol = "AAPL240920C00210000"

try:
    req = OptionSnapshotsRequest(symbol_or_symbols=[symbol])
    snaps = client.get_option_snapshots(req)
    print(snaps)
except Exception as e:
    print("❌ No access or error:", e)