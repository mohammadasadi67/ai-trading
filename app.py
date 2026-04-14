import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 ONE CANDLE STRATEGY")

# ======================
# INPUT
# ======================
start = st.date_input("Start")
end   = st.date_input("End")

capital = st.number_input("Capital ($)", value=1000)

# ======================
# DATA
# ======================
df = yf.download("BTC-USD", interval="4h", start=start, end=end)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close"]]

# ======================
# TREND (ساده)
# ======================
df["Trend"] = df["Close"].shift(1) > df["Close"].shift(2)

# ======================
# ENTRY / TARGET / PNL
# ======================
df["Decision"] = np.where(df["Trend"], "TRADE", "WAIT")
df["Entry"] = np.nan
df["Target"] = np.nan
df["PnL %"] = np.nan

for i in range(2, len(df)):

    if df["Trend"].iloc[i]:

        entry = df["Open"].iloc[i]

        # تارگت بر اساس روند (حرکت قبلی)
        prev_move = df["Close"].iloc[i-1] - df["Close"].iloc[i-2]
        target = entry + prev_move

        high = df["High"].iloc[i]
        close = df["Close"].iloc[i]

        # برخورد به تارگت؟
        if high >= target:
            exit_price = target
        else:
            exit_price = close

        pnl = (exit_price - entry) / entry * 100

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

st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION
# ======================
balance = capital

for i in range(len(table)):
    if table["Execute"].iloc[i]:
        pnl = table["PnL %"].iloc[i]
        if not np.isnan(pnl):
            balance *= (1 + pnl / 100)

st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
