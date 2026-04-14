import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

# 1. Page Configuration
st.set_page_config(layout="wide", page_title="Professional Trading Dashboard")

# 2. Data Fetching Function
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 200}
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "close_time","qav","trades","tbbav","tbqav","ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        df = df.astype(float)
        return df
    except Exception:
        return pd.DataFrame()

def get_time_remaining():
    now = datetime.utcnow()
    next_4h = (now.hour // 4 + 1) * 4
    if next_4h >= 24:
        target_t = datetime(now.year, now.month, now.day) + timedelta(days=1)
    else:
        target_t = datetime(now.year, now.month, now.day, next_4h)
    remaining = target_t - now
    return str(remaining).split(".")[0]

# 3. Sidebar Settings
st.sidebar.title("Configuration")
initial_capital = st.sidebar.number_input("Initial Capital ($)", value=1000.0, step=100.0)
start_date = st.sidebar.date_input("Start Date", value=date(2024, 1, 1))
fee_rate = st.sidebar.slider("CoinEx Fee (%)", 0.0, 0.5, 0.2) / 100

# 4. Processing Logic
df = get_live_data()

if not df.empty:
    df_filtered = df[df.index.date >= start_date].copy()
    
    if df_filtered.empty:
        st.warning("No data found for selected range.")
    else:
        # Initialize Trading Columns
        df_filtered["Signal"] = "WAIT"
        df_filtered["Entry"] = np.nan
        df_filtered["Target"] = np.nan
        df_filtered["StopLoss"] = np.nan
        df_filtered["Confidence"] = 0.0
        df_filtered["PnL_Percent"] = 0.0

        best_multiplier = 1.0
        total_bal_multiplier = 1.0
        trade_count = 0

        # Loop through Data
        for i in range(2, len(df_filtered)):
            p1, p2 = df_filtered.iloc[i-1], df_filtered.iloc[i-2]
            
            # Strategy Condition
            if p1["Close"] > p2["Close"]:
                trade_count += 1
                
                # FIXED Values (Locks on Candle Open)
                fixed_entry = df_filtered["Open"].iloc[i]
                fixed_target = fixed_entry + ((p1["Close"] - p2["Close"]) * best_multiplier)
                fixed_sl = p1["Low"]
                
                # Live PnL Calculation
                curr_close = df_filtered["Close"].iloc[i]
                raw_pnl = (curr_close - fixed_entry) / fixed_entry
                
                # COMPOUND PNL WITH FEES: (1 + r) * (1 - fee)^2 - 1
                net_pnl = (1 + raw_pnl) * (1 - fee_rate)**2 - 1
                
                # Update DataFrame Row
                df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "BUY"
                df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = fixed_entry
                df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = fixed_target
                df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = fixed_sl
                
                # Agent Learning Logic (Reward/Penalty)
                conf = min(0.98, 0.65 + (best_multiplier * 0.1)) if net_pnl > 0 else max(0.40, 0.60 - abs(best_multiplier * 0.05))
                df_filtered.iloc[i, df_filtered.columns.get_loc("Confidence")] = conf
                df_filtered.iloc[i, df_filtered.columns.get_loc("PnL_Percent")] = net_pnl * 100
                
                # Update Learning Multiplier (only for closed candles)
                if i < len(df_filtered) - 1:
                    if net_pnl > 0: best_multiplier = min(2.5, best_multiplier + 0.05)
                    else: best_multiplier = max(0.5, best_multiplier - 0.1)

                # Compound Interest Calculation
                total_bal_multiplier *= (1 + net_pnl)

        # 5. Dashboard Header
        curr_p = df_filtered["Close"].iloc[-1]
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"<div style='background-color:#1e1e1e;padding:15px;border-radius:10px;border-left:5px solid #4CAF50;'><p style='color:#888;margin:0;'>BTCUSDT PRICE</p><h1 style='margin:0; color:white;'>${curr_p:,.2f}</h1></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='background-color:#1e1e1e;padding:15px;border-radius:10px;border-left:5px solid #ffca28;'><p style='color:#888;margin:0;'>NEXT CANDLE</p><h1 style='margin:0;color:#ffca28;'>{get_time_remaining()}</h1></div>", unsafe_allow_html=True)

        st.write("")
        final_balance = initial_capital * total_bal_multiplier
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current Balance", f"${final_balance:,.2f}")
        m2.metric("Net Profit", f"${final_balance - initial_capital:,.2f}", delta=f"{(total_bal_multiplier-1)*100:.2f}%")
        m3.metric("Total Trades", f"{trade_count}")
        m4.metric("Avg. PnL per Trade", f"{( (total_bal_multiplier**(1/trade_count))-1 )*100:.2f}%" if trade_count > 0 else "0%")

        st.divider()

        # 6. Trade Logs Table
        st.subheader("Trading Logs & Predictions")
        view_df = df_filtered.sort_index(ascending=False).copy()
        
        st.dataframe(
            view_df,
            use_container_width=True,
            height=450,
            column_config={
                "Signal": "Signal",
                "Confidence": st.column_config.ProgressColumn("Confidence", format="%.0f%%", min_value=0.0, max_value=1.0),
                "Entry": st.column_config.NumberColumn("Entry", format="$%.1f"),
                "Target": st.column_config.NumberColumn("Target (TP)", format="$%.1f"),
                "StopLoss": st.column_config.NumberColumn("Stop (SL)", format="$%.1f"),
                "PnL_Percent": st.column_config.NumberColumn("Net PnL %", format="%.2f%%"),
                "Close": st.column_config.NumberColumn("Exit/Current", format="$%.1f"),
                "Open": None, "High": None, "Low": None
            }
        )

# Auto-Refresh Page every 20 seconds
st.markdown("<script>setTimeout(function(){window.location.reload();}, 20000);</script>", unsafe_allow_html=True)
