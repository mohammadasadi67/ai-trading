import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

# --- تنظیمات صفحه ---
st.set_page_config(layout="wide", page_title="AI Trading Dashboard")
st.title("🤖 MOHAMMAD PATTERN (RL Advanced Backtest)")

# ======================
# 1. دریافت ۲۰۰۰ کندل
# ======================
@st.cache_data(ttl=300)
def get_data_2000(symbol="BTCUSDT", interval="4h"):
    url = "https://data-api.binance.vision/api/v3/klines"
    all_candles = []
    last_time = None
    
    # دریافت در دو مرحله (چون سقف هر درخواست ۱۰۰۰ تاست)
    for _ in range(2):
        params = {"symbol": symbol, "interval": interval, "limit": 1000}
        if last_time: params["endTime"] = last_time - 1
        res = requests.get(url, params=params).json()
        all_candles = res + all_candles
        last_time = res[0][0]
        
    df = pd.DataFrame(all_candles, columns=["time","open","high","low","close","volume","ct","qav","trades","tb","tq","ig"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    return df.sort_values("time").reset_index(drop=True)

# ======================
# 2. محیط معاملاتی برای RL
# ======================
class TradingEnv(gym.Env):
    def __init__(self, df):
        super().__init__()
        self.df = df
        self.action_space = spaces.Discrete(2) # 0: Wait, 1: Buy
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.current_step = 1
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.current_step]
        prev_row = self.df.iloc[self.current_step-1]
        return np.array([row['open']/prev_row['close'], row['high']/row['open'], 
                         row['low'] / row['open'], row['close']/row['open'], 1.0], dtype=np.float32)

    def step(self, action):
        p_now = self.df.iloc[self.current_step]['open']
        p_next = self.df.iloc[self.current_step]['close'] # خروج فرضی در انتهای همان کندل
        
        reward = (p_next - p_now) / p_now if action == 1 else 0
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. اجرای پنل کاربری و محاسبات
# ======================
df = get_data_2000()

# Sidebar
st.sidebar.header("تنظیمات سرمایه")
initial_capital = st.sidebar.number_input("سرمایه اولیه ($)", value=1000.0)
fee_rate = 0.001 # 0.1% کارمزد

if not df.empty:
    with st.spinner('در حال آموزش هوش مصنوعی روی ۲۰۰۰ کندل...'):
        env = TradingEnv(df)
        model = PPO("MlpPolicy", env, verbose=0).learn(total_timesteps=5000)

    # تست و استخراج نتایج
    obs, _ = env.reset()
    history = []
    current_balance = initial_capital

    for i in range(len(df)-1):
        action, _ = model.predict(obs)
        price_open = df.iloc[i]['open']
        price_close = df.iloc[i]['close']
        
        signal = "WAIT"
        pnl_pct = 0.0
        
        if action == 1: # مدل سیگنال خرید داده
            signal = "🟢 BUY"
            raw_return = (price_close - price_open) / price_open
            net_return = raw_return - (fee_rate * 2) # خرید و فروش
            pnl_pct = net_return * 100
            current_balance *= (1 + net_return)
        
        history.append({
            "Time": df.iloc[i]['time'],
            "Price": f"${price_open:,.2f}",
            "Signal": signal,
            "PnL %": pnl_pct,
            "Balance": current_balance
        })
        obs, _, done, _, _ = env.step(action)
        if done: break

    # تبدیل به دیتای نهایی
    report_df = pd.DataFrame(history)

    # نمایش متریک‌های اصلی
    total_profit = current_balance - initial_capital
    profit_pct = (total_profit / initial_capital) * 100
    
    c1, c2, c3 = st.columns(3)
    c1.metric("موجودی نهایی", f"${current_balance:,.2f}")
    c2.metric("سود کل", f"${total_profit:,.2f}", f"{profit_pct:.2f}%")
    c3.metric("تعداد کندل بررسی شده", len(df))

    st.divider()

    # نمایش جدول با استایل
    st.subheader("📋 گزارش دقیق سیگنال‌ها و موجودی (۲۰۰۰ کندل)")
    st.dataframe(
        report_df.sort_values("Time", ascending=False),
        use_container_width=True,
        column_config={
            "PnL %": st.column_config.NumberColumn("سود معامله", format="%.2f%%"),
            "Balance": st.column_config.NumberColumn("موجودی لحظه‌ای", format="$%.2f"),
            "Time": "زمان کندل"
        }
    )
