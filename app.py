import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

st.set_page_config(layout="wide", page_title="BTC Whale PRO")

# ======================
# SIDEBAR
# ======================
st.sidebar.title("⚙️ Binance Settings")
capital = st.sidebar.number_input("💰 Capital ($)", 100, 1000000, 1000)
fee = st.sidebar.slider("💸 Fee (%)", 0.0, 0.5, 0.1) / 100
risk_per_trade = st.sidebar.slider("⚠️ Risk (%)", 0.1, 5.0, 1.0) / 100

start_date_input = st.sidebar.date_input("📅 Start", datetime(2023, 1, 1))
end_date_input = st.sidebar.date_input("📅 End", datetime.now())

# ======================
# BINANCE DEEP FETCH (Stable Loop)
# ======================
@st.cache_data(ttl=86400)
def fetch_binance_history(symbol, interval, s_date, e_date):
    url = "https://api.binance.com/api/v3/klines"
    all_klines = []
    
    current_ts = int(pd.to_datetime(s_date).timestamp() * 1000)
    final_ts = int(pd.to_datetime(e_date).timestamp() * 1000)
    
    # Progress UI
    p_bar = st.sidebar.progress(0)
    p_text = st.sidebar.empty()
    
    with requests.Session() as session:
        while current_ts < final_ts:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_ts,
                "limit": 1000
            }
            try:
                res = session.get(url, params=params, timeout=15)
                
                if res.status_code == 429: # Rate limit hit
                    p_text.warning("⚠️ Binance limit! Waiting 10s...")
                    time.sleep(10)
                    continue
                
                data = res.json()
                if not data: break
                
                all_klines.extend(data)
                current_ts = data[-1][0] + 1
                
                # Update progress
                progress = min(1.0, (current_ts - int(pd.to_datetime(s_date).timestamp()*1000)) / (final_ts - int(pd.to_datetime(s_date).timestamp()*1000)))
                p_bar.progress(progress)
                p_text.info(f"📥 Downloading: {pd.to_datetime(current_ts, unit='ms').date()}")
                
                # برای جلوگیری از بن شدن، یک وقفه بسیار کوتاه
                time.sleep(0.1)
                
            except Exception as e:
                p_text.error(f"Error: {str(e)}")
                time.sleep(2)
                continue
                
    if not all_klines: return pd.DataFrame()
    
    df = pd.DataFrame(all_klines).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    p_text.success("✅ Data Fully Loaded!")
    return df.astype(float)

# بارگذاری دیتا
df_raw = fetch_binance_history("BTCUSDT", "1h", start_date_input, end_date_input)

if df_raw.empty:
    st.error("دیتا از بایننس دریافت نشد. اتصال اینترنت را چک کنید.")
    st.stop()

# ======================
# STRATEGY & LOGIC
# ======================
df = df_raw.copy()
df["EMA50"] = df["Close"].ewm(span=50).mean()
df["H_24"] = df["High"].rolling(24).max().shift(1)
df["L_24"] = df["Low"].rolling(24).min().shift(1)
df = df.dropna()

balance = capital
equity = []
in_pos = False
entry_p = sl_p = units = 0

for i in range(len(df)-1):
    row = df.iloc[i]
    next_open = df.iloc[i+1]["Open"]
    
    curr_val = balance + ((row["Close"] - entry_p) * units if in_pos else 0)
    equity.append(curr_val)

    if not in_pos:
        if row["Close"] > row["H_24"] and row["Close"] > row["EMA50"]:
            entry_p = next_open * (1 + fee)
            sl_p = row["L_24"]
            dist = entry_p - sl_p
            if dist > 0:
                risk_amt = balance * risk_per_trade
                units = min(risk_amt / dist, (balance * 0.95) / entry_p)
                balance -= entry_p * units * fee
                in_pos = True
    else:
        if row["Open"] <= sl_p or row["Low"] <= sl_p or row["Close"] < row["EMA50"]:
            exit_p = (sl_p if (row["Open"] <= sl_p or row["Low"] <= sl_p) else next_open) * (1 - fee)
            balance += exit_p * units
            balance -= exit_p * units * fee
            in_pos = False
            units = 0

# ======================
# DASHBOARD
# ======================
equity_df = pd.DataFrame({"Strategy": equity}, index=df.index)
daily = equity_df.resample("D").last().ffill()

# HODL Calculation
first_price = df["Close"].iloc[0]
daily["HODL"] = (pd.DataFrame(df["Close"]).resample("D").last().ffill()["Close"] / first_price) * capital
daily["Daily %"] = daily["Strategy"].pct_change().fillna(0) * 100

st.title("🐋 BTC Whale PRO")
st.subheader(f"Strategy Performance: {start_date_input} to {end_date_input}")

c1, c2 = st.columns(2)
c1.metric("Strategy Final", f"${daily['Strategy'].iloc[-1]:,.0f}")
c2.metric("HODL Final", f"${daily['HODL'].iloc[-1]:,.0f}")

st.line_chart(daily[["Strategy", "HODL"]])

st.subheader("📅 Daily Performance Table")
st.dataframe(daily.sort_index(ascending=False), use_container_width=True)
