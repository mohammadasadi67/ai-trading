import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("SPOT SWING SYSTEM (BALANCED MODE)")

# ======================
# DATA
# ======================
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 800}
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

df = get_data()
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS
# ======================
ma = df["Close"].rolling(20).mean()
atr = (df["High"] - df["Low"]).rolling(14).mean()

# ======================
# VARIABLES
# ======================
balance = 1.0
trades = 0
wins = 0
losses = 0
total_profit = 0
total_loss = 0

max_hold = 20

df["Signal"] = "WAIT"
df["PnL"] = np.nan

# ======================
# STRATEGY
# ======================
for i in range(20, len(df)-max_hold):

    p1 = df.iloc[i-1]
    p2 = df.iloc[i-2]

    move = (p1["Close"] - p2["Close"]) / p2["Close"]

    # حداقل مومنتوم
    if move < 0.0008:
        continue

    # روند
    if df["Close"].iloc[i-1] < ma.iloc[i-1]:
        continue

    # ولتیلیتی
    vol = atr.iloc[i] / df["Close"].iloc[i]
    if vol < 0.002:
        continue

    entry = df["Open"].iloc[i]

    # 🔥 breakout نرم
    recent_high = df["High"].iloc[i-8:i].max()
    if entry < recent_high * 0.995:
        continue

    # SL و TP
    sl = min(p1["Low"], entry * 0.99)
    tp = entry * 1.015  # 1.5%

    # فقط ورود اگر حداقل 1% پتانسیل داشته باشه
    predicted = (tp - entry) / entry
    if predicted < 0.01:
        continue

    exit_price = entry
    highest = entry

    # ======================
    # HOLD LOOP
    # ======================
    for j in range(1, max_hold+1):

        high = df["High"].iloc[i+j]
        low = df["Low"].iloc[i+j]

        # ثبت سقف
        if high > highest:
            highest = high

        # trailing stop
        trail_sl = highest * 0.985

        if low <= sl:
            exit_price = sl
            break

        if low <= trail_sl:
            exit_price = trail_sl
            break

        exit_price = df["Close"].iloc[i+j]

    # ======================
    # RESULT
    # ======================
    raw = (exit_price - entry) / entry
    net = (1 + raw) * (1 - fee)**2 - 1

    trades += 1
    balance *= (1 + net)

    if net > 0:
        wins += 1
        total_profit += net
    else:
        losses += 1
        total_loss += abs(net)

    df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
    df.iloc[i, df.columns.get_loc("PnL")] = net * 100

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
