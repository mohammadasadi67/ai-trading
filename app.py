import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC PRO SPOT V10")
st.title("🛡️ BTC PRO TREND-MASTER (V10)")

# ======================
# DATA FETCHING
# ======================
@st.cache_data(ttl=600)
def get_data(limit=1500):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "1h", "limit": limit}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        df = pd.DataFrame(data, columns=["time","open","high","low","close","volume","ct","qav","trades","tb","tq","ig"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except:
        return pd.DataFrame()

# ======================
# SETTINGS
# ======================
with st.sidebar:
    st.header("Settings")
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100
    start_date = st.date_input("Start Date", value=date(2023, 1, 1))

df_hourly = get_data()
if df_hourly.empty:
    st.error("Connection Error")
    st.stop()

# ======================
# INDICATORS
# ======================
df = df_hourly.copy()
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE (PRO TREND MODE - OPTIMIZED)
# ======================
df["Action"] = "WAIT"
df["PnL_Trade"] = 0.0

balance = 1.0
in_pos = False
entry_val = 0
sl_val = 0
highest = 0

for i in range(200, len(df)):
    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]
    rsi = df["RSI"].iloc[i]
    ma50 = df["MA50"].iloc[i]
    ma200 = df["MA200"].iloc[i]
    atr = df["ATR"].iloc[i]

    if not in_pos:
        # ورود: روند صعودی تثبیت شده + مومنتوم مثبت
        if c > ma50 > ma200 and 55 < rsi < 70:
            in_pos = True
            entry_val = c
            sl_val = entry_val - (atr * 1.2) # استاپ لاس طبق انجین شما
            highest = entry_val
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"
    else:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
        if h > highest:
            highest = h
        
        # Trailing واقعی طبق انجین شما
        if highest > entry_val * 1.03:
            sl_val = max(sl_val, highest * 0.96)

        exit_p = 0
        if l <= sl_val:
            exit_p = sl_val

        if exit_p > 0:
            pnl = ((exit_p - entry_val) / entry_val) - (fee * 2)
            balance *= (1 + pnl)
            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL_Trade")] = pnl * 100
            in_pos = False

# ======================
# DAILY AGGREGATION
# ======================
df['Date'] = df.index.date
daily_df = df.groupby('Date').agg({
    'Close': 'last',
    'Action': lambda x: 'BUY' if 'BUY' in x.values else ('EXIT' if 'EXIT' in x.values else ('HOLD' if 'HOLD' in x.values else 'WAIT')),
    'PnL_Trade': 'sum'
})

daily_df = daily_df[daily_df.index >= start_date]

# ======================
# METRICS & DISPLAY
# ======================
net_profit = (balance - 1) * 100
c1, c2, c3 = st.columns(3)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")
c3.metric("Last Status", daily_df['Action'].iloc[-1])

st.divider()
st.subheader("🗓️ Daily Trade Log (Hourly Analysis)")

# رفع خطای applymap با استفاده از map (نسخه‌های جدید پانداز)
def style_action(val):
    colors = {'BUY': '#27ae60', 'EXIT': '#c0392b', 'HOLD': '#2980b9', 'WAIT': '#7f8c8d'}
    return f'background-color: {colors.get(val, "white")}; color: white; font-weight: bold'

st.dataframe(
    daily_df.sort_index(ascending=False)
    .style.map(style_action, subset=['Action'])
    .format({"PnL_Trade": "{:+.2f}%", "Close": "{:,.1f}"}),
    use_container_width=True,
    height=600
)
