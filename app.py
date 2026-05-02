import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("TREND SYSTEM (EMA + ADX + ATR)")

# ======================
# DATA
# ======================
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 1000}
    data = requests.get(url, params=params).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close"]]
    df.columns = ["Time","Open","High","Low","Close"]
    df.set_index("Time", inplace=True)

    return df.astype(float)

df = get_data()

# ======================
# INDICATORS
# ======================
df["EMA50"] = df["Close"].ewm(span=50).mean()
df["EMA200"] = df["Close"].ewm(span=200).mean()

# ATR
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# ADX ساده
up = df["High"].diff()
down = -df["Low"].diff()

plus_dm = np.where((up > down) & (up > 0), up, 0)
minus_dm = np.where((down > up) & (down > 0), down, 0)

tr = np.maximum(df["High"] - df["Low"],
     np.maximum(abs(df["High"] - df["Close"].shift()),
                abs(df["Low"] - df["Close"].shift())))

atr = pd.Series(tr).rolling(14).mean()

plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr)
minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr)

dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
df["ADX"] = dx.rolling(14).mean()

# ======================
# BACKTEST
# ======================
balance = 1.0
trades = wins = losses = 0
in_position = False
entry = 0
sl = 0
highest = 0

df["Signal"] = "WAIT"
df["PnL"] = np.nan

for i in range(200, len(df)):

    close = df["Close"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]

    ema50 = df["EMA50"].iloc[i]
    ema200 = df["EMA200"].iloc[i]
    atr = df["ATR"].iloc[i]
    adx = df["ADX"].iloc[i]

    # ======================
    # ENTRY
    # ======================
    if not in_position:

        if close > ema50 > ema200 and adx > 20:

            entry = close
            sl = entry - atr * 1.5
            highest = entry

            in_position = True
            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"

    # ======================
    # HOLD
    # ======================
    else:

        df.iloc[i, df.columns.get_loc("Signal")] = "HOLD"

        if high > highest:
            highest = high

        # trailing
        if highest > entry * 1.02:
            sl = max(sl, highest - atr * 1.5)

        exit_price = None

        if low <= sl:
            exit_price = sl

        if exit_price is not None:

            pnl = (exit_price - entry) / entry

            balance *= (1 + pnl)
            trades += 1

            if pnl > 0:
                wins += 1
            else:
                losses += 1

            df.iloc[i, df.columns.get_loc("PnL")] = pnl * 100

            in_position = False

# ======================
# RESULTS
# ======================
winrate = wins / trades * 100 if trades else 0
profit = (balance - 1) * 100

st.metric("Trades", trades)
st.metric("Winrate", f"{winrate:.2f}%")
st.metric("Profit %", f"{profit:.2f}%")

st.dataframe(df.tail(200))
