import streamlit as st
import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, date

st.set_page_config(layout="wide")
st.title("💰 BTC PRO-TRADER (V6.0 - CCXT ENGINE)")

# ======================
# DATA FETCHING (Using CCXT)
# ======================
@st.cache_data(ttl=600)
def get_data(symbol="BTC/USDT", timeframe="4h", limit=1000):
    try:
        # استفاده از CCXT برای پایداری ۱۰۰٪
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        # دریافت اوپن-های-لو-کلوز
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Time'] = pd.to_datetime(df['Time'], unit='ms')
        df.set_index('Time', inplace=True)
        return df.astype(float)
    except Exception as e:
        st.error(f"خطای دیتای صرافی: {e}")
        return pd.DataFrame()

# ======================
# SETTINGS
# ======================
with st.sidebar:
    st.header("تنظیمات استراتژی")
    capital = st.number_input("سرمایه (Capital)", value=1000.0)
    fee_pct = st.slider("کارمزد (Fee %)", 0.0, 0.5, 0.04)
    fee = fee_pct / 100
    start_date = st.sidebar.date_input("تاریخ شروع", value=date(2023, 1, 1))

df = get_data()

if df.empty:
    st.warning("⚠️ دیتایی دریافت نشد. در حال تلاش مجدد با متد جایگزین...")
    st.stop()

# فیلتر تاریخ
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS (بهینه شده برای سود مرکب)
# ======================
df["MA25"] = df["Close"].rolling(25).mean()
df["MA50"] = df["Close"].rolling(50).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# RSI
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# SYSTEM (ENTRY, TP, SL, CONFIDENCE)
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
e_p = sl_p = tp_p = 0

for i in range(50, len(df)):
    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]
    rsi = df["RSI"].iloc[i]
    atr = df["ATR"].iloc[i]
    ma25 = df["MA25"].iloc[i]

    if not in_pos:
        # استراتژی: شکست سقف کانال + تایید RSI + فیلتر MA
        if c > df["High"].iloc[i-10:i].max() and rsi > 52:
            # محاسبه Confidence (0-100)
            conf = 0
            if rsi > 58: conf += 40
            if c > ma25: conf += 30
            if df["Volume"].iloc[i] > df["Volume"].iloc[i-1]: conf += 30
            
            if conf >= 50: # آستانه ورود
                e_p = c
                sl_p = e_p - (atr * 1.6)
                tp_p = e_p + (atr * 2.8) # RR = 1.75
                in_pos = True
                
                df.iloc[i, df.columns.get_loc("Signal")] = "BUY"
                df.iloc[i, df.columns.get_loc("Confidence")] = conf
                df.iloc[i, df.columns.get_loc("Entry")] = e_p
                df.iloc[i, df.columns.get_loc("SL")] = sl_p
                df.iloc[i, df.columns.get_loc("TP")] = tp_p
    else:
        # مدیریت خروج
        exit_val = 0
        if h >= tp_p: exit_val = tp_p
        elif l <= sl_p: exit_val = sl_p
        elif rsi < 42: exit_val = c # خروج با ضعف مومنتوم

        if exit_val > 0:
            net_ret = ((exit_val - e_p) / e_p) - (fee * 2)
            balance *= (1 + net_ret)
            trades += 1
            if net_ret > 0: wins += 1
            else: losses += 1
            df.iloc[i, df.columns.get_loc("PnL_Trade")] = net_ret * 100
            in_pos = False

# ======================
# UI & METRICS
# ======================
winrate = (wins / trades * 100) if trades else 0
net_profit = (balance - 1) * 100

m1, m2, m3, m4 = st.columns(4)
m1.metric("تعداد معاملات", trades)
m2.metric("وین‌ریت", f"{winrate:.1f}%")
m3.metric("سود خالص کل", f"{net_profit:.2f}%")
m4.metric("موجودی نهایی", f"${capital * balance:,.2f}")

st.divider()

# نمایش جدول معاملات
report = df[(df["Signal"] == "BUY") | (df["PnL_Trade"] != 0)].copy()
if not report.empty:
    st.subheader("📋 لیست معاملات با جزئیات کامل")
    st.dataframe(report[["Signal", "Confidence", "Entry", "TP", "SL", "PnL_Trade"]].sort_index(ascending=False).style.format({
        "Entry": "{:,.1f}", "TP": "{:,.1f}", "SL": "{:,.1f}", 
        "PnL_Trade": "{:+.2f}%", "Confidence": "{}%"
    }), use_container_width=True)
else:
    st.info("معامله‌ای یافت نشد. بازه زمانی یا تنظیمات را تغییر دهید.")
