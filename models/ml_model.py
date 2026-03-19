import pandas as pd
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error
import logging

logger = logging.getLogger(__name__)

class MLModel:
    def __init__(self, target_windows: list):
        """
        Initialize the MLModel with the target prediction windows.
        target_windows e.g., ['1W', '2W', '1M', '3M']
        """
        self.models = {}
        self.target_windows = target_windows
        self.features = ['Open', 'High', 'Low', 'Close', 'Volume', 'MA_5', 'MA_20', 'MA_60', 'RSI_14', 'MACD', 'Signal_Line']
        
        # Initialize a model for each target
        for tw in target_windows:
            self.models[tw] = HistGradientBoostingRegressor(
                max_iter=100, 
                learning_rate=0.1, 
                max_depth=5, 
                random_state=42
            )

    def train(self, data: pd.DataFrame):
        """
        Train models on the provided dataset. The data DataFrame should contain
        features and the target columns ('Target_Ret_{window}').
        """
        # Ensure only rows with no NaNs in features and targets are used
        train_data = data.dropna(subset=self.features + [f'Target_Ret_{tw}' for tw in self.target_windows])
        
        if train_data.empty:
            logger.warning("No valid training data after dropping NaNs.")
            return

        X = train_data[self.features]
        
        for tw in self.target_windows:
            y = train_data[f'Target_Ret_{tw}']
            logger.info(f"Training model for {tw} window on {len(X)} samples...")
            self.models[tw].fit(X, y)
            
            # Brief training evaluation (in-sample)
            preds = self.models[tw].predict(X)
            mse = mean_squared_error(y, preds)
            logger.info(f"Training MSE for {tw}: {mse:.6f}")

    def predict(self, recent_data: pd.DataFrame) -> dict:
        """
        Predict future returns based on the most recent data row.
        recent_data should be a DataFrame containing the features for the latest date.
        Returns a dictionary mapping window -> predicted return.
        """
        predictions = {}
        
        # Get the latest valid row data
        latest_row = recent_data.iloc[-1:]
        X_latest = latest_row[self.features]
        
        for tw in self.target_windows:
            pred = self.models[tw].predict(X_latest)[0]
            predictions[tw] = pred
            
        return predictions

    def get_feature_importances(self, window: str):
        """
        Return the feature importances (mocked or skipped for HistGradientBoostingRegressor).
        """
        return {}
