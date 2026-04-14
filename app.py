import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# =====================
# AUTO REFRESH
# =====================
st_autorefresh(interval=60 * 1000, key="refresh")

st.set_page_config(layout="wide")
st.title("🚀 BTC LIVE AI TRADER")

# =====================
# DATA
# =====================
df = yf.download("BTC-USD", interval="4h", period="10d")

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df.dropna()

# =====================
# INDICATORS
# =====================
df["EMA50"] = df["Close"].ewm(span=50).mean()
df["EMA200"] = df["Close"].ewm(span=200).mean()

# RSI
delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()
rs = gain / loss
df["RSI"] = 100 - (100 / (1 + rs))

# =====================
# SIGNAL
# =====================
df["buy"] = (df["Close"] > df["EMA200"]) & (df["RSI"] < 40)

# =====================
# LIVE PRICE
# =====================
last_price = float(df["Close"].iloc[-1])

# =====================
# CANDLE TIMER (4H)
# =====================
now = datetime.utcnow()
hour = now.hour
next_candle_hour = (hour // 4 + 1) * 4
if next_candle_hour >= 24:
    next_candle_hour = 0

next_candle = now.replace(hour=next_candle_hour, minute=0, second=0, microsecond=0)
if next_candle <= now:
    next_candle += timedelta(hours=4)

remaining = next_candle - now

# =====================
# UI
# =====================
col1, col2, col3 = st.columns(3)

col1.metric("💰 Price", f"{last_price:.2f}")
col2.metric("⏳ Candle Close", str(remaining).split(".")[0])
col3.metric("📊 RSI", f"{df['RSI'].iloc[-1]:.1f}")

# =====================
# SIGNAL DISPLAY
# =====================
last_signal = df["buy"].iloc[-1]

if last_signal:
    st.success(f"🔥 BUY SIGNAL @ {last_price:.2f}")
else:
    st.warning("No Trade")

# =====================
# CHART
# =====================
st.subheader("📈 Chart")

chart_df = df[["Close", "EMA50", "EMA200"]]

st.line_chart(chart_df)

# =====================
# SIGNAL TABLE
# =====================
st.subheader("📊 Signals")

signals = df[df["buy"]]
st.dataframe(signals.tail(10))
