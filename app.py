import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

st.set_page_config(layout="wide", page_title="BTC Whale PRO | Deep History")

# ======================
# SIDEBAR
# ======================
st.sidebar.title("⚙️ Strategy Settings")

capital = st.sidebar.number_input("💰 Initial Capital ($)", 100, 1000000, 1000)
fee = st.sidebar.slider("💸 Exchange Fee (%)", 0.0, 0.5, 0.1) / 100
risk_per_trade = st.sidebar.slider("⚠️ Risk Per Trade (%)", 0.1, 5.0, 1.0) / 100

# بازه زمانی گسترده
start_date_input = st.sidebar.date_input("📅 Start Date", datetime(2023, 1, 1))
end_date_input = st.sidebar.date_input("📅 End Date", datetime.now())

# تبدیل به Timestamp برای بایننس
start_dt = pd.to_datetime(start_date_input)
end_dt = pd.to_datetime(end_date_input)

# ======================
# DEEP DATA ENGINE (Historical Loop)
# ======================
@st.cache_data(ttl=86400)
def fetch_historical_data(symbol, interval, start_ts_dt, end_ts_dt):
    url = "https://api.binance.com/api/v3/klines"
    all_data = []
    
    current_ts = int(start_ts_dt.timestamp() * 1000)
    final_ts = int(end_ts_dt.timestamp() * 1000)
    
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    with requests.Session() as session:
        while current_ts < final_ts:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_ts,
                "limit": 1000
            }
            try:
                res = session.get(url, params=params, timeout=10)
                data = res.json()
                if not data or len(data) == 0: break
                
                all_data.extend(data)
                current_ts = data[-1][0] + 1
                
                # نمایش وضعیت دانلود
                prog_val = min(1.0, (current_ts - int(start_ts_dt.timestamp() * 1000)) / (final_ts - int(start_ts_dt.timestamp() * 1000)))
                progress_bar.progress(prog_val)
                status_text.text(f"📥 Loading: {pd.to_datetime(current_ts, unit='ms').date()}")
            except:
                time.sleep(1)
                continue
                
    if not all_data: return pd.DataFrame()
    
    df = pd.DataFrame(all_data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    return df.astype(float)

# بارگذاری دیتا
raw_df = fetch_historical_data("BTCUSDT", "1h", start_dt, end_dt)

if raw_df.empty:
    st.error("❌ دیتایی یافت نشد. بازه زمانی را چک کنید.")
    st.stop()

df = raw_df.copy()

# ======================
# INDICATORS
# ======================
df["EMA50"] = df["Close"].ewm(span=50).mean()
df["H_24"] = df["High"].rolling(24).max().shift(1)
df["L_24"] = df["Low"].rolling(24).min().shift(1)
df = df.dropna()

# ======================
# ENGINE
# ======================
balance = capital
equity = []
equity_time = []
in_pos = False
entry_p = sl_p = units = 0

for i in range(len(df)-1):
    row = df.iloc[i]
    next_open = df.iloc[i+1]["Open"]
    
    curr_val = balance + ((row["Close"] - entry_p) * units if in_pos else 0)
    equity.append(curr_val)
    equity_time.append(df.index[i])

    if not in_pos:
        if row["Close"] > row["H_24"] and row["Close"] > row["EMA50"]:
            entry_p = next_open * (1 + fee)
            sl_p = row["L_24"]
            dist = entry_p - sl_p
            if dist > 0:
                risk_amt = balance * risk_per_trade
                units = min(risk_amt / dist, (balance * 0.95) / entry_p) # Safe leverage limit
                balance -= entry_p * units * fee
                in_pos = True
    else:
        stop_hit = row["Open"] <= sl_p or row["Low"] <= sl_p
        if stop_hit or row["Close"] < row["EMA50"]:
            exit_p = (sl_p if stop_hit else next_open) * (1 - fee)
            balance += exit_p * units
            balance -= exit_p * units * fee
            in_pos = False
            units = 0

# ======================
# ANALYTICS & TABLES
# ======================
equity_df = pd.DataFrame({"Strategy": equity}, index=pd.to_datetime(equity_time))
equity_df = equity_df[~equity_df.index.duplicated(keep='last')].sort_index()

full_days = pd.date_range(start=df.index.min(), end=df.index.max(), freq="D")
daily = equity_df.resample("D").last().reindex(full_days).ffill()

daily["Daily PnL $"] = daily["Strategy"].diff().fillna(0)
daily["Daily %"] = daily["Strategy"].pct_change().fillna(0) * 100

# HODL Calc
first_price = df["Close"].iloc[0]
daily["HODL"] = (pd.DataFrame(df["Close"]).resample("D").last().reindex(full_days).ffill()["Close"] / first_price) * capital
daily["HODL %"] = daily["HODL"].pct_change().fillna(0) * 100

# ======================
# UI & VISUALS
# ======================
st.title("🐋 BTC Whale PRO")
st.info(f"Backtest Period: {df.index.min().date()} to {df.index.max().date()}")

m1, m2, m3 = st.columns(3)
m1.metric("Final Balance", f"${daily['Strategy'].iloc[-1]:,.2f}")
m2.metric("HODL Comparison", f"${daily['HODL'].iloc[-1]:,.2f}")
m3.metric("Total Trades", "Analyzed")

st.line_chart(daily[["Strategy", "HODL"]])

# جدول با استایل جدید
st.subheader("📅 Daily Performance Log")

def color_negative_red(val):
    color = 'lime' if val > 0 else 'red' if val < 0 else 'white'
    return f'color: {color}'

st.dataframe(
    daily.sort_index(ascending=False)
    .style.applymap(color_negative_red, subset=["Daily %", "HODL %"])
    .format({
        "Strategy":"{:,.0f}$", "Daily PnL $":"{:+,.0f}$", 
        "Daily %":"{:+.2f}%", "HODL":"{:,.0f}$", "HODL %":"{:+.2f}%"
    }),
    use_container_width=True
)
