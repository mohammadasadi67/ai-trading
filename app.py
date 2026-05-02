import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("SPOT SWING SYSTEM (POSITION HOLD MODE)")

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
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS
# ======================
df["MA20"] = df["Close"].rolling(20).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# ======================
# VARIABLES
# ======================
balance = 1.0
trades = 0
wins = 0
losses = 0
total_profit = 0
total_loss = 0

in_position = False
entry_price = 0
sl = 0
highest = 0

df["Signal"] = "WAIT"
df["PnL"] = np.nan

# ======================
# LOOP
# ======================
for i in range(30, len(df)):

    close = df["Close"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]
    ma = df["MA20"].iloc[i]
    atr = df["ATR"].iloc[i]

    # ======================
    # ENTRY
    # ======================
    if not in_position:

        # breakout ساده + روند
        recent_high = df["High"].iloc[i-8:i].max()

        if close > ma and close > recent_high:

            entry_price = close
            sl = entry_price - atr * 0.7
            highest = entry_price

            in_position = True
            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"

    # ======================
    # HOLD
    # ======================
    else:

        # آپدیت سقف
        if high > highest:
            highest = high

        # trailing فقط وقتی سود داریم
        if highest > entry_price * 1.03:
            trail = highest * 0.97
        else:
            trail = sl

        trend_ok = close > ma

        exit_price = None

        # شرایط خروج
        if not trend_ok:
            exit_price = close

        elif low <= sl:
            exit_price = sl

        elif low <= trail:
            exit_price = trail

        # ======================
        # EXIT → فقط اینجا PnL حساب میشه
        # ======================
        if exit_price is not None:

            raw = (exit_price - entry_price) / entry_price
            net = (1 + raw) * (1 - fee)**2 - 1

            trades += 1
            balance *= (1 + net)

            if net > 0:
                wins += 1
                total_profit += net
            else:
                losses += 1
                total_loss += abs(net)

            df.iloc[i, df.columns.get_loc("Signal")] = "SELL"
            df.iloc[i, df.columns.get_loc("PnL")] = net * 100

            in_position = False

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
