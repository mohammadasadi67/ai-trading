import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

st.set_page_config(layout="wide", page_title="BTC Whale PRO")

# ======================
# UI CONTROL
# ======================
st.sidebar.header("⚙️ Data Settings")

mode = st.sidebar.selectbox(
    "Mode",
    ["⚡ Fast (6 months)", "🧠 Deep (2023+)"]
)

# ======================
# DATA ENGINE (SMART)
# ======================
@st.cache_data(ttl=3600)
def fetch_data(mode):

    url = "https://data-api.binance.vision/api/v3/klines"

    if "Fast" in mode:
        start_time = datetime.now() - pd.Timedelta(days=180)
        max_loops = 10
    else:
        start_time = datetime(2023, 1, 1)
        max_loops = 60  # کنترل شده

    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(datetime.now().timestamp() * 1000)

    all_data = []
    current_ts = start_ts

    progress = st.sidebar.progress(0)
    status = st.sidebar.empty()

    loops = 0

    while current_ts < end_ts and loops < max_loops:
        loops += 1

        try:
            params = {
                "symbol": "BTCUSDT",
                "interval": "4h",
                "startTime": current_ts,
                "limit": 1000
            }

            res = requests.get(url, params=params, timeout=10)

            if res.status_code != 200:
                time.sleep(1)
                continue

            data = res.json()

            if not isinstance(data, list) or len(data) == 0:
                break

            all_data.extend(data)

            current_ts = data[-1][0] + 1

            progress.progress(min(1.0, loops / max_loops))
            status.text(f"Loading chunk {loops}")

        except:
            time.sleep(1)
            continue

    if len(all_data) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(all_data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]

    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)


# ======================
# INDICATORS
# ======================
def add_indicators(df):

    df = df.copy()

    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    tr = pd.concat([
        df["High"]-df["Low"],
        abs(df["High"]-df["Close"].shift()),
        abs(df["Low"]-df["Close"].shift())
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(span=14).mean()

    df["H_48"] = df["High"].rolling(12).max().shift(1)
    df["L_48"] = df["Low"].rolling(12).min().shift(1)

    return df.dropna()


# ======================
# ENGINE
# ======================
def run_engine(df, capital=1000):

    balance = capital
    equity = []
    trades = []

    in_pos = False
    entry = sl = units = 0

    for i in range(50, len(df)):

        row = df.iloc[i]

        curr_val = balance + ((row["Close"] - entry) * units if in_pos else 0)
        equity.append(curr_val)

        if not in_pos:

            if row["Close"] > row["H_48"] and row["Close"] > row["EMA50"]:

                entry = row["Close"] * 1.001
                sl = row["L_48"]

                risk = balance * 0.01
                dist = entry - sl

                if dist <= 0:
                    continue

                units = risk / dist

                balance -= entry * units * 0.001

                in_pos = True
                trades.append(("BUY", df.index[i], entry))

        else:

            if row["Low"] <= sl or row["Close"] < row["EMA50"]:

                exit_p = row["Close"] * 0.999

                balance += exit_p * units
                balance -= exit_p * units * 0.001

                trades.append(("SELL", df.index[i], exit_p))

                in_pos = False
                units = 0

    return trades, equity, balance


# ======================
# RUN
# ======================
st.title("🐋 BTC Whale PRO")

df = fetch_data(mode)

if df.empty:
    st.error("❌ Data failed")
    st.stop()

df = add_indicators(df)

trades, equity, final_balance = run_engine(df)

# ======================
# UI
# ======================
c1, c2 = st.columns(2)

c1.metric("Final Balance", f"${final_balance:,.2f}")
c2.metric("Trades", len(trades))

st.subheader("📈 Equity Curve")
st.line_chart(equity)

st.subheader("📝 Trades")
st.write(trades)
