import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("💰 BTC PROFIT MAXIMIZER (V7.0)")

# ======================
# DATA (با متد درخواستی شما)
# ======================
@st.cache_data(ttl=600)
def get_data(limit=1000):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": limit}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if not isinstance(data, list):
            st.error("API Error")
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ig"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except Exception as e:
        st.error(f"Data Error: {e}")
        return pd.DataFrame()

# ======================
# INPUTS
# ======================
capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.04) / 100
start_date = st.sidebar.date_input("Start Date", value=date(2023, 1, 1))

df = get_data(limit=1500)
if df.empty: st.stop()
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS (بهینه شده برای دقت ورود)
# ======================
df["MA20"] = df["Close"].rolling(20).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
df["DonHigh"] = df["High"].rolling(12).max().shift(1)

# RSI برای فیلتر ورود
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE (اصلاح منطق TP/SL)
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
entry_p = sl_p = tp_p = 0
highest_p = 0

for i in range(50, len(df)):
    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]
    rsi = df["RSI"].iloc[i]
    atr = df["ATR"].iloc[i]
    don_h = df["DonHigh"].iloc[i]

    if not in_pos:
        # ورود با تاییدیه قوی‌تر
        if c > don_h and rsi > 52 and rsi < 70:
            conf = int(np.clip((rsi-50)*5 + 50, 0, 100))
            entry_p = c
            # حد ضرر و سود داینامیک بر اساس نوسان (ATR)
            sl_p = entry_p - (atr * 1.5)
            tp_p = entry_p + (atr * 2.0) # تارگت نزدیک‌تر برای نقد کردن سود
            
            highest_p = entry_p
            in_pos = True
            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
            df.iloc[i, df.columns.get_loc("Confidence")] = conf
            df.iloc[i, df.columns.get_loc("Entry")] = entry_p
            df.iloc[i, df.columns.get_loc("SL")] = sl_p
            df.iloc[i, df.columns.get_loc("TP")] = tp_p

    else:
        # مدیریت هوشمند پوزیشن
        highest_p = max(highest_p, h)
        exit_v = 0
        
        # ۱. اگر قیمت نصف راه تارگت را رفت، استاپ را به نقطه ورود بیار (ریسک فری)
        if highest_p > entry_p + (tp_p - entry_p) * 0.5:
            sl_p = max(sl_p, entry_p + (entry_p * 0.002)) # ورود + کارمزد
        
        # ۲. بررسی خروج
        if h >= tp_p: exit_v = tp_p # سود زده شد
        elif l <= sl_p: exit_v = sl_p # ضرر زده شد
        elif rsi < 45: exit_v = c # خروج اضطراری در ضعف روند

        if exit_v > 0:
            net_r = ((exit_v - entry_p) / entry_p) - (fee * 2)
            balance *= (1 + net_r)
            trades += 1
            if net_r > 0: wins += 1
            else: losses += 1
            df.iloc[i, df.columns.get_loc("PnL_Trade")] = net_r * 100
            in_pos = False

# ======================
# DISPLAY
# ======================
winrate = (wins / trades * 100) if trades else 0
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Trades", trades)
c2.metric("Winrate", f"{winrate:.1f}%")
c3.metric("Net Profit %", f"{(balance-1)*100:.2f}%")
c4.metric("Final Balance", f"${capital * balance:,.2f}")

st.divider()
report = df[(df["Signal"] == "BUY") | (df["PnL_Trade"] != 0)].copy()
st.subheader("📊 Professional Trade Log")
st.dataframe(report[["Signal", "Confidence", "Entry", "TP", "SL", "PnL_Trade"]].sort_index(ascending=False), use_container_width=True)
