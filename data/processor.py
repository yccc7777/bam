import pandas as pd
import numpy as np

class DataProcessor:
    def __init__(self):
        pass

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators (MA, RSI, MACD).
        df should have 'Close' column.
        """
        if 'Close' not in df.columns:
            return df
            
        close = df['Close']
        
        # Moving Averages
        df['MA_5'] = close.rolling(window=5).mean()
        df['MA_20'] = close.rolling(window=20).mean()
        df['MA_60'] = close.rolling(window=60).mean()
        
        # RSI (Relative Strength Index)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))
        
        # MACD (Moving Average Convergence Divergence)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_12 - ema_26
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        return df

    def calculate_future_returns(self, df: pd.DataFrame, windows: dict) -> pd.DataFrame:
        """
        Calculate future returns for target prediction (1W, 2W, 1M, 3M)
        windows: dictionary mapping label to trading days (e.g., {"1W": 5})
        """
        if 'Close' not in df.columns:
            return df
            
        for label, days in windows.items():
            # Shift backwards to get future price.
            # E.g., label="1W" days=5, future_return = (Close[t+5] - Close[t]) / Close[t]
            future_price = df['Close'].shift(-days)
            df[f'Target_Ret_{label}'] = (future_price - df['Close']) / df['Close']
            
        return df

    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values using forward fill, then backward fill for the start.
        """
        return df.ffill().bfill()

    def process_stock_data(self, df: pd.DataFrame, target_windows: dict) -> pd.DataFrame:
        """
        Run the complete processing pipeline for a single stock.
        """
        # Ensure index is datetime
        df.index = pd.to_datetime(df.index)
        
        # Fill missing before calculating indicators
        df = self.handle_missing_values(df)
        
        # Technical indicators
        df = self.calculate_technical_indicators(df)
        
        # Future returns (Targets)
        df = self.calculate_future_returns(df, target_windows)
        
        return df
