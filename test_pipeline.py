import pandas as pd
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from models.ml_model import MLModel
from config.settings import FORECAST_WINDOWS

fetcher = DataFetcher()
processor = DataProcessor()
model = MLModel(list(FORECAST_WINDOWS.keys()))

tickers = ["2330.TW"]
data = fetcher.fetch_yahoo_finance_data(tickers, "2023-01-01", "2024-05-01")
print(data.columns)
