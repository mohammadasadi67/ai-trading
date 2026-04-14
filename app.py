import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# تنظیمات اصلی صفحه
st.set_page_config(layout="wide", page_title="پنل معامله‌گری هوشمند")

# ======================
# دریافت داده‌های زنده از بایننس
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 50}
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
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
    except Exception as e:
        st.error(f"خطا در اتصال: {e}")
        return pd.DataFrame()

# ======================
# پردازش داده‌ها
# ======================
df = get_live_data()

if not df.empty:
    # تعریف ستون‌های مورد نیاز
    df["Signal"] = "⚪ WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["StopLoss"] = np.nan

    # محاسبه سیگنال‌ها بر اساس استراتژی شما
    for i in range(2, len(df)):
        p1 = df.iloc[i-1]
        p2 = df.iloc[i-2]
        
        # شرط ورود: کلوز قبلی بالاتر از کلوز ماقبل قبلی
        if p1["Close"] > p2["Close"]:
            entry_price = df["Open"].iloc[i]
            diff = p1["Close"] - p2["Close"]
            
            df.iloc[i, df.columns.get_loc("Signal")] = "🟢 BUY"
            df.iloc[i, df.columns.get_loc("Entry")] = entry_price
            df.iloc[i, df.columns.get_loc("Target")] = entry_price + diff
            # حد ضرر: کف کندل قبلی
            df.iloc[i, df.columns.get_loc("StopLoss")] = p1["Low"]

    # ======================
    # طراحی رابط کاربری (UI)
    # ======================
    current_p = df["Close"].iloc[-1]
    
    # نمایش قیمت لحظه‌ای در بالا
    st.markdown(f"""
        <div style="text-align: center; background-color: #1e1e1e; padding: 20px; border-radius: 10px; border: 1px solid #ffca28;">
            <h1 style="margin: 0; color: #ffca28;">BTCUSDT Live</h1>
            <h2 style="margin: 0; color: white;">${current_p:,.2f}</h2>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("") # فاصله

    # بخش کارت‌های آخرین سیگنال
    trade_signals = df[df["Signal"] == "🟢 BUY"]
    if not trade_signals.empty:
        last_s = trade_signals.iloc[-1]
        
        st.subheader("🎯 آخرین سیگنال فعال")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.info(f"**Entry (قیمت ورود)**\n\n${last_s['Entry']:,.1f}")
        with c2:
            st.success(f"**Target (حد سود)**\n\n${last_s['Target']:,.1f}")
        with c3:
            st.error(f"**Stop Loss (حد ضرر)**\n\n${last_s['StopLoss']:,.1f}")
            
    st.divider()

    # جدول تاریخچه سیگنال‌ها
    st.subheader("📋 تاریخچه و وضعیت کندل‌ها")
    
    # آماده‌سازی دیتافریم برای نمایش
    view_df = df.sort_index(ascending=False).copy()
    
    st.dataframe(
        view_df,
        use_container_width=True,
        height=400,
        column_config={
            "Signal": st.column_config.TextColumn("وضعیت"),
            "Entry": st.column_config.NumberColumn("ورود", format="$%.1f"),
            "Target": st.column_config.NumberColumn("هدف (TP)", format="$%.1f"),
            "StopLoss": st.column_config.NumberColumn("استاپ (SL)", format="$%.1f"),
            "Close": st.column_config.NumberColumn("قیمت فعلی", format="$%.1f"),
            "Open": st.column_config.NumberColumn("Open", format="$%.1f"),
            "High": None, # مخفی کردن برای خلوت شدن
            "Low": None,
        }
    )

# ======================
# سیستم رفرش خودکار
# ======================
st.markdown("""
    <script>
    setTimeout(function(){
        window.location.reload();
    }, 20000); // رفرش هر 20 ثانیه
    </script>
""", unsafe_allow_html=True)
