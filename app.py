import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")
st.title("🚀 REAL LIVE TRADING SYSTEM (TRADINGVIEW MODE)")

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
# GET HISTORICAL DATA (4H)
# ======================
def get_4h(symbol="BTCUSDT", start=None, end=None):

    url = "https://data-api.binance.vision/api/v3/klines"

    start_ms = int(pd.Timestamp(start).timestamp()*1000)
    end_ms   = int((pd.Timestamp(end)+pd.Timedelta(days=1)).timestamp()*1000)

    all_data = []

    while True:
        params = {
            "symbol": symbol,
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

    # 🔥 تبدیل به ساعت TradingView (عراق)
    df.index = df.index.tz_localize("UTC").tz_convert("Asia/Baghdad")

    return df

# ======================
# LOAD DATA + BUFFER
# ======================
real_start = pd.Timestamp(start) - pd.Timedelta(days=2)
df = get_4h(start=real_start, end=end)

if df.empty:
    st.error("No data")
    st.stop()

# ======================
# LIVE 1m DATA
# ======================
live = requests.get(
    "https://data-api.binance.vision/api/v3/klines",
    params={"symbol": "BTCUSDT", "interval": "1m", "limit": 300}
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

# 🔥 timezone هماهنگ
live_df.index = live_df.index.tz_localize("UTC").tz_convert("Asia/Baghdad")

# ======================
# ساخت کندل 4H لایو (مثل TradingView)
# ======================
last_candle_time = df.index[-1]
next_candle_time = last_candle_time + pd.Timedelta(hours=4)

current = live_df[live_df.index >= next_candle_time]

if not current.empty:

    open_ = current["Open"].iloc[0]
    high_ = current["High"].max()
    low_  = current["Low"].min()
    close_ = current["Close"].iloc[-1]

    new_candle = pd.DataFrame({
        "Open":[open_],
        "High":[high_],
        "Low":[low_],
        "Close":[close_]
    }, index=[next_candle_time])

    df = pd.concat([df, new_candle])

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

    trend = prev1["Close"] > prev2["Close"]

    if trend:

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
# FILTER VIEW
# ======================
df_view = df[(df.index >= pd.Timestamp(start).tz_localize("Asia/Baghdad")) & 
             (df.index <= (pd.Timestamp(end)+pd.Timedelta(days=1)).tz_localize("Asia/Baghdad"))]

# ======================
# TABLE
# ======================
table = df_view.reset_index()[[
    "Time","Open","High","Low","Close",
    "Decision","Entry","Target","PnL %"
]].copy()

table["Execute"] = False

st.subheader("📊 ALL 4H CANDLES + LIVE (TradingView Match)")

edited = st.data_editor(table, use_container_width=True)

# ======================
# RESULT
# ======================
balance = capital

for i in range(len(edited)):
    if edited.iloc[i]["Execute"]:
        pnl = edited.iloc[i]["PnL %"]
        if pd.notna(pnl):
            balance *= (1 + pnl/100)

st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
