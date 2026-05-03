import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime

# =================================================================
# 1. تنظیمات اولیه و مدیریت خطا (API & Data)
# =================================================================
st.set_page_config(layout="wide", page_title="BTC Institutional Master 2026")

@st.cache_data(ttl=600)
def fetch_institutional_data(symbol="BTCUSDT", interval="1h"):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": 1000}
        # اضافه کردن timeout برای جلوگیری از خطای اتصال در لاگ
        res = requests.get(url, params=params, timeout=15).json()
        df = pd.DataFrame(res).iloc[:, :6]
        df.columns = ["Time", "Open", "High", "Low", "Close", "Volume"]
        df["Time"] = pd.to_datetime(df["Time"], unit="ms")
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# =================================================================
# 2. مهندسی ویژگی‌ها (God Whale Logic)
# =================================================================
def apply_indicators(df):
    if df.empty: return df
    
    # الف) True 4H Multi-Timeframe
    df_4h = df.resample('4H').agg({'Close': 'last'})
    df_4h['MA_4H'] = df_4h['Close'].rolling(50).mean()
    df = df.merge(df_4h[['MA_4H']], left_index=True, right_index=True, how='left').ffill()

    # ب) Adaptive Volatility
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(span=14).mean()
    df['Trend_Score'] = (df['Close'] - df['MA_4H']) / df['ATR']
    
    # ج) Structure & Momentum
    df['Structure_Low'] = df['Low'].rolling(10).min().shift(1)
    df['MA_Fast'] = df['Close'].rolling(5).mean()
    df['H_24'] = df['High'].rolling(24).max().shift(1)
    
    return df

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
    
    for i in range(100, len(df) - 1):
        row = df.iloc[i]
        h, day = df.index[i].hour, df.index[i].dayofweek
        vol_factor = row['ATR'] / row['Close']
        
        # ۱. Adaptive Kill Switch (ثبت لحظه‌ای بالانس)
        dynamic_ks = 0.05 if vol_factor > 0.02 else 0.10
        curr_val = balance + ((row['Close'] - entry_p) * units if in_pos else 0)
        equity.append(curr_val)
        peak = max(peak, curr_val)
        
        if (peak - curr_val) / peak > dynamic_ks:
            break 

        if not in_pos:
            # ۲. Entry: Impulse + Continuation + Time Edge
            is_mon_to_wed = day in [0, 1, 2] # دوشنبه تا چهارشنبه
            is_session = h in [8, 9, 10, 11, 14, 15, 16, 17]
            
            breakout = row['Close'] > row['H_24']
            impulse = abs(row['Close'] - row['Open']) > 0.6 * (row['High'] - row['Low'])
            continuation = row['Close'] > df.iloc[i-1]['High']
            
            if is_mon_to_wed and is_session and breakout and impulse and continuation:
                # Smooth Adaptive SL
                atr_mult = np.clip(2 + (row['Trend_Score'] * 0.8), 2.2, 4.0)
                entry_p = row['Close'] * 1.001 # 0.1% Slippage
                sl_p = entry_p - (row['ATR'] * atr_mult)
                
                # Risk 0.5%
                units = (balance * 0.005) / (entry_p - sl_p)
                balance -= (entry_p * units * 0.001) # Fee
                in_pos, pyramid_level = True, 0
                trades.append({"Time": df.index[i], "Action": "ENTRY", "Price": entry_p})
        
        else:
            # ۳. Multi-Level Pyramiding & Profit Protection
            profit_r = (row['Close'] - entry_p) / row['ATR']
            
            if profit_r > 2.0: sl_p = max(sl_p, entry_p) # Lock BE
            
            # Pyramid Logic
            pyramid_steps = {1: (1.5, 0.5), 2: (2.5, 0.3)}
            next_step = pyramid_level + 1
            if next_step in pyramid_steps:
                r_target, u_mult = pyramid_steps[next_step]
                if profit_r > r_target:
                    add_u = units * u_mult
                    # Risk Cap 2.5%
                    if ((row['Close'] - sl_p) * (units + add_u)) < (balance * 0.025):
                        balance -= (row['Close'] * add_u * 1.001)
                        entry_p = ((entry_p * units) + (row['Close'] * add_u)) / (units + add_u)
                        units += add_u
                        pyramid_level = next_step
                        trades.append({"Time": df.index[i], "Action": f"PYRAMID_{next_step}R", "Price": row['Close']})

            # ۴. Exit: Structure & Momentum
            if row['Low'] <= sl_p or row['Close'] < row['MA_Fast'] or row['Low'] < row['Structure_Low']:
                exit_raw = sl_p if row['Low'] <= sl_p else df.iloc[i+1]['Open']
                exit_p = exit_raw * 0.999
                balance += (exit_p * units)
                balance -= (exit_p * units * 0.001)
                trades.append({"Time": df.index[i], "Action": "EXIT", "Price": exit_p, "PnL%": ((exit_p/entry_p)-1)*100})
                in_pos, units = False, 0

    return pd.DataFrame(trades), equity, balance

# =================================================================
# 4. رابط کاربری (Streamlit UI 2026 Ready)
# =================================================================
st.title("🐋 BTC God Whale Strategy (Professional Edition)")

with st.sidebar:
    st.header("⚙️ Risk Management")
    initial_balance = st.number_input("Starting Capital ($)", value=1000.0)
    st.info("Strategy uses 0.5% dynamic risk per trade with adaptive SL.")

df_raw = fetch_institutional_data()
if not df_raw.empty:
    df_p = apply_indicators(df_raw)
    trades_df, equity_curve, final_balance = run_whale_backtest(df_p, initial_balance)

    # نمایش متریک‌های اصلی
    c1, c2, c3 = st.columns(3)
    c1.metric("Final Balance", f"${final_balance:,.2f}")
    if not trades_df.empty and 'PnL%' in trades_df.columns:
        exits = trades_df.dropna(subset=['PnL%'])
        wr = (exits['PnL%'] > 0).mean() * 100
        c2.metric("Win Rate", f"{wr:.1f}%")
        c3.metric("Net Profit", f"{((final_balance/initial_balance)-1)*100:.2f}%")

        # نمودار رشد سرمایه با استانداردهای ۲۰۲۶
        st.subheader("📈 Equity Curve")
        st.line_chart(equity_curve, width="stretch")

        # مونت کارلو
        st.subheader("🎲 Monte Carlo Survival Paths")
        pnls = exits['PnL%'].values
        fig_mc = go.Figure()
        for _ in range(30):
            path = np.insert(1 + (np.random.choice(pnls, len(pnls)) / 100), 0, initial_balance).cumprod()
            fig_mc.add_trace(go.Scatter(y=path, mode='lines', line=dict(width=0.8), opacity=0.4, showlegend=False))
        fig_mc.update_layout(xaxis_title="Trades", yaxis_title="Capital ($)")
        st.plotly_chart(fig_mc, width="stretch")

        # لاگ تریدها
        st.subheader("📝 Trade History")
        st.dataframe(trades_df.sort_values("Time", ascending=False), width="stretch")
    else:
        st.warning("No trades found in the current period. Market might be in 'No-Trade' regime.")
else:
    st.error("Failed to load data. Please check connection.")
