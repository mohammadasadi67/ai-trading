import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Advanced Trading Panel")

# ======================
# دریافت داده‌های زنده
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 50}
    try:
        data = requests.get(url, params=params, timeout=5).json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "close_time","qav","trades","tbbav","tbqav","ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        df = df.astype(float)
        return df
    except:
        return pd.DataFrame()

# ======================
# منطق محاسبات (Entry, Target, StopLoss)
# ======================
df = get_live_data()

if not df.empty:
    df["Signal"] = "⚪ WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["StopLoss"] = np.nan
    df["Status"] = "Closed"

    for i in range(2, len(df)):
        p1, p2 = df.iloc[i-1], df.iloc[i-2]
        
        # شرط ورود شما
        if p1["Close"] > p2["Close"]:
            entry = df["Open"].iloc[i]
            diff = p1["Close"] - p2["Close"]
            
            df.iloc[i, df.columns.get_loc("Signal")] = "🟢 BUY"
            df.iloc[i, df.columns.get_loc("Entry")] = entry
            df.iloc[i, df.columns.get_loc("Target")] = entry + diff
            
            # تعیین حد ضرر: (کمترین قیمت کندل قبلی یا 1 درصد پایین‌تر از ورود)
            # اینجا برای امنیت بیشتر، کفِ کندل قبلی را به عنوان استاپ در نظر می‌گیریم
            df.iloc[i, df.columns.get_loc("StopLoss")] = min(p1["Low"], entry * 0.99)

    # تعیین وضعیت لایو برای آخرین ردیف
    df.iloc[-1, df.columns.get_loc("Status")] = "⚡ LIVE"

    # ======================
    # نمایش UI
    # ======================
    current_p = df["Close"].iloc[-1]
    
    # هدر اصلی
    st.markdown(f"<h1 style='text-align: center; color: #ffca28;'>BTC Live: ${current_p:,.2f}</h1>", unsafe_allow_html=True)
    
    st.divider()

    # مرتب‌سازی برای نمایش (جدیدترین در بالا)
    view_df = df.sort_index(ascending=False).head(15)

    # استایل‌دهی و نمایش جدول مرتب
    def color_signal(val):
        color = '#2e7d32' if 'BUY' in val else '#757575'
        return f'color: {color}; font-weight: bold'

    st.subheader("📋 لیست سیگنال‌ها و سطوح قیمتی")
    
    # استفاده از dataframe برای نمایش مرتب‌تر
    styled_df = view_df.style.applymap(color_signal, subset=['Signal'])\
        .format({
            "Open": "{:,.1f}", "High": "{:,.1f}", "Low": "{:,.1f}", 
            "Close": "{:,.1f}", "Entry": "{:,.1f}", "Target": "{:,.1f}", "StopLoss": "{:,.1f}"
        })\
        .highlight_null(null_color="transparent")

    st.dataframe(styled_df, use_container_width=True, height=500)

    # نمایش کارت‌های سریع برای آخرین سیگنال
    last_signal = df[df["Signal"] == "🟢 BUY"].iloc[-1]
    
    st.success(f"📌 آخرین سیگنال صادر شده در: {last_signal.name.strftime('%H:%M')}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Entry Price (ورود)", f"${last_signal['Entry']:,.1f}")
    c2.metric("Target (هدف)", f"${last_signal['Target']:,.1f}", delta=f"{last_signal['Target']-last_signal['Entry']:.1f}")
    c3.metric("Stop Loss (حد ضرر)", f"${last_signal['StopLoss']:,.1f}", delta=f"{last_signal['StopLoss']-last_signal['Entry']:.1f}", delta_color="inverse")

# رفرش خودکار
st.markdown("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", unsafe_allow_html=True)
