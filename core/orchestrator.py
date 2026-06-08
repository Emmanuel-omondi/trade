import json
import numpy as np
import threading
import time
from pathlib import Path
from datetime import datetime
from core.data.bridge import DataBridge
from core.data.brokers import create_broker_from_config
from core.data.features import FeatureExtractor
from core.data.market_clock import MarketClock
from core.brain.experts import ExpertEnsemble
from core.brain.esn import TemporalDifferenceMemory
from core.brain.bayesian import ReasoningEngine
from core.brain.predictive import PredictiveCodingLoop
from core.brain.meta_learner import AdaptiveWeighting
from core.risk.engine import RiskManager
from core.learning.online_learner import OnlineLearner, SelfImprovementEngine
from core.learning.historical_trainer import HistoricalTrainer
from db.database import Database

try:
    import MetaTrader5 as mt5
    _TF = {1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15,
           60: mt5.TIMEFRAME_H1, 240: mt5.TIMEFRAME_H4}
except Exception:
    _TF = {1: 1, 5: 5, 15: 15, 60: 16385, 240: 16388}


class TradingOrchestrator:
    def __init__(self, config_path='config/settings.json'):
        self.config_path  = Path(config_path)
        self.config       = self._load_config()
        self._lock        = threading.Lock()
        self.is_running   = False
        self.is_connected = False
        self.status       = 'stopped'
        self.last_error   = None
        self._state       = {}
        self._log_cbs     = []

        self.database     = Database(path=self.config.get('database_path', 'db/forex_ai.db'))
        self.broker       = create_broker_from_config(self.config)
        self.bridge       = DataBridge(self.broker)
        self.extractor    = FeatureExtractor(lookback_window=500)
        self.clock        = MarketClock()
        self.experts      = ExpertEnsemble(n_experts=self.config.get('num_experts', 20))
        self.esn          = TemporalDifferenceMemory(state_size=11, esn_hidden=self.config.get('esn_hidden', 120))
        self.reasoning    = ReasoningEngine()
        self.predictive   = PredictiveCodingLoop(state_size=11)
        self.meta_learner = AdaptiveWeighting(num_components=4)
        self.risk_manager = RiskManager(
            account_balance=self.config.get('account_balance', 10000),
            risk_per_trade =self.config.get('risk_per_trade', 0.02),
            max_daily_loss =self.config.get('max_daily_loss', 0.05)
        )
        self.online_learner   = OnlineLearner(self.experts, self.esn, self.reasoning, self.predictive)
        self.self_improvement = SelfImprovementEngine(self.risk_manager, self.online_learner)
        self.hist_trainer     = HistoricalTrainer(
            self.extractor, self.experts, self.esn,
            self.reasoning, self.predictive, self.database
        )

        self.symbols           = self.config.get('trade_symbols', ['EURUSD', 'GBPUSD'])
        self.timeframe         = _TF.get(self.config.get('timeframe', 5), 5)
        self.update_interval   = self.config.get('poll_interval_seconds', 2.0)
        self._loop_thread      = None
        self._bootstrap_thread = None
        self._tick_counter     = 0
        self._closed_markets   = {}
        self._closed_retry_sec = 300
        self._bootstrapped     = False
        self._weekend_warned   = False

    # ── logging ──────────────────────────────────────────────────────────────

    def add_log_callback(self, cb):
        self._log_cbs.append(cb)

    def _log(self, level, message):
        try:
            self.database.insert_log(level, message)
        except Exception:
            pass
        for cb in self._log_cbs:
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

    # ── connect / disconnect ─────────────────────────────────────────────────

    def connect(self):
        if self.broker is None:
            self._log('ERROR', 'No broker configured — check Config tab')
            return False
        self._log('INFO', 'Connecting to broker...')
        try:
            ok = self.broker.connect()
        except Exception as e:
            self._log('ERROR', f'Connect exception: {e}')
            return False
        self.is_connected = ok
        if ok:
            info = self.broker.get_account_info()
            if info:
                self.risk_manager.sync_live_account(
                    info['balance'], info['equity'], info.get('profit', 0.0)
                )
                self._log('INFO',
                    f"Connected: {info.get('name','')} | "
                    f"Balance: {info['currency']} {info['balance']:,.2f} | "
                    f"Leverage: 1:{info['leverage']}")
            else:
                self._log('WARNING', 'Connected but could not read account info')
        else:
            err = getattr(self.broker, 'last_error', 'unknown')
            self.last_error = err
            self._log('ERROR', f'Connection failed: {err}')
        return ok

    def disconnect(self):
        if self.broker:
            try:
                self.broker.disconnect()
            except Exception:
                pass
        self.is_connected = False
        self._log('INFO', 'Disconnected from broker')

    def _reconnect(self):
        self.is_connected = False
        self._log('WARNING', 'Connection lost — reconnecting...')
        try:
            ok = self.broker.reconnect() if hasattr(self.broker, 'reconnect') else self.connect()
        except Exception:
            ok = False
        self.is_connected = ok
        if ok:
            info = self.broker.get_account_info()
            if info:
                self.risk_manager.sync_live_account(
                    info['balance'], info['equity'], info.get('profit', 0.0))
                self._log('INFO', f'Reconnected | Balance: {info["balance"]:,.2f}')
        return ok

    # ── start / stop ─────────────────────────────────────────────────────────

    def start(self):
        with self._lock:
            if self.is_running:
                return
            self.is_running = True
            self.status     = 'bootstrapping'

        self._log('INFO', f'AI trading started | Symbols: {", ".join(self.symbols)}')
        self._log('INFO', f'Market clock UTC: {self.clock.utc_now().strftime("%Y-%m-%d %H:%M")} | Session: {self.clock.active_session()}')

        # bootstrap in background — trading starts immediately after
        self._bootstrap_thread = threading.Thread(
            target=self._run_bootstrap, daemon=True)
        self._bootstrap_thread.start()

        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

    def stop(self):
        with self._lock:
            self.is_running = False
            self.status     = 'stopped'
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5)
        self._log('INFO', 'AI trading stopped')

    # ── historical bootstrap (background) ────────────────────────────────────

    def _run_bootstrap(self):
        with self._lock:
            self.status = 'bootstrapping'
        try:
            self.hist_trainer.run_full_bootstrap(
                self.bridge, self.symbols, self.timeframe, log_fn=self._log)
        except Exception as e:
            self._log('ERROR', f'Bootstrap error: {e}')
        with self._lock:
            self._bootstrapped = True
            if self.is_running:
                self.status = 'running'

    # ── main trading loop ─────────────────────────────────────────────────────

    def _run_loop(self):
        while True:
            with self._lock:
                if not self.is_running:
                    break

            # ── weekend / market hours check ─────────────────────────────────
            if self.clock.is_weekend():
                if not self._weekend_warned:
                    mins = self.clock.minutes_to_open()
                    self._log('INFO',
                        f'⏸ Market closed (weekend). '
                        f'Reopens in ~{mins} min '
                        f'(Sunday 22:00 UTC). AI standing by...')
                    self._weekend_warned = True
                    with self._lock:
                        self.status = 'weekend'
                time.sleep(60)
                continue
            else:
                if self._weekend_warned:
                    self._weekend_warned = False
                    self._log('INFO', '▶ Market reopened — resuming trading')
                    with self._lock:
                        self.status = 'running' if self._bootstrapped else 'bootstrapping'

            # ── warn 30 min before weekend ───────────────────────────────────
            if self.clock.close_positions_warning():
                self._handle_pre_weekend_close()

            if not self.is_connected:
                with self._lock:
                    self.status = 'reconnecting'
                if not self._reconnect():
                    time.sleep(5)
                    continue
                with self._lock:
                    self.status = 'running' if self._bootstrapped else 'bootstrapping'

            try:
                self._sync_balance()
                self._process_symbols()
            except Exception as e:
                self._log('ERROR', f'Loop error: {e}')

            time.sleep(max(0.1, float(self.update_interval)))

    def _handle_pre_weekend_close(self):
        positions = self.risk_manager.get_open_positions()
        if not positions:
            return
        self._log('WARNING', '⚠ 30 min to weekend close — closing all positions')
        for symbol, pos in positions.items():
            try:
                tick = self.bridge.fetch_ticks(symbol)
                if not tick:
                    continue
                price = tick['bid'] if pos['direction'] == 'BUY' else tick['ask']
                closed = self.risk_manager.close_position(symbol, price, 'pre_weekend')
                if closed:
                    self.database.insert_trade(
                        pair=symbol, direction=closed['direction'],
                        entry_price=closed['entry_price'],
                        exit_price=closed.get('exit_price', price),
                        size=closed['position_size'], pnl=closed['pnl'],
                        confidence=closed.get('confidence', 0.0),
                        reason='pre_weekend'
                    )
                    self._log('TRADE',
                        f'Closed {symbol} before weekend | pnl={closed["pnl"]:+.2f}')
            except Exception as e:
                self._log('ERROR', f'Pre-weekend close error {symbol}: {e}')

    # ── balance sync ─────────────────────────────────────────────────────────

    def _sync_balance(self):
        self._tick_counter += 1
        if self._tick_counter % 3 != 0:
            return
        try:
            info = self.broker.get_account_info()
            if info:
                self.risk_manager.sync_live_account(
                    info['balance'], info['equity'], info.get('profit', 0.0))
                self.database.insert_equity_point(
                    info['balance'], info['equity'], info.get('profit', 0.0))
            broker_pos = self.broker.get_open_positions()
            if broker_pos:
                for pos in broker_pos:
                    self.risk_manager.update_open_pnl(pos['symbol'], pos['current_price'])
        except Exception as e:
            self._log('WARNING', f'Balance sync error: {e}')

    # ── symbol processing ─────────────────────────────────────────────────────

    def _process_symbols(self):
        session = self.clock.active_session()

        for symbol in self.symbols:
            with self._lock:
                if not self.is_running:
                    return

            # skip if recently closed
            if symbol in self._closed_markets:
                if time.time() - self._closed_markets[symbol] < self._closed_retry_sec:
                    continue
                del self._closed_markets[symbol]

            # session-aware skip
            if not self.clock.symbol_is_tradeable(symbol):
                continue

            try:
                candles = self.bridge.fetch_candles(symbol, self.timeframe, count=500)
                if not candles:
                    continue
                tick = self.bridge.fetch_ticks(symbol)
                if not tick:
                    continue

                features = self.extractor.extract_features(candles)
                if not features:
                    continue
                state = self.extractor.get_state_vector(features)

                expert_pred, _, expert_conf, _ = self.experts.predict(state)
                esn_pred   = self.esn.predict_next_state(state)
                reasoning  = self.reasoning.reason(features)
                predictive = self.predictive.process_tick(state)

                # rule-based seed signal
                rsi    = features.get('rsi_14', 50.0)
                macd_h = features.get('macd_histogram', 0.0)
                ma20   = features.get('ma_20', 1.0)
                ma50   = features.get('ma_50', 1.0)
                price  = features.get('price', 1.0)
                trend  = (ma20 - ma50) / (price + 1e-8)
                rsi_sig     = (rsi - 50.0) / 50.0
                rule_signal = float(np.tanh(rsi_sig * 0.4 + trend * 20.0 + macd_h * 500.0))

                w          = self.meta_learner.get_weights()
                esn_scalar = float(np.tanh(float(np.mean(esn_pred))))
                raw_signal = (
                    float(expert_pred)  * w[0] +
                    esn_scalar          * w[1] +
                    reasoning['confidence'] * np.sign(rule_signal) * w[2] +
                    predictive.get('confidence', 0.0) * np.sign(rule_signal) * w[3] +
                    rule_signal * 0.4
                )
                signal = float(np.tanh(raw_signal))

                self.meta_learner.update_weights(
                    expert_scores=float(expert_conf),
                    esn_score=max(0.0, esn_scalar),
                    bayesian_score=float(reasoning.get('confidence', 0.0)),
                    predictive_score=float(predictive.get('confidence', 0.0))
                )
                recent_trades = self.risk_manager.trade_history[-20:]
                if recent_trades:
                    self.meta_learner.feed_trade_results(recent_trades)

                # log every 15 ticks
                if self._tick_counter % 15 == 0:
                    self._log('INFO',
                        f'{symbol} | {session} | regime={reasoning.get("regime","?")} | '
                        f'conf={reasoning.get("confidence",0):.2f} | signal={signal:.3f}')

                self._evaluate_positions(symbol, tick)
                self._attempt_trade(symbol, features, signal, reasoning, tick)

            except Exception as e:
                self._log('ERROR', f'Error processing {symbol}: {e}')

            time.sleep(0.05)

        self._rebuild_state()

    # ── trade attempt ─────────────────────────────────────────────────────────

    def _attempt_trade(self, symbol, features, signal, reasoning, tick):
        if not self.risk_manager.can_open_position():
            return
        if symbol in self.risk_manager.get_open_positions():
            return

        # wait for bootstrap to complete before trading
        # (still trade with rule-based if bootstrap taking too long)
        progress, is_trained = self.hist_trainer.get_progress()
        if not is_trained and progress < 0.3:
            return  # wait until at least 30% through bootstrap

        should_trade, confidence = self.reasoning.should_trade(reasoning)
        if not should_trade or abs(signal) < 0.10:
            return

        # prefer high-liquidity sessions
        if not self.clock.is_high_liquidity():
            if abs(signal) < 0.25:  # require stronger signal in off-peak
                return

        direction = 'BUY' if signal > 0 else 'SELL'
        price     = tick['ask'] if direction == 'BUY' else tick['bid']
        atr       = max(features.get('atr_14', 0.0001), 0.0001)
        sl        = price - atr * 1.5 if direction == 'BUY' else price + atr * 1.5
        tp        = price + atr * 3.0 if direction == 'BUY' else price - atr * 3.0
        size      = self.risk_manager.calculate_position_size(price, sl, symbol, confidence)
        if size <= 0:
            return

        # validate volume against broker live specs
        sym_info = self.broker.get_symbol_info(symbol) if hasattr(self.broker, 'get_symbol_info') else None
        if sym_info:
            vol_min  = sym_info.get('volume_min', 0.01)
            vol_max  = sym_info.get('volume_max', 100.0)
            vol_step = sym_info.get('volume_step', 0.01)
            if vol_step > 0:
                size = round(round(size / vol_step) * vol_step, 2)
            size = max(vol_min, min(vol_max, size))

        result = self.broker.send_order(symbol, direction, size, price, sl, tp)
        if result:
            actual_price = result.get('price', price)
            actual_size  = result.get('volume', size)
            self.risk_manager.open_position(
                symbol, direction, actual_price, sl, tp, actual_size, confidence)
            self._log('TRADE',
                f'OPENED {direction} {symbol} | '
                f'size={actual_size:.2f} | price={actual_price:.5f} | '
                f'conf={confidence:.2f} | session={self.clock.active_session()}')
        else:
            err = str(getattr(self.broker, 'last_error', 'unknown'))
            if 'code 10018' in err or 'Market closed' in err:
                self._closed_markets[symbol] = time.time()
                self._log('INFO', f'{symbol} market closed — retry in 5 min')
            elif 'code 10014' in err or 'Invalid volume' in err:
                self._log('WARNING', f'Volume error {symbol}: {err}')
            else:
                self._log('ERROR', f'Order rejected {symbol}: {err}')

    # ── position evaluation ───────────────────────────────────────────────────

    def _evaluate_positions(self, symbol, tick):
        positions = self.risk_manager.get_open_positions()
        pos = positions.get(symbol)
        if not pos:
            return
        try:
            direction = pos.get('direction', 'BUY')
            current   = tick['bid'] if direction == 'BUY' else tick['ask']
        except (KeyError, TypeError):
            return

        self.risk_manager.update_open_pnl(symbol, current)
        closed = self.risk_manager.check_stop_loss(symbol, current)
        if not closed:
            closed = self.risk_manager.check_take_profit(symbol, current)

        if closed and isinstance(closed, dict):
            pnl = closed.get('pnl', 0.0)
            try:
                self.database.insert_trade(
                    pair=symbol,
                    direction=closed.get('direction', direction),
                    entry_price=closed.get('entry_price', 0.0),
                    exit_price=closed.get('exit_price', current),
                    size=closed.get('position_size', 0.0),
                    pnl=pnl,
                    confidence=closed.get('confidence', 0.0),
                    reason=closed.get('close_reason', 'closed')
                )
            except Exception as db_err:
                self._log('WARNING', f'DB error: {db_err}')
            icon = '✅' if pnl >= 0 else '❌'
            self._log('TRADE',
                f'{icon} CLOSED {symbol} | pnl={pnl:+.2f} | {closed.get("close_reason","?")}')

            # online learning: reward/penalise based on outcome
            try:
                state = self.extractor.get_state_vector(
                    self.extractor.extract_features(
                        self.bridge.fetch_candles(symbol, self.timeframe, count=200) or []))
                if state is not None:
                    reward = float(np.sign(pnl))
                    self.online_learner.add_experience(
                        state=state, action=1.0 if direction == 'BUY' else -1.0,
                        reward=reward, next_state=state, done=True)
            except Exception:
                pass

    # ── state rebuild ─────────────────────────────────────────────────────────

    def _rebuild_state(self):
        try:
            progress, is_trained = self.hist_trainer.get_progress()
            account   = self.risk_manager.get_account_status()
            positions = self.risk_manager.get_open_positions()
            stats     = self.risk_manager.get_trade_stats()
            weights   = self.meta_learner.get_weights().tolist()
            with self._lock:
                self._state = {
                    'status':           self.status,
                    'symbols':          self.symbols,
                    'session':          self.clock.active_session(),
                    'is_weekend':       self.clock.is_weekend(),
                    'bootstrap_progress': progress,
                    'is_trained':       is_trained,
                    'account':          account,
                    'open_positions':   positions,
                    'trade_stats':      stats,
                    'meta_weights':     weights,
                    'prediction': {
                        'expert': 0.0, 'esn_confidence': 0.0,
                        'bayesian_confidence': 0.0, 'predictive_confidence': 0.0
                    }
                }
        except Exception as e:
            self._log('ERROR', f'State rebuild: {e}')

    def get_state(self):
        with self._lock:
            return dict(self._state)

    def get_light_diagnostics(self):
        with self._lock:
            pred = self._state.get('prediction', {})
            return {
                'ensemble_confidence':   float(pred.get('expert', 0)),
                'esn_confidence':        float(pred.get('esn_confidence', 0)),
                'bayesian_confidence':   float(pred.get('bayesian_confidence', 0)),
                'predictive_confidence': float(pred.get('predictive_confidence', 0)),
                'meta_weights':          self._state.get('meta_weights', [])
            }
