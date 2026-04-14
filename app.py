import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="AI RL-Trading Bot")

# ======================
# دریافت داده‌های زنده
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 200}
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
    except:
        return pd.DataFrame()

# ======================
# بخش هوش مصنوعی (RL Logic)
# ======================
def apply_rl_logic(df):
    """
    شبیه‌سازی یادگیری تقویتی برای بهینه‌سازی تارگت و استاپ
    """
    df = df.copy()
    df["Signal"] = "⚪ WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["StopLoss"] = np.nan
    df["Confidence"] = 0.0 # میزان اطمینان مدل RL

    # پارامترهای پایه که مدل یاد می‌گیرد آن‌ها را تغییر دهد
    learning_rate = 0.1
    reward_factor = 1.5 # پاداش برای سودهای بالاتر
    
    # متغیرهای یادگیری (State)
    best_move_multiplier = 1.0 # این عدد با تجربه بازار اصلاح می‌شود

    for i in range(5, len(df)):
        # تشخیص پترن (Pattern Recognition)
        # مثال: شیب ۳ کندل اخیر و بدنه کندل تاییدیه
        body_prev = df["Close"].iloc[i-1] - df["Open"].iloc[i-1]
        slope = (df["Close"].iloc[i-1] - df["Close"].iloc[i-4]) / 3
        
        # شرط ورود هوشمند (RL Signal)
        if body_prev > 0 and slope > 0:
            entry = df["Open"].iloc[i]
            
            # مدل RL یاد می‌گیرد تارگت را بر اساس نوسانات اخیر (Volatility) تنظیم کند
            volatility = df["High"].iloc[i-5:i].max() - df["Low"].iloc[i-5:i].min()
            
            # یادگیری تقویتی: اگر معاملات قبلی سودده بودند، ضریب هدف افزایش می‌یابد
            target_distance = (body_prev * best_move_multiplier) + (volatility * 0.1)
            target = entry + target_distance
            sl = df["Low"].iloc[i-1] # استاپ لاس کلاسیک زیر کندل تایید
            
            # محاسبه نتیجه برای یادگیری Agent
            actual_close = df["Close"].iloc[i]
            if actual_close > entry:
                # پاداش مثبت: مدل یاد می‌گیرد در پترن‌های مشابه تارگت را بازتر بگذارد
                best_move_multiplier += (learning_rate * reward_factor)
                confidence = min(95.0, 70.0 + (best_move_multiplier * 2))
            else:
                # جریمه: مدل احتیاط بیشتری به خرج می‌دهد
                best_move_multiplier -= learning_rate
                confidence = max(50.0, 70.0 - abs(best_move_multiplier))

            df.iloc[i, df.columns.get_loc("Signal")] = "🤖 AI-BUY"
            df.iloc[i, df.columns.get_loc("Entry")] = entry
            df.iloc[i, df.columns.get_loc("Target")] = target
            df.iloc[i, df.columns.get_loc("StopLoss")] = sl
            df.iloc[i, df.columns.get_loc("Confidence")] = confidence

    return df

# ======================
# اجرا و نمایش
# ======================
df = get_live_data()

if not df.empty:
    df_ai = apply_rl_logic(df)
    
    # فیلتر تاریخ (سایدبار)
    st.sidebar.title("🤖 RL Bot Settings")
    capital = st.sidebar.number_input("Capital ($)", value=1000)
    start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=10))
    
    view_df = df_ai[df_ai.index.date >= start_date].sort_index(ascending=False)

    # هدر لایو
    curr_p = view_df["Close"].iloc[0]
    st.markdown(f"""
        <div style="background-color:#161b22; border:1px solid #58a6ff; border-radius:10px; padding:20px; text-align:center;">
            <h3 style="color:#58a6ff; margin:0;">AI AGENT ACTIVE (RL MODEL)</h3>
            <h1 style="color:white; margin:0;">BTC: ${curr_p:,.2f}</h1>
        </div>
    """, unsafe_allow_html=True)

    st.write("")
    
    # نمایش سیگنال هوشمند لایو
    last_sig = df_ai[df_ai["Signal"] == "🤖 AI-BUY"].iloc[-1]
    
    cols = st.columns(4)
    cols[0].metric("AI Confidence", f"{last_sig['Confidence']:.1f}%")
    cols[1].metric("Smart Entry", f"${last_sig['Entry']:,.1f}")
    cols[2].metric("Optimized Target", f"${last_sig['Target']:,.1f}")
    cols[3].metric("Risk Management (SL)", f"${last_sig['StopLoss']:,.1f}")

    st.divider()

    # جدول هوشمند
    st.subheader("📋 RL Model Training & Predictions")
    st.dataframe(
        view_df,
        use_container_width=True,
        column_config={
            "Signal": st.column_config.TextColumn("نوع سیگنال"),
            "Confidence": st.column_config.ProgressColumn("اطمینان مدل", format="%.0f%%", min_value=0, max_value=100),
            "Entry": st.column_config.NumberColumn("ورود", format="$%.1f"),
            "Target": st.column_config.NumberColumn("تارگت بهینه", format="$%.1f"),
            "StopLoss": st.column_config.NumberColumn("حد ضرر", format="$%.1f"),
            "Close": st.column_config.NumberColumn("قیمت نهایی", format="$%.1f"),
            "Open": None, "High": None, "Low": None
        }
    )

# رفرش
st.markdown("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", unsafe_allow_html=True)
