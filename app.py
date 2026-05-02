# ======================
# VARIABLES
# ======================
in_position = False
entry_price = 0
sl = 0
tp = 0
highest = 0

df["Signal"] = "WAIT"
df["PnL"] = np.nan

for i in range(30, len(df)):

    close = df["Close"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]
    ma = df["MA20"].iloc[i]
    atr = df["ATR"].iloc[i]

    # ======================
    # ENTRY
    # ======================
    if not in_position:

        recent_high = df["High"].iloc[i-8:i].max()

        if close > ma and close > recent_high:

            entry_price = close
            sl = entry_price - atr * 0.7
            tp = entry_price + atr * 2

            highest = entry_price
            in_position = True

            df.iloc[i, df.columns.get_loc("Signal")] = "BUY"

    # ======================
    # HOLD
    # ======================
    else:

        df.iloc[i, df.columns.get_loc("Signal")] = "HOLD"

        # آپدیت سقف
        if high > highest:
            highest = high

        # 🔥 TP داینامیک (با رشد قیمت)
        tp = max(tp, highest + atr * 1.5)

        # 🔥 SL داینامیک (Trailing)
        if highest > entry_price * 1.02:
            sl = max(sl, highest - atr * 1.0)

        exit_price = None

        # ======================
        # EXIT LOGIC
        # ======================

        # رسیدن به تارگت
        if high >= tp:
            exit_price = tp

        # حد ضرر
        elif low <= sl:
            exit_price = sl

        # ضعف روند
        elif close < ma * 0.995:
            exit_price = close

        # ======================
        # EXIT → فقط PnL
        # ======================
        if exit_price is not None:

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

            # ❗ فقط این مهمه
            df.iloc[i, df.columns.get_loc("PnL")] = net * 100

            in_position = False
