import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime

# =================================================================
# 1. تنظیمات اولیه و دریافت دیتا (با هندل کردن خطای Scalar)
# =================================================================
st.set_page_config(layout="wide", page_title="BTC Institutional Master 2026")

@st.cache_data(ttl=300)
def fetch_institutional_data(symbol="BTCUSDT", interval="1h"):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": 700}
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        # بررسی اینکه آیا خروجی واقعاً یک لیست است (لیست کندل‌ها)
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data).iloc[:, :6]
            df.columns = ["Time", "Open", "High", "Low", "Close", "Volume"]
            df["Time"] = pd.to_datetime(df["Time"], unit="ms")
            df.set_index("Time", inplace=True)
            return df.astype(float)
        else:
            # اگر بایننس خطا برگردانده باشد (مثلاً محدودیت IP)
            st.error(f"Binance API Error: {data}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Connection/Data Error: {e}")
        return pd.DataFrame()

# =================================================================
# 2. مهندسی ویژگی‌ها (God Whale Indicators)
# =================================================================
def apply_indicators(df):
    if df.empty: return df
    
    # الف) True 4H Multi-Timeframe
    df_4h = df.resample('4H').agg({'Close': 'last'})
    df_4h['MA_4H'] = df_4h['Close'].rolling(50).mean()
    df = df.merge(df_4h[['MA_4H']], left_index=True, right_index=True, how='left').ffill()

    # ب) Adaptive Volatility & Trend Score
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(span=14).mean()
    df['Trend_Score'] = (df['Close'] - df['MA_4H']) / df['ATR']
    
    # ج) Structure & Fast Momentum
    df['Structure_Low'] = df['Low'].rolling(10).min().shift(1)
    df['MA_Fast'] = df['Close'].rolling(5).mean()
    df['H_24'] = df['High'].rolling(24).max().shift(1)
    
    return df.dropna(subset=['MA_4H', 'ATR'])

# =================================================================
# 3. موتور استراتژی (Elite Execution Engine)
# =================================================================
def run_whale_backtest(df, initial_cap=1000.0):
    balance = initial_cap
    equity = []
    trades = []
    in_pos = False
    pyramid_level = 0
    peak = initial_cap
    
    entry_p, sl_p, units = 0, 0, 0
    
    for i in range(1, len(df) - 1):
        row = df.iloc[i]
        h, day = df.index[i].hour, df.index[i].dayofweek
        
        # ۱. Adaptive Kill Switch
        vol_factor = row['ATR'] / row['Close']
        dynamic_ks = 0.05 if vol_factor > 0.02 else 0.10
        curr_val = balance + ((row['Close'] - entry_p) * units if in_pos else 0)
        equity.append(curr_val)
        peak = max(peak, curr_val)
        
        if (peak - curr_val) / peak > dynamic_ks: break 

        if not in_pos:
            # ۲. Entry Logic (Only Session + Mon-Wed)
            is_mon_to_wed = day in [0, 1, 2]
            is_session = h in [8, 9, 10, 11, 14, 15, 16, 17]
            
            breakout = row['Close'] > row['H_24']
            impulse = abs(row['Close'] - row['Open']) > 0.6 * (row['High'] - row['Low'])
            
            if is_mon_to_wed and is_session and breakout and impulse:
                atr_mult = np.clip(2 + (row['Trend_Score'] * 0.8), 2.2, 4.0)
                entry_p = row['Close'] * 1.001
                sl_p = entry_p - (row['ATR'] * atr_mult)
                
                # Risk 0.5%
                risk_amt = balance * 0.005
                units = risk_amt / (entry_p - sl_p)
                balance -= (entry_p * units * 0.001)
                in_pos, pyramid_level = True, 0
                trades.append({"Time": df.index[i], "Action": "ENTRY", "Price": entry_p})
        
        else:
            # ۳. Multi-Level Pyramiding & Profit Protection
            profit_r = (row['Close'] - entry_p) / row['ATR']
            if profit_r > 2.0: sl_p = max(sl_p, entry_p) 
            
            # Pyramid
            if profit_r > 1.5 and pyramid_level == 0:
                add_u = units * 0.5
                if ((row['Close'] - sl_p) * (units + add_u)) < (balance * 0.025):
                    balance -= (row['Close'] * add_u * 1.001)
                    entry_p = ((entry_p * units) + (row['Close'] * add_u)) / (units + add_u)
                    units += add_u
                    pyramid_level = 1
                    trades.append({"Time": df.index[i], "Action": "PYRAMID_1.5R", "Price": row['Close']})

            # ۴. Exit
            if row['Low'] <= sl_p or row['Close'] < row['MA_Fast'] or row['Low'] < row['Structure_Low']:
                exit_p = sl_p if row['Low'] <= sl_p else df.iloc[i+1]['Open']
                exit_p *= 0.999
                balance += (exit_p * units)
                balance -= (exit_p * units * 0.001)
                trades.append({"Time": df.index[i], "Action": "EXIT", "Price": exit_p, "PnL%": ((exit_p/entry_p)-1)*100})
                in_pos, units = False, 0

    return pd.DataFrame(trades), equity, balance

# =================================================================
# 4. رابط کاربری (UI)
# =================================================================
st.title("🐋 BTC God Whale Strategy (Professional Edition)")

df_raw = fetch_institutional_data()
if not df_raw.empty:
    df_p = apply_indicators(df_raw)
    trades_df, equity_curve, final_balance = run_whale_backtest(df_p)

    c1, c2, c3 = st.columns(3)
    c1.metric("Final Balance", f"${final_balance:,.2f}")
    
    if not trades_df.empty:
        exits = trades_df.dropna(subset=['PnL%'])
        wr = (exits['PnL%'] > 0).mean() * 100
        c2.metric("Win Rate", f"{wr:.1f}%")
        c3.metric("Net Profit", f"{((final_balance/1000)-1)*100:.2f}%")

        st.subheader("📈 Equity Curve")
        st.line_chart(equity_curve, width="stretch")

        st.subheader("📝 Trade History")
        st.dataframe(trades_df.sort_values("Time", ascending=False), width="stretch")
    else:
        st.info("Market is currently out of Whale Trading Parameters (No Trades Found).")
else:
    st.warning("Please check your internet connection or Binance API status.")
