import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

st.set_page_config(layout="wide", page_title="BTC Whale PRO")

# ======================
# SIDEBAR
# ======================
st.sidebar.title("⚙️ Settings")

capital = st.sidebar.number_input("💰 Capital ($)", 100, 100000, 1000)

fee = st.sidebar.slider("💸 Fee (%)", 0.0, 0.5, 0.1) / 100
risk_per_trade = st.sidebar.slider("⚠️ Risk per trade (%)", 0.1, 5.0, 1.0) / 100

timeframe = st.sidebar.selectbox("⏱️ Timeframe", ["1h","4h","1d"])

start_date = st.sidebar.date_input("📅 Start Date", datetime(2024,1,1))
end_date = st.sidebar.date_input("📅 End Date", datetime.now())

# ======================
# DATA
# ======================
@st.cache_data(ttl=3600)
def fetch_data(tf):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol":"BTCUSDT","interval":tf,"limit":1000}

    res = requests.get(url, params=params)
    data = res.json()

    df = pd.DataFrame(data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]

    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)

df = fetch_data(timeframe)

# فیلتر تاریخ
df = df[(df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))]

# ======================
# INDICATORS
# ======================
df["EMA50"] = df["Close"].ewm(span=50).mean()

df["ATR"] = (
    pd.concat([
        df["High"]-df["Low"],
        abs(df["High"]-df["Close"].shift()),
        abs(df["Low"]-df["Close"].shift())
    ], axis=1).max(axis=1)
).ewm(span=14).mean()

df["H_48"] = df["High"].rolling(12).max().shift(1)
df["L_48"] = df["Low"].rolling(12).min().shift(1)

df = df.dropna()

# ======================
# ENGINE (NO BIAS)
# ======================
balance = capital
equity = []
equity_time = []
trades = []

in_pos = False
entry = sl = units = 0

for i in range(50, len(df)-1):

    row = df.iloc[i]
    next_open = df.iloc[i+1]["Open"]

    curr_val = balance + ((row["Close"] - entry) * units if in_pos else 0)

    equity.append(curr_val)
    equity_time.append(df.index[i])

    if not in_pos:

        if row["Close"] > row["H_48"] and row["Close"] > row["EMA50"]:

            entry = next_open * (1 + fee)
            sl = row["L_48"]

            dist = entry - sl
            if dist <= 0:
                continue

            risk_amt = balance * risk_per_trade
            units = risk_amt / dist

            units = min(units, (balance * 0.3) / entry)

            balance -= entry * units * fee

            in_pos = True
            trades.append({
                "Time": df.index[i],
                "Type": "BUY",
                "Price": entry
            })

    else:

        stop_hit = row["Open"] <= sl or row["Low"] <= sl

        if stop_hit or row["Close"] < row["EMA50"]:

            exit_price = (sl if stop_hit else next_open) * (1 - fee)

            pnl = (exit_price - entry) * units

            balance += exit_price * units
            balance -= exit_price * units * fee

            trades.append({
                "Time": df.index[i],
                "Type": "SELL",
                "Price": exit_price,
                "PnL": pnl,
                "PnL%": (exit_price/entry - 1) * 100
            })

            in_pos = False
            units = 0

trades = pd.DataFrame(trades)

# ======================
# UI
# ======================
st.title("🐋 BTC Whale PRO")

c1, c2, c3 = st.columns(3)
c1.metric("Final Balance", f"${balance:,.2f}")
c2.metric("Trades", len(trades))

if "PnL%" in trades.columns:
    win_rate = (trades["PnL%"] > 0).mean()*100
    c3.metric("Win Rate", f"{win_rate:.1f}%")

# ======================
# EQUITY CHART
# ======================
st.subheader("📈 Equity Curve")

equity_df = pd.DataFrame({
    "Time": equity_time,
    "Strategy": equity
}).set_index("Time")

st.line_chart(equity_df)

# ======================
# DAILY TABLE + HODL
# ======================
st.subheader("📅 Daily Performance (Strategy vs HODL)")

daily = equity_df.resample("D").last()

daily["Daily PnL $"] = daily["Strategy"].diff().fillna(0)
daily["Daily %"] = daily["Strategy"].pct_change().fillna(0) * 100

# HODL
first_price = df["Close"].iloc[0]
hodl = df["Close"] / first_price * capital

hodl_df = pd.DataFrame({"HODL": hodl})
hodl_daily = hodl_df.resample("D").last()

daily["HODL"] = hodl_daily["HODL"]
daily["HODL %"] = daily["HODL"].pct_change().fillna(0) * 100

# رنگی
def style_daily(row):
    styles = []
    for col in row.index:
        val = row[col]
        if col in ["Daily %","HODL %"]:
            styles.append("color: lime" if val>0 else "color: red")
        else:
            styles.append("")
    return styles

st.dataframe(
    daily.sort_index(ascending=False)
    .style.apply(style_daily, axis=1)
    .format({
        "Strategy":"{:,.0f}$",
        "Daily PnL $":"{:+,.0f}$",
        "Daily %":"{:+.2f}%",
        "HODL":"{:,.0f}$",
        "HODL %":"{:+.2f}%"
    }),
    use_container_width=True
)

# ======================
# COMPARE CHART
# ======================
st.subheader("📊 Strategy vs HODL")

compare = pd.DataFrame({
    "Strategy": daily["Strategy"],
    "HODL": daily["HODL"]
})

st.line_chart(compare)

# ======================
# TRADES TABLE
# ======================
st.subheader("📊 Trades")

def style_row(row):
    styles = []
    for col in row.index:
        val = row[col]

        if col in ["PnL","PnL%"]:
            if pd.notna(val):
                styles.append("color: lime" if val > 0 else "color: red")
            else:
                styles.append("")
        elif col == "Type":
            styles.append("background-color:#0f5132;color:white" if val=="BUY"
                          else "background-color:#842029;color:white")
        else:
            styles.append("")
    return styles

if not trades.empty:
    st.dataframe(
        trades.sort_values("Time", ascending=False)
        .style.apply(style_row, axis=1)
        .format({
            "Price":"{:,.2f}",
            "PnL":"{:,.2f}",
            "PnL%":"{:.2f}%"
        }),
        use_container_width=True
    )
