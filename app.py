import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.title("AI TRADER PRO")

# ======================
# INPUT
# ======================
start = st.date_input("Start", datetime(2026,1,1))
end   = st.date_input("End", datetime.now())

capital = st.number_input("Capital ($)", value=1000)

# ======================
# DATA
# ======================
df = yf.download("BTC-USD", interval="4h", start=start, end=end)

# 💥 مهم: فیکس ستون‌ها
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# فقط ستون‌های لازم
df = df[["Open","High","Low","Close","Volume"]]

df = df.dropna()

# ======================
# INDICATORS
# ======================
df["EMA50"] = df["Close"].ewm(span=50).mean()
df["EMA200"] = df["Close"].ewm(span=200).mean()

# RSI
delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()
rs = gain / loss
df["RSI"] = 100 - (100 / (1 + rs))

df = df.dropna()

# ======================
# سیگنال (فیکس شده)
# ======================
close = df["Close"].astype(float)
ema200 = df["EMA200"].astype(float)
rsi = df["RSI"].astype(float)

df["buy"] = (close > ema200) & (rsi < 45)

# ======================
# ENTRY / SL / TP
# ======================
df["Entry"] = np.where(df["buy"], close, np.nan)
df["SL"] = close * 0.97
df["TP"] = close * 1.05

# ======================
# TABLE
# ======================
table = df[["Close","Entry","SL","TP","RSI"]].dropna(subset=["Entry"])

table["Trade?"] = False

# ======================
# UI
# ======================
st.subheader("Trade Table")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION
# ======================
balance = capital

for i in range(len(edited)):
    if edited["Trade?"].iloc[i]:
        entry = edited["Entry"].iloc[i]
        tp = edited["TP"].iloc[i]

        profit = (tp - entry) / entry
        balance *= (1 + profit)

st.metric("Final Balance", f"${balance:.2f}")
