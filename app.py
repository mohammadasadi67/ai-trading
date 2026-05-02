import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("🐋 BTC SMART WHALE (FIXED VERSION)")

# ======================
# DATA
# ======================
@st.cache_data(ttl=600)
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol":"BTCUSDT","interval":"1h","limit":1500}

    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data).iloc[:, :5]

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

# ======================
# INDICATORS
# ======================
df["MA200"] = df["Close"].rolling(200).mean()

# سریع‌ترش کردیم
df["H_24"] = df["High"].rolling(24).max().shift(1)
df["L_24"] = df["Low"].rolling(24).min().shift(1)

# ======================
# ENGINE
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
    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]
    ma200 = df["MA200"].iloc[i]
    h24 = df["H_24"].iloc[i]
    l24 = df["L_24"].iloc[i]

    idx = df.index[i]

    # ======================
    # ENTRY
    # ======================
    if not in_pos and (start_dt <= t.date() <= end_dt):

        if c > h24 and c > ma200:
            entry = c
            sl = l24
            tp = entry * 1.08
            highest = entry
            in_pos = True

            df.at[idx, "Action"] = "BUY"
            df.at[idx, "Entry"] = entry

    # ======================
    # HOLD
    # ======================
    elif in_pos:

        if df.at[idx, "Action"] != "BUY":
            df.at[idx, "Action"] = "HOLD"

        if h > highest:
            highest = h

        # trailing بهتر
        sl = max(sl, l24)

        # قفل سود
        if highest > entry * 1.05:
            sl = max(sl, entry)

        if highest > entry * 1.12:
            sl = max(sl, highest * 0.95)

        df.at[idx, "Entry"] = entry
        df.at[idx, "SL"] = sl
        df.at[idx, "TP"] = tp

        # EXIT
        if l <= sl:
            pnl = (sl - entry) / entry
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
    "Action": lambda x: "BUY" if "BUY" in x.values else (
        "EXIT" if "EXIT" in x.values else (
            "HOLD" if "HOLD" in x.values else "WAIT"
        )
    ),
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

c1, c2 = st.columns(2)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")

# ======================
# COLOR STYLE
# ======================
def color_action(val):
    colors = {
        "BUY": "background-color: #2ecc71; color:white",
        "SELL": "background-color: #e74c3c; color:white",
        "EXIT": "background-color: #e74c3c; color:white",
        "HOLD": "background-color: #3498db; color:white",
        "WAIT": "background-color: #95a5a6; color:white"
    }
    return colors.get(val, "")

# ======================
# TABLE
# ======================
st.dataframe(
    daily.sort_index(ascending=False)
    .style.applymap(color_action, subset=["Action"])
    .format({
        "Close": "{:,.1f}",
        "Entry": "{:,.1f}",
        "SL": "{:,.1f}",
        "TP": "{:,.1f}",
        "PnL": "{:+.2f}%"
    }),
    use_container_width=True,
    height=600
)
