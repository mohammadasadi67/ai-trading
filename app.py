import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("🐋 BTC SMART WHALE (2-3 Day Hold Mode)")

# ======================
# DATA LOOP
# ======================
@st.cache_data(ttl=600)
def get_data(start_str="2023-01-01"):

    url = "https://data-api.binance.vision/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)

    all_data = []

    while True:
        params = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "startTime": start_ts,
            "limit": 1000
        }

        data = requests.get(url, params=params).json()

        if not data:
            break

        all_data.extend(data)
        start_ts = data[-1][0] + 1

        if len(data) < 1000:
            break

    df = pd.DataFrame(all_data).iloc[:, :5]
    df.columns = ["Time","Open","High","Low","Close"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)

df = get_data()

# ======================
# SETTINGS
# ======================
with st.sidebar:
    start_dt = st.date_input("Start", value=date(2024,1,1))
    end_dt = st.date_input("End", value=date.today())
    capital = st.number_input("Capital", value=1000.0)
    max_hold_days = st.slider("Max Hold Days", 1, 5, 2)

# ======================
# INDICATORS
# ======================
df["MA200"] = df["Close"].rolling(200).mean()
df["H_24"] = df["High"].rolling(24).max().shift(1)
df["L_24"] = df["Low"].rolling(24).min().shift(1)

df["Date"] = df.index.date

# ======================
# ENGINE
# ======================
df["Action"] = "WAIT"
df["Entry"] = 0.0
df["PnL"] = 0.0

balance = 1.0
in_pos = False
entry = 0
entry_time = None

for i in range(200, len(df)):

    t = df.index[i]
    d = t.date()

    if not (start_dt <= d <= end_dt):
        continue

    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]

    ma200 = df["MA200"].iloc[i]
    ma200_prev = df["MA200"].iloc[i-10]

    h24 = df["H_24"].iloc[i]
    l24 = df["L_24"].iloc[i]

    idx = df.index[i]

    # ======================
    # ENTRY
    # ======================
    if not in_pos:
        trend_ok = (c > ma200) and (ma200 > ma200_prev)

        if c > h24 and trend_ok:
            entry = c
            entry_time = t
            sl = entry * 0.97
            highest = entry
            in_pos = True

            df.at[idx, "Action"] = "BUY"
            df.at[idx, "Entry"] = entry

    # ======================
    # HOLD
    # ======================
    else:
        df.at[idx, "Action"] = "HOLD"
        df.at[idx, "Entry"] = entry

        if h > highest:
            highest = h

        # 🔥 trailing profit lock
        if highest > entry * 1.03:
            sl = max(sl, entry)

        if highest > entry * 1.08:
            sl = max(sl, highest * 0.96)

        # ⏱️ time-based exit
        days_held = (t - entry_time).days

        exit_price = 0

        if l <= sl:
            exit_price = sl

        elif days_held >= max_hold_days:
            exit_price = c

        if exit_price > 0:
            pnl = (exit_price - entry) / entry
            balance *= (1 + pnl)

            df.at[idx, "Action"] = "EXIT"
            df.at[idx, "PnL"] = pnl * 100

            in_pos = False

# ======================
# DAILY VIEW
# ======================
daily = df.groupby("Date").agg({
    "Close": "last",
    "Action": lambda x: "BUY" if "BUY" in x.values else (
        "EXIT" if "EXIT" in x.values else (
            "HOLD" if "HOLD" in x.values else "WAIT"
        )
    ),
    "Entry": "last",
    "PnL": "sum"
})

daily = daily[(daily.index >= start_dt) & (daily.index <= end_dt)]

# ======================
# METRICS
# ======================
net_profit = (balance - 1) * 100

c1, c2 = st.columns(2)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")

# ======================
# STYLE
# ======================
def color(x):
    return {
        "BUY": "background-color:#2ecc71;color:white",
        "EXIT": "background-color:#e74c3c;color:white",
        "HOLD": "background-color:#3498db;color:white",
        "WAIT": "background-color:#95a5a6;color:white"
    }.get(x, "")

# ======================
# TABLE
# ======================
st.dataframe(
    daily.sort_index(ascending=False)
    .style.apply(lambda col: col.map(color), subset=["Action"])
    .format({
        "Close": "{:,.1f}",
        "Entry": "{:,.1f}",
        "PnL": "{:+.2f}%"
    }),
    use_container_width=True
)
