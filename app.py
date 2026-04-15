import streamlit as st
import pandas as pd
import numpy as np
import requests
import pandas_ta as ta # برای اندیکاتورهای فنی
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

# --- تنظیمات صفحه ---
st.set_page_config(layout="wide", page_title="AI Pro Trader")
st.title("🧠 MOHAMMAD PATTERN (Super AI Edition)")

# ======================
# 1. دریافت و غنی‌سازی داده‌ها (2000 کندل + اندیکاتور)
# ======================
@st.cache_data(ttl=300)
def get_pro_data():
    # دریافت داده‌ها (مشابه قبل)
    url = "https://data-api.binance.vision/api/v3/klines"
    all_candles = []
    last_time = None
    for _ in range(2):
        params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 1000}
        if last_time: params["endTime"] = last_time - 1
        res = requests.get(url, params=params).json()
        all_candles = res + all_candles
        last_time = res[0][0]
    
    df = pd.DataFrame(all_candles, columns=["time","open","high","low","close","volume","ct","qav","trades","tb","tq","ig"])
    df[["open","high","low","close", "volume"]] = df[["open","high","low","close", "volume"]].astype(float)
    
    # اضافه کردن اندیکاتورها برای هوشمندتر شدن مدل
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA_20'] = ta.ema(df['close'], length=20)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14) # برای تعیین حد ضرر
    
    return df.dropna().reset_index(drop=True)

# ======================
# 2. محیط هوشمند (با حد ضرر و حد سود)
# ======================
class SmartTradingEnv(gym.Env):
    def __init__(self, df):
        super().__init__()
        self.df = df
        # اکشن‌ها: 0=صبر، 1=خرید با مدیریت ریسک
        self.action_space = spaces.Discrete(2)
        # مشاهدات: قیمت، RSI، فاصله از EMA، و نوسان (ATR)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.current_step = 0
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.current_step]
        return np.array([
            row['RSI'] / 100, 
            row['close'] / row['EMA_20'], 
            row['ATR'] / row['close'],
            row['close'] / row['open'],
            1.0
        ], dtype=np.float32)

    def step(self, action):
        row = self.df.iloc[self.current_step]
        price_open = row['close'] # ورود در انتهای کندل فعلی
        
        reward = 0
        if action == 1:
            # پیشنهاد حد ضرر (1.5 برابر ATR) و حد سود (3 برابر ATR)
            sl_price = price_open - (row['ATR'] * 1.5)
            tp_price = price_open + (row['ATR'] * 3)
            
            # چک کردن کندل بعدی برای دیدن نتیجه
            next_row = self.df.iloc[self.current_step + 1]
            if next_row['low'] <= sl_price:
                reward = -0.02 # ضرر محدود به 2 درصد
            elif next_row['high'] >= tp_price:
                reward = 0.04 # سود 4 درصدی
            else:
                reward = (next_row['close'] - price_open) / price_open
        
        self.current_step += 1
        done = self.current_step >= len(self.df) - 2
        return self._get_obs(), reward, done, False, {}

# ======================
# 3. اجرا و گزارش‌گیری
# ======================
df = get_pro_data()

if not df.empty:
    st.sidebar.header("مدیریت سرمایه")
    capital = st.sidebar.number_input("سرمایه (دلار)", value=1000.0)
    risk_per_trade = st.sidebar.slider("ریسک در هر معامله (%)", 1, 5, 2)

    if st.button("🚀 آموزش استراتژی هوشمند"):
        env = SmartTradingEnv(df)
        model = PPO("MlpPolicy", env, verbose=0, learning_rate=0.0005).learn(total_timesteps=10000)
        
        st.success("هوش مصنوعی با رعایت حد ضرر آموزش دید!")

        # بک‌تست
        obs, _ = env.reset()
        history = []
        for i in range(len(df)-2):
            action, _ = model.predict(obs)
            row = df.iloc[i]
            
            signal = "WAIT"
            entry = sl = tp = 0
            
            if action == 1:
                signal = "🟢 BUY"
                entry = row['close']
                sl = entry - (row['ATR'] * 1.5) # پیشنهاد حد ضرر
                tp = entry + (row['ATR'] * 3)   # پیشنهاد حد سود
                
                # محاسبه تغییر موجودی (ساده شده)
                res_row = df.iloc[i+1]
                pnl = (res_row['close'] - entry) / entry
                capital *= (1 + pnl)

            history.append({
                "زمان": row['time'],
                "سیگنال": signal,
                "قیمت ورود": f"${entry:,.2f}" if entry > 0 else "-",
                "حد ضرر (SL)": f"${sl:,.2f}" if sl > 0 else "-",
                "حد سود (TP)": f"${tp:,.2f}" if tp > 0 else "-",
                "موجودی": capital
            })
            obs, _, _, _, _ = env.step(action)

        report_df = pd.DataFrame(history)
        
        # نمایش نتایج
        st.metric("موجودی نهایی با مدیریت ریسک", f"${capital:,.2f}", f"{((capital-1000)/10):.2f}%")
        st.dataframe(report_df.sort_values("زمان", ascending=False), use_container_width=True)
