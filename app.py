import requests
import pandas as pd
import numpy as np

# ======================
# DATA (SAFE VERSION)
# ======================
def get_binance_klines(symbol="BTCUSDT", interval="4h", start_str="2024-01-01", max_loops=30):
    url = "https://data-api.binance.vision/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)

    all_rows = []
    last_time = None

    for _ in range(max_loops):

        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ts,
            "limit": 1000
        }

        data = requests.get(url, params=params).json()

        if not data:
            break

        if last_time == data[-1][0]:
            break

        last_time = data[-1][0]
        all_rows.extend(data)
        start_ts = last_time + 1

        if len(data) < 1000:
            break

    df = pd.DataFrame(all_rows, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df[["time","open","high","low","close"]]
    df.columns = ["Time","Open","High","Low","Close"]
    df.set_index("Time", inplace=True)

    return df.astype(float)

# ======================
# INDICATORS
# ======================
def add_indicators(df, ema_f, ema_s):
    df = df.copy()
    df["EMA_F"] = df["Close"].ewm(span=ema_f).mean()
    df["EMA_S"] = df["Close"].ewm(span=ema_s).mean()

    tr = np.maximum(df["High"] - df["Low"],
        np.maximum(abs(df["High"] - df["Close"].shift()),
                   abs(df["Low"] - df["Close"].shift())))

    df["ATR"] = pd.Series(tr).rolling(14).mean()
    return df

# ======================
# BACKTEST
# ======================
def backtest(df, atr_mult=1.0, trail=0.03):

    balance = 1.0
    trades = wins = losses = 0

    in_pos = False
    entry = sl = highest = 0

    for i in range(50, len(df)):

        row = df.iloc[i]
        close = row["Close"]
        high = row["High"]
        low = row["Low"]

        ema_f = row["EMA_F"]
        ema_s = row["EMA_S"]
        atr = row["ATR"]

        # ENTRY
        if not in_pos:
            if close > ema_f > ema_s:
                entry = close
                sl = entry - atr * atr_mult
                highest = entry
                in_pos = True

        # HOLD
        else:
            if high > highest:
                highest = high

            if highest > entry * 1.02:
                sl = max(sl, highest * (1 - trail))

            if low <= sl:
                pnl = (sl - entry) / entry

                balance *= (1 + pnl)
                trades += 1

                if pnl > 0:
                    wins += 1
                else:
                    losses += 1

                in_pos = False

    winrate = (wins / trades * 100) if trades else 0
    profit = (balance - 1) * 100

    return profit, winrate, trades

# ======================
# OPTIMIZE (FAST)
# ======================
def optimize(df):

    ema_fast = [20, 50]
    ema_slow = [100, 200]
    atr_mult = [0.8, 1.2]
    trail = [0.02, 0.03]

    results = []

    for ef in ema_fast:
        for es in ema_slow:
            if ef >= es:
                continue

            df_ind = add_indicators(df, ef, es)

            for am in atr_mult:
                for tr in trail:

                    profit, winrate, trades = backtest(df_ind, am, tr)

                    results.append({
                        "profit": profit,
                        "winrate": winrate,
                        "trades": trades,
                        "ema_f": ef,
                        "ema_s": es,
                        "atr": am,
                        "trail": tr
                    })

    res = pd.DataFrame(results)
    res = res.sort_values("profit", ascending=False)

    return res

# ======================
# RUN
# ======================
print("Loading data...")
df = get_binance_klines()

print("Data size:", len(df))

print("Optimizing...")
result = optimize(df)

print("\n=== TOP RESULTS ===")
print(result.head(10))
