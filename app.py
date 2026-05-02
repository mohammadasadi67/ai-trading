import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("⚡ BTC RECOVERY SCALPER (OPTIMIZED HIGH FREQ)")

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
# SETTINGS
# ======================
capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.05) / 100 # کارمزد را دقیق وارد کنید
start_date = st.sidebar.date_input("Start Date", value=date(2024,1,1))

df = get_data("4h", 1000)
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS (بهینه شده برای دقت)
# ======================
df["MA25"] = df["Close"].rolling(25).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
df["DonHigh"] = df["High"].rolling(12).max().shift(1) # بازه را از 7 به 12 رساندم تا نویز کم شود

# RSI برای تشخیص قدرت روند
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain / loss)))

# ======================
# ENGINE
# ======================
df["Signal"] = "WAIT"
balance = 1.0
trades = wins = losses = 0
total_profit = total_loss = 0

in_position = False
entry_price = 0
sl = 0
highest = 0

for i in range(25, len(df)):
    close = df["Close"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]
    rsi = df["RSI"].iloc[i]
    don_high = df["DonHigh"].iloc[i]
    atr = df["ATR"].iloc[i]

    if not in_position:
        # ورود: قیمت بالای سقف قبلی + RSI در ناحیه صعودی (بالای 52)
        if close > don_high and rsi > 52 and rsi < 68:
            entry_price = close
            sl = entry_price - (atr * 1.5) # استاپ منطقی‌تر
            highest = entry_price
            in_position = True
            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"

    else:
        df.iloc[i, df.columns.get_loc("Signal")] = "HOLD"
        highest = max(highest, high)

        # تریلینگ استاپ هوشمند: وقتی سود به 2% رسید، استاپ را به سود 0.5% منتقل کن
        if highest > entry_price * 1.02:
            sl = max(sl, entry_price * 1.005)
        
        # خروج تهاجمی اگر RSI شروع به ریزش شدید کرد
        if low <= sl or rsi < 48:
            exit_price = sl if low <= sl else close
            raw = (exit_price - entry_price) / entry_price
            net = (1 + raw) * (1 - fee)**2 - 1
            
            balance *= (1 + net)
            trades += 1
            if net > 0: wins += 1; total_profit += net
            else: losses += 1; total_loss += abs(net)
            
            in_position = False

# ======================
# DISPLAY
# ======================
final_balance = capital * balance
winrate = (wins / trades * 100) if trades else 0

c1, c2, c3 = st.columns(3)
c1.metric("Trades", trades)
c2.metric("Winrate", f"{winrate:.2f}%")
c3.metric("Net Profit %", f"{(balance-1)*100:.2f}%")
st.metric("Final Balance", f"${final_balance:,.2f}")

st.dataframe(df.sort_index(ascending=False), use_container_width=True)
