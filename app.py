import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 SMART HOLD STRATEGY")

# ======================
# INPUT
# ======================
col1, col2 = st.columns(2)

with col1:
    start = st.date_input("Start")
    end   = st.date_input("End")

with col2:
    capital = st.number_input("Capital ($)", value=1000)

# ======================
# DATA
# ======================
df = yf.download("BTC-USD", interval="4h", start=start, end=end)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close","Volume"]]

# ======================
# SIGNAL (پنهان)
# ======================
vol_avg = df["Volume"].rolling(20).mean()
signal = df["Volume"] > vol_avg

# ======================
# ENTRY / EXIT LOGIC
# ======================
df["Entry"] = np.nan
df["Target"] = np.nan
df["Exit"] = np.nan
df["PnL %"] = np.nan

for i in range(len(df)-1):

    if signal.iloc[i]:

        entry = df["Close"].iloc[i]
        target = entry * 1.05

        prev_close = entry
        max_high = entry
        exit_price = entry

        for j in range(i+1, len(df)):

            close = df["Close"].iloc[j]
            high = df["High"].iloc[j]

            # اگر تارگت خورد
            if high >= target:
                exit_price = target
                break

            # کندل خوب؟
            good_candle = (close > prev_close) or (high > max_high)

            if good_candle:
                prev_close = close
                max_high = max(max_high, high)
                exit_price = close
            else:
                # کندل بد → خروج
                exit_price = close
                break

        pnl = (exit_price - entry) / entry * 100

        df.at[df.index[i], "Entry"] = entry
        df.at[df.index[i], "Target"] = target
        df.at[df.index[i], "Exit"] = exit_price
        df.at[df.index[i], "PnL %"] = pnl

# ======================
# DECISION
# ======================
df["Decision"] = np.where(signal, "TRADE", "WAIT")

# ======================
# TABLE
# ======================
table = df[[
    "Open","High","Low","Close",
    "Decision","Entry","Target","Exit","PnL %"
]].copy()

table["Execute"] = False

st.subheader("📊 ALL 4H CANDLES")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION
# ======================
balance = capital

for i in range(len(edited)):

    if edited["Execute"].iloc[i]:

        pnl = edited["PnL %"].iloc[i]

        if not np.isnan(pnl):
            balance *= (1 + pnl / 100)

# ======================
# RESULT
# ======================
st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
