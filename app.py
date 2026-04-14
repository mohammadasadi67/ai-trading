import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 FULL CANDLE TABLE")

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

# فیکس ستون
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close","Volume"]]

# ❗ مهم: هیچ dropna روی کل دیتا نزن
df = df.copy()

# ======================
# INDICATORS
# ======================
df["EMA200"] = df["Close"].ewm(span=200).mean()

delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()
rs = gain / loss
df["RSI"] = 100 - (100 / (1 + rs))

# ======================
# SIGNAL
# ======================
df["Signal"] = (df["Close"] > df["EMA200"]) & (df["RSI"] < 45)

# ======================
# ENTRY / SL / EXIT فقط برای سیگنال
# ======================
df["Entry"] = np.nan
df["SL"] = np.nan
df["Exit"] = np.nan

mask = df["Signal"] == True

df.loc[mask, "Entry"] = df["Close"]
df.loc[mask, "SL"] = df["Close"] * 0.97
df.loc[mask, "Exit"] = df["Close"] * 1.05

# ======================
# TABLE (همه کندل‌ها)
# ======================
table = df[["Open","High","Low","Close","Volume","Signal","Entry","SL","Exit","RSI"]].copy()

table["Trade?"] = False

st.subheader("📊 ALL 4H CANDLES")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION
# ======================
balance = capital
in_trade = False

for i in range(len(edited)):

    if edited["Trade?"].iloc[i] and not in_trade:

        entry = edited["Entry"].iloc[i]
        exit_price = edited["Exit"].iloc[i]

        if not np.isnan(entry) and not np.isnan(exit_price):
            profit = (exit_price - entry) / entry
            balance *= (1 + profit)
            in_trade = True

    if not edited["Trade?"].iloc[i]:
        in_trade = False

# ======================
# RESULT
# ======================
st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
