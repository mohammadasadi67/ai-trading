import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")
st.title("🚀 FINAL LIVE (MATCH TRADINGVIEW)")

# ======================
# INPUT
# ======================
col1, col2 = st.columns(2)

with col1:
    start = st.date_input("Start Date")
    end   = st.date_input("End Date")

with col2:
    capital = st.number_input("Capital ($)", value=1000)

# ======================
# HISTORICAL
# ======================
def get_hist(start, end):
    url = "https://data-api.binance.vision/api/v3/klines"

    start_ms = int(pd.Timestamp(start).timestamp()*1000)
    end_ms   = int((pd.Timestamp(end)+pd.Timedelta(days=1)).timestamp()*1000)

    all_data = []

    while True:
        params = {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000
        }

        data = requests.get(url, params=params).json()

        if not data:
            break

        all_data.extend(data)

        if len(data) < 1000:
            break

        start_ms = data[-1][0] + 1

    df = pd.DataFrame(all_data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close"]]
    df.columns = ["Time","Open","High","Low","Close"]
    df.set_index("Time", inplace=True)
    df = df.astype(float)

    return df

# buffer برای سیگنال
df = get_hist(pd.Timestamp(start)-pd.Timedelta(days=2), end)

# ======================
# LIVE 4H (REAL)
# ======================
live = requests.get(
    "https://data-api.binance.vision/api/v3/klines",
    params={"symbol": "BTCUSDT", "interval": "4h", "limit": 2}
).json()

live_df = pd.DataFrame(live, columns=[
    "time","open","high","low","close","volume",
    "close_time","qav","trades","tbbav","tbqav","ignore"
])

live_df["time"] = pd.to_datetime(live_df["time"], unit="ms")
live_df = live_df[["time","open","high","low","close"]]
live_df.columns = ["Time","Open","High","Low","Close"]
live_df.set_index("Time", inplace=True)
live_df = live_df.astype(float)

# 🔥 این مهمه:
df = df.iloc[:-1]          # حذف آخرین قدیمی
df = pd.concat([df, live_df])  # اضافه کردن واقعی

# ======================
# SIGNAL
# ======================
df["Decision"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan
df["PnL %"] = np.nan

for i in range(2, len(df)):

    prev1 = df.iloc[i-1]
    prev2 = df.iloc[i-2]

    if prev1["Close"] > prev2["Close"]:

        entry = df["Open"].iloc[i]
        move = prev1["Close"] - prev2["Close"]
        target = entry + move

        high = df["High"].iloc[i]
        close = df["Close"].iloc[i]

        exit_price = target if high >= target else close
        pnl = (exit_price - entry) / entry * 100

        df.iloc[i, df.columns.get_loc("Decision")] = "TRADE"
        df.iloc[i, df.columns.get_loc("Entry")] = entry
        df.iloc[i, df.columns.get_loc("Target")] = target
        df.iloc[i, df.columns.get_loc("PnL %")] = pnl

# ======================
# FILTER
# ======================
df_view = df[(df.index >= pd.Timestamp(start)) & 
             (df.index <= pd.Timestamp(end)+pd.Timedelta(days=1))]

# ======================
# TABLE
# ======================
table = df_view.reset_index()[[
    "Time","Open","High","Low","Close",
    "Decision","Entry","Target","PnL %"
]].copy()

table["Execute"] = False

st.data_editor(table, use_container_width=True)

# ======================
# RESULT
# ======================
balance = capital

for i in range(len(table)):
    if table.iloc[i]["Execute"]:
        pnl = table.iloc[i]["PnL %"]
        if pd.notna(pnl):
            balance *= (1 + pnl/100)

st.metric("Final Balance", f"${balance:.2f}")
