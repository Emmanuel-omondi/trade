import numpy as np
import threading


class BayesianBeliefNetwork:
    def __init__(self, num_nodes=6):
        self.num_nodes = num_nodes
        self.lock      = threading.Lock()
        self.belief    = np.ones(num_nodes) / num_nodes
        self.history   = []

    def update_beliefs(self, observations):
        with self.lock:
            obs = np.array(observations, dtype=np.float64)
            obs = np.nan_to_num(obs, nan=0.0)
            probs = 1.0 / (1.0 + np.exp(-obs))
            weights = np.array([
                np.mean(probs),
                float(probs[0] > 0.7 or probs[0] < 0.3),
                float(probs[2] > 0.7 or probs[2] < 0.3),
                float(abs(obs[1]) > 0.5),
                float(probs[3] > 0.6),
                float(abs(obs[8]) > 0.3)
            ])
            weights = np.clip(weights, 0.01, 1.0)
            weights /= weights.sum()
            self.belief = 0.7 * self.belief + 0.3 * weights
            self.belief /= self.belief.sum()
            self.history.append(float(np.max(self.belief)))
            if len(self.history) > 100:
                self.history.pop(0)

    def get_confidence(self):
        with self.lock:
            top2 = np.sort(self.belief)[-2:]
            dominance = top2[-1] - top2[-2]
            return float(np.clip(self.belief.max() * 3.0 + dominance * 2.0, 0.0, 1.0))

    def get_uncertainty(self):
        with self.lock:
            p = self.belief + 1e-8
            return float(-np.sum(p * np.log(p)))

    def get_top_beliefs(self, k=3):
        with self.lock:
            idx = np.argsort(self.belief)[-k:][::-1]
            return [(int(i), float(self.belief[i])) for i in idx]

    def reset(self):
        with self.lock:
            self.belief = np.ones(self.num_nodes) / self.num_nodes


class MarketRegimeDetector:
    REGIMES = ['strong_uptrend', 'weak_uptrend', 'ranging',
               'weak_downtrend', 'strong_downtrend', 'high_volatility']

    def __init__(self):
        self.lock           = threading.Lock()
        self.current_regime = 'ranging'
        self.history        = []

    def detect(self, rsi, adx, atr, ma_trend, volatility, price_action):
        with self.lock:
            rsi = float(rsi) if not np.isnan(rsi) else 50.0
            adx = float(adx) if not np.isnan(adx) else 20.0

            # volatility threshold normalised to price-relative units
            vol_thresh = 0.005
            regime = 'ranging'
            if volatility > vol_thresh:
                regime = 'high_volatility'
            elif adx > 20:
                if ma_trend > 0 and price_action >= 0:
                    regime = 'strong_uptrend' if rsi > 55 else 'weak_uptrend'
                elif ma_trend < 0 and price_action <= 0:
                    regime = 'strong_downtrend' if rsi < 45 else 'weak_downtrend'

            self.current_regime = regime
            self.history.append(regime)
            if len(self.history) > 100:
                self.history.pop(0)
            return regime

    def get_regime_duration(self, regime):
        with self.lock:
            count = 0
            for r in reversed(self.history):
                if r == regime:
                    count += 1
                else:
                    break
            return count

    def get_regime_probability(self):
        with self.lock:
            if not self.history:
                return {r: 1/6 for r in self.REGIMES}
            total = len(self.history)
            return {r: self.history.count(r) / total for r in self.REGIMES}


class ReasoningEngine:
    def __init__(self):
        self._lock        = threading.Lock()
        self.belief_net   = BayesianBeliefNetwork(num_nodes=6)
        self.regime_detector = MarketRegimeDetector()
        self.trace        = []

    def reason(self, features):
        observations = [
            (features.get('rsi_14', 50.0) - 50.0) / 50.0,
            features.get('macd', 0.0) * 1000.0,
            (features.get('stoch_k', 50.0) - 50.0) / 50.0,
            features.get('adx', 20.0) / 100.0,
            features.get('cci', 0.0) / 200.0,
            (features.get('bb_position', 0.5) - 0.5) * 2.0 if 'bb_position' in features
                else (features.get('price', 1.0) - features.get('bb_middle', 1.0)) /
                     (features.get('atr_14', 0.001) + 1e-8),
            features.get('direction', 0.0),
            features.get('volatility', 0.0) * 100.0,
            features.get('ma_trend', 0.0) * 100.0 if 'ma_trend' in features
                else (features.get('ma_20', 1.0) - features.get('ma_50', 1.0)) /
                     (features.get('price', 1.0) + 1e-8) * 100.0,
            features.get('returns', 0.0) * 100.0,
            features.get('log_returns', 0.0) * 100.0,
        ]

        self.belief_net.update_beliefs(observations)

        regime = self.regime_detector.detect(
            rsi=features.get('rsi_14', 50.0),
            adx=features.get('adx', 20.0),
            atr=features.get('atr_14', 0.0001),
            ma_trend=features.get('ma_trend',
                (features.get('ma_20', 1.0) - features.get('ma_50', 1.0))),
            volatility=features.get('volatility', 0.0),
            price_action=features.get('returns', 0.0)
        )

        confidence  = self.belief_net.get_confidence()
        uncertainty = self.belief_net.get_uncertainty()

        output = {
            'regime':            regime,
            'confidence':        confidence,
            'uncertainty':       uncertainty,
            'top_predictions':   self.belief_net.get_top_beliefs(k=3),
            'regime_duration':   self.regime_detector.get_regime_duration(regime),
            'regime_probability':self.regime_detector.get_regime_probability(),
            'observations':      observations
        }

        with self._lock:
            self.trace.append(output)
            if len(self.trace) > 200:
                self.trace.pop(0)

        return output

    def should_trade(self, reasoning_output):
        # No lock here — reasoning_output is already a plain dict copy
        confidence  = float(reasoning_output.get('confidence', 0.0))
        uncertainty = float(reasoning_output.get('uncertainty', 99.0))
        regime      = reasoning_output.get('regime', 'ranging')

        if uncertainty > 3.5:
            return False, confidence
        if regime == 'high_volatility' and confidence < 0.35:
            return False, confidence
        return confidence > 0.25, confidence

    def get_reasoning_trace(self, depth=10):
        with self._lock:
            return self.trace[-depth:]

    def reset(self):
        with self._lock:
            self.belief_net.reset()
            self.trace.clear()
