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

st.set_page_config(layout="wide", page_title="AI Price Action Trader Pro")
st.title("🚀 AI TRADER PRO: PRICE ACTION & PNL DASHBOARD")

# ======================
# 1. دریافت داده‌های ۳ ساله
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
    
    # ویژگی‌های پرایس اکشن
    df['body_size'] = (df['close'] - df['open']) / df['open']
    df['upper_wick'] = (df['high'] - np.maximum(df['close'], df['open'])) / df['open']
    df['lower_wick'] = (np.minimum(df['close'], df['open']) - df['low']) / df['open']
    df['rel_volume'] = df['volume'] / df['volume'].rolling(20).mean()
    
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
        self.action_space = spaces.Discrete(2) # 0: WAIT/SELL, 1: BUY/HOLD
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

        if action == 1: # BUY or HOLD
            if self.position == 0:
                self.position = 1
                self.entry_price = row['close']
            
            pnl = (next_row['close'] / self.entry_price) - 1
            if pnl <= -self.stop_loss_pct:
                reward = -10 
                self.balance *= (1 - self.stop_loss_pct)
                self.position = 0
                self.entry_price = 0
            else:
                reward = price_diff * 20
                self.balance *= (1 + price_diff)
        
        else: # WAIT/SELL
            if self.position == 1:
                reward = (row['close'] - self.entry_price) / self.entry_price * 15
                self.position = 0
                self.entry_price = 0
            elif price_diff > 0.01: # جریمه برای جا ماندن از بازار صعودی
                reward = -2

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. داشبورد اصلی
# ======================
df = get_historical_data(years=3)

st.sidebar.header("⚙️ Strategy Settings")
init_cash = st.sidebar.number_input("Initial Balance ($)", value=1000)
sl_val = st.sidebar.slider("Stop Loss (%)", 1, 10, 4)
sl_pct = sl_val / 100
train_steps = st.sidebar.select_slider("Train Intensity", options=[50000, 100000, 200000], value=100000)

env = PriceActionEnv(df, initial_balance=init_cash, stop_loss=sl_pct)
MODEL_NAME = "pa_trading_model"

col_a, col_b = st.columns(2)
with col_a:
    if st.button("🚀 Train Model (Price Action)"):
        with st.spinner("یادگیری کندل‌ها آغاز شد..."):
            model = PPO("MlpPolicy", env, verbose=0, learning_rate=0.0003)
            model.learn(total_timesteps=train_steps)
            model.save(MODEL_NAME)
        st.success("مدل با موفقیت آموزش دید! ✅")
        st.rerun()
with col_b:
    if st.button("🗑 Reset & Clear Cache"):
        st.cache_data.clear()
        if os.path.exists(f"{MODEL_NAME}.zip"): os.remove(f"{MODEL_NAME}.zip")
        st.rerun()

# --- خروجی و گزارشات ---
if os.path.exists(f"{MODEL_NAME}.zip"):
    model = PPO.load(MODEL_NAME)
    obs, _ = env.reset()
    trade_log = []
    current_trade = None

    # شبیه‌سازی دقیق تاریخچه
    for i in range(len(df) - 2):
        action, _ = model.predict(obs, deterministic=True)
        row = df.iloc[i]
        
        if action == 1 and current_trade is None:
            current_trade = {"Entry Time": pd.to_datetime(row['time'], unit='ms'), "Entry Price": row['close']}
        elif current_trade is not None:
            next_row = df.iloc[i+1]
            if action == 0 or (next_row['close'] <= current_trade['Entry Price'] * (1 - sl_pct)):
                exit_price = next_row['close']
                pnl_pct = ((exit_price - current_trade['Entry Price']) / current_trade['Entry Price']) * 100
                trade_log.append({
                    "Entry Time": current_trade['Entry Time'],
                    "Exit Time": pd.to_datetime(next_row['time'], unit='ms'),
                    "Entry Price": round(current_trade['Entry Price'], 2),
                    "Exit Price": round(exit_price, 2),
                    "PnL (%)": round(pnl_pct, 2),
                    "Outcome": "✅ Profit" if pnl_pct > 0 else "❌ Loss"
                })
                current_trade = None
        obs, _, done, _, _ = env.step(action)
        if done: break

    trades_df = pd.DataFrame(trade_log)

    st.divider()
    # معیارهای کلیدی
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Price", f"${df.iloc[-1]['close']:,}")
    m2.metric("Total Trades", len(trades_df))
    if not trades_df.empty:
        win_rate = (len(trades_df[trades_df['PnL (%)'] > 0]) / len(trades_df)) * 100
        m3.metric("Win Rate", f"{win_rate:.1f}%")
        m4.metric("Net Profit (%)", f"{trades_df['PnL (%)'].sum():.2f}%")

        st.subheader("📜 Trade History")
        f_choice = st.radio("Show:", ["All", "Profits", "Losses"], horizontal=True)
        if f_choice == "Profits": display_df = trades_df[trades_df['PnL (%)'] > 0]
        elif f_choice == "Losses": display_df = trades_df[trades_df['PnL (%)'] <= 0]
        else: display_df = trades_df
        st.dataframe(display_df.tail(100), use_container_width=True)
    else:
        st.warning("⚠️ هیچ تریدی در این بازه ثبت نشد. شدت آموزش یا Stop Loss را تغییر دهید.")

    # پیش‌بینی زنده
    st.divider()
    last_action, _ = model.predict(obs, deterministic=True)
    if last_action == 1:
        st.success(f"🎯 SIGNAL: **BUY / HOLD** (Entry: {df.iloc[-1]['close']})")
    else:
        st.warning("🎯 SIGNAL: **WAIT / SELL**")
    
    next_c = datetime.fromtimestamp(df.iloc[-1]['time']/1000) + timedelta(hours=4)
    st.info(f"⏳ زمان تا کندل بعدی: {str(next_c - datetime.now()).split('.')[0]}")
else:
    st.info("ابتدا مدل را آموزش دهید تا تحلیل تاریخچه ۳ ساله نمایش داده شود.")
