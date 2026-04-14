import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

st.title("AI TRADER PRO")

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

# فیکس ستون
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close","Volume"]]

# 💥 تبدیل زمان به لوکال
df.index = df.index.tz_localize("UTC").tz_convert("Asia/Baghdad")

df = df.dropna()

# ======================
# اندیکاتور
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
# اضافه کردن قیمت لایو (کندل امروز)
# ======================
live = yf.download("BTC-USD", period="1d", interval="1m")

if not live.empty:
    last_price = live["Close"].iloc[-1]
    now = datetime.now(pytz.timezone("Asia/Baghdad"))

    df.loc[now] = [last_price]*5 + [np.nan]*5

# ======================
# TABLE
# ======================
table = df[["Close","Entry","SL","TP","RSI"]].dropna(subset=["Entry"])

table["Trade?"] = False

st.subheader("Trade Table")
edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION (فیکس شده)
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

    else:
        in_trade = False

# ======================
# RESULT
# ======================
st.metric("Final Balance", f"${balance:.2f}")
