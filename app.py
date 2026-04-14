import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 FULL 4H SIGNAL + LIVE")

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
# DATA 4H
# ======================
df = yf.download("BTC-USD", interval="4h", start=start, end=end)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df[["Open","High","Low","Close"]]

# ======================
# SIGNAL برای همه کندل‌ها
# ======================
df["Decision"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan

for i in range(2, len(df)):

    prev1 = df.iloc[i-1]
    prev2 = df.iloc[i-2]

    trend = prev1["Close"] > prev2["Close"]

    if trend:

        entry = df["Open"].iloc[i]
        prev_move = prev1["Close"] - prev2["Close"]
        target = entry + prev_move

        df.at[df.index[i], "Decision"] = "TRADE"
        df.at[df.index[i], "Entry"] = entry
        df.at[df.index[i], "Target"] = target

# ======================
# LIVE DATA (1m)
# ======================
live = yf.download("BTC-USD", period="1d", interval="1m")

if isinstance(live.columns, pd.MultiIndex):
    live.columns = live.columns.get_level_values(0)

# ======================
# ADD LIVE CANDLE (بدون ارور timezone)
# ======================
if not live.empty:

    # هم‌تراز timezone
    now = pd.Timestamp.now(tz=live.index.tz)

    hour_block = (now.hour // 4) * 4
    candle_start = now.replace(hour=hour_block, minute=0, second=0, microsecond=0)

    current_data = live[live.index >= candle_start]

    if not current_data.empty:

        open_ = current_data["Open"].iloc[0]
        high_ = current_data["High"].max()
        low_ = current_data["Low"].min()
        close_ = current_data["Close"].iloc[-1]

        new_row = pd.DataFrame({
            "Open": [open_],
            "High": [high_],
            "Low": [low_],
            "Close": [close_],
            "Decision": ["LIVE"],
            "Entry": [open_],
            "Target": [np.nan]
        }, index=[candle_start])

        df = pd.concat([df, new_row])

# ======================
# TABLE
# ======================
table = df[[
    "Open","High","Low","Close",
    "Decision","Entry","Target"
]].copy()

table["Execute"] = False

st.subheader("📊 ALL 4H CANDLES + LIVE")

edited = st.data_editor(table, use_container_width=True)

# ======================
# SIMULATION (FIXED)
# ======================
balance = capital

edited_df = pd.DataFrame(edited).reset_index(drop=True)

for i in range(len(edited_df)):

    if edited_df.at[i, "Execute"]:

        entry = edited_df.at[i, "Entry"]
        target = edited_df.at[i, "Target"]

        if pd.notna(entry) and pd.notna(target):
            pnl = (target - entry) / entry
            balance *= (1 + pnl)

# ======================
# RESULT
# ======================
st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
