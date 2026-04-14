import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

st.set_page_config(layout="wide", page_title="SMART TRADING AI")

# ======================
# DATA
# ======================
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 300}
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
# TIME
# ======================
def time_left():
    now = datetime.utcnow()
    next_4h = (now.hour // 4 + 1) * 4
    if next_4h >= 24:
        target = datetime(now.year, now.month, now.day) + timedelta(days=1)
    else:
        target = datetime(now.year, now.month, now.day, next_4h)
    return str((target - now)).split(".")[0]

# ======================
# UI
# ======================
st.title("🔥 SMART MONEY PANEL")

initial_capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee %", 0.0, 0.5, 0.1) / 100
start_date = st.sidebar.date_input("Start", value=date(2024,1,1))

df = get_data()
df = df[df.index.date >= start_date].copy()

# ======================
# STRATEGY
# ======================
df["Signal"] = "WAIT"
df["PnL"] = 0.0

balance = 1.0
trades = 0

for i in range(2, len(df)):

    p1 = df.iloc[i-1]
    p2 = df.iloc[i-2]

    move = (p1["Close"] - p2["Close"]) / p2["Close"]

    # ✅ فقط حرکت قوی
    if move < 0.004:   # 0.4%
        continue

    entry = df["Open"].iloc[i]

    # TP و SL واقعی‌تر
    tp = entry + (move * entry * 1.5)
    sl = p1["Low"]

    # بررسی داخل کندل
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]

    exit_price = df["Close"].iloc[i]

    if low <= sl:
        exit_price = sl
    elif high >= tp:
        exit_price = tp

    raw = (exit_price - entry) / entry
    net = (1 + raw) * (1 - fee)**2 - 1

    # ✅ فقط اگر بعد از کارمزد سودده بود
    if net <= 0:
        continue

    trades += 1
    balance *= (1 + net)

    df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
    df.iloc[i, df.columns.get_loc("PnL")] = net * 100

# ======================
# RESULT
# ======================
final_balance = initial_capital * balance

c1, c2 = st.columns(2)

c1.metric("Balance", f"${final_balance:,.2f}")
c2.metric("Trades", trades)

st.write(f"⏳ Next Candle: {time_left()}")

st.dataframe(df.sort_index(ascending=False), use_container_width=True)

# AUTO REFRESH
st.markdown(
    "<script>setTimeout(()=>window.location.reload(),20000)</script>",
    unsafe_allow_html=True
)
