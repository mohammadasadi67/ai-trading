import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC SUPER WHALE PRO")
st.title("🐋 BTC PRO: Super Whale Mode (REAL FINAL)")

# ======================
# DATA (MULTI-ENDPOINT SAFE)
# ======================
@st.cache_data(ttl=3600)
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

                res = requests.get(url, params=params, timeout=15)

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
                break

        except:
            continue

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df = df.iloc[:, :5]
    df.columns = ["Time", "Open", "High", "Low", "Close"]

    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)

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
with st.spinner("Loading BTC data..."):
    df_raw = get_data("2023-01-01")

if df_raw.empty:
    st.error("❌ Data load failed")
    st.stop()

# ======================
# INDICATORS
# ======================
df = df_raw.copy()

df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE (SUPER WHALE REAL)
# ======================
df["Action"] = "WAIT"
df["PnL"] = 0.0

balance = 1.0
in_pos = False
entry = sl = highest = 0

for i in range(200, len(df)):

    t = df.index[i]

    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]

    rsi = df["RSI"].iloc[i]
    ma50 = df["MA50"].iloc[i]
    ma200 = df["MA200"].iloc[i]
    atr = df["ATR"].iloc[i]

    # ======================
    # ENTRY (فقط داخل بازه)
    # ======================
    if not in_pos and (start_dt <= t.date() <= end_dt):

        if c > ma50 > ma200 and rsi > 50:

            entry = c
            sl = entry - (atr * 2.0)   # اصلاح شد
            highest = entry
            in_pos = True

            df.iloc[i, df.columns.get_loc("Action")] = "BUY"

    # ======================
    # HOLD (همیشه اجرا)
    # ======================
    elif in_pos:

        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"

        if h > highest:
            highest = h

        # 🔥 مرحله 1: risk free
        if highest > entry * 1.05:
            sl = max(sl, entry)

        # 🔥 مرحله 2: profit lock
        if highest > entry * 1.10:
            sl = max(sl, highest * 0.92)

        if highest > entry * 1.25:
            sl = max(sl, highest * 0.88)

        exit_price = 0

        # فقط SL (حذف خروج MA200)
        if l <= sl:
            exit_price = sl

        # ======================
        # EXIT
        # ======================
        if exit_price > 0:

            pnl = ((exit_price - entry) / entry) - (fee * 2)
            balance *= (1 + pnl)

            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL")] = pnl * 100

            in_pos = False

# ======================
# DISPLAY
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

col1, col2, col3 = st.columns(3)
col1.metric("Net Profit %", f"{net_profit:.2f}%")
col2.metric("Final Balance", f"${capital * balance:,.2f}")
col3.metric("Trades", len(df[df["Action"] == "EXIT"]))

# ======================
# TABLE
# ======================
st.divider()
st.subheader("📊 Trade Report")

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
