import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 CLEAN TRADING TABLE")

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
# INTERNAL LOGIC (پنهان)
# ======================
vol_avg = df["Volume"].rolling(20).mean()
vol_signal = df["Volume"] > vol_avg

# ======================
# ENTRY / SL / TP
# ======================
df["Entry"] = np.nan
df["SL"] = np.nan
df["TP"] = np.nan

df.loc[vol_signal, "Entry"] = df["Close"]
df.loc[vol_signal, "SL"] = df["Close"] * 0.97
df.loc[vol_signal, "TP"] = df["Close"] * 1.05

# ======================
# REAL PNL
# ======================
df["PnL %"] = np.nan

for i in range(len(df)):

    if vol_signal.iloc[i]:

        entry = df["Close"].iloc[i]
        tp = entry * 1.05
        sl = entry * 0.97

        for j in range(i+1, len(df)):

            high = df["High"].iloc[j]
            low = df["Low"].iloc[j]

            if high >= tp:
                df.at[df.index[i], "PnL %"] = ((tp - entry) / entry) * 100
                break

            if low <= sl:
                df.at[df.index[i], "PnL %"] = ((sl - entry) / entry) * 100
                break

# ======================
# DECISION
# ======================
df["Decision"] = np.where(vol_signal, "TRADE", "WAIT")

# ======================
# TABLE (فقط چیزهای مهم)
# ======================
table = df[[
    "Open","High","Low","Close",
    "Decision","Entry","SL","TP","PnL %"
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
