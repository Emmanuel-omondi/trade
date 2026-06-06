import MetaTrader5 as mt5
import numpy as np
import threading
from datetime import datetime
import time


class MT5Bridge:
    def __init__(self, login=None, password=None, server=None):
        self.login = login
        self.password = password
        self.server = server
        self.lock = threading.Lock()
        self.is_connected = False
        self.account_info = None
        self.last_error = None
        self.connection_attempts = 0
        self.max_connection_attempts = 5

    def connect(self):
        with self.lock:
            if not mt5.initialize():
                self.last_error = mt5.last_error()
                return False
            if self.login and self.password and self.server:
                authorized = mt5.login(
                    login=int(self.login),
                    password=str(self.password),
                    server=str(self.server)
                )
                if not authorized:
                    self.last_error = mt5.last_error()
                    mt5.shutdown()
                    return False
            info = mt5.account_info()
            if info is None:
                self.last_error = mt5.last_error()
                mt5.shutdown()
                return False
            self.account_info = info
            self.is_connected = True
            self.connection_attempts = 0
            return True

    def disconnect(self):
        with self.lock:
            if self.is_connected:
                mt5.shutdown()
                self.is_connected = False

    def check_connection(self):
        with self.lock:
            if not self.is_connected:
                return False
            try:
                info = mt5.account_info()
                if info is None:
                    self.is_connected = False
                    return False
                return True
            except Exception:
                self.is_connected = False
                return False

    def reconnect(self):
        self.disconnect()
        time.sleep(1)
        return self.connect()

    def get_account_info(self):
        with self.lock:
            if not self.is_connected:
                return None
            try:
                info = mt5.account_info()
                if info is None:
                    return None
                return {
                    'balance': float(info.balance),
                    'equity': float(info.equity),
                    'profit': float(info.profit),
                    'margin': float(info.margin),
                    'margin_free': float(info.margin_free),
                    'margin_level': float(info.margin_level) if info.margin > 0 else 0.0,
                    'leverage': int(info.leverage),
                    'currency': str(info.currency),
                    'name': str(info.name),
                    'login': int(info.login),
                    'server': str(info.server),
                    'trade_allowed': bool(info.trade_allowed)
                }
            except Exception as e:
                self.last_error = str(e)
                return None

    def get_candle_data(self, symbol, timeframe, count=500):
        with self.lock:
            if not self.is_connected:
                return None
            try:
                rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
                if rates is None or len(rates) == 0:
                    return None
                return [
                    {
                        'time': datetime.fromtimestamp(r[0]),
                        'open': float(r[1]),
                        'high': float(r[2]),
                        'low': float(r[3]),
                        'close': float(r[4]),
                        'volume': float(r[5])
                    }
                    for r in rates
                ]
            except Exception as e:
                self.last_error = str(e)
                return None

    def get_tick_data(self, symbol):
        with self.lock:
            if not self.is_connected:
                return None
            try:
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    return None
                return {
                    'bid': float(tick.bid),
                    'ask': float(tick.ask),
                    'time': datetime.fromtimestamp(tick.time),
                    'volume': float(tick.volume)
                }
            except Exception as e:
                self.last_error = str(e)
                return None

    def send_order(self, symbol, action, volume, price=0, sl=0, tp=0, comment="forex_ai"):
        with self.lock:
            if not self.is_connected:
                return None
            try:
                info = mt5.symbol_info(symbol)
                if info is None:
                    return None
                if not info.visible:
                    mt5.symbol_select(symbol, True)

                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    return None

                if action == 'BUY':
                    order_type = mt5.ORDER_TYPE_BUY
                    exec_price = tick.ask
                else:
                    order_type = mt5.ORDER_TYPE_SELL
                    exec_price = tick.bid

                volume = round(max(float(volume), info.volume_min), 2)

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": order_type,
                    "price": exec_price,
                    "sl": float(sl),
                    "tp": float(tp),
                    "deviation": 30,
                    "magic": 202601,
                    "comment": comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }

                result = mt5.order_send(request)
                if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                    code = result.retcode if result else -1
                    comment_err = result.comment if result else "no result"
                    self.last_error = f"Order failed: {comment_err} (code {code})"
                    return None

                return {
                    'order': result.order,
                    'deal': result.deal,
                    'retcode': result.retcode,
                    'price': result.price,
                    'volume': result.volume
                }
            except Exception as e:
                self.last_error = str(e)
                return None

    def close_position(self, ticket, symbol, volume, direction):
        with self.lock:
            if not self.is_connected:
                return None
            try:
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    return None
                close_type = mt5.ORDER_TYPE_SELL if direction == 'BUY' else mt5.ORDER_TYPE_BUY
                close_price = tick.bid if direction == 'BUY' else tick.ask
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": float(volume),
                    "type": close_type,
                    "position": int(ticket),
                    "price": close_price,
                    "deviation": 30,
                    "magic": 202601,
                    "comment": "forex_ai_close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    return result.order
                return None
            except Exception as e:
                self.last_error = str(e)
                return None

    def get_open_positions(self):
        with self.lock:
            if not self.is_connected:
                return []
            try:
                positions = mt5.positions_get()
                if positions is None:
                    return []
                result = []
                for pos in positions:
                    if pos.magic == 202601:
                        result.append({
                            'ticket': pos.ticket,
                            'symbol': pos.symbol,
                            'type': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                            'volume': float(pos.volume),
                            'open_price': float(pos.price_open),
                            'current_price': float(pos.price_current),
                            'pnl': float(pos.profit),
                            'time_open': datetime.fromtimestamp(pos.time),
                            'sl': float(pos.sl),
                            'tp': float(pos.tp)
                        })
                return result
            except Exception as e:
                self.last_error = str(e)
                return []

    def get_symbol_info(self, symbol):
        with self.lock:
            if not self.is_connected:
                return None
            try:
                info = mt5.symbol_info(symbol)
                if info is None:
                    return None
                return {
                    'name': info.name,
                    'bid': float(info.bid),
                    'ask': float(info.ask),
                    'point': float(info.point),
                    'digits': int(info.digits),
                    'volume_min': float(info.volume_min),
                    'volume_max': float(info.volume_max),
                    'volume_step': float(info.volume_step),
                    'spread': int(info.spread)
                }
            except Exception as e:
                self.last_error = str(e)
                return None


class DataBridge:
    def __init__(self, mt5_bridge):
        self.mt5 = mt5_bridge
        self.candle_cache = {}
        self.tick_cache = {}
        self.cache_ttl = 1.0
        self.last_update = {}

    def fetch_candles(self, symbol, timeframe, count=500, force_update=False):
        key = f"{symbol}_{timeframe}"
        now = datetime.now().timestamp()
        last = self.last_update.get(key, 0)
        if not force_update and (now - last) < self.cache_ttl and key in self.candle_cache:
            return self.candle_cache[key]
        candles = self.mt5.get_candle_data(symbol, timeframe, count)
        if candles:
            self.candle_cache[key] = candles
            self.last_update[key] = now
            return candles
        return self.candle_cache.get(key)

    def fetch_ticks(self, symbol, force_update=False):
        now = datetime.now().timestamp()
        last = self.last_update.get(symbol, 0)
        if not force_update and (now - last) < 0.5 and symbol in self.tick_cache:
            return self.tick_cache[symbol]
        tick = self.mt5.get_tick_data(symbol)
        if tick:
            self.tick_cache[symbol] = tick
            self.last_update[symbol] = now
            return tick
        return self.tick_cache.get(symbol)

    def get_batch_candles(self, symbols, timeframe, count=500):
        return {s: self.fetch_candles(s, timeframe, count) for s in symbols if self.fetch_candles(s, timeframe, count)}

    def get_batch_ticks(self, symbols):
        return {s: t for s in symbols if (t := self.fetch_ticks(s)) is not None}
