import pandas as pd
import numpy as np
import requests
import random

print("START...")

# ======================
# LOAD DATA (REAL + SAFE)
# ======================
def load_data():
    try:
        url = "https://data-api.binance.vision/api/v3/klines"
        params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 200}
        r = requests.get(url, params=params, timeout=5)
        data = r.json()

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ig"
        ])

        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time","open","high","low","close"]]
        df.columns = ["Time","Open","High","Low","Close"]
        df.set_index("Time", inplace=True)

        print("DATA FROM BINANCE ✅")
        return df.astype(float)

    except:
        print("API FAIL ❌ → USING OFFLINE DATA")

        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="4h")
        price = np.cumsum(np.random.randn(n)) + 30000

        df = pd.DataFrame({
            "Time": dates,
            "Open": price,
            "High": price + np.random.rand(n)*20,
            "Low": price - np.random.rand(n)*20,
            "Close": price + np.random.randn(n)
        }).set_index("Time")

        return df

df = load_data()

# ======================
# RL SETUP
# ======================
Q = {}
actions = [0,1,2]  # 0=no trade, 1=breakout, 2=pullback

def get_state(p1, p2):
    move = (p1["Close"] - p2["Close"]) / p2["Close"]
    body = abs(p1["Close"] - p1["Open"])
    rng = p1["High"] - p1["Low"]
    strength = body / rng if rng != 0 else 0

    return (
        round(move, 3),
        round(strength, 2)
    )

def choose_action(state):
    if random.random() < 0.1:
        return random.choice(actions)
    return max(actions, key=lambda a: Q.get((state,a),0))

def update_q(s,a,r):
    old = Q.get((s,a),0)
    Q[(s,a)] = old + 0.1*(r - old)

# ======================
# TRAIN (FAST)
# ======================
print("TRAINING...")

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

    reward = 0

    if nxt["High"] >= entry:
        if nxt["Low"] <= sl:
            reward = -0.01
        elif nxt["High"] >= tp:
            reward = 0.02

    update_q(s,a,reward)

print("TRAIN DONE ✅")

# ======================
# BACKTEST
# ======================
balance = 1
trades = 0

for i in range(2, len(df)-1):
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
            balance *= 0.98
        elif nxt["High"] >= tp:
            balance *= 1.02

print("BALANCE:", round(balance,3))
print("TRADES:", trades)

# ======================
# LIVE SIGNAL
# ======================
p1 = df.iloc[-2]
p2 = df.iloc[-3]

s = get_state(p1,p2)
a = max(actions, key=lambda x: Q.get((s,x),0))

signal = ["NO TRADE","BREAKOUT","PULLBACK"][a]

print("LIVE SIGNAL:", signal)
print("DONE 🚀")
