import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
from stable_baselines3.common.utils import get_linear_fn

# ===============================
# 🔥 ENV (FINAL VERSION)
# ===============================
class SovereignQuantEnv(gym.Env):
    def __init__(self, df, initial_balance=1000):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.observation_space = spaces.Box(low=-5, high=5, shape=(10,), dtype=np.float32)
        self.action_space = spaces.Discrete(4)
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.balance = self.initial_balance
        self.peak_equity = self.initial_balance
        self.position = 0
        self.entry_price = 0
        self.position_size = 0
        self.holding_steps = 0
        self.step_i = 50
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.step_i]
        equity = self.get_total_equity(row['close'])
        pnl = (row['close'] / self.entry_price - 1) * self.position if self.entry_price > 0 else 0

        obs = np.array([
            ((row['EMA_20'] - row['EMA_50']) / row['EMA_50']) * 20,
            (row['close'] / row['EMA_50'] - 1) * 10,
            row['volatility'] / 0.04,
            row['rel_vol'] - 1.0,
            (row['close'] / self.df.iloc[max(self.step_i-5, 0)]['close'] - 1) * 10,
            (row['RSI'] - 50) / 20,
            float(self.position),
            pnl * 5,
            min(float(self.holding_steps) / 100.0, 1.0),
            ((self.peak_equity - equity) / self.peak_equity) * 5
        ], dtype=np.float32)

        return np.clip(np.nan_to_num(obs), -5, 5)

    def step(self, action):
        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]

        fee = 0.001
        reward = 0

        if action in [1,2,3]:
            reward -= 0.0007

        if action == 1 and self.position == 0:
            self._open_pos(row, 1, fee)
        elif action == 2 and self.position == 0:
            self._open_pos(row, -1, fee)
        elif action == 3 and self.position != 0:
            if self.holding_steps < 3:
                reward -= 0.002
            self.exit_pos(row['close'], fee)

        price_return = (next_row['close'] / row['close'] - 1)
        vol = np.clip(row['volatility'], 0.01, 0.05)
        adj_return = np.clip(price_return / vol, -0.05, 0.05)

        if self.position == 1:
            reward += adj_return * 22
            reward -= 0.025 * abs(adj_return)
        elif self.position == -1:
            reward -= adj_return * 22
            reward -= 0.025 * abs(adj_return)
        elif self.position == 0 and abs(adj_return) < 0.003:
            reward += 0.0005

        equity = self.get_total_equity(next_row['close'])
        self.peak_equity = max(self.peak_equity, equity)
        dd = (self.peak_equity - equity) / self.peak_equity

        reward -= dd * 0.05
        if dd > 0.1:
            reward -= 0.01

        if self.position != 0:
            pnl = (row['close'] / self.entry_price - 1) * self.position
            reward -= 0.02 * abs(pnl)

            sl = max(0.02, row['volatility'] * 2)
            if pnl < -sl:
                self.exit_pos(row['close'], fee)

            if pnl > 0.04:
                reward += 0.003
            elif pnl > 0.02:
                reward += 0.002

            self.holding_steps += 1
            if self.holding_steps > 100:
                self.exit_pos(row['close'], fee)

        self.step_i += 1
        done = self.step_i >= len(self.df) - 1
        return self._get_obs(), reward, done, False, {}

    def _open_pos(self, row, side, fee):
        vol = max(row['volatility'], 0.01)
        risk = 0.015 * (0.02 / vol)
        self.position_size = min(self.balance * risk, self.balance * 0.95)

        self.balance -= self.position_size * (1 + fee)
        self.entry_price = row['close']
        self.position = side
        self.holding_steps = 0

    def exit_pos(self, price, fee):
        pnl = (price / self.entry_price - 1) * self.position
        val = self.position_size * (1 + pnl)
        self.balance += val * (1 - fee)

        self.position = 0
        self.entry_price = 0
        self.position_size = 0

    def get_total_equity(self, price):
        if self.position != 0:
            pnl = (price / self.entry_price - 1) * self.position
            return self.balance + self.position_size * (1 + pnl)
        return self.balance


# ===============================
# 🔥 TRAIN FUNCTION
# ===============================
def train(df):

    train_df = df[df.index < "2025-01-01"]
    val_df = df[df.index >= "2025-01-01"]

    def make_env(data):
        return lambda: Monitor(SovereignQuantEnv(data))

    env = SubprocVecEnv([make_env(train_df) for _ in range(8)])
    env = VecNormalize(env, norm_obs=True, norm_reward=True)

    eval_env = SubprocVecEnv([make_env(val_df)])
    eval_env = VecNormalize(eval_env, training=False)

    lr = get_linear_fn(3e-4, 1e-5, 1.0)

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=lr,
        batch_size=256,
        gamma=0.995,
        target_kl=0.02,
        verbose=1
    )

    model.learn(1_000_000)

    model.save("model.zip")
    env.save("norm.pkl")


# ===============================
# 🔥 BACKTEST
# ===============================
def backtest(df):

    env = SubprocVecEnv([lambda: SovereignQuantEnv(df)])
    env = VecNormalize.load("norm.pkl", env)

    env.training = False
    env.norm_reward = False

    model = PPO.load("model.zip")

    obs = env.reset()
    equity = []

    for _ in range(len(df)-1):
        action, _ = model.predict(obs)
        obs, _, done, _, _ = env.step(action)

        equity.append(env.get_attr("balance")[0])

        if done:
            break

    return equity


# ===============================
# 🔥 RUN
# ===============================
if __name__ == "__main__":

    df = pd.read_csv("data.csv", index_col=0, parse_dates=True)

    train(df)

    eq = backtest(df)

    print("Final Balance:", eq[-1])
