import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC SMART WHALE V30")
st.title("🐋 BTC SMART WHALE (Hourly Engine → Daily View)")

# ======================
# DATA ENGINE (STABLE)
# ======================
@st.cache_data(ttl=600)
def get_data(start_str="2023-01-01"):

    endpoints = [
        "https://data-api.binance.vision/api/v3/klines",
        "https://api1.binance.com/api/v3/klines"
    ]

    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)

    for url in endpoints:
        all_data = []
        current_ts = start_ts

        try:
            while True:
                params = {
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "startTime": current_ts,
                    "limit": 1000
                }

                res = requests.get(url, params=params, timeout=10)

                if res.status_code != 200:
                    break

                data = res.json()

                if not isinstance(data, list) or not data:
                    break

                all_data.extend(data)
                current_ts = data[-1][0] + 1

                if len(data) < 1000:
                    break

            if all_data:
                df = pd.DataFrame(all_data)
                df = df.iloc[:, :5]
                df.columns = ["Time", "Open", "High", "Low", "Close"]
                df["Time"] = pd.to_datetime(df["Time"], unit="ms")
                df.set_index("Time", inplace=True)
                return df.astype(float)

        except:
            continue

    return pd.DataFrame()

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("⚙️ Settings")
    start_dt = st.date_input("Start Date", value=date(2023,1,1))
    end_dt = st.date_input("End Date", value=date.today())

    capital = st.number_input("Capital ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100

# ======================
# LOAD DATA
# ======================
df_raw = get_data("2023-01-01")

if df_raw.empty:
    st.error("❌ Data loading failed")
    st.stop()

# ======================
# INDICATORS
# ======================
df = df_raw.copy()

df["MA200"] = df["Close"].rolling(200).mean()
df["H_48"] = df["High"].rolling(48).max().shift(1)
df["L_48"] = df["Low"].rolling(48).min().shift(1)

# ======================
# BACKTEST ENGINE (1H)
# ======================
df["Action"] = "WAIT"
df["Entry"] = 0.0
df["SL"] = 0.0
df["TP"] = 0.0
df["PnL"] = 0.0

balance = 1.0
in_pos = False
entry = sl = tp = highest = 0

for i in range(200, len(df)):

    t = df.index[i]
    if not (start_dt <= t.date() <= end_dt):
        continue

    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]
    ma200 = df["MA200"].iloc[i]
    h48 = df["H_48"].iloc[i]
    l48 = df["L_48"].iloc[i]

    idx = df.index[i]

    # ENTRY
    if not in_pos:
        if c > h48 and c > ma200:
            entry = c
            sl = l48
            tp = entry * 1.05
            highest = entry
            in_pos = True

            df.at[idx, "Action"] = "BUY"
            df.at[idx, "Entry"] = entry
            df.at[idx, "SL"] = sl
            df.at[idx, "TP"] = tp

    # HOLD
    else:
        df.at[idx, "Action"] = "HOLD"

        if h > highest:
            highest = h

        # trailing
        sl = max(sl, l48)
        tp = max(tp, highest * 1.03)

        df.at[idx, "Entry"] = entry
        df.at[idx, "SL"] = sl
        df.at[idx, "TP"] = tp

        exit_price = 0

        if l <= sl:
            exit_price = sl

        if exit_price > 0:
            pnl = ((exit_price - entry) / entry) - (fee * 2)
            balance *= (1 + pnl)

            df.at[idx, "Action"] = "EXIT"
            df.at[idx, "PnL"] = pnl * 100

            in_pos = False

# ======================
# DAILY VIEW
# ======================
df["Date"] = df.index.date

daily = df.groupby("Date").agg({
    "Close": "last",
    "Action": lambda x: x.iloc[-1],
    "Entry": "last",
    "SL": "last",
    "TP": "last",
    "PnL": "sum"
})

daily = daily[(daily.index >= start_dt) & (daily.index <= end_dt)]

# ======================
# METRICS
# ======================
net_profit = (balance - 1) * 100
trades = len(df[df["Action"] == "EXIT"])

c1, c2, c3 = st.columns(3)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")
c3.metric("Trades", trades)

# ======================
# TABLE
# ======================
st.divider()
st.subheader("📊 Daily Trade View (with Dynamic Levels)")

st.dataframe(
    daily.sort_index(ascending=False)
    .style.format({
        "Close": "{:,.1f}",
        "Entry": "{:,.1f}",
        "SL": "{:,.1f}",
        "TP": "{:,.1f}",
        "PnL": "{:+.2f}%"
    }),
    use_container_width=True,
    height=600
)
