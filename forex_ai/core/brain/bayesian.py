import numpy as np
from scipy.special import softmax, expit
import threading

class BayesianBeliefNetwork:
    def __init__(self, num_nodes=15):
        self.num_nodes = num_nodes
        self.lock = threading.Lock()
        
        self.belief = np.ones(num_nodes) / num_nodes
        self.prior = np.ones(num_nodes) / num_nodes
        self.likelihood = np.ones((num_nodes, 11))
        self.posterior = np.ones(num_nodes) / num_nodes
        
        self.update_history = []
        self.max_history = 100
        
    def update_beliefs(self, observations):
        with self.lock:
            obs = np.array(observations, dtype=np.float32)
            
            if len(obs) != self.likelihood.shape[1]:
                obs = np.pad(obs, (0, self.likelihood.shape[1] - len(obs)))[:self.likelihood.shape[1]]
            
            obs_prob = expit(obs)
            
            likelihood_update = obs_prob / (np.sum(obs_prob) + 1e-8)
            self.likelihood = 0.9 * self.likelihood + 0.1 * likelihood_update
            
            self.posterior = self.prior * np.prod(self.likelihood + 1e-8, axis=1)
            self.posterior = self.posterior / (np.sum(self.posterior) + 1e-8)
            
            self.belief = 0.8 * self.belief + 0.2 * self.posterior
            
            self.update_history.append({
                'belief': self.belief.copy(),
                'observations': obs.copy(),
                'entropy': self._compute_entropy()
            })
            
            if len(self.update_history) > self.max_history:
                self.update_history.pop(0)
    
    def get_top_beliefs(self, k=3):
        with self.lock:
            top_indices = np.argsort(self.belief)[-k:][::-1]
            return [(idx, self.belief[idx]) for idx in top_indices]
    
    def _compute_entropy(self):
        prob = self.belief + 1e-8
        return -np.sum(prob * np.log(prob))
    
    def get_uncertainty(self):
        with self.lock:
            return self._compute_entropy()
    
    def get_confidence(self):
        with self.lock:
            max_belief = np.max(self.belief)
            return max_belief
    
    def predict_state(self):
        with self.lock:
            top_node = np.argmax(self.belief)
            
            predictions = []
            for i, belief in enumerate(self.belief):
                if belief > 0.05:
                    predictions.append((i, belief))
            
            return predictions
    
    def sample_from_belief(self):
        with self.lock:
            return np.random.choice(self.num_nodes, p=self.belief)
    
    def reset(self):
        with self.lock:
            self.belief = np.ones(self.num_nodes) / self.num_nodes
            self.posterior = np.ones(self.num_nodes) / self.num_nodes
            self.update_history.clear()


class MarketRegimeDetector:
    REGIMES = {
        'strong_uptrend': 0,
        'weak_uptrend': 1,
        'ranging': 2,
        'weak_downtrend': 3,
        'strong_downtrend': 4,
        'high_volatility': 5
    }
    
    def __init__(self):
        self.lock = threading.Lock()
        self.current_regime = 'ranging'
        self.regime_history = []
        self.max_history = 100
        
    def detect(self, rsi, adx, atr, ma_trend, volatility, price_action):
        with self.lock:
            regime = self._classify_regime(rsi, adx, atr, ma_trend, volatility, price_action)
            self.current_regime = regime
            self.regime_history.append(regime)
            
            if len(self.regime_history) > self.max_history:
                self.regime_history.pop(0)
            
            return regime
    
    def _classify_regime(self, rsi, adx, atr, ma_trend, volatility, price_action):
        if np.isnan(rsi) or np.isnan(adx):
            return 'ranging'
        
        if volatility > 0.02:
            return 'high_volatility'
        
        if adx > 25:
            if ma_trend > 0 and price_action > 0:
                if rsi > 60:
                    return 'strong_uptrend'
                else:
                    return 'weak_uptrend'
            elif ma_trend < 0 and price_action < 0:
                if rsi < 40:
                    return 'strong_downtrend'
                else:
                    return 'weak_downtrend'
        
        return 'ranging'
    
    def get_regime_duration(self, regime):
        with self.lock:
            if not self.regime_history:
                return 0
            
            count = 0
            for r in reversed(self.regime_history):
                if r == regime:
                    count += 1
                else:
                    break
            
            return count
    
    def get_regime_probability(self):
        with self.lock:
            if not self.regime_history:
                return {k: 1/len(self.REGIMES) for k in self.REGIMES}
            
            counts = {}
            for regime in self.REGIMES:
                counts[regime] = self.regime_history.count(regime)
            
            total = sum(counts.values())
            return {k: v/total for k, v in counts.items()}


class ReasoningEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.belief_net = BayesianBeliefNetwork(num_nodes=15)
        self.regime_detector = MarketRegimeDetector()
        self.reasoning_trace = []
        self.max_trace = 200
        
    def reason(self, features):
        with self.lock:
            observations = [
                features.get('rsi_14', 0.5),
                features.get('macd', 0),
                features.get('stoch_k', 0.5),
                features.get('adx', 0.5),
                features.get('cci', 0),
                features.get('bb_position', 0.5),
                features.get('direction', 0.5),
                features.get('volatility', 0),
                features.get('ma_trend', 0),
                features.get('returns', 0),
                features.get('obv', 0)
            ]
            
            self.belief_net.update_beliefs(observations)
            
            regime = self.regime_detector.detect(
                rsi=features.get('rsi_14', 50),
                adx=features.get('adx', 20),
                atr=features.get('atr_14', 0),
                ma_trend=features.get('ma_trend', 0),
                volatility=features.get('volatility', 0),
                price_action=features.get('returns', 0)
            )
            
            confidence = self.belief_net.get_confidence()
            uncertainty = self.belief_net.get_uncertainty()
            
            predictions = self.belief_net.predict_state()
            
            reasoning_output = {
                'regime': regime,
                'confidence': confidence,
                'uncertainty': uncertainty,
                'top_predictions': self.belief_net.get_top_beliefs(k=3),
                'regime_duration': self.regime_detector.get_regime_duration(regime),
                'regime_probability': self.regime_detector.get_regime_probability(),
                'observations': observations
            }
            
            self.reasoning_trace.append(reasoning_output)
            if len(self.reasoning_trace) > self.max_trace:
                self.reasoning_trace.pop(0)
            
            return reasoning_output
    
    def get_reasoning_trace(self, depth=10):
        with self.lock:
            return self.reasoning_trace[-depth:]
    
    def should_trade(self, reasoning_output):
        with self.lock:
            confidence = reasoning_output['confidence']
            uncertainty = reasoning_output['uncertainty']
            
            if confidence < 0.4 or uncertainty > 2.0:
                return False, confidence
            
            regime = reasoning_output['regime']
            if regime == 'high_volatility':
                return confidence > 0.6, confidence
            
            return confidence > 0.45, confidence
    
    def reset(self):
        with self.lock:
            self.belief_net.reset()
            self.reasoning_trace.clear()
