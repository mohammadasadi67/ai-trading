import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("🐋 BTC SMART WHALE (FULL DATA ENGINE)")

# ======================
# DATA (LOOP REAL)
# ======================
@st.cache_data(ttl=600)
def get_data(start_str="2023-01-01"):

    url = "https://data-api.binance.vision/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)

    all_data = []
    last_time = None

    while True:
        params = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "startTime": start_ts,
            "limit": 1000
        }

        try:
            res = requests.get(url, params=params, timeout=10)
            data = res.json()

            if not isinstance(data, list) or not data:
                break

            if last_time == data[-1][0]:
                break

            last_time = data[-1][0]

            all_data.extend(data)
            start_ts = last_time + 1

            if len(data) < 1000:
                break

        except:
            break

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data).iloc[:, :5]
    df.columns = ["Time","Open","High","Low","Close"]

    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)

# ======================
# SETTINGS
# ======================
with st.sidebar:
    start_dt = st.date_input("Start", value=date(2023,1,1))
    end_dt = st.date_input("End", value=date.today())
    capital = st.number_input("Capital", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100

# ======================
# LOAD DATA
# ======================
df = get_data("2023-01-01")

if df.empty:
    st.error("❌ Data load failed")
    st.stop()

# ======================
# INDICATORS
# ======================
df["MA200"] = df["Close"].rolling(200).mean()
df["H_24"] = df["High"].rolling(24).max().shift(1)
df["L_24"] = df["Low"].rolling(24).min().shift(1)

# ======================
# ENGINE (REAL)
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
    ma200_prev = df["MA200"].iloc[i-10]

    h24 = df["H_24"].iloc[i]
    l24 = df["L_24"].iloc[i]

    idx = df.index[i]

    # ENTRY
    if not in_pos and (start_dt <= t.date() <= end_dt):

        trend_ok = (c > ma200) and (ma200 > ma200_prev)

        if c > h24 and trend_ok:
            entry = c
            sl = entry * 0.97
            tp = entry * 1.08
            highest = entry
            in_pos = True

            df.at[idx, "Action"] = "BUY"
            df.at[idx, "Entry"] = entry

    # HOLD
    elif in_pos:

        df.at[idx, "Action"] = "HOLD"

        if h > highest:
            highest = h

        # trailing حرفه‌ای
        if highest > entry * 1.05:
            sl = max(sl, entry)

        if highest > entry * 1.15:
            sl = max(sl, highest * 0.94)

        df.at[idx, "Entry"] = entry
        df.at[idx, "SL"] = sl
        df.at[idx, "TP"] = tp

        # EXIT
        if l <= sl:
            pnl = ((sl - entry) / entry) - (fee * 2)
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
trades = len(df[df["Action"] == "EXIT"])

c1, c2, c3 = st.columns(3)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")
c3.metric("Trades", trades)

# ======================
# STYLE
# ======================
def color_action(val):
    return {
        "BUY": "background-color:#2ecc71;color:white",
        "EXIT": "background-color:#e74c3c;color:white",
        "HOLD": "background-color:#3498db;color:white",
        "WAIT": "background-color:#95a5a6;color:white"
    }.get(val, "")

# ======================
# TABLE
# ======================
st.dataframe(
    daily.sort_index(ascending=False)
    .style.apply(lambda col: col.map(color_action), subset=["Action"])
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
