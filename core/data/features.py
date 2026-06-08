import numpy as np
import threading

try:
    from core.engine.feature_engine_wrapper import FeatureEngineC
except Exception:
    FeatureEngineC = None


class RSI:
    @staticmethod
    def compute(prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices)
        up = np.where(deltas > 0, deltas, 0.0)
        dn = np.where(deltas < 0, -deltas, 0.0)
        avg_up = np.mean(up[-period:])
        avg_dn = np.mean(dn[-period:])
        rs = avg_up / avg_dn if avg_dn != 0 else 0
        return float(100.0 - (100.0 / (1.0 + rs)))


class MACD:
    @staticmethod
    def compute(prices, fast=12, slow=26, signal=9):
        if len(prices) < slow:
            return 0.0, 0.0, 0.0
        def ema(p, n):
            k = 2.0 / (n + 1)
            e = p[0]
            for v in p[1:]:
                e = v * k + e * (1 - k)
            return e
        macd = ema(prices[-fast*3:], fast) - ema(prices[-slow*3:], slow)
        sig = macd * 0.85
        return float(macd), float(sig), float(macd - sig)


class ATR:
    @staticmethod
    def compute(high, low, close, period=14):
        if len(high) < period + 1:
            return float(abs(high[-1] - low[-1]))
        tr = np.maximum(
            high[-period:] - low[-period:],
            np.maximum(
                np.abs(high[-period:] - close[-period-1:-1]),
                np.abs(low[-period:] - close[-period-1:-1])
            )
        )
        return float(np.mean(tr))


class Bollinger:
    @staticmethod
    def compute(prices, period=20, std_dev=2):
        if len(prices) < period:
            return float(prices[-1]), float(prices[-1]), float(prices[-1])
        ma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        return float(ma + std_dev * std), float(ma), float(ma - std_dev * std)


class Stochastic:
    @staticmethod
    def compute(high, low, close, period=14):
        if len(high) < period:
            return 50.0, 50.0
        lo = np.min(low[-period:])
        hi = np.max(high[-period:])
        k = 100.0 * (close[-1] - lo) / (hi - lo) if hi != lo else 50.0
        return float(k), float(k)


class CCI:
    @staticmethod
    def compute(high, low, close, period=20):
        if len(high) < period:
            return 0.0
        tp = (high[-period:] + low[-period:] + close[-period:]) / 3.0
        sma = np.mean(tp)
        mad = np.mean(np.abs(tp - sma))
        return float((tp[-1] - sma) / (0.015 * mad)) if mad != 0 else 0.0


class ADX:
    @staticmethod
    def compute(high, low, close, period=14):
        if len(high) < period * 2:
            return 0.0
        up = high[-period:] - high[-period-1:-1]
        down = low[-period-1:-1] - low[-period:]
        pos_dm = np.where((up > down) & (up > 0), up, 0.0)
        neg_dm = np.where((down > up) & (down > 0), down, 0.0)
        tr = np.maximum(
            high[-period:] - low[-period:],
            np.maximum(np.abs(high[-period:] - close[-period-1:-1]),
                       np.abs(low[-period:] - close[-period-1:-1]))
        )
        atr = np.mean(tr)
        if atr == 0:
            return 0.0
        di_plus = 100 * np.mean(pos_dm) / atr
        di_minus = 100 * np.mean(neg_dm) / atr
        di_sum = di_plus + di_minus
        return float(100 * abs(di_plus - di_minus) / di_sum) if di_sum > 0 else 0.0


class OBV:
    @staticmethod
    def compute(close, volume):
        if len(close) < 2:
            return 0.0
        obv = 0.0
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv += volume[i]
            elif close[i] < close[i-1]:
                obv -= volume[i]
        return float(obv)


class FeatureExtractor:
    def __init__(self, lookback_window=500):
        self.lookback = lookback_window
        self.lock = threading.Lock()

    def extract_features(self, candle_data):
        with self.lock:
            if not candle_data or len(candle_data) < 50:
                return None
            window = candle_data[-self.lookback:]
            closes  = np.array([c['close']  for c in window], dtype=np.float64)
            highs   = np.array([c['high']   for c in window], dtype=np.float64)
            lows    = np.array([c['low']    for c in window], dtype=np.float64)
            volumes = np.array([c['volume'] for c in window], dtype=np.float64)

            f = {}
            f['rsi_14']        = RSI.compute(closes, 14)
            f['rsi_7']         = RSI.compute(closes, 7)
            macd, sig, hist    = MACD.compute(closes)
            f['macd']          = macd
            f['macd_signal']   = sig
            f['macd_histogram']= hist
            f['stoch_k'], f['stoch_d'] = Stochastic.compute(highs, lows, closes, 14)
            f['cci']           = CCI.compute(highs, lows, closes, 20)
            f['adx']           = ADX.compute(highs, lows, closes, 14)
            f['atr_14']        = ATR.compute(highs, lows, closes, 14)
            f['atr_20']        = ATR.compute(highs, lows, closes, 20)
            f['bb_upper'], f['bb_middle'], f['bb_lower'] = Bollinger.compute(closes, 20)
            f['obv']           = OBV.compute(closes, volumes)
            f['price']         = float(closes[-1])
            f['high_50']       = float(np.max(highs[-50:]))
            f['low_50']        = float(np.min(lows[-50:]))
            f['ma_20']         = float(np.mean(closes[-20:]))
            f['ma_50']         = float(np.mean(closes[-50:]))
            f['ma_200']        = float(np.mean(closes[-min(200, len(closes)):]))
            f['volatility']    = float(np.std(closes[-20:]))
            f['volume']        = float(volumes[-1])
            f['volume_ma_20']  = float(np.mean(volumes[-20:]))
            f['direction']     = 1.0 if closes[-1] > closes[-2] else -1.0
            f['returns']       = float((closes[-1] - closes[-2]) / closes[-2]) if closes[-2] != 0 else 0.0
            f['log_returns']   = float(np.log(closes[-1] / closes[-2])) if closes[-2] > 0 else 0.0
            return f

    def normalize_features(self, features):
        if not features:
            return {}
        price = features.get('price', 1.0) or 1.0
        atr   = features.get('atr_14', 0.0001) or 0.0001
        bb_u  = features.get('bb_upper', price)
        bb_l  = features.get('bb_lower', price)
        bb_range = (bb_u - bb_l) or 0.0001
        ma20  = features.get('ma_20', price)
        ma200 = features.get('ma_200', price)

        normalized = {
            'rsi_14':        (features.get('rsi_14', 50.0) - 50.0) / 50.0,
            'macd':          np.tanh(features.get('macd', 0.0) / (atr + 1e-8)),
            'macd_histogram':np.tanh(features.get('macd_histogram', 0.0) / (atr + 1e-8)),
            'stoch_k':       (features.get('stoch_k', 50.0) - 50.0) / 50.0,
            'cci':           np.tanh(features.get('cci', 0.0) / 100.0),
            'adx':           features.get('adx', 0.0) / 100.0,
            'direction':     float(features.get('direction', 0.0)),
            'volatility':    np.tanh(features.get('volatility', 0.0) / (atr + 1e-8)),
            'returns':       np.tanh(features.get('returns', 0.0) * 100.0),
            'bb_position':   (features.get('price', price) - bb_l) / bb_range - 0.5,
            'ma_trend':      np.tanh((ma20 - ma200) / (price + 1e-8) * 100.0),
        }
        return normalized

    def get_state_vector(self, features):
        if not features:
            return np.zeros(11, dtype=np.float32)
        normalized = self.normalize_features(features)
        keys = ['rsi_14', 'macd', 'macd_histogram', 'stoch_k',
                'cci', 'adx', 'direction', 'volatility', 'returns',
                'bb_position', 'ma_trend']
        vec = np.array([normalized.get(k, 0.0) for k in keys], dtype=np.float32)
        vec = np.nan_to_num(vec, nan=0.0, posinf=1.0, neginf=-1.0)
        return vec
