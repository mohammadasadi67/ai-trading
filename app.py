import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

st.set_page_config(layout="wide")
st.title("🚀 TRUE LIVE SIGNAL (REAL TRADER MODE)")

# ======================
# INPUT
# ======================
start = st.date_input("Start Date")
end   = st.date_input("End Date")
capital = st.number_input("Capital", value=100)

# ======================
# GET 4H HISTORY
# ======================
def get_4h(limit=200):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": limit}
    data = requests.get(url, params=params).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close"]]
    df.columns = ["Time","Open","High","Low","Close"]
    df.set_index("Time", inplace=True)
    df = df.astype(float)

    return df

df = get_4h()

# ======================
# GET LIVE PRICE (1m)
# ======================
live = requests.get(
    "https://data-api.binance.vision/api/v3/klines",
    params={"symbol": "BTCUSDT", "interval": "1m", "limit": 1}
).json()

live_price = float(live[0][4])  # Close 1m

# ======================
# BUILD NEW CANDLE (REAL)
# ======================
last_close = df["Close"].iloc[-1]
last_time  = df.index[-1]

new_time = last_time + pd.Timedelta(hours=4)

# 🔥 شروع کندل = قیمت لایو
open_ = live_price
high_ = live_price
low_  = live_price
close_ = live_price

new_row = pd.DataFrame({
    "Open":[open_],
    "High":[high_],
    "Low":[low_],
    "Close":[close_]
}, index=[new_time])

df = pd.concat([df, new_row])
df = df.sort_index()

# ======================
# SIGNAL (همون لحظه)
# ======================
df["Decision"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan

for i in range(2, len(df)):

    prev1 = df.iloc[i-1]
    prev2 = df.iloc[i-2]

    trend = prev1["Close"] > prev2["Close"]

    if trend:

        entry = df["Open"].iloc[i]
        move = prev1["Close"] - prev2["Close"]
        target = entry + move

        df.iloc[i, df.columns.get_loc("Decision")] = "TRADE"
        df.iloc[i, df.columns.get_loc("Entry")] = entry
        df.iloc[i, df.columns.get_loc("Target")] = target

# ======================
# FILTER
# ======================
df.index.name = "Time"

df_view = df[(df.index >= pd.Timestamp(start)) &
             (df.index <= pd.Timestamp(end)+pd.Timedelta(days=1))]

# ======================
# TABLE
# ======================
table = df_view.reset_index()[[
    "Time","Open","High","Low","Close",
    "Decision","Entry","Target"
]].copy()

table["Execute"] = False

st.data_editor(table, use_container_width=True)

# ======================
# RESULT
# ======================
balance = capital

for i in range(len(table)):
    if table.iloc[i]["Execute"]:

        entry = table.iloc[i]["Entry"]
        target = table.iloc[i]["Target"]

        if pd.notna(entry) and pd.notna(target):
            pnl = (target - entry) / entry
            balance *= (1 + pnl)

st.metric("Final Balance", f"${balance:.2f}")
