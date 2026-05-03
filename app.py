import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

st.set_page_config(layout="wide", page_title="BTC Whale PRO")

# ======================
# SIDEBAR & SETTINGS
# ======================
st.sidebar.title("⚙️ Settings")
capital = st.sidebar.number_input("💰 Capital ($)", 100, 1000000, 1000)
fee = st.sidebar.slider("💸 Fee (%)", 0.0, 0.5, 0.1) / 100
risk_per_trade = st.sidebar.slider("⚠️ Risk (%)", 0.1, 5.0, 1.0) / 100

# دیتای 2023 به بعد
start_date_input = st.sidebar.date_input("📅 Start", datetime(2023, 1, 1))
end_date_input = st.sidebar.date_input("📅 End", datetime.now())

start_dt = pd.to_datetime(start_date_input)
end_dt = pd.to_datetime(end_date_input)

# ======================
# CORE DATA ENGINE (Multi-Year)
# ======================
@st.cache_data(ttl=86400)
def fetch_deep_data(symbol, interval, s_dt, e_dt):
    base_url = "https://api.binance.com/api/v3/klines"
    all_klines = []
    current_ts = int(s_dt.timestamp() * 1000)
    final_ts = int(e_dt.timestamp() * 1000)
    
    p_bar = st.sidebar.progress(0)
    p_text = st.sidebar.empty()
    
    with requests.Session() as session:
        while current_ts < final_ts:
            params = {"symbol": symbol, "interval": interval, "startTime": current_ts, "limit": 1000}
            try:
                res = session.get(base_url, params=params, timeout=15)
                if res.status_code != 200: 
                    time.sleep(2)
                    continue
                data = res.json()
                if not data: break
                
                all_klines.extend(data)
                current_ts = data[-1][0] + 1
                
                percent = min(1.0, (current_ts - int(s_dt.timestamp()*1000)) / (final_ts - int(s_dt.timestamp()*1000)))
                p_bar.progress(percent)
                p_text.text(f"📥 Loading: {pd.to_datetime(current_ts, unit='ms').date()}")
            except:
                time.sleep(1)
                continue
                
    if not all_klines: return pd.DataFrame()
    
    df = pd.DataFrame(all_klines).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    p_text.success("✅ Data Loaded!")
    return df.astype(float)

raw_df = fetch_deep_data("BTCUSDT", "1h", start_dt, end_dt)

if raw_df.empty:
    st.warning("🔄 در حال دریافت دیتا... سایدبار را چک کنید.")
    st.stop()

# ======================
# STRATEGY LOGIC
# ======================
df = raw_df.copy()
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
        # Exit logic
        if row["Open"] <= sl_p or row["Low"] <= sl_p or row["Close"] < row["EMA50"]:
            exit_p = (sl_p if (row["Open"] <= sl_p or row["Low"] <= sl_p) else next_open) * (1 - fee)
            balance += exit_p * units
            balance -= exit_p * units * fee
            in_pos = False
            units = 0

# ======================
# ANALYTICS & DASHBOARD
# ======================
equity_df = pd.DataFrame({"Strategy": equity}, index=df.index)
daily = equity_df.resample("D").last().ffill()

first_price = df["Close"].iloc[0]
daily["HODL"] = (pd.DataFrame(df["Close"]).resample("D").last().ffill()["Close"] / first_price) * capital

daily["Daily %"] = daily["Strategy"].pct_change().fillna(0) * 100
daily["HODL %"] = daily["HODL"].pct_change().fillna(0) * 100
daily["Daily PnL $"] = daily["Strategy"].diff().fillna(0)

# --- UI ---
st.title("🐋 BTC Whale PRO (Deep Backtest)")
c1, c2, c3 = st.columns(3)
c1.metric("Final Balance", f"${daily['Strategy'].iloc[-1]:,.0f}", f"{((daily['Strategy'].iloc[-1]/capital)-1)*100:.1f}%")
c2.metric("HODL Balance", f"${daily['HODL'].iloc[-1]:,.0f}", f"{((daily['HODL'].iloc[-1]/capital)-1)*100:.1f}%")
c3.metric("Data Points", f"{len(df):,}")

st.line_chart(daily[["Strategy", "HODL"]])

# --- Table ---
# استفاده از map به جای applymap برای سازگاری با پانداهای جدید
def color_pnl(val):
    if isinstance(val, (int, float)):
        color = 'lime' if val > 0 else 'red' if val < 0 else 'gray'
        return f'color: {color}'
    return ''

st.subheader("📅 Daily Performance Log")
st.dataframe(
    daily.sort_index(ascending=False)
    .style.map(color_pnl, subset=["Daily %", "HODL %"])
    .format("{:,.1f}$", subset=["Strategy", "HODL", "Daily PnL $"])
    .format("{:+,.2f}%", subset=["Daily %", "HODL %"]),
    use_container_width=True
)
