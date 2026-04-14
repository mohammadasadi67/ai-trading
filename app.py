# ======================
# RL Logic Processing (Fixed Version)
# ======================
df = get_live_data()

if not df.empty:
    df_filtered = df[df.index.date >= start_date].copy()
    
    if df_filtered.empty:
        st.warning("No data found for the selected date range.")
    else:
        df_filtered["Signal"] = "WAIT"
        df_filtered["Entry"] = np.nan
        df_filtered["Target"] = np.nan
        df_filtered["StopLoss"] = np.nan
        df_filtered["Confidence"] = 0.0
        df_filtered["PnL_Percent"] = 0.0

        best_multiplier = 1.0
        total_bal_multiplier = 1.0

        for i in range(2, len(df_filtered)):
            p1, p2 = df_filtered.iloc[i-1], df_filtered.iloc[i-2]
            
            # --- FIXED LOGIC ---
            # Calculations are based ONLY on p1 and p2 (Completed candles)
            # This makes the Entry and Target constant throughout the current candle.
            
            if p1["Close"] > p2["Close"]:
                # Entry is locked at the OPEN of the current candle
                fixed_entry = df_filtered["Open"].iloc[i] 
                
                # Target is locked based on previous candles' move
                base_diff = p1["Close"] - p2["Close"]
                fixed_target = fixed_entry + (base_diff * best_multiplier)
                
                # StopLoss is locked at previous candle's Low
                fixed_sl = p1["Low"]
                
                # Current price only affects PnL, not the Signal/Target
                curr_close = df_filtered["Close"].iloc[i]
                pnl_raw = (curr_close - fixed_entry) / fixed_entry
                
                # Update DataFrame
                df_filtered.iloc[i, df_filtered.columns.get_loc("Signal")] = "BUY"
                df_filtered.iloc[i, df_filtered.columns.get_loc("Entry")] = fixed_entry
                df_filtered.iloc[i, df_filtered.columns.get_loc("Target")] = fixed_target
                df_filtered.iloc[i, df_filtered.columns.get_loc("StopLoss")] = fixed_sl
                
                # Confidence remains stable
                conf = min(0.98, 0.65 + (best_multiplier * 0.1)) if pnl_raw > 0 else max(0.40, 0.60 - abs(best_multiplier * 0.05))
                df_filtered.iloc[i, df_filtered.columns.get_loc("Confidence")] = conf
                df_filtered.iloc[i, df_filtered.columns.get_loc("PnL_Percent")] = pnl_raw * 100
                
                # Learning update (only for previous candles to avoid feedback loops)
                if i < len(df_filtered) - 1:
                    if pnl_raw > 0:
                        best_multiplier = min(2.5, best_multiplier + 0.05)
                    else:
                        best_multiplier = max(0.5, best_multiplier - 0.1)

                total_bal_multiplier *= (1 + pnl_raw)
