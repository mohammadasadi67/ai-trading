import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC TREND HUNTER V18")
st.title("🐋 BTC PRO: Trend Hunter (V18 - Max Profit)")

# ======================
# DATA LOADER
# ======================
@st.cache_data(ttl=3600)
def get_data(start_str="2023-01-01"):
    url = "https://api1.binance.com/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    params = {"symbol": "BTCUSDT", "interval": "1h", "startTime": start_ts, "limit": 1000}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        df = pd.DataFrame(data).iloc[:, :5]
        df.columns = ["Time", "Open", "High", "Low", "Close"]
        df["Time"] = pd.to_datetime(df["Time"], unit="ms")
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except: return pd.DataFrame()

# ======================
# PROCESS
# ======================
with st.sidebar:
    st.header("⚙️ تنظیمات شکارچی")
    start_dt = st.date_input("Start Date", value=date(2023,1,1))
    end_dt = st.date_input("End Date", value=date.today())
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = 0.0005 # 0.05% کارمزد ثابت

df_raw = get_data("2023-01-01")
if df_raw.empty:
    st.error("دیتا دریافت نشد.")
    st.stop()

df = df_raw.copy()
df["MA200"] = df["Close"].rolling(200).mean()
df["HH_20"] = df["High"].rolling(20).max().shift(1) # سقف ۲۰ ساعت اخیر
df["LL_20"] = df["Low"].rolling(20).min().shift(1)  # کف ۲۰ ساعت اخیر

# ======================
# ENGINE (TREND FOLLOWING)
# ======================
df["Action"] = "WAIT"
df["PnL"] = 0.0
balance, in_pos = 1.0, False
entry = sl = 0

for i in range(20, len(df)):
    t = df.index[i]
    c, l, h = df["Close"].iloc[i], df["Low"].iloc[i], df["High"].iloc[i]
    ma200, hh, ll = df["MA200"].iloc[i], df["HH_20"].iloc[i], df["LL_20"].iloc[i]

    # ورود: قیمت سقف ۲۰ ساعته را بزند و بالای MA200 باشد
    if not in_pos and (start_dt <= t.date() <= end_dt):
        if c > hh and c > ma200:
            entry = c
            sl = ll # استاپ روی کف ۲۰ ساعته (منطقی و متحرک)
            in_pos = True
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"

    elif in_pos:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
        
        # تریلینگ استاپ: همیشه استاپ را به کف ۲۰ ساعت اخیر منتقل کن
        sl = max(sl, ll)

        exit_p = 0
        if l <= sl:
            exit_p = sl
        
        if exit_p > 0:
            p = ((exit_p - entry) / entry) - (fee * 2)
            balance *= (1 + p)
            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL")] = p * 100
            in_pos = False

# ======================
# RESULTS
# ======================
net_profit = (balance - 1) * 100
c1, c2, c3 = st.columns(3)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")
c3.metric("Trades", len(df[df["Action"] == "EXIT"]))

st.divider()
st.subheader("📊 وضعیت روزانه و تریدها")
st.dataframe(df[df["Action"] != "WAIT"].sort_index(ascending=False), use_container_width=True)
