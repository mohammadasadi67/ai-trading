import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 FULL 4H TRADING TABLE")

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
# INDICATOR (فقط EMA)
# ======================
df["EMA200"] = df["Close"].ewm(span=200).mean()

# ======================
# SIGNAL (با حجم)
# ======================
df["Vol_Avg"] = df["Volume"].rolling(20).mean()
df["Vol_Signal"] = df["Volume"] > df["Vol_Avg"]

df["Signal"] = (df["Close"] > df["EMA200"]) & df["Vol_Signal"]

# ======================
# ENTRY / EXIT / SL
# ======================
df["Entry"] = np.nan
df["Exit"] = np.nan
df["SL"] = np.nan

mask = df["Signal"] == True

df.loc[mask, "Entry"] = df["Close"]
df.loc[mask, "Exit"] = df["Close"] * 1.05
df.loc[mask, "SL"] = df["Close"] * 0.97

# ======================
# سود/ضرر درصدی
# ======================
df["PnL %"] = np.where(
    df["Signal"],
    ((df["Exit"] - df["Entry"]) / df["Entry"]) * 100,
    np.nan
)

# ======================
# DECISION
# ======================
df["Decision"] = np.where(df["Signal"], "TRADE", "WAIT")

# ======================
# TABLE
# ======================
table = df[[
    "Open","High","Low","Close","Volume",
    "Vol_Signal","Signal","Decision",
    "Entry","SL","Exit","PnL %"
]].copy()

table["Execute"] = False

st.subheader("📊 ALL 4H CANDLES")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION
# ======================
balance = capital
in_trade = False

for i in range(len(edited)):

    if edited["Execute"].iloc[i] and not in_trade:

        entry = edited["Entry"].iloc[i]
        exit_price = edited["Exit"].iloc[i]

        if not np.isnan(entry) and not np.isnan(exit_price):
            profit = (exit_price - entry) / entry
            balance *= (1 + profit)
            in_trade = True

    if not edited["Execute"].iloc[i]:
        in_trade = False

# ======================
# RESULT
# ======================
st.subheader("💰 RESULT")

st.metric("Final Balance", f"${balance:.2f}")
