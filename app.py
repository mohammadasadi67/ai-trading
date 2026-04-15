import pandas as pd
import numpy as np
import requests
import random

# ======================
# DATA
# ======================
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 500}
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

# ======================
# RL SETUP
# ======================
actions = {
    0: "NO_TRADE",
    1: "BREAKOUT",
    2: "PULLBACK"
}

Q = {}

# ======================
# STATE
# ======================
def get_state(p1, p2):
    move = (p1["Close"] - p2["Close"]) / p2["Close"]

    body = abs(p1["Close"] - p1["Open"])
    range_ = p1["High"] - p1["Low"]
    strength = body / range_ if range_ != 0 else 0

    volatility = (p1["High"] - p1["Low"]) / p1["Close"]
    direction = 1 if p1["Close"] > p2["Close"] else 0

    return (
        round(move, 3),
        round(strength, 2),
        round(volatility, 3),
        direction
    )

# ======================
# ACTION SELECTION
# ======================
def choose_action(state, epsilon=0.1):
    if random.random() < epsilon:
        return random.choice(list(actions.keys()))
    
    return max(range(len(actions)), key=lambda a: Q.get((state, a), 0))

# ======================
# Q UPDATE
# ======================
def update_q(state, action, reward, next_state, alpha=0.1, gamma=0.9):
    old = Q.get((state, action), 0)
    future = max([Q.get((next_state, a), 0) for a in actions])
    Q[(state, action)] = old + alpha * (reward + gamma * future - old)

# ======================
# TRAIN RL
# ======================
def train_rl(df, episodes=50):
    global Q

    for _ in range(episodes):
        for i in range(2, len(df)-1):
            p1 = df.iloc[i-1]
            p2 = df.iloc[i-2]
            next_candle = df.iloc[i]

            state = get_state(p1, p2)
            action = choose_action(state)

            if action == 0:
                continue

            # entry logic
            if action == 1:
                entry = p1["High"]
            else:
                entry = (p1["High"] + p1["Low"]) / 2

            sl = p1["Low"]
            tp = entry + (entry - sl) * 1.5

            reward = 0

            if next_candle["High"] >= entry:
                if next_candle["Low"] <= sl:
                    reward = (sl - entry) / entry
                elif next_candle["High"] >= tp:
                    reward = (tp - entry) / entry

            next_state = get_state(p1, p2)
            update_q(state, action, reward, next_state)

# ======================
# BACKTEST WITH RL
# ======================
def backtest_rl(df):
    balance = 1
    trades = 0

    for i in range(2, len(df)-1):
        p1 = df.iloc[i-1]
        p2 = df.iloc[i-2]
        next_candle = df.iloc[i]

        state = get_state(p1, p2)

        action = max(range(len(actions)), key=lambda a: Q.get((state, a), 0))

        if action == 0:
            continue

        if action == 1:
            entry = p1["High"]
        else:
            entry = (p1["High"] + p1["Low"]) / 2

        sl = p1["Low"]
        tp = entry + (entry - sl) * 1.5

        if next_candle["High"] >= entry:
            trades += 1

            if next_candle["Low"] <= sl:
                balance *= 0.98
            elif next_candle["High"] >= tp:
                balance *= 1.02

    return balance, trades

# ======================
# LIVE DECISION
# ======================
def live_signal(df):
    p1 = df.iloc[-2]
    p2 = df.iloc[-3]

    state = get_state(p1, p2)

    action = max(range(len(actions)), key=lambda a: Q.get((state, a), 0))

    return actions[action]

# ======================
# RUN
# ======================
df = get_data()

# آموزش RL
train_rl(df, episodes=100)

# بک‌تست
balance, trades = backtest_rl(df)

print("Balance:", balance)
print("Trades:", trades)

# سیگنال لایو
signal = live_signal(df)
print("LIVE SIGNAL:", signal)
