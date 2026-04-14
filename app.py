import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 PRO ENTRY (SMART REVERSAL)")

# ======================
# INPUT
# ======================
col1, col2 = st.columns(2)

with col1:
    start = st.date_input("Start")
    end   = st.date_input("End")

with col2:
    capital = st.number_input("Capital ($)", value=1000)

# ======================
# DATA
# ======================
df = yf.download("BTC-USD", interval="4h", start=start, end=end)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close"]]

# ======================
# TREND
# ======================
df["Trend"] = df["Close"].shift(1) > df["Close"].shift(2)

# ======================
# ENTRY LOGIC حرفه‌ای
# ======================
df["Decision"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan
df["PnL %"] = np.nan

for i in range(3, len(df)):

    if df["Trend"].iloc[i]:

        open_ = df["Open"].iloc[i]
        close = df["Close"].iloc[i]
        high = df["High"].iloc[i]
        low = df["Low"].iloc[i]

        # شرط برگشت واقعی
        strong_reversal = (
            (close > open_) and
            ((high - close) < (close - low))  # نزدیک سقف بسته شده
        )

        # کف جدید
        new_low = low < df["Low"].iloc[i-1]

        if strong_reversal and new_low:

            entry = close  # ورود روی قدرت

            # تارگت بر اساس حرکت قبلی
            prev_move = df["Close"].iloc[i-1] - df["Close"].iloc[i-2]
            target = entry + prev_move

            # بررسی داخل همان کندل
            if high >= target:
                exit_price = target
            else:
                exit_price = close

            pnl = (exit_price - entry) / entry * 100

            df.at[df.index[i], "Decision"] = "TRADE"
            df.at[df.index[i], "Entry"] = entry
            df.at[df.index[i], "Target"] = target
            df.at[df.index[i], "PnL %"] = pnl

# ======================
# TABLE
# ======================
table = df[[
    "Open","High","Low","Close",
    "Decision","Entry","Target","PnL %"
]].copy()

table["Execute"] = False

st.subheader("📊 ALL 4H CANDLES")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION
# ======================
balance = capital

edited_df = pd.DataFrame(edited).reset_index(drop=True)

for i in range(len(edited_df)):

    if edited_df.at[i, "Execute"]:

        pnl = edited_df.at[i, "PnL %"]

        if pd.notna(pnl):
            balance *= (1 + pnl / 100)

# ======================
# RESULT
# ======================
st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
