import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC SUPER WHALE PRO")
st.title("🐋 BTC PRO: Super Whale Mode (High Growth)")

# ======================
# DATA (FULL HISTORY + SAFE LOADING)
# ======================
@st.cache_data(ttl=3600)
def get_data(start_str="2023-01-01"):
    url = "https://api.binance.com/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    all_data = []

    while True:
        params = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "startTime": start_ts,
            "limit": 1000
        }
        try:
            res = requests.get(url, params=params, timeout=15)
            data = res.json()
            if not isinstance(data, list) or not data:
                break
            all_data.extend(data)
            start_ts = data[-1][0] + 1
            if len(data) < 1000:
                break
        except:
            break

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df = df.iloc[:, :5] # برداشتن 5 ستون اصلی
    df.columns = ["Time", "Open", "High", "Low", "Close"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    return df.astype(float)

# ======================
# SIDEBAR SETTINGS
# ======================
with st.sidebar:
    st.header("⚙️ تنظیمات بازه و سرمایه")
    start_dt = st.date_input("تاریخ شروع بک‌تست", value=date(2023,1,1))
    end_dt = st.date_input("تاریخ پایان بک‌تست", value=date.today())
    st.divider()
    capital = st.number_input("سرمایه اولیه ($)", value=1000.0)
    fee = st.slider("کارمزد هر معامله (%)", 0.0, 0.5, 0.05) / 100

# ======================
# PROCESS DATA
# ======================
with st.spinner("در حال دریافت و پردازش دیتای کامل بایننس..."):
    df_raw = get_data("2023-01-01")

if df_raw.empty:
    st.error("❌ خطا در دریافت دیتا. لطفا اینترنت خود را چک کنید.")
    st.stop()

# محاسبه اندیکاتورها
df = df_raw.copy()
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# SUPER WHALE ENGINE (PRO TREND)
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

    # منطق ورود (فقط داخل بازه انتخابی)
    if not in_pos and (start_dt <= t.date() <= end_dt):
        # ورود در روندهای صعودی معتبر
        if c > ma50 > ma200 and rsi > 50:
            entry = c
            sl = entry - (atr * 3.5) # استاپ عریض برای جلوگیری از فیک‌اوت
            highest = entry
            in_pos = True
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"

    # منطق مدیریت معامله و خروج
    elif in_pos:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
        highest = max(highest, h)

        # ریسک‌فری و قفل سود هوشمند
        if highest > entry * 1.05:
            sl = max(sl, entry) # نقطه سر به سر
        
        if highest > entry * 1.20:
            sl = max(sl, highest * 0.85) # اجازه نوسان 15 درصدی در سودهای بزرگ

        exit_p = 0
        if l <= sl:
            exit_p = sl
        elif c < ma200: # خروج استراتژیک در صورت تغییر روند کلی بازار
            exit_p = c

        if exit_p > 0:
            pnl_raw = ((exit_p - entry) / entry) - (fee * 2)
            balance *= (1 + pnl_raw)
            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL")] = pnl_raw * 100
            in_pos = False

# ======================
# FINAL REPORT
# ======================
df_display = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()
df_display["Date"] = df_display.index.date

daily = df_display.groupby("Date").agg({
    "Close": "last",
    "Action": lambda x: "BUY" if "BUY" in x.values else ("EXIT" if "EXIT" in x.values else ("HOLD" if "HOLD" in x.values else "WAIT")),
    "PnL": "sum"
})

# نمایش متریک‌ها
net_profit = (balance - 1) * 100
col1, col2, col3 = st.columns(3)
col1.metric("Net Profit %", f"{net_profit:.2f}%")
col2.metric("Final Balance", f"${capital * balance:,.2f}")
col3.metric("Trades Count", len(df[df["Action"] == "EXIT"]))

st.divider()
st.subheader(f"📊 جزئیات معاملات روزانه ({start_dt} تا {end_dt})")

def style_action(val):
    color_map = {"BUY": "#2ecc71", "EXIT": "#e74c3c", "HOLD": "#3498db", "WAIT": "#95a5a6"}
    return f"background-color: {color_map.get(val, 'white')}; color: white; font-weight: bold"

st.dataframe(
    daily.sort_index(ascending=False)
    .style.map(style_action, subset=["Action"])
    .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
    use_container_width=True,
    height=600
)
