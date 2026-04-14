import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")
st.title("🚀 REAL TRADINGVIEW SIGNAL (BINANCE FIXED)")

# ======================
# INPUT
# ======================
capital = st.number_input("Capital ($)", value=1000)

# ======================
# GET BINANCE DATA (FIXED)
# ======================
def get_binance_klines(symbol="BTCUSDT", interval="4h", limit=200):

    url = "https://data-api.binance.vision/api/v3/klines"  # 🔥 نسخه بدون بلاک

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            st.error("❌ Binance API Error")
            st.write(response.text)
            return pd.DataFrame()

        data = response.json()

        if not data or isinstance(data, dict):
            st.error("❌ No Data from Binance")
            st.write(data)
            return pd.DataFrame()

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

    except Exception as e:
        st.error("❌ Request Failed")
        st.write(e)
        return pd.DataFrame()

# ======================
# LOAD DATA
# ======================
df = get_binance_klines()

if df.empty:
    st.stop()

# ======================
# SIGNAL LOGIC (همون تو)
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

        prev_move = prev1["Close"] - prev2["Close"]
        target = entry + prev_move

        high = df["High"].iloc[i]
        close = df["Close"].iloc[i]

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
table = df.reset_index()[[
    "Time","Open","High","Low","Close",
    "Decision","Entry","Target","PnL %"
]].copy()

table["Execute"] = False

st.subheader("📊 ALL 4H CANDLES (REAL BINANCE)")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION (FIXED)
# ======================
balance = capital

edited_df = pd.DataFrame(edited)

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
