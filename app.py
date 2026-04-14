import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")

# ======================
# AUTO REFRESH 1s
# ======================
st.markdown("""
<script>
setTimeout(function(){
    window.location.reload();
}, 1000);
</script>
""", unsafe_allow_html=True)

st.title("🚀 LIVE TRADING SYSTEM FINAL")

# ======================
# SESSION STATE
# ======================
if "exec" not in st.session_state:
    st.session_state.exec = {}

# ======================
# INPUT
# ======================
start = st.date_input("Start Date")
end   = st.date_input("End Date")
capital = st.number_input("Capital", value=100)

# ======================
# GET 4H DATA
# ======================
def get_4h():
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

df = get_4h()

# ======================
# LIVE PRICE (SAFE)
# ======================
ticker = requests.get(
    "https://api.binance.com/api/v3/ticker/price",
    params={"symbol": "BTCUSDT"}
).json()

live_price = float(ticker["price"]) if "price" in ticker else df["Close"].iloc[-1]

# ======================
# LIVE 1m DATA
# ======================
live = requests.get(
    "https://data-api.binance.vision/api/v3/klines",
    params={"symbol": "BTCUSDT", "interval": "1m", "limit": 30}
).json()

live_df = pd.DataFrame(live, columns=[
    "time","open","high","low","close","volume",
    "close_time","qav","trades","tbbav","tbqav","ignore"
])

live_df["time"] = pd.to_datetime(live_df["time"], unit="ms")
live_df = live_df[["time","open","high","low","close"]]
live_df.columns = ["Time","Open","High","Low","Close"]
live_df.set_index("Time", inplace=True)
live_df = live_df.astype(float)

# ======================
# BUILD CURRENT CANDLE
# ======================
last_4h = df.index[-1]
next_4h = last_4h + pd.Timedelta(hours=4)

current = live_df[live_df.index >= last_4h]

if not current.empty:

    open_ = current["Open"].iloc[0]
    high_ = max(current["High"].max(), live_price)
    low_  = min(current["Low"].min(), live_price)
    close_ = live_price

    new_row = pd.DataFrame({
        "Open":[open_],
        "High":[high_],
        "Low":[low_],
        "Close":[close_]
    }, index=[next_4h])

    if next_4h in df.index:
        df = df.drop(next_4h)

    df = pd.concat([df, new_row])
    df = df.sort_index()

# ======================
# SIGNAL + PnL
# ======================
df["Decision"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan
df["PnL %"] = np.nan

for i in range(2, len(df)):

    prev1 = df.iloc[i-1]
    prev2 = df.iloc[i-2]

    if prev1["Close"] > prev2["Close"]:

        entry = df["Open"].iloc[i]
        move = prev1["Close"] - prev2["Close"]
        target = entry + move

        high = df["High"].iloc[i]
        close = df["Close"].iloc[i]

        exit_price = target if high >= target else close
        pnl = (exit_price - entry) / entry * 100

        df.iloc[i, df.columns.get_loc("Decision")] = "TRADE"
        df.iloc[i, df.columns.get_loc("Entry")] = entry
        df.iloc[i, df.columns.get_loc("Target")] = target
        df.iloc[i, df.columns.get_loc("PnL %")] = pnl

# ======================
# FILTER
# ======================
df.index.name = "Time"

df_view = df[(df.index >= pd.Timestamp(start)) &
             (df.index <= pd.Timestamp(end)+pd.Timedelta(days=1))]

# ======================
# TABLE
# ======================
table = df_view.reset_index()[[
    "Time","Open","High","Low","Close",
    "Decision","Entry","Target","PnL %"
]].copy()

# Execute با کلید Time
table["Execute"] = [
    st.session_state.exec.get(str(row["Time"]), False)
    for _, row in table.iterrows()
]

edited = st.data_editor(table, use_container_width=True)

# ذخیره Execute
for i in range(len(edited)):
    key = str(edited.iloc[i]["Time"])
    st.session_state.exec[key] = edited.iloc[i]["Execute"]

# ======================
# RESULT
# ======================
balance = capital

for i in range(len(edited)):

    key = str(edited.iloc[i]["Time"])

    if st.session_state.exec.get(key, False):

        if i < len(edited) - 1:

            entry = edited.iloc[i]["Entry"]
            target = edited.iloc[i]["Target"]
            high = edited.iloc[i]["High"]
            close = edited.iloc[i]["Close"]

            if pd.notna(entry):

                exit_price = target if high >= target else close
                pnl = (exit_price - entry) / entry
                balance *= (1 + pnl)

st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
