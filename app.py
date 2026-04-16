import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import time
from datetime import datetime

# RL Libraries
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

st.set_page_config(layout="wide", page_title="AI Hunter 2026")
st.title("🏹 AI HUNTER: TRAINED ON HISTORY, TESTED ON 2026")

# ======================
# 1. دریافت داده‌ها (۳ سال کامل)
# ======================
@st.cache_data(ttl=3600)
def get_historical_data(symbol="BTCUSDT", interval="4h", years=3.5):
    url = "https://data-api.binance.vision/api/v3/klines"
    total_needed = int(years * 365 * 6)
    all_candles = []
    last_time = None
    
    with st.spinner("در حال جمع‌آوری تاریخچه قیمتی برای بازنگری مدل..."):
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
    
    # اندیکاتورها برای درک فراز و نشیب
    df['EMA_Long'] = df['close'].ewm(span=50).mean()
    df['body_pct'] = (df['close'] - df['open']) / df['open']
    df['rel_vol'] = df['volume'] / df['volume'].rolling(20).mean()
    
    return df.dropna().reset_index(drop=True)

# ======================
# 2. محیط معاملاتی با پاداش متعادل
# ======================
class BalancedHunterEnv(gym.Env):
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
            if self.position == 0:
                self.position = 1
                self.entry_price = row['close']
                self.balance *= (1 - self.fee)
                reward = -0.5 # جریمه کم برای تشویق به شکار
            
            pnl = (next_row['close'] / self.entry_price) - 1
            if pnl <= -self.sl_pct:
                reward = -30
                self.balance *= (1 - self.sl_pct)
                self.position = 0
                self.entry_price = 0
            else:
                reward = price_diff * 180 # پاداش همراهی با روند
        
        else: # WAIT/SELL
            if self.position == 1:
                pnl = (row['close'] - self.entry_price) / self.entry_price
                reward = (pnl * 500) if pnl > 0.01 else -2
                self.balance *= (1 - self.fee)
                self.position = 0
                self.entry_price = 0
            else:
                reward = 0.02 # پاداش اندک برای نقد ماندن

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. اجرای اصلی
# ======================
df = get_historical_data()

st.sidebar.header("⚙️ تنظیمات مدل")
init_cash = st.sidebar.number_input("سرمایه ($)", value=1000)
exchange_fee = st.sidebar.slider("کارمزد (%)", 0.0, 0.5, 0.1) / 100
sl_val = st.sidebar.slider("حد ضرر (%)", 1, 10, 5) / 100

if st.sidebar.button("♻️ حذف مدل قبلی"):
    if os.path.exists("hunter_2026.zip"): os.remove("hunter_2026.zip")
    st.rerun()

env = BalancedHunterEnv(df, initial_balance=init_cash, stop_loss=sl_val, fee=exchange_fee)
MODEL_NAME = "hunter_2026"

if not os.path.exists(f"{MODEL_NAME}.zip"):
    if st.button("🚀 شروع آموزش (۳۰۰,۰۰۰ گام بازنگری)"):
        with st.spinner("هوش مصنوعی در حال بازنگری تمام فراز و نشیب‌های ۳ سال اخیر..."):
            model = PPO("MlpPolicy", env, verbose=0, learning_rate=0.0002)
            model.learn(total_timesteps=300000)
            model.save(MODEL_NAME)
        st.success("آموزش تمام شد!")
        st.rerun()

if os.path.exists(f"{MODEL_NAME}.zip"):
    model = PPO.load(MODEL_NAME)
    obs, _ = env.reset()
    trade_log = []
    current_trade = None
    
    # فیلتر برای شروع از اول ۲۰۲۶ در نمایش نتایج
    start_of_2026 = pd.to_datetime("2026-01-01")

    for i in range(len(df) - 2):
        action, _ = model.predict(obs, deterministic=True)
        row = df.iloc[i]
        
        # ثبت معامله فقط اگر بعد از اول ۲۰۲۶ باشد
        if row['date'] >= start_of_2026:
            if action == 1 and current_trade is None:
                current_trade = {"In": row['date'], "Price": row['close']}
            elif current_trade is not None:
                next_row = df.iloc[i+1]
                if action == 0 or (next_row['close'] <= current_trade['Price'] * (1 - sl_val)):
                    pnl = (((next_row['close'] - current_trade['Price']) / current_trade['Price']) - (2 * exchange_fee))
                    trade_log.append({
                        "تاریخ": current_trade['In'],
                        "ورود": current_trade['Price'],
                        "خروج": next_row['close'],
                        "سود %": round(pnl * 100, 2),
                        "سود $": round(pnl * init_cash, 2)
                    })
                    current_trade = None
        
        obs, _, done, _, _ = env.step(action)
        if done: break

    t_df = pd.DataFrame(trade_log)
    
    st.divider()
    st.subheader("📊 عملکرد هوش مصنوعی در سال ۲۰۲۶")
    if not t_df.empty:
        c1, c2, c3 = st.columns(3)
        total_p = t_df['سود $'].sum()
        c1.metric("سرمایه نهایی", f"${init_cash + total_p:.2f}")
        c2.metric("سود خالص ۲۰۲۶", f"${total_p:.2f}", f"{(total_p/init_cash)*100:.2f}%")
        c3.metric("تعداد ترید", len(t_df))
        st.dataframe(t_df.sort_values(by="تاریخ", ascending=False), use_container_width=True)
    else:
        st.warning("در سال ۲۰۲۶ هنوز تریدی با این استراتژی انجام نشده است.")

    st.divider()
    last_action, _ = model.predict(obs, deterministic=True)
    if last_action == 1:
        st.success(f"🎯 سیگنال لحظه‌ای: **BUY** (بر اساس بازنگری روندها)")
    else:
        st.info("🎯 سیگنال لحظه‌ای: **WAIT** (در انتظار تایید روند ۲۰۲۶)")
