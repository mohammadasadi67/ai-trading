import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

st.set_page_config(layout="wide", page_title="Professional Trading Dashboard")
st.title("mohammad pattern - REAL ENTRY MODE")

# ======================
# DATA
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 500}
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
# SUPPORT / RESISTANCE
# ======================
def get_sr_levels(df):
    highs = df["High"].rolling(50).max()
    lows = df["Low"].rolling(50).min()
    return lows.iloc[-1], highs.iloc[-1]

# ======================
# INPUTS
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

    df["Signal"] = "WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["StopLoss"] = np.nan
    df["Confidence"] = 0.0
    df["PnL_Percent"] = np.nan

    balance = 1.0
    trades = 0
    wins = 0
    losses = 0
    total_profit = 0
    total_loss = 0

    max_hold = 12
    scale_trigger = 0.004

    ma = df["Close"].rolling(20).mean()

    for i in range(20, len(df)-max_hold):

        p1 = df.iloc[i-1]
        p2 = df.iloc[i-2]

        move = abs((p1["Close"] - p2["Close"]) / p2["Close"])

        if move < 0.0008:
            continue

        if df["Close"].iloc[i-1] < ma.iloc[i-1]:
            continue

        entry = df["Open"].iloc[i]
        sl = p1["Low"]
        tp = entry + (move * entry * 1.4)

        # ======================
        # ✅ ENTRY FILTER (>=1%)
        # ======================
        predicted_profit = (tp - entry) / entry
        if predicted_profit < 0.01:
            continue

        avg_entry = entry
        scaled = False
        exit_price = entry

        for j in range(1, max_hold+1):

            high = df["High"].iloc[i+j]
            low = df["Low"].iloc[i+j]

            # SCALE IN
            if (not scaled) and (low < entry * (1 - scale_trigger)):
                add_price = entry * (1 - scale_trigger)
                avg_entry = (avg_entry + add_price) / 2
                scaled = True

            if low <= sl:
                exit_price = sl
                break

            if high >= tp:
                exit_price = tp
                break

            exit_price = df["Close"].iloc[i+j]

        raw = (exit_price - avg_entry) / avg_entry
        net = (1 + raw) * (1 - fee_rate)**2 - 1

        # ======================
        # ✅ REAL RECORD (NO FILTER)
        # ======================
        trades += 1
        balance *= (1 + net)

        if net > 0:
            wins += 1
            total_profit += net
        else:
            losses += 1
            total_loss += abs(net)

        df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
        df.iloc[i, df.columns.get_loc("Entry")] = avg_entry
        df.iloc[i, df.columns.get_loc("Target")] = tp
        df.iloc[i, df.columns.get_loc("StopLoss")] = sl
        df.iloc[i, df.columns.get_loc("PnL_Percent")] = net * 100

        # CONFIDENCE
        rr = (tp - avg_entry) / max((avg_entry - sl), 1e-6)
        conf = (move * 50 + rr) / 2
        conf = conf / (1 + conf)

        df.iloc[i, df.columns.get_loc("Confidence")] = max(0, min(conf, 1))

    # ======================
    # METRICS
    # ======================
    price = df["Close"].iloc[-1]
    support, resistance = get_sr_levels(df)

    final_balance = initial_capital * balance
    winrate = (wins / trades * 100) if trades else 0
    net_profit_percent = (balance - 1) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("BTC Price", f"${price:,.2f}")
    c2.metric("Support", f"${support:,.2f}")
    c3.metric("Resistance", f"${resistance:,.2f}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trades", trades)
    m2.metric("Winrate", f"{winrate:.2f}%")
    m3.metric("Wins / Losses", f"{wins} / {losses}")
    m4.metric("Net Profit %", f"{net_profit_percent:.2f}%")

    m5, m6, m7 = st.columns(3)
    m5.metric("Total Profit %", f"{total_profit*100:.2f}%")
    m6.metric("Total Loss %", f"{total_loss*100:.2f}%")
    m7.metric("Balance", f"${final_balance:,.2f}")

    st.divider()

    st.subheader("All Trades (Real Results)")
    st.dataframe(df.sort_index(ascending=False), use_container_width=True, height=600)

# AUTO REFRESH
st.markdown(
    "<script>setTimeout(()=>window.location.reload(),20000)</script>",
    unsafe_allow_html=True
)
