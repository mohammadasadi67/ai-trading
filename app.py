import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("🔥 BTC AGGRESSIVE SCALPER (LEFT SIDE - HIGH FREQ)")

# ======================
# DATA
# ======================
def get_data(interval="4h", limit=1000):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": interval, "limit": limit}
    try:
        data = requests.get(url, params=params).json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ig"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)
        return df.astype(float)
    except:
        st.error("خطا در دریافت دیتا از صرافی")
        return pd.DataFrame()

# ======================
# SETTINGS
# ======================
capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.1) / 100
start_date = st.sidebar.date_input("Start Date", value=date(2024,1,1))

df = get_data("4h", 1000)
if df.empty: st.stop()
df = df[df.index.date >= start_date].copy()

# ======================
# STRATEGY INDICATORS (AGGRESSIVE)
# ======================
df["MA20"] = df["Close"].rolling(20).mean() # سریع‌تر از MA50
df["ATR"] = (df["High"] - df["Low"]).rolling(10).mean()
df["DonHigh"] = df["High"].rolling(7).max().shift(1) # بسیار سریع برای ورودهای مکرر

# ======================
# BACKTEST ENGINE
# ======================
df["Signal"] = "WAIT"
df["PnL"] = np.nan

balance = 1.0
trades = wins = losses = 0
total_profit = total_loss = 0

in_position = False
entry_price = 0
sl = 0
highest = 0
last_trade_i = -100

for i in range(20, len(df)):
    close = df["Close"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]
    ma20 = df["MA20"].iloc[i]
    atr = df["ATR"].iloc[i]
    don_high = df["DonHigh"].iloc[i]

    if not in_position:
        # ورود سریع: قیمت بالای MA20 و شکست سقف 7 کندلی
        if close > don_high and close > ma20:
            if i - last_trade_i >= 2: # فقط 2 کندل فاصله بین معاملات
                entry_price = close
                sl = entry_price - (atr * 1.2) # استاپ نزدیک‌تر برای حفظ سرمایه
                highest = entry_price
                in_position = True
                last_trade_i = i
                df.iloc[i, df.columns.get_loc("Signal")] = "BUY"

    else:
        df.iloc[i, df.columns.get_loc("Signal")] = "HOLD"
        if high > highest:
            highest = high

        # تریلینگ استاپ تهاجمی
        # به محض 1.5% سود، استاپ را به نقطه ورود بیار (ریسک فری)
        if highest > entry_price * 1.015:
            sl = max(sl, entry_price * 1.002)
        
        # قفل کردن سودهای بالای 4%
        if highest > entry_price * 1.04:
            sl = max(sl, highest * 0.975)

        if low <= sl:
            exit_price = sl
            raw = (exit_price - entry_price) / entry_price
            net = (1 + raw) * (1 - fee)**2 - 1
            
            balance *= (1 + net)
            trades += 1
            if net > 0:
                wins += 1
                total_profit += net
            else:
                losses += 1
                total_loss += abs(net)
            
            df.iloc[i, df.columns.get_loc("PnL")] = net * 100
            in_position = False

# ======================
# DISPLAY METRICS
# ======================
final_balance = capital * balance
winrate = (wins / trades * 100) if trades else 0
net_profit_pct = (balance - 1) * 100

col1, col2, col3 = st.columns(3)
col1.metric("Total Trades", trades)
col2.metric("Winrate", f"{winrate:.2f}%")
col3.metric("Net Profit %", f"{net_profit_pct:.2f}%")

col4, col5, col6 = st.columns(3)
col4.metric("Final Balance", f"${final_balance:,.2f}")
col5.metric("Total Profit %", f"{total_profit*100:.2f}%")
col6.metric("Total Loss %", f"{total_loss*100:.2f}%")

st.divider()
st.subheader("Historical Data & Signals")
st.dataframe(df.sort_index(ascending=False), use_container_width=True, height=500)
