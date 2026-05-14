import os
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta

# Ensure correct import paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TW50_TICKERS, FORECAST_WINDOWS
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from models.ml_model import MLModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_training_pipeline():
    """
    Standalone pipeline to fetch data, process it, train ML models, and save weights.
    Designed to be run via GitHub Actions.
    """
    logger.info("Starting MLOps Training Pipeline...")
    
    fetcher = DataFetcher()
    processor = DataProcessor()
    
    # Initialize the model engine
    model_engine = MLModel(target_windows=list(FORECAST_WINDOWS.keys()), model_dir="weights")
    
    # Determine date range (e.g. last 5 years)
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(years=5)
    
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    logger.info(f"Fetching market data from {start_date_str} to {end_date_str}")
    
    # We train models globally, but wait! The current ml_model is designed to train on ALL available data together, 
    # or on a per-ticker basis. We'll train a global model by concatenating all ticker data to make it robust.
    
    # Fetch all TW50 data at once
    df_raw = fetcher.fetch_yahoo_finance_data(TW50_TICKERS, start_date_str, end_date_str)
    
    if df_raw.empty:
        logger.error("Failed to fetch data from Yahoo Finance. Aborting training.")
        return
        
    all_train_data = []
    
    # Process each ticker and accumulate
    for ticker in TW50_TICKERS:
        df_ticker = pd.DataFrame()
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if (col, ticker) in df_raw.columns:
                df_ticker[col] = df_raw[(col, ticker)]
            elif col in df_raw.columns: # fallback if single ticker or flat columns
                df_ticker[col] = df_raw[col]
                
        if len(df_ticker) < 100:
            continue
            
        # Process technical indicators and targets
        df_processed = processor.process_stock_data(df_ticker, FORECAST_WINDOWS)
        train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
        
        if not train_data.empty:
            all_train_data.append(train_data)
            
    if not all_train_data:
        logger.error("No valid data for training after processing. Aborting.")
        return
        
    # Concatenate all tickers' data into one giant dataset for robust Global model training
    global_train_data = pd.concat(all_train_data, ignore_index=True)
    logger.info(f"Total training samples across TW50: {len(global_train_data)}")
    
    # Train the Global model
    model_engine.train(global_train_data, ticker="GLOBAL")
    
    # Save the weights to disk
    model_engine.save_weights(ticker="GLOBAL")
    
    logger.info("MLOps Training Pipeline Completed Successfully! Weights saved to weights/ directory.")

if __name__ == "__main__":
    run_training_pipeline()
