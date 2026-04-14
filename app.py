import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

st.set_page_config(layout="wide")
st.title("🚀 AI TRADER REAL-TIME")

# ======================
# INPUT
# ======================
col1, col2 = st.columns(2)

with col1:
    capital = st.number_input("Capital ($)", value=1000)

with col2:
    period = st.selectbox("Data Range", ["7d","30d","60d","90d"])

# ======================
# DATA 4H
# ======================
df = yf.download("BTC-USD", interval="4h", period=period)

# fix columns
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close","Volume"]]
df = df.dropna()

# timezone fix
if df.index.tz is None:
    df.index = df.index.tz_localize("UTC").tz_convert("Asia/Baghdad")
else:
    df.index = df.index.tz_convert("Asia/Baghdad")

# ======================
# INDICATORS
# ======================
df["EMA200"] = df["Close"].ewm(span=200).mean()

delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()
rs = gain / loss
df["RSI"] = 100 - (100 / (1 + rs))

df = df.dropna()

# ======================
# SIGNAL (CLOSED CANDLE)
# ======================
df["buy"] = (df["Close"] > df["EMA200"]) & (df["RSI"] < 45)

df["Entry"] = np.where(df["buy"], df["Close"], np.nan)
df["SL"] = df["Close"] * 0.97
df["TP"] = df["Close"] * 1.05

# ======================
# LIVE DATA (1m)
# ======================
live = yf.download("BTC-USD", period="1d", interval="1m")

if isinstance(live.columns, pd.MultiIndex):
    live.columns = live.columns.get_level_values(0)

if "Close" in live and not live["Close"].dropna().empty:
    live_price = float(live["Close"].dropna().iloc[-1])
else:
    live_price = float(df["Close"].iloc[-1])

# ======================
# REAL-TIME SIGNAL
# ======================
ema200 = df["EMA200"].iloc[-1]
rsi = df["RSI"].iloc[-1]

live_signal = (live_price > ema200) and (rsi < 45)

# ======================
# UI (LIVE)
# ======================
col1, col2, col3 = st.columns(3)

col1.metric("💰 Live Price", f"{live_price:.2f}")
col2.metric("EMA200", f"{ema200:.2f}")
col3.metric("RSI", f"{rsi:.1f}")

st.subheader("🔥 REAL-TIME SIGNAL")

if live_signal:
    st.success(f"BUY NOW @ {live_price:.2f}")
else:
    st.warning("WAIT")

# ======================
# TABLE
# ======================
table = df[["Close","Entry","SL","TP","RSI"]].dropna(subset=["Entry"]).copy()

table["Trade?"] = False

st.subheader("📊 Trade Table")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION (FIXED)
# ======================
balance = capital
in_trade = False

for i in range(len(edited)):
    if edited["Trade?"].iloc[i] and not in_trade:
        entry = edited["Entry"].iloc[i]
        tp = edited["TP"].iloc[i]

        profit = (tp - entry) / entry
        balance *= (1 + profit)

        in_trade = True

    if not edited["Trade?"].iloc[i]:
        in_trade = False

# ======================
# RESULT
# ======================
st.subheader("💰 RESULT")

st.metric("Final Balance", f"${balance:.2f}")

# ======================
# CHART
# ======================
st.subheader("📈 Chart")

st.line_chart(df[["Close","EMA200"]])
