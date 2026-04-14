import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

st_autorefresh(interval=60 * 1000, key="refresh")

st.set_page_config(layout="wide")
st.title("🚀 AI TRADER PRO")

# ======================
# INPUT
# ======================
col1, col2 = st.columns(2)

with col1:
    start = st.date_input("Start", datetime(2026,1,1))
    end = st.date_input("End", datetime.now())

with col2:
    capital = st.number_input("Capital ($)", value=1000)

# ======================
# DATA (UTC FIX)
# ======================
df = yf.download("BTC-USD", interval="4h", start=start, end=end)

df.index = df.index.tz_localize(None)

df = df.dropna()

# ======================
# INDICATORS
# ======================
df["EMA50"] = df["Close"].ewm(span=50).mean()
df["EMA200"] = df["Close"].ewm(span=200).mean()

delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()
rs = gain / loss
df["RSI"] = 100 - (100 / (1 + rs))

# ======================
# SIGNAL LOGIC
# ======================
df["buy"] = (df["Close"] > df["EMA200"]) & (df["RSI"] < 45)

# ======================
# ENTRY / SL / EXIT
# ======================
df["Entry"] = np.where(df["buy"], df["Close"], np.nan)
df["SL"] = df["Close"] * 0.97
df["TP"] = df["Close"] * 1.05

# ======================
# LIVE FIX (کندل امروز)
# ======================
now = datetime.utcnow()
if df.index[-1].date() < now.date():
    last_price = yf.download("BTC-USD", period="1d", interval="1m")["Close"].iloc[-1]
else:
    last_price = df["Close"].iloc[-1]

# ======================
# TABLE
# ======================
table = df[["Close","Entry","SL","TP","RSI"]].copy()
table = table.dropna(subset=["Entry"])

table["Trade?"] = False

# ======================
# UI
# ======================
col1, col2, col3 = st.columns(3)

col1.metric("💰 Price", f"{last_price:.2f}")
col2.metric("📊 Signals", len(table))
col3.metric("💼 Capital", capital)

st.subheader("📊 Trade Table")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION
# ======================
balance = capital

for i in range(len(edited)):
    if edited["Trade?"].iloc[i]:
        entry = edited["Entry"].iloc[i]
        tp = edited["TP"].iloc[i]
        sl = edited["SL"].iloc[i]

        # فرض ساده
        if tp > entry:
            profit = (tp - entry) / entry
        else:
            profit = (sl - entry) / entry

        balance *= (1 + profit)

st.subheader("💰 Result")

st.metric("Final Balance", f"${balance:.2f}")
