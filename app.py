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

    # indicators
    df['EMA'] = df['close'].ewm(span=20).mean()

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df = df.dropna().reset_index(drop=True)
    return df
