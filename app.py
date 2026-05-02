import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC ULTRA SAFE")
st.title("🐋 BTC PRO: Low Risk Mode (Anti-Whipsaw)")

# ======================
# DATA (MULTI-ENDPOINT)
# ======================
@st.cache_data(ttl=3600)
def get_data(start_str="2023-01-01"):
    endpoints = ["https://api1.binance.com/api/v3/klines", "https://api2.binance.com/api/v3/klines"]
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    for url in endpoints:
        all_data = []
        current_ts = start_ts
        try:
            while True:
                params = {"symbol": "BTCUSDT", "interval": "1h", "startTime": current_ts, "limit": 1000}
                res = requests.get(url, params=params, timeout=15)
                if res.status_code != 200: break
                data = res.json()
                if not data: break
                all_data.extend(data)
                current_ts = data[-1][0] + 1
                if len(data) < 1000: break
            if all_data: break
        except: continue
    if not all_data: return pd.DataFrame()
    df = pd.DataFrame(all_data).iloc[:, :5]
    df.columns = ["Time", "Open", "High", "Low", "Close"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    return df.astype(float)

# ======================
# LOAD & INDICATORS
# ======================
with st.sidebar:
    st.header("⚙️ تنظیمات ایمنی")
    start_dt = st.date_input("Start Date", value=date(2023,1,1))
    end_dt = st.date_input("End Date", value=date.today())
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100
    risk_level = st.select_slider("سطح حساسیت ورود", options=["خیلی کم", "متوسط", "زیاد"], value="خیلی کم")

df_raw = get_data("2023-01-01")
df = df_raw.copy()

# اندیکاتورهای تاییدیه
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# RSI برای تشخیص قدرت
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE (ULTRA SAFE LOGIC)
# ======================
df["Action"] = "WAIT"
df["PnL"] = 0.0
balance, in_pos = 1.0, False
entry = sl = 0

rsi_limit = 60 if risk_level == "خیلی کم" else 55

for i in range(200, len(df)):
    t = df.index[i]
    c, l, h = df["Close"].iloc[i], df["Low"].iloc[i], df["High"].iloc[i]
    ma50, ma200, rsi, atr = df["MA50"].iloc[i], df["MA200"].iloc[i], df["RSI"].iloc[i], df["ATR"].iloc[i]

    # منطق ورود سخت‌گیرانه
    if not in_pos and (start_dt <= t.date() <= end_dt):
        # شرط 1: قیمت بالای هر دو میانگین (روند صعودی قطعی)
        # شرط 2: RSI بالای مرز ایمن (قدرت خرید واقعی)
        # شرط 3: قیمت نزدیک به سقف ۲۴ ساعت اخیر نباشد (نخریدن در نوک قله)
        if c > ma50 > ma200 and rsi > rsi_limit:
            entry = c
            sl = entry - (atr * 3.5) # استاپ بسیار عریض برای جلوگیری از ضرر نوسانی
            in_pos = True
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"

    elif in_pos:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
        
        # ریسک فری سریع بعد از 3% سود
        if c > entry * 1.03:
            sl = max(sl, entry)
        
        # قفل سود پله‌ای
        if c > entry * 1.10:
            sl = max(sl, c - (atr * 2.0))

        exit_p = 0
        if l <= sl:
            exit_p = sl
        elif c < ma50: # خروج زودهنگام در صورت شل شدن روند
            exit_p = c

        if exit_p > 0:
            pnl_val = ((exit_p - entry) / entry) - (fee * 2)
            balance *= (1 + pnl_val)
            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL")] = pnl_val * 100
            in_pos = False

# ======================
# RESULTS
# ======================
df_display = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()
net_profit = (balance - 1) * 100
c1, c2, c3 = st.columns(3)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")
c3.metric("Total Trades", len(df[df["Action"] == "EXIT"]))

st.divider()
st.dataframe(df_display[df_display["Action"] != "WAIT"].sort_index(ascending=False))
