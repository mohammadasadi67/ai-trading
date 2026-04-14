import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")
st.title("🚀 REAL TRADINGVIEW SIGNAL (BINANCE)")

# ======================
# INPUT
# ======================
capital = st.number_input("Capital ($)", value=1000)

# ======================
# GET BINANCE DATA
# ======================
def get_binance_klines(symbol="BTCUSDT", interval="4h", limit=200):
    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

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

# ======================
# DATA (مثل TradingView)
# ======================
df = get_binance_klines()

# ======================
# SIGNAL (همون منطق تو)
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

        # تارگت داینامیک
        prev_move = prev1["Close"] - prev2["Close"]
        target = entry + prev_move

        high = df["High"].iloc[i]
        close = df["Close"].iloc[i]

        # داخل همان کندل
        if high >= target:
            exit_price = target
        else:
            exit_price = close

        pnl = (exit_price - entry) / entry * 100

        df.at[df.index[i], "Decision"] = "TRADE"
        df.at[df.index[i], "Entry"] = entry
        df.at[df.index[i], "Target"] = target
        df.at[df.index[i], "PnL %"] = pnl

# ======================
# TABLE
# ======================
table = df[[
    "Open","High","Low","Close",
    "Decision","Entry","Target","PnL %"
]].copy()

table["Execute"] = False

st.subheader("📊 ALL 4H CANDLES (BINANCE)")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION
# ======================
balance = capital

edited_df = pd.DataFrame(edited).reset_index(drop=True)

for i in range(len(edited_df)):

    if edited_df.at[i, "Execute"]:

        pnl = edited_df.at[i, "PnL %"]

        if pd.notna(pnl):
            balance *= (1 + pnl / 100)

# ======================
# RESULT
# ======================
st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
