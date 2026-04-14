import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(layout="wide")
st.title("🚀 AI TRADER (RL + BACKTEST)")

# ======================
# INPUTS
# ======================
col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("Start Date", datetime(2024,1,1))
    end_date   = st.date_input("End Date", datetime(2024,6,1))

with col2:
    capital = st.number_input("Capital ($)", value=1000)

# ======================
# DATA
# ======================
df = yf.download("BTC-USD", interval="4h", start=start_date, end=end_date)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df.dropna()

# ======================
# FEATURES
# ======================
df["return"] = df["Close"].pct_change()
df["ema"] = df["Close"].ewm(span=50).mean()

df["rsi"] = 100 - (100 / (1 + (df["Close"].diff().clip(lower=0).rolling(14).mean() /
                              (-df["Close"].diff().clip(upper=0).rolling(14).mean()))))

df = df.dropna()

# ======================
# SIMPLE RL LOGIC (جایگزین سریع)
# ======================
df["signal"] = ((df["Close"] > df["ema"]) & (df["rsi"] < 45)).astype(int)

# ======================
# BACKTEST
# ======================
balance = capital
position = 0
entry_price = 0

trades = []

for i in range(len(df)):

    price = df["Close"].iloc[i]
    sig = df["signal"].iloc[i]

    # ورود
    if sig == 1 and position == 0:
        position = 1
        entry_price = price

    # خروج
    elif sig == 0 and position == 1:
        profit = (price - entry_price) / entry_price
        balance *= (1 + profit)

        trades.append(profit)

        position = 0

# ======================
# RESULTS
# ======================
total_trades = len(trades)
wins = [t for t in trades if t > 0]
losses = [t for t in trades if t <= 0]

# ======================
# UI
# ======================
col1, col2, col3 = st.columns(3)

col1.metric("Final Balance", f"${balance:.2f}")
col2.metric("Trades", total_trades)
col3.metric("Win Rate", f"{(len(wins)/total_trades*100 if total_trades>0 else 0):.1f}%")

st.subheader("Trade Analysis")

st.write(f"Profitable Trades: {len(wins)}")
st.write(f"Losing Trades: {len(losses)}")

# کوچک / بزرگ
small = [t for t in trades if abs(t) < 0.01]
big = [t for t in trades if abs(t) >= 0.01]

st.write(f"Small Trades: {len(small)}")
st.write(f"Big Trades: {len(big)}")

# ======================
# CHART
# ======================
st.line_chart(df["Close"])

# ======================
# MANUAL MODE
# ======================
st.subheader("Manual Trade Simulation")

simulate = st.checkbox("I take this trade")

if simulate:
    st.success("Trade Executed (Manual Mode)")
