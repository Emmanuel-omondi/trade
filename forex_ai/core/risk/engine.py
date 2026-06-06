import numpy as np
import threading
from datetime import datetime, timedelta

class RiskManager:
    def __init__(self, account_balance=10000, risk_per_trade=0.02, max_daily_loss=0.05):
        self.initial_balance = account_balance
        self.current_balance = account_balance
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.lock = threading.Lock()
        
        self.open_positions = {}
        self.daily_pnl = 0
        self.session_start = datetime.now()
        self.trade_history = []
        self.max_history = 500
        
    def calculate_position_size(self, entry_price, stop_loss, pair, confidence=1.0):
        with self.lock:
            if entry_price == 0 or stop_loss == 0:
                return 0
            
            daily_loss_limit = self.current_balance * self.max_daily_loss
            remaining_daily_loss = daily_loss_limit - max(0, self.daily_pnl)
            
            if remaining_daily_loss <= 0:
                return 0
            
            risk_amount = self.current_balance * self.risk_per_trade * confidence
            risk_amount = min(risk_amount, remaining_daily_loss)
            
            price_difference = abs(entry_price - stop_loss)
            if price_difference == 0:
                return 0
            
            position_size = risk_amount / price_difference
            
            max_position = self.current_balance * 0.1 / entry_price
            position_size = min(position_size, max_position)
            
            return max(0, position_size)
    
    def open_position(self, pair, direction, entry_price, stop_loss, take_profit, position_size, confidence=1.0):
        with self.lock:
            if pair in self.open_positions:
                return None
            
            self.open_positions[pair] = {
                'direction': direction,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'entry_time': datetime.now(),
                'confidence': confidence,
                'pnl': 0,
                'status': 'open'
            }
            
            return self.open_positions[pair]
    
    def close_position(self, pair, exit_price, reason='manual'):
        with self.lock:
            if pair not in self.open_positions:
                return None
            
            position = self.open_positions[pair]
            
            if position['direction'] == 'BUY':
                pnl = (exit_price - position['entry_price']) * position['position_size']
            else:
                pnl = (position['entry_price'] - exit_price) * position['position_size']
            
            position['exit_price'] = exit_price
            position['exit_time'] = datetime.now()
            position['pnl'] = pnl
            position['status'] = 'closed'
            position['close_reason'] = reason
            
            self.current_balance += pnl
            self.daily_pnl += pnl
            
            self.trade_history.append(position.copy())
            if len(self.trade_history) > self.max_history:
                self.trade_history.pop(0)
            
            del self.open_positions[pair]
            
            return position
    
    def check_stop_loss(self, pair, current_price):
        with self.lock:
            if pair not in self.open_positions:
                return None
            
            position = self.open_positions[pair]
            
            if position['direction'] == 'BUY':
                if current_price <= position['stop_loss']:
                    return self.close_position(pair, position['stop_loss'], 'stop_loss')
            else:
                if current_price >= position['stop_loss']:
                    return self.close_position(pair, position['stop_loss'], 'stop_loss')
            
            return None
    
    def check_take_profit(self, pair, current_price):
        with self.lock:
            if pair not in self.open_positions:
                return None
            
            position = self.open_positions[pair]
            
            if position['direction'] == 'BUY':
                if current_price >= position['take_profit']:
                    return self.close_position(pair, position['take_profit'], 'take_profit')
            else:
                if current_price <= position['take_profit']:
                    return self.close_position(pair, position['take_profit'], 'take_profit')
            
            return None
    
    def update_open_positions(self, current_prices):
        with self.lock:
            closed_positions = []
            
            for pair, position in list(self.open_positions.items()):
                if pair in current_prices:
                    current_price = current_prices[pair]
                    
                    if position['direction'] == 'BUY':
                        position['pnl'] = (current_price - position['entry_price']) * position['position_size']
                    else:
                        position['pnl'] = (position['entry_price'] - current_price) * position['position_size']
            
            return closed_positions
    
    def get_open_positions(self):
        with self.lock:
            return {pair: pos.copy() for pair, pos in self.open_positions.items()}
    
    def can_open_position(self):
        with self.lock:
            if self.daily_pnl < -self.current_balance * self.max_daily_loss:
                return False
            
            if self.current_balance <= 0:
                return False
            
            return True
    
    def get_account_status(self):
        with self.lock:
            open_pnl = sum(pos['pnl'] for pos in self.open_positions.values())
            total_balance = self.current_balance + open_pnl
            
            return {
                'account_balance': self.current_balance,
                'total_equity': total_balance,
                'open_pnl': open_pnl,
                'daily_pnl': self.daily_pnl,
                'open_positions_count': len(self.open_positions),
                'daily_loss_remaining': (self.current_balance * self.max_daily_loss) - max(0, -self.daily_pnl),
                'risk_per_trade': self.risk_per_trade,
                'can_trade': self.can_open_position()
            }
    
    def get_drawdown(self):
        with self.lock:
            if len(self.trade_history) == 0:
                return 0
            
            equity_curve = [self.initial_balance]
            current_equity = self.initial_balance
            
            for trade in self.trade_history:
                current_equity += trade['pnl']
                equity_curve.append(current_equity)
            
            peak = max(equity_curve)
            trough = min(equity_curve)
            
            if peak > 0:
                return (peak - trough) / peak
            
            return 0
    
    def reset_daily_stats(self):
        with self.lock:
            self.daily_pnl = 0
            self.session_start = datetime.now()
    
    def get_trade_stats(self):
        with self.lock:
            if len(self.trade_history) == 0:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'avg_win': 0,
                    'avg_loss': 0,
                    'profit_factor': 0
                }
            
            winning_trades = [t['pnl'] for t in self.trade_history if t['pnl'] > 0]
            losing_trades = [t['pnl'] for t in self.trade_history if t['pnl'] < 0]
            
            total_wins = sum(winning_trades)
            total_losses = sum(losing_trades)
            
            return {
                'total_trades': len(self.trade_history),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': len(winning_trades) / len(self.trade_history) if self.trade_history else 0,
                'total_pnl': sum([t['pnl'] for t in self.trade_history]),
                'avg_win': np.mean(winning_trades) if winning_trades else 0,
                'avg_loss': np.mean(losing_trades) if losing_trades else 0,
                'profit_factor': total_wins / abs(total_losses) if total_losses < 0 else 0,
                'max_drawdown': self.get_drawdown()
            }
