import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("Smart Trading System")

# ======================
# SIDEBAR (تنظیمات)
# ======================
capital = st.sidebar.number_input("Capital ($)", value=1000.0)
fee = st.sidebar.slider("Exchange Fee (%)", 0.0, 0.5, 0.1) / 100
start_date = st.sidebar.date_input("Start Date", value=date(2024,1,1))

# ======================
# DATA
# ======================
@st.cache_data
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 500}
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

df = get_data()

# فیلتر تاریخ
df = df[df.index.date >= start_date]

# ======================
# INDICATORS
# ======================
df["EMA20"] = df["Close"].ewm(span=20).mean()
df["EMA50"] = df["Close"].ewm(span=50).mean()

# ATR
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# ======================
# BACKTEST (بهبود یافته)
# ======================
balance = 1.0
trades = wins = losses = 0
total_profit = 0
total_loss = 0

in_pos = False
entry = 0
sl = 0
highest = 0

df["Signal"] = ""
df["PnL"] = np.nan

for i in range(50, len(df)):

    close = df["Close"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]

    ema20 = df["EMA20"].iloc[i]
    ema50 = df["EMA50"].iloc[i]
    atr = df["ATR"].iloc[i]

    # ======================
    # ENTRY (بهبود یافته)
    # ======================
    if not in_pos:
        breakout = close > df["High"].iloc[i-10:i].max()

        if close > ema20 > ema50 and breakout:
            entry = close
            sl = entry - atr * 0.8
            highest = entry
            in_pos = True
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
            sl = max(sl, highest * 0.97)

        exit_price = None

        if low <= sl:
            exit_price = sl

        if exit_price is not None:

            raw = (exit_price - entry) / entry
            net = (1 + raw) * (1 - fee)**2 - 1

            balance *= (1 + net)
            trades += 1

            if net > 0:
                wins += 1
                total_profit += net
            else:
                losses += 1
                total_loss += abs(net)

            df.iloc[i, df.columns.get_loc("PnL")] = net * 100
            in_pos = False

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
c4.metric("Wins / Losses", f"{wins}/{losses}")
c5.metric("Total Profit %", f"{total_profit*100:.2f}%")
c6.metric("Total Loss %", f"{total_loss*100:.2f}%")

st.metric("Final Balance", f"${final_balance:,.2f}")

st.divider()
st.dataframe(df.tail(150), use_container_width=True)
