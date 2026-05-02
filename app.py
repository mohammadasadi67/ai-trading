import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")
st.title("Trading System (Streamlit Version)")

# ======================
# DATA
# ======================
@st.cache_data
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 300}

    data = requests.get(url, params=params, timeout=10).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close"]]
    df.columns = ["Time","Open","High","Low","Close"]
    df.set_index("Time", inplace=True)

    return df.astype(float)

# ======================
# LOAD
# ======================
df = get_data()

if df.empty:
    st.error("Data not loaded")
    st.stop()

# ======================
# INDICATORS
# ======================
df["EMA20"] = df["Close"].ewm(span=20).mean()
df["EMA50"] = df["Close"].ewm(span=50).mean()

# ======================
# BACKTEST
# ======================
balance = 1.0
trades = 0
wins = 0
losses = 0

in_pos = False
entry = 0

df["Signal"] = ""
df["PnL"] = np.nan

for i in range(50, len(df)):

    close = df["Close"].iloc[i]

    if not in_pos:
        if close > df["EMA20"].iloc[i] > df["EMA50"].iloc[i]:
            entry = close
            in_pos = True
            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"

    else:
        df.iloc[i, df.columns.get_loc("Signal")] = "HOLD"

        if close < df["EMA20"].iloc[i]:

            pnl = (close - entry) / entry
            balance *= (1 + pnl)
            trades += 1

            if pnl > 0:
                wins += 1
            else:
                losses += 1

            df.iloc[i, df.columns.get_loc("PnL")] = pnl * 100
            in_pos = False

# ======================
# METRICS
# ======================
winrate = (wins / trades * 100) if trades else 0
profit = (balance - 1) * 100

c1, c2, c3 = st.columns(3)
c1.metric("Trades", trades)
c2.metric("Winrate", f"{winrate:.2f}%")
c3.metric("Profit %", f"{profit:.2f}%")

st.divider()
st.dataframe(df.tail(100), use_container_width=True)
