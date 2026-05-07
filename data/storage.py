import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Initialize Supabase client globally
supabase: Client = None
try:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
    else:
        logger.warning("SUPABASE_URL or SUPABASE_KEY is missing. Cloud storage will fail.")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")

class StorageHelper:
    @staticmethod
    def get_subscribers() -> list:
        if not supabase: return []
        try:
            response = supabase.table('subscribers').select('chat_id').execute()
            return [row['chat_id'] for row in response.data]
        except Exception as e:
            logger.error(f"Error getting subscribers from Supabase: {e}")
            return []

    @staticmethod
    def add_subscriber(chat_id: int):
        if not supabase: return
        try:
            supabase.table('subscribers').upsert({'chat_id': chat_id}).execute()
        except Exception as e:
            logger.error(f"Error adding subscriber {chat_id}: {e}")

    @staticmethod
    def remove_subscriber(chat_id: int):
        if not supabase: return
        try:
            supabase.table('subscribers').delete().eq('chat_id', chat_id).execute()
        except Exception as e:
            logger.error(f"Error removing subscriber {chat_id}: {e}")

    @staticmethod
    def save_daily_state(date_str: str, ticker: str, predictions: dict, pm_view: str, current_price: float):
        if not supabase: return
        try:
            data = {
                "date_str": date_str,
                "ticker": ticker,
                "predictions": predictions,
                "pm_view": pm_view,
                "morning_price": float(current_price)
            }
            supabase.table('daily_states').upsert(data).execute()
        except Exception as e:
            logger.error(f"Error saving daily state for {date_str}: {e}")

    @staticmethod
    def get_daily_state(date_str: str):
        if not supabase: return None
        try:
            response = supabase.table('daily_states').select('*').eq('date_str', date_str).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting daily state for {date_str}: {e}")
            return None

    @staticmethod
    def set_tomorrow_target(ticker: str):
        if not supabase: return
        try:
            data = {
                "date_str": "tomorrow_target",
                "ticker": ticker
            }
            supabase.table('daily_states').upsert(data).execute()
        except Exception as e:
            logger.error(f"Error saving tomorrow target: {e}")

    @staticmethod
    def get_tomorrow_target() -> str:
        if not supabase: return None
        try:
            response = supabase.table('daily_states').select('ticker').eq('date_str', 'tomorrow_target').execute()
            if response.data:
                return response.data[0].get('ticker')
            return None
        except Exception as e:
            logger.error(f"Error getting tomorrow target: {e}")
            return None
