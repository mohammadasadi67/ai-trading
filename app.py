import streamlit as st
import pandas as pd
import numpy as np
import websocket
import json
import threading
import time

st.set_page_config(layout="wide")
st.title("🚀 REALTIME TRADING PANEL (WebSocket)")

# ======================
# STATE
# ======================
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Time","Open","High","Low","Close"])

if "last_price" not in st.session_state:
    st.session_state.last_price = None

# ======================
# WEBSOCKET HANDLER
# ======================
def on_message(ws, message):
    data = json.loads(message)

    k = data["k"]

    t = pd.to_datetime(k["t"], unit="ms")
    o = float(k["o"])
    h = float(k["h"])
    l = float(k["l"])
    c = float(k["c"])
    closed = k["x"]

    st.session_state.last_price = c

    df = st.session_state.df

    if t in df.index:
        df.loc[t] = [o, h, l, c]
    else:
        df.loc[t] = [o, h, l, c]

    st.session_state.df = df.sort_index().tail(200)

def run_ws():
    ws = websocket.WebSocketApp(
        "wss://stream.binance.com:9443/ws/btcusdt@kline_4h",
        on_message=on_message
    )
    ws.run_forever()

# ======================
# START THREAD
# ======================
if "ws_started" not in st.session_state:
    thread = threading.Thread(target=run_ws)
    thread.daemon = True
    thread.start()
    st.session_state.ws_started = True

# ======================
# SIGNAL LOGIC
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
# UI LOOP (بدون رفرش)
# ======================
placeholder = st.empty()

while True:

    df = st.session_state.df.copy()

    if not df.empty:

        df = apply_strategy(df)

        with placeholder.container():

            st.subheader("📡 LIVE BTC")

            if st.session_state.last_price:
                st.metric("BTC Price", f"{st.session_state.last_price:,.0f}")

            st.dataframe(df.tail(15), use_container_width=True)

    time.sleep(1)
