import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC SUPER WHALE PRO V21")
st.title("🐋 BTC PRO: Whale Mode (Stable + Real Data)")

# ======================
# DATA ENGINE (MULTI SOURCE + LOOP)
# ======================
@st.cache_data(ttl=600)
def get_data(start_str="2023-01-01"):

    endpoints = [
        "https://data-api.binance.vision/api/v3/klines",
        "https://api1.binance.com/api/v3/klines",
        "https://api2.binance.com/api/v3/klines"
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

    st.divider()
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
# FILTER RANGE
# ======================
df_bt = df[
    (df.index.date >= start_dt) &
    (df.index.date <= end_dt)
].copy()

# ======================
# ENGINE (REAL WHALE LOGIC)
# ======================
df_bt["Action"] = "WAIT"
df_bt["PnL"] = 0.0

balance = 1.0
in_pos = False
entry = sl = highest = 0

for i in range(len(df_bt)):

    c = df_bt["Close"].iloc[i]
    h = df_bt["High"].iloc[i]
    l = df_bt["Low"].iloc[i]

    ma200 = df_bt["MA200"].iloc[i]
    h48 = df_bt["H_48"].iloc[i]
    l48 = df_bt["L_48"].iloc[i]

    idx = df_bt.index[i]

    # ======================
    # ENTRY
    # ======================
    if not in_pos:
        if c > h48 and c > ma200:

            entry = c
            sl = l48
            highest = entry
            in_pos = True

            df_bt.at[idx, "Action"] = "BUY"

    # ======================
    # HOLD
    # ======================
    else:
        df_bt.at[idx, "Action"] = "HOLD"

        if h > highest:
            highest = h

        # trailing واقعی
        sl = max(sl, l48)

        exit_price = 0

        if l <= sl:
            exit_price = sl

        # ======================
        # EXIT
        # ======================
        if exit_price > 0:

            pnl = ((exit_price - entry) / entry) - (fee * 2)
            balance *= (1 + pnl)

            df_bt.at[idx, "Action"] = "EXIT"
            df_bt.at[idx, "PnL"] = pnl * 100

            in_pos = False

# ======================
# RESULTS
# ======================
net_profit = (balance - 1) * 100
trades = len(df_bt[df_bt["Action"] == "EXIT"])

c1, c2, c3 = st.columns(3)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")
c3.metric("Trades", trades)

# ======================
# TABLE
# ======================
st.divider()

def style(x):
    colors = {
        "BUY": "#2ecc71",
        "EXIT": "#e74c3c",
        "HOLD": "#3498db",
        "WAIT": "#95a5a6"
    }
    return f"background-color:{colors.get(x,'white')};color:white"

st.dataframe(
    df_bt[df_bt["Action"] != "WAIT"]
    .sort_index(ascending=False)
    .style.map(style, subset=["Action"])
    .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
    use_container_width=True
)
