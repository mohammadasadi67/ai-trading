import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

st.set_page_config(layout="wide", page_title="Professional Trading Dashboard")
st.title("🚀 REALTIME PANEL")

# ======================
# DATA
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 300}
    data = requests.get(url, params=params).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close"]]
    df.columns = ["Time","Open","High","Low","Close"]
    df.set_index("Time", inplace=True)

    return df.astype(float)

# ======================
# TIME
# ======================
def get_time_remaining():
    now = datetime.utcnow()
    next_4h = (now.hour // 4 + 1) * 4

    if next_4h >= 24:
        target = datetime(now.year, now.month, now.day) + timedelta(days=1)
    else:
        target = datetime(now.year, now.month, now.day, next_4h)

    remaining = target - now
    return remaining, str(remaining).split(".")[0]

# ======================
# SIDEBAR
# ======================
initial_capital = st.sidebar.number_input("Capital", value=1000.0)
fee_rate = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.1) / 100
start_date = st.sidebar.date_input("Start", value=date(2024,1,1))

# ======================
# LOAD
# ======================
df = get_live_data()
df = df[df.index.date >= start_date].copy()

if not df.empty:

    # ======================
    # STATUS
    # ======================
    remaining, time_left = get_time_remaining()
    df["Status"] = "CLOSED"
    df.iloc[-1, df.columns.get_loc("Status")] = "LIVE"

    # ======================
    # CANDLE TYPE + O→C
    # ======================
    df["Candle"] = np.where(df["Close"] > df["Open"], "Bullish", "Bearish")
    df["O→C"] = df["Open"].round(1).astype(str) + " → " + df["Close"].round(1).astype(str)

    # ======================
    # STRATEGY
    # ======================
    df["Signal"] = "WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["StopLoss"] = np.nan
    df["Confidence"] = 0.0
    df["PnL_Percent"] = 0.0

    balance = 1.0
    trades = 0

    for i in range(2, len(df)):

        p1 = df.iloc[i-1]
        p2 = df.iloc[i-2]

        move = (p1["Close"] - p2["Close"]) / p2["Close"]

        if move < 0.004:
            continue

        entry = df["Open"].iloc[i]
        sl = p1["Low"]
        tp = entry + (move * entry * 1.5)

        high = df["High"].iloc[i]
        low = df["Low"].iloc[i]

        exit_price = df["Close"].iloc[i]

        if low <= sl:
            exit_price = sl
        elif high >= tp:
            exit_price = tp

        raw = (exit_price - entry) / entry
        net = (1 + raw) * (1 - fee_rate)**2 - 1

        if net <= 0:
            continue

        trades += 1
        balance *= (1 + net)

        df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
        df.iloc[i, df.columns.get_loc("Entry")] = entry
        df.iloc[i, df.columns.get_loc("Target")] = tp
        df.iloc[i, df.columns.get_loc("StopLoss")] = sl
        df.iloc[i, df.columns.get_loc("PnL_Percent")] = net * 100
        df.iloc[i, df.columns.get_loc("Confidence")] = min(0.95, 0.6 + move*10)

    # ======================
    # HEADER
    # ======================
    price = df["Close"].iloc[-1]

    c1, c2 = st.columns([2,1])
    c1.metric("BTC Price", f"${price:,.2f}")
    c2.metric("Next Candle", time_left)

    final_balance = initial_capital * balance

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Balance", f"${final_balance:,.2f}")
    m2.metric("Profit", f"${final_balance-initial_capital:,.2f}", f"{(balance-1)*100:.2f}%")
    m3.metric("Trades", trades)
    m4.metric("Avg Trade", f"{((balance**(1/max(trades,1)))-1)*100:.2f}%")

    st.divider()

    # ======================
    # STYLE (رنگی)
    # ======================
    def color_candle(val):
        if val == "Bullish":
            return "color: #00ff9d; font-weight: bold;"
        else:
            return "color: #ff4d4d; font-weight: bold;"

    styled_df = df.sort_index(ascending=False).style.applymap(
        color_candle, subset=["Candle"]
    )

    # ======================
    # TABLE
    # ======================
    st.subheader("Trading Logs")

    st.dataframe(
        styled_df,
        use_container_width=True,
        height=600,
        column_config={
            "O→C": "Open → Close",
            "Candle": "Type",
            "High": st.column_config.NumberColumn("High", format="$%.1f"),
            "Low": st.column_config.NumberColumn("Low", format="$%.1f"),
            "Entry": st.column_config.NumberColumn("Entry", format="$%.1f"),
            "Target": st.column_config.NumberColumn("TP", format="$%.1f"),
            "StopLoss": st.column_config.NumberColumn("SL", format="$%.1f"),
            "PnL_Percent": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
            "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1),
        }
    )

# AUTO REFRESH
st.markdown(
    "<script>setTimeout(()=>window.location.reload(),20000)</script>",
    unsafe_allow_html=True
)
