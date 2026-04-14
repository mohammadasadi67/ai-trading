import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date

# ======================
# PAGE
# ======================
st.set_page_config(layout="wide", page_title="Professional Trading Dashboard")
st.title("🚀 REALTIME PANEL")

# ======================
# DATA
# ======================
def get_live_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 300}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ig"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except:
        return pd.DataFrame()

def get_time_remaining():
    now = datetime.utcnow()
    next_4h = (now.hour // 4 + 1) * 4
    if next_4h >= 24:
        target_t = datetime(now.year, now.month, now.day) + timedelta(days=1)
    else:
        target_t = datetime(now.year, now.month, now.day, next_4h)
    return str((target_t - now)).split(".")[0]

# ======================
# SIDEBAR
# ======================
st.sidebar.title("Configuration")
initial_capital = st.sidebar.number_input("Initial Capital ($)", value=1000.0, step=100.0)
start_date = st.sidebar.date_input("Start Date", value=date(2024, 1, 1))
fee_rate = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.1) / 100

# ======================
# DATA LOAD
# ======================
df = get_live_data()

if not df.empty:
    df_filtered = df[df.index.date >= start_date].copy()

    if df_filtered.empty:
        st.warning("No data found.")
    else:
        # ======================
        # COLUMNS
        # ======================
        df_filtered["Signal"] = "WAIT"
        df_filtered["Entry"] = np.nan
        df_filtered["Target"] = np.nan
        df_filtered["StopLoss"] = np.nan
        df_filtered["Confidence"] = 0.0
        df_filtered["PnL_Percent"] = 0.0

        balance = 1.0
        trades = 0

        # ======================
        # STRATEGY (FIXED)
        # ======================
        for i in range(2, len(df_filtered)):

            p1 = df_filtered.iloc[i-1]
            p2 = df_filtered.iloc[i-2]

            move = (p1["Close"] - p2["Close"]) / p2["Close"]

            # 🔥 فقط حرکت قوی
            if move < 0.004:
                continue

            entry = df_filtered["Open"].iloc[i]
            sl = p1["Low"]
            tp = entry + (move * entry * 1.5)

            high = df_filtered["High"].iloc[i]
            low = df_filtered["Low"].iloc[i]

            exit_price = df_filtered["Close"].iloc[i]

            # ✅ TP / SL واقعی
            if low <= sl:
                exit_price = sl
            elif high >= tp:
                exit_price = tp

            raw = (exit_price - entry) / entry
            net = (1 + raw) * (1 - fee_rate)**2 - 1

            # ❗ فیلتر سود بعد از کارمزد
            if net <= 0:
                continue

            trades += 1
            balance *= (1 + net)

            # ثبت دیتا
            df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "BUY"
            df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = entry
            df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = tp
            df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = sl
            df_filtered.iloc[i, df_filtered.columns.get_loc("PnL_Percent")] = net * 100

            # Confidence ساده
            conf = min(0.95, 0.6 + (move * 10))
            df_filtered.iloc[i, df_filtered.columns.get_loc("Confidence")] = conf

        # ======================
        # HEADER
        # ======================
        curr_price = df_filtered["Close"].iloc[-1]

        c1, c2 = st.columns([2,1])
        with c1:
            st.markdown(f"""
            <div style='background:#1e1e1e;padding:15px;border-radius:10px'>
            <p style='color:#aaa'>BTC PRICE</p>
            <h1 style='color:white'>${curr_price:,.2f}</h1>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            st.markdown(f"""
            <div style='background:#1e1e1e;padding:15px;border-radius:10px'>
            <p style='color:#aaa'>NEXT CANDLE</p>
            <h1 style='color:#ffca28'>{get_time_remaining()}</h1>
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        final_balance = initial_capital * balance

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Balance", f"${final_balance:,.2f}")
        m2.metric("Profit", f"${final_balance-initial_capital:,.2f}", f"{(balance-1)*100:.2f}%")
        m3.metric("Trades", trades)
        m4.metric("Avg Trade", f"{((balance**(1/max(trades,1)))-1)*100:.2f}%")

        st.divider()

        # ======================
        # TABLE (همون کامل)
        # ======================
        st.subheader("Trading Logs & Predictions")

        view_df = df_filtered.sort_index(ascending=False)

        st.dataframe(
            view_df,
            use_container_width=True,
            height=500,
            column_config={
                "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1),
                "Entry": st.column_config.NumberColumn("Entry", format="$%.1f"),
                "Target": st.column_config.NumberColumn("TP", format="$%.1f"),
                "StopLoss": st.column_config.NumberColumn("SL", format="$%.1f"),
                "PnL_Percent": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
                "Close": st.column_config.NumberColumn("Price", format="$%.1f"),
                "Open": None, "High": None, "Low": None
            }
        )

# ======================
# AUTO REFRESH
# ======================
st.markdown(
    "<script>setTimeout(()=>window.location.reload(),20000)</script>",
    unsafe_allow_html=True
)
