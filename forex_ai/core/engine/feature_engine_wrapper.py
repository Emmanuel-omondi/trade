import ctypes
import os
import sys
from pathlib import Path
import numpy as np

_lib = None

def _load_library():
    global _lib
    base = Path(__file__).parent
    candidates = [
        base / 'feature_engine.dll',
        base / 'feature_engine.so',
        base / 'feature_engine.dylib'
    ]
    for p in candidates:
        if p.exists():
            _lib = ctypes.CDLL(str(p))
            break
    if _lib is None:
        raise ImportError('Native feature engine library not found. Build it using build_feature_engine.bat')

_load_library()

_lib.compute_features.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_int
]
_lib.compute_features.restype = ctypes.c_int

def compute_features_py(high, low, close, volume):
    n = len(close)
    if not (len(high) == n and len(low) == n and len(volume) == n):
        raise ValueError('arrays must be same length')
    arr_high = (ctypes.c_double * n)(*map(float, high))
    arr_low = (ctypes.c_double * n)(*map(float, low))
    arr_close = (ctypes.c_double * n)(*map(float, close))
    arr_vol = (ctypes.c_double * n)(*map(float, volume))
    out_len = 12
    out_arr = (ctypes.c_double * out_len)()
    res = _lib.compute_features(arr_high, arr_low, arr_close, arr_vol, ctypes.c_int(n), out_arr, ctypes.c_int(out_len))
    if res != 0:
        raise RuntimeError('native compute_features failed')
    out = [out_arr[i] for i in range(out_len)]
    return {
        'rsi_14': out[0],
        'rsi_7': out[1],
        'macd': out[2],
        'macd_histogram': out[3],
        'atr_14': out[4],
        'atr_20': out[5],
        'bb_upper': out[6],
        'bb_middle': out[7],
        'bb_lower': out[8],
        'obv': out[9],
        'volatility': out[10],
        'direction': out[11]
    }
