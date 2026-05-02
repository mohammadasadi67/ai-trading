import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC BACKTEST PRO")
st.title("🧪 BTC BACKTEST (REAL RANGE ENGINE)")

# ======================
# DATA (FULL HISTORY)
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

        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if not data:
            break

        all_data.extend(data)

        last_time = data[-1][0]
        start_ts = last_time + 1

        if len(data) < 1000:
            break

    df = pd.DataFrame(all_data, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close"]]
    df.columns = ["Time","Open","High","Low","Close"]
    df.set_index("Time", inplace=True)

    return df.astype(float)

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("📅 Backtest Range")
    start_dt = st.date_input("From", value=date(2023,1,1))
    end_dt = st.date_input("To", value=date.today())

    st.divider()
    st.header("💰 Capital")
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100

# ======================
# LOAD DATA
# ======================
df_raw = get_data("2023-01-01")

# ======================
# INDICATORS
# ======================
df = df_raw.copy()

df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# RSI
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE
# ======================
df["Action"] = "WAIT"
df["PnL"] = 0.0

balance = 1.0
in_pos = False
entry = sl = highest = 0

for i in range(200, len(df)):

    t = df.index[i]
    if not (start_dt <= t.date() <= end_dt):
        continue

    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]

    rsi = df["RSI"].iloc[i]
    ma50 = df["MA50"].iloc[i]
    ma200 = df["MA200"].iloc[i]
    atr = df["ATR"].iloc[i]

    # ENTRY
    if not in_pos:
        if c > ma50 > ma200 and 55 < rsi < 68:
            entry = c
            sl = entry - (atr * 1.2)
            highest = entry
            in_pos = True
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"

    # HOLD
    else:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"

        if h > highest:
            highest = h

        # 🔥 Risk Free
        if highest > entry * 1.02:
            sl = max(sl, entry)

        # 🔥 Profit Lock
        if highest > entry * 1.04:
            sl = max(sl, highest * 0.96)

        exit_price = 0

        if l <= sl:
            exit_price = sl

        # EXIT
        if exit_price > 0:
            pnl = ((exit_price - entry) / entry) - (fee * 2)
            balance *= (1 + pnl)

            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL")] = pnl * 100

            in_pos = False

# ======================
# FILTER DISPLAY RANGE
# ======================
df_display = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()

df_display["Date"] = df_display.index.date

daily = df_display.groupby("Date").agg({
    "Close": "last",
    "Action": lambda x: "BUY" if "BUY" in x.values else ("EXIT" if "EXIT" in x.values else ("HOLD" if "HOLD" in x.values else "WAIT")),
    "PnL": "sum"
})

# ======================
# METRICS
# ======================
net_profit = (balance - 1) * 100

c1, c2 = st.columns(2)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")

# ======================
# TABLE
# ======================
st.divider()
st.subheader(f"📊 Trades from {start_dt} to {end_dt}")

def color(x):
    colors = {
        "BUY": "#2ecc71",
        "EXIT": "#e74c3c",
        "HOLD": "#3498db",
        "WAIT": "#95a5a6"
    }
    return f"background-color:{colors.get(x,'white')};color:white"

st.dataframe(
    daily.sort_index(ascending=False)
    .style.map(color, subset=["Action"])
    .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
    use_container_width=True,
    height=600
)
