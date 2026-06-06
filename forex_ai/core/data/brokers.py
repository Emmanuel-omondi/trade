import requests
import time
import threading
from datetime import datetime

class BrokerBridgeBase:
    def connect(self):
        raise NotImplementedError()
    def disconnect(self):
        raise NotImplementedError()
    def get_account_info(self):
        raise NotImplementedError()
    def get_candle_data(self, symbol, timeframe, count=500):
        raise NotImplementedError()
    def get_tick_data(self, symbol):
        raise NotImplementedError()
    def send_order(self, *args, **kwargs):
        raise NotImplementedError()
    def get_open_positions(self):
        raise NotImplementedError()

class GenericRESTBridge(BrokerBridgeBase):
    def __init__(self, base_url, api_key=None, timeout=10):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.timeout = timeout
        self.lock = threading.Lock()
        self.connected = False

    def connect(self):
        with self.lock:
            self.connected = True
            return True

    def disconnect(self):
        with self.lock:
            self.session.close()
            self.connected = False

    def _headers(self):
        h = {'Content-Type': 'application/json'}
        if self.api_key:
            h['Authorization'] = f'Bearer {self.api_key}'
        return h

    def get_account_info(self):
        with self.lock:
            try:
                r = self.session.get(f"{self.base_url}/account", headers=self._headers(), timeout=self.timeout)
                if r.status_code == 200:
                    return r.json()
            except Exception:
                return None

    def get_candle_data(self, symbol, timeframe, count=500):
        with self.lock:
            try:
                params = {'symbol': symbol, 'timeframe': timeframe, 'count': count}
                r = self.session.get(f"{self.base_url}/candles", headers=self._headers(), params=params, timeout=self.timeout)
                if r.status_code == 200:
                    return r.json().get('candles')
            except Exception:
                return None

    def get_tick_data(self, symbol):
        with self.lock:
            try:
                r = self.session.get(f"{self.base_url}/tick", headers=self._headers(), params={'symbol': symbol}, timeout=self.timeout)
                if r.status_code == 200:
                    return r.json()
            except Exception:
                return None

    def send_order(self, symbol, side, volume, price=None, sl=None, tp=None, comment=None):
        with self.lock:
            payload = {'symbol': symbol, 'side': side, 'volume': volume}
            if price is not None: payload['price'] = price
            if sl is not None: payload['sl'] = sl
            if tp is not None: payload['tp'] = tp
            if comment is not None: payload['comment'] = comment
            try:
                r = self.session.post(f"{self.base_url}/order", json=payload, headers=self._headers(), timeout=self.timeout)
                if r.status_code in (200,201):
                    return r.json()
            except Exception:
                return None

    def get_open_positions(self):
        with self.lock:
            try:
                r = self.session.get(f"{self.base_url}/positions", headers=self._headers(), timeout=self.timeout)
                if r.status_code == 200:
                    return r.json().get('positions', [])
            except Exception:
                return []


def create_broker_from_config(cfg):
    broker = cfg.get('broker', 'mt5')
    if broker == 'mt5':
        try:
            from core.data.bridge import MT5Bridge
            return MT5Bridge(login=cfg.get('mt5_login'), password=cfg.get('mt5_password'), server=cfg.get('mt5_server'))
        except Exception:
            return None
    else:
        base_url = cfg.get('broker_base_url')
        api_key = cfg.get('broker_api_key')
        return GenericRESTBridge(base_url=base_url, api_key=api_key)
