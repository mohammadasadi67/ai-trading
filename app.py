import streamlit as st
import pandas as pd
import numpy as np
import websocket
import json
import threading
import time
import requests

st.set_page_config(layout="wide")
st.title("🚀 PRO REALTIME TRADING PANEL")

# ======================
# LOAD HISTORY
# ======================
@st.cache_data
def load_history():
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

# ======================
# STATE
# ======================
if "df" not in st.session_state:
    st.session_state.df = load_history()

if "last_price" not in st.session_state:
    st.session_state.last_price = None

if "exec" not in st.session_state:
    st.session_state.exec = {}

# ======================
# WEBSOCKET
# ======================
def on_message(ws, message):
    data = json.loads(message)
    k = data["k"]

    t = pd.to_datetime(k["t"], unit="ms")
    o = float(k["o"])
    h = float(k["h"])
    l = float(k["l"])
    c = float(k["c"])

    st.session_state.last_price = c

    df = st.session_state.df
    df.loc[t] = [o, h, l, c]
    st.session_state.df = df.sort_index().tail(200)

def run_ws():
    ws = websocket.WebSocketApp(
        "wss://stream.binance.com:9443/ws/btcusdt@kline_4h",
        on_message=on_message
    )
    ws.run_forever()

if "ws_started" not in st.session_state:
    threading.Thread(target=run_ws, daemon=True).start()
    st.session_state.ws_started = True

# ======================
# INPUT UI
# ======================
col1, col2, col3 = st.columns(3)

start = col1.date_input("Start", value=st.session_state.df.index.min().date())
end   = col2.date_input("End", value=st.session_state.df.index.max().date())
capital = col3.number_input("Capital", value=100)

only_trades = st.toggle("Show Only TRADE", False)

# ======================
# STRATEGY
# ======================
def apply_strategy(df):

    df = df.copy()

    df["Decision"] = "WAIT"
    df["Entry"] = np.nan
    df["Target"] = np.nan
    df["PnL %"] = np.nan

    for i in range(2, len(df)-1):

        if pd.isna(df["Close"].iloc[i]) or pd.isna(df["Close"].iloc[i+1]):
            continue

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

    return df

# ======================
# UI LOOP
# ======================
placeholder = st.empty()

while True:

    df = st.session_state.df.copy()

    if not df.empty:

        df = apply_strategy(df)

        # FILTER
        df_view = df[(df.index >= pd.Timestamp(start)) &
                     (df.index <= pd.Timestamp(end)+pd.Timedelta(days=1))]

        if only_trades:
            df_view = df_view[df_view["Decision"] == "TRADE"]

        rows = list(df_view.iterrows())

        with placeholder.container():

            st.subheader("📡 LIVE BTC")

            if st.session_state.last_price:
                st.metric("BTC Price", f"{st.session_state.last_price:,.0f}")

            st.markdown("### 📊 SIGNAL TABLE")

            header = st.columns([2,1,1,1,1,1,1,1,1,1])
            titles = ["Time","Open","High","Low","Close","Signal","Entry","Target","PnL %","✔"]

            for col, t in zip(header, titles):
                col.markdown(f"**{t}**")

            for i, (idx, row) in enumerate(rows):

                key = str(idx)
                cols = st.columns([2,1,1,1,1,1,1,1,1,1])

                cols[0].write(idx.strftime("%m-%d %H:%M"))
                cols[1].write(round(row["Open"],2))
                cols[2].write(round(row["High"],2))
                cols[3].write(round(row["Low"],2))
                cols[4].write(round(row["Close"],2) if pd.notna(row["Close"]) else "LIVE")

                # رنگی
                if row["Decision"] == "TRADE":
                    cols[5].markdown("🟢 TRADE")
                else:
                    cols[5].markdown("⚪ WAIT")

                cols[6].write(round(row["Entry"],2) if pd.notna(row["Entry"]) else "-")
                cols[7].write(round(row["Target"],2) if pd.notna(row["Target"]) else "-")

                if pd.notna(row["PnL %"]):
                    color = "green" if row["PnL %"] > 0 else "red"
                    cols[8].markdown(f"<span style='color:{color}'>{round(row['PnL %'],3)}</span>", unsafe_allow_html=True)
                else:
                    cols[8].write("-")

                cols[9].checkbox("", key=key)

            # ======================
            # RESULT
            # ======================
            balance = capital

            for i, (idx, row) in enumerate(rows):

                if st.session_state.get(str(idx), False):

                    if i < len(rows) - 1:

                        next_row = rows[i+1][1]

                        entry = row["Entry"]
                        target = row["Target"]

                        if pd.notna(entry):

                            high = next_row["High"]
                            close = next_row["Close"]

                            exit_price = target if high >= target else close
                            pnl = (exit_price - entry) / entry

                            balance *= (1 + pnl)

            st.markdown("### 💰 RESULT")
            st.metric("Final Balance", f"${balance:.2f}")

    time.sleep(1)
