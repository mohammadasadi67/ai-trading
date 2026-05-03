import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(layout="wide", page_title="BTC Whale PRO: 2023-2026 Edition")

# ======================
# 1. DEEP DATA ENGINE (2023 READY)
# ======================
@st.cache_data(ttl=86400) # کش کردن دیتا برای ۲۴ ساعت
def fetch_deep_data(symbol="BTCUSDT", interval="4h", start_year=2023):
    all_klines = []
    # تبدیل سال ۲۰۲۳ به میلی‌ثانیه
    start_ts = int(datetime(start_year, 1, 1).timestamp() * 1000)
    end_ts = int(datetime.now().timestamp() * 1000)
    
    url = "https://api.binance.com/api/v3/klines"
    current_ts = start_ts
    
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    while current_ts < end_ts:
        params = {"symbol": symbol, "interval": interval, "startTime": current_ts, "limit": 1000}
        try:
            res = requests.get(url, params=params, timeout=15)
            data = res.json()
            if not data or len(data) == 0: break
            
            all_klines.extend(data)
            current_ts = data[-1][0] + 1
            
            # Update Progress
            progress = min(1.0, (current_ts - start_ts) / (end_ts - start_ts))
            progress_bar.progress(progress)
            status_text.text(f"📥 Loading: {pd.to_datetime(current_ts, unit='ms').date()}")
        except:
            time.sleep(1)
            continue
            
    df = pd.DataFrame(all_klines).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    return df.astype(float)

# ======================
# 2. INDICATORS (4H ANALYTICS)
# ======================
def add_indicators(df):
    df = df.copy()
    # 4H EMA for Institutional Trend
    df["EMA_50"] = df["Close"].ewm(span=50).mean()
    df["EMA_200"] = df["Close"].ewm(span=200).mean()
    
    # ATR for Volatility Stop
    tr = pd.concat([df["High"]-df["Low"], abs(df["High"]-df["Close"].shift()), abs(df["Low"]-df["Close"].shift())], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(span=14).mean()
    
    # Structure
    df["H_24"] = df["High"].rolling(12).max().shift(1) # 12 * 4h = 48h High
    df["L_24"] = df["Low"].rolling(12).min().shift(1)
    return df.dropna()

# ======================
# 3. ENGINE (4H EXECUTION)
# ======================
def run_engine(df, capital=1000):
    balance = capital
    equity = []
    trades = []
    in_pos = False
    entry_p = sl_p = units = 0

    for i in range(50, len(df)):
        row = df.iloc[i]
        curr_val = balance + ((row["Close"] - entry_p) * units if in_pos else 0)
        equity.append({"Time": df.index[i], "Equity": curr_val})

        if not in_pos:
            # Entry on 4H Breakout + Trend Alignment
            if row["Close"] > row["H_24"] and row["Close"] > row["EMA_50"]:
                entry_p = row["Close"] * 1.001
                sl_p = row["L_24"] # Stop at 48h Low
                
                risk_amt = balance * 0.01 # 1% Risk
                units = risk_amt / (entry_p - sl_p) if (entry_p > sl_p) else 0
                if units > 0:
                    balance -= entry_p * units * 0.001
                    in_pos = True
                    trades.append({"Time": df.index[i], "Action": "BUY", "Price": entry_p})
        else:
            # Exit on Structure Break or EMA Cross
            if row["Low"] <= sl_p or row["Close"] < row["EMA_50"]:
                exit_p = row["Close"] * 0.999
                balance += exit_p * units
                balance -= exit_p * units * 0.001
                trades.append({"Time": df.index[i], "Action": "SELL", "Price": exit_p, "PnL": (exit_p - entry_p) * units})
                in_pos, units = False, 0

    return pd.DataFrame(trades), pd.DataFrame(equity), balance

# ======================
# 4. DASHBOARD (DAILY REPORTING)
# ======================
st.sidebar.header("⚙️ Settings")
init_cap = st.sidebar.number_input("Capital ($)", value=1000)

raw_df = fetch_deep_data()
if not raw_df.empty:
    processed_df = add_indicators(raw_df)
    trades_df, equity_df, final_bal = run_engine(processed_df, init_cap)
    
    # --- Metrics ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Final Balance", f"${final_bal:,.2f}", f"{((final_bal/init_cap)-1)*100:.1f}%")
    
    # --- CHART ---
    st.subheader("📈 Performance (4H Analysis)")
    equity_df.set_index("Time", inplace=True)
    st.line_chart(equity_df["Equity"])

    # --- DAILY REPORT TABLE (گزینه دوم شما) ---
    st.subheader("📅 Daily Performance Table")
    if not equity_df.empty:
        # تبدیل دیتای ۴ ساعته به روزانه برای جدول
        daily_df = equity_df.resample('D').last()
        daily_df["Daily Return $"] = daily_df["Equity"].diff().fillna(0)
        daily_df["Return %"] = daily_df["Equity"].pct_change().fillna(0) * 100
        
        # نمایش جدول با فرمت زیبا
        st.dataframe(
            daily_df.sort_index(ascending=False).style.format({
                "Equity": "{:,.2f}$",
                "Daily Return $": "{:+,.2f}$",
                "Return %": "{:+.2f}%"
            }), 
            use_container_width=True
        )

    # --- TRADE LOG ---
    st.subheader("📝 Execution Log")
    st.dataframe(trades_df.sort_values("Time", ascending=False), use_container_width=True)
