import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("SPOT SWING SYSTEM (HOLD SMART MODE)")

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

# ======================
# INPUT
# ======================
capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.1) / 100
start_date = st.sidebar.date_input("Start", value=date(2024,1,1))

df = get_data("4h", 800)
df_daily = get_data("1d", 400)
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS
# ======================
df["MA20"] = df["Close"].rolling(20).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
df_daily["MA20"] = df_daily["Close"].rolling(20).mean()

# ======================
# SUPPORT / RESISTANCE
# ======================
def pivots(df, w=5):
    highs = df["High"]
    lows = df["Low"]
    piv_high = highs[(highs.shift(w) < highs) & (highs.shift(-w) < highs)]
    piv_low = lows[(lows.shift(w) > lows) & (lows.shift(-w) > lows)]
    return piv_low.dropna(), piv_high.dropna()

supports, resistances = pivots(df)

# ======================
# VARIABLES
# ======================
balance = 1.0
trades = 0
wins = 0
losses = 0
total_profit = 0
total_loss = 0
last_trade_index = -50

df["Signal"] = "WAIT"
df["PnL"] = np.nan
df["Confidence"] = 0.0

# ======================
# SCORE (RL-like)
# ======================
def score(i):
    s = 0
    if df["Close"].iloc[i] > df["MA20"].iloc[i]:
        s += 1
    if df_daily["Close"].iloc[-1] > df_daily["MA20"].iloc[-1]:
        s += 1
    if df["Close"].iloc[i] > df["High"].iloc[i-8:i].max():
        s += 1
    if len(supports) > 0:
        dist = (df["Close"].iloc[i] - supports.iloc[-1]) / df["Close"].iloc[i]
        if dist < 0.02:
            s += 1
    return s

# ======================
# STRATEGY
# ======================
for i in range(30, len(df)-1):

    if i - last_trade_index < 10:
        continue

    sc = score(i)
    if sc < 4:
        continue

    entry = df["Close"].iloc[i]
    atr = df["ATR"].iloc[i]

    # جلوگیری از خرید نزدیک مقاومت
    if len(resistances) > 0:
        dist_r = (resistances.iloc[-1] - entry) / entry
        if dist_r < 0.02:
            continue

    sl = entry - atr * 0.6
    tp = entry + atr * 3   # دور → برای رشد

    highest = entry
    exit_price = entry

    # 🔥 HOLD واقعی (تا هرجا لازم شد)
    for j in range(i+1, len(df)):

        high = df["High"].iloc[j]
        low = df["Low"].iloc[j]

        if high > highest:
            highest = high

        # trailing پله‌ای
        if highest > entry * 1.02:
            trail = highest - atr * 0.8
        elif highest > entry * 1.01:
            trail = highest - atr * 1.0
        else:
            trail = sl

        # خروج‌ها
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

    pnl = (exit_price - entry) / entry
    net = (1 + pnl) * (1 - fee)**2 - 1

    trades += 1
    balance *= (1 + net)
    last_trade_index = i

    if net > 0:
        wins += 1
        total_profit += net
    else:
        losses += 1
        total_loss += abs(net)

    df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
    df.iloc[i, df.columns.get_loc("PnL")] = net * 100

    conf = (sc / 4) * (atr / entry * 100)
    df.iloc[i, df.columns.get_loc("Confidence")] = min(conf, 1)

# ======================
# METRICS
# ======================
final_balance = capital * balance
winrate = (wins / trades * 100) if trades else 0
net_profit = (balance - 1) * 100

c1, c2, c3 = st.columns(3)
c1.metric("Trades", trades)
c2.metric("Winrate", f"{winrate:.2f}%")
c3.metric("Net Profit %", f"{net_profit:.2f}%")

c4, c5, c6 = st.columns(3)
c4.metric("Wins / Losses", f"{wins} / {losses}")
c5.metric("Total Profit %", f"{total_profit*100:.2f}%")
c6.metric("Total Loss %", f"{total_loss*100:.2f}%")

st.metric("Balance", f"${final_balance:,.2f}")

st.divider()
st.dataframe(df.sort_index(ascending=False), use_container_width=True, height=600)
