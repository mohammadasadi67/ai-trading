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

st.set_page_config(layout="wide", page_title="AI Price Action Trader")
st.title("🚀 AI TRADER PRO (FEE & DATE FILTER)")

# ======================
# 1. دریافت داده‌ها
# ======================
@st.cache_data(ttl=3600)
def get_historical_data(symbol="BTCUSDT", interval="4h", years=3):
    url = "https://data-api.binance.vision/api/v3/klines"
    total_needed = years * 365 * 6 
    all_candles = []
    last_time = None
    
    with st.spinner("در حال دریافت دیتای زنده..."):
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
# 2. محیط معاملاتی هوشمند
# ======================
class SmartTradingEnv(gym.Env):
    def __init__(self, df, initial_balance=1000, stop_loss=0.03, fee=0.001):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.sl_pct = stop_loss
        self.fee = fee
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
        # جلوگیری از خروج از محدوده Index
        if self.step_i >= len(self.df) - 2:
            return self._get_obs(), 0, True, False, {}

        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]
        price_diff = (next_row['close'] - row['close']) / row['close']
        reward = 0

        if action == 1: # BUY/HOLD
            if self.position == 0:
                self.position = 1
                self.entry_price = row['close']
                self.balance *= (1 - self.fee)
            
            pnl = (next_row['close'] / self.entry_price) - 1
            if pnl <= -self.sl_pct:
                reward = -20
                self.balance *= (1 - self.sl_pct)
                self.position = 0
                self.entry_price = 0
                done = True # توقف در صورت کال مارجین مجازی
            else:
                reward = price_diff * 15
                self.balance *= (1 + price_diff)
        
        else: # WAIT/SELL
            if self.position == 1:
                self.balance *= (1 - self.fee)
                pnl = (row['close'] - self.entry_price) / self.entry_price
                reward = (pnl - self.fee) * 25
                self.position = 0
                self.entry_price = 0
            else:
                reward = 0.01 # پاداش ناچیز برای حفظ سرمایه

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. اجرای اصلی
# ======================
df = get_historical_data(years=3)

# Sidebar
st.sidebar.header("📊 تنظیمات صرافی")
init_cash = st.sidebar.number_input("سرمایه اولیه ($)", value=1000)
exchange_fee = st.sidebar.slider("کارمزد صرافی (%)", 0.0, 0.5, 0.1) / 100
sl_val = st.sidebar.slider("Stop Loss (%)", 1, 10, 4) / 100

st.sidebar.header("📅 فیلتر زمان")
min_d, max_d = df['date'].min().to_pydatetime(), df['date'].max().to_pydatetime()
date_range = st.sidebar.date_input("بازه نمایش معاملات", [min_d, max_d])

env = SmartTradingEnv(df, initial_balance=init_cash, stop_loss=sl_val, fee=exchange_fee)
MODEL_NAME = "final_trader_model"

col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 شروع آموزش"):
        with st.spinner("مدل در حال یادگیری..."):
            model = PPO("MlpPolicy", env, verbose=0)
            model.learn(total_timesteps=100000)
            model.save(MODEL_NAME)
        st.success("آموزش تمام شد!")
        st.rerun()

if os.path.exists(f"{MODEL_NAME}.zip"):
    model = PPO.load(MODEL_NAME)
    obs, _ = env.reset()
    trade_log = []
    current_trade = None

    # شبیه‌سازی با رعایت مرز Index
    for i in range(len(df) - 2):
        action, _ = model.predict(obs, deterministic=True)
        row = df.iloc[i]
        
        if action == 1 and current_trade is None:
            current_trade = {"Date": row['date'], "Price": row['close']}
        elif current_trade is not None:
            next_row = df.iloc[i+1]
            # خروج بر اساس مدل یا استاپ لاس
            if action == 0 or (next_row['close'] <= current_trade['Price'] * (1 - sl_val)):
                exit_p = next_row['close']
                pnl = (((exit_p - current_trade['Price']) / current_trade['Price']) - (2 * exchange_fee))
                trade_log.append({
                    "تاریخ ورود": current_trade['Date'],
                    "قیمت ورود": round(current_trade['Price'], 2),
                    "قیمت خروج": round(exit_p, 2),
                    "سود خالص (%)": round(pnl * 100, 2),
                    "سود خالص ($)": round(pnl * init_cash, 2)
                })
                current_trade = None
        
        obs, _, done, _, _ = env.step(action)
        if done: break

    t_df = pd.DataFrame(trade_log)
    if not t_df.empty:
        if len(date_range) == 2:
            t_df = t_df[(t_df['تاریخ ورود'].dt.date >= date_range[0]) & (t_df['تاریخ ورود'].dt.date <= date_range[1])]

        st.divider()
        c1, c2, c3 = st.columns(3)
        total_p = t_df['سود خالص ($)'].sum()
        c1.metric("سرمایه نهایی", f"${init_cash + total_p:.2f}")
        c2.metric("سود/ضرر کل", f"${total_p:.2f}", f"{ (total_p/init_cash)*100:.2f}%")
        c3.metric("تعداد ترید", len(t_df))

        st.dataframe(t_df.sort_values(by="تاریخ ورود", ascending=False), use_container_width=True)
    else:
        st.info("تریدی یافت نشد. مدل را آموزش دهید.")
    
    # سیگنال لحظه‌ای
    st.divider()
    last_action, _ = model.predict(obs, deterministic=True)
    if last_action == 1:
        st.success(f"🎯 سیگنال: **BUY / HOLD** | قیمت: {df.iloc[-1]['close']}")
    else:
        st.warning("🎯 سیگنال: **WAIT / SELL**")
