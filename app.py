import gymnasium as gym
from gymnasium import spaces
import numpy as np

class SovereignQuantEnv(gym.Env):
    def __init__(self, df, initial_balance=1000):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        self.observation_space = spaces.Box(low=-5, high=5, shape=(10,), dtype=np.float32)
        self.action_space = spaces.Discrete(4) # 0:Stay, 1:Long, 2:Short, 3:Close
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
        return np.nan_to_num(np.clip(obs, -5, 5))

    def step(self, action):
        row = self.df.iloc[self.step_i]
        next_row = self.df.iloc[self.step_i + 1]
        fee = 0.001
        reward = 0

        # ۱. مدیریت اکشن‌ها با جریمه دقیق 0.0007 (Perfect Balance)
        if action in [1, 2, 3]: reward -= 0.0007
        
        if action == 1 and self.position == 0:
            self._open_pos(row, 1, fee)
        elif action == 2 and self.position == 0:
            self._open_pos(row, -1, fee)
        elif action == 3 and self.position != 0:
            if self.holding_steps < 3: reward -= 0.002
            self.exit_pos(row['close'], fee)

        # ۲. پاداش Risk-Neutral (22 vs 0.025)
        price_return = (next_row['close'] / row['close'] - 1)
        vol_clip = np.clip(row['volatility'], 0.01, 0.05)
        adj_return = np.clip(price_return / vol_clip, -0.05, 0.05)
        
        if self.position == 1: 
            reward += adj_return * 22
            reward -= 0.025 * abs(adj_return)
        elif self.position == -1: 
            reward -= adj_return * 22
            reward -= 0.025 * abs(adj_return)
        
        # پاداش برای نقد ماندن (Flat is Good)
        elif self.position == 0 and abs(adj_return) < 0.003:
            reward += 0.0005

        # ۳. مدیریت دراوداون و خط قرمز ۱۰٪
        current_equity = self.get_total_equity(next_row['close'])
        self.peak_equity = max(self.peak_equity, current_equity)
        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        reward -= drawdown * 0.05
        if drawdown > 0.1: reward -= 0.01

        if self.position != 0:
            pnl = (row['close'] / self.entry_price - 1) * self.position
            reward -= 0.02 * abs(pnl)
            
            # جریمه Chop شرطی
            trend_strength = abs((row['EMA_20'] - row['EMA_50']) / row['EMA_50'])
            if trend_strength < 0.0005: reward -= 0.001
            
            # تشویق سود (Profit Encouragement)
            if pnl > 0.04: reward += 0.003
            elif pnl > 0.02: reward += 0.002
            
            # استاپ لاس داینامیک
            sl = max(0.02, row['volatility'] * 2)
            if pnl < -sl: self.exit_pos(row['close'], fee)

            self.holding_steps += 1
            if self.holding_steps > 100: self.exit_pos(row['close'], fee)

        self.step_i += 1
        done = self.step_i >= len(self.df) - 1
        return self._get_obs(), reward, done, False, {}

    def _open_pos(self, row, side, fee):
        vol = max(row['volatility'], 0.01)
        risk_adj = 0.015 * (0.02 / vol)
        self.position_size = min(self.balance * risk_adj, self.balance * 0.95)
        self.balance -= self.position_size * (1 + fee)
        self.entry_price = row['close']
        self.position = side
        self.holding_steps = 0

    def exit_pos(self, price, fee):
        pnl = (price / self.entry_price - 1) * self.position
        realized_val = self.position_size * (1 + pnl)
        self.balance += realized_val * (1 - fee)
        self.position = 0
        self.entry_price = 0
        self.position_size = 0

    def get_total_equity(self, price):
        if self.position != 0:
            pnl = (price / self.entry_price - 1) * self.position
            return self.balance + (self.position_size * (1 + pnl))
        return self.balance
