import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timezone

st.set_page_config(layout="wide", page_title="BTC Whale PRO")

# ======================
# SIDEBAR
# ======================
st.sidebar.title("⚙️ Settings")

capital = st.sidebar.number_input("💰 Capital ($)", 100, 1_000_000, 1000)
fee = st.sidebar.slider("💸 Fee (%)", 0.0, 0.5, 0.1) / 100
risk_per_trade = st.sidebar.slider("⚠️ Risk (%)", 0.1, 5.0, 1.0) / 100

start_date = pd.to_datetime(st.sidebar.date_input("📅 Start", datetime(2024,1,1)))
end_date   = pd.to_datetime(st.sidebar.date_input("📅 End",   datetime.now()))

# ---- DATE GUARD (future / invalid) ----
now_utc = pd.Timestamp.utcnow().tz_localize(None)
if end_date > now_utc:
    st.sidebar.warning("End date adjusted to now")
    end_date = now_utc

if start_date >= end_date:
    st.error("❌ Invalid date range (start >= end)")
    st.stop()

# ======================
# FETCH (Range-based, safe)
# ======================
@st.cache_data(ttl=3600)
def fetch_range(symbol: str, interval: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp):
    """
    Pulls klines in forward chunks using startTime/endTime.
    Stops safely (no infinite loop), returns exactly the requested window.
    """
    url = "https://api.binance.com/api/v3/klines"

    start_ts = int(start_dt.timestamp() * 1000)
    end_ts   = int(end_dt.timestamp()   * 1000)

    rows = []
    current = start_ts
    last_open_time = None

    # حداکثر حلقه برای جلوگیری از هنگ
    max_loops = 80

    for _ in range(max_loops):
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current,
            "endTime": end_ts,
            "limit": 1000
        }

        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                time.sleep(0.5)
                continue

            data = r.json()
            if not isinstance(data, list) or len(data) == 0:
                break

            rows.extend(data)

            new_open_time = data[-1][0]

            # جلوگیری از گیر
            if last_open_time == new_open_time:
                break

            last_open_time = new_open_time
            current = new_open_time + 1

            # اگر رسیدیم به انتهای بازه
            if new_open_time >= end_ts:
                break

            time.sleep(0.03)

        except Exception:
            time.sleep(0.5)
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df = df.drop_duplicates(subset=["Time"]).set_index("Time").sort_index()
    df = df.astype(float)

    # فیلتر دقیق بازه (امن)
    df = df[(df.index >= start_dt) & (df.index <= end_dt)]

    return df

# ======================
# LOAD DATA
# ======================
df = fetch_range("BTCUSDT", "1h", start_date, end_date)

if df.empty:
    st.error("❌ No data for selected range. Try a closer (recent) window.")
    st.stop()

# ======================
# INDICATORS (intraday)
# ======================
df["EMA50"] = df["Close"].ewm(span=50).mean()
df["H_24"]  = df["High"].rolling(24).max().shift(1)
df["L_24"]  = df["Low"].rolling(24).min().shift(1)
df = df.dropna()

# ======================
# ENGINE (no-bias)
# ======================
balance = capital
equity = []
equity_time = []

in_pos = False
entry = sl = units = 0.0

for i in range(len(df)-1):
    row = df.iloc[i]
    next_open = df.iloc[i+1]["Open"]

    curr_val = balance + ((row["Close"] - entry) * units if in_pos else 0.0)
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
            units = 0.0

# FORCE CLOSE
if in_pos:
    last_price = df.iloc[-1]["Close"] * (1 - fee)
    balance += last_price * units
    equity.append(balance)
    equity_time.append(df.index[-1])
    in_pos = False
    units = 0.0

# ======================
# EQUITY DF (clean)
# ======================
equity_df = pd.DataFrame(
    {"Strategy": equity},
    index=pd.to_datetime(equity_time)
)
equity_df = equity_df[~equity_df.index.duplicated(keep="last")].sort_index()

# ======================
# DAILY (calendar-aligned)
# ======================
full_days = pd.date_range(
    start=start_date.normalize(),
    end=end_date.normalize(),
    freq="D"
)

daily = equity_df.resample("D").last().reindex(full_days)
daily["Strategy"] = daily["Strategy"].ffill()

daily["Daily PnL $"] = daily["Strategy"].diff().fillna(0.0)
daily["Daily %"]     = daily["Strategy"].pct_change().fillna(0.0) * 100.0

# ======================
# HODL (aligned)
# ======================
price_daily = df["Close"].resample("D").last().reindex(full_days).ffill()
first_price = price_daily.iloc[0]

daily["HODL"]   = (price_daily / first_price) * capital
daily["HODL %"] = daily["HODL"].pct_change().fillna(0.0) * 100.0

# ======================
# FINAL BALANCE
# ======================
final_balance = float(daily["Strategy"].iloc[-1])

# ======================
# UI
# ======================
st.title("🐋 BTC Whale PRO (Range Fetch • Stable)")

c1, c2 = st.columns(2)
c1.metric("Final Balance", f"${final_balance:,.2f}")
c2.metric("HODL", f"${daily['HODL'].iloc[-1]:,.2f}")

st.subheader("📈 Strategy vs HODL")
st.line_chart(daily[["Strategy","HODL"]])

st.subheader("📅 Daily Table")

def style_row(row):
    out = []
    for col in row.index:
        v = row[col]
        if col in ["Daily %","HODL %"]:
            if v > 0:
                out.append("color: lime")
            elif v < 0:
                out.append("color: red")
            else:
                out.append("")
        else:
            out.append("")
    return out

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
