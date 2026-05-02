import requests
import pandas as pd
import numpy as np
from itertools import product
from datetime import datetime, timedelta

# ======================
# 1) DATA (BINANCE)
# ======================
def get_binance_klines(symbol="BTCUSDT", interval="4h", start_str="2023-01-01", limit=1000):
    url = "https://data-api.binance.vision/api/v3/klines"
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)

    all_rows = []
    while True:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ts,
            "limit": limit
        }
        data = requests.get(url, params=params).json()
        if not data:
            break

        all_rows.extend(data)
        last_time = data[-1][0]
        start_ts = last_time + 1

        # توقف اگر کمتر از limit برگشت
        if len(data) < limit:
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
# 2) INDICATORS
# ======================
def add_indicators(df, ema_fast, ema_slow, atr_len, adx_len):
    out = df.copy()
    out["EMA_FAST"] = out["Close"].ewm(span=ema_fast).mean()
    out["EMA_SLOW"] = out["Close"].ewm(span=ema_slow).mean()

    # ATR
    tr = np.maximum(out["High"] - out["Low"],
        np.maximum(abs(out["High"] - out["Close"].shift()),
                   abs(out["Low"] - out["Close"].shift())))
    out["ATR"] = pd.Series(tr, index=out.index).rolling(atr_len).mean()

    # ADX (ساده)
    up = out["High"].diff()
    down = -out["Low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)

    atr = pd.Series(tr, index=out.index).rolling(adx_len).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=out.index).rolling(adx_len).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=out.index).rolling(adx_len).mean() / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    out["ADX"] = dx.rolling(adx_len).mean()

    return out

# ======================
# 3) BACKTEST (POSITION-BASED)
# ======================
def backtest(df, fee=0.001,
             atr_mult_sl=1.2,
             trail_pct=0.03,
             adx_th=20):

    balance = 1.0
    in_pos = False
    entry = sl = highest = 0
    trades = wins = losses = 0
    equity_curve = []

    for i in range(200, len(df)):
        row = df.iloc[i]
        close, high, low = row["Close"], row["High"], row["Low"]
        ema_f, ema_s = row["EMA_FAST"], row["EMA_SLOW"]
        atr, adx = row["ATR"], row["ADX"]

        # ENTRY
        if not in_pos:
            if close > ema_f > ema_s and adx > adx_th:
                entry = close
                sl = entry - atr * atr_mult_sl
                highest = entry
                in_pos = True

        # HOLD
        else:
            if high > highest:
                highest = high

            # trailing after small profit
            if highest > entry * 1.02:
                sl = max(sl, highest * (1 - trail_pct))

            exit_price = None
            if low <= sl:
                exit_price = sl

            if exit_price is not None:
                pnl = (exit_price - entry) / entry
                net = (1 + pnl) * (1 - fee)**2 - 1

                balance *= (1 + net)
                trades += 1
                if net > 0:
                    wins += 1
                else:
                    losses += 1

                in_pos = False

        equity_curve.append(balance)

    # metrics
    winrate = (wins / trades * 100) if trades else 0
    profit = (balance - 1) * 100

    # max drawdown
    ec = pd.Series(equity_curve)
    peak = ec.cummax()
    dd = (ec - peak) / peak
    max_dd = dd.min() * 100

    return {
        "profit": profit,
        "winrate": winrate,
        "trades": trades,
        "max_dd": max_dd
    }

# ======================
# 4) GRID SEARCH
# ======================
def optimize(df):
    ema_fast_list = [20, 30, 50]
    ema_slow_list = [100, 150, 200]
    atr_mult_list = [0.8, 1.0, 1.2]
    trail_list = [0.02, 0.03, 0.04]
    adx_list = [18, 20, 25]

    results = []

    for ema_f, ema_s, atr_m, tr, adx_th in product(
        ema_fast_list, ema_slow_list, atr_mult_list, trail_list, adx_list
    ):
        if ema_f >= ema_s:
            continue

        df_ind = add_indicators(df, ema_f, ema_s, 14, 14)

        res = backtest(df_ind,
                       atr_mult_sl=atr_m,
                       trail_pct=tr,
                       adx_th=adx_th)

        res.update({
            "ema_f": ema_f,
            "ema_s": ema_s,
            "atr_mult": atr_m,
            "trail": tr,
            "adx": adx_th
        })

        results.append(res)

    results_df = pd.DataFrame(results)

    # فیلتر: دراودان منطقی + حداقل ترید
    results_df = results_df[
        (results_df["max_dd"] > -40) &
        (results_df["trades"] >= 10)
    ]

    # رتبه‌بندی: سود بالا + دراودان کمتر
    results_df["score"] = results_df["profit"] + results_df["max_dd"] * 0.5

    best = results_df.sort_values("score", ascending=False).head(10)
    return best

# ======================
# RUN
# ======================
if __name__ == "__main__":
    df = get_binance_klines(start_str="2023-01-01")
    best = optimize(df)

    print("\n=== TOP STRATEGIES ===")
    print(best.to_string(index=False))
