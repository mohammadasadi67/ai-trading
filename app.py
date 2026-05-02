import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC LONG-TERM BACKTEST")
st.title("🧪 BTC BACKTEST: Long-Term vs Short-Term")

# ======================
# DATA FETCHING (Dynamic Interval)
# ======================
@st.cache_data(ttl=3600)
def get_data(symbol="BTCUSDT", interval="1d", limit=1500):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        df = pd.DataFrame(data, columns=["time","open","high","low","close","volume","ct","qav","trades","tb","tq","ig"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except:
        return pd.DataFrame()

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("🗓️ تنظیمات بازه")
    # انتخاب تایم‌فریم برای حل مشکل محدودیت تعداد کندل
    time_mode = st.radio("تایم‌فریم تحلیل:", 
                         ["روزانه (برای بک‌تست طولانی از 2023)", 
                          "یک ساعته (فقط 2 ماه اخیر)"])
    
    interval = "1d" if "روزانه" in time_mode else "1h"
    
    start_dt = st.date_input("از تاریخ", value=date(2023, 1, 1))
    end_dt = st.date_input("تا تاریخ", value=date(2026, 5, 2))
    
    st.divider()
    capital = st.number_input("سرمایه اولیه ($)", value=1000.0)
    fee = st.slider("کارمزد (%)", 0.0, 0.5, 0.05) / 100

# دریافت دیتا (اگر روزانه باشد 1500 کندل یعنی حدود 4 سال دیتا)
df_raw = get_data(interval=interval)

if not df_raw.empty:
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
    # ENGINE (PRO TREND)
    # ======================
    df["Action"] = "WAIT"
    df["PnL_Trade"] = 0.0
    balance = 1.0
    in_pos = False
    entry_val = sl_val = highest = 0

    for i in range(50, len(df)):
        curr_dt = df.index[i].date()
        if not (start_dt <= curr_dt <= end_dt):
            continue

        c, h, l = df["Close"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i]
        rsi, ma50, ma200, atr = df["RSI"].iloc[i], df["MA50"].iloc[i], df["MA200"].iloc[i], df["ATR"].iloc[i]

        if not in_pos:
            if c > ma50 > ma200 and 55 < rsi < 70:
                in_pos, entry_val = True, c
                sl_val = entry_val - (atr * 1.5)
                highest = entry_val
                df.iloc[i, df.columns.get_loc("Action")] = "BUY"
        else:
            df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
            highest = max(highest, h)
            if highest > entry_val * 1.03:
                sl_val = max(sl_val, highest * 0.96)
            
            if l <= sl_val:
                pnl = ((sl_val - entry_val) / entry_val) - (fee * 2)
                balance *= (1 + pnl)
                df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
                df.iloc[i, df.columns.get_loc("PnL_Trade")] = pnl * 100
                in_pos = False

    # ======================
    # DISPLAY
    # ======================
    df_final = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()
    
    col1, col2 = st.columns(2)
    col1.metric("Net Profit %", f"{(balance-1)*100:.2f}%")
    col2.metric("Final Balance", f"${capital * balance:,.2f}")

    st.subheader(f"📊 گزارش معاملات ({interval})")
    
    def style_act(val):
        color = {'BUY': '#2ecc71', 'EXIT': '#e74c3c', 'HOLD': '#3498db'}.get(val, '#95a5a6')
        return f'background-color: {color}; color: white; font-weight: bold'

    # اگر تایم‌فریم روزانه است، تجمیع نمی‌خواهیم، مستقیم نشان می‌دهیم
    st.dataframe(
        df_final[["Close", "Action", "PnL_Trade"]].sort_index(ascending=False)
        .style.map(style_act, subset=['Action'])
        .format({"PnL_Trade": "{:+.2f}%", "Close": "{:,.1f}"}),
        use_container_width=True
    )
else:
    st.error("دیتا از بایننس دریافت نشد.")
