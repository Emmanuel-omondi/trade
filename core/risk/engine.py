import numpy as np
import threading
from datetime import datetime


class RiskManager:
    def __init__(self, account_balance=10000, risk_per_trade=0.02, max_daily_loss=0.05):
        self.initial_balance = account_balance
        self.current_balance = account_balance
        self.live_balance    = 0.0
        self.live_equity     = 0.0
        self.live_open_pnl   = 0.0
        self.risk_per_trade  = risk_per_trade
        self.max_daily_loss  = max_daily_loss
        self.lock            = threading.Lock()
        self.open_positions  = {}
        self.daily_pnl       = 0.0
        self.session_start   = datetime.now()
        self.trade_history   = []
        self.max_history     = 500

    def sync_live_account(self, balance, equity, open_pnl):
        with self.lock:
            self.live_balance  = float(balance)
            self.live_equity   = float(equity)
            self.live_open_pnl = float(open_pnl)
            self.current_balance = float(balance)
            if self.initial_balance == 10000 and balance > 0:
                self.initial_balance = float(balance)

    def calculate_position_size(self, entry_price, stop_loss, pair, confidence=1.0):
        with self.lock:
            balance = self.live_balance if self.live_balance > 0 else self.current_balance
            if balance <= 0 or entry_price == 0 or stop_loss == 0:
                return 0.0
            daily_loss_limit = balance * self.max_daily_loss
            remaining = daily_loss_limit - max(0, -self.daily_pnl)
            if remaining <= 0:
                return 0.0
            risk_amount = balance * self.risk_per_trade * min(max(confidence, 0.1), 1.0)
            risk_amount = min(risk_amount, remaining)
            price_diff = abs(entry_price - stop_loss)
            if price_diff == 0:
                return 0.0
            # convert risk amount to lots
            # For forex: 1 standard lot = 100,000 units
            # pip value ≈ price_diff in quote currency per lot
            raw_size = risk_amount / (price_diff * 100000.0)
            # clamp: min 0.01 lots, max 5% of balance in lots
            raw_size = max(0.01, min(raw_size, 10.0))
            return round(raw_size, 2)

    def open_position(self, pair, direction, entry_price, stop_loss, take_profit, position_size, confidence=1.0):
        with self.lock:
            if pair in self.open_positions:
                return None
            self.open_positions[pair] = {
                'direction':     direction,
                'entry_price':   entry_price,
                'current_price': entry_price,
                'stop_loss':     stop_loss,
                'take_profit':   take_profit,
                'position_size': position_size,
                'entry_time':    datetime.now(),
                'confidence':    confidence,
                'pnl':           0.0,
                'status':        'open'
            }
            return self.open_positions[pair]

    def _close_position_locked(self, pair, exit_price, reason='manual'):
        if pair not in self.open_positions:
            return None
        raw = self.open_positions[pair]
        entry  = float(raw.get('entry_price', exit_price))
        size   = float(raw.get('position_size', 0.0))
        direct = raw.get('direction', 'BUY')
        pnl    = (exit_price - entry) * size if direct == 'BUY' else (entry - exit_price) * size
        position = dict(raw)
        position['exit_price']   = float(exit_price)
        position['exit_time']    = datetime.now()
        position['pnl']          = float(pnl)
        position['status']       = 'closed'
        position['close_reason'] = reason
        position.setdefault('confidence', 0.0)
        position.setdefault('position_size', size)
        position.setdefault('entry_price', entry)
        position.setdefault('direction', direct)
        self.current_balance += pnl
        self.daily_pnl       += pnl
        self.trade_history.append(position)
        if len(self.trade_history) > self.max_history:
            self.trade_history.pop(0)
        del self.open_positions[pair]
        return position

    def close_position(self, pair, exit_price, reason='manual'):
        with self.lock:
            return self._close_position_locked(pair, exit_price, reason)

    def check_stop_loss(self, pair, current_price):
        with self.lock:
            pos = self.open_positions.get(pair)
            if not pos:
                return None
            hit = (pos['direction'] == 'BUY'  and current_price <= pos['stop_loss']) or \
                  (pos['direction'] == 'SELL' and current_price >= pos['stop_loss'])
            if hit:
                return self._close_position_locked(pair, pos['stop_loss'], 'stop_loss')
        return None

    def check_take_profit(self, pair, current_price):
        with self.lock:
            pos = self.open_positions.get(pair)
            if not pos:
                return None
            hit = (pos['direction'] == 'BUY'  and current_price >= pos['take_profit']) or \
                  (pos['direction'] == 'SELL' and current_price <= pos['take_profit'])
            if hit:
                return self._close_position_locked(pair, pos['take_profit'], 'take_profit')
        return None

    def update_open_pnl(self, pair, current_price):
        with self.lock:
            pos = self.open_positions.get(pair)
            if not pos:
                return
            pos['current_price'] = current_price
            if pos['direction'] == 'BUY':
                pos['pnl'] = (current_price - pos['entry_price']) * pos['position_size']
            else:
                pos['pnl'] = (pos['entry_price'] - current_price) * pos['position_size']

    def get_open_positions(self):
        with self.lock:
            return {p: dict(v) for p, v in self.open_positions.items()}

    def can_open_position(self):
        with self.lock:
            if self.current_balance <= 0:
                return False
            if self.daily_pnl < -(self.current_balance * self.max_daily_loss):
                return False
            return True

    def get_account_status(self):
        with self.lock:
            balance   = self.live_balance  if self.live_balance  > 0 else 0.0
            equity    = self.live_equity   if self.live_equity   > 0 else 0.0
            open_pnl  = self.live_open_pnl
            return {
                'account_balance':      balance,
                'total_equity':         equity,
                'open_pnl':             open_pnl,
                'daily_pnl':            self.daily_pnl,
                'open_positions_count': len(self.open_positions),
                'daily_loss_remaining': (self.current_balance * self.max_daily_loss) - max(0, -self.daily_pnl),
                'risk_per_trade':       self.risk_per_trade,
                'can_trade':            self.daily_pnl >= -(self.current_balance * self.max_daily_loss) and self.current_balance > 0
            }

    def get_drawdown(self):
        with self.lock:
            if not self.trade_history:
                return 0.0
            curve = [self.initial_balance]
            eq = self.initial_balance
            for t in self.trade_history:
                eq += t['pnl']
                curve.append(eq)
            peak = max(curve)
            if peak <= 0:
                return 0.0
            trough = min(curve)
            return (peak - trough) / peak

    def get_trade_stats(self):
        with self.lock:
            if not self.trade_history:
                return {'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                        'win_rate': 0.0, 'total_pnl': 0.0, 'avg_win': 0.0,
                        'avg_loss': 0.0, 'profit_factor': 0.0, 'max_drawdown': 0.0}
            wins   = [t['pnl'] for t in self.trade_history if t['pnl'] > 0]
            losses = [t['pnl'] for t in self.trade_history if t['pnl'] <= 0]
            gw = sum(wins)
            gl = abs(sum(losses))
            return {
                'total_trades':   len(self.trade_history),
                'winning_trades': len(wins),
                'losing_trades':  len(losses),
                'win_rate':       len(wins) / len(self.trade_history),
                'total_pnl':      sum(t['pnl'] for t in self.trade_history),
                'avg_win':        float(np.mean(wins))   if wins   else 0.0,
                'avg_loss':       float(np.mean(losses)) if losses else 0.0,
                'profit_factor':  gw / gl if gl > 0 else 0.0,
                'max_drawdown':   self.get_drawdown()
            }

    def reset_daily_stats(self):
        with self.lock:
            self.daily_pnl     = 0.0
            self.session_start = datetime.now()
