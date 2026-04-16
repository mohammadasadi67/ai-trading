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

st.set_page_config(layout="wide", page_title="AI Hunter Trader")
st.title("🏹 AI HUNTER: HIGH-QUALITY TRADES ONLY")

# ======================
# 1. دریافت داده‌ها
# ======================
@st.cache_data(ttl=3600)
def get_historical_data(symbol="BTCUSDT", interval="4h", years=3):
    url = "https://data-api.binance.vision/api/v3/klines"
    total_needed = years * 365 * 6 
    all_candles = []
    last_time = None
    
    with st.spinner("در حال دریافت دیتای ۳ ساله..."):
        while len(all_candles) < total_needed:
            params = {"symbol": symbol, "interval": interval, "limit": 1000}
            if last_time: params["endTime"] = last_time - 1
            try:
                res = requests.get(url, params=params).json()
                if not res or len(res) == 0: break
                all_candles = res + all_candles
                last_time = res[0][0]
                time.sleep(0.01)
            except: break

    df = pd.DataFrame(all_candles, columns=["time", "open", "high", "low", "close", "volume", "ct", "qav", "trades", "tb", "tq", "ig"])
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    df['date'] = pd.to_datetime(df['time'], unit='ms')
    
    # اندیکاتورهای پایه
    df['EMA_Long'] = df['close'].ewm(span=50).mean()
    df['body_pct'] = (df['close'] - df['open']) / df['open']
    df['rel_vol'] = df['volume'] / df['volume'].rolling(20).mean()
    
    return df.dropna().reset_index(drop=True)

# ======================
# 2. محیط معاملاتی سخت‌گیر
# ======================
class HunterEnv(gym.Env):
    def __init__(self, df, initial_balance=1000, stop_loss=0.05, fee=0.001):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.sl_pct = stop_loss
        self.fee = fee
        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.balance = self.initial_balance
        self.position = 0 
        self.entry_price = 0
        self.step_i = 50 
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.step_i]
        dist_ema = (row['close'] - row['EMA_Long']) / row['EMA_Long']
        floating_pnl = (row['close'] / self.entry_price) - 1 if self.entry_price > 0 else 0
        return np.array([row['body_pct'], dist_ema, row['rel_vol'], float(self.position), floating_pnl], dtype=np.float32)

    def step(self, action):
        if self.step_i >= len(self.df) - 2:
            return self._get_obs(), 0, True, False, {}

        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]
        price_diff = (next_row['close'] - row['close']) / row['close']
        
        reward = 0
        
        if action == 1: # BUY/HOLD
            if self.position == 0: # باز کردن ترید
                self.position = 1
                self.entry_price = row['close']
                self.balance *= (1 - self.fee)
                reward = -2 # جریمه ورود (باید دلیل خیلی خوبی برای ورود داشته باشه)
            
            pnl = (next_row['close'] / self.entry_price) - 1
            if pnl <= -self.sl_pct: # استاپ خوردن
                reward = -50
                self.balance *= (1 - self.sl_pct)
                self.position = 0
                self.entry_price = 0
            else:
                reward = price_diff * 100 # پاداش همراهی با روند
        
        else: # WAIT/SELL
            if self.position == 1: # بستن پوزیشن
                pnl = (row['close'] - self.entry_price) / self.entry_price
                if pnl > 0.02: # فقط پاداش بزرگ برای سودهای بالای ۲٪
                    reward = pnl * 500 
                else: # جریمه برای تریدهای بی‌خاصیت و الکی
                    reward = -10
                self.balance *= (1 - self.fee)
                self.position = 0
                self.entry_price = 0
            else:
                reward = 0.5 # پاداش برای صبوری و ترید نکردن بیهوده

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. اجرای برنامه
# ======================
df = get_historical_data(years=3)

st.sidebar.header("🛠 تنظیمات شکارچی")
init_cash = st.sidebar.number_input("سرمایه ($)", value=1000)
exchange_fee = st.sidebar.slider("کارمزد (%)", 0.0, 0.5, 0.1) / 100
sl_val = st.sidebar.slider("حد ضرر (%)", 1, 10, 5) / 100

if st.sidebar.button("♻️ پاکسازی و آموزش مجدد"):
    if os.path.exists("hunter_model.zip"): os.remove("hunter_model.zip")
    st.rerun()

env = HunterEnv(df, initial_balance=init_cash, stop_loss=sl_val, fee=exchange_fee)
MODEL_NAME = "hunter_model"

if not os.path.exists(f"{MODEL_NAME}.zip"):
    if st.button("🚀 شروع آموزش مدل شکارچی (صبور)"):
        with st.spinner("در حال آموزش دیدن برای " + "نخریدن" + " در مواقع خطر..."):
            model = PPO("MlpPolicy", env, verbose=0, learning_rate=0.0002)
            model.learn(total_timesteps=200000)
            model.save(MODEL_NAME)
        st.success("آموزش تمام شد!")
        st.rerun()

if os.path.exists(f"{MODEL_NAME}.zip"):
    model = PPO.load(MODEL_NAME)
    obs, _ = env.reset()
    trade_log = []
    current_trade = None

    for i in range(len(df) - 2):
        action, _ = model.predict(obs, deterministic=True)
        row = df.iloc[i]
        if action == 1 and current_trade is None:
            current_trade = {"In": row['date'], "Price": row['close']}
        elif current_trade is not None:
            next_row = df.iloc[i+1]
            if action == 0 or (next_row['close'] <= current_trade['Price'] * (1 - sl_val)):
                pnl = (((next_row['close'] - current_trade['Price']) / current_trade['Price']) - (2 * exchange_fee))
                trade_log.append({
                    "Date": current_trade['In'],
                    "Entry": current_trade['Price'],
                    "Exit": next_row['close'],
                    "PnL %": round(pnl * 100, 2),
                    "Profit $": round(pnl * init_cash, 2)
                })
                current_trade = None
        obs, _, done, _, _ = env.step(action)
        if done: break

    t_df = pd.DataFrame(trade_log)
    
    if not t_df.empty:
        st.divider()
        c1, c2, c3 = st.columns(3)
        total_p = t_df['Profit $'].sum()
        c1.metric("سرمایه نهایی", f"${init_cash + total_p:.2f}")
        c2.metric("سود کل", f"${total_p:.2f}", f"{(total_p/init_cash)*100:.2f}%")
        c3.metric("تعداد ترید", len(t_df))
        st.dataframe(t_df.sort_values(by="Date", ascending=False), use_container_width=True)
    else:
        st.warning("مدل آنقدر سخت‌گیر شده که فعلاً هیچ تریدی پیدا نکرده! دوباره Train کنید.")

    # وضعیت زنده
    st.divider()
    last_action, _ = model.predict(obs, deterministic=True)
    if last_action == 1:
        st.success(f"🎯 سیگنال: **BUY** | قیمت: {df.iloc[-1]['close']}")
    else:
        st.info("🎯 سیگنال: **WAIT** (مدل فعلاً منتظر فرصت است)")
