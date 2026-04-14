import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Advanced Live Panel")

# ======================
# توابع کمکی (زمان و دیتا)
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 150}
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

def get_time_remaining():
    # محاسبه زمان باقی‌مانده تا کندل 4 ساعته بعدی (UTC)
    now = datetime.utcnow()
    next_4h_mark = (now.hour // 4 + 1) * 4
    if next_4h_mark >= 24:
        next_candle = datetime(now.year, now.month, now.day) + timedelta(days=1)
    else:
        next_candle = datetime(now.year, now.month, now.day, next_4h_mark)
    
    remaining = next_candle - now
    # فرمت کردن به صورت HH:MM:SS
    return str(remaining).split(".")[0]

# ======================
# سایدبار
# ======================
st.sidebar.title("💰 تنظیمات")
initial_capital = st.sidebar.number_input("سرمایه اولیه ($)", value=1000.0)
start_date = st.sidebar.date_input("تاریخ شروع", value=datetime.now() - timedelta(days=15))

# ======================
# پردازش اصلی
# ======================
df = get_live_data()

if not df.empty:
    # فیلتر تاریخ
    df_filtered = df[df.index.date >= start_date].copy()
    
    # محاسبات سیگنال
    df_filtered["Signal"] = "⚪ WAIT"
    df_filtered["Entry"] = np.nan
    df_filtered["Target"] = np.nan
    df_filtered["StopLoss"] = np.nan
    df_filtered["PnL%"] = 0.0
    df_filtered["Live_Status"] = "Closed"

    total_multiplier = 1.0

    for i in range(2, len(df_filtered)):
        p1, p2 = df_filtered.iloc[i-1], df_filtered.iloc[i-2]
        
        if p1["Close"] > p2["Close"]:
            entry = df_filtered["Open"].iloc[i]
            target = entry + (p1["Close"] - p2["Close"])
            sl = p1["Low"]
            
            # در ردیف آخر (لایو) قیمت کلوز فعلی رو ملاک قرار بده
            curr_close = df_filtered["Close"].iloc[i]
            pnl = (curr_close - entry) / entry
            
            df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "🟢 BUY"
            df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = entry
            df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = target
            df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = sl
            df_filtered.iloc[i, df_filtered.columns.get_loc("PnL%")] = pnl * 100
            
            total_multiplier *= (1 + pnl)

    # علامت‌گذاری آخرین کندل به عنوان لایو
    df_filtered.iloc[-1, df_filtered.columns.get_loc("Live_Status")] = "🔵 LIVE"

    # ======================
    # هدر لایو (قیمت و کانتر)
    # ======================
    curr_p = df_filtered["Close"].iloc[-1]
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"""
            <div style="background-color: #0e1117; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50;">
                <p style="color: #888; margin:0;">BTC/USDT LIVE PRICE</p>
                <h1 style="margin:0;">${curr_p:,.2f}</h1>
            </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown(f"""
            <div style="background-color: #0e1117; padding: 15px; border-radius: 10px; border-left: 5px solid #ffca28;">
                <p style="color: #888; margin:0;">TIME TO NEXT CANDLE</p>
                <h1 style="margin:0; color: #ffca28;">{get_time_remaining()}</h1>
            </div>
        """, unsafe_allow_html=True)

    # نمایش موجودی
    st.write("")
    final_bal = initial_capital * total_multiplier
    m1, m2, m3 = st.columns(3)
    m1.metric("سرمایه شروع", f"${initial_capital:,.0f}")
    m2.metric("موجودی فعلی", f"${final_bal:,.2f}", delta=f"{(total_multiplier-1)*100:.2f}%")
    m3.metric("سود/ضرر خالص", f"${final_bal - initial_capital:,.2f}")

    st.divider()

    # ======================
    # جدول با استایل لایو
    # ======================
    st.subheader("📊 لیست سیگنال‌ها و وضعیت لحظه‌ای")
    
    view_df = df_filtered.sort_index(ascending=False).copy()
    
    st.dataframe(
        view_df,
        use_container_width=True,
        height=450,
        column_config={
            "Live_Status": st.column_config.TextColumn("وضعیت کندل"),
            "Signal": st.column_config.TextColumn("سیگنال"),
            "Entry": st.column_config.NumberColumn("ورود", format="$%.1f"),
            "Target": st.column_config.NumberColumn("هدف", format="$%.1f"),
            "StopLoss": st.column_config.NumberColumn("استاپ", format="$%.1f"),
            "PnL%": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
            "Close": st.column_config.NumberColumn("قیمت نهایی/فعلی", format="$%.1f"),
            "Open": None, "High": None, "Low": None
        }
    )

# رفرش خودکار برای آپدیت قیمت و تایمر
st.markdown("<script>setTimeout(function(){window.location.reload();}, 10000);</script>", unsafe_allow_html=True)
