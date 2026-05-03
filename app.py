import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="BTC Spot Whale PRO")

# ======================
# DATA ENGINE (SAFE)
# ======================
@st.cache_data(ttl=600)
def fetch_data():

    urls = [
        "https://api.binance.com/api/v3/klines",
        "https://data-api.binance.vision/api/v3/klines"
    ]

    params = {"symbol": "BTCUSDT", "interval": "1h", "limit": 1000}

    for url in urls:
        for attempt in range(3):
            try:
                res = requests.get(url, params=params, timeout=10)

                if res.status_code != 200:
                    time.sleep(1)
                    continue

                data = res.json()

                # اگر error object بود
                if not isinstance(data, list):
                    time.sleep(1)
                    continue

                if len(data) == 0:
                    continue

                df = pd.DataFrame(data).iloc[:, :6]
                df.columns = ["Time","Open","High","Low","Close","Volume"]

                df["Time"] = pd.to_datetime(df["Time"], unit="ms")
                df.set_index("Time", inplace=True)

                return df.astype(float)

            except:
                time.sleep(1)

    st.error("❌ Data fetch failed (Binance blocked or unavailable)")
    return pd.DataFrame()

# ======================
# INDICATORS
# ======================
def add_indicators(df):

    df_4h = df.resample("4H").agg({"Close":"last"})
    df_4h["MA_4H"] = df_4h["Close"].rolling(50).mean()

    df = df.join(df_4h["MA_4H"], how="left")
    df["MA_4H"] = df["MA_4H"].ffill()

    tr = pd.concat([
        df["High"]-df["Low"],
        abs(df["High"]-df["Close"].shift()),
        abs(df["Low"]-df["Close"].shift())
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(span=14).mean()

    df["Trend_Score"] = (df["Close"] - df["MA_4H"]) / df["ATR"]

    df["Structure_Low"] = df["Low"].rolling(10).min().shift(1)
    df["MA_Fast"] = df["Close"].rolling(5).mean()
    df["H_24"] = df["High"].rolling(24).max().shift(1)

    return df.dropna().copy()

# ======================
# ENGINE
# ======================
def run_engine(df, capital=1000):

    balance = capital
    equity = []
    trades = []

    in_pos = False
    added = False
    peak = capital

    entry_p = sl_p = units = 0

    for i in range(100, len(df)-1):

        row = df.iloc[i]
        next_open = df.iloc[i+1]["Open"]

        # safety
        if row["Close"] == 0 or np.isnan(row["ATR"]):
            continue

        curr_val = balance + ((row["Close"] - entry_p) * units if in_pos else 0)
        equity.append(curr_val)
        peak = max(peak, curr_val)

        # kill switch
        if (peak - curr_val)/peak > 0.08:
            break

        # ================= ENTRY =================
        if not in_pos:

            hour = df.index[i].hour
            day = df.index[i].dayofweek

            session = hour in [8,9,10,11,14,15,16,17]
            weekday = day in [0,1,2]

            breakout = row["Close"] > row["H_24"]
            impulse = abs(row["Close"] - row["Open"]) > 0.6*(row["High"]-row["Low"])
            continuation = row["Close"] > df.iloc[i-1]["High"]

            if session and weekday and breakout and impulse and continuation:

                atr_mult = np.clip(2 + row["Trend_Score"]*0.8, 2.2, 4.0)

                entry_p = row["Close"] * 1.001
                sl_p = entry_p - row["ATR"] * atr_mult

                risk_dist = entry_p - sl_p
                if risk_dist <= 0:
                    continue

                units = (balance * 0.005) / risk_dist
                balance -= entry_p * units * 0.001

                in_pos = True
                added = False

                trades.append({
                    "Time": df.index[i],
                    "Action": "BUY",
                    "Price": entry_p
                })

        # ================= MANAGEMENT =================
        else:

            profit_r = (row["Close"] - entry_p) / row["ATR"]

            # breakeven
            if profit_r > 2:
                sl_p = max(sl_p, entry_p)

            # pyramiding
            if profit_r > 1.5 and not added:

                add_u = units * 0.5
                risk = (entry_p - sl_p) * (units + add_u)

                if risk < balance * 0.02:

                    balance -= row["Close"] * add_u * 1.001

                    entry_p = (
                        (entry_p * units + row["Close"] * add_u)
                        / (units + add_u)
                    )

                    units += add_u
                    added = True

                    trades.append({
                        "Time": df.index[i],
                        "Action": "PYRAMID",
                        "Price": row["Close"]
                    })

            # exit
            stop_hit = row["Open"] <= sl_p or row["Low"] <= sl_p
            weakness = row["Close"] < row["MA_Fast"]
            structure = row["Low"] < row["Structure_Low"]

            if stop_hit or weakness or structure:

                exit_raw = sl_p if stop_hit else next_open
                exit_p = exit_raw * 0.999

                balance += exit_p * units
                balance -= exit_p * units * 0.001

                trades.append({
                    "Time": df.index[i],
                    "Action": "EXIT",
                    "Price": exit_p,
                    "PnL%": ((exit_p/entry_p)-1)*100
                })

                in_pos = False
                units = 0

    return pd.DataFrame(trades), equity, balance

# ======================
# UI
# ======================
st.title("🐋 BTC Spot Whale PRO")

df = fetch_data()

if df.empty:
    st.stop()

df = add_indicators(df)
trades, equity, final_balance = run_engine(df)

c1, c2, c3 = st.columns(3)
c1.metric("Final Balance", f"${final_balance:,.2f}")

if not trades.empty and "PnL%" in trades.columns:

    exits = trades.dropna(subset=["PnL%"])

    win_rate = (exits["PnL%"] > 0).mean() * 100
    expectancy = (
        (win_rate/100 * exits[exits["PnL%"]>0]["PnL%"].mean()) -
        ((1 - win_rate/100) * abs(exits[exits["PnL%"]<=0]["PnL%"].mean()))
    )

    c2.metric("Win Rate", f"{win_rate:.1f}%")
    c3.metric("Expectancy", f"{expectancy:.2f}%")

    st.subheader("📈 Equity Curve")
    st.line_chart(equity)

    # Monte Carlo safe
    if len(exits) > 5:
        st.subheader("🎲 Monte Carlo")

        pnls = exits["PnL%"].values
        fig = go.Figure()

        for _ in range(30):
            path = np.insert(
                1 + (np.random.choice(pnls, len(pnls))/100),
                0,
                1
            ).cumprod()

            fig.add_trace(go.Scatter(y=path, mode="lines", opacity=0.3))

        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📝 Trades")
    st.dataframe(trades.sort_values("Time", ascending=False))

else:
    st.warning("No trades found.")
