import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

st.set_page_config(layout="wide")
st.title("🔥 SMART AI TRADING PANEL")

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
# FEAR & GREED
# ======================
def get_fear_greed():
    try:
        url = "https://api.alternative.me/fng/"
        data = requests.get(url).json()
        return int(data["data"][0]["value"])
    except:
        return 50

# ======================
# INDICATORS
# ======================
def add_indicators(df):
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    # ATR
    df["H-L"] = df["High"] - df["Low"]
    df["H-C"] = abs(df["High"] - df["Close"].shift())
    df["L-C"] = abs(df["Low"] - df["Close"].shift())
    df["TR"] = df[["H-L","H-C","L-C"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(14).mean()

    return df

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
# SETTINGS
# ======================
capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee %", 0.0, 0.5, 0.1) / 100
start_date = st.sidebar.date_input("Start", value=date(2024,1,1))

# ======================
# LOAD
# ======================
df = get_data()
df = df[df.index.date >= start_date].copy()
df = add_indicators(df)

fear = get_fear_greed()

# ======================
# STATUS
# ======================
df["Status"] = "CLOSED"
df.iloc[-1, df.columns.get_loc("Status")] = "LIVE"

# ======================
# STRATEGY
# ======================
df["Signal"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan
df["StopLoss"] = np.nan
df["Confidence"] = 0.0
df["PnL"] = 0.0

balance = 1.0
trades = 0

for i in range(200, len(df)):

    p1 = df.iloc[i-1]
    p2 = df.iloc[i-2]
    row = df.iloc[i]

    # ======================
    # SMART FILTERS
    # ======================

    # 1. Trend
    if row["Close"] < row["EMA200"]:
        continue

    # 2. Fear
    if fear > 75:
        continue

    # 3. Volatility
    if row["ATR"] < row["Close"] * 0.003:
        continue

    # 4. Momentum
    move = (p1["Close"] - p2["Close"]) / p2["Close"]
    if move < 0.004:
        continue

    # ======================
    # TRADE
    # ======================
    entry = row["Open"]
    sl = p1["Low"]
    tp = entry + (move * entry * 1.5)

    high = row["High"]
    low = row["Low"]

    exit_price = row["Close"]

    if low <= sl:
        exit_price = sl
    elif high >= tp:
        exit_price = tp

    raw = (exit_price - entry) / entry
    net = (1 + raw) * (1 - fee)**2 - 1

    if net <= 0:
        continue

    trades += 1
    balance *= (1 + net)

    df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
    df.iloc[i, df.columns.get_loc("Entry")] = entry
    df.iloc[i, df.columns.get_loc("Target")] = tp
    df.iloc[i, df.columns.get_loc("StopLoss")] = sl
    df.iloc[i, df.columns.get_loc("PnL")] = net * 100
    df.iloc[i, df.columns.get_loc("Confidence")] = min(0.95, 0.6 + move*10)

# ======================
# UI
# ======================
price = df["Close"].iloc[-1]

c1, c2, c3 = st.columns(3)
c1.metric("BTC", f"${price:,.2f}")
c2.metric("Fear & Greed", fear)
c3.metric("Next Candle", time_left())

final_balance = capital * balance

m1, m2, m3, m4 = st.columns(4)
m1.metric("Balance", f"${final_balance:,.2f}")
m2.metric("Profit", f"${final_balance-capital:,.2f}", f"{(balance-1)*100:.2f}%")
m3.metric("Trades", trades)
m4.metric("Avg Trade", f"{((balance**(1/max(trades,1)))-1)*100:.2f}%")

st.dataframe(
    df.sort_index(ascending=False),
    use_container_width=True,
    height=600
)

st.markdown(
    "<script>setTimeout(()=>window.location.reload(),20000)</script>",
    unsafe_allow_html=True
)
