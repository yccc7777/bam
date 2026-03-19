import os
from dotenv import load_dotenv

load_dotenv()# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Google Gemini Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Model Training Parameters
TRAIN_START_DATE = "2022-01-01"
TRAIN_END_DATE = "2025-12-31"

# Trading Cost (0.1425% fee, 0.3% tax)
TRANSACTION_FEE = 0.001425
TRANSACTION_TAX = 0.003

# Top N Stocks for /top command
TOP_N_STOCKS = 5

# Taiwan 50 (0050.TW) Constituent Stock Tickers (Can be updated dynamically or statically)
# Hardcoding some major tickers for prototype purposes, but this should be fetched or updated periodically.
TW50_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", 
    "2882.TW", "1303.TW", "2891.TW", "2382.TW", "1301.TW",
    "2886.TW", "1216.TW", "2002.TW", "2884.TW", "2892.TW",
    "2303.TW", "2885.TW", "5871.TW", "1326.TW", "2357.TW",
    # We will implement logic to dynamically fetch the other tickers or read from a CSV.
]

# Forecast Window Options (in trading days)
FORECAST_WINDOWS = {
    "1W": 5,    # 1 Week (5 trading days)
    "2W": 10,   # 2 Weeks (10 trading days)
    "3W": 15,   # 3 Weeks (15 trading days)
    "1M": 21,   # 1 Month (21 trading days)
    "3M": 63    # 3 Months (63 trading days)
}
