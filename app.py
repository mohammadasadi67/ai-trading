import streamlit as st
import pandas as pd
import numpy as np
import requests
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

# --- تنظیمات صفحه ---
st.set_page_config(layout="wide", page_title="RL 2000 Candle Dashboard")
st.title("🤖 MOHAMMAD PATTERN (RL 2000+ Candles)")

# ======================
# 1. DATA FETCHING (2000 CANDLES)
# ======================
@st.cache_data(ttl=300)
def get_historical_data(symbol="BTCUSDT", interval="4h", total_candles=2000):
    url = "https://data-api.binance.vision/api/v3/klines"
    all_candles = []
    last_time = None
    
    # چون بایننس در هر بار حداکثر 1000 تا می‌دهد، در دو مرحله می‌گیریم
    iterations = (total_candles // 1000) + (1 if total_candles % 1000 != 0 else 0)
    
    try:
        for _ in range(iterations):
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": 1000
            }
            if last_time:
                params["endTime"] = last_time - 1 # یک میلی‌ثانیه قبل از آخرین کندل گرفته شده
            
            response = requests.get(url, params=params).json()
            if not response:
                break
                
            all_candles = response + all_candles # اضافه کردن به ابتدای لیست
            last_time = response[0][0] # زمان اولین کندل در این دسته
            
        df = pd.DataFrame(all_candles, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ig"
        ])
        
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df[["open","high","low","close", "volume"]] = df[["open","high","low","close", "volume"]].astype(float)
        
        # حذف داده‌های تکراری احتمالی و مرتب‌سازی
        df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
        return df.tail(total_candles) # اطمینان از خروجی دقیقاً 2000 تا
    except Exception as e:
        st.error(f"خطا در دریافت داده: {e}")
        return pd.DataFrame()

# ======================
# 2. RL ENVIRONMENT
# ======================
class TradingEnv(gym.Env):
    def __init__(self, df):
        super(TradingEnv, self).__init__()
        self.df = df
        self.action_space = spaces.Discrete(3) # 0=Hold, 1=Buy, 2=Sell
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.current_step = 10
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.current_step]
        # ویژگی‌ها: قیمت‌ها + حجم (نرمال‌سازی ساده با لگاریتم یا تقسیم بر قیمت قبلی)
        obs = np.array([
            row['open'] / row['close'],
            row['high'] / row['close'],
            row['low'] / row['close'],
            row['close'] / self.df.iloc[self.current_step-1]['close'],
            row['volume'] / self.df['volume'].mean(),
            1.0 # Bias
        ], dtype=np.float32)
        return obs

    def step(self, action):
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        
        current_price = self.df.iloc[self.current_step]['close']
        prev_price = self.df.iloc[self.current_step-1]['close']
        
        # محاسبه پاداش (Reward)
        change = (current_price - prev_price) / prev_price
        if action == 1: # Buy
            reward = change
        elif action == 2: # Sell
            reward = -change
        else: # Hold
            reward = -0.0001 # جریمه خیلی کم برای جلوگیری از تنبلی مدل
            
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. RUNNING THE SYSTEM
# ======================
df = get_historical_data(total_candles=2000)

if not df.empty:
    st.write(f"✅ تعداد **{len(df)}** کندل با موفقیت بارگذاری شد.")
    
    # سایدبار تنظیمات آموزش
    st.sidebar.header("RL Training Settings")
    train_steps = st.sidebar.slider("Training Steps", 1000, 10000, 5000)
    
    if st.sidebar.button("🚀 شروع آموزش مدل"):
        env = TradingEnv(df)
        model = PPO("MlpPolicy", env, verbose=0, learning_rate=0.0003)
        
        with st.spinner(f'در حال پردازش {len(df)} کندل و یادگیری...'):
            model.learn(total_timesteps=train_steps)
            st.success("مدل با ۲۰۰۰ کندل آموزش دید!")

        # تست مدل روی داده‌ها
        obs, _ = env.reset()
        actions = []
        for i in range(len(df) - 11):
            action, _ = model.predict(obs)
            actions.append(["HOLD", "BUY", "SELL"][action])
            obs, _, _, _, _ = env.step(action)

        # نمایش نتایج نهایی
        res_df = df.iloc[10:10+len(actions)].copy()
        res_df['AI_Decision'] = actions
        
        st.subheader("📈 نتایج تحلیل ۲۰۰۰ کندل اخیر")
        st.dataframe(res_df[['time', 'close', 'AI_Decision']].sort_index(ascending=False), use_container_width=True)
else:
    st.warning("داده‌ای دریافت نشد. اتصال اینترنت یا فیلترشکن را چک کنید.")
