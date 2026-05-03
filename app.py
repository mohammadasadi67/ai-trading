import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import plotly.graph_objects as go
from datetime import datetime

# تنظیمات صفحه
st.set_page_config(layout="wide", page_title="BTC Spot Whale PRO | Dashboard")

# ======================
# DATA ENGINE
# ======================
@st.cache_data(ttl=600)
def fetch_data():
    urls = ["https://api.binance.com/api/v3/klines", "https://data-api.binance.vision/api/v3/klines"]
    params = {"symbol": "BTCUSDT", "interval": "1h", "limit": 1000}
    for url in urls:
        for _ in range(3):
            try:
                res = requests.get(url, params=params, timeout=10)
                if res.status_code != 200: continue
                data = res.json()
                if not isinstance(data, list) or len(data) == 0: continue
                df = pd.DataFrame(data).iloc[:, :6]
                df.columns = ["Time","Open","High","Low","Close","Volume"]
                df["Time"] = pd.to_datetime(df["Time"], unit="ms")
                df.set_index("Time", inplace=True)
                return df.astype(float)
            except: time.sleep(1)
    return pd.DataFrame()

# ======================
# INDICATORS
# ======================
def add_indicators(df):
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    # 4H Context
    df_4h = df.resample("4h").agg({"Close": "last"})
    df_4h["MA_4H"] = df_4h["Close"].rolling(50).mean()
    df = df.join(df_4h["MA_4H"], how="left").ffill()
    # ATR & Trend
    tr = pd.concat([df["High"] - df["Low"], abs(df["High"] - df["Close"].shift()), abs(df["Low"] - df["Close"].shift())], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(span=14).mean()
    df["Trend_Score"] = (df["Close"] - df["MA_4H"]) / df["ATR"]
    # Levels
    df["Structure_Low"] = df["Low"].rolling(10).min().shift(1)
    df["MA_Fast"] = df["Close"].rolling(5).mean()
    df["H_24"] = df["High"].rolling(24).max().shift(1)
    return df.dropna().copy()

# ======================
# ENGINE
# ======================
def run_engine(df, capital, risk_per_trade, drawdown_limit):
    balance = capital
    equity = []
    trades = []
    in_pos, added = False, False
    peak = capital
    entry_p = sl_p = units = 0

    for i in range(100, len(df)-1):
        row = df.iloc[i]
        next_open = df.iloc[i+1]["Open"]
        curr_val = balance + ((row["Close"] - entry_p) * units if in_pos else 0)
        equity.append(curr_val)
        peak = max(peak, curr_val)

        if (peak - curr_val)/peak > drawdown_limit: break

        if not in_pos:
            hour, day = df.index[i].hour, df.index[i].dayofweek
            if hour in [8,9,10,11,14,15,16,17] and day in [0,1,2]:
                if row["Close"] > row["H_24"] and abs(row["Close"] - row["Open"]) > 0.6*(row["High"]-row["Low"]):
                    atr_mult = np.clip(2 + row["Trend_Score"]*0.8, 2.2, 4.0)
                    entry_p = row["Close"] * 1.001
                    sl_p = entry_p - row["ATR"] * atr_mult
                    if (entry_p - sl_p) > 0:
                        units = (balance * risk_per_trade) / (entry_p - sl_p)
                        balance -= entry_p * units * 0.001
                        in_pos, added = True, False
                        trades.append({"Time": df.index[i], "Action": "BUY", "Price": entry_p})
        else:
            profit_r = (row["Close"] - entry_p) / row["ATR"]
            if profit_r > 2: sl_p = max(sl_p, entry_p)
            if profit_r > 1.5 and not added:
                add_u = units * 0.5
                if (entry_p - sl_p) * (units + add_u) < balance * 0.02:
                    balance -= row["Close"] * add_u * 1.001
                    entry_p = ((entry_p * units + row["Close"] * add_u) / (units + add_u))
                    units += add_u
                    added = True
                    trades.append({"Time": df.index[i], "Action": "PYRAMID", "Price": row["Close"]})
            
            if row["Open"] <= sl_p or row["Low"] <= sl_p or row["Close"] < row["MA_Fast"] or row["Low"] < row["Structure_Low"]:
                exit_p = (sl_p if (row["Open"] <= sl_p or row["Low"] <= sl_p) else next_open) * 0.999
                balance += exit_p * units
                balance -= exit_p * units * 0.001
                trades.append({"Time": df.index[i], "Action": "EXIT", "Price": exit_p, "PnL%": ((exit_p/entry_p)-1)*100})
                in_pos, units = False, 0
    return pd.DataFrame(trades), equity, balance

# ======================
# SIDEBAR (تنظیمات سمت چپ)
# ======================
with st.sidebar:
    st.header("🏢 Strategy Lab")
    st.divider()
    init_cap = st.number_input("Initial Capital ($)", 100, 1000000, 1000)
    risk_pct = st.slider("Risk Per Trade (%)", 0.1, 2.0, 0.5) / 100
    kill_switch = st.slider("Drawdown Kill-Switch (%)", 5, 20, 8) / 100
    
    st.divider()
    st.subheader("📅 Time Filter")
    raw_df = fetch_data()
    if not raw_df.empty:
        min_date = raw_df.index.min().date()
        max_date = raw_df.index.max().date()
        start_date = st.date_input("Start Date", min_date)
        end_date = st.date_input("End Date", max_date)
    st.info("Institutional Grade Whale Strategy v3.0")

# ======================
# MAIN UI
# ======================
if raw_df.empty:
    st.error("❌ API Connection Failed")
    st.stop()

# اعمال فیلتر تاریخ و اندیکاتورها
filtered_df = raw_df.loc[str(start_date):str(end_date)]
processed_df = add_indicators(filtered_df)

trades, equity, final_bal = run_engine(processed_df, init_cap, risk_pct, kill_switch)

# --- Metric Bar ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Final Balance", f"${final_bal:,.2f}", f"{((final_bal/init_cap)-1)*100:.2f}%")

if not trades.empty and "PnL%" in trades.columns:
    exits = trades.dropna(subset=["PnL%"])
    wins = exits[exits["PnL%"] > 0]
    losses = exits[exits["PnL%"] <= 0]
    
    win_rate = len(wins) / len(exits) * 100 if len(exits) > 0 else 0
    
    c2.metric("Win Rate", f"{win_rate:.1f}%")
    c3.metric("Total Trades", len(exits))
    c4.metric("Avg Profit", f"{exits['PnL%'].mean():.2f}%")

    # --- Analytics Table ---
    st.divider()
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        st.subheader("📊 Performance Statistics")
        stats = {
            "Total Winners ✅": len(wins),
            "Total Losers ❌": len(losses),
            "Max Drawdown Limit": f"{kill_switch*100}%",
            "Initial Capital": f"${init_cap}",
            "Net Profit ($)": f"${final_bal - init_cap:,.2f}"
        }
        st.table(pd.Series(stats, name="Value"))

    with col_b:
        st.subheader("📈 Growth Curve")
        st.line_chart(equity)

    # --- Monte Carlo ---
    if len(exits) > 5:
        st.divider()
        st.subheader("🎲 Robustness Check (Monte Carlo)")
        pnls = exits["PnL%"].values
        fig = go.Figure()
        for _ in range(25):
            path = np.insert(1 + (np.random.choice(pnls, len(pnls))/100), 0, 1).cumprod() * init_cap
            fig.add_trace(go.Scatter(y=path, mode="lines", opacity=0.3, showlegend=False, line=dict(width=1)))
        fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

    # --- Trade Log ---
    st.divider()
    st.subheader("📝 Activity Log")
    st.dataframe(trades.sort_values("Time", ascending=False), use_container_width=True)

else:
    st.warning("No trades executed for this date range/parameters.")
