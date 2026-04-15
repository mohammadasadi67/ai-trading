import streamlit as st
import pandas as pd
import numpy as np
import requests
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

st.set_page_config(layout="wide", page_title="MOHAMMAD PATTERN RL")
st.title("🤖 MOHAMMAD PATTERN (Reinforcement Learning)")

# --- بخش اول: دریافت ۲۰۰۰ کندل ---
@st.cache_data(ttl=300)
def get_data_2000():
    url = "https://data-api.binance.vision/api/v3/klines"
    all_c = []
    last_t = None
    for _ in range(2):
        p = {"symbol": "BTCUSDT", "interval": "4h", "limit": 1000}
        if last_t: p["endTime"] = last_t - 1
        res = requests.get(url, params=p).json()
        all_c = res + all_c
        last_t = res[0][0]
    df = pd.DataFrame(all_c, columns=["time","open","high","low","close","vol","ct","qav","trd","tb","tq","ig"])
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    # اضافه کردن RSI و ATR بصورت دستی (برای حذف نیاز به pandas_ta)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    tr = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift()), abs(df['low']-df['close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    return df.dropna().reset_index(drop=True)

# --- بخش دوم: محیط یادگیری هوش مصنوعی ---
class CryptoEnv(gym.Env):
    def __init__(self, df):
        super().__init__()
        self.df = df
        self.action_space = spaces.Discrete(2) # 0=Wait, 1=Buy
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32)
        self.reset()
    def reset(self, seed=None, options=None):
        self.current_step = 0
        return self._get_obs(), {}
    def _get_obs(self):
        row = self.df.iloc[self.current_step]
        return np.array([row['RSI']/100, row['close']/row['open'], row['ATR']/row['close'], 1.0], dtype=np.float32)
    def step(self, action):
        p1 = self.df.iloc[self.current_step]['close']
        p2 = self.df.iloc[self.current_step + 1]['close']
        reward = (p2 - p1) / p1 if action == 1 else 0
        self.current_step += 1
        return self._get_obs(), reward, (self.current_step >= len(self.df)-2), False, {}

# --- بخش سوم: بک‌تست و اجرا ---
df = get_data_2000()
if not df.empty:
    init_cap = st.sidebar.number_input("سرمایه اولیه ($)", value=1000.0)
    if st.button("🚀 آموزش مغز RL و شروع ترید"):
        with st.spinner("هوش مصنوعی در حال مرور ۲۰۰۰ کندل برای یادگیری الگوهاست..."):
            env = CryptoEnv(df)
            model = PPO("MlpPolicy", env, verbose=0).learn(total_timesteps=5000)
        
        curr_cap = init_cap
        history = []
        for i in range(len(df)-2):
            row = df.iloc[i]
            obs = np.array([row['RSI']/100, row['close']/row['open'], row['ATR']/row['close'], 1.0], dtype=np.float32)
            action, _ = model.predict(obs)
            
            sig, entry, sl, tp, pnl = "WAIT", "-", "-", "-", 0
            if action == 1:
                sig, entry_p = "🟢 BUY", row['close']
                entry = f"${entry_p:,.0f}"
                sl_p, tp_p = entry_p - (row['ATR']*1.5), entry_p + (row['ATR']*3)
                sl, tp = f"${sl_p:,.0f}", f"${tp_p:,.0f}"
                
                nxt = df.iloc[i+1]
                pnl_raw = -0.02 if nxt['low'] <= sl_p else (0.05 if nxt['high'] >= tp_p else (nxt['close']-entry_p)/entry_p)
                curr_cap *= (1 + pnl_raw - 0.002) # کسر کارمزد
                pnl = pnl_raw * 100

            history.append({"زمان": row['time'], "سیگنال": sig, "ورود": entry, "SL": sl, "TP": tp, "PnL %": pnl, "موجودی": curr_cap})
        
        st.metric("موجودی نهایی هوش مصنوعی", f"${curr_cap:,.2f}", f"{((curr_cap-init_cap)/init_cap*100):.2f}%")
        st.dataframe(pd.DataFrame(history).sort_values("زمان", ascending=False), use_container_width=True)
