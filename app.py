import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

st.set_page_config(layout="wide", page_title="BTC Whale PRO")

# ======================
# DATA (FAST + SAFE)
# ======================
@st.cache_data(ttl=3600)
def fetch_data():
    url = "https://data-api.binance.vision/api/v3/klines"

    params = {
        "symbol": "BTCUSDT",
        "interval": "4h",
        "limit": 1000
    }

    res = requests.get(url, params=params, timeout=10)
    data = res.json()

    df = pd.DataFrame(data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]

    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)


# ======================
# INDICATORS
# ======================
def add_indicators(df):

    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["ATR"] = (
        pd.concat([
            df["High"]-df["Low"],
            abs(df["High"]-df["Close"].shift()),
            abs(df["Low"]-df["Close"].shift())
        ], axis=1).max(axis=1)
    ).ewm(span=14).mean()

    df["H_48"] = df["High"].rolling(12).max().shift(1)
    df["L_48"] = df["Low"].rolling(12).min().shift(1)

    return df.dropna()


# ======================
# ENGINE (NO BIAS)
# ======================
def run_engine(df, capital=1000):

    balance = capital
    equity = []
    trades = []

    in_pos = False
    entry = sl = units = 0

    for i in range(50, len(df)-1):

        row = df.iloc[i]
        next_open = df.iloc[i+1]["Open"]

        curr_val = balance + ((row["Close"] - entry) * units if in_pos else 0)
        equity.append(curr_val)

        if not in_pos:

            if row["Close"] > row["H_48"] and row["Close"] > row["EMA50"]:

                entry = next_open * 1.001
                sl = row["L_48"]

                dist = entry - sl
                if dist <= 0:
                    continue

                risk = balance * 0.01
                units = risk / dist

                # cap position
                units = min(units, (balance * 0.3) / entry)

                balance -= entry * units * 0.001

                in_pos = True
                trades.append({
                    "Time": df.index[i],
                    "Type": "BUY",
                    "Price": entry
                })

        else:

            stop_hit = row["Open"] <= sl or row["Low"] <= sl

            if stop_hit or row["Close"] < row["EMA50"]:

                exit_price = (sl if stop_hit else next_open) * 0.999

                pnl = (exit_price - entry) * units

                balance += exit_price * units
                balance -= exit_price * units * 0.001

                trades.append({
                    "Time": df.index[i],
                    "Type": "SELL",
                    "Price": exit_price,
                    "PnL": pnl,
                    "PnL%": (exit_price/entry - 1) * 100
                })

                in_pos = False
                units = 0

    return pd.DataFrame(trades), equity, balance


# ======================
# UI
# ======================
st.title("🐋 BTC Whale PRO (Realistic)")

df = fetch_data()
df = add_indicators(df)

trades, equity, final_balance = run_engine(df)

# ======================
# METRICS
# ======================
c1, c2, c3 = st.columns(3)

c1.metric("Final Balance", f"${final_balance:,.2f}")
c2.metric("Trades", len(trades))

if "PnL%" in trades.columns:
    exits = trades.dropna()
    win_rate = (exits["PnL%"] > 0).mean() * 100
    c3.metric("Win Rate", f"{win_rate:.1f}%")

# ======================
# EQUITY
# ======================
st.subheader("📈 Equity Curve")
st.line_chart(equity)

# ======================
# TABLE (🔥 رنگی حرفه‌ای)
# ======================
st.subheader("📊 Trade Table")

if not trades.empty:

    trades = trades.sort_values("Time", ascending=False)

    def color_pnl(val):
        if pd.isna(val):
            return ""
        return "color: lime" if val > 0 else "color: red"

    def bg_type(val):
        if val == "BUY":
            return "background-color: #0f5132; color:white"
        elif val == "SELL":
            return "background-color: #842029; color:white"
        return ""

    styled = trades.style \
        .applymap(color_pnl, subset=["PnL","PnL%"]) \
        .applymap(bg_type, subset=["Type"]) \
        .format({
            "Price": "{:,.2f}",
            "PnL": "{:,.2f}",
            "PnL%": "{:.2f}%"
        })

    st.dataframe(styled, use_container_width=True)

else:
    st.warning("No trades yet.")
