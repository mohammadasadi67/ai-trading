import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC BACKTEST PRO")
st.title("🧪 BTC BACKTEST: Custom Range (Hourly/Daily)")

# ======================
# DATA FETCHING
# ======================
@st.cache_data(ttl=600)
def get_data(limit=2000):
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
# SIDEBAR - RANGE SETTINGS
# ======================
with st.sidebar:
    st.header("🗓️ بازه بک‌تست")
    start_dt = st.date_input("از تاریخ", value=date(2023, 1, 1))
    end_dt = st.date_input("تا تاریخ", value=date.today())
    
    st.divider()
    st.header("💰 تنظیمات سرمایه")
    capital = st.number_input("Capital ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100

df_raw = get_data()
if df_raw.empty:
    st.error("خطا در اتصال به API بایننس")
    st.stop()

# ======================
# INDICATORS (Pre-calculated)
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
# ENGINE (RANGE-BASED BACKTEST)
# ======================
df["Action"] = "WAIT"
df["PnL_Trade"] = 0.0

balance = 1.0
in_pos = False
entry_val = 0
sl_val = 0
highest = 0

# حلقه اصلی روی کل دیتا اما اعمال منطق فقط در بازه انتخابی
for i in range(200, len(df)):
    current_date = df.index[i].date()
    
    # فیلتر بازه زمانی
    if not (start_dt <= current_date <= end_dt):
        continue

    c = df["Close"].iloc[i]
    h = df["High"].iloc[i]
    l = df["Low"].iloc[i]
    rsi = df["RSI"].iloc[i]
    ma50 = df["MA50"].iloc[i]
    ma200 = df["MA200"].iloc[i]
    atr = df["ATR"].iloc[i]

    if not in_pos:
        if c > ma50 > ma200 and 55 < rsi < 70:
            in_pos = True
            entry_val = c
            sl_val = entry_val - (atr * 1.2)
            highest = entry_val
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"
    else:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
        if h > highest:
            highest = h
        
        # Trailing 3%
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
# DATA AGGREGATION & FILTERING
# ======================
df['Date'] = df.index.date
# فیلتر نهایی دیتای نمایش برای جدول
df_display = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()

daily_df = df_display.groupby('Date').agg({
    'Close': 'last',
    'Action': lambda x: 'BUY' if 'BUY' in x.values else ('EXIT' if 'EXIT' in x.values else ('HOLD' if 'HOLD' in x.values else 'WAIT')),
    'PnL_Trade': 'sum'
})

# ======================
# RESULTS & UI
# ======================
net_profit = (balance - 1) * 100
col1, col2, col3 = st.columns(3)
col1.metric("Net Profit (%)", f"{net_profit:.2f}%")
col2.metric("Final Balance ($)", f"{capital * balance:,.1f}")
col3.metric("Status", daily_df['Action'].iloc[-1] if not daily_df.empty else "None")

st.divider()
st.subheader(f"📊 جدول معاملات از {start_dt} تا {end_dt}")

def style_action(val):
    colors = {'BUY': '#2ecc71', 'EXIT': '#e74c3c', 'HOLD': '#3498db', 'WAIT': '#95a5a6'}
    return f'background-color: {colors.get(val, "white")}; color: white; font-weight: bold'

if not daily_df.empty:
    st.dataframe(
        daily_df.sort_index(ascending=False)
        .style.map(style_action, subset=['Action'])
        .format({"PnL_Trade": "{:+.2f}%", "Close": "{:,.1f}"}),
        use_container_width=True,
        height=600
    )
else:
    st.info("دیتایی در این بازه یافت نشد. لطفاً بازه زمانی را تغییر دهید.")
