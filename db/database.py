import sqlite3
import threading
import json
from datetime import datetime
from pathlib import Path


class Database:
    _local = threading.local()

    def __init__(self, path='db/forex_ai.db'):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_schema(self):
        c = self._conn()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
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
            );
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                level TEXT,
                message TEXT
            );
            CREATE TABLE IF NOT EXISTS market_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                pair TEXT,
                features TEXT,
                prediction REAL,
                error REAL,
                confidence REAL
            );
            CREATE TABLE IF NOT EXISTS equity_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                balance REAL,
                equity REAL,
                open_pnl REAL
            );
        """)
        c.commit()

    def insert_trade(self, pair, direction, entry_price, exit_price, size, pnl, confidence, reason):
        c = self._conn()
        c.execute(
            "INSERT INTO trades (timestamp,pair,direction,entry_price,exit_price,size,pnl,confidence,reason) VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(), pair, direction, entry_price, exit_price, size, pnl, confidence, reason)
        )
        c.commit()

    def insert_log(self, level, message):
        c = self._conn()
        c.execute(
            "INSERT INTO logs (timestamp,level,message) VALUES (?,?,?)",
            (datetime.now().strftime('%H:%M:%S'), level.upper(), message)
        )
        c.commit()

    def insert_market_event(self, pair, feature_snapshot, prediction, error, confidence):
        c = self._conn()
        features_json = json.dumps(feature_snapshot) if isinstance(feature_snapshot, dict) else str(feature_snapshot)
        c.execute(
            "INSERT INTO market_events (timestamp,pair,features,prediction,error,confidence) VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(), pair, features_json, float(prediction), float(error), float(confidence))
        )
        c.commit()

    def insert_equity_point(self, balance, equity, open_pnl):
        c = self._conn()
        c.execute(
            "INSERT INTO equity_curve (timestamp,balance,equity,open_pnl) VALUES (?,?,?,?)",
            (datetime.now().isoformat(), balance, equity, open_pnl)
        )
        c.commit()

    def get_recent_trades(self, limit=100):
        c = self._conn()
        rows = c.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_logs(self, limit=200):
        c = self._conn()
        rows = c.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_equity_curve(self, limit=500):
        c = self._conn()
        rows = c.execute(
            "SELECT * FROM equity_curve ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_trade_summary(self):
        c = self._conn()
        total = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        if total == 0:
            return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0.0,
                    'total_pnl': 0.0, 'avg_win': 0.0, 'avg_loss': 0.0, 'profit_factor': 0.0}
        wins = c.execute("SELECT COUNT(*),SUM(pnl) FROM trades WHERE pnl>0").fetchone()
        losses = c.execute("SELECT COUNT(*),SUM(pnl) FROM trades WHERE pnl<=0").fetchone()
        total_pnl = c.execute("SELECT SUM(pnl) FROM trades").fetchone()[0] or 0.0
        win_count = wins[0] or 0
        loss_count = losses[0] or 0
        gross_win = wins[1] or 0.0
        gross_loss = abs(losses[1] or 0.0)
        return {
            'total': total,
            'wins': win_count,
            'losses': loss_count,
            'win_rate': win_count / total if total else 0.0,
            'total_pnl': float(total_pnl),
            'avg_win': float(gross_win / win_count) if win_count else 0.0,
            'avg_loss': float(gross_loss / loss_count) if loss_count else 0.0,
            'profit_factor': float(gross_win / gross_loss) if gross_loss > 0 else 0.0
        }
