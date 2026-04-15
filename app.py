import pandas as pd
import numpy as np
import requests
import random

# ======================
# DATA (safe + fast)
# ======================
def load_data():
    try:
        url = "https://data-api.binance.vision/api/v3/klines"
        params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 300}
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

        return df.astype(float)

    except:
        # fallback
        n = 300
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="4h")
        price = np.cumsum(np.random.randn(n)) + 30000

        df = pd.DataFrame({
            "Time": dates,
            "Open": price,
            "High": price + np.random.rand(n)*30,
            "Low": price - np.random.rand(n)*30,
            "Close": price + np.random.randn(n)
        }).set_index("Time")

        return df

df = load_data()

# ======================
# RL SETUP (Profit Focus)
# ======================
actions = ["WAIT","BUY"]
Q = {}

def get_state(p1, p2):
    move = (p1["Close"] - p2["Close"]) / p2["Close"]

    body = abs(p1["Close"] - p1["Open"])
    rng = p1["High"] - p1["Low"]
    strength = body / rng if rng != 0 else 0

    volatility = rng / p1["Close"]

    return (
        round(move,3),
        round(strength,2),
        round(volatility,3)
    )

def choose_action(state, eps=0.05):
    # کمتر explore → تمرکز روی سود
    if random.random() < eps:
        return random.choice(actions)
    return max(actions, key=lambda a: Q.get((state,a), 0))

def update_q(s,a,r):
    old = Q.get((s,a), 0)
    Q[(s,a)] = old + 0.2 * (r - old)   # learning rate بالاتر

# ======================
# TRAIN (Profit Weighted)
# ======================
for i in range(2, len(df)-1):
    p1 = df.iloc[i-1]
    p2 = df.iloc[i-2]
    nxt = df.iloc[i]

    state = get_state(p1, p2)
    action = choose_action(state)

    # شرط پایه استراتژی (همون ایده خودت)
    move = (p1["Close"] - p2["Close"]) / p2["Close"]

    if action == "WAIT" or move < 0.004:
        continue

    entry = p1["High"]      # breakout
    sl = p1["Low"]
    tp = entry + (entry - sl) * 2   # RR = 2 (سودمحور)

    reward = 0

    if nxt["High"] >= entry:
        if nxt["Low"] <= sl:
            reward = -0.02     # ضرر سنگین‌تر
        elif nxt["High"] >= tp:
            reward = 0.04      # سود بزرگ‌تر

    # penalize overtrading
    if reward == 0:
        reward = -0.002

    update_q(state, action, reward)

# ======================
# BACKTEST
# ======================
balance = 1
trades = 0

for i in range(2, len(df)-1):
    p1 = df.iloc[i-1]
    p2 = df.iloc[i-2]
    nxt = df.iloc[i]

    state = get_state(p1, p2)
    action = max(actions, key=lambda a: Q.get((state,a),0))

    move = (p1["Close"] - p2["Close"]) / p2["Close"]

    if action == "WAIT" or move < 0.004:
        continue

    entry = p1["High"]
    sl = p1["Low"]
    tp = entry + (entry - sl) * 2

    if nxt["High"] >= entry:
        trades += 1

        if nxt["Low"] <= sl:
            balance *= 0.98
        elif nxt["High"] >= tp:
            balance *= 1.04

# ======================
# LIVE SIGNAL
# ======================
p1 = df.iloc[-2]
p2 = df.iloc[-3]

state = get_state(p1, p2)
action = max(actions, key=lambda a: Q.get((state,a),0))

move = (p1["Close"] - p2["Close"]) / p2["Close"]

if action == "BUY" and move >= 0.004:
    signal = "BUY"
else:
    signal = "WAIT"

# ======================
# OUTPUT
# ======================
print("BALANCE:", round(balance,3))
print("TRADES:", trades)
print("LIVE SIGNAL:", signal)
