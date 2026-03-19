import pandas as pd
from config.settings import FORECAST_WINDOWS
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from models.ml_model import MLModel

def predict_stock(ticker="2330.TW"):
    fetcher = DataFetcher()
    processor = DataProcessor()
    
    print(f"Fetching data for {ticker}...")
    df_raw = fetcher.fetch_yahoo_finance_data([ticker], "2023-01-01", pd.Timestamp.now().strftime("%Y-%m-%d"))
    
    df_ticker = pd.DataFrame()
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if (col, ticker) in df_raw.columns:
            df_ticker[col] = df_raw[(col, ticker)]
        elif col in df_raw.columns:
            df_ticker[col] = df_raw[col]
            
    current_price = df_ticker['Close'].iloc[-1]
    if isinstance(current_price, pd.Series):
        current_price = current_price.iloc[0]
        
    df_processed = processor.process_stock_data(df_ticker, FORECAST_WINDOWS)
    train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
    
    model = MLModel(list(FORECAST_WINDOWS.keys()))
    model.train(train_data)
    preds = model.predict(train_data)
    
    print(f"\n--- {ticker} Prediction ---")
    print(f"Current Price (as of latest close): {current_price:.2f}")
    
    # 3/27 is ~1 week away (1W forecast)
    # 4/2 is ~2 weeks away (2W forecast)
    pred_1w = preds.get('1W', 0)
    pred_2w = preds.get('2W', 0)
    
    if hasattr(pred_1w, 'item'): pred_1w = pred_1w.item()
    if hasattr(pred_2w, 'item'): pred_2w = pred_2w.item()
    else: 
        pred_1w = float(pred_1w)
        pred_2w = float(pred_2w)
        
    price_1w = current_price * (1 + pred_1w)
    price_2w = current_price * (1 + pred_2w)
    
    print(f"1W Expected Return (~03/26): {pred_1w*100:+.2f}% -> Expected Price: {price_1w:.2f}")
    print(f"2W Expected Return (~04/02): {pred_2w*100:+.2f}% -> Expected Price: {price_2w:.2f}")
    print("---------------------------\n")

if __name__ == "__main__":
    predict_stock("2330.TW")
