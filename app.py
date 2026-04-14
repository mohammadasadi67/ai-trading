import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")

# ======================
# AUTO REFRESH (آروم)
# ======================
st.markdown("""
<script>
setTimeout(function(){
    window.location.reload();
}, 3000);
</script>
""", unsafe_allow_html=True)

st.title("🚀 LIVE TRADING SYSTEM")

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
# ساخت کندل جدید
# ======================
last_4h = df.index[-1]
next_4h = last_4h + pd.Timedelta(hours=4)

if next_4h not in df.index:
    new_row = pd.DataFrame({
        "Open":[df["Close"].iloc[-1]],
        "High":[df["Close"].iloc[-1]],
        "Low":[df["Close"].iloc[-1]],
        "Close":[np.nan]
    }, index=[next_4h])

    df = pd.concat([df, new_row]).sort_index()

# ======================
# SIGNAL + PnL
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
df_view = df[(df.index >= pd.Timestamp(start)) &
             (df.index <= pd.Timestamp(end)+pd.Timedelta(days=1))]

# ======================
# TABLE + CHECKBOX
# ======================
st.subheader("📊 SIGNALS")

rows = list(df_view.iterrows())

for i, (idx, row) in enumerate(rows):

    key = str(idx)

    col1, col2 = st.columns([8,1])

    with col1:
        st.write({
            "Time": idx,
            "Open": row["Open"],
            "High": row["High"],
            "Low": row["Low"],
            "Close": row["Close"],
            "Decision": row["Decision"],
            "Entry": row["Entry"],
            "Target": row["Target"],
            "PnL %": row["PnL %"]
        })

    with col2:
        st.session_state.exec[key] = st.checkbox(
            "",
            value=st.session_state.exec.get(key, False),
            key=key
        )

# ======================
# RESULT
# ======================
balance = capital

for i, (idx, row) in enumerate(rows):

    if st.session_state.exec.get(str(idx), False):

        if i < len(rows) - 1:

            entry = row["Entry"]
            target = row["Target"]
            high = row["High"]
            close = row["Close"]

            if pd.notna(entry):

                exit_price = target if high >= target else close
                pnl = (exit_price - entry) / entry
                balance *= (1 + pnl)

st.subheader("💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
