import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 REAL-TIME 4H SIGNAL")

# ======================
# INPUT
# ======================
capital = st.number_input("Capital ($)", value=1000)

# ======================
# DATA 4H (بسته شده‌ها)
# ======================
df = yf.download("BTC-USD", interval="4h", period="3d")

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close"]]

# ======================
# LIVE 1m DATA
# ======================
live = yf.download("BTC-USD", period="1d", interval="1m")

if isinstance(live.columns, pd.MultiIndex):
    live.columns = live.columns.get_level_values(0)

# ======================
# تشخیص شروع کندل جدید
# ======================
now = pd.Timestamp.now()

new_candle = (now.minute == 0) and (now.hour % 4 == 0)

# ======================
# SIGNAL
# ======================
signal_data = []

if new_candle:

    prev1 = df.iloc[-1]
    prev2 = df.iloc[-2]

    trend = prev1["Close"] > prev2["Close"]

    if trend:

        entry = live["Open"].iloc[-1]

        prev_move = prev1["Close"] - prev2["Close"]
        target = entry + prev_move

        signal_data.append({
            "Time": now,
            "Decision": "TRADE",
            "Entry": entry,
            "Target": target
        })

        st.success("🔥 NEW 4H SIGNAL")
        st.write(f"Entry: {entry:.2f}")
        st.write(f"Target: {target:.2f}")

    else:
        st.warning("WAIT")

else:
    st.info("⏳ Waiting for new 4H candle...")

# ======================
# TABLE
# ======================
signal_df = pd.DataFrame(signal_data)

if not signal_df.empty:

    signal_df["Execute"] = False

    edited = st.data_editor(signal_df, use_container_width=True)

    # ======================
    # SIMULATION
    # ======================
    balance = capital

    edited_df = pd.DataFrame(edited)

    for i in range(len(edited_df)):

        if edited_df.at[i, "Execute"]:

            entry = edited_df.at[i, "Entry"]
            target = edited_df.at[i, "Target"]

            pnl = (target - entry) / entry
            balance *= (1 + pnl)

    st.subheader("💰 RESULT")
    st.metric("Final Balance", f"${balance:.2f}")
