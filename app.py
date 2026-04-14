import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

st.set_page_config(layout="wide", page_title="Professional Trading Panel")

# ======================
# دریافت داده‌های زنده
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
        st.error(f"خطا در اتصال به بایننس: {e}")
        return pd.DataFrame()

# ======================
# سایدبار (مدیریت سرمایه)
# ======================
st.sidebar.title("💰 مدیریت سرمایه")
initial_capital = st.sidebar.number_input("سرمایه اولیه ($)", value=1000.0, step=100.0)

# ======================
# محاسبات سیگنال و PnL
# ======================
df = get_live_data()

if not df.empty:
    df["Signal"] = "⚪ WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["StopLoss"] = np.nan
    df["PnL_Percent"] = 0.0

    total_pnl_multiplier = 1.0 # برای محاسبه سود مرکب

    for i in range(2, len(df)):
        p1 = df.iloc[i-1]
        p2 = df.iloc[i-2]
        
        if p1["Close"] > p2["Close"]:
            entry = df["Open"].iloc[i]
            target = entry + (p1["Close"] - p2["Close"])
            sl = p1["Low"]
            
            curr_high = df["High"].iloc[i] if "High" in df.columns else df["Close"].iloc[i]
            curr_low = df["Low"].iloc[i] if "Low" in df.columns else df["Close"].iloc[i]
            curr_close = df["Close"].iloc[i]

            # منطق خروج: اول هدف، بعد استاپ، در نهایت کلوز کندل
            if curr_high >= target:
                exit_price = target
            elif curr_low <= sl:
                exit_price = sl
            else:
                exit_price = curr_close

            pnl_perc = (exit_price - entry) / entry
            
            df.iloc[i, df.columns.get_loc("Signal")] = "🟢 BUY"
            df.iloc[i, df.columns.get_loc("Entry")] = entry
            df.iloc[i, df.columns.get_loc("Target")] = target
            df.iloc[i, df.columns.get_loc("StopLoss")] = sl
            df.iloc[i, df.columns.get_loc("PnL_Percent")] = pnl_perc * 100
            
            # محاسبه سرمایه (فقط برای معاملات کامل شده یا جاری)
            total_pnl_multiplier *= (1 + pnl_perc)

    final_balance = initial_capital * total_pnl_multiplier

    # ======================
    # نمایش هدر و قیمت
    # ======================
    current_p = df["Close"].iloc[-1]
    st.markdown(f"""
        <div style="text-align: center; background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #4CAF50;">
            <h2 style="margin: 0; color: white;">BTC Current Price: <span style="color: #4CAF50;">${current_p:,.2f}</span></h2>
        </div>
    """, unsafe_allow_html=True)

    # نمایش وضعیت موجودی
    st.write("")
    c1, c2, c3 = st.columns(3)
    c1.metric("سرمایه اولیه", f"${initial_capital:,.0f}")
    c2.metric("موجودی فعلی", f"${final_balance:,.2f}", delta=f"{((final_balance/initial_capital)-1)*100:.2f}%")
    c3.metric("سود/ضرر کل", f"${final_balance - initial_capital:,.2f}")

    st.divider()

    # ======================
    # جدول معاملات
    # ======================
    st.subheader("📋 جزئیات معاملات و PnL")
    
    view_df = df.sort_index(ascending=False).copy()
    
    st.dataframe(
        view_df,
        use_container_width=True,
        height=400,
        column_config={
            "Signal": st.column_config.TextColumn("وضعیت"),
            "Entry": st.column_config.NumberColumn("ورود", format="$%.1f"),
            "Target": st.column_config.NumberColumn("هدف", format="$%.1f"),
            "StopLoss": st.column_config.NumberColumn("استاپ", format="$%.1f"),
            "PnL_Percent": st.column_config.NumberColumn("سود/ضرر %", format="%.2f%%"),
            "Close": st.column_config.NumberColumn("قیمت فعلی/نهایی", format="$%.1f"),
            "Open": None, "High": None, "Low": None # مخفی کردن موارد غیرضروری
        }
    )

# ======================
# رفرش خودکار
# ======================
st.markdown("<script>setTimeout(function(){window.location.reload();}, 30000);</script>", unsafe_allow_html=True)
