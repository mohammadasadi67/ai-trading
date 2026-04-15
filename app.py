import pandas as pd
import numpy as np
import requests
import random

# ======================
# DATA (FAST + SAFE)
# ======================
def get_data():
    try:
        url = "https://data-api.binance.vision/api/v3/klines"
        params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 300}

        res = requests.get(url, params=params, timeout=5)
        data = res.json()

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ig"
        ])

        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)

        print("✅ Data loaded")
        return df.astype(float)

    except Exception as e:
        print("❌ API Error:", e)

        # fallback fake data
        print("⚠️ Using fallback data...")
        dates = pd.date_range(end=pd.Timestamp.now(), periods=300, freq="4H")
        price = np.cumsum(np.random.randn(300)) + 30000

        df = pd.DataFrame({
            "Time": dates,
            "Open": price,
            "High": price + np.random.rand(300)*50,
            "Low": price - np.random.rand(300)*50,
            "Close": price + np.random.randn(300)
        }).set_index("Time")

        return df

# ======================
# RL
# ======================
actions = [0,1,2]  # 0=no trade, 1=breakout, 2=pullback
Q = {}

def get_state(p1, p2):
    move = (p1["Close"] - p2["Close"]) / p2["Close"]
    body = abs(p1["Close"] - p1["Open"])
    range_ = p1["High"] - p1["Low"]

    strength = body / range_ if range_ != 0 else 0
    volatility = (p1["High"] - p1["Low"]) / p1["Close"]

    return (
        round(move, 3),
        round(strength, 2),
        round(volatility, 3)
    )

def choose_action(state, eps=0.1):
    if random.random() < eps:
        return random.choice(actions)
    return max(actions, key=lambda a: Q.get((state,a),0))

def update_q(s,a,r,ns):
    old = Q.get((s,a),0)
    future = max([Q.get((ns,x),0) for x in actions])
    Q[(s,a)] = old + 0.1*(r + 0.9*future - old)

# ======================
# TRAIN (LIGHT)
# ======================
def train(df, episodes=10):
    print("🚀 Training...")

    for ep in range(episodes):
        if ep % 2 == 0:
            print(f"Episode {ep}")

        for i in range(2, len(df)-1):
            p1 = df.iloc[i-1]
            p2 = df.iloc[i-2]
            nxt = df.iloc[i]

            s = get_state(p1,p2)
            a = choose_action(s)

            if a == 0:
                continue

            entry = p1["High"] if a==1 else (p1["High"]+p1["Low"])/2
            sl = p1["Low"]
            tp = entry + (entry-sl)*1.5

            r = 0

            if nxt["High"] >= entry:
                if nxt["Low"] <= sl:
                    r = -0.01
                elif nxt["High"] >= tp:
                    r = 0.02

            ns = get_state(p1,p2)
            update_q(s,a,r,ns)

    print("✅ Training done")

# ======================
# BACKTEST
# ======================
def backtest(df):
    bal = 1
    trades = 0

    for i in range(2,len(df)-1):
        p1 = df.iloc[i-1]
        p2 = df.iloc[i-2]
        nxt = df.iloc[i]

        s = get_state(p1,p2)
        a = max(actions, key=lambda x: Q.get((s,x),0))

        if a == 0:
            continue

        entry = p1["High"] if a==1 else (p1["High"]+p1["Low"])/2
        sl = p1["Low"]
        tp = entry + (entry-sl)*1.5

        if nxt["High"] >= entry:
            trades += 1
            if nxt["Low"] <= sl:
                bal *= 0.98
            elif nxt["High"] >= tp:
                bal *= 1.02

    print("💰 Balance:", round(bal,3))
    print("📊 Trades:", trades)

# ======================
# LIVE SIGNAL
# ======================
def live(df):
    p1 = df.iloc[-2]
    p2 = df.iloc[-3]

    s = get_state(p1,p2)
    a = max(actions, key=lambda x: Q.get((s,x),0))

    print("📡 LIVE:", ["NO","BREAKOUT","PULLBACK"][a])

# ======================
# RUN
# ======================
df = get_data()

train(df, episodes=10)
backtest(df)
live(df)
