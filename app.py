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
risk_per_trade = st.sidebar.slider("⚠️ Risk (%)", 0.1, 5.0, 1.0) / 100

start_date = st.sidebar.date_input("📅 Start", datetime(2024,1,1))
end_date = st.sidebar.date_input("📅 End", datetime.now())

# ======================
# DATA (1H همیشه)
# ======================
@st.cache_data(ttl=3600)
def fetch_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol":"BTCUSDT","interval":"1h","limit":1000}

    res = requests.get(url, params=params)
    data = res.json()

    df = pd.DataFrame(data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]

    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)

df = fetch_data()

# فیلتر تاریخ
df = df[(df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))]

# ======================
# INDICATORS (intraday)
# ======================
df["EMA50"] = df["Close"].ewm(span=50).mean()

df["H_24"] = df["High"].rolling(24).max().shift(1)
df["L_24"] = df["Low"].rolling(24).min().shift(1)

df = df.dropna()

# ======================
# ENGINE (REAL)
# ======================
balance = capital
equity = []
equity_time = []

in_pos = False
entry = sl = units = 0

for i in range(50, len(df)-1):

    row = df.iloc[i]
    next_open = df.iloc[i+1]["Open"]

    # equity واقعی هر کندل
    curr_val = balance + ((row["Close"] - entry) * units if in_pos else 0)

    equity.append(curr_val)
    equity_time.append(df.index[i])

    # ===== ENTRY =====
    if not in_pos:

        if row["Close"] > row["H_24"] and row["Close"] > row["EMA50"]:

            entry = next_open * (1 + fee)
            sl = row["L_24"]

            dist = entry - sl
            if dist <= 0:
                continue

            risk_amt = balance * risk_per_trade
            units = risk_amt / dist

            units = min(units, (balance * 0.3) / entry)

            balance -= entry * units * fee
            in_pos = True

    # ===== EXIT =====
    else:

        stop_hit = row["Open"] <= sl or row["Low"] <= sl

        if stop_hit or row["Close"] < row["EMA50"]:

            exit_price = (sl if stop_hit else next_open) * (1 - fee)

            balance += exit_price * units
            balance -= exit_price * units * fee

            in_pos = False
            units = 0

# ======================
# FORCE CLOSE (خیلی مهم)
# ======================
if in_pos:
    last_price = df.iloc[-1]["Close"] * (1 - fee)
    balance += last_price * units

# ======================
# EQUITY DF
# ======================
equity_df = pd.DataFrame({
    "Time": equity_time,
    "Strategy": equity
}).set_index("Time")

# ======================
# DAILY (REAL)
# ======================
daily = equity_df.resample("D").last()

# پر کردن روزهای خالی
full_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
daily = daily.reindex(full_range)
daily["Strategy"] = daily["Strategy"].ffill()

daily["Daily PnL $"] = daily["Strategy"].diff().fillna(0)
daily["Daily %"] = daily["Strategy"].pct_change().fillna(0)*100

# ======================
# HODL
# ======================
first_price = df["Close"].iloc[0]
hodl = df["Close"] / first_price * capital

hodl_daily = pd.DataFrame({"HODL": hodl}).resample("D").last()
hodl_daily = hodl_daily.reindex(full_range)
hodl_daily["HODL"] = hodl_daily["HODL"].ffill()

daily["HODL"] = hodl_daily["HODL"]
daily["HODL %"] = daily["HODL"].pct_change().fillna(0)*100

# ======================
# UI
# ======================
st.title("🐋 BTC Whale PRO (Intraday Real Daily)")

c1, c2 = st.columns(2)
c1.metric("Final Balance", f"${balance:,.2f}")
c2.metric("Days", len(daily))

# ======================
# CHART
# ======================
st.subheader("📈 Strategy vs HODL")

compare = pd.DataFrame({
    "Strategy": daily["Strategy"],
    "HODL": daily["HODL"]
})

st.line_chart(compare)

# ======================
# TABLE
# ======================
st.subheader("📅 Daily Table (Real)")

def style_daily(row):
    styles = []
    for col in row.index:
        val = row[col]

        if col in ["Daily %","HODL %"]:
            if val > 0:
                styles.append("color: lime")
            elif val < 0:
                styles.append("color: red")
            else:
                styles.append("")
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
