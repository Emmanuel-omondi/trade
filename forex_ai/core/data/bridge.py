import MetaTrader5 as mt5
import numpy as np
import threading
from datetime import datetime, timedelta
import time

class MT5Bridge:
    def __init__(self, login=None, password=None, server=None):
        self.login = login
        self.password = password
        self.server = server
        self.lock = threading.Lock()
        
        self.is_connected = False
        self.account_info = None
        self.positions = {}
        self.orders = {}
        self.tick_data = {}
        self.last_error = None
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        
    def connect(self):
        with self.lock:
            if not mt5.initialize():
                err = mt5.last_error()
                self.last_error = err
                print(f"MT5 initialization failed: {err}")
                self.connection_attempts += 1
                if self.connection_attempts >= self.max_connection_attempts:
                    print('MT5: reached max connection attempts')
                return False
            
            if self.login and self.password and self.server:
                authorized = mt5.login(
                    login=self.login,
                    password=self.password,
                    server=self.server
                )
                
                if not authorized:
                    err = mt5.last_error()
                    self.last_error = err
                    print(f"MT5 login failed: {err}")
                    mt5.shutdown()
                    self.connection_attempts += 1
                    if self.connection_attempts >= self.max_connection_attempts:
                        print('MT5: reached max login attempts')
                    return False
            
            self.is_connected = True
            self.account_info = mt5.account_info()
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
                account_info = mt5.account_info()
                if account_info is None:
                    self.is_connected = False
                    return False
                return True
            except Exception:
                self.is_connected = False
                return False
    
    def reconnect(self):
        with self.lock:
            self.disconnect()
            return self.connect()
    
    def get_account_info(self):
        with self.lock:
            if not self.is_connected:
                return None
            
            account_info = mt5.account_info()
            
            return {
                'balance': account_info.balance,
                'equity': account_info.equity,
                'profit': account_info.profit,
                'margin': account_info.margin,
                'margin_free': account_info.margin_free,
                'margin_level': account_info.margin_level,
                'trades': account_info.trade_allowed,
                'leverage': account_info.leverage,
                'currency': account_info.currency
            }
    
    def get_candle_data(self, symbol, timeframe, count=500):
        with self.lock:
            if not self.is_connected:
                return None
            
            try:
                rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
                
                if rates is None or len(rates) == 0:
                    return None
                
                candles = []
                for rate in rates:
                    candles.append({
                        'time': datetime.fromtimestamp(rate[0]),
                        'open': rate[1],
                        'high': rate[2],
                        'low': rate[3],
                        'close': rate[4],
                        'volume': rate[5]
                    })
                
                return candles
            
            except Exception as e:
                print(f"Error getting candle data: {e}")
                return None
    
    def get_tick_data(self, symbol):
        with self.lock:
            if not self.is_connected:
                return None
            
            try:
                tick = mt5.symbol_info_tick(symbol)
                
                return {
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'time': datetime.fromtimestamp(tick.time),
                    'volume': tick.volume
                }
            
            except Exception as e:
                print(f"Error getting tick data: {e}")
                return None
    
    def send_order(self, symbol, action, volume, price=0, sl=0, tp=0, comment=""):
        with self.lock:
            if not self.is_connected:
                return None
            
            try:
                request = {
                    "action": action,
                    "symbol": symbol,
                    "volume": volume,
                    "type": mt5.ORDER_TYPE_BUY if action == mt5.TRADE_ACTION_DEAL else mt5.ORDER_TYPE_SELL,
                    "price": price,
                    "sl": sl,
                    "tp": tp,
                    "comment": comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(request)
                
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"Order failed: {result.retcode}")
                    return None
                
                return {
                    'order': result.order,
                    'deal': result.deal,
                    'retcode': result.retcode
                }
            
            except Exception as e:
                print(f"Error sending order: {e}")
                return None
    
    def close_position(self, symbol, volume, price=0):
        with self.lock:
            if not self.is_connected:
                return None
            
            try:
                tick = mt5.symbol_info_tick(symbol)
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": mt5.ORDER_TYPE_SELL if tick.bid > price else mt5.ORDER_TYPE_BUY,
                    "price": price if price > 0 else tick.bid,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(request)
                
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"Close order failed: {result.retcode}")
                    return None
                
                return result.order
            
            except Exception as e:
                print(f"Error closing position: {e}")
                return None
    
    def get_open_positions(self):
        with self.lock:
            if not self.is_connected:
                return None
            
            try:
                positions = mt5.positions_get()
                
                if positions is None or len(positions) == 0:
                    return []
                
                position_list = []
                for pos in positions:
                    position_list.append({
                        'ticket': pos.ticket,
                        'symbol': pos.symbol,
                        'type': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                        'volume': pos.volume,
                        'open_price': pos.price_open,
                        'current_price': pos.price_current,
                        'pnl': pos.profit,
                        'time_open': datetime.fromtimestamp(pos.time),
                        'sl': pos.sl,
                        'tp': pos.tp
                    })
                
                return position_list
            
            except Exception as e:
                print(f"Error getting positions: {e}")
                return []
    
    def get_symbol_info(self, symbol):
        with self.lock:
            if not self.is_connected:
                return None
            
            try:
                info = mt5.symbol_info(symbol)
                
                return {
                    'name': info.name,
                    'bid': info.bid,
                    'ask': info.ask,
                    'point': info.point,
                    'digits': info.digits,
                    'volume_min': info.volume_min,
                    'volume_max': info.volume_max,
                    'volume_step': info.volume_step
                }
            
            except Exception as e:
                print(f"Error getting symbol info: {e}")
                return None
    
    def get_available_symbols(self):
        with self.lock:
            if not self.is_connected:
                return []
            
            try:
                symbols = mt5.symbols_get()
                return [s.name for s in symbols if 'Forex' in s.description or 'FX' in s.description]
            
            except Exception as e:
                print(f"Error getting symbols: {e}")
                return []


class DataBridge:
    def __init__(self, mt5_bridge):
        self.mt5 = mt5_bridge
        self.lock = threading.Lock()
        
        self.candle_cache = {}
        self.tick_cache = {}
        self.update_interval = 1
        self.last_update = {}
        
    def fetch_candles(self, symbol, timeframe=mt5.TIMEFRAME_M5, count=500, force_update=False):
        with self.lock:
            cache_key = f"{symbol}_{timeframe}"
            
            if cache_key in self.last_update:
                elapsed = (datetime.now() - self.last_update[cache_key]).total_seconds()
                if elapsed < self.update_interval and not force_update:
                    return self.candle_cache.get(cache_key)
            
            candles = self.mt5.get_candle_data(symbol, timeframe, count)
            
            if candles:
                self.candle_cache[cache_key] = candles
                self.last_update[cache_key] = datetime.now()
                return candles
            
            return self.candle_cache.get(cache_key)
    
    def fetch_ticks(self, symbol, force_update=False):
        with self.lock:
            if symbol in self.last_update:
                elapsed = (datetime.now() - self.last_update[symbol]).total_seconds()
                if elapsed < 0.5 and not force_update:
                    return self.tick_cache.get(symbol)
            
            tick = self.mt5.get_tick_data(symbol)
            
            if tick:
                self.tick_cache[symbol] = tick
                self.last_update[symbol] = datetime.now()
                return tick
            
            return self.tick_cache.get(symbol)
    
    def get_batch_candles(self, symbols, timeframe=mt5.TIMEFRAME_M5, count=500):
        with self.lock:
            batch_data = {}
            
            for symbol in symbols:
                candles = self.fetch_candles(symbol, timeframe, count)
                if candles:
                    batch_data[symbol] = candles
            
            return batch_data
    
    def get_batch_ticks(self, symbols):
        with self.lock:
            batch_ticks = {}
            
            for symbol in symbols:
                tick = self.fetch_ticks(symbol)
                if tick:
                    batch_ticks[symbol] = tick
            
            return batch_ticks
