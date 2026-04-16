import streamlit as st
import pandas as pd
import numpy as np
import requests
import os

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
    try:
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

        # indicators
        df['EMA'] = df['close'].ewm(span=20).mean()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        df = df.dropna().reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

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
            row['close']/row['EMA'] if row['EMA'] != 0 else 1.0,
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
# 3. EXECUTION
# ======================
df = get_data()

if df is not None:
    st.write("### 📈 Recent Data", df.tail(3))
    
    env = TradingEnv(df)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 Train AI Model"):
            with st.spinner("Training..."):
                model = PPO("MlpPolicy", env, verbose=0)
                model.learn(total_timesteps=1000)
                model.save("trading_model")
            st.success("Model Trained Successfully! ✅")
            st.rerun()

    with col2:
        if st.button("🗑 Reset Model"):
            if os.path.exists("trading_model.zip"):
                os.remove("trading_model.zip")
                st.info("Model deleted.")
                st.rerun()

    st.divider()

    # LOAD & RUN
    if os.path.exists("trading_model.zip"):
        model = PPO.load("trading_model")
        obs, _ = env.reset()
        signals = []

        for i in range(len(df)-2):
            action, _ = model.predict(obs)
            signals.append({
                "Time": pd.to_datetime(df.iloc[i]['time'], unit='ms'),
                "Price": df.iloc[i]['close'],
                "Signal": "🟢 BUY" if action == 1 else "⚪ WAIT"
            })
            obs, _, _, _, _ = env.step(action)

        st.write("### 📊 AI Trading Signals")
        st.table(pd.DataFrame(signals).tail(10))
    else:
        st.warning("⚠️ No model found. Please click 'Train AI Model' first.")
else:
    st.error("Could not load data from Binance.")
