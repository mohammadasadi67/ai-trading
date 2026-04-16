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

# تنظیمات صفحه
st.set_page_config(layout="wide", page_title="AI Crypto Trader Pro")
st.title("🚀 AI TRADER PRO: SL/TP, HOLD & PNL TRACKER")

# ======================
# 1. دریافت داده‌های ۳ ساله (Batch Fetching)
# ======================
@st.cache_data(ttl=3600)
def get_historical_data(symbol="BTCUSDT", interval="4h", years=3):
    url = "https://data-api.binance.vision/api/v3/klines"
    total_needed = years * 365 * 6 # تعداد تقریبی کندل‌های 4 ساعته
    all_candles = []
    last_time = None
    
    with st.spinner(f"در حال دریافت داده‌های {years} سال اخیر از بایننس..."):
        while len(all_candles) < total_needed:
            params = {"symbol": symbol, "interval": interval, "limit": 1000}
            if last_time: params["endTime"] = last_time - 1
            
            try:
                res = requests.get(url, params=params).json()
                if not res or len(res) == 0: break
                all_candles = res + all_candles
                last_time = res[0][0]
                if len(all_candles) >= total_needed: break
                time.sleep(0.1)
            except: break

    df = pd.DataFrame(all_candles, columns=["time", "open", "high", "low", "close", "volume", "ct", "qav", "trades", "tb", "tq", "ig"])
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    
    # محاسبه اندیکاتورها
    df['EMA'] = df['close'].ewm(span=20).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    return df.dropna().reset_index(drop=True)

# ======================
# 2. محیط معاملاتی (Environment)
# ======================
class AdvancedTradingEnv(gym.Env):
    def __init__(self, df, initial_balance=1000, stop_loss=0.02):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.stop_loss_pct = stop_loss
        self.action_space = spaces.Discrete(2) # 0: WAIT/SELL, 1: BUY/HOLD
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.balance = self.initial_balance
        self.position = 0 
        self.entry_price = 0
        self.step_i = 0
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.step_i]
        return np.array([
            row['RSI'] / 100,
            row['close'] / row['EMA'] if row['EMA'] != 0 else 1.0,
            float(self.position),
            (row['close'] / self.entry_price) if self.entry_price > 0 else 1.0
        ], dtype=np.float32)

    def step(self, action):
        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]
        reward = 0

        if action == 1: # BUY or HOLD
            if self.position == 0:
                self.position = 1
                self.entry_price = row['close']
            
            # بررسی استاپ لاس
            if (next_row['close'] / self.entry_price) - 1 <= -self.stop_loss_pct:
                reward = -2 # جریمه سنگین
                self.balance *= (1 - self.stop_loss_pct)
                self.position = 0
                self.entry_price = 0
            else:
                reward = (next_row['close'] - row['close']) / row['close']
                self.balance *= (1 + reward)
        
        elif action == 0 and self.position == 1: # SELL
            reward = (row['close'] - self.entry_price) / self.entry_price
            self.position = 0
            self.entry_price = 0

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. داشبورد و اجرای اصلی
# ======================
df = get_historical_data(years=3)

# Sidebar Settings
st.sidebar.header("⚙️ Trading Strategy")
init_cash = st.sidebar.number_input("Initial Balance ($)", value=1000)
sl_pct = st.sidebar.slider("Stop Loss (%)", 1, 10, 2) / 100
train_steps = st.sidebar.select_slider("Training Intensity", options=[10000, 50000, 100000], value=50000)

env = AdvancedTradingEnv(df, initial_balance=init_cash, stop_loss=sl_pct)
MODEL_NAME = "trading_model_pro"

# کانتینر دکمه‌ها
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("🚀 Train New Model"):
        with st.spinner("مدل در حال یادگیری الگوهای ۳ سال اخیر است..."):
            model = PPO("MlpPolicy", env, verbose=0)
            model.learn(total_timesteps=train_steps)
            model.save(MODEL_NAME)
        st.success("آموزش کامل شد! ✅")
        st.rerun()

with col_btn2:
    if st.button("🗑 Reset Data"):
        if os.path.exists(f"{MODEL_NAME}.zip"): os.remove(f"{MODEL_NAME}.zip")
        st.cache_data.clear()
        st.rerun()

# --- بخش نتایج (فقط اگر مدل وجود داشته باشد) ---
if os.path.exists(f"{MODEL_NAME}.zip"):
    model = PPO.load(MODEL_NAME)
    
    # اجرای بک‌تست برای استخراج تاریخچه
    obs, _ = env.reset()
    trade_log = []
    current_trade = None

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

    # نمایش آمار کلی
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Price", f"${df.iloc[-1]['close']:,}")
    m2.metric("Total Trades", len(trades_df))
    if not trades_df.empty:
        win_rate = (len(trades_df[trades_df['PnL (%)'] > 0]) / len(trades_df)) * 100
        m3.metric("Win Rate", f"{win_rate:.1f}%")
        m4.metric("Net PnL (%)", f"{trades_df['PnL (%)'].sum():.2f}%")

    # فیلتر و جدول معاملات
    st.subheader("📜 Trade History & PnL Log")
    filter_choice = st.radio("Filter History:", ["All", "Profits", "Losses"], horizontal=True)
    
    display_df = trades_df
    if filter_choice == "Profits": display_df = trades_df[trades_df['PnL (%)'] > 0]
    elif filter_choice == "Losses": display_df = trades_df[trades_df['PnL (%)'] <= 0]

    st.dataframe(display_df.tail(100), use_container_width=True)

    # سیگنال لحظه‌ای
    st.divider()
    last_action, _ = model.predict(obs, deterministic=True)
    if last_action == 1:
        st.success(f"🎯 CURRENT SIGNAL: **BUY / HOLD** (Entry: {df.iloc[-1]['close']})")
    else:
        st.warning("🎯 CURRENT SIGNAL: **WAIT / SELL**")
    
    # تایمر کندل بعدی
    next_c = datetime.fromtimestamp(df.iloc[-1]['time']/1000) + timedelta(hours=4)
    st.info(f"⏳ زمان تا کندل ۴ ساعته بعدی: {str(next_c - datetime.now()).split('.')[0]}")

else:
    st.warning("👈 لطفاً روی دکمه Train کلیک کنید تا هوش مصنوعی شروع به تحلیل ۳ سال اخیر کند.")
