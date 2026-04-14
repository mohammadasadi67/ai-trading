import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

st.set_page_config(layout="wide", page_title="Professional Trading Dashboard")

# --- Data Fetching ---
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 300} # Increased for better indicator calculation
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "close_time","qav","trades","tbbav","tbqav","ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close","volume"]]
        df.columns = ["Time","Open","High","Low","Close","Volume"]
        df.set_index("Time", inplace=True)
        df = df.astype(float)
        return df
    except: return pd.DataFrame()

def calculate_indicators(df):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    # Volume SMA
    df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()
    return df

# --- Sidebar ---
st.sidebar.title("Configuration")
initial_capital = st.sidebar.number_input("Initial Capital ($)", value=1000.0)
start_date = st.sidebar.date_input("Start Date", value=date(2024, 1, 1))
fee_rate = 0.001 # Standardized for CoinEx (0.1% - 0.2%)

# --- Core Logic ---
df = get_live_data()
if not df.empty:
    df = calculate_indicators(df)
    df_filtered = df[df.index.date >= start_date].copy()
    
    df_filtered["Signal"] = "WAIT"
    df_filtered["Entry"] = np.nan
    df_filtered["Target"] = np.nan
    df_filtered["StopLoss"] = np.nan
    df_filtered["PnL_Percent"] = 0.0

    total_multiplier = 1.0
    trade_count = 0

    for i in range(1, len(df_filtered)):
        p1 = df_filtered.iloc[i-1] # Previous candle (Confirmed)
        
        # --- ENHANCED ENTRY RULES ---
        # 1. Price Action: Close > Open (Bullish)
        # 2. RSI: Above 45 (Starting momentum) and Below 72 (Not overheated)
        # 3. Volume: Current volume > Average volume (Real money moving)
        
        if p1["Close"] > p1["Open"] and 45 < p1["RSI"] < 72 and p1["Volume"] > p1["Vol_SMA"] * 0.9:
            trade_count += 1
            entry = df_filtered["Open"].iloc[i]
            
            # Smart Target: Based on previous candle range
            target = entry + (p1["High"] - p1["Low"]) * 1.2
            sl = p1["Low"] * 0.995 # Slightly below the low
            
            curr_close = df_filtered["Close"].iloc[i]
            curr_low = df_filtered["Low"].iloc[i]
            curr_high = df_filtered["High"].iloc[i]

            # Realistic Exit Simulation
            if curr_low <= sl: exit_p = sl
            elif curr_high >= target: exit_p = target
            else: exit_p = curr_close

            net_pnl = ((exit_p - entry) / entry) - (fee_rate * 2)
            
            df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "BUY"
            df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = entry
            df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = target
            df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = sl
            df_filtered.iloc[i, df_filtered.columns.get_loc("PnL_Percent")] = net_pnl * 100
            
            total_multiplier *= (1 + net_pnl)

    # --- UI Display ---
    final_balance = initial_capital * total_multiplier
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Balance", f"${final_balance:,.2f}")
    c2.metric("Total Trades", trade_count)
    c3.metric("Net Profit", f"${final_balance - initial_capital:,.2f}", delta=f"{(total_multiplier-1)*100:.2f}%")

    st.divider()
    
    st.subheader("Trading Logs")
    st.dataframe(
        df_filtered[df_filtered["Signal"] == "BUY"].sort_index(ascending=False),
        use_container_width=True,
        column_config={
            "Entry": st.column_config.NumberColumn(format="$%.1f"),
            "Target": st.column_config.NumberColumn(format="$%.1f"),
            "StopLoss": st.column_config.NumberColumn(format="$%.1f"),
            "PnL_Percent": st.column_config.NumberColumn("Net PnL %", format="%.2f%%"),
            "Close": st.column_config.NumberColumn("Price", format="$%.1f"),
            "Volume": None, "Vol_SMA": None, "RSI": None
        }
    )

st.markdown("<script>setTimeout(function(){window.location.reload();}, 30000);</script>", unsafe_allow_html=True)
