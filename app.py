import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import time
from datetime import datetime, timedelta

# RL Libraries
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

st.set_page_config(layout="wide", page_title="AI Pro Trader (Fee Aware)")
st.title("🚀 AI TRADER PRO: FEE-AWARE & DATE FILTER")

# ======================
# 1. دریافت داده‌ها
# ======================
@st.cache_data(ttl=3600)
def get_historical_data(symbol="BTCUSDT", interval="4h", years=3):
    url = "https://data-api.binance.vision/api/v3/klines"
    total_needed = years * 365 * 6 
    all_candles = []
    last_time = None
    
    with st.spinner("در حال به‌روزرسانی داده‌های بازار..."):
        while len(all_candles) < total_needed:
            params = {"symbol": symbol, "interval": interval, "limit": 1000}
            if last_time: params["endTime"] = last_time - 1
            try:
                res = requests.get(url, params=params).json()
                if not res or len(res) == 0: break
                all_candles = res + all_candles
                last_time = res[0][0]
                if len(all_candles) >= total_needed: break
                time.sleep(0.05)
            except: break

    df = pd.DataFrame(all_candles, columns=["time", "open", "high", "low", "close", "volume", "ct", "qav", "trades", "tb", "tq", "ig"])
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    df['date'] = pd.to_datetime(df['time'], unit='ms')
    
    # ویژگی‌های پرایس اکشن
    df['body_size'] = (df['close'] - df['open']) / df['open']
    df['upper_wick'] = (df['high'] - np.maximum(df['close'], df['open'])) / df['open']
    df['lower_wick'] = (np.minimum(df['close'], df['open']) - df['low']) / df['open']
    df['rel_volume'] = df['volume'] / df['volume'].rolling(20).mean()
    
    return df.dropna().reset_index(drop=True)

# ======================
# 2. محیط معاملاتی هوشمند (با لحاظ کارمزد)
# ======================
class SmartTradingEnv(gym.Env):
    def __init__(self, df, initial_balance=1000, stop_loss=0.03, fee=0.001):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.sl_pct = stop_loss
        self.fee = fee # کارمزد صرافی
        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.balance = self.initial_balance
        self.position = 0 
        self.entry_price = 0
        self.step_i = 20 
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.step_i]
        floating_pnl = (row['close'] / self.entry_price) - 1 if self.entry_price > 0 else 0
        return np.array([
            row['body_size'], row['upper_wick'], row['lower_wick'],
            row['rel_volume'] if not np.isnan(row['rel_volume']) else 1.0,
            float(self.position), floating_pnl
        ], dtype=np.float32)

    def step(self, action):
        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]
        price_diff = (next_row['close'] - row['close']) / row['close']
        reward = 0

        if action == 1: # BUY/HOLD
            if self.position == 0: # ورود جدید (پرداخت کارمزد)
                self.position = 1
                self.entry_price = row['close']
                self.balance *= (1 - self.fee) 
                reward = -self.fee # جریمه برای باز کردن ترید
            
            pnl = (next_row['close'] / self.entry_price) - 1
            if pnl <= -self.sl_pct:
                reward = -15 # جریمه سنگین استاپ خوردن
                self.balance *= (1 - self.sl_pct)
                self.position = 0
                self.entry_price = 0
            else:
                reward = price_diff * 10
                self.balance *= (1 + price_diff)
        
        else: # WAIT/SELL
            if self.position == 1: # خروج (پرداخت کارمزد)
                self.balance *= (1 - self.fee)
                pnl = (row['close'] - self.entry_price) / self.entry_price
                reward = (pnl - self.fee) * 20 # سود خالص منهای کارمزد
                self.position = 0
                self.entry_price = 0
            else:
                reward = -0.1 if price_diff > 0.01 else 0.05 # پاداش برای تماشای بازار منفی

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. اجرای اصلی و داشبورد
# ======================
df = get_historical_data(years=3)

# --- Sidebar ---
st.sidebar.header("💰 Money Management")
init_cash = st.sidebar.number_input("سرمایه اولیه ($)", value=1000)
exchange_fee = st.sidebar.slider("کارمزد صرافی (%)", 0.0, 0.5, 0.1, step=0.05) / 100
sl_val = st.sidebar.slider("حد ضرر Stop Loss (%)", 1, 10, 3) / 100

st.sidebar.header("🗓 Date Filter")
min_date = df['date'].min().to_pydatetime()
max_date = df['date'].max().to_pydatetime()
date_range = st.sidebar.date_input("انتخاب بازه تاریخ معاملات", [min_date, max_date])

# --- Training Logic ---
env = SmartTradingEnv(df, initial_balance=init_cash, stop_loss=sl_val, fee=exchange_fee)
MODEL_NAME = "smart_pa_model"

col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 شروع آموزش مدل"):
        with st.spinner("مدل در حال یادگیری با احتساب کارمزد..."):
            model = PPO("MlpPolicy", env, verbose=0, learning_rate=0.0002)
            model.learn(total_timesteps=100000)
            model.save(MODEL_NAME)
        st.success("آموزش تمام شد!")
        st.rerun()

if os.path.exists(f"{MODEL_NAME}.zip"):
    model = PPO.load(MODEL_NAME)
    obs, _ = env.reset()
    trade_log = []
    current_trade = None

    # Backtest Loop
    for i in range(len(df) - 2):
        action, _ = model.predict(obs, deterministic=True)
        row = df.iloc[i]
        
        if action == 1 and current_trade is None:
            current_trade = {"Entry Time": row['date'], "Entry Price": row['close']}
        elif current_trade is not None:
            next_row = df.iloc[i+1]
            if action == 0 or (next_row['close'] <= current_trade['Entry Price'] * (1 - sl_val)):
                exit_price = next_row['close']
                raw_pnl = ((exit_price - current_trade['Entry Price']) / current_trade['Entry Price'])
                net_pnl_pct = (raw_pnl - (2 * exchange_fee)) * 100 # کارمزد ورود + خروج
                
                trade_log.append({
                    "Date": current_trade['Entry Time'],
                    "Entry Price": round(current_trade['Entry Price'], 2),
                    "Exit Price": round(exit_price, 2),
                    "Net PnL (%)": round(net_pnl_pct, 2),
                    "Profit ($)": round((net_pnl_pct/100) * init_cash, 2)
                })
                current_trade = None
        obs, _, _, _, _ = env.step(action)

    # تبدیل به دیتافریم و اعمال فیلتر تاریخ
    trades_df = pd.DataFrame(trade_log)
    if not trades_df.empty:
        if len(date_range) == 2:
            mask = (trades_df['Date'].dt.date >= date_range[0]) & (trades_df['Date'].dt.date <= date_range[1])
            trades_df = trades_df.loc[mask]

        # نمایش آمار کلیدی
        st.divider()
        st.subheader("📊 عملکرد نهایی")
        total_pnl_cash = trades_df['Profit ($)'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("سرمایه نهایی", f"${init_cash + total_pnl_cash:.2f}")
        c2.metric("سود خالص کل", f"${total_pnl_cash:.2f}", delta=f"{(total_pnl_cash/init_cash)*100:.2f}%")
        c3.metric("تعداد معاملات (فیلتر شده)", len(trades_df))

        # لیست معاملات
        st.write("### 📜 لیست معاملات انجام شده")
        st.dataframe(trades_df.sort_values(by="Date", ascending=False), use_container_width=True)
    else:
        st.warning("⚠️ در این بازه زمانی تریدی انجام نشده یا مدل هنوز آموزش ندیده است.")

    # نمایش سیگنال لحظه‌ای
    st.divider()
    last_action, _ = model.predict(obs, deterministic=True)
    if last_action == 1:
        st.success(f"🎯 سیگنال لحظه‌ای: **BUY / HOLD** | قیمت فعلی: {df.iloc[-1]['close']}")
    else:
        st.warning("🎯 سیگنال لحظه‌ای: **WAIT / SELL**")
