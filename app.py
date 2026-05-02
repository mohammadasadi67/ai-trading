import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC ULTRA SAFE V17")
st.title("🐋 BTC PRO: Ultra Safe Mode (V17)")

# ======================
# 1. SAFE DATA LOADER (رفع خطای KeyError)
# ======================
@st.cache_data(ttl=3600)
def get_data(start_str="2023-01-01"):
    endpoints = [
        "https://api1.binance.com/api/v3/klines",
        "https://api2.binance.com/api/v3/klines",
        "https://data-api.binance.vision/api/v3/klines"
    ]
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    all_data = []

    for url in endpoints:
        try:
            params = {"symbol": "BTCUSDT", "interval": "1h", "startTime": start_ts, "limit": 1000}
            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list):
                    all_data = data
                    break
        except: continue

    if not all_data:
        return pd.DataFrame() # برگرداندن دیتافریم خالی در صورت شکست

    df = pd.DataFrame(all_data).iloc[:, :5]
    df.columns = ["Time", "Open", "High", "Low", "Close"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    return df.astype(float)

# ======================
# 2. SIDEBAR
# ======================
with st.sidebar:
    st.header("⚙️ تنظیمات ایمنی")
    start_dt = st.date_input("Start Date", value=date(2023,1,1))
    end_dt = st.date_input("End Date", value=date.today())
    st.divider()
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100
    st.success("سنسور ورود: روی حالت 'تاییدیه سنگین' تنظیم شد.")

# ======================
# 3. CORE PROCESS
# ======================
with st.spinner("در حال فراخوانی دیتا..."):
    df_raw = get_data(start_dt.strftime("%Y-%m-%d"))

# جلوگیری از خطای KeyError: اگر دیتا خالی بود، بقیه کد اجرا نشود
if df_raw.empty or "Close" not in df_raw.columns:
    st.error("⚠️ خطا در دریافت دیتا از بایننس. لطفا چند لحظه دیگر صفحه را Refresh کنید.")
    st.stop()

df = df_raw.copy()

# محاسبه اندیکاتورها با اطمینان از وجود ستون Close
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# RSI
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# 4. ULTRA SAFE ENGINE (فقط ورود با ریسک کم)
# ======================
df["Action"] = "WAIT"
df["PnL"] = 0.0
balance, in_pos = 1.0, False
entry = sl = 0

for i in range(200, len(df)):
    c, l, rsi = df["Close"].iloc[i], df["Low"].iloc[i], df["RSI"].iloc[i]
    ma50, ma200, atr = df["MA50"].iloc[i], df["MA200"].iloc[i], df["ATR"].iloc[i]

    # ورود فقط وقتی همه چیز سبز است + RSI بالای 60 (قدرت مطلق)
    if not in_pos:
        if c > ma50 > ma200 and rsi > 60:
            entry = c
            sl = entry - (atr * 4.0) # استاپ بسیار عریض برای حذف نوسان ۲۰۲۶
            in_pos = True
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"

    elif in_pos:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
        
        # مدیریت خروج سخت‌گیرانه برای حفظ سود
        if c > entry * 1.05: sl = max(sl, entry) # ریسک فری سریع
        if c > entry * 1.15: sl = max(sl, c * 0.92) # قفل سود

        exit_p = 0
        if l <= sl or c < ma50: # خروج با اولین نشانه ضعف
            exit_p = c

        if exit_p > 0:
            p = ((exit_p - entry) / entry) - (fee * 2)
            balance *= (1 + p)
            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL")] = p * 100
            in_pos = False

# ======================
# 5. RESULTS
# ======================
net_profit = (balance - 1) * 100
c1, c2, c3 = st.columns(3)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")
c3.metric("Trades", len(df[df["Action"] == "EXIT"]))

st.divider()
st.subheader("📝 لیست تریدهای ایمن")
trades = df[df["Action"].isin(["BUY", "EXIT"])].copy()
if not trades.empty:
    st.dataframe(trades[["Close", "Action", "PnL"]].sort_index(ascending=False), use_container_width=True)
else:
    st.info("در این بازه زمانی، سیگنالی با ریسک پایین پیدا نشد.")
