import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC ALPHA TRADER")
st.title("🚀 BTC PRO-ENGINE (V8.0 - DOUBLE CONFIRMATION)")

# ======================
# DATA FETCHING
# ======================
@st.cache_data(ttl=600)
def get_data(limit=1500):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": limit}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        df = pd.DataFrame(data, columns=["time","open","high","low","close","volume","ct","qav","trades","tb","tq","ig"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except:
        return pd.DataFrame()

# ======================
# SETTINGS
# ======================
with st.sidebar:
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.04) / 100
    start_date = st.date_input("Start Date", value=date(2023, 1, 1))

df = get_data()
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS
# ======================
df["MA20"] = df["Close"].rolling(20).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
df["DonHigh"] = df["High"].rolling(12).max().shift(1)

delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE (YOUR IMPROVED LOGIC)
# ======================
df["Signal"] = "WAIT"
df["Confidence"] = 0
df["Entry"] = 0.0
df["SL"] = 0.0
df["Exit"] = 0.0
df["PnL_%"] = 0.0

balance = 1.0
trades = wins = losses = 0
in_pos = False
entry = sl = highest = 0

for i in range(50, len(df)):
    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]
    atr = df["ATR"].iloc[i]
    rsi = df["RSI"].iloc[i]
    ma20 = df["MA20"].iloc[i]
    don_h = df["DonHigh"].iloc[i]

    if not in_pos:
        if c > don_h and 52 < rsi < 68:
            entry = c
            sl = entry - (atr * 1.2)
            highest = entry
            in_pos = True
            conf = int(np.clip((rsi-50)*6 + 40, 0, 100))
            
            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
            df.iloc[i, df.columns.get_loc("Entry")] = entry
            df.iloc[i, df.columns.get_loc("SL")] = sl
            df.iloc[i, df.columns.get_loc("Confidence")] = conf

    else:
        df.iloc[i, df.columns.get_loc("Signal")] = "HOLD"
        highest = max(highest, h)

        # ریسک‌فری و تریلینگ
        if highest > entry * 1.015:
            sl = max(sl, entry + (entry * 0.001))
        if highest > entry * 1.04: # تریلینگ کمی دورتر برای اجازه رشد بیشتر
            sl = max(sl, highest * 0.96)

        exit_price = 0

        # 🔥 انجین اصلاح شده توسط شما
        if l <= sl:
            exit_price = sl
        elif c < ma20 and rsi < 45: # تاییدیه دوگانه برای خروج زودهنگام
            exit_price = c

        if exit_price > 0:
            pnl = ((exit_price - entry) / entry) - (fee * 2)
            balance *= (1 + pnl)
            trades += 1
            if pnl > 0: wins += 1
            else: losses += 1
            df.iloc[i, df.columns.get_loc("Exit")] = exit_price
            df.iloc[i, df.columns.get_loc("PnL_%")] = pnl * 100
            in_pos = False

# ======================
# DASHBOARD
# ======================
winrate = (wins / trades * 100) if trades else 0
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Trades", trades)
c2.metric("Winrate", f"{winrate:.1f}%")
c3.metric("Net Profit", f"{(balance-1)*100:.2f}%")
c4.metric("Final Balance", f"${capital * balance:,.2f}")

st.divider()
report = df[(df["Signal"] == "BUY") | (df["PnL_%"] != 0)].copy()
st.dataframe(report[["Signal", "Confidence", "Entry", "SL", "Exit", "PnL_%"]].sort_index(ascending=False), use_container_width=True)
