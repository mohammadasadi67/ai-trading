import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import time

# RL
from stable_baselines3 import PPO
import gymnasium as gym
from gymnasium import spaces

st.set_page_config(layout="wide")
st.title("🚀 AI TRADER (PRO VERSION)")

# ======================
# 1. داده‌های طولانی مدت (مثلاً ۳ سال)
# ======================
@st.cache_data(ttl=86400) # ذخیره داده‌ها برای یک روز
def get_historical_data(symbol="BTCUSDT", interval="4h", years=3):
    st.write(f"⏳ در حال دریافت داده‌های {years} سال اخیر...")
    url = "https://data-api.binance.vision/api/v3/klines"
    
    # محاسبه تعداد کندل‌های مورد نیاز (تقریبی)
    # هر سال حدود ۲۱۹۰ کندل ۴ ساعته دارد
    total_needed = years * 365 * 6 
    all_candles = []
    last_time = None

    while len(all_candles) < total_needed:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1000
        }
        if last_time:
            params["endTime"] = last_time - 1
        
        res = requests.get(url, params=params).json()
        if not res or len(res) == 0:
            break
            
        all_candles = res + all_candles
        last_time = res[0][0] # زمان اولین کندل در لیست فعلی
        
        # وقفه کوتاه برای رعایت محدودیت API
        time.sleep(0.1)
        if len(all_candles) >= total_needed:
            break

    df = pd.DataFrame(all_candles, columns=[
        "time","open","high","low","close","volume",
        "ct","qav","trades","tb","tq","ig"
    ])
    
    df[["open","high","low","close","volume"]] = df[
        ["open","high","low","close","volume"]
    ].astype(float)

    # شاخص‌ها
    df['EMA'] = df['close'].ewm(span=20).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    return df.dropna().reset_index(drop=True)

# ... (کلاس TradingEnv مشابه قبل باقی می‌ماند) ...

# ======================
# 3. اجرای برنامه
# ======================
df = get_historical_data(years=3) # تنظیم روی ۳ سال
st.write(f"✅ تعداد {len(df)} کندل بارگذاری شد.")

env = gym.make('os-v0') # یا استفاده مستقیم از کلاس محیط خودت
# برای سادگی فرض می‌کنیم کلاس TradingEnv بالا تعریف شده است
env = TradingEnv(df)

MODEL_NAME = "trading_model_3years"

# بررسی وجود مدل
if os.path.exists(f"{MODEL_NAME}.zip"):
    st.success("🤖 مدل هوشمند از قبل آموزش دیده و آماده است!")
    model = PPO.load(MODEL_NAME)
    
    if st.button("🔄 آموزش دوباره (Re-train)"):
        os.remove(f"{MODEL_NAME}.zip")
        st.rerun()
else:
    st.warning("⚠️ مدلی یافت نشد. باید آموزش را شروع کنید.")
    train_steps = st.slider("تعداد گام‌های آموزش:", 10000, 200000, 50000)
    
    if st.button("🚀 شروع آموزش سنگین"):
        with st.spinner("این فرآیند ممکن است چند دقیقه طول بکشد..."):
            model = PPO("MlpPolicy", env, verbose=0)
            model.learn(total_timesteps=train_steps)
            model.save(MODEL_NAME)
        st.success("آموزش تمام شد و مدل ذخیره شد! ✅")
        st.rerun()

# نمایش سیگنال‌ها (فقط اگر مدل وجود داشته باشد)
if os.path.exists(f"{MODEL_NAME}.zip"):
    # (کد پیش‌بینی سیگنال‌ها مشابه قبل)
    st.write("### 📊 آخرین سیگنال‌های صادر شده")
    # ...
