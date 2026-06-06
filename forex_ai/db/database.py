import sqlite3
import threading
from datetime import datetime

class Database:
    def __init__(self, path='db/forex_ai.db'):
        self.path = path
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                pair TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                size REAL,
                pnl REAL,
                confidence REAL,
                reason TEXT
            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS market_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                pair TEXT,
                feature_snapshot TEXT,
                prediction REAL,
                error REAL,
                confidence REAL
            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                category TEXT,
                message TEXT
            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
            conn.commit()
            conn.close()

    def insert_trade(self, pair, direction, entry_price, exit_price, size, pnl, confidence, reason='strategy'):
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO trades (timestamp, pair, direction, entry_price, exit_price, size, pnl, confidence, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (datetime.now().isoformat(), pair, direction, entry_price, exit_price, size, pnl, confidence, reason)
            )
            conn.commit()
            conn.close()

    def insert_market_event(self, pair, feature_snapshot, prediction, error, confidence):
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO market_events (timestamp, pair, feature_snapshot, prediction, error, confidence) VALUES (?, ?, ?, ?, ?, ?)',
                (datetime.now().isoformat(), pair, str(feature_snapshot), prediction, error, confidence)
            )
            conn.commit()
            conn.close()

    def insert_log(self, category, message):
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO system_logs (timestamp, category, message) VALUES (?, ?, ?)',
                (datetime.now().isoformat(), category, message)
            )
            conn.commit()
            conn.close()

    def get_recent_trades(self, limit=50):
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp, pair, direction, entry_price, exit_price, size, pnl, confidence, reason FROM trades ORDER BY id DESC LIMIT ?', (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    'timestamp': row[0],
                    'pair': row[1],
                    'direction': row[2],
                    'entry_price': row[3],
                    'exit_price': row[4],
                    'size': row[5],
                    'pnl': row[6],
                    'confidence': row[7],
                    'reason': row[8]
                }
                for row in rows
            ]

    def get_recent_logs(self, limit=100):
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp, category, message FROM system_logs ORDER BY id DESC LIMIT ?', (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [
                {'timestamp': row[0], 'category': row[1], 'message': row[2]}
                for row in rows
            ]
