import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC WHALE PRO V16")
st.title("🐋 BTC PRO: Whale Mode (V16 - Ultra Growth)")

# ======================
# DATA (MULTI-ENDPOINT SAFE)
# ======================
@st.cache_data(ttl=3600)
def get_data(start_str="2023-01-01"):
    endpoints = [
        "https://api1.binance.com/api/v3/klines",
        "https://api2.binance.com/api/v3/klines",
        "https://data-api.binance.vision/api/v3/klines"
    ]
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)

    for url in endpoints:
        all_data = []
        current_ts = start_ts
        try:
            while True:
                params = {"symbol": "BTCUSDT", "interval": "1h", "startTime": current_ts, "limit": 1000}
                res = requests.get(url, params=params, timeout=15)
                if res.status_code != 200: break
                data = res.json()
                if not isinstance(data, list) or not data: break
                all_data.extend(data)
                current_ts = data[-1][0] + 1
                if len(data) < 1000: break
            if all_data: break
        except: continue

    if not all_data: return pd.DataFrame()
    df = pd.DataFrame(all_data).iloc[:, :5]
    df.columns = ["Time", "Open", "High", "Low", "Close"]
    df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    df.set_index("Time", inplace=True)
    return df.astype(float)

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("⚙️ تنظیمات بک‌تست")
    start_dt = st.date_input("Start Date", value=date(2023,1,1))
    end_dt = st.date_input("End Date", value=date.today())
    st.divider()
    capital = st.number_input("سرمایه اولیه ($)", value=1000.0)
    fee = st.slider("Fee (%)", 0.0, 0.5, 0.05) / 100
    st.warning("توجه: این استراتژی برای شکار روندهای بزرگ (Trend Following) است.")

# ======================
# LOAD & PROCESS
# ======================
with st.spinner("در حال دریافت دیتای زنده بایننس..."):
    df_raw = get_data("2023-01-01")

if df_raw.empty:
    st.error("❌ دیتایی دریافت نشد!")
    st.stop()

df = df_raw.copy()
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

# RSI
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + (gain/loss)))

# ======================
# ENGINE (SUPER WHALE V16)
# ======================
df["Action"] = "WAIT"
df["PnL"] = 0.0

balance = 1.0
in_pos = False
entry = sl = highest = 0

for i in range(200, len(df)):
    t = df.index[i]
    c, h, l = df["Close"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i]
    rsi, ma50, ma200, atr = df["RSI"].iloc[i], df["MA50"].iloc[i], df["MA200"].iloc[i], df["ATR"].iloc[i]

    # ENTRY
    if not in_pos and (start_dt <= t.date() <= end_dt):
        # فیلتر قوی‌تر برای ورود (RSI > 55)
        if c > ma50 > ma200 and rsi > 55:
            entry, highest, in_pos = c, c, True
            sl = entry - (atr * 3.0) # استاپ عریض‌تر برای بقا در نوسان
            df.iloc[i, df.columns.get_loc("Action")] = "BUY"

    # HOLD & EXIT
    elif in_pos:
        df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
        highest = max(highest, h)

        # Trailing Stop پله‌ای
        if highest > entry * 1.05: sl = max(sl, entry) # Risk free
        if highest > entry * 1.15: sl = max(sl, highest * 0.90) # Profit Lock 10%
        if highest > entry * 1.30: sl = max(sl, highest * 0.85) # Profit Lock 15%

        exit_p = 0
        if l <= sl: exit_p = sl
        
        if exit_p > 0:
            pnl_raw = ((exit_p - entry) / entry) - (fee * 2)
            balance *= (1 + pnl_raw)
            df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
            df.iloc[i, df.columns.get_loc("PnL")] = pnl_raw * 100
            in_pos = False

# ======================
# UI & METRICS
# ======================
df_display = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()
df_display["Date"] = df_display.index.date

daily = df_display.groupby("Date").agg({
    "Close": "last",
    "Action": lambda x: "BUY" if "BUY" in x.values else ("EXIT" if "EXIT" in x.values else ("HOLD" if "HOLD" in x.values else "WAIT")),
    "PnL": "sum"
})

net_profit = (balance - 1) * 100
c1, c2, c3 = st.columns(3)
c1.metric("Net Profit %", f"{net_profit:.2f}%")
c2.metric("Final Balance", f"${capital * balance:,.2f}")
c3.metric("Total Trades", len(df[df["Action"] == "EXIT"]))

st.divider()
st.subheader("📊 Trade & Daily Report")

def color_action(val):
    colors = {"BUY": "#2ecc71", "EXIT": "#e74c3c", "HOLD": "#3498db", "WAIT": "#95a5a6"}
    return f"background-color: {colors.get(val, 'gray')}; color: white; font-weight: bold"

st.dataframe(
    daily.sort_index(ascending=False)
    .style.map(color_action, subset=["Action"])
    .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
    use_container_width=True, height=600
)
