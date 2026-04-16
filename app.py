import streamlit as st
import pandas as pd
import numpy as np
import requests

# RL
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

st.set_page_config(layout="wide")
st.title("🚀 AI TRADER (FAST VERSION)")

# ======================
# 1. DATA
# ======================
@st.cache_data(ttl=300)
def get_data():
    url = "https://data-api.binance.vision/api/v3/klines"
    res = requests.get(url, params={
        "symbol": "BTCUSDT",
        "interval": "4h",
        "limit": 500
    }).json()

    df = pd.DataFrame(res, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])

    df[["open","high","low","close","volume"]] = df[
        ["open","high","low","close","volume"]
    ].astype(float)

    # === indicators بدون pandas-ta ===
    df['EMA'] = df['close'].ewm(span=20).mean()

    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df = df.dropna().reset_index(drop=True)
    return df


# ======================
# 2. ENV
# ======================
class TradingEnv(gym.Env):
    def __init__(self, df):
        super().__init__()
        self.df = df
        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(3,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        self.step_i = 0
        return self._obs(), {}

    def _obs(self):
        row = self.df.iloc[self.step_i]
        return np.array([
            row['RSI']/100,
            row['close']/row['EMA'],
            1.0
        ], dtype=np.float32)

    def step(self, action):
        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]

        reward = 0
        if action == 1:
            reward = (next_row['close'] - row['close']) / row['close']

        self.step_i += 1
        done = self.step_i >= len(self.df) - 2
        return self._obs(), reward, done, False, {}


# ======================
# 3. MAIN
# ======================
df = get_data()

st.write("DATA READY ✅", df.tail())

env = TradingEnv(df)

# ======================
# 4. TRAIN BUTTON
# ======================
if st.button("🚀 Train AI (Light)"):
    with st.spinner("Training..."):
        model = PPO("MlpPolicy", env, verbose=0)
        model.learn(total_timesteps=500)  # سبک
        
        model.save("model.zip")

    st.success("Model Trained & Saved ✅")


# ======================
# 5. LOAD & RUN
# ======================
try:
    model = PPO.load("model.zip")

    obs, _ = env.reset()
    signals = []

    for i in range(len(df)-2):
        action, _ = model.predict(obs)

        signals.append({
            "time": df.iloc[i]['time'],
            "signal": "BUY" if action == 1 else "WAIT"
        })

        obs, _, _, _, _ = env.step(action)

    st.write("📊 SIGNALS", pd.DataFrame(signals).tail(20))

except:
    st.warning("⚠️ اول مدل رو train کن")

این کد چی میگه؟
