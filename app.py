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
st.title("🚀 AI TRADER PRO: PRICE ACTION LOGIC")

# ======================
# 1. دریافت داده‌ها
# ======================
@st.cache_data(ttl=3600)
def get_historical_data(symbol="BTCUSDT", interval="4h", years=3):
    url = "https://data-api.binance.vision/api/v3/klines"
    total_needed = years * 365 * 6 
    all_candles = []
    last_time = None
    
    with st.spinner(f"در حال دریافت داده‌های {years} سال اخیر..."):
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
    
    # --- ویژگی‌های پرایس اکشن (Price Action Features) ---
    df['body_size'] = (df['close'] - df['open']) / df['open']
    df['upper_wick'] = (df['high'] - np.maximum(df['close'], df['open'])) / df['open']
    df['lower_wick'] = (np.minimum(df['close'], df['open']) - df['low']) / df['open']
    df['rel_volume'] = df['volume'] / df['volume'].rolling(20).mean()
    df['returns'] = df['close'].pct_change()
    
    return df.dropna().reset_index(drop=True)

# ======================
# 2. محیط معاملاتی پرایس اکشن
# ======================
class PriceActionEnv(gym.Env):
    def __init__(self, df, initial_balance=1000, stop_loss=0.03):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.stop_loss_pct = stop_loss
        
        # 0: WAIT/SELL, 1: BUY/HOLD
        self.action_space = spaces.Discrete(2)
        # ویژگی‌ها: بدنه، سقف، کف، حجم، وضعیت پوزیشن، سود شناور
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.balance = self.initial_balance
        self.position = 0 
        self.entry_price = 0
        self.step_i = 10 # شروع از جایی که داده‌های قبلی موجود باشد
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.step_i]
        floating_pnl = (row['close'] / self.entry_price) - 1 if self.entry_price > 0 else 0
        return np.array([
            row['body_size'],
            row['upper_wick'],
            row['lower_wick'],
            row['rel_volume'] if not np.isnan(row['rel_volume']) else 1.0,
            float(self.position),
            floating_pnl
        ], dtype=np.float32)

    def step(self, action):
        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]
        price_diff = (next_row['close'] - row['close']) / row['close']
        reward = 0

        if action == 1: # BUY or HOLD
            if self.position == 0:
                self.position = 1
                self.entry_price = row['close']
            
            # چک کردن استاپ لاس
            current_pnl = (next_row['close'] / self.entry_price) - 1
            if current_pnl <= -self.stop_loss_pct:
                reward = -5 # جریمه سنگین برای ضرر
                self.balance *= (1 - self.stop_loss_pct)
                self.position = 0
                self.entry_price = 0
            else:
                reward = price_diff * 10 # تشویق برای گرفتن سود
                self.balance *= (1 + price_diff)
        
        else: # action == 0 (WAIT/SELL)
            if self.position == 1:
                pnl = (row['close'] - self.entry_price) / self.entry_price
                reward = pnl * 10
                self.position = 0
                self.entry_price = 0
            else:
                # اگر بازار صعودی بود و مدل بیرون ماند، جریمه شود (ضد ترس)
                if price_diff > 0.01:
                    reward = -1

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. اجرای اصلی
# ======================
df = get_historical_data(years=3)

st.sidebar.header("⚙️ Strategy")
init_cash = st.sidebar.number_input("Initial Balance ($)", value=1000)
sl_pct = st.sidebar.slider("Stop Loss (%)", 1, 10, 3) / 100
train_steps = st.sidebar.select_slider("Train Intensity", options=[50000, 100000, 200000], value=100000)

env = PriceActionEnv(df, initial_balance=init_cash, stop_loss=sl_pct)
MODEL_NAME = "pa_trading_model"

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("🚀 Train Price Action Model"):
        with st.spinner("مدل در حال یادگیری ساختار کندل‌ها..."):
            model = PPO("MlpPolicy", env, verbose=0, learning_rate=0.0003)
            model.learn(total_timesteps=train_steps)
            model.save(MODEL_NAME)
        st.success("یادگیری کامل شد! ✅")
        st.rerun()

if os.path.exists(f"{MODEL_NAME}.zip"):
    model = PPO.load(MODEL_NAME)
    obs, _ = env.reset()
    trade_log = []
    current_trade = None

    # شبیه‌سازی برای استخراج تاریخچه
    for i in range(len(df) - 1):
        action, _ = model.predict(obs, deterministic=True)
        row = df.iloc[i]
        
        if action == 1 and current_trade is None:
            current_trade = {"Entry Time": pd.to_datetime(row['time'], unit='ms'), "Entry Price": row['close']}
        elif (action == 0 or (current_trade and df.iloc[i+1]['close'] <= current_trade['Entry Price'] * (1-sl_pct))) and current_trade is not None:
            exit_price = df.iloc[i+1]['close']
            pnl_pct = ((exit_price - current_trade['Entry Price']) / current_trade['Entry Price']) * 100
            trade_log.append({
                "Entry Time": current_trade['Entry Time'],
                "Entry Price": round(current_trade['Entry Price'], 2),
                "Exit Price": round(exit_price, 2),
                "PnL (%)": round(pnl_pct, 2),
                "Outcome": "✅ Profit" if pnl_pct > 0 else "❌ Loss"
            })
            current_trade = None
        obs, _, _, _, _ = env.step(action)

    trades_df = pd.DataFrame(trade_log)

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Price", f"${df.iloc[-1]['close']:,}")
    m2.metric("Total Trades", len(trades_df))
    if not trades_df.empty:
        win_rate = (len(trades_df[trades_df['PnL (%)'] > 0]) / len(trades_df)) * 100
        m3.metric("Win Rate", f"{win_rate:.1f}%")
        m4.metric("Total PnL (%)", f"{trades_df['PnL (%)'].sum():.2f}%")
        st.dataframe(trades_df.tail(50), use_container_width=True)
    else:
        st.warning("⚠️ مدل هنوز جرات ترید پیدا نکرده. دوباره دکمه Train را بزنید یا شدت (Intensity) را زیاد کنید.")

    # وضعیت لحظه‌ای
    st.divider()
    last_action, _ = model.predict(obs, deterministic=True)
    if last_action == 1:
        st.success(f"🎯 LIVE SIGNAL: **BUY / HOLD**")
    else:
        st.warning("🎯 LIVE SIGNAL: **WAIT / SELL**")
