import sys
import asyncio
from unittest.mock import MagicMock
import pandas as pd

class MockMLModel:
    def __init__(self, *args, **kwargs): pass
    def train(self, data): pass
    def predict(self, data): return {'1W': 0.65, '1M': 0.6}
sys.modules['models.ml_model'] = MagicMock()
sys.modules['models.ml_model'].MLModel = MockMLModel

from main import _run_premarket_report
import main
import logging

async def run_test():
    print("Testing get_tomorrow_target")
    print(main.StorageHelper.get_tomorrow_target())
    
    print("Testing DataFetcher init")
    fetcher = main.DataFetcher()
    
    print("Testing run_in_executor")
    loop = asyncio.get_event_loop()
    df_raw = await loop.run_in_executor(None, fetcher.fetch_yahoo_finance_data, ["2330.TW"], "2023-01-01", "2026-01-01")
    print("df_raw empty:", df_raw.empty)
    
asyncio.run(run_test())
