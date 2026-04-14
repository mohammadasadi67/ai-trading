import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")
st.title("🚀 FINAL WORKING VERSION")

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
# FORCE ADD LIVE CANDLE
# ======================
live = get_4h(limit=1)  # 👈 آخرین کندل

last_time = live.index[-1]

# اگر این کندل تو df نیست → اضافه کن
if last_time not in df.index:
    df.loc[last_time] = live.iloc[-1]
else:
    # آپدیت کن
    df.loc[last_time] = live.iloc[-1]

df = df.sort_index()

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
df.index.name = "Time"

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
