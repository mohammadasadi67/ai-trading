import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(layout="wide", page_title="BTC WHALE ENGINE")
st.title("🐋 BTC PRO: Whale Mode (Trend Follower)")

# ======================
# DATA (FULL HISTORY)
# ======================
@st.cache_data(ttl=3600)
def get_data(start_str="2023-01-01"):
    url = "https://api.binance.com/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    all_data = []
    
    msg = st.empty()
    msg.info("⏳ در حال فراخوانی تاریخچه کامل از بایننس...")
    
    while True:
        params = {"symbol": "BTCUSDT", "interval": "1h", "startTime": start_ts, "limit": 1000}
        try:
            res = requests.get(url, params=params, timeout=10)
            data = res.json()
            if not data: break
            all_data.extend(data)
            start_ts = data[-1][0] + 1
            if len(data) < 1000: break
        except: break

    df = pd.DataFrame(all_data, columns=["time","open","high","low","close","volume","ct","qav","trades","tb","tq","ig"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close"]]
    df.columns = ["Time","Open","High","Low","Close"]
    df.set_index("Time", inplace=True)
    msg.success(f"✅ {len(df)} کندل بارگذاری شد.")
    return df.astype(float)

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("⚙️ تنظیمات بک‌تست")
    start_dt = st.date_input("شروع", value=date(2023,1,1))
    end_dt = st.date_input("پایان", value=date(2026,5,2))
    st.divider()
    capital = st.number_input("سرمایه ($)", value=1000.0)
    fee = st.slider("کارمزد (%)", 0.0, 0.5, 0.05) / 100

df_raw = get_data("2023-01-01")

if not df_raw.empty:
    # ======================
    # INDICATORS
    # ======================
    df = df_raw.copy()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + (gain/loss)))

    # ======================
    # ENGINE (WHALE MODE)
    # ======================
    df["Action"] = "WAIT"
    df["PnL"] = 0.0
    balance = 1.0
    in_pos = False
    entry = sl = highest = 0

    for i in range(200, len(df)):
        t = df.index[i]
        if not (start_dt <= t.date() <= end_dt): continue

        c, h, l = df["Close"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i]
        rsi, ma50, ma200, atr = df["RSI"].iloc[i], df["MA50"].iloc[i], df["MA200"].iloc[i], df["ATR"].iloc[i]

        if not in_pos:
            # ورود در ابتدای روندهای قوی
            if c > ma50 > ma200 and 52 < rsi < 65:
                entry = c
                sl = entry - (atr * 3.0) # استاپ‌لاس عریض برای حفظ معامله
                highest = entry
                in_pos = True
                df.iloc[i, df.columns.get_loc("Action")] = "BUY"
        else:
            df.iloc[i, df.columns.get_loc("Action")] = "HOLD"
            highest = max(highest, h)

            # ریسک‌فری: وقتی قیمت ۳٪ رشد کرد
            if highest > entry * 1.03:
                sl = max(sl, entry)

            # تریلینگ استاپ برای سودهای بزرگ: وقتی ۱۰٪ در سود هستیم
            if highest > entry * 1.10:
                sl = max(sl, highest * 0.94) # فاصله ۶ درصدی برای اجازه به نوسان

            exit_price = 0
            if l <= sl:
                exit_price = sl
            elif c < ma50 and rsi < 45: # خروج اضطراری در صورت چرخش روند
                exit_price = c

            if exit_price > 0:
                pnl = ((exit_price - entry) / entry) - (fee * 2)
                balance *= (1 + pnl)
                df.iloc[i, df.columns.get_loc("Action")] = "EXIT"
                df.iloc[i, df.columns.get_loc("PnL")] = pnl * 100
                in_pos = False

    # ======================
    # FINAL DISPLAY
    # ======================
    df_display = df[(df.index.date >= start_dt) & (df.index.date <= end_dt)].copy()
    df_display["Date"] = df_display.index.date

    daily = df_display.groupby("Date").agg({
        "Close": "last",
        "Action": lambda x: "BUY" if "BUY" in x.values else ("EXIT" if "EXIT" in x.values else ("HOLD" if "HOLD" in x.values else "WAIT")),
        "PnL": "sum"
    })

    net_profit = (balance - 1) * 100
    c1, c2 = st.columns(2)
    c1.metric("Net Profit %", f"{net_profit:.2f}%", delta=f"{net_profit - (-3.12):.2f}% vs Last Run")
    c2.metric("Final Balance", f"${capital * balance:,.2f}")

    st.divider()
    st.subheader(f"📊 وضعیت روزانه از {start_dt}")

    def color_act(val):
        colors = {"BUY": "#2ecc71", "EXIT": "#e74c3c", "HOLD": "#3498db", "WAIT": "#95a5a6"}
        return f"background-color: {colors.get(val, 'gray')}; color: white; font-weight: bold"

    st.dataframe(
        daily.sort_index(ascending=False)
        .style.map(color_act, subset=["Action"])
        .format({"PnL": "{:+.2f}%", "Close": "{:,.1f}"}),
        use_container_width=True,
        height=600
    )
