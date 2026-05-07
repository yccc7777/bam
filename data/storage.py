import json
import os
import logging

logger = logging.getLogger(__name__)

SUBSCRIBERS_FILE = 'data/subscribers.json'
DAILY_STATE_FILE = 'data/daily_state.json'

def load_json(filepath, default):
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return default

def save_json(filepath, data):
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving {filepath}: {e}")

class StorageHelper:
    @staticmethod
    def get_subscribers() -> list:
        return load_json(SUBSCRIBERS_FILE, [])

    @staticmethod
    def add_subscriber(chat_id: int):
        subs = StorageHelper.get_subscribers()
        if chat_id not in subs:
            subs.append(chat_id)
            save_json(SUBSCRIBERS_FILE, subs)

    @staticmethod
    def remove_subscriber(chat_id: int):
        subs = StorageHelper.get_subscribers()
        if chat_id in subs:
            subs.remove(chat_id)
            save_json(SUBSCRIBERS_FILE, subs)

    @staticmethod
    def save_daily_state(date_str: str, ticker: str, predictions: dict, pm_view: str, current_price: float):
        data = load_json(DAILY_STATE_FILE, {})
        data[date_str] = {
            "ticker": ticker,
            "predictions": predictions,
            "pm_view": pm_view,
            "morning_price": current_price
        }
        save_json(DAILY_STATE_FILE, data)

    @staticmethod
    def get_daily_state(date_str: str):
        data = load_json(DAILY_STATE_FILE, {})
        return data.get(date_str)

    @staticmethod
    def set_tomorrow_target(ticker: str):
        data = load_json(DAILY_STATE_FILE, {})
        data["tomorrow_target"] = ticker
        save_json(DAILY_STATE_FILE, data)

    @staticmethod
    def get_tomorrow_target() -> str:
        data = load_json(DAILY_STATE_FILE, {})
        return data.get("tomorrow_target")
