import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC SUPER WHALE PRO")
st.title("🐋 BTC PRO: Super Whale Mode (V20 - RISK & GROWTH)")

# ======================
# DATA ENGINE
# ======================
@st.cache_data(ttl=600)
def get_data(start_str="2023-01-01"):
    url = "https://api1.binance.com/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    try:
        params = {"symbol": "BTCUSDT", "interval": "1h", "startTime": start_ts, "limit": 1000}
        res = requests.get(url, params=params, timeout=15)
        data = res.json()
        df = pd.DataFrame(data).iloc[:, :5]
        df.columns = ["Time", "Open", "High", "Low", "Close"]
        df["Time"] = pd.to_datetime(df["Time"], unit="ms")
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except: return pd.DataFrame()

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("⚙️ Settings")
    start_dt = st.date_input("Start Date", value=date(2023,1,1))
    end_dt = st.date_input("End Date", value=date.today())
    st.divider()
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = 0.0005 # کارمزد فیکس 0.05%

# ======================
# LOAD DATA
# ======================
with st.spinner("Loading BTC data..."):
    df = get_data("2023-01-01")

if df.empty:
    st.error("❌ اتصال برقرار نشد. لطفا دوباره تلاش کنید.")
    st.stop()

# ======================
# INDICATORS (THE ENGINE)
# ======================
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
# برای حذف ضرر کوچک، از کانال قیمتی بلندمدت‌تر استفاده می‌کنیم
df["Highest_48h"] = df["High"].rolling(48).max().shift(1)
df["Lowest_48h"] = df["Low"].rolling(48).min().shift(1)

# ======================
# SUPER WHALE ENGINE (V20)
# ======================
df["Action"] = "WAIT"
df["PnL"] = 0.0
balance = 1.0
in_pos = False
entry = sl = 0

df_test = df[df.index.date >= start_dt].copy()

for i in range(len(df_test)):
    idx = df_test.index[i]
    c, l, h = df_test["Close"].iloc[i], df_test["Low"].iloc[i], df_test["High"].iloc[i]
    ma50, ma200 = df_test["MA50"].iloc[i], df_test["MA200"].iloc[i]
    h48, l48 = df_test["Highest_48h"].iloc[i], df_test["Lowest_48h"].iloc[i]

    # ورود با ریسک بالا: شکست سقف ۲ روزه + روند صعودی کلان
    if not in_pos:
        if c > h48 and c > ma200:
            entry = c
            sl = l48 # استاپ عریض (کف ۲ روز اخیر) برای حذف نوسان فیک
            in_pos = True
            df_test.loc[idx, "Action"] = "BUY"

    elif in_pos:
        df_test.loc[idx, "Action"] = "HOLD"
        
        # تریلینگ استاپ هوشمند: فقط وقتی قیمت بالا می‌رود، استاپ را بالا بکش
        # این کار اجازه می‌دهد سودهای نجومی رشد کنند
        sl = max(sl, l48)

        # خروج فقط وقتی روند ۲ روزه کاملاً بشکند
        if l <= sl:
            pnl = ((sl - entry) / entry) - (fee * 2)
            balance *= (1 + pnl)
            df_test.loc[idx, "Action"] = "EXIT"
            df_test.loc[idx, "PnL"] = pnl * 100
            in_pos = False

# ======================
# DISPLAY (YOUR ORIGINAL STYLE)
# ======================
net_profit = (balance - 1) * 100
col1, col2, col3 = st.columns(3)
col1.metric("Net Profit %", f"{net_profit:.2f}%")
col2.metric("Final Balance", f"${capital * balance:,.2f}")
col3.metric("Total Trades", len(df_test[df_test["Action"] == "EXIT"]))

st.divider()
st.subheader("📊 Trade Report")

def color_act(x):
    colors = {"BUY": "#2ecc71", "EXIT": "#e74c3c", "HOLD": "#3498db", "WAIT": "#95a5a6"}
    return f"background-color:{colors.get(x,'white')};color:white"

st.dataframe(
    df_test[df_test["Action"] != "WAIT"].sort_index(ascending=False)
    .style.map(color_act, subset=["Action"])
    .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
    use_container_width=True, height=600
)
