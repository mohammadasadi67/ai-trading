import requests
import pandas as pd

print("START...")

url = "https://data-api.binance.vision/api/v3/klines"
params = {
    "symbol": "BTCUSDT",
    "interval": "4h",
    "limit": 200
}

data = requests.get(url, params=params, timeout=10).json()

print("DATA RECEIVED:", len(data))

df = pd.DataFrame(data)
print("DF OK")

print("DONE")
