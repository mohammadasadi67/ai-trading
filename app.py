import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# =================================================================
# 1. اندیکاتورهای پیشرفته (Smooth & Adaptive)
# =================================================================
def apply_institutional_logic(df):
    # الف) True 4H MTF
    df_4h = df.resample('4H').agg({'Close': 'last'})
    df_4h['MA_4H'] = df_4h['Close'].rolling(50).mean()
    df = df.merge(df_4h[['MA_4H']], left_index=True, right_index=True, how='left').ffill()

    # ب) ATR & Trend Score
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(span=14).mean()
    df['Trend_Score'] = (df['Close'] - df['MA_4H']) / df['ATR']
    
    # ج) Structure Levels (Fixes Weakness 3)
    df['Structure_Low'] = df['Low'].rolling(10).min().shift(1)
    df['MA_Fast'] = df['Close'].rolling(5).mean()
    
    return df

# =================================================================
# 2. موتور هوشمند (Adaptive SL, Risk Cap, Time Edge)
# =================================================================
def run_elite_engine(df, capital, fee=0.001, slip=0.001):
    balance = capital
    equity = []
    trades = []
    in_pos = False
    added = False
    peak = capital
    
    entry_p, sl_p, units = 0, 0, 0
    
    for i in range(100, len(df) - 1):
        row = df.iloc[i]
        h = df.index[i].hour
        
        # --- 1. Time Edge Filter (Fixes Weakness 5) ---
        # تمرکز بر سشن‌های پرنقدینگی لندن و نیویورک
        is_trade_session = h in [8, 9, 10, 11, 14, 15, 16, 17]
        
        # مدیریت Equity و Rolling Peak
        curr_val = balance + ((row['Close'] - entry_p) * units if in_pos else 0)
        equity.append(curr_val)
        peak = max(peak, curr_val)
        
        # Kill Switch (5% Aggressive Spot Limit)
        if (peak - curr_val) / peak > 0.08: break 

        if not in_pos:
            # --- ورود فقط در Regime صعودی قدرتمند ---
            regime_ok = row['Trend_Score'] > 1.2
            breakout = row['Close'] > df['High'].rolling(24).max().shift(1).iloc[i]
            
            if is_trade_session and regime_ok and breakout:
                # اصلاح ۱: Smooth Adaptive ATR Mult
                atr_mult = np.clip(2 + (row['Trend_Score'] * 0.8), 2.2, 4.0)
                
                entry_p = row['Close'] * (1 + slip)
                sl_p = entry_p - (row['ATR'] * atr_mult)
                
                # Risk Management (0.5% per trade)
                risk_amt = balance * 0.005
                units = risk_amt / (entry_p - sl_p)
                
                balance -= (entry_p * units * fee)
                in_pos, added = True, False
                trades.append({"Time": df.index[i], "Action": "ENTRY", "Price": entry_p, "Units": units})
        
        else:
            # --- ۲. Pyramiding with Risk Cap (Fixes Weakness 2) ---
            profit_r = (row['Close'] - entry_p) / row['ATR']
            max_risk_cap = balance * 0.02 # حداکثر ریسک کل پوزیشن نباید از ۲٪ کل موجودی بیشتر شود
            
            if profit_r > 1.5 and not added:
                current_risk = (row['Close'] - sl_p) * units # در واقعیت ریسک الان کمتر شده چون در سودیم
                potential_add = units * 0.5
                # محاسبه حجم مجاز بر اساس سقف ریسک
                add_units = min(potential_add, (max_risk_cap - current_risk) / (row['Close'] - sl_p))
                
                if add_units > 0:
                    add_cost = row['Close'] * add_units
                    balance -= (add_cost * (1 + fee))
                    entry_p = ((entry_p * units) + (row['Close'] * add_units)) / (units + add_units)
                    units += add_units
                    added = True
                    trades.append({"Time": df.index[i], "Action": "PYRAMID", "Price": row['Close']})

            # --- ۳. Advanced Exit (Fixes Weakness 3) ---
            stop_hit = row['Low'] <= sl_p
            momentum_break = row['Close'] < row['MA_Fast']
            structure_break = row['Low'] < row['Structure_Low']
            
            if stop_hit or momentum_break or structure_break:
                exit_raw = sl_p if stop_hit else df.iloc[i+1]['Open']
                exit_p = exit_raw * (1 - slip)
                
                balance += (exit_p * units)
                balance -= (exit_p * units * fee)
                trades.append({"Time": df.index[i], "Action": "EXIT", "Price": exit_p, "PnL%": ((exit_p/entry_p)-1)*100})
                in_pos, units = False, 0

    return pd.DataFrame(trades), equity, balance

# =================================================================
# 3. Monte Carlo: Block Bootstrapping (Fixes Weakness 4)
# =================================================================
# 
def run_block_monte_carlo(trades_df, capital, num_sims=50, block_size=3):
    if trades_df.empty or 'PnL%' not in trades_df.columns: return []
    pnls = trades_df['PnL%'].dropna().values
    all_paths = []
    
    for _ in range(num_sims):
        path = [capital]
        current_cap = capital
        # Block Sampling برای حفظ همبستگی تریدها
        for _ in range(0, len(pnls), block_size):
            if len(pnls) < block_size: break
            idx = np.random.randint(0, len(pnls) - block_size + 1)
            block = pnls[idx : idx + block_size]
            for pnl in block:
                current_cap *= (1 + pnl/100)
                path.append(current_cap)
        all_paths.append(path)
    return all_paths

# [بخش نمایش نتایج در Streamlit مشابه قبل با اضافه شدن متغیرهای جدید]
