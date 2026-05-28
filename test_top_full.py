import asyncio
import pandas as pd
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from config.settings import TW50_TICKERS, FORECAST_WINDOWS

async def test_top_logic():
    try:
        fetcher = DataFetcher()
        processor = DataProcessor()
        
        scan_tickers = TW50_TICKERS[:10] 
        
        df_raw = fetcher.fetch_yahoo_finance_data(
            scan_tickers, "2023-01-01", pd.Timestamp.now().strftime("%Y-%m-%d")
        )
        print("df_raw empty?", df_raw.empty)
        
        top_stocks_unsorted = []
        for ticker in scan_tickers:
            df_ticker = pd.DataFrame()
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if (col, ticker) in df_raw.columns:
                    df_ticker[col] = df_raw[(col, ticker)]
                elif col in df_raw.columns:
                    df_ticker[col] = df_raw[col]
                    
            if len(df_ticker) < 100: 
                print(f"{ticker} len < 100")
                continue
            
            df_processed = processor.process_stock_data(df_ticker, FORECAST_WINDOWS)
            train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
            if train_data.empty: 
                print(f"{ticker} train_data empty")
                continue
            
            current_price = df_ticker['Close'].iloc[-1]
            if isinstance(current_price, pd.Series):
                current_price = current_price.iloc[0]
            if hasattr(current_price, 'item'):
                current_price = current_price.item()
                
            top_stocks_unsorted.append((ticker, current_price, 0.5))
            print(f"Success for {ticker}")
            
        print("Final unsorted list length:", len(top_stocks_unsorted))
        
    except Exception as e:
        print("Exception:", e)

asyncio.run(test_top_logic())
