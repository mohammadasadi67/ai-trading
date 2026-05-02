import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC WHALE PRO V14")
st.title("🐋 BTC PRO: Whale Mode (Fixed Engine)")

# ======================
# DATA (FULL HISTORY) - Fixed ValueError
# ======================
@st.cache_data(ttl=3600)
def get_data(start_str="2023-01-01"):
    url = "https://api.binance.com/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    all_data = []
    
    # برای جلوگیری از خطا، عملیات سنگین را بدون UI داخلی انجام می‌دهیم
    while True:
        params = {"symbol": "BTCUSDT", "interval": "1h", "startTime": start_ts, "limit": 1000}
        try:
            res = requests.get(url, params=params, timeout=15)
            data = res.json()
            if not data or len(data) == 0: break
            all_data.extend(data)
            start_ts = data[-1][0] + 1
            if len(data) < 1000: break
        except: break

    if not all_data:
        return pd.DataFrame()

    # تبدیل به دیتافریم بدون اجبار به تعداد ستون خاص (رفع خطای اصلی)
    df = pd.DataFrame(all_data)
    
    # ما فقط به 5 ستون اول نیاز داریم: Time, Open, High, Low, Close
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
    end_dt = st.date_input("End Date", value=date(2026,5,2))
    st.divider()
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100

# بارگذاری دیتا با مدیریت نمایش
with st.spinner("در حال دریافت دیتای کامل (ممکن است چند ثانیه طول بکشد)..."):
    df_raw = get_data("2023-01-01")

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
    # ENGINE (WHALE MODE)
    # ======================
    df["Action"] = "WAIT"
    df["PnL"] = 0.0
    balance = 1.0
    in_pos = False
    entry = sl = highest = 0

    for i in range(200, len(df)):
        t = df.index[i]
        if not (start_dt <= t.date() <= end_dt): continue

        c, h, l = df["Close"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i]
        rsi, ma50, ma200, atr = df["RSI"].iloc[i], df["MA50"].iloc[i], df["MA200"].iloc[i], df["ATR"].iloc[i]

        if not in_pos:
            if c > ma50 > ma200 and 52 < rsi < 65:
                entry, highest = c, c
                sl = entry - (atr * 3.0) 
                in_pos = True
                df.iloc[i, df.columns.get_loc("Action")] = "BUY"
        else:
            df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
            highest = max(highest, h)

            if highest > entry * 1.03: sl = max(sl, entry)
            if highest > entry * 1.10: sl = max(sl, highest * 0.94)

            exit_p = 0
            if l <= sl: exit_p = sl
            elif c < ma50 and rsi < 45: exit_p = c

            if exit_p > 0:
                pnl = ((exit_p - entry) / entry) - (fee * 2)
                balance *= (1 + pnl)
                df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
                df.iloc[i, df.columns.get_loc("PnL")] = pnl * 100
                in_pos = False

    # ======================
    # RESULTS
    # ======================
    df_display = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()
    df_display["Date"] = df_display.index.date

    daily = df_display.groupby("Date").agg({
        "Close": "last",
        "Action": lambda x: "BUY" if "BUY" in x.values else ("EXIT" if "EXIT" in x.values else ("HOLD" if "HOLD" in x.values else "WAIT")),
        "PnL": "sum"
    })

    net_prof = (balance - 1) * 100
    st.columns(2)[0].metric("Net Profit %", f"{net_prof:.2f}%")
    st.columns(2)[1].metric("Final Balance", f"${capital * balance:,.2f}")

    def color_act(val):
        colors = {"BUY": "#2ecc71", "EXIT": "#e74c3c", "HOLD": "#3498db"}
        return f"background-color: {colors.get(val, '#95a5a6')}; color: white; font-weight: bold"

    st.dataframe(
        daily.sort_index(ascending=False)
        .style.map(color_act, subset=["Action"])
        .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
        use_container_width=True
    )
else:
    st.error("دیتا دریافت نشد. اینترنت را چک کنید.")
