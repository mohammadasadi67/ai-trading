import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("SPOT RL-LIKE SWING SYSTEM")

# ======================
# DATA
# ======================
def get_data(interval="4h", limit=800):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": interval, "limit": limit}
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

df = get_data("4h", 800)
df_daily = get_data("1d", 400)

# ======================
# INDICATORS
# ======================
df["MA20"] = df["Close"].rolling(20).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

df_daily["MA20"] = df_daily["Close"].rolling(20).mean()

# ======================
# SUPPORT / RESISTANCE (Pivot)
# ======================
def pivots(df, window=5):
    highs = df["High"]
    lows = df["Low"]

    piv_high = highs[(highs.shift(window) < highs) & (highs.shift(-window) < highs)]
    piv_low = lows[(lows.shift(window) > lows) & (lows.shift(-window) > lows)]

    return piv_low.dropna(), piv_high.dropna()

support_levels, resistance_levels = pivots(df)

# ======================
# RL-LIKE SCORE
# ======================
def compute_score(i):
    score = 0

    # 1. Trend 4H
    if df["Close"].iloc[i] > df["MA20"].iloc[i]:
        score += 1

    # 2. Trend Daily
    d_close = df_daily["Close"].iloc[-1]
    d_ma = df_daily["MA20"].iloc[-1]
    if d_close > d_ma:
        score += 1

    # 3. Breakout
    recent_high = df["High"].iloc[i-8:i].max()
    if df["Close"].iloc[i] > recent_high:
        score += 1

    # 4. Distance from support
    nearest_support = support_levels.iloc[-1] if len(support_levels) else df["Low"].iloc[i]
    dist = (df["Close"].iloc[i] - nearest_support) / df["Close"].iloc[i]
    if dist < 0.02:
        score += 1

    return score

# ======================
# BACKTEST
# ======================
balance = 1.0
trades = 0
wins = 0
losses = 0

df["Signal"] = ""
df["PnL"] = np.nan
df["Confidence"] = 0.0

for i in range(30, len(df)-1):

    score = compute_score(i)

    # 🔥 RL-like decision
    if score < 3:
        continue

    entry = df["Close"].iloc[i]

    # dynamic SL / TP
    atr = df["ATR"].iloc[i]
    sl = entry - atr
    tp = entry + atr * 3

    highest = entry
    exit_price = entry

    # 🔓 HOLD آزاد
    for j in range(i+1, len(df)):

        high = df["High"].iloc[j]
        low = df["Low"].iloc[j]

        if high > highest:
            highest = high

        trail = highest - atr

        if low <= sl:
            exit_price = sl
            break

        if low <= trail:
            exit_price = trail
            break

        if high >= tp:
            exit_price = tp
            break

        exit_price = df["Close"].iloc[j]

    # RESULT
    pnl = (exit_price - entry) / entry

    balance *= (1 + pnl)
    trades += 1

    if pnl > 0:
        wins += 1
    else:
        losses += 1

    df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
    df.iloc[i, df.columns.get_loc("PnL")] = pnl * 100

    # confidence
    conf = score / 4
    df.iloc[i, df.columns.get_loc("Confidence")] = conf

# ======================
# METRICS
# ======================
winrate = wins / trades * 100 if trades else 0
profit = (balance - 1) * 100

st.metric("Trades", trades)
st.metric("Winrate", f"{winrate:.2f}%")
st.metric("Profit %", f"{profit:.2f}%")

st.dataframe(df.tail(200))
