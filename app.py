import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("💰 BTC ULTRA-STRATEGY (V5.0 - PRO ENTRY)")

# ======================
# ROBUST DATA FETCHING
# ======================
def get_raw_data(symbol="BTCUSDT", interval="4h", limit=1500):
    # لیست آدرس‌های جایگزین بایننس برای دور زدن محدودیت‌ها
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://api1.binance.com/api/v3/klines",
        "https://api2.binance.com/api/v3/klines",
        "https://api3.binance.com/api/v3/klines"
    ]
    
    for url in endpoints:
        try:
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
        except:
            continue
    return None

def get_data():
    data = get_raw_data()
    if data:
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ig"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close","volume"]]
        df.columns = ["Time","Open","High","Low","Close","Volume"]
        df.set_index("Time", inplace=True)
        return df.astype(float)
    return pd.DataFrame()

# ======================
# CONFIG & INPUTS
# ======================
with st.sidebar:
    st.header("Settings")
    capital = st.number_input("Capital", value=1000.0)
    fee_pct = st.slider("Fee (%)", 0.0, 0.5, 0.04)
    fee = fee_pct / 100
    start_date = st.date_input("Start Date", value=date(2023, 1, 1))

df = get_data()

if df.empty:
    st.error("❌ Connection Error: Binance API is not responding. Please check your network.")
    st.stop()

# فیلتر تاریخ
df = df[df.index.date >= start_date].copy()

# ======================
# SMART INDICATORS
# ======================
df["MA20"] = df["Close"].rolling(20).mean()
df["MA50"] = df["Close"].rolling(50).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# RSI
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# PRO BACKTEST ENGINE
# ======================
df["Signal"] = "WAIT"
df["Confidence"] = 0
df["Entry"] = 0.0
df["TP"] = 0.0
df["SL"] = 0.0
df["PnL_Trade"] = 0.0

balance = 1.0
trades = wins = losses = 0
in_pos = False
e_price = sl_price = tp_price = 0

for i in range(50, len(df)):
    c_price = df["Close"].iloc[i]
    h_price = df["High"].iloc[i]
    l_price = df["Low"].iloc[i]
    rsi = df["RSI"].iloc[i]
    atr = df["ATR"].iloc[i]
    ma20 = df["MA20"].iloc[i]
    ma50 = df["MA50"].iloc[i]

    if not in_pos:
        # ورود: بریک‌اوت + تایید RSI + تایید روند
        if c_price > df["High"].iloc[i-10:i].max() and rsi > 50:
            # محاسبه Confidence هوشمند
            conf_score = 0
            if rsi > 55: conf_score += 40
            if ma20 > ma50: conf_score += 30
            if c_price > ma20: conf_score += 30
            
            if conf_score >= 60:
                e_price = c_price
                sl_price = e_price - (atr * 1.8)
                tp_price = e_price + (atr * 3.2)
                in_pos = True
                
                df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
                df.iloc[i, df.columns.get_loc("Confidence")] = conf_score
                df.iloc[i, df.columns.get_loc("Entry")] = e_price
                df.iloc[i, df.columns.get_loc("SL")] = sl_price
                df.iloc[i, df.columns.get_loc("TP")] = tp_price
    else:
        # مدیریت خروج
        exit_val = 0
        if h_price >= tp_price: exit_val = tp_price
        elif l_price <= sl_price: exit_val = sl_price
        elif rsi < 45: exit_val = c_price # خروج اضطراری

        if exit_val > 0:
            raw_ret = (exit_val - e_price) / e_price
            net_ret = (1 + raw_ret) * (1 - fee)**2 - 1
            
            balance *= (1 + net_ret)
            trades += 1
            if net_ret > 0: wins += 1
            else: losses += 1
            
            df.iloc[i, df.columns.get_loc("PnL_Trade")] = net_ret * 100
            in_pos = False

# ======================
# FINAL DASHBOARD
# ======================
winrate = (wins / trades * 100) if trades else 0
net_profit = (balance - 1) * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Trades", trades)
c2.metric("Winrate", f"{winrate:.1f}%")
c3.metric("Net Profit %", f"{net_profit:.2f}%")
c4.metric("Final Balance", f"${capital * balance:,.2f}")

st.divider()

# نمایش دقیق لاگ معاملات
report = df[(df["Signal"] == "BUY") | (df["PnL_Trade"] != 0)].copy()
if not report.empty:
    # فرمت‌دهی برای نمایش زیباتر
    st.subheader("📝 Professional Trade Log")
    display_df = report[["Signal", "Confidence", "Entry", "TP", "SL", "PnL_Trade"]].sort_index(ascending=False)
    st.dataframe(display_df.style.format({
        "Entry": "{:,.2f}",
        "TP": "{:,.2f}",
        "SL": "{:,.2f}",
        "PnL_Trade": "{:+.2f}%",
        "Confidence": "{}%"
    }), use_container_width=True)
else:
    st.info("No trades found for the selected period. Try lowering the Confidence filter in code or changing the Start Date.")
