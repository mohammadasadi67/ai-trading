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
st.sidebar.title("⚙️ Settings")

capital = st.sidebar.number_input("💰 Capital ($)", 100, 1000000, 1000)
fee = st.sidebar.slider("💸 Fee (%)", 0.0, 0.5, 0.1) / 100
risk_per_trade = st.sidebar.slider("⚠️ Risk (%)", 0.1, 5.0, 1.0) / 100

start_date = pd.to_datetime(st.sidebar.date_input("📅 Start", datetime(2023,1,1)))
end_date = pd.to_datetime(st.sidebar.date_input("📅 End", datetime.now()))

# ======================
# SAFE FETCH (🔥 FIX)
# ======================
@st.cache_data(ttl=3600)
def fetch_data(symbol, interval, start_dt, end_dt):

    url = "https://api.binance.com/api/v3/klines"
    all_data = []

    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    current_ts = start_ts
    last_ts = None

    p_bar = st.sidebar.progress(0)
    p_text = st.sidebar.empty()

    max_loops = 200
    loops = 0

    with requests.Session() as session:

        while current_ts < end_ts and loops < max_loops:
            loops += 1

            try:
                params = {
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": current_ts,
                    "limit": 1000
                }

                res = session.get(url, params=params, timeout=10)

                if res.status_code != 200:
                    time.sleep(1)
                    continue

                data = res.json()

                if not isinstance(data, list) or len(data) == 0:
                    break

                # جلوگیری از گیر
                if last_ts == data[-1][0]:
                    break

                last_ts = data[-1][0]

                all_data.extend(data)
                current_ts = data[-1][0] + 1

                progress = min(1.0, (current_ts - start_ts) / (end_ts - start_ts))
                p_bar.progress(progress)
                p_text.text(f"📥 {pd.to_datetime(current_ts, unit='ms')}")

                time.sleep(0.05)

            except:
                time.sleep(1)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.astype(float)

# ======================
# LOAD DATA
# ======================
df = fetch_data("BTCUSDT", "1h", start_date, end_date)

if df.empty:
    st.error("❌ Data load failed")
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

# FORCE CLOSE
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

equity_df = equity_df[~equity_df.index.duplicated(keep="last")].sort_index()

# ======================
# DAILY (CALENDAR FIX)
# ======================
full_days = pd.date_range(start=start_date.normalize(), end=end_date.normalize(), freq="D")

daily = equity_df.resample("D").last().reindex(full_days)
daily["Strategy"] = daily["Strategy"].ffill()

daily["Daily PnL $"] = daily["Strategy"].diff().fillna(0)
daily["Daily %"] = daily["Strategy"].pct_change().fillna(0) * 100

# ======================
# HODL
# ======================
price_daily = df["Close"].resample("D").last().reindex(full_days).ffill()
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
st.title("🐋 BTC Whale PRO")

c1, c2 = st.columns(2)
c1.metric("Final Balance", f"${final_balance:,.2f}")
c2.metric("HODL", f"${daily['HODL'].iloc[-1]:,.2f}")

st.subheader("📈 Strategy vs HODL")
st.line_chart(daily[["Strategy","HODL"]])

# ======================
# TABLE
# ======================
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

st.subheader("📅 Daily Table")

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
