import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

st.set_page_config(layout="wide")
st.title("🚀 LIVE TRADING (1s UPDATE)")

# ======================
# AUTO REFRESH
# ======================
time.sleep(1)
st.experimental_rerun()

# ======================
# INPUT
# ======================
start = st.date_input("Start Date")
end   = st.date_input("End Date")
capital = st.number_input("Capital", value=100)

# ======================
# GET 4H DATA
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
# LIVE DATA (چند دقیقه اخیر)
# ======================
live = requests.get(
    "https://data-api.binance.vision/api/v3/klines",
    params={"symbol": "BTCUSDT", "interval": "1m", "limit": 30}
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

# ======================
# BUILD LIVE CANDLE
# ======================
last_4h = df.index[-1]
next_4h = last_4h + pd.Timedelta(hours=4)

current = live_df[live_df.index >= last_4h]

if not current.empty:

    open_ = current["Open"].iloc[0]
    high_ = current["High"].max()
    low_  = current["Low"].min()
    close_ = current["Close"].iloc[-1]  # 🔥 لایو

    new_row = pd.DataFrame({
        "Open":[open_],
        "High":[high_],
        "Low":[low_],
        "Close":[close_]
    }, index=[next_4h])

    if next_4h in df.index:
        df = df.drop(next_4h)

    df = pd.concat([df, new_row])
    df = df.sort_index()

# ======================
# SIGNAL
# ======================
df["Decision"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan

for i in range(2, len(df)):

    prev1 = df.iloc[i-1]
    prev2 = df.iloc[i-2]

    if prev1["Close"] > prev2["Close"]:

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
# RESULT (PnL مثل قبل)
# ======================
balance = capital

for i in range(len(table)):

    if table.iloc[i]["Execute"]:

        entry = table.iloc[i]["Entry"]
        target = table.iloc[i]["Target"]
        close  = table.iloc[i]["Close"]

        if pd.notna(entry) and pd.notna(target):

            if close >= target:
                pnl = (target - entry) / entry
            else:
                pnl = (close - entry) / entry

            balance *= (1 + pnl)

st.metric("Final Balance", f"${balance:.2f}")
