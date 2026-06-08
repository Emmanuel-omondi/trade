import threading
import time
from datetime import datetime, timezone, timedelta
import urllib.request
import email.utils


class MarketClock:
    """
    NTP-accurate market session checker.
    Falls back to system time if internet unreachable.
    All times in UTC.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._offset_secs = 0.0
        self._last_sync   = 0.0
        self._sync_interval = 3600
        self._sync()

    def _sync(self):
        """Get accurate UTC time from HTTP Date header (works without NTP port)."""
        servers = [
            'http://worldtimeapi.org/api/timezone/UTC',
            'http://time.cloudflare.com',
            'https://www.google.com',
        ]
        for url in servers:
            try:
                req = urllib.request.Request(url, method='HEAD')
                with urllib.request.urlopen(req, timeout=3) as r:
                    date_str = r.headers.get('Date', '')
                    if date_str:
                        server_dt = email.utils.parsedate_to_datetime(date_str)
                        server_utc = server_dt.astimezone(timezone.utc)
                        local_utc  = datetime.now(timezone.utc)
                        self._offset_secs = (server_utc - local_utc).total_seconds()
                        self._last_sync   = time.time()
                        return
            except Exception:
                continue
        self._offset_secs = 0.0
        self._last_sync   = time.time()

    def utc_now(self) -> datetime:
        if time.time() - self._last_sync > self._sync_interval:
            threading.Thread(target=self._sync, daemon=True).start()
        return datetime.now(timezone.utc) + timedelta(seconds=self._offset_secs)

    def is_weekend(self) -> bool:
        now = self.utc_now()
        # Forex market closed: Friday 22:00 UTC → Sunday 22:00 UTC
        wd = now.weekday()  # 0=Mon … 6=Sun
        if wd == 5:   # Saturday all day
            return True
        if wd == 4 and now.hour >= 22:  # Friday after 22:00 UTC
            return True
        if wd == 6 and now.hour < 22:   # Sunday before 22:00 UTC
            return True
        return False

    def minutes_to_open(self) -> int:
        """Minutes until forex market reopens (only meaningful when closed)."""
        now = self.utc_now()
        wd  = now.weekday()
        if wd == 6:
            open_dt = now.replace(hour=22, minute=0, second=0, microsecond=0)
            if now >= open_dt:
                return 0
            return int((open_dt - now).total_seconds() / 60)
        if wd == 5:
            # Sunday 22:00
            days_ahead = (6 - wd) % 7
            open_dt = (now + timedelta(days=days_ahead)).replace(
                hour=22, minute=0, second=0, microsecond=0)
            return int((open_dt - now).total_seconds() / 60)
        return 0

    def active_session(self) -> str:
        """Returns which major session is active."""
        now  = self.utc_now()
        hour = now.hour
        if 22 <= hour or hour < 7:
            return 'Sydney/Tokyo'
        if 7 <= hour < 9:
            return 'Tokyo/London overlap'
        if 9 <= hour < 12:
            return 'London'
        if 12 <= hour < 17:
            return 'London/NewYork overlap'
        if 17 <= hour < 22:
            return 'NewYork'
        return 'Off-peak'

    def is_high_liquidity(self) -> bool:
        """London/NY overlap is highest liquidity — best time to trade."""
        now  = self.utc_now()
        hour = now.hour
        return 12 <= hour < 17 or 9 <= hour < 12

    def symbol_is_tradeable(self, symbol: str) -> bool:
        """Per-symbol session check."""
        if self.is_weekend():
            return False
        now  = self.utc_now()
        hour = now.hour
        # JPY pairs thin outside Asia/London
        if 'JPY' in symbol and not (0 <= hour < 17):
            return True  # still tradeable, just lower liquidity
        # Gold/commodities follow NY session roughly
        if symbol in ('GOLD', 'XAUUSD', 'WTI', 'SILVER'):
            return 8 <= hour < 22
        return True

    def close_positions_warning(self) -> bool:
        """True in the 30 min window before weekend close (Fri 21:30 UTC)."""
        now = self.utc_now()
        return now.weekday() == 4 and now.hour == 21 and now.minute >= 30
