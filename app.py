import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC SUPER WHALE FINAL")
st.title("🐋 BTC PRO: Super Whale Mode (V15 - Ultra Stable)")

# ======================
# DATA (MULTI-ENDPOINT + RETRY)
# ======================
@st.cache_data(ttl=3600)
def get_data(start_str="2023-01-01"):
    # لیست دامین‌های بایننس برای دور زدن محدودیت‌های IP
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://data-api.binance.vision/api/v3/klines",
        "https://api1.binance.com/api/v3/klines",
        "https://api2.binance.com/api/v3/klines"
    ]
    
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    all_data = []
    
    for url in endpoints:
        all_data = []
        current_ts = start_ts
        try:
            while True:
                params = {
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "startTime": current_ts,
                    "limit": 1000
                }
                res = requests.get(url, params=params, timeout=15)
                
                if res.status_code == 200:
                    data = res.json()
                    if not data or not isinstance(data, list):
                        break
                    all_data.extend(data)
                    current_ts = data[-1][0] + 1
                    if len(data) < 1000:
                        break
                else:
                    break
            
            if all_data: # اگر از این دامین دیتا گرفتیم، عملیات موفقه
                break
        except:
            continue
            
    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df = df.iloc[:, :5]
    df.columns = ["Time", "Open", "High", "Low", "Close"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    return df.astype(float)

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("⚙️ تنظیمات بک‌تست")
    start_dt = st.date_input("از تاریخ", value=date(2023,1,1))
    end_dt = st.date_input("تا تاریخ", value=date.today())
    st.divider()
    capital = st.number_input("سرمایه (USD)", value=1000.0)
    fee = st.slider("کارمزد هر معامله (%)", 0.0, 0.5, 0.05) / 100
    st.info("💡 این استراتژی روی حالت Super Whale تنظیم شده تا روندهای بزرگ را شکار کند.")

# ======================
# LOAD DATA
# ======================
with st.spinner("🚀 در حال فراخوانی دیتای بایننس از چند سرور مختلف..."):
    df_raw = get_data("2023-01-01")

if df_raw.empty:
    st.error("❌ متاسفانه ارتباط با سرورهای بایننس برقرار نشد. لطفا صفحه را رفرش کنید یا کمی بعد تلاش کنید.")
    st.stop()

# ======================
# INDICATORS
# ======================
df = df_raw.copy()
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE (SUPER WHALE - TREND)
# ======================
df["Action"] = "WAIT"
df["PnL"] = 0.0

balance = 1.0
in_pos = False
entry = sl = highest = 0

for i in range(200, len(df)):
    t = df.index[i]
    c, h, l = df["Close"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i]
    rsi, ma50, ma200, atr = df["RSI"].iloc[i], df["MA50"].iloc[i], df["MA200"].iloc[i], df["ATR"].iloc[i]

    if not in_pos and (start_dt <= t.date() <= end_dt):
        # شرط ورود: قیمت بالای هر دو میانگین متحرک (روند صعودی تثبیت شده)
        if c > ma50 > ma200 and rsi > 50:
            entry = c
            sl = entry - (atr * 3.5) # استاپ عریض برای فریب نخوردن از نوسانات
            highest = entry
            in_pos = True
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"

    elif in_pos:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
        highest = max(highest, h)

        # مدیریت هوشمند حد ضرر
        if highest > entry * 1.05:
            sl = max(sl, entry) # سر به سر کردن
        
        if highest > entry * 1.20:
            sl = max(sl, highest * 0.85) # تریلینگ استاپ 15 درصدی

        exit_p = 0
        if l <= sl:
            exit_p = sl
        elif c < ma200: # خروج اگر کل روند بازار خرسی شد
            exit_p = c

        if exit_p > 0:
            pnl_val = ((exit_p - entry) / entry) - (fee * 2)
            balance *= (1 + pnl_val)
            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL")] = pnl_val * 100
            in_pos = False

# ======================
# RESULTS & DISPLAY
# ======================
df_display = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()
df_display["Date"] = df_display.index.date

daily = df_display.groupby("Date").agg({
    "Close": "last",
    "Action": lambda x: "BUY" if "BUY" in x.values else ("EXIT" if "EXIT" in x.values else ("HOLD" if "HOLD" in x.values else "WAIT")),
    "PnL": "sum"
})

# نمایش متریک‌ها
net_prof = (balance - 1) * 100
col1, col2, col3 = st.columns(3)
col1.metric("Net Profit %", f"{net_prof:.2f}%")
col2.metric("Final Balance", f"${capital * balance:,.2f}")
col3.metric("Trades", len(df[df["Action"] == "EXIT"]))

st.divider()
st.subheader(f"📊 گزارش معاملات روزانه")

def style_row(val):
    colors = {"BUY": "#2ecc71", "EXIT": "#e74c3c", "HOLD": "#3498db", "WAIT": "#95a5a6"}
    return f"background-color: {colors.get(val, 'gray')}; color: white; font-weight: bold"

st.dataframe(
    daily.sort_index(ascending=False)
    .style.map(style_row, subset=["Action"])
    .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
    use_container_width=True,
    height=600
)
