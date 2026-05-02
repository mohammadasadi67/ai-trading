import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("SPOT POSITION SYSTEM (PRO ENTRY + HOLD)")

# ======================
# DATA
# ======================
def get_data(interval="4h", limit=1000):
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

df = get_data("4h", 1000)
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS
# ======================
df["MA50"] = df["Close"].rolling(50).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# Donchian (breakout واقعی)
df["DonHigh"] = df["High"].rolling(20).max().shift(1)

# ======================
# INIT
# ======================
df["Signal"] = "WAIT"
df["PnL"] = np.nan

balance = 1.0
trades = wins = losses = 0
total_profit = total_loss = 0

in_position = False
entry_price = 0
sl = 0
highest = 0
last_trade_i = -100

# ======================
# LOOP
# ======================
for i in range(60, len(df)):

    close = df["Close"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]

    ma50 = df["MA50"].iloc[i]
    atr = df["ATR"].iloc[i]
    don_high = df["DonHigh"].iloc[i]

    # شیب MA50
    ma_slope = df["MA50"].iloc[i] - df["MA50"].iloc[i-5]

    # ATR%
    atr_pct = atr / close

    # ======================
    # ENTRY (فقط ستاپ قوی)
    # ======================
    if not in_position:

        # کول‌دان برای جلوگیری از اورترید
        if i - last_trade_i < 10:
            continue

        cond_trend = close > ma50 and ma_slope > 0
        cond_breakout = close > don_high
        cond_vol = atr_pct > 0.002  # بازار فعال

        # فاصله تا سقف 50 کندلی (نخریدن خیلی نزدیک سقف)
        recent_res = df["High"].iloc[i-50:i].max()
        dist_res = (recent_res - close) / close

        if cond_trend and cond_breakout and cond_vol and dist_res > 0.01:

            entry_price = close

            # SL کوچک
            sl = entry_price - atr * 0.5

            highest = entry_price
            in_position = True
            last_trade_i = i

            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"

    # ======================
    # HOLD
    # ======================
    else:

        df.iloc[i, df.columns.get_loc("Signal")] = "HOLD"

        if high > highest:
            highest = high

        # trailing بعد از 2% سود فعال
        if highest > entry_price * 1.02:
            sl = max(sl, highest * 0.97)

        exit_price = None

        # فقط SL
        if low <= sl:
            exit_price = sl

        # ======================
        # EXIT → PnL
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
