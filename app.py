import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

# تنظیمات صفحه
st.set_page_config(layout="wide", page_title="Professional Trading Dashboard")
st.title(" MOHAMMAD PATTERN")

# ======================
# DATA FETCHING
# ======================
@st.cache_data(ttl=60) # کش کردن داده‌ها برای سرعت بیشتر
def get_live_data():
    try:
        url = "https://data-api.binance.vision/api/v3/klines"
        params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 500}
        data = requests.get(url, params=params).json()

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ig"
        ])

        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# ======================
# TIME CALCULATION
# ======================
def get_time_remaining():
    now = datetime.utcnow()
    next_4h = (now.hour // 4 + 1) * 4
    
    if next_4h >= 24:
        target = datetime(now.year, now.month, now.day) + timedelta(days=1)
    else:
        target = datetime(now.year, now.month, now.day, next_4h)
    
    remaining = target - now
    return str(remaining).split(".")[0]

# ======================
# SIDEBAR (Control Panel)
# ======================
st.sidebar.header("Settings")
initial_capital = st.sidebar.number_input("Capital ($)", value=1000.0, step=100.0)
fee_rate = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.1) / 100

# تنظیم تاریخ پیش‌فرض روی یک هفته قبل
default_start = date.today() - timedelta(days=7)
start_date = st.sidebar.date_input("Start Date", value=default_start)

# ======================
# CORE LOGIC
# ======================
df_raw = get_live_data()

if not df_raw.empty:
    # فیلتر کردن بر اساس تاریخ انتخاب شده
    df = df_raw[df_raw.index.date >= start_date].copy()
    
    if len(df) < 3:
        st.warning("داده‌های کافی در این بازه زمانی یافت نشد. بازه را طولانی‌تر کنید.")
    else:
        # وضعیت کندل آخر
        df["Status"] = "CLOSED"
        df.iloc[-1, df.columns.get_loc("Status")] = "LIVE"

        # تشخیص نوع کندل
        df["Candle"] = np.where(df["Close"] > df["Open"], "🟢 Bullish", "🔴 Bearish")
        df["O→C"] = df["Open"].astype(str) + " → " + df["Close"].astype(str)

        # ستون‌های استراتژی
        df["Signal"] = "WAIT"
        df["Entry"] = np.nan
        df["Target"] = np.nan
        df["StopLoss"] = np.nan
        df["Confidence"] = 0.0
        df["PnL_Percent"] = 0.0

        balance = 1.0
        trades = 0

        # بک‌تست استراتژی
        for i in range(2, len(df)):
            p1 = df.iloc[i-1]
            p2 = df.iloc[i-2]

            # محاسبه مومنتوم
            move = (p1["Close"] - p2["Close"]) / p2["Close"]

            if move < 0.004: # شرط ورود
                continue

            entry = df["Open"].iloc[i]
            sl = p1["Low"]
            tp = entry + (move * entry * 1.5)

            high = df["High"].iloc[i]
            low = df["Low"].iloc[i]
            exit_price = df["Close"].iloc[i]

            # منطق خروج (SL یا TP)
            if low <= sl:
                exit_price = sl
            elif high >= tp:
                exit_price = tp

            raw_return = (exit_price - entry) / entry
            net_return = (1 + raw_return) * (1 - fee_rate)**2 - 1

            if net_return <= 0 and exit_price != sl: # فیلتر کردن معاملات خنثی
                continue

            trades += 1
            balance *= (1 + net_return)

            # ثبت در جدول
            idx = df.index[i]
            df.at[idx, "Signal"] = "BUY"
            df.at[idx, "Entry"] = entry
            df.at[idx, "Target"] = tp
            df.at[idx, "StopLoss"] = sl
            df.at[idx, "PnL_Percent"] = net_return * 100
            df.at[idx, "Confidence"] = min(0.95, 0.6 + move*10)

        # ======================
        # UI - HEADER METRICS
        # ======================
        price = df["Close"].iloc[-1]
        final_balance = initial_capital * balance
        profit_pct = (balance - 1) * 100

        c1, c2 = st.columns([2, 1])
        c1.metric("BTC Price", f"${price:,.2f}")
        c2.metric("Next Candle In", get_time_remaining())

        st.divider()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current Balance", f"${final_balance:,.2f}")
        m2.metric("Total Profit", f"${final_balance-initial_capital:,.2f}", f"{profit_pct:.2f}%")
        m3.metric("Total Trades", trades)
        m4.metric("Avg. Profit/Trade", f"{((balance**(1/max(trades,1)))-1)*100:.2f}%" if trades > 0 else "0%")

        st.divider()

        # ======================
        # UI - DATA TABLE
        # ======================
        st.subheader("📊 Trading Logs & Strategy Signals")
        
        # مرتب‌سازی برای نمایش (جدیدترین در بالا)
        view_df = df.sort_index(ascending=False).copy()
        
        st.dataframe(
            view_df,
            use_container_width=True,
            height=500,
            column_config={
                "O→C": "Price Range",
                "Candle": "Type",
                "High": st.column_config.NumberColumn("High", format="$%.1f"),
                "Low": st.column_config.NumberColumn("Low", format="$%.1f"),
                "Open": st.column_config.NumberColumn("Open", format="$%.1f"),
                "Close": st.column_config.NumberColumn("Close", format="$%.1f"),
                "Entry": st.column_config.NumberColumn("Entry", format="$%.1f"),
                "Target": st.column_config.NumberColumn("TP", format="$%.1f"),
                "StopLoss": st.column_config.NumberColumn("SL", format="$%.1f"),
                "PnL_Percent": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
                "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1),
            }
        )

# ======================
# AUTO REFRESH (Every 30s)
# ======================
st.markdown(
    "<script>setTimeout(()=>window.location.reload(),30000)</script>",
    unsafe_allow_html=True
)
