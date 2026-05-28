import asyncio
import pandas as pd
from config.settings import FORECAST_WINDOWS, TW50_TICKERS
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from models.ml_model import MLModel

def test():
    print("Starting test...")
    fetcher = DataFetcher()
    processor = DataProcessor()
    ml_model = MLModel(list(FORECAST_WINDOWS.keys()))
    ml_model.load_weights("GLOBAL")
    scan_tickers = TW50_TICKERS[:20] 
    print(f"Fetching data for {scan_tickers}...")
    df_raw = fetcher.fetch_yahoo_finance_data(scan_tickers, "2023-01-01", pd.Timestamp.now().strftime("%Y-%m-%d"))
    print(f"Data fetched: {df_raw.shape}")
    
    top_stocks_unsorted = []
    for ticker in scan_tickers:
        df_ticker = pd.DataFrame()
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if (col, ticker) in df_raw.columns:
                df_ticker[col] = df_raw[(col, ticker)]
            elif col in df_raw.columns:
                df_ticker[col] = df_raw[col]
                
        if len(df_ticker) < 100: continue
        
        df_processed = processor.process_stock_data(df_ticker, FORECAST_WINDOWS)
        train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
        if train_data.empty: continue
        
        preds = ml_model.predict(train_data)
        print(f"Preds for {ticker}: {preds}")

test()
