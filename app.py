import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

st.set_page_config(layout="wide", page_title="BTC Whale PRO")

# ======================
# SIDEBAR
# ======================
st.sidebar.title("⚙️ Strategy Settings")

capital = st.sidebar.number_input("💰 Capital ($)", 100, 1000000, 1000)
fee = st.sidebar.slider("💸 Fee (%)", 0.0, 0.5, 0.1) / 100
risk_per_trade = st.sidebar.slider("⚠️ Risk Per Trade (%)", 0.1, 5.0, 1.0) / 100

start_date_input = st.sidebar.date_input("📅 Start Date", datetime(2023, 1, 1))
end_date_input = st.sidebar.date_input("📅 End Date", datetime.now())

start_dt = pd.to_datetime(start_date_input)
end_dt = pd.to_datetime(end_date_input)

# ======================
# DATA ENGINE
# ======================
@st.cache_data(ttl=86400)
def fetch_historical_data(symbol, interval, start_dt, end_dt):
    url = "https://api.binance.com/api/v3/klines"
    all_data = []

    current_ts = int(start_dt.timestamp() * 1000)
    final_ts = int(end_dt.timestamp() * 1000)

    with requests.Session() as session:
        while current_ts < final_ts:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_ts,
                "limit": 1000
            }
            try:
                res = session.get(url, params=params, timeout=10)
                data = res.json()
                if not isinstance(data, list) or len(data) == 0:
                    break

                all_data.extend(data)
                current_ts = data[-1][0] + 1

            except:
                time.sleep(1)
                continue

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)

df = fetch_historical_data("BTCUSDT", "1h", start_dt, end_dt)

if df.empty:
    st.error("❌ No data")
    st.stop()

# ======================
# INDICATORS
# ======================
df["EMA50"] = df["Close"].ewm(span=50).mean()
df["H_24"] = df["High"].rolling(24).max().shift(1)
df["L_24"] = df["Low"].rolling(24).min().shift(1)

df = df.dropna()

# ======================
# ENGINE
# ======================
balance = capital
equity = []
equity_time = []

in_pos = False
entry = sl = units = 0

for i in range(len(df)-1):

    row = df.iloc[i]
    next_open = df.iloc[i+1]["Open"]

    curr_val = balance + ((row["Close"] - entry) * units if in_pos else 0)
    equity.append(curr_val)
    equity_time.append(df.index[i])

    if not in_pos:
        if row["Close"] > row["H_24"] and row["Close"] > row["EMA50"]:

            entry = next_open * (1 + fee)
            sl = row["L_24"]

            dist = entry - sl
            if dist <= 0:
                continue

            risk_amt = balance * risk_per_trade
            units = min(risk_amt / dist, (balance * 0.3) / entry)

            balance -= entry * units * fee
            in_pos = True

    else:
        stop_hit = row["Open"] <= sl or row["Low"] <= sl

        if stop_hit or row["Close"] < row["EMA50"]:

            exit_price = (sl if stop_hit else next_open) * (1 - fee)

            balance += exit_price * units
            balance -= exit_price * units * fee

            in_pos = False
            units = 0

# ======================
# FORCE CLOSE
# ======================
if in_pos:
    last_price = df.iloc[-1]["Close"] * (1 - fee)
    balance += last_price * units

    equity.append(balance)
    equity_time.append(df.index[-1])

# ======================
# EQUITY CLEAN
# ======================
equity_df = pd.DataFrame(
    {"Strategy": equity},
    index=pd.to_datetime(equity_time)
)

equity_df = equity_df[~equity_df.index.duplicated(keep="last")]
equity_df = equity_df.sort_index()

# ======================
# DAILY (CALENDAR FIX)
# ======================
full_days = pd.date_range(start=start_dt.normalize(), end=end_dt.normalize(), freq="D")

daily = equity_df.resample("D").last()
daily = daily.reindex(full_days)

daily["Strategy"] = daily["Strategy"].ffill()

daily["Daily PnL $"] = daily["Strategy"].diff().fillna(0)
daily["Daily %"] = daily["Strategy"].pct_change().fillna(0) * 100

# ======================
# HODL (ALIGNED)
# ======================
price_daily = df["Close"].resample("D").last()
price_daily = price_daily.reindex(full_days).ffill()

first_price = price_daily.iloc[0]

daily["HODL"] = (price_daily / first_price) * capital
daily["HODL %"] = daily["HODL"].pct_change().fillna(0) * 100

# ======================
# FINAL BALANCE
# ======================
final_balance = daily["Strategy"].iloc[-1]

# ======================
# UI
# ======================
st.title("🐋 BTC Whale PRO (Final Fixed)")

c1, c2 = st.columns(2)
c1.metric("Final Balance", f"${final_balance:,.2f}")
c2.metric("HODL", f"${daily['HODL'].iloc[-1]:,.2f}")

# ======================
# CHART
# ======================
st.subheader("📈 Strategy vs HODL")
st.line_chart(daily[["Strategy","HODL"]])

# ======================
# TABLE
# ======================
st.subheader("📅 Daily Table")

def style_row(row):
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
    .style.apply(style_row, axis=1)
    .format({
        "Strategy":"{:,.0f}$",
        "Daily PnL $":"{:+,.0f}$",
        "Daily %":"{:+.2f}%",
        "HODL":"{:,.0f}$",
        "HODL %":"{:+.2f}%"
    }),
    use_container_width=True
)
