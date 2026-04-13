import streamlit as st
import yfinance as yf
import pandas as pd

st.title("BTC AI Dashboard")

df = yf.download("BTC-USD", interval="4h", period="30d")

# اگر MultiIndex بود، درستش کن
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# حذف NaN
df = df.dropna()

# اندیکاتورها
df["EMA200"] = df["Close"].ewm(span=200).mean()
df["EMA20"] = df["Close"].ewm(span=20).mean()

# سیگنال
df["buy"] = (df["Close"] > df["EMA200"]) & (df["Close"] < df["EMA20"])

# چارت
st.line_chart(df[["Close", "EMA200", "EMA20"]])

# سیگنال‌ها
signals = df[df["buy"]]

st.write("BUY Signals:")
st.dataframe(signals.tail())
