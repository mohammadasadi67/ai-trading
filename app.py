import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import time
from datetime import datetime, timedelta

# RL
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

st.set_page_config(layout="wide", page_title="AI Crypto Trader")
st.title("🚀 AI TRADER PRO: SL/TP & HOLD LOGIC")

# ======================
# 1. دریافت داده‌های تاریخچه‌ای
# ======================
@st.cache_data(ttl=600)
def get_data(symbol="BTCUSDT", interval="4h", limit=2000):
    url = "https://data-api.binance.vision/api/v3/klines"
    res = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}).json()
    df = pd.DataFrame(res, columns=["time", "open", "high", "low", "close", "volume", "ct", "qav", "trades", "tb", "tq", "ig"])
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    
    # اندیکاتورها
    df['EMA'] = df['close'].ewm(span=20).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    return df.dropna().reset_index(drop=True)

# ======================
# 2. محیط معاملاتی پیشرفته
# ======================
class AdvancedTradingEnv(gym.Env):
    def __init__(self, df, initial_balance=1000, stop_loss=0.02):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.stop_loss_pct = stop_loss
        
        # Actions: 0 = WAIT/SELL, 1 = BUY/HOLD
        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.balance = self.initial_balance
        self.position = 0  # 0: No position, 1: Holding
        self.entry_price = 0
        self.step_i = 0
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.step_i]
        return np.array([
            row['RSI'] / 100,
            row['close'] / row['EMA'],
            float(self.position),
            (row['close'] / self.entry_price) if self.entry_price > 0 else 1.0
        ], dtype=np.float32)

    def step(self, action):
        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]
        current_price = row['close']
        next_price = next_row['close']
        reward = 0

        # منطق پوزیشن
        if action == 1: # قصد خرید یا نگهداری
            if self.position == 0: # ورود به معامله
                self.position = 1
                self.entry_price = current_price
            
            # چک کردن استاپ لاس
            if (next_price / self.entry_price) - 1 <= -self.stop_loss_pct:
                reward = -self.stop_loss_pct * 10 # جریمه سنگین برای استاپ خوردن
                self.balance *= (1 - self.stop_loss_pct)
                self.position = 0
                self.entry_price = 0
            else:
                # سود یا ضرر شناور
                reward = (next_price - current_price) / current_price
                self.balance *= (1 + reward)
        
        elif action == 0 and self.position == 1: # خروج از معامله
            reward = (current_price - self.entry_price) / self.entry_price
            self.position = 0
            self.entry_price = 0

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. اجرای برنامه و رابط کاربری
# ======================
df = get_data(limit=1000)
st.sidebar.header("⚙️ Settings")
init_cash = st.sidebar.number_input("Initial Balance ($)", value=1000)
sl_pct = st.sidebar.slider("Stop Loss (%)", 1, 10, 2) / 100

env = AdvancedTradingEnv(df, initial_balance=init_cash, stop_loss=sl_pct)
MODEL_NAME = "adv_trading_model"

# دکمه‌های آموزش و حذف
col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Train Model"):
        with st.spinner("Training on Historical Data..."):
            model = PPO("MlpPolicy", env, verbose=0)
            model.learn(total_timesteps=30000)
            model.save(MODEL_NAME)
        st.success("Trained! ✅")
        st.rerun()

# لود و نمایش پیش‌بینی
if os.path.exists(f"{MODEL_NAME}.zip"):
    model = PPO.load(MODEL_NAME)
    
    # --- تایمر کندل بعدی ---
    last_candle_time = datetime.fromtimestamp(df.iloc[-1]['time'] / 1000)
    next_candle_time = last_candle_time + timedelta(hours=4)
    time_diff = next_candle_time - datetime.now()
    
    st.info(f"⏳ زمان باقی‌مانده تا کندل بعدی: {str(time_diff).split('.')[0]}")

    # --- پیش‌بینی برای کندل فعلی ---
    obs, _ = env.reset()
    # اجرای مدل روی کل داده‌ها برای محاسبه سود نهایی
    for i in range(len(df)-1):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, _, _ = env.step(action)
    
    final_profit = env.balance - init_cash
    
    # نمایش وضعیت لحظه‌ای
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${df.iloc[-1]['close']:,}")
    c2.metric("Final Balance", f"${env.balance:.2f}")
    c3.metric("Total Profit", f"${final_profit:.2f}", delta=f"{(final_profit/init_cash)*100:.2f}%")

    # وضعیت سیگنال نهایی (Prediction)
    st.divider()
    last_obs = obs # آخرین وضعیت بازار
    final_action, _ = model.predict(last_obs, deterministic=True)
    
    if final_action == 1:
        st.success(f"🎯 SIGNAL: **BUY / HOLD**")
        if env.entry_price > 0:
            st.write(f"🔹 Entry Price: `${env.entry_price:.2f}`")
            st.write(f"🛑 Stop Loss: `${env.entry_price * (1-sl_pct):.2f}`")
    else:
        st.warning("🎯 SIGNAL: **WAIT / SELL**")

else:
    st.warning("لطفاً ابتدا مدل را آموزش دهید.")
