import streamlit as st
import yfinance as yf
import pandas as pd

st.title("BTC AI Dashboard")

df = yf.download("BTC-USD", interval="4h", period="30d")

df["EMA200"] = df["Close"].ewm(span=200).mean()
df["EMA20"] = df["Close"].ewm(span=20).mean()

df["buy"] = (df["Close"] > df["EMA200"]) & (df["Close"] < df["EMA20"])

st.line_chart(df[["Close", "EMA200", "EMA20"]])

signals = df[df["buy"] == True]

st.write("BUY Signals:")
st.write(signals.tail())
