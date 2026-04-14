import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(layout="wide")

# ======================
# AUTO REFRESH سبک‌تر
# ======================
st.markdown("""
<meta http-equiv="refresh" content="3">
""", unsafe_allow_html=True)

st.title("🚀 PRO TRADING PANEL")

# ======================
# STATE
# ======================
if "exec" not in st.session_state:
    st.session_state.exec = {}

# ======================
# INPUT
# ======================
col1, col2, col3 = st.columns(3)
start = col1.date_input("Start")
end   = col2.date_input("End")
capital = col3.number_input("Capital", value=100)

only_trades = st.toggle("Show Only TRADE", False)

# ======================
# DATA
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
# NEW CANDLE (LIVE)
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
# SIGNAL (اصلاح شده)
# ======================
df["Decision"] = "WAIT"
df["Entry"] = np.nan
df["Target"] = np.nan
df["PnL %"] = np.nan

for i in range(2, len(df)-1):

    # اگر کندل فعلی یا بعدی بسته نشده → رد کن
    if pd.isna(df["Close"].iloc[i]) or pd.isna(df["Close"].iloc[i+1]):
        continue

    prev1 = df.iloc[i-1]
    prev2 = df.iloc[i-2]

    if prev1["Close"] > prev2["Close"]:

        entry = df["Open"].iloc[i]
        move = prev1["Close"] - prev2["Close"]
        target = entry + move

        # 🔥 خروج از کندل بعدی
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
df_view = df[(df.index >= pd.Timestamp(start)) &
             (df.index <= pd.Timestamp(end)+pd.Timedelta(days=1))]

if only_trades:
    df_view = df_view[df_view["Decision"] == "TRADE"]

rows = list(df_view.iterrows())

# ======================
# TABLE UI
# ======================
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

    # close یا LIVE
    if pd.isna(row["Close"]):
        cols[4].write("LIVE")
    else:
        cols[4].write(round(row["Close"],2))

    # سیگنال
    if pd.isna(row["Close"]):
        cols[5].markdown("🟡 LIVE")
    elif row["Decision"] == "TRADE":
        cols[5].markdown("🟢 TRADE")
    else:
        cols[5].markdown("⚪ WAIT")

    cols[6].write(round(row["Entry"],2) if pd.notna(row["Entry"]) else "-")
    cols[7].write(round(row["Target"],2) if pd.notna(row["Target"]) else "-")

    # pnl
    if pd.notna(row["PnL %"]):
        color = "green" if row["PnL %"] > 0 else "red"
        cols[8].markdown(f"<span style='color:{color}'>{round(row['PnL %'],3)}</span>", unsafe_allow_html=True)
    else:
        cols[8].write("-")

    cols[9].checkbox(
        "",
        value=st.session_state.exec.get(key, False),
        key=key
    )

# ======================
# RESULT (اصلاح کامل)
# ======================
balance = capital

for i, (idx, row) in enumerate(rows):

    if st.session_state.exec.get(str(idx), False):

        if i < len(rows) - 1:

            next_row = rows[i+1][1]

            entry = row["Entry"]
            target = row["Target"]

            if pd.notna(entry) and pd.notna(next_row["Close"]):

                high = next_row["High"]
                close = next_row["Close"]

                exit_price = target if high >= target else close
                pnl = (exit_price - entry) / entry

                balance *= (1 + pnl)

st.markdown("### 💰 RESULT")
st.metric("Final Balance", f"${balance:.2f}")
