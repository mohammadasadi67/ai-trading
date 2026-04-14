import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# تنظیمات صفحه
st.set_page_config(layout="wide", page_title="پنل معامله‌گری حرفه‌ای")

# ======================
# رفرش خودکار (بهینه‌تر)
# ======================
st.markdown("""
    <script>
    if (!window.location.hash) {
        setTimeout(function(){
            window.location.reload();
        }, 30000); // زمان به 30 ثانیه افزایش یافت تا فشار به API کمتر شود
    }
    </script>
""", unsafe_allow_html=True)

# ======================
# دریافت داده‌ها با قابلیت کش
# ======================
@st.cache_data(ttl=60) # دیتا تا 60 ثانیه معتبر است
def get_4h_data():
    try:
        url = "https://data-api.binance.vision/api/v3/klines"
        params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 100}
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
# مدیریت حافظه (Session State)
# ======================
if "exec" not in st.session_state:
    st.session_state.exec = {}

# ======================
# ورودی‌ها (سایدبار برای تمیزی بیشتر)
# ======================
st.title("🚀 پنل معامله‌گری پرو")

with st.sidebar:
    st.header("⚙️ تنظیمات")
    start = st.date_input("تاریخ شروع", value=datetime(2024, 1, 1))
    end = st.date_input("تاریخ پایان")
    capital = st.number_input("سرمایه اولیه ($)", value=100.0)
    only_trades = st.toggle("فقط نمایش سیگنال‌های TRADE", False)
    
    if st.button("پاک کردن سابقه معاملات"):
        st.session_state.exec = {}
        st.rerun()

# ======================
# پردازش داده‌ها
# ======================
df = get_4h_data()

if not df.empty:
    # اضافه کردن کندل در حال تشکیل (Pending)
    last_4h = df.index[-1]
    next_4h = last_4h + pd.Timedelta(hours=4)
    new_row = pd.DataFrame({
        "Open":[df["Close"].iloc[-1]], "High":[df["Close"].iloc[-1]],
        "Low":[df["Close"].iloc[-1]], "Close":[np.nan]
    }, index=[next_4h])
    df = pd.concat([df, new_row]).sort_index()

    # منطق سیگنال‌دهی
    df["Decision"] = "WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["PnL %"] = np.nan

    for i in range(2, len(df)):
        prev1 = df.iloc[i-1]
        prev2 = df.iloc[i-2]

        if prev1["Close"] > prev2["Close"]: # استراتژی ساده شما
            entry = df["Open"].iloc[i]
            move = prev1["Close"] - prev2["Close"]
            target = entry + move
            high = df["High"].iloc[i]
            close = df["Close"].iloc[i] if pd.notna(df["Close"].iloc[i]) else entry

            exit_price = target if high >= target else close
            pnl = (exit_price - entry) / entry * 100

            df.iloc[i, df.columns.get_loc("Decision")] = "TRADE"
            df.iloc[i, df.columns.get_loc("Entry")] = entry
            df.iloc[i, df.columns.get_loc("Target")] = target
            df.iloc[i, df.columns.get_loc("PnL %")] = pnl

    # فیلتر کردن بر اساس تاریخ
    mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end) + pd.Timedelta(days=1))
    df_view = df.loc[mask]

    if only_trades:
        df_view = df_view[df_view["Decision"] == "TRADE"]

    # ======================
    # نمایش جدول
    # ======================
    st.subheader("📊 جدول سیگنال‌ها")
    
    header = st.columns([2,1,1,1,1,1,1,1,1,0.5])
    cols_names = ["زمان","Open","High","Low","Close","سیگنال","ورود","هدف","سود %","✅"]
    for col, name in zip(header, cols_names):
        col.write(f"**{name}**")

    for idx, row in df_view.iterrows():
        key = str(idx)
        r_cols = st.columns([2,1,1,1,1,1,1,1,1,0.5])
        
        r_cols[0].text(idx.strftime("%m-%d %H:%M"))
        r_cols[1].text(f"{row['Open']:.0f}")
        r_cols[2].text(f"{row['High']:.0f}")
        r_cols[3].text(f"{row['Low']:.0f}")
        r_cols[4].text(f"{row['Close']:.0f}" if pd.notna(row['Close']) else "LIVE")
        
        if row["Decision"] == "TRADE":
            r_cols[5].markdown("🟢 TRADE")
            r_cols[6].text(f"{row['Entry']:.0f}")
            r_cols[7].text(f"{row['Target']:.0f}")
            pnl = row["PnL %"]
            color = "green" if pnl > 0 else "red"
            r_cols[8].markdown(f":{color}[{pnl:.2f}%]")
        else:
            r_cols[5].text("⚪ WAIT")
            r_cols[6].text("-")
            r_cols[7].text("-")
            r_cols[8].text("-")

        # چک‌باکس برای تایید معامله
        st.session_state.exec[key] = r_cols[9].checkbox("", value=st.session_state.exec.get(key, False), key=f"cb_{key}")

    # ======================
    # محاسبه نتیجه نهایی
    # ======================
    balance = capital
    for idx_str, is_checked in st.session_state.exec.items():
        if is_checked:
            # تبدیل کلید رشته‌ای به Timestamp برای پیدا کردن در دیتافریم اصلی
            ts = pd.to_timestamp(idx_str)
            if ts in df.index:
                pnl_val = df.loc[ts, "PnL %"]
                if pd.notna(pnl_val):
                    balance *= (1 + pnl_val/100)

    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("موجودی نهایی", f"${balance:.2f}", delta=f"{balance-capital:.2f}")
else:
    st.warning("در حال دریافت داده‌ها از بایننس...")
