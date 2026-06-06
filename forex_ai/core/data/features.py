import numpy as np
from scipy import stats
import threading
try:
    from core.engine.feature_engine_wrapper import compute_features_py as native_compute_features
    _NATIVE_AVAILABLE = True
except Exception:
    native_compute_features = None
    _NATIVE_AVAILABLE = False

try:
    from core.engine.feature_engine_wrapper import FeatureEngineC
except Exception:
    FeatureEngineC = None

class RSI:
    @staticmethod
    def compute(prices, period=14):
        if len(prices) < period + 1:
            return np.nan
        
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        rs = up / down if down != 0 else 0
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        for d in deltas[period+1:]:
            up = (up * (period - 1) + (d if d > 0 else 0)) / period
            down = (down * (period - 1) + (-d if d < 0 else 0)) / period
            rs = up / down if down != 0 else 0
            rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi

class MACD:
    @staticmethod
    def compute(prices, fast=12, slow=26, signal=9):
        if len(prices) < slow:
            return np.nan, np.nan, np.nan
        
        exp_fast = prices[-fast:].mean()
        exp_slow = prices[-slow:].mean()
        macd = exp_fast - exp_slow
        
        signal_line = (macd + np.mean(prices[-signal:])) / 2
        histogram = macd - signal_line
        
        return macd, signal_line, histogram

class ATR:
    @staticmethod
    def compute(high, low, close, period=14):
        if len(high) < period:
            return np.nan
        
        tr = np.maximum(
            high[-period:] - low[-period:],
            np.maximum(
                np.abs(high[-period:] - close[-period-1]),
                np.abs(low[-period:] - close[-period-1])
            )
        )
        
        return np.mean(tr)

class Bollinger:
    @staticmethod
    def compute(prices, period=20, std_dev=2):
        if len(prices) < period:
            return np.nan, np.nan, np.nan
        
        ma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = ma + (std_dev * std)
        lower = ma - (std_dev * std)
        
        return upper, ma, lower

class Stochastic:
    @staticmethod
    def compute(high, low, close, period=14, smooth_k=3):
        if len(high) < period:
            return np.nan, np.nan
        
        lowest = np.min(low[-period:])
        highest = np.max(high[-period:])
        
        k = 100 * (close[-1] - lowest) / (highest - lowest) if highest != lowest else 50
        
        recent_k = [k]
        d = np.mean(recent_k[-smooth_k:]) if len(recent_k) >= smooth_k else k
        
        return k, d

class CCI:
    @staticmethod
    def compute(high, low, close, period=20):
        if len(high) < period:
            return np.nan
        
        tp = (high[-period:] + low[-period:] + close[-period:]) / 3
        sma = np.mean(tp)
        mad = np.mean(np.abs(tp - sma))
        
        cci = (tp[-1] - sma) / (0.015 * mad) if mad != 0 else 0
        return cci

class ADX:
    @staticmethod
    def compute(high, low, close, period=14):
        if len(high) < period * 2:
            return np.nan
        
        up = high[-period:] - high[-period-1:-1]
        down = low[-period-1:-1] - low[-period:]
        
        pos_dm = np.where((up > down) & (up > 0), up, 0)
        neg_dm = np.where((down > up) & (down > 0), down, 0)
        
        tr = np.maximum(
            high[-period:] - low[-period:],
            np.maximum(
                np.abs(high[-period:] - close[-period-1]),
                np.abs(low[-period:] - close[-period-1])
            )
        )
        
        atr = np.mean(tr)
        di_plus = 100 * np.mean(pos_dm) / atr if atr > 0 else 0
        di_minus = 100 * np.mean(neg_dm) / atr if atr > 0 else 0
        
        di_diff = np.abs(di_plus - di_minus)
        di_sum = di_plus + di_minus
        adx = 100 * di_diff / di_sum if di_sum > 0 else 0
        
        return adx

class OBV:
    @staticmethod
    def compute(close, volume):
        if len(close) < 2:
            return np.nan
        
        obv = np.zeros(len(close))
        obv[0] = volume[0]
        
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]
        
        return obv[-1]

class FeatureExtractor:
    def __init__(self, lookback_window=500):
        self.lookback = lookback_window
        self.lock = threading.Lock()
        self.cache = {}
        
    def extract_features(self, candle_data):
        with self.lock:
            if len(candle_data) < 50:
                return None
            
            closes = np.array([c['close'] for c in candle_data[-self.lookback:]])
            highs = np.array([c['high'] for c in candle_data[-self.lookback:]])
            lows = np.array([c['low'] for c in candle_data[-self.lookback:]])
            volumes = np.array([c['volume'] for c in candle_data[-self.lookback:]])
            
            features = {}
            
            c_values = None
            if FeatureEngineC is not None and FeatureEngineC.available():
                c_values = FeatureEngineC.compute_features(highs, lows, closes, volumes)
            
            if c_values is not None:
                features['rsi_14'] = float(c_values[0])
                features['rsi_7'] = float(RSI.compute(closes, 7))
                features['macd'] = float(c_values[1])
                features['macd_signal'] = float(c_values[1] * 0.85)
                features['macd_histogram'] = float(c_values[2])
                features['stoch_k'] = float(c_values[3])
                features['stoch_d'] = float(c_values[4])
                features['cci'] = float(c_values[5])
                features['adx'] = float(c_values[6])
                features['bb_upper'] = float(np.max(closes[-20:]) if len(closes) >= 20 else closes[-1])
                features['bb_middle'] = float(np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1])
                features['bb_lower'] = float(np.min(closes[-20:]) if len(closes) >= 20 else closes[-1])
                features['obv'] = OBV.compute(closes, volumes)
            else:
                features['rsi_14'] = RSI.compute(closes, 14)
                features['rsi_7'] = RSI.compute(closes, 7)
                macd, signal, hist = MACD.compute(closes)
                features['macd'] = macd
                features['macd_signal'] = signal
                features['macd_histogram'] = hist
                features['stoch_k'] = Stochastic.compute(highs, lows, closes, 14, 3)[0]
                features['stoch_d'] = Stochastic.compute(highs, lows, closes, 14, 3)[1]
                features['cci'] = CCI.compute(highs, lows, closes, 20)
                features['adx'] = ADX.compute(highs, lows, closes, 14)
                features['obv'] = OBV.compute(closes, volumes)
            
            features['atr_14'] = ATR.compute(highs, lows, closes, 14)
            features['atr_20'] = ATR.compute(highs, lows, closes, 20)
            
            upper, mid, lower = Bollinger.compute(closes, 20, 2)
            features['bb_upper'] = upper
            features['bb_middle'] = mid
            features['bb_lower'] = lower
            
            features['price'] = closes[-1]
            features['high_50'] = np.max(highs[-50:])
            features['low_50'] = np.min(lows[-50:])
            features['ma_20'] = np.mean(closes[-20:])
            features['ma_50'] = np.mean(closes[-50:])
            features['ma_200'] = np.mean(closes[-min(200, len(closes)):])
            
            features['volatility'] = np.std(closes[-20:])
            features['volume'] = volumes[-1]
            features['volume_ma_20'] = np.mean(volumes[-20:])
            
            direction = 1 if closes[-1] > closes[-2] else -1
            features['direction'] = direction
            
            features['returns'] = (closes[-1] - closes[-2]) / closes[-2]
            features['log_returns'] = np.log(closes[-1] / closes[-2])
            
            return features
    
    def normalize_features(self, features):
        if not features:
            if _NATIVE_AVAILABLE:
                try:
                    native = native_compute_features(list(highs), list(lows), list(closes), list(volumes))
                except Exception:
                    native = None
            else:
                native = None

            features = {}
            if native is not None:
                features['rsi_14'] = native.get('rsi_14', np.nan)
                features['rsi_7'] = native.get('rsi_7', np.nan)
                features['macd'] = native.get('macd', np.nan)
                features['macd_signal'] = native.get('macd_histogram', np.nan)
                features['macd_histogram'] = native.get('macd_histogram', np.nan)
                features['atr_14'] = native.get('atr_14', np.nan)
                features['atr_20'] = native.get('atr_20', np.nan)
                features['bb_upper'] = native.get('bb_upper', np.nan)
                features['bb_middle'] = native.get('bb_middle', np.nan)
                features['bb_lower'] = native.get('bb_lower', np.nan)
                features['stoch_k'] = np.nan
                features['stoch_d'] = np.nan
                features['cci'] = np.nan
                features['adx'] = np.nan
                features['obv'] = native.get('obv', np.nan)
            else:
                features['rsi_14'] = RSI.compute(closes, 14)
                features['rsi_7'] = RSI.compute(closes, 7)
                macd, signal, hist = MACD.compute(closes)
                features['macd'] = macd
                features['macd_signal'] = signal
                features['macd_histogram'] = hist
                features['atr_14'] = ATR.compute(highs, lows, closes, 14)
                features['atr_20'] = ATR.compute(highs, lows, closes, 20)
                upper, mid, lower = Bollinger.compute(closes, 20, 2)
                features['bb_upper'] = upper
                features['bb_middle'] = mid
                features['bb_lower'] = lower
                k, d = Stochastic.compute(highs, lows, closes, 14, 3)
                features['stoch_k'] = k
                features['stoch_d'] = d
                features['cci'] = CCI.compute(highs, lows, closes, 20)
                features['adx'] = ADX.compute(highs, lows, closes, 14)
                features['obv'] = OBV.compute(closes, volumes)
        else:
            normalized['ma_trend'] = 0
        
        return normalized
    
    def get_state_vector(self, features, history_len=10):
        if not features:
            return np.zeros(11 * history_len)
        
        normalized = self.normalize_features(features)
        
        state_keys = [
            'rsi_14', 'macd', 'macd_histogram', 'stoch_k', 
            'cci', 'adx', 'direction', 'volatility', 'returns', 
            'bb_position', 'ma_trend'
        ]
        
        state_vector = np.array([normalized.get(key, 0) for key in state_keys], dtype=np.float32)
        
        return state_vector
