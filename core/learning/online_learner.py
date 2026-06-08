import numpy as np
import threading
from datetime import datetime

class OnlineLearner:
    def __init__(self, expert_ensemble, esn, bayesian, predictive):
        self.experts = expert_ensemble
        self.esn = esn
        self.bayesian = bayesian
        self.predictive = predictive
        self.lock = threading.Lock()
        
        self.learning_buffer = []
        self.max_buffer_size = 100
        self.learning_rate = 0.01
        self.update_interval = 20
        self.update_counter = 0
        
        self.learning_stats = {
            'updates_performed': 0,
            'avg_expert_update_loss': 0,
            'avg_esn_td_error': 0,
            'learning_efficiency': 0.5
        }
        
    def add_experience(self, state, action, reward, next_state, done, info=None):
        with self.lock:
            self.learning_buffer.append({
                'state': state,
                'action': action,
                'reward': reward,
                'next_state': next_state,
                'done': done,
                'info': info or {},
                'timestamp': datetime.now()
            })
            
            if len(self.learning_buffer) > self.max_buffer_size:
                self.learning_buffer.pop(0)
            
            self.update_counter += 1
            
            if self.update_counter % self.update_interval == 0:
                self._perform_learning_update()
    
    def _perform_learning_update(self):
        if len(self.learning_buffer) < 5:
            return
        
        batch = self.learning_buffer[-min(20, len(self.learning_buffer)):]
        
        states = np.array([e['state'] for e in batch], dtype=np.float32)
        actions = np.array([e['action'] for e in batch], dtype=np.float32)
        rewards = np.array([e['reward'] for e in batch], dtype=np.float32)
        next_states = np.array([e['next_state'] for e in batch], dtype=np.float32)
        
        if len(states) > 0:
            self.experts.update_all(states, actions)
            
            for state, reward, next_state in zip(states, rewards, next_states):
                td_error = self.esn.update_value_network(state, reward, next_state)
                self.learning_stats['avg_esn_td_error'] = 0.9 * self.learning_stats['avg_esn_td_error'] + 0.1 * abs(td_error)
        
        self.learning_stats['updates_performed'] += 1
        
        if self.learning_stats['avg_esn_td_error'] < 0.1:
            self.learning_stats['learning_efficiency'] = min(1.0, self.learning_stats['learning_efficiency'] + 0.01)
        else:
            self.learning_stats['learning_efficiency'] = max(0.1, self.learning_stats['learning_efficiency'] - 0.01)
    
    def get_learning_stats(self):
        with self.lock:
            return self.learning_stats.copy()
    
    def adapt_learning_rate(self, market_volatility):
        with self.lock:
            if market_volatility > 0.02:
                self.learning_rate = 0.001
            elif market_volatility > 0.01:
                self.learning_rate = 0.005
            else:
                self.learning_rate = 0.01
    
    def reset(self):
        with self.lock:
            self.learning_buffer.clear()
            self.update_counter = 0
            self.learning_stats = {
                'updates_performed': 0,
                'avg_expert_update_loss': 0,
                'avg_esn_td_error': 0,
                'learning_efficiency': 0.5
            }


class SelfImprovementEngine:
    def __init__(self, risk_manager, memory_tracker):
        self.risk_manager = risk_manager
        self.memory_tracker = memory_tracker
        self.lock = threading.Lock()
        
        self.improvement_log = []
        self.max_log_size = 100
        
        self.adjustment_threshold = 0.55
        self.win_rate_target = 0.55
        self.profit_factor_target = 1.5
        
    def analyze_performance(self):
        with self.lock:
            metrics = self.risk_manager.get_trade_stats()
            
            if metrics['total_trades'] < 10:
                return None
            
            analysis = {
                'timestamp': datetime.now(),
                'metrics': metrics,
                'adjustments': []
            }
            
            if metrics['win_rate'] < self.adjustment_threshold:
                analysis['adjustments'].append({
                    'type': 'reduce_trade_frequency',
                    'reason': f'win_rate={metrics["win_rate"]:.2%}',
                    'severity': 'medium'
                })
            
            if metrics['profit_factor'] < 1.2 and metrics['profit_factor'] > 0:
                analysis['adjustments'].append({
                    'type': 'increase_risk_management',
                    'reason': f'profit_factor={metrics["profit_factor"]:.2f}',
                    'severity': 'high'
                })
            
            if metrics['max_drawdown'] > 0.1:
                analysis['adjustments'].append({
                    'type': 'reduce_position_size',
                    'reason': f'drawdown={metrics["max_drawdown"]:.2%}',
                    'severity': 'high'
                })
            
            self.improvement_log.append(analysis)
            if len(self.improvement_log) > self.max_log_size:
                self.improvement_log.pop(0)
            
            return analysis
    
    def apply_adjustments(self, analysis, meta_learner):
        with self.lock:
            if not analysis or not analysis['adjustments']:
                return
            
            for adjustment in analysis['adjustments']:
                if adjustment['type'] == 'reduce_trade_frequency':
                    pass
                
                elif adjustment['type'] == 'increase_risk_management':
                    current_risk = self.risk_manager.risk_per_trade
                    new_risk = max(0.005, current_risk * 0.8)
                    self.risk_manager.risk_per_trade = new_risk
                
                elif adjustment['type'] == 'reduce_position_size':
                    current_risk = self.risk_manager.risk_per_trade
                    new_risk = max(0.005, current_risk * 0.7)
                    self.risk_manager.risk_per_trade = new_risk
    
    def get_improvement_log(self, depth=20):
        with self.lock:
            return self.improvement_log[-depth:]
    
    def get_next_adjustment_suggestion(self):
        with self.lock:
            analysis = self.analyze_performance()
            
            if analysis and analysis['adjustments']:
                return analysis['adjustments'][0]
            
            return None
