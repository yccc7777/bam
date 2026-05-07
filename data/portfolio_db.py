import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class PortfolioDB:
    def __init__(self, db_path=None):
        if db_path is None:
            # 預設儲存在 data 目錄下
            db_path = os.path.join(os.path.dirname(__file__), 'portfolio.db')
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 建立 User 表格：記錄每個使用者的虛擬本金
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Users (
                    user_id INTEGER PRIMARY KEY,
                    balance REAL DEFAULT 1000000.0
                )
            ''')
            # 建立 Holdings 表格：記錄庫存
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    quantity INTEGER,
                    avg_price REAL,
                    UNIQUE(user_id, ticker),
                    FOREIGN KEY (user_id) REFERENCES Users(user_id)
                )
            ''')
            # 建立 Trades 表格：記錄交易歷史
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    action TEXT,
                    price REAL,
                    quantity INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES Users(user_id)
                )
            ''')
            conn.commit()

    def get_or_create_user(self, user_id: int) -> float:
        """取得使用者的現金餘額，如果不存在則建立一個預設 100 萬餘額的帳戶"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM Users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return row[0]
            else:
                cursor.execute('INSERT INTO Users (user_id, balance) VALUES (?, ?)', (user_id, 1000000.0))
                conn.commit()
                return 1000000.0

    def update_balance(self, user_id: int, new_balance: float):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE Users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
            conn.commit()

    def record_trade(self, user_id: int, ticker: str, action: str, price: float, quantity: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO Trades (user_id, ticker, action, price, quantity) VALUES (?, ?, ?, ?, ?)',
                (user_id, ticker, action, price, quantity)
            )
            conn.commit()

    def get_holding(self, user_id: int, ticker: str):
        """回傳 (quantity, avg_price)，如果沒有持股回傳 (0, 0.0)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT quantity, avg_price FROM Holdings WHERE user_id = ? AND ticker = ?', (user_id, ticker))
            row = cursor.fetchone()
            return row if row else (0, 0.0)

    def update_holding(self, user_id: int, ticker: str, quantity: int, avg_price: float):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if quantity == 0:
                cursor.execute('DELETE FROM Holdings WHERE user_id = ? AND ticker = ?', (user_id, ticker))
            else:
                cursor.execute('''
                    INSERT INTO Holdings (user_id, ticker, quantity, avg_price) 
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, ticker) DO UPDATE SET 
                        quantity = excluded.quantity,
                        avg_price = excluded.avg_price
                ''', (user_id, ticker, quantity, avg_price))
            conn.commit()

    def get_all_holdings(self, user_id: int):
        """取得某位使用者的所有持股"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT ticker, quantity, avg_price FROM Holdings WHERE user_id = ?', (user_id,))
            return cursor.fetchall()
