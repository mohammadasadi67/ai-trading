import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
import streamlit as st
import requests
from datetime import datetime

st.set_page_config(page_title="AI Pro Strategy Lab v2.1", layout="wide")

# ======================
# 1. Sidebar & Settings
# ======================
st.sidebar.header("⚙️ تنظیمات پیشرفته استراتژی")
selected_ticker = st.sidebar.selectbox("نماد معاملاتی:", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
interval = st.sidebar.selectbox("تایم‌فریم:", ["15m", "1h", "4h"], index=0)  # پیش‌فرض روی 15 دقیقه برای دیتای بیشتر
init_balance = st.sidebar.number_input("سرمایه اولیه ($):", value=10000)
commission_rate = st.sidebar.slider("کارمزد صرافی (%):", 0.0, 0.5, 0.07, step=0.01) / 100

st.sidebar.divider()
st.sidebar.subheader("🧠 تنظیمات پاداش هوش مصنوعی")
learning_steps = st.sidebar.select_slider("شدت آموزش:", options=[100000, 200000, 500000, 1000000], value=200000)
risk_tolerance = st.sidebar.slider("حد ضرر (Stop Loss %):", 0.5, 5.0, 1.5) / 100


# ======================
# 2. Advanced Technical Analysis
# ======================
@st.cache_data(ttl=3600)
def get_pro_data(symbol, interval):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": 1000}
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        df = pd.DataFrame(data, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
        df['close'] = df['c'].astype(np.float32)
        df['high'] = df['h'].astype(np.float32)
        df['low'] = df['l'].astype(np.float32)

        # 1. RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-8))))

        # 2. MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # 3. ATR برای تشخیص نوسان
        df['tr'] = np.maximum(df['high'] - df['low'],
                              np.maximum(abs(df['high'] - df['close'].shift()),
                                         abs(df['low'] - df['close'].shift())))
        df['atr'] = df['tr'].rolling(window=14).mean()

        df.fillna(0, inplace=True)
        return df
    except Exception as e:
        st.error(f"خطا در دریافت دیتای بایننس: {e}")
        return pd.DataFrame()


# ======================
# 3. Advanced Trading Environment
# ======================
class ProEnv(gym.Env):
    def __init__(self, df, balance, commission, stop_loss):
        super().__init__()
        self.df = df
        self.initial_balance = float(balance)
        self.commission = float(commission)
        self.stop_loss_pct = stop_loss

        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(low=-1e2, high=1e2, shape=(5,), dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.balance = self.initial_balance
        self.current_step = 30
        self.position = 0.0
        self.entry_price = 0.0
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.current_step]
        unrealized_pnl = 0.0
        if self.position > 0:
            unrealized_pnl = (row['close'] - self.entry_price) / self.entry_price

        obs = np.array([
            (row['rsi'] - 50) / 25,
            (row['macd'] - row['signal']) / (row['close'] * 0.01 + 1e-8),
            row['atr'] / (row['close'] + 1e-8) * 100,
            self.position,
            unrealized_pnl * 20  # بزرگنمایی سود برای درک بهتر هوش مصنوعی
        ], dtype=np.float32)
        return obs

    def step(self, action):
        row = self.df.iloc[self.current_step]
        price = float(row['close'])
        reward = 0.0

        # مدیریت حد ضرر سخت‌گیرانه
        if self.position == 1.0:
            current_pnl = (price - self.entry_price) / self.entry_price
            if current_pnl < -self.stop_loss_pct:
                action = 2  # اجبار به فروش در صورت برخورد به حد ضرر

        # منطق اکشن‌ها
        if action == 1 and self.position == 0:  # ورود به معامله
            self.position = 1.0
            self.entry_price = price
            self.balance -= self.balance * self.commission
            # جریمه سنگین‌تر برای جلوگیری از تریدهای بیهوده (باید سود احتمالی از این جریمه بیشتر باشد)
            reward = -0.25

        elif action == 2 and self.position == 1:  # خروج از معامله
            pnl = (price - self.entry_price) / self.entry_price
            # پاداش تصاعدی: سودهای کوچک پاداش کمی دارند، سودهای بزرگ پاداش عالی
            if pnl > 0:
                reward = (pnl * 150) ** 1.2
            else:
                reward = pnl * 200  # تنبیه شدید برای ضرر

            self.balance *= (1 + pnl - self.commission)
            self.position = 0.0
            self.entry_price = 0.0

        elif action == 0 and self.position == 1:  # نگهداری پوزیشن
            pnl = (price - self.entry_price) / self.entry_price
            if pnl > self.commission * 2:  # فقط اگر در سود قابل توجه است پاداش بگیرد
                reward = 0.01
            else:
                reward = -0.01  # جریمه برای باز نگه داشتن پوزیشن درجا زن

        elif action == 0 and self.position == 0:  # صبر کردن
            reward = 0.005  # پاداش کوچک برای صبر و معامله نکردن در بازار بد

        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        return self._get_obs(), float(reward), done, False, {}


# ======================
# 4. Interface & Execution
# ======================
df = get_pro_data(selected_ticker, interval)

if not df.empty:
    st.title(f"🚀 پلتفرم هوش مصنوعی بایننس: {selected_ticker}")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.line_chart(df.set_index('ts')['close'], height=400)

    with col2:
        st.info("اطلاعات استراتژی:")
        st.write(f"تعداد داده‌ها: {len(df)}")
        st.write(f"اندیکاتورها: RSI, MACD, ATR")

    if st.button('🧠 شروع آموزش و بک‌تست نهایی'):
        with st.status("هوش مصنوعی در حال تحلیل الگوهای بازار...") as status:
            env = DummyVecEnv([lambda: ProEnv(df, init_balance, commission_rate, risk_tolerance)])

            # تنظیم پارامترهای PPO برای یادگیری عمیق‌تر
            model = PPO("MlpPolicy", env, verbose=0, learning_rate=5e-5, n_steps=2048, batch_size=128)
            model.learn(total_timesteps=learning_steps)

            # تست
            test_env = ProEnv(df, init_balance, commission_rate, risk_tolerance)
            obs, _ = test_env.reset()
            balances = [init_balance]
            done = False

            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, done, _, _ = test_env.step(action)
                balances.append(test_env.balance)

            status.update(label="بک‌تست کامل شد!", state="complete")

        # نمایش نتایج
        st.divider()
        res_col1, res_col2, res_col3 = st.columns(3)
        final_b = balances[-1]
        res_col1.metric("سرمایه نهایی", f"${final_b:,.2f}")
        res_col2.metric("بازدهی کل", f"{((final_b / init_balance) - 1) * 100:+.2f}%")
        res_col3.metric("وضعیت نهایی", "سودده ✅" if final_b > init_balance else "ضررده ❌")

        st.subheader("نمودار رشد سرمایه (Equity Curve)")
        st.line_chart(balances)
