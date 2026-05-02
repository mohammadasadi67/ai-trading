import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("🛡️ BTC AI-CONFIDENCE SCALPER (V3.0)")

# ======================
# DATA (Expanded for 2023)
# ======================
@st.cache_data
def get_data(symbol="BTCUSDT", interval="4h", limit=1500):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close","volume"]]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df.set_index("Time", inplace=True)
    return df.astype(float)

# ======================
# INPUTS
# ======================
capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.04) / 100
start_date = st.sidebar.date_input("Start Date", value=date(2023, 1, 1))

df_all = get_data(limit=1500) # دریافت دیتای بیشتر
df = df_all[df_all.index.date >= start_date].copy()

# ======================
# INDICATORS
# ======================
df["MA20"] = df["Close"].rolling(20).mean()
df["MA50"] = df["Close"].rolling(50).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
df["DonHigh"] = df["High"].rolling(10).max().shift(1)

# RSI
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# BACKTEST ENGINE + CONFIDENCE
# ======================
df["Signal"] = "WAIT"
df["Confidence"] = 0
df["Entry"] = np.nan
df["TP"] = np.nan
df["SL"] = np.nan
df["PnL_Trade"] = np.nan

balance = 1.0
trades_count = wins = losses = 0
in_position = False
entry_price = sl = tp = 0

for i in range(50, len(df)):
    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]
    rsi = df["RSI"].iloc[i]
    atr = df["ATR"].iloc[i]
    ma20 = df["MA20"].iloc[i]
    ma50 = df["MA50"].iloc[i]

    if not in_position:
        # شرط ورود ترکیبی
        if c > df["DonHigh"].iloc[i] and c > ma20:
            # محاسبه Confidence (0-100)
            conf = 0
            if rsi > 55 and rsi < 70: conf += 40
            if ma20 > ma50: conf += 30
            if c > ma20 * 1.01: conf += 30
            
            if conf >= 60: # فقط ورود با اطمینان بالا
                entry_price = c
                sl = entry_price - (atr * 2.1) # استاپ امن‌تر
                tp = entry_price + (atr * 3.5) # تارگت بزرگتر برای سوددهی
                in_position = True
                
                df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
                df.iloc[i, df.columns.get_loc("Confidence")] = conf
                df.iloc[i, df.columns.get_loc("Entry")] = entry_price
                df.iloc[i, df.columns.get_loc("SL")] = sl
                df.iloc[i, df.columns.get_loc("TP")] = tp

    else:
        # مدیریت خروج
        exit_p = 0
        if h >= tp: exit_p = tp
        elif l <= sl: exit_p = sl
        elif rsi < 45: exit_p = c # خروج زودهنگام در صورت ضعف

        if exit_p > 0:
            raw = (exit_p - entry_price) / entry_price
            net = (1 + raw) * (1 - fee)**2 - 1
            balance *= (1 + net)
            trades_count += 1
            if net > 0: wins += 1
            else: losses += 1
            
            df.iloc[i, df.columns.get_loc("PnL_Trade")] = net * 100
            in_position = False

# ======================
# RESULTS
# ======================
final_val = capital * balance
winrate = (wins / trades_count * 100) if trades_count else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Trades", trades_count)
c2.metric("Winrate", f"{winrate:.1f}%")
c3.metric("Net Profit %", f"{(balance-1)*100:.2f}%")
c4.metric("Final Balance", f"${final_val:,.2f}")

st.divider()
# فیلتر کردن فقط ردیف‌هایی که معامله داشته‌اند برای نمایش بهتر
trade_log = df[(df["Signal"] == "BUY") | (df["PnL_Trade"].notna())].copy()
st.subheader("📊 Trade Log with Confidence Score")
st.dataframe(trade_log[["Signal", "Confidence", "Entry", "TP", "SL", "PnL_Trade"]].sort_index(ascending=False), use_container_width=True)
