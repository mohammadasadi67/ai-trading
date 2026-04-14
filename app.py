import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

st.set_page_config(layout="wide")
st.title("🚀 AI TRADER PRO FINAL")

# ======================
# INPUT
# ======================
col1, col2 = st.columns(2)

with col1:
    start = st.date_input("Start")
    end = st.date_input("End")

with col2:
    capital = st.number_input("Capital ($)", value=1000)

# ======================
# DATA
# ======================
df = yf.download("BTC-USD", interval="4h", start=start, end=end)

# Fix MultiIndex
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close","Volume"]]

# ===== TIMEZONE FIX =====
if df.index.tz is None:
    df.index = df.index.tz_localize("UTC").tz_convert("Asia/Baghdad")
else:
    df.index = df.index.tz_convert("Asia/Baghdad")

df = df.dropna()

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
# SIGNAL
# ======================
df["buy"] = (df["Close"] > df["EMA200"]) & (df["RSI"] < 45)

df["Entry"] = np.where(df["buy"], df["Close"], np.nan)
df["SL"] = df["Close"] * 0.97
df["TP"] = df["Close"] * 1.05

# ======================
# LIVE PRICE
# ======================
live = yf.download("BTC-USD", period="1d", interval="1m")

if not live.empty:
    last_price = float(live["Close"].iloc[-1])
    now = datetime.now(pytz.timezone("Asia/Baghdad"))

    new_row = {col: np.nan for col in df.columns}
    new_row["Close"] = last_price
    new_row["Open"] = last_price
    new_row["High"] = last_price
    new_row["Low"] = last_price

    df.loc[now] = new_row
else:
    last_price = df["Close"].iloc[-1]

# ======================
# TABLE
# ======================
table = df[["Close","Entry","SL","TP","RSI"]].dropna(subset=["Entry"]).copy()

table["Trade?"] = False

st.subheader("📊 Trade Table")
edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION (REAL FIX)
# ======================
balance = capital
in_trade = False

for i in range(len(edited)):

    if edited["Trade?"].iloc[i] and not in_trade:
        entry = edited["Entry"].iloc[i]
        tp = edited["TP"].iloc[i]
        sl = edited["SL"].iloc[i]

        # ساده: فرض TP
        profit = (tp - entry) / entry

        balance *= (1 + profit)
        in_trade = True

    if not edited["Trade?"].iloc[i]:
        in_trade = False

# ======================
# UI
# ======================
col1, col2, col3 = st.columns(3)

col1.metric("💰 Live Price", f"{last_price:.2f}")
col2.metric("📊 Signals", len(table))
col3.metric("💼 Capital", capital)

st.metric("💰 Final Balance", f"${balance:.2f}")
