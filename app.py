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

capital = st.sidebar.number_input("Capital ($)", 100, 1_000_000, 1000)
fee = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.1) / 100
risk = st.sidebar.slider("Risk (%)", 0.1, 5.0, 1.0) / 100

# 👇 تاریخ‌ها را به صورت naive (بدون timezone) بساز
start_date = pd.to_datetime(st.sidebar.date_input("Start", datetime(2026, 5, 1))).tz_localize(None)
end_date   = pd.to_datetime(st.sidebar.date_input("End",   datetime(2026, 5, 3))).tz_localize(None)

# ======================
# DATE FIX (🔥 رفع TypeError)
# ======================
now = pd.Timestamp.utcnow().tz_localize(None)  # 👈 این مهمه

if end_date > now:
    end_date = now
    st.sidebar.warning("End date adjusted to now")

if start_date >= end_date:
    st.error("❌ Invalid date range")
    st.stop()

# ======================
# SMART FETCH
# ======================
@st.cache_data(ttl=3600)
def fetch_data(symbol, interval, start_dt, end_dt):

    url = "https://api.binance.com/api/v3/klines"

    start_ts = int(start_dt.timestamp() * 1000)
    end_ts   = int(end_dt.timestamp()   * 1000)

    hours = (end_dt - start_dt).total_seconds() / 3600

    # -------- SMALL RANGE (<=1000 candles)
    if hours <= 1000:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": 1000
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return pd.DataFrame()

        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(data).iloc[:, :6]
        df.columns = ["Time","Open","High","Low","Close","Volume"]
        df["Time"] = pd.to_datetime(df["Time"], unit="ms")
        df.set_index("Time", inplace=True)
        return df.astype(float)

    # -------- LARGE RANGE (chunk backward)
    all_data = []
    current_end = end_ts

    for _ in range(50):
        params = {
            "symbol": symbol,
            "interval": interval,
            "endTime": current_end,
            "limit": 1000
        }

        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            break

        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            break

        all_data.extend(data)
        first_ts = data[0][0]

        if first_ts <= start_ts:
            break

        current_end = first_ts - 1
        time.sleep(0.05)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    df = df.sort_index()
    df = df[(df.index >= start_dt) & (df.index <= end_dt)]
    return df.astype(float)

# ======================
# LOAD DATA
# ======================
df = fetch_data("BTCUSDT", "1h", start_date, end_date)

if df.empty:
    st.error("❌ No data → expand range")
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
times = []

in_pos = False
entry = sl = units = 0.0

for i in range(len(df)-1):
    row = df.iloc[i]
    next_open = df.iloc[i+1]["Open"]

    value = balance + ((row["Close"] - entry) * units if in_pos else 0.0)
    equity.append(value)
    times.append(df.index[i])

    if not in_pos:
        if row["Close"] > row["H_24"] and row["Close"] > row["EMA50"]:
            entry = next_open * (1 + fee)
            sl = row["L_24"]

            dist = entry - sl
            if dist <= 0:
                continue

            risk_amt = balance * risk
            units = min(risk_amt / dist, (balance * 0.3) / entry)

            balance -= entry * units * fee
            in_pos = True
    else:
        if row["Low"] <= sl or row["Close"] < row["EMA50"]:
            exit_price = next_open * (1 - fee)

            balance += exit_price * units
            balance -= exit_price * units * fee

            in_pos = False
            units = 0.0

# FORCE CLOSE
if in_pos:
    last_price = df.iloc[-1]["Close"] * (1 - fee)
    balance += last_price * units
    equity.append(balance)
    times.append(df.index[-1])

# ======================
# DAILY
# ======================
eq = pd.DataFrame({"Strategy": equity}, index=times)

days = pd.date_range(start_date.normalize(), end_date.normalize())

daily = eq.resample("D").last().reindex(days)
daily["Strategy"] = daily["Strategy"].ffill()

daily["PnL"] = daily["Strategy"].diff().fillna(0)
daily["%"] = daily["Strategy"].pct_change().fillna(0) * 100

# ======================
# HODL
# ======================
price = df["Close"].resample("D").last().reindex(days).ffill()
daily["HODL"] = (price / price.iloc[0]) * capital

# ======================
# UI
# ======================
st.title("🐋 BTC Whale PRO")

st.metric("Final Balance", f"${daily['Strategy'].iloc[-1]:,.2f}")

st.line_chart(daily[["Strategy","HODL"]])

st.dataframe(daily.sort_index(ascending=False))
