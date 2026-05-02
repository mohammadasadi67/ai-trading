import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC SUPER WHALE PRO")
st.title("🐋 BTC PRO: Super Whale Mode (V20 - RISK & GROWTH)")

# ======================
# DATA ENGINE (FAST & STABLE)
# ======================
@st.cache_data(ttl=300)
def get_data(start_str="2023-01-01"):
    # دامین مستقیم و پرسرعت
    url = "https://api1.binance.com/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    try:
        params = {"symbol": "BTCUSDT", "interval": "1h", "startTime": start_ts, "limit": 1000}
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            df = pd.DataFrame(data).iloc[:, :5]
            df.columns = ["Time", "Open", "High", "Low", "Close"]
            df["Time"] = pd.to_datetime(df["Time"], unit="ms")
            df.set_index("Time", inplace=True)
            return df.astype(float)
    except:
        pass
    return pd.DataFrame()

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("⚙️ Settings")
    start_dt = st.date_input("Start Date", value=date(2023,1,1))
    end_dt = st.date_input("End Date", value=date.today())
    st.divider()
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = 0.0005 # 0.05%

# ======================
# EXECUTION
# ======================
df_raw = get_data("2023-01-01")

if df_raw.empty:
    st.warning("⚠️ در حال تلاش مجدد برای اتصال به دیتای زنده...")
    st.stop()

# محاسبات اندیکاتورهای شکارچی
df = df_raw.copy()
df["MA200"] = df["Close"].rolling(200).mean()
# برای حذف ضررهای کوچک، بازه سقف و کف را روی 48 ساعت گذاشتیم
df["H_48"] = df["High"].rolling(48).max().shift(1)
df["L_48"] = df["Low"].rolling(48).min().shift(1)

# فیلتر بازه زمانی انتخابی کاربر
df_backtest = df[df.index.date >= start_dt].copy()

# ======================
# ENGINE (V20 - NO FEAR)
# ======================
balance = 1.0
in_pos = False
entry = sl = 0
df_backtest["Action"] = "WAIT"
df_backtest["PnL"] = 0.0

for i in range(len(df_backtest)):
    idx = df_backtest.index[i]
    c, l, h = df_backtest["Close"].iloc[i], df_backtest["Low"].iloc[i], df_backtest["High"].iloc[i]
    h48, l48, ma200 = df_backtest["H_48"].iloc[i], df_backtest["L_48"].iloc[i], df_backtest["MA200"].iloc[i]

    # ورود: نترس و وقتی سقف شکسته شد و روند صعودی بود وارد شو
    if not in_pos:
        if c > h48 and c > ma200:
            entry = c
            sl = l48 # استاپ عریض برای حذف نوسان فیک
            in_pos = True
            df_backtest.at[idx, "Action"] = "BUY"

    elif in_pos:
        df_backtest.at[idx, "Action"] = "HOLD"
        # تریلینگ استاپ: با سود بالا می‌آید
        sl = max(sl, l48)

        # خروج: فقط وقتی روند ۴۸ ساعته واقعاً بشکند
        if l <= sl:
            pnl = ((sl - entry) / entry) - (fee * 2)
            balance *= (1 + pnl)
            df_backtest.at[idx, "Action"] = "EXIT"
            df_backtest.at[idx, "PnL"] = pnl * 100
            in_pos = False

# ======================
# DISPLAY
# ======================
net_profit = (balance - 1) * 100
col1, col2, col3 = st.columns(3)
col1.metric("Net Profit %", f"{net_profit:.2f}%")
col2.metric("Final Balance", f"${capital * balance:,.2f}")
col3.metric("Trades", len(df_backtest[df_backtest["Action"] == "EXIT"]))

st.divider()
def color_act(x):
    colors = {"BUY": "#2ecc71", "EXIT": "#e74c3c", "HOLD": "#3498db", "WAIT": "#95a5a6"}
    return f"background-color:{colors.get(x,'#f0f2f6')};color:white"

st.dataframe(
    df_backtest[df_backtest["Action"] != "WAIT"].sort_index(ascending=False)
    .style.map(color_act, subset=["Action"])
    .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
    use_container_width=True
)
