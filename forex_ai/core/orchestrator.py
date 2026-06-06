import json
import numpy as np
import threading
import time
from pathlib import Path
from core.data.bridge import DataBridge
from core.data.brokers import create_broker_from_config
from core.data.features import FeatureExtractor
from core.brain.experts import ExpertEnsemble
from core.brain.esn import TemporalDifferenceMemory
from core.brain.bayesian import ReasoningEngine
from core.brain.predictive import PredictiveCodingLoop
from core.brain.meta_learner import AdaptiveWeighting
from core.risk.engine import RiskManager
from core.learning.online_learner import OnlineLearner, SelfImprovementEngine
from db.database import Database

class TradingOrchestrator:
    def __init__(self, config_path='config/settings.json'):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.lock = threading.Lock()
        self.is_running = False
        self.thread = None
        self.state = {}

        self.database = Database(path=self.config.get('database_path', 'db/forex_ai.db'))
        self.broker = create_broker_from_config(self.config)
        self.bridge = DataBridge(self.broker)
        self.feature_extractor = FeatureExtractor(lookback_window=500)
        self.experts = ExpertEnsemble(n_experts=self.config.get('num_experts', 20))
        self.esn = TemporalDifferenceMemory(state_size=11, esn_hidden=self.config.get('esn_hidden', 120))
        self.reasoning = ReasoningEngine()
        self.predictive = PredictiveCodingLoop(state_size=11)
        self.meta_learner = AdaptiveWeighting(num_components=4)
        self.risk_manager = RiskManager(
            account_balance=self.config.get('account_balance', 10000),
            risk_per_trade=self.config.get('risk_per_trade', 0.02),
            max_daily_loss=self.config.get('max_daily_loss', 0.05)
        )
        self.online_learner = OnlineLearner(
            self.experts,
            self.esn,
            self.reasoning,
            self.predictive
        )
        self.self_improvement = SelfImprovementEngine(self.risk_manager, self.online_learner)
        self.symbols = self.config.get('trade_symbols', ['EURUSD', 'GBPUSD'])
        self.timeframe = self.config.get('timeframe', 5)
        self.update_interval = self.config.get('poll_interval_seconds', 2)
        self.last_tick = None
        self.open_orders = {}
        self.status = 'stopped'
        self.history = []
        self.is_connected = False

    def _load_config(self):
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def connect(self):
        if self.broker is None:
            return False
        if self.is_connected and hasattr(self.broker, 'check_connection') and self.broker.check_connection():
            return True

        connected = self.broker.connect()
        self.is_connected = connected
        if connected:
            account_info = self.broker.get_account_info()
            if account_info:
                self.risk_manager.current_balance = account_info['balance']
        else:
            # expose broker last_error to UI
            try:
                self.last_error = getattr(self.broker, 'last_error', None)
            except Exception:
                self.last_error = None
        return connected

    def disconnect(self):
        if self.broker is not None:
            self.broker.disconnect()
        self.is_connected = False

    def ensure_connection(self):
        if self.broker is None:
            self.is_connected = False
            return False

        if self.is_connected and hasattr(self.broker, 'check_connection'):
            if self.broker.check_connection():
                return True
            self.is_connected = False

        if self.broker is not None and hasattr(self.broker, 'reconnect'):
            connected = self.broker.reconnect()
        else:
            connected = self.connect()

        self.is_connected = connected
        if connected:
            account_info = self.broker.get_account_info()
            if account_info:
                self.risk_manager.current_balance = account_info['balance']
        return connected

    def start(self):
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            self.status = 'running'
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()

    def stop(self):
        with self.lock:
            self.is_running = False
            self.status = 'stopped'
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _run_loop(self):
        while True:
            with self.lock:
                if not self.is_running:
                    break
            if not self.ensure_connection():
                with self.lock:
                    self.status = 'reconnecting'
                time.sleep(5)
                continue
            self._process_symbols()
            time.sleep(self.update_interval)

    def _process_symbols(self):
        batch = self.bridge.get_batch_candles(self.symbols, timeframe=self._map_timeframe(self.timeframe), count=500)
        current_ticks = self.bridge.get_batch_ticks(self.symbols)
        
        for symbol, candles in batch.items():
            if not candles:
                continue
            features = self.feature_extractor.extract_features(candles)
            if not features:
                continue
            state = self.feature_extractor.get_state_vector(features)
            expert_pred, expert_preds, expert_confidence, expert_agreement = self.experts.predict(state)
            esn_pred = self.esn.predict_next_state(state)
            reasoning_output = self.reasoning.reason(features)
            predictive_output = self.predictive.process_tick(state)
            
            combined_signal = self._combine_signals(
                expert_pred,
                np.mean(esn_pred) if hasattr(esn_pred, '__len__') else float(esn_pred),
                reasoning_output['confidence'] * (1 if reasoning_output['regime'] != 'high_volatility' else 0.5),
                predictive_output['confidence']
            )
            
            self.meta_learner.update_weights(
                expert_scores=expert_confidence,
                esn_score=np.clip(np.tanh(np.mean(esn_pred)), 0, 1),
                bayesian_score=reasoning_output['confidence'],
                predictive_score=predictive_output['confidence']
            )
            
            self.database.insert_market_event(
                pair=symbol,
                feature_snapshot=features,
                prediction=combined_signal,
                error=predictive_output['error'],
                confidence=reasoning_output['confidence']
            )
            
            if symbol in current_ticks:
                tick = current_ticks[symbol]
                self._evaluate_positions(symbol, tick)
                self._attempt_open_position(symbol, features, state, combined_signal, reasoning_output, tick)
        
        self._update_status()

    def _map_timeframe(self, timeframe):
        try:
            if self.broker.__class__.__name__ == 'MT5Bridge':
                from MetaTrader5 import TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15, TIMEFRAME_H1, TIMEFRAME_H4
                if timeframe == 1:
                    return TIMEFRAME_M1
                if timeframe == 5:
                    return TIMEFRAME_M5
                if timeframe == 15:
                    return TIMEFRAME_M15
                if timeframe == 60:
                    return TIMEFRAME_H1
                if timeframe == 240:
                    return TIMEFRAME_H4
                return TIMEFRAME_M5
        except Exception:
            return timeframe

    def _combine_signals(self, expert_signal, esn_signal, bayesian_confidence, predictive_confidence):
        weights = self.meta_learner.get_weights()
        combined = (
            expert_signal * weights[0] +
            esn_signal * weights[1] +
            bayesian_confidence * weights[2] +
            predictive_confidence * weights[3]
        )
        return float(np.tanh(combined))

    def _attempt_open_position(self, symbol, features, state, signal, reasoning_output, tick):
        if not self.risk_manager.can_open_position():
            return
        
        should_trade, confidence = self.reasoning.should_trade(reasoning_output)
        if not should_trade:
            return
        
        if abs(signal) < 0.2:
            return
        
        price = tick['ask'] if signal > 0 else tick['bid']
        direction = 'BUY' if signal > 0 else 'SELL'
        atr = max(features.get('atr_14', 0.0001), 0.0001)
        stop_loss = price - atr * 1.5 if direction == 'BUY' else price + atr * 1.5
        take_profit = price + atr * 3 if direction == 'BUY' else price - atr * 3
        position_size = self.risk_manager.calculate_position_size(price, stop_loss, symbol, confidence)
        if position_size <= 0 or not self.is_connected:
            return
        
        order = self.broker.send_order(
            symbol=symbol,
            action='BUY' if direction == 'BUY' else 'SELL',
            volume=position_size,
            price=price,
            sl=stop_loss,
            tp=take_profit,
            comment='forex_ai'
        )
        
        if order:
            self.risk_manager.open_position(symbol, direction, price, stop_loss, take_profit, position_size, confidence)
            self.database.insert_log('trade', f'opened {direction} {symbol} size={position_size:.2f} price={price:.5f}')

    def _evaluate_positions(self, symbol, tick):
        position = self.risk_manager.open_positions.get(symbol)
        if not position:
            return
        current_price = tick['bid'] if position['direction'] == 'BUY' else tick['ask']
        closed = self.risk_manager.check_stop_loss(symbol, current_price)
        if not closed:
            closed = self.risk_manager.check_take_profit(symbol, current_price)
        
        if closed:
            self.database.insert_trade(
                pair=symbol,
                direction=closed['direction'],
                entry_price=closed['entry_price'],
                exit_price=closed['exit_price'],
                size=closed['position_size'],
                pnl=closed['pnl'],
                confidence=closed.get('confidence', 0.0),
                reason=closed.get('close_reason', 'closed')
            )
            self.database.insert_log('trade', f'closed {symbol} pnl={closed["pnl"]:.2f}')

    def _update_status(self):
        import sys
        with self.lock:
            self.status = 'running' if self.is_running else 'stopped'
            try:
                account_status = self.risk_manager.get_account_status()
                print(f'[orch] account_status: {account_status}', flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f'[orch] get_account_status failed: {e}', flush=True)
                account_status = {}
                sys.stdout.flush()
            
            try:
                open_pos = self.risk_manager.get_open_positions()
                print(f'[orch] open_pos: {open_pos}', flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f'[orch] get_open_positions failed: {e}', flush=True)
                open_pos = {}
                sys.stdout.flush()
            
            try:
                trade_stats = self.risk_manager.get_trade_stats()
                print(f'[orch] trade_stats: {trade_stats}', flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f'[orch] get_trade_stats failed: {e}', flush=True)
                trade_stats = {}
                sys.stdout.flush()
            
            try:
                meta_weights = self.meta_learner.get_weights().tolist()
                print(f'[orch] meta_weights: {meta_weights}', flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f'[orch] get_weights failed: {e}', flush=True)
                meta_weights = []
                sys.stdout.flush()
            
            try:
                reasoning_trace = self.reasoning.get_reasoning_trace(depth=5)
                print(f'[orch] reasoning_trace obtained', flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f'[orch] get_reasoning_trace failed: {e}', flush=True)
                reasoning_trace = {}
                sys.stdout.flush()
            
            try:
                top_experts = self.experts.get_top_experts(k=3)
                expert_confidence = np.mean([e['performance_score'] for e in top_experts]) if top_experts else 0
                print(f'[orch] expert_confidence: {expert_confidence}', flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f'[orch] get_top_experts failed: {e}', flush=True)
                expert_confidence = 0
                sys.stdout.flush()
            
            self.state = {
                'status': self.status,
                'symbols': self.symbols,
                'account': account_status,
                'open_positions': open_pos,
                'trade_stats': trade_stats,
                'meta_weights': meta_weights,
                'reasoning': reasoning_trace,
                'prediction': {
                    'expert': expert_confidence,
                    'esn_confidence': getattr(self.predictive, 'confidence_level', 0),
                    'bayesian_confidence': self.reasoning.belief_net.get_confidence() if hasattr(self.reasoning, 'belief_net') else 0,
                    'predictive_confidence': getattr(self.predictive, 'confidence_level', 0)
                }
            }
            print(f'[orch] _update_status complete, state keys: {list(self.state.keys())}', flush=True)
            sys.stdout.flush()

    def get_state(self):
        with self.lock:
            return self.state.copy()

    def get_diagnostics(self):
        with self.lock:
            return {
                'ensemble': self.experts.get_ensemble_metrics(),
                'esn': {
                    'avg_td_error': self.esn.get_average_td_error(),
                    'state_size': self.esn.state_size
                },
                'reasoning': {
                    'confidence': self.reasoning.belief_net.get_confidence(),
                    'uncertainty': self.reasoning.belief_net.get_uncertainty()
                },
                'predictive': self.predictive.get_diagnostics(),
                'meta': self.meta_learner.get_component_contribution(),
                'trade_stats': self.risk_manager.get_trade_stats()
            }

    def get_light_diagnostics(self):
        """Return a small, fast diagnostics snapshot for UI use to avoid heavy computation on the main thread."""
        with self.lock:
            s = self.state if hasattr(self, 'state') else {}
            prediction = s.get('prediction', {})
            return {
                'ensemble_confidence': float(prediction.get('expert', 0.0)),
                'esn_confidence': float(prediction.get('esn_confidence', 0.0)),
                'bayesian_confidence': float(prediction.get('bayesian_confidence', 0.0)),
                'predictive_confidence': float(prediction.get('predictive_confidence', 0.0)),
                'meta_weights': s.get('meta_weights', [])
            }
