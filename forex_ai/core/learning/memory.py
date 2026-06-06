import numpy as np
from collections import deque
from datetime import datetime
import threading

class ExperienceBuffer:
    def __init__(self, max_size=10000):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.state_shape = None
        
    def add(self, state, action, reward, next_state, done, info=None):
        with self.lock:
            self.buffer.append({
                'state': state,
                'action': action,
                'reward': reward,
                'next_state': next_state,
                'done': done,
                'info': info or {},
                'timestamp': datetime.now()
            })
            
    def sample_batch(self, batch_size=32):
        with self.lock:
            if len(self.buffer) < batch_size:
                indices = np.arange(len(self.buffer))
            else:
                indices = np.random.choice(len(self.buffer), batch_size, replace=False)
            
            batch = [self.buffer[i] for i in indices]
            return batch
    
    def get_recent(self, n=100):
        with self.lock:
            return list(self.buffer)[-n:]
    
    def get_stats(self):
        with self.lock:
            if not self.buffer:
                return {'total': 0, 'avg_reward': 0, 'win_rate': 0}
            
            rewards = [e['reward'] for e in self.buffer]
            wins = sum(1 for r in rewards if r > 0)
            
            return {
                'total': len(self.buffer),
                'avg_reward': np.mean(rewards),
                'total_reward': np.sum(rewards),
                'win_rate': wins / len(self.buffer) if self.buffer else 0,
                'std_reward': np.std(rewards)
            }
    
    def clear(self):
        with self.lock:
            self.buffer.clear()


class PerformanceTracker:
    def __init__(self, window_size=50):
        self.window_size = window_size
        self.trades = deque(maxlen=window_size)
        self.lock = threading.Lock()
        self.peak_equity = 0
        self.starting_equity = 0
        
    def add_trade(self, entry_price, exit_price, size, direction, pair, timestamp=None):
        with self.lock:
            if direction == 'BUY':
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size
            
            self.trades.append({
                'entry': entry_price,
                'exit': exit_price,
                'size': size,
                'direction': direction,
                'pair': pair,
                'pnl': pnl,
                'timestamp': timestamp or datetime.now(),
                'pnl_pct': (pnl / (entry_price * size)) * 100
            })
    
    def get_metrics(self):
        with self.lock:
            if not self.trades:
                return {
                    'win_rate': 0,
                    'profit_factor': 0,
                    'avg_win': 0,
                    'avg_loss': 0,
                    'total_pnl': 0,
                    'trades_count': 0,
                    'consecutive_wins': 0,
                    'consecutive_losses': 0
                }
            
            pnls = [t['pnl'] for t in self.trades]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]
            
            win_rate = len(wins) / len(self.trades) if self.trades else 0
            total_wins = sum(wins) if wins else 0
            total_losses = abs(sum(losses)) if losses else 1
            profit_factor = total_wins / total_losses if total_losses > 0 else 0
            
            consecutive_wins = 0
            consecutive_losses = 0
            for trade in reversed(self.trades):
                if trade['pnl'] > 0:
                    consecutive_wins += 1
                    consecutive_losses = 0
                else:
                    consecutive_losses += 1
                    consecutive_wins = 0
            
            return {
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'avg_win': np.mean(wins) if wins else 0,
                'avg_loss': np.mean(losses) if losses else 0,
                'total_pnl': sum(pnls),
                'trades_count': len(self.trades),
                'consecutive_wins': consecutive_wins,
                'consecutive_losses': consecutive_losses,
                'largest_win': max(wins) if wins else 0,
                'largest_loss': min(losses) if losses else 0
            }
    
    def get_drawdown(self, equity_curve):
        if len(equity_curve) == 0:
            return 0
        
        peak = equity_curve[0]
        max_dd = 0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd


class MarketMemory:
    def __init__(self, lookback=500):
        self.lookback = lookback
        self.cache = {}
        self.lock = threading.Lock()
        
    def store_correlation(self, pair1, pair2, correlation, timestamp):
        with self.lock:
            key = f"{pair1}_{pair2}"
            if key not in self.cache:
                self.cache[key] = deque(maxlen=self.lookback)
            self.cache[key].append({'corr': correlation, 'ts': timestamp})
    
    def get_avg_correlation(self, pair1, pair2, periods=20):
        with self.lock:
            key = f"{pair1}_{pair2}"
            if key not in self.cache or len(self.cache[key]) == 0:
                return 0
            
            recent = list(self.cache[key])[-periods:]
            return np.mean([c['corr'] for c in recent])
    
    def get_volatility_regime(self, pair, periods=20):
        with self.lock:
            key = f"{pair}_volatility"
            if key not in self.cache or len(self.cache[key]) < periods:
                return 'normal'
            
            recent_vol = list(self.cache[key])[-periods:]
            vols = [v['vol'] for v in recent_vol]
            avg_vol = np.mean(vols)
            current_vol = vols[-1]
            
            if current_vol > avg_vol * 1.5:
                return 'high'
            elif current_vol < avg_vol * 0.7:
                return 'low'
            return 'normal'
