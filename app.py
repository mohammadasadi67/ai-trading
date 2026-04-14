import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

st.set_page_config(layout="wide")
st.title("🚀 REALTIME PANEL")

# ======================
# AUTO RERUN SAFE
# ======================
if "last_run" not in st.session_state:
    st.session_state.last_run = time.time()

if time.time() - st.session_state.last_run > 4:
    st.session_state.last_run = time.time()
    st.rerun()

# ======================
# DATA
# ======================
@st.cache_data(ttl=2)
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 200}
    data = requests.get(url, params=params).json()

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

df = get_data()

# ======================
# STRATEGY
# ======================
df["Decision"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan
df["PnL %"] = np.nan

for i in range(2, len(df)-1):

    prev1 = df.iloc[i-1]
    prev2 = df.iloc[i-2]

    if prev1["Close"] > prev2["Close"]:

        entry = df["Open"].iloc[i]
        move = prev1["Close"] - prev2["Close"]
        target = entry + move

        high_next = df["High"].iloc[i+1]
        close_next = df["Close"].iloc[i+1]

        exit_price = target if high_next >= target else close_next
        pnl = (exit_price - entry) / entry * 100

        df.iloc[i, df.columns.get_loc("Decision")] = "TRADE"
        df.iloc[i, df.columns.get_loc("Entry")] = entry
        df.iloc[i, df.columns.get_loc("Target")] = target
        df.iloc[i, df.columns.get_loc("PnL %")] = pnl

# ======================
# FILTER
# ======================
only_trades = st.toggle("Show Only TRADE", False)

df_view = df[df["Decision"] == "TRADE"] if only_trades else df
rows = list(df_view.iterrows())

# ======================
# TABLE
# ======================
header = st.columns([2,1,1,1,1,1,1,1,1,1])
titles = ["Time","Open","High","Low","Close","Signal","Entry","Target","PnL %","✔"]

for col, t in zip(header, titles):
    col.markdown(f"**{t}**")

for i, (idx, row) in enumerate(rows):

    key = f"trade_{idx.strftime('%Y%m%d%H%M')}"  # 🔥 پایدار

    cols = st.columns([2,1,1,1,1,1,1,1,1,1])

    cols[0].write(idx.strftime("%m-%d %H:%M"))
    cols[1].write(round(row["Open"],2))
    cols[2].write(round(row["High"],2))
    cols[3].write(round(row["Low"],2))
    cols[4].write(round(row["Close"],2))

    cols[5].markdown("🟢 TRADE" if row["Decision"]=="TRADE" else "⚪ WAIT")

    cols[6].write(round(row["Entry"],2) if pd.notna(row["Entry"]) else "-")
    cols[7].write(round(row["Target"],2) if pd.notna(row["Target"]) else "-")

    if pd.notna(row["PnL %"]):
        color = "green" if row["PnL %"] > 0 else "red"
        cols[8].markdown(
            f"<span style='color:{color}'>{round(row['PnL %'],3)}</span>",
            unsafe_allow_html=True
        )
    else:
        cols[8].write("-")

    if row["Decision"] == "TRADE":

        # فقط بار اول → سودده‌ها تیک بخورن
        if key not in st.session_state:
            st.session_state[key] = row["PnL %"] > 0

        cols[9].checkbox(
            "",
            key=key
        )
    else:
        cols[9].write("—")
