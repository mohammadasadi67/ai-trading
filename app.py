import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("🛡️ BTC AI-CONFIDENCE SCALPER (V4.0)")

# ======================
# DATA
# ======================
@st.cache_data(ttl=600)
def get_data(symbol="BTCUSDT", interval="4h", limit=1500):
    try:
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
    except:
        return pd.DataFrame()

# ======================
# INPUTS
# ======================
capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.1) / 100
start_date = st.sidebar.date_input("Start Date", value=date(2023, 1, 1))

df = get_data()
if df.empty:
    st.error("دیتا دریافت نشد. فیلترشکن خود را بررسی کنید.")
    st.stop()

df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS (بهینه شده برای سیگنال دهی بیشتر)
# ======================
df["MA20"] = df["Close"].rolling(20).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
df["L-Band"] = df["MA20"] - (df["ATR"] * 1.5) # کف کانال نوسانی

# RSI
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE
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

for i in range(20, len(df)):
    c = df["Close"].iloc[i]
    low = df["Low"].iloc[i]
    high = df["High"].iloc[i]
    rsi = df["RSI"].iloc[i]
    atr = df["ATR"].iloc[i]
    l_band = df["L-Band"].iloc[i]

    if not in_position:
        # شرط ورود: قیمت به کف کانال رسیده + RSI پایین (اشباع فروش)
        if low <= l_band and rsi < 40:
            entry_price = c
            # Confidence بر اساس شدت اشباع فروش
            conf = int(np.clip((40 - rsi) * 5 + 50, 0, 100))
            
            sl = entry_price - (atr * 2.0)
            tp = entry_price + (atr * 3.0)
            in_position = True
            
            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
            df.iloc[i, df.columns.get_loc("Confidence")] = conf
            df.iloc[i, df.columns.get_loc("Entry")] = entry_price
            df.iloc[i, df.columns.get_loc("SL")] = sl
            df.iloc[i, df.columns.get_loc("TP")] = tp
    else:
        # مدیریت خروج
        exit_p = 0
        if high >= tp: exit_p = tp
        elif low <= sl: exit_p = sl
        elif rsi > 70: exit_p = c # خروج در اشباع خرید

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
# DISPLAY
# ======================
winrate = (wins / trades_count * 100) if trades_count else 0
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Trades", trades_count)
c2.metric("Winrate", f"{winrate:.1f}%")
c3.metric("Net Profit %", f"{(balance-1)*100:.2f}%")
c4.metric("Final Balance", f"${capital * balance:,.2f}")

st.divider()
# نمایش جدول فقط برای ردیف‌های معامله شده
log = df[(df["Signal"] == "BUY") | (df["PnL_Trade"].notna())].copy()
if not log.empty:
    st.subheader("📊 Trade Log")
    st.dataframe(log[["Signal", "Confidence", "Entry", "TP", "SL", "PnL_Trade"]].sort_index(ascending=False), use_container_width=True)
else:
    st.warning("در این بازه زمانی هیچ سیگنالی با پارامترهای فعلی یافت نشد.")
