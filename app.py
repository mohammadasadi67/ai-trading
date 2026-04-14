import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Live Trading Panel")

# ======================
# دریافت دیتای کاملاً زنده (بدون کش سنگین)
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 100}
    try:
        data = requests.get(url, params=params).json()
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
# تایمر معکوس تا کندل بعدی
# ======================
def get_countdown():
    now = datetime.utcnow()
    # پیدا کردن ساعت بسته شدن کندل 4 ساعته بعدی (0, 4, 8, 12, 16, 20)
    next_hour = (now.hour // 4 + 1) * 4
    if next_hour >= 24:
        next_candle_time = datetime(now.year, now.month, now.day) + timedelta(days=1)
    else:
        next_candle_time = datetime(now.year, now.month, now.day, next_hour)
    
    remaining = next_candle_time - now
    return str(remaining).split(".")[0] # فرمت HH:MM:SS

# ======================
# رابط کاربری
# ======================
df = get_live_data()

if not df.empty:
    current_price = df["Close"].iloc[-1]
    
    col_t1, col_t2 = st.columns([3, 1])
    col_t1.title(f"💰 قیمت لحظه‌ای: ${current_price:,.2f}")
    col_t2.metric("⏳ زمان تا کندل بعد", get_countdown())

    # منطق سیگنال
    df["Decision"] = "WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    
    # محاسبه سیگنال برای ردیف‌های قبلی و فعلی
    for i in range(2, len(df)):
        p1 = df.iloc[i-1]
        p2 = df.iloc[i-2]
        
        if p1["Close"] > p2["Close"]:
            df.iloc[i, df.columns.get_loc("Decision")] = "TRADE"
            entry = df["Open"].iloc[i]
            df.iloc[i, df.columns.get_loc("Entry")] = entry
            df.iloc[i, df.columns.get_loc("Target")] = entry + (p1["Close"] - p2["Close"])

    # نمایش جدول (فقط 10 ردیف آخر برای سرعت بیشتر)
    st.subheader("📊 وضعیت سیگنال‌های اخیر")
    
    # معکوس کردن برای نمایش جدیدترین‌ها در بالا
    view_df = df.iloc[-10:].copy().sort_index(ascending=False)
    
    for idx, row in view_df.iterrows():
        is_live = (idx == df.index[-1])
        with st.container():
            c = st.columns([2, 1, 1, 1, 1, 1])
            
            # زمان
            c[0].write(f"📅 {idx.strftime('%m-%d %H:%M')}")
            
            # وضعیت کندل
            if is_live:
                c[1].info("LIVE 🔵")
                c[2].write(f"Price: {row['Close']:.1f}")
            else:
                c[1].write("CLOSED ⚪")
                c[2].write(f"Close: {row['Close']:.1f}")
            
            # سیگنال
            if row["Decision"] == "TRADE":
                c[3].success("🟢 TRADE")
                c[4].write(f"Target: {row['Target']:.1f}")
                # محاسبه سود لحظه‌ای برای کندل لایو
                pnl = ((row['Close'] - row['Open']) / row['Open']) * 100
                color = "green" if pnl > 0 else "red"
                c[5].markdown(f"**:{color}[{pnl:.2f}%]**")
            else:
                c[3].write("⚪ WAIT")
                c[4].write("-")
                c[5].write("-")
        st.divider()

# رفرش خودکار صفحه هر 10 ثانیه برای آپدیت قیمت
st.empty()
st.markdown("<script>setTimeout(function(){window.location.reload();}, 10000);</script>", unsafe_allow_html=True)
