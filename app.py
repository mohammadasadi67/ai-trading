# ======================
# Enhanced Processing Logic
# ======================

# اضافه کردن محاسبه RSI برای فیلتر کردن ورودها
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

if not df.empty:
    df_filtered = df[df.index.date >= start_date].copy()
    
    # محاسبه RSI
    df_filtered["RSI"] = calculate_rsi(df_filtered["Close"])
    
    # ستون‌های جدید برای فیلتر
    df_filtered["Signal"] = "WAIT"
    df_filtered["Entry"] = np.nan
    df_filtered["Target"] = np.nan
    df_filtered["StopLoss"] = np.nan
    df_filtered["PnL_Percent"] = 0.0

    best_multiplier = 1.0
    total_bal_multiplier = 1.0
    trade_count = 0

    for i in range(14, len(df_filtered)):
        p1, p2 = df_filtered.iloc[i-1], df_filtered.iloc[i-2]
        
        # --- فیلترهای تقویت شده ---
        is_bullish = p1["Close"] > p2["Close"]
        is_strong_body = (p1["Close"] - p1["Open"]) > (p1["High"] - p1["Low"]) * 0.4 # بدنه کندل حداقل ۴۰٪ کل طول کندل باشد
        is_not_overbought = df_filtered["RSI"].iloc[i-1] < 70 # جلوگیری از ورود در قله‌ها
        is_momentum = df_filtered["RSI"].iloc[i-1] > 50 # اطمینان از وجود قدرت صعودی

        if is_bullish and is_strong_body and is_not_overbought and is_momentum:
            trade_count += 1
            
            entry = df_filtered["Open"].iloc[i]
            
            # تقویت خروج: تارگت را بر اساس قدرت کندل قبلی منعطف می‌کنیم
            volatility_factor = (p1["High"] - p1["Low"]) 
            target = entry + (volatility_factor * best_multiplier)
            
            # حد ضرر تقویت شده: کمی پایین‌تر از کف کندل قبلی برای جلوگیری از شکار استاپ
            sl = p1["Low"] * 0.998 
            
            curr_close = df_filtered["Close"].iloc[i]
            
            # منطق واقع‌گرایانه خروج در بک‌تست
            # اگر قیمت در طول کندل به SL رسیده باشد
            if df_filtered["Low"].iloc[i] <= sl:
                exit_p = sl
            elif df_filtered["High"].iloc[i] >= target:
                exit_p = target
            else:
                exit_p = curr_close

            raw_pnl = (exit_p - entry) / entry
            net_pnl = (1 + raw_pnl) * (1 - fee_rate)**2 - 1
            
            # ذخیره نتایج
            df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "STRONG BUY"
            df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = entry
            df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = target
            df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = sl
            df_filtered.iloc[i, df_filtered.columns.get_loc("PnL_Percent")] = net_pnl * 100
            
            # بروزرسانی موجودی
            total_bal_multiplier *= (1 + net_pnl)
