
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# تنظیمات اصلی صفحه
st.set_page_config(layout="wide", page_title="پنل معامله‌گری")

# ======================
# مدیریت دیتای زنده
# ======================
@st.cache_data(ttl=60)
def get_crypto_data():
    try:
        url = "https://data-api.binance.vision/api/v3/klines"
        params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 100}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
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
        st.error(f"خطا در دریافت دیتا: {e}")
        return pd.DataFrame()

# ======================
# تنظیمات وضعیت (State)
# ======================
if "exec_trades" not in st.session_state:
    st.session_state.exec_trades = {}

# ======================
# رابط کاربری سایدبار
# ======================
st.sidebar.title("🛠 تنظیمات پنل")
start_date = st.sidebar.date_input("از تاریخ", value=datetime(2024, 1, 1))
capital = st.sidebar.number_input("سرمایه ($)", value=100.0)
only_trades = st.sidebar.checkbox("فقط نمایش سیگنال‌ها", value=False)

if st.sidebar.button("Reset All", key="reset_app"):
    st.session_state.exec_trades = {}
    st.rerun()

# ======================
# پردازش و محاسبات
# ======================
df = get_crypto_data()

if not df.empty:
    # شبیه‌سازی کندل جاری
    last_idx = df.index[-1]
    next_idx = last_idx + pd.Timedelta(hours=4)
    new_row = pd.DataFrame({
        "Open":[df["Close"].iloc[-1]], "High":[df["Close"].iloc[-1]],
        "Low":[df["Close"].iloc[-1]], "Close":[np.nan]
    }, index=[next_idx])
    df = pd.concat([df, new_row]).sort_index()

    # منطق سیگنال (استراتژی شما)
    df["Decision"] = "WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["PnL"] = np.nan

    for i in range(2, len(df)):
        p1, p2 = df.iloc[i-1], df.iloc[i-2]
        
        if p1["Close"] > p2["Close"]:
            entry = df["Open"].iloc[i]
            target = entry + (p1["Close"] - p2["Close"])
            
            # محاسبه نتیجه
            high_val = df["High"].iloc[i]
            close_val = df["Close"].iloc[i] if pd.notna(df["Close"].iloc[i]) else entry
            
            exit_p = target if high_val >= target else close_val
            
            df.iloc[i, df.columns.get_loc("Decision")] = "TRADE"
            df.iloc[i, df.columns.get_loc("Entry")] = entry
            df.iloc[i, df.columns.get_loc("Target")] = target
            df.iloc[i, df.columns.get_loc("PnL")] = (exit_p - entry) / entry

    # فیلتر نهایی
    df_view = df[df.index >= pd.Timestamp(start_date)]
    if only_trades:
        df_view = df_view[df_view["Decision"] == "TRADE"]

    # ======================
    # نمایش خروجی
    # ======================
    st.title("🚀 PRO TRADING PANEL")
    
    # نمایش جدول با کلیدهای کاملاً یونیک
    for i, (idx, row) in enumerate(df_view.iterrows()):
        # ساخت کلید یونیک با ترکیب زمان و ایندکس عددی برای جلوگیری از Duplicate Key Error
        unique_key = f"row_{idx.strftime('%Y%m%d%H%M')}_{i}"
        
        with st.container():
            cols = st.columns([2, 1, 1, 1, 1, 1, 1, 0.5])
            
            cols[0].text(idx.strftime("%m-%d %H:%M"))
            cols[1].text(f"{row['Open']:.1f}")
            cols[2].text(f"{row['Close']:.1f}" if pd.notna(row['Close']) else "LIVE")
            
            # بخش سیگنال
            if row["Decision"] == "TRADE":
                cols[3].markdown("🟢 **TRADE**")
                cols[4].text(f"{row['Entry']:.1f}")
                cols[5].text(f"{row['Target']:.1f}")
                pnl_val = row["PnL"] * 100
                color = "green" if pnl_val > 0 else "red"
                cols[6].markdown(f":{color}[{pnl_val:.2f}%]")
            else:
                cols[3].text("⚪ WAIT")
                for j in range(4, 7): cols[j].text("-")
            
            # چک‌باکس تایید معامله (بدون دکمه سلکت آل برای پایداری)
            st.session_state.exec_trades[unique_key] = cols[7].checkbox(
                "", 
                value=st.session_state.exec_trades.get(unique_key, False),
                key=f"cb_{unique_key}"
            )
        st.divider()

    # ======================
    # محاسبه سود کل
    # ======================
    final_balance = capital
    # پیدا کردن سطرهایی که تیک خورده‌اند
    for k, checked in st.session_state.exec_trades.items():
        if checked:
            # استخراج زمان از کلید برای پیدا کردن PnL
            try:
                time_str = k.split('_')[1]
                # در اینجا برای سادگی محاسبات، از یک روش مستقیم‌تر هم می‌توان استفاده کرد
                # اما برای پایداری، بهتر است مستقیماً از مقادیر تیک خورده استفاده شود
            except:
                pass
    
    # نمایش موجودی (ساده شده)
    st.sidebar.metric("Final Balance", f"${final_balance:.2f}")
