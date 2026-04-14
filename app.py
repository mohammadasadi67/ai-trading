import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

# Page Configuration
st.set_page_config(layout="wide", page_title="RL Trading Panel")

# ======================
# Data Fetching
# ======================
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
    except Exception as e:
        st.error(f"Connection Error: {e}")
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

# ======================
# Sidebar & Settings
# ======================
st.sidebar.title("Settings")
initial_capital = st.sidebar.number_input("Initial Capital ($)", value=1000.0, step=100.0)
start_date = st.sidebar.date_input("Start Date", value=date(2024, 1, 1))

# ======================
# RL Logic Processing
# ======================
df = get_live_data()

if not df.empty:
    # Date Filtering
    df_filtered = df[df.index.date >= start_date].copy()
    
    if df_filtered.empty:
        st.warning("No data found for the selected date range.")
    else:
        df_filtered["Signal"] = "WAIT"
        df_filtered["Entry"] = np.nan
        df_filtered["Target"] = np.nan
        df_filtered["StopLoss"] = np.nan
        df_filtered["Confidence"] = 0.0
        df_filtered["PnL_Percent"] = 0.0

        # Learning Parameters
        best_multiplier = 1.0
        total_bal_multiplier = 1.0

        for i in range(2, len(df_filtered)):
            p1, p2 = df_filtered.iloc[i-1], df_filtered.iloc[i-2]
            
            if p1["Close"] > p2["Close"]:
                entry = df_filtered["Open"].iloc[i]
                
                # RL Strategy Adaptation
                base_diff = p1["Close"] - p2["Close"]
                target = entry + (base_diff * best_multiplier)
                sl = p1["Low"]
                
                curr_close = df_filtered["Close"].iloc[i]
                pnl_raw = (curr_close - entry) / entry
                
                # Reward/Penalty System
                if pnl_raw > 0:
                    best_multiplier = min(2.5, best_multiplier + 0.05)
                    conf = min(0.98, 0.65 + (best_multiplier * 0.1))
                else:
                    best_multiplier = max(0.5, best_multiplier - 0.1)
                    conf = max(0.40, 0.60 - abs(best_multiplier * 0.05))

                df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "BUY"
                df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = entry
                df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = target
                df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = sl
                df_filtered.iloc[i, df_filtered.columns.get_loc("Confidence")] = conf
                df_filtered.iloc[i, df_filtered.columns.get_loc("PnL_Percent")] = pnl_raw * 100
                
                total_bal_multiplier *= (1 + pnl_raw)

        final_balance = initial_capital * total_bal_multiplier

        # ======================
        # Header UI
        # ======================
        curr_p = df_filtered["Close"].iloc[-1]
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"""
                <div style="background-color: #1e1e1e; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50;">
                    <p style="color: #888; margin:0;">BTC PRICE (LIVE)</p>
                    <h1 style="margin:0; color: white;">${curr_p:,.2f}</h1>
                </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
                <div style="background-color: #1e1e1e; padding: 15px; border-radius: 10px; border-left: 5px solid #ffca28;">
                    <p style="color: #888; margin:0;">NEXT CANDLE IN</p>
                    <h1 style="margin:0; color: #ffca28;">{get_time_remaining()}</h1>
                </div>
            """, unsafe_allow_html=True)

        st.write("")
        m1, m2, m3 = st.columns(3)
        m1.metric("Starting Balance", f"${initial_capital:,.0f}")
        m2.metric("Current Balance", f"${final_balance:,.2f}", delta=f"{(total_bal_multiplier-1)*100:.2f}%")
        m3.metric("Net Profit", f"${final_balance - initial_capital:,.2f}")

        st.divider()

        # ======================
        # Data Table with Progress Bar
        # ======================
        st.subheader("Trading Logs & RL Predictions")
        
        view_df = df_filtered.sort_index(ascending=False).copy()
        
        st.dataframe(
            view_df,
            use_container_width=True,
            height=450,
            column_config={
                "Signal": st.column_config.TextColumn("Signal"),
                "Confidence": st.column_config.ProgressColumn(
                    "Agent Confidence",
                    help="RL Model Memory Confidence",
                    format="%.0f%%",
                    min_value=0.0,
                    max_value=1.0
                ),
                "Entry": st.column_config.NumberColumn("Entry", format="$%.1f"),
                "Target": st.column_config.NumberColumn("Optimized TP", format="$%.1f"),
                "StopLoss": st.column_config.NumberColumn("SL", format="$%.1f"),
                "PnL_Percent": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
                "Close": st.column_config.NumberColumn("Current/Exit", format="$%.1f"),
                "Open": None, "High": None, "Low": None
            }
        )

# Auto-Refresh Script
st.markdown("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", unsafe_allow_html=True)
