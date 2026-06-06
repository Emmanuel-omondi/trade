import json
import numpy as np
import threading
import time
from pathlib import Path
from datetime import datetime
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

try:
    import MetaTrader5 as mt5
    _TF_M1 = mt5.TIMEFRAME_M1
    _TF_M5 = mt5.TIMEFRAME_M5
    _TF_M15 = mt5.TIMEFRAME_M15
    _TF_H1 = mt5.TIMEFRAME_H1
    _TF_H4 = mt5.TIMEFRAME_H4
except Exception:
    _TF_M1 = 1; _TF_M5 = 5; _TF_M15 = 15; _TF_H1 = 16385; _TF_H4 = 16388

_TF_MAP = {1: _TF_M1, 5: _TF_M5, 15: _TF_M15, 60: _TF_H1, 240: _TF_H4}


class TradingOrchestrator:
    def __init__(self, config_path='config/settings.json'):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.lock = threading.Lock()
        self.is_running = False
        self.thread = None
        self.state = {}
        self.log_callbacks = []

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
        self.online_learner = OnlineLearner(self.experts, self.esn, self.reasoning, self.predictive)
        self.self_improvement = SelfImprovementEngine(self.risk_manager, self.online_learner)
        self.symbols = self.config.get('trade_symbols', ['EURUSD', 'GBPUSD'])
        self.timeframe = _TF_MAP.get(self.config.get('timeframe', 5), _TF_M5)
        self.update_interval = self.config.get('poll_interval_seconds', 2)
        self.open_orders = {}
        self.status = 'stopped'
        self.is_connected = False
        self.last_error = None
        self._balance_sync_counter = 0

    def add_log_callback(self, cb):
        self.log_callbacks.append(cb)

    def _log(self, level, message):
        self.database.insert_log(level, message)
        for cb in self.log_callbacks:
            try:
                cb(level, message)
            except Exception:
                pass

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
            self._log('ERROR', 'No broker configured')
            return False
        self._log('INFO', 'Connecting to broker...')
        connected = self.broker.connect()
        self.is_connected = connected
        if connected:
            info = self.broker.get_account_info()
            if info:
                self.risk_manager.current_balance = info['balance']
                self.risk_manager.initial_balance = info['balance']
                self._log('INFO', f"Connected: {info.get('name','')} | Balance: {info['currency']} {info['balance']:.2f} | Leverage: 1:{info['leverage']}")
            else:
                self._log('WARNING', 'Connected but could not retrieve account info')
        else:
            err = getattr(self.broker, 'last_error', 'Unknown error')
            self.last_error = err
            self._log('ERROR', f'Connection failed: {err}')
        return connected

    def disconnect(self):
        if self.broker is not None:
            self.broker.disconnect()
        self.is_connected = False
        self._log('INFO', 'Disconnected from broker')

    def ensure_connection(self):
        if self.broker is None:
            return False
        if self.is_connected and hasattr(self.broker, 'check_connection'):
            if self.broker.check_connection():
                return True
            self.is_connected = False
            self._log('WARNING', 'Connection lost, reconnecting...')
        connected = self.broker.reconnect() if hasattr(self.broker, 'reconnect') else self.connect()
        self.is_connected = connected
        if connected:
            info = self.broker.get_account_info()
            if info:
                self.risk_manager.current_balance = info['balance']
                self._log('INFO', f'Reconnected. Balance: {info["balance"]:.2f}')
        return connected

    def start(self):
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            self.status = 'running'
        self._log('INFO', f'AI trading started | Symbols: {", ".join(self.symbols)}')
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        with self.lock:
            self.is_running = False
            self.status = 'stopped'
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        self._log('INFO', 'AI trading stopped')

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
            with self.lock:
                self.status = 'running'
            try:
                self._sync_balance()
                self._process_symbols()
            except Exception as e:
                self._log('ERROR', f'Loop error: {e}')
            time.sleep(self.update_interval)

    def _sync_balance(self):
        self._balance_sync_counter += 1
        if self._balance_sync_counter % 5 == 0:
            info = self.broker.get_account_info()
            if info:
                self.risk_manager.current_balance = info['balance']
                open_pnl = info.get('profit', 0.0)
                self.database.insert_equity_point(info['balance'], info['equity'], open_pnl)
            broker_positions = self.broker.get_open_positions()
            if broker_positions is not None:
                for pos in broker_positions:
                    sym = pos['symbol']
                    if sym in self.risk_manager.open_positions:
                        self.risk_manager.open_positions[sym]['pnl'] = pos['pnl']
                        self.risk_manager.open_positions[sym]['current_price'] = pos['current_price']

    def _process_symbols(self):
        batch = self.bridge.get_batch_candles(self.symbols, timeframe=self.timeframe, count=500)
        ticks = self.bridge.get_batch_ticks(self.symbols)

        for symbol, candles in batch.items():
            if not candles:
                continue
            try:
                features = self.feature_extractor.extract_features(candles)
                if not features:
                    continue
                state = self.feature_extractor.get_state_vector(features)
                expert_pred, _, expert_confidence, _ = self.experts.predict(state)
                esn_pred = self.esn.predict_next_state(state)
                reasoning_output = self.reasoning.reason(features)
                predictive_output = self.predictive.process_tick(state)

                signal = self._combine_signals(
                    expert_pred,
                    float(np.mean(esn_pred)) if hasattr(esn_pred, '__len__') else float(esn_pred),
                    reasoning_output['confidence'] * (0.5 if reasoning_output.get('regime') == 'high_volatility' else 1.0),
                    predictive_output['confidence']
                )

                self.meta_learner.update_weights(
                    expert_scores=expert_confidence,
                    esn_score=float(np.clip(np.tanh(float(np.mean(esn_pred))), 0, 1)),
                    bayesian_score=reasoning_output['confidence'],
                    predictive_score=predictive_output['confidence']
                )

                self.database.insert_market_event(
                    pair=symbol,
                    feature_snapshot=features,
                    prediction=signal,
                    error=predictive_output['error'],
                    confidence=reasoning_output['confidence']
                )

                if symbol in ticks:
                    tick = ticks[symbol]
                    self._evaluate_positions(symbol, tick)
                    self._attempt_open_position(symbol, features, state, signal, reasoning_output, tick)
            except Exception as e:
                self._log('ERROR', f'Error processing {symbol}: {e}')

        self._update_state()

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
        if symbol in self.risk_manager.open_positions:
            return
        should_trade, confidence = self.reasoning.should_trade(reasoning_output)
        if not should_trade:
            return
        if abs(signal) < 0.2:
            return

        direction = 'BUY' if signal > 0 else 'SELL'
        price = tick['ask'] if direction == 'BUY' else tick['bid']
        atr = max(features.get('atr_14', 0.0001), 0.0001)
        sl = price - atr * 1.5 if direction == 'BUY' else price + atr * 1.5
        tp = price + atr * 3.0 if direction == 'BUY' else price - atr * 3.0
        size = self.risk_manager.calculate_position_size(price, sl, symbol, confidence)

        if size <= 0:
            return

        result = self.broker.send_order(
            symbol=symbol,
            action=direction,
            volume=size,
            price=price,
            sl=sl,
            tp=tp,
            comment='forex_ai'
        )

        if result:
            actual_price = result.get('price', price)
            actual_size = result.get('volume', size)
            self.risk_manager.open_position(symbol, direction, actual_price, sl, tp, actual_size, confidence)
            self._log('TRADE', f'OPENED {direction} {symbol} | size={actual_size:.2f} | price={actual_price:.5f} | conf={confidence:.2f}')
        else:
            err = getattr(self.broker, 'last_error', 'unknown')
            self._log('ERROR', f'Order rejected {symbol}: {err}')

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
                exit_price=closed.get('exit_price', current_price),
                size=closed['position_size'],
                pnl=closed['pnl'],
                confidence=closed.get('confidence', 0.0),
                reason=closed.get('close_reason', 'closed')
            )
            pnl = closed['pnl']
            emoji = '✅' if pnl >= 0 else '❌'
            self._log('TRADE', f'{emoji} CLOSED {symbol} | pnl={pnl:+.2f} | reason={closed.get("close_reason","??")}')

    def _update_state(self):
        try:
            account_status = self.risk_manager.get_account_status()
            info = self.broker.get_account_info() if self.is_connected else None
            if info:
                account_status['account_balance'] = info['balance']
                account_status['total_equity'] = info['equity']
                account_status['open_pnl'] = info.get('profit', 0.0)
            open_pos = self.risk_manager.get_open_positions()
            trade_stats = self.risk_manager.get_trade_stats()
            meta_weights = self.meta_learner.get_weights().tolist()
            try:
                top_experts = self.experts.get_top_experts(k=3)
                expert_conf = float(np.mean([e['performance_score'] for e in top_experts])) if top_experts else 0.0
            except Exception:
                expert_conf = 0.0
            with self.lock:
                self.state = {
                    'status': self.status,
                    'symbols': self.symbols,
                    'account': account_status,
                    'open_positions': open_pos,
                    'trade_stats': trade_stats,
                    'meta_weights': meta_weights,
                    'prediction': {
                        'expert': expert_conf,
                        'esn_confidence': float(getattr(self.predictive, 'confidence_level', 0)),
                        'bayesian_confidence': float(self.reasoning.belief_net.get_confidence()) if hasattr(self.reasoning, 'belief_net') else 0.0,
                        'predictive_confidence': float(getattr(self.predictive, 'confidence_level', 0))
                    }
                }
        except Exception as e:
            self._log('ERROR', f'State update error: {e}')

    def get_state(self):
        with self.lock:
            return self.state.copy()

    def get_light_diagnostics(self):
        with self.lock:
            s = self.state
            pred = s.get('prediction', {})
            return {
                'ensemble_confidence': float(pred.get('expert', 0.0)),
                'esn_confidence': float(pred.get('esn_confidence', 0.0)),
                'bayesian_confidence': float(pred.get('bayesian_confidence', 0.0)),
                'predictive_confidence': float(pred.get('predictive_confidence', 0.0)),
                'meta_weights': s.get('meta_weights', [])
            }
