import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class PortfolioDB:
    def __init__(self, db_path=None):
        self.supabase: Client = None
        try:
            supabase_url = os.environ.get("SUPABASE_URL")
            supabase_key = os.environ.get("SUPABASE_KEY")
            if supabase_url and supabase_key:
                self.supabase = create_client(supabase_url, supabase_key)
            else:
                logger.warning("SUPABASE_URL or SUPABASE_KEY is missing. PortfolioDB will fail.")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client for PortfolioDB: {e}")

    def get_or_create_user(self, user_id: int) -> float:
        """取得使用者的現金餘額，如果不存在則建立一個預設 100 萬餘額的帳戶"""
        if not self.supabase: return 1000000.0
        try:
            response = self.supabase.table('users').select('balance').eq('user_id', user_id).execute()
            if response.data:
                return float(response.data[0]['balance'])
            else:
                self.supabase.table('users').insert({'user_id': user_id, 'balance': 1000000.0}).execute()
                return 1000000.0
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {e}")
            return 1000000.0

    def update_balance(self, user_id: int, new_balance: float):
        if not self.supabase: return
        try:
            self.supabase.table('users').update({'balance': float(new_balance)}).eq('user_id', user_id).execute()
        except Exception as e:
            logger.error(f"Error updating balance: {e}")

    def record_trade(self, user_id: int, ticker: str, action: str, price: float, quantity: int):
        if not self.supabase: return
        try:
            data = {
                'user_id': user_id,
                'ticker': ticker,
                'action': action,
                'price': float(price),
                'quantity': quantity
            }
            self.supabase.table('trades').insert(data).execute()
        except Exception as e:
            logger.error(f"Error recording trade: {e}")

    def get_holding(self, user_id: int, ticker: str):
        """回傳 (quantity, avg_price)，如果沒有持股回傳 (0, 0.0)"""
        if not self.supabase: return (0, 0.0)
        try:
            response = self.supabase.table('holdings').select('quantity, avg_price').eq('user_id', user_id).eq('ticker', ticker).execute()
            if response.data:
                return (int(response.data[0]['quantity']), float(response.data[0]['avg_price']))
            return (0, 0.0)
        except Exception as e:
            logger.error(f"Error getting holding: {e}")
            return (0, 0.0)

    def update_holding(self, user_id: int, ticker: str, quantity: int, avg_price: float):
        if not self.supabase: return
        try:
            if quantity == 0:
                self.supabase.table('holdings').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            else:
                # Upsert relies on a unique constraint on (user_id, ticker)
                data = {
                    'user_id': user_id,
                    'ticker': ticker,
                    'quantity': quantity,
                    'avg_price': float(avg_price)
                }
                # Check if exists to do update or insert (if ON CONFLICT is not fully supported by REST upsert without specifying column)
                existing = self.supabase.table('holdings').select('id').eq('user_id', user_id).eq('ticker', ticker).execute()
                if existing.data:
                    self.supabase.table('holdings').update({
                        'quantity': quantity,
                        'avg_price': float(avg_price)
                    }).eq('id', existing.data[0]['id']).execute()
                else:
                    self.supabase.table('holdings').insert(data).execute()
        except Exception as e:
            logger.error(f"Error updating holding: {e}")

    def get_all_holdings(self, user_id: int):
        """取得某位使用者的所有持股"""
        if not self.supabase: return []
        try:
            response = self.supabase.table('holdings').select('ticker, quantity, avg_price').eq('user_id', user_id).execute()
            return [(row['ticker'], int(row['quantity']), float(row['avg_price'])) for row in response.data]
        except Exception as e:
            logger.error(f"Error getting all holdings: {e}")
            return []
