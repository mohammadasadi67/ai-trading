import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide")
st.title("🚀 SPOT POSITION PRO (MAX ALPHA)")

# ======================
# DATA
# ======================
def get_data(interval="4h", limit=1000):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": interval, "limit": limit}
    data = requests.get(url, params=params).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close","volume"]]
    df.columns = ["Time","Open","High","Low","Close","Volume"]
    df.set_index("Time", inplace=True)
    return df.astype(float)

# ======================
# INPUT
# ======================
capital = st.sidebar.number_input("Capital", value=1000.0)
fee = st.sidebar.slider("Fee (%)", 0.0, 0.5, 0.1) / 100
start_date = st.sidebar.date_input("Start", value=date(2024,1,1))

df = get_data("4h", 1000)
df = df[df.index.date >= start_date].copy()

# ======================
# INDICATORS (بهینه‌سازی شده)
# ======================
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean() # فیلتر روند بلندمدت
df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
df["DonHigh"] = df["High"].rolling(20).max().shift(1)
df["VolMA"] = df["Volume"].rolling(20).mean() # میانگین حجم

# RSI Calculation
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df["RSI"] = 100 - (100 / (1 + rs))

# ======================
# INIT
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

# ======================
# LOOP (منطق حرفه‌ای ورود و خروج)
# ======================
for i in range(50, len(df)):

    close = df["Close"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]
    vol = df["Volume"].iloc[i]
    rsi = df["RSI"].iloc[i]
    ma50 = df["MA50"].iloc[i]
    ma200 = df["MA200"].iloc[i]
    atr = df["ATR"].iloc[i]
    don_high = df["DonHigh"].iloc[i]

    # ======================
    # ENTRY LOGIC
    # ======================
    if not in_position:
        
        # شرط ۱: تایید روند (قیمت بالای هر دو میانگین و شیب مثبت)
        cond_trend = close > ma50 and ma50 > ma200
        # شرط ۲: شکست سقف کانال دونچیان
        cond_breakout = close > don_high
        # شرط ۳: تایید حجم (حجم باید بیشتر از میانگین باشد - فرار از تله)
        cond_vol = vol > df["VolMA"].iloc[i] * 1.2
        # شرط ۴: RSI در محدوده قدرت (نه اشباع خرید)
        cond_rsi = 50 < rsi < 70

        if cond_trend and cond_breakout and cond_vol and cond_rsi:
            if i - last_trade_i > 5: # کاهش کول‌دان برای شکار فرصت‌ها
                entry_price = close
                # حد ضرر داینامیک بر اساس نوسان بازار
                sl = entry_price - (atr * 2.0) 
                highest = entry_price
                in_position = True
                df.iloc[i, df.columns.get_loc("Signal")] = "BUY"

    # ======================
    # EXIT LOGIC (تریلینگ هوشمند)
    # ======================
    else:
        df.iloc[i, df.columns.get_loc("Signal")] = "HOLD"
        
        if high > highest:
            highest = high

        # تریلینگ استاپ تهاجمی: اگر سود > 4% شد، استاپ را به 2% زیر سقف ببر
        if highest > entry_price * 1.04:
            sl = max(sl, highest * 0.98)
        
        # خروج اضطراری: اگر RSI به شدت ریزش کرد (نشانه تغییر روند سریع)
        exit_signal = False
        if low <= sl:
            exit_price = sl
            exit_signal = True
        elif rsi < 45: # خروج زودهنگام در صورت ضعف مومنتوم
            exit_price = close
            exit_signal = True

        if exit_signal:
            raw = (exit_price - entry_price) / entry_price
            net = (1 + raw) * (1 - fee)**2 - 1

            trades += 1
            balance *= (1 + net)

            if net > 0:
                wins += 1
                total_profit += net
            else:
                losses += 1
                total_loss += abs(net)

            df.iloc[i, df.columns.get_loc("PnL")] = net * 100
            in_position = False
            last_trade_i = i

# ======================
# METRICS (قالب درخواستی شما)
# ======================
final_balance = capital * balance
winrate = (wins / trades * 100) if trades else 0
net_profit = (balance - 1) * 100

c1, c2, c3 = st.columns(3)
c1.metric("Trades", trades)
c2.metric("Winrate", f"{winrate:.2f}%")
c3.metric("Net Profit %", f"{net_profit:.2f}%")

c4, c5, c6 = st.columns(3)
c4.metric("Wins / Losses", f"{wins} / {losses}")
c5.metric("Total Profit %", f"{total_profit*100:.2f}%")
c6.metric("Total Loss %", f"{total_loss*100:.2f}%")

st.metric("Final Balance", f"${final_balance:,.2f}")

st.divider()
st.dataframe(df.sort_index(ascending=False), use_container_width=True, height=600)
