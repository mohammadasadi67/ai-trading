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
# DATE FIX (🔥 مهم)
# ======================
now = pd.to_datetime(datetime.utcnow())

if end_date > now:
    st.sidebar.warning("End date adjusted to today")
    end_date = now

if start_date >= end_date:
    st.error("❌ Invalid date range")
    st.stop()

# ======================
# FAST CHUNK FETCH
# ======================
@st.cache_data(ttl=3600)
def fetch_data(symbol="BTCUSDT", interval="1h", chunks=15):

    url = "https://api.binance.com/api/v3/klines"
    all_data = []
    end_time = None

    for _ in range(chunks):

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1000
        }

        if end_time:
            params["endTime"] = end_time

        try:
            res = requests.get(url, params=params, timeout=10)

            if res.status_code != 200:
                break

            data = res.json()

            if not isinstance(data, list) or len(data) == 0:
                break

            all_data.extend(data)

            # حرکت به عقب (safe)
            end_time = data[0][0] - 1

            time.sleep(0.05)

        except:
            break

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)

    return df.sort_index().astype(float)

# ======================
# LOAD DATA
# ======================
df = fetch_data()

if df.empty:
    st.error("❌ Data load failed")
    st.stop()

# اعمال تقویم
df = df.loc[start_date:end_date].copy()

# fallback اگر بازه خالی شد
if df.empty:
    st.warning("⚠️ No data in selected range → using last 30 days")
    df = fetch_data().last("30D")

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
# EQUITY
# ======================
equity_df = pd.DataFrame(
    {"Strategy": equity},
    index=pd.to_datetime(equity_time)
)

equity_df = equity_df[~equity_df.index.duplicated()].sort_index()

# ======================
# DAILY
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
# FINAL
# ======================
final_balance = daily["Strategy"].iloc[-1]

# ======================
# UI
# ======================
st.title("🐋 BTC Whale PRO (Stable)")

c1, c2 = st.columns(2)
c1.metric("Final Balance", f"${final_balance:,.2f}")
c2.metric("HODL", f"${daily['HODL'].iloc[-1]:,.2f}")

st.subheader("📈 Strategy vs HODL")
st.line_chart(daily[["Strategy","HODL"]])

st.subheader("📅 Daily Table")

st.dataframe(
    daily.sort_index(ascending=False).format({
        "Strategy":"{:,.0f}$",
        "Daily PnL $":"{:+,.0f}$",
        "Daily %":"{:+.2f}%",
        "HODL":"{:,.0f}$",
        "HODL %":"{:+.2f}%"
    }),
    use_container_width=True
)
