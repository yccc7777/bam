import pandas as pd
import numpy as np
import os
import logging
from xgboost import XGBClassifier

# Torch imports (wrapped in try-except in case installation fails or for lightweight envs)
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Lightweight LSTM Model Definition
if TORCH_AVAILABLE:
    class SimpleLSTM(nn.Module):
        def __init__(self, input_size, hidden_size=16, num_layers=1):
            super(SimpleLSTM, self).__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
            self.fc = nn.Linear(hidden_size, 1)
            self.sigmoid = nn.Sigmoid()

        def forward(self, x):
            # x shape: (batch, seq_len, input_size)
            h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
            c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
            out, _ = self.lstm(x, (h0, c0))
            out = self.fc(out[:, -1, :]) # Take last time step
            out = self.sigmoid(out)
            return out

class MLModel:
    def __init__(self, target_windows: list, model_dir: str = "weights"):
        """
        Initialize the MLModel with XGBoost and LSTM classifiers.
        target_windows e.g., ['1W', '2W', '1M', '3M']
        """
        self.xgb_models = {}
        self.lstm_models = {}
        self.target_windows = target_windows
        self.features = ['Open', 'High', 'Low', 'Close', 'Volume', 'MA_5', 'MA_20', 'MA_60', 'RSI_14', 'MACD', 'Signal_Line']
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        
        for tw in target_windows:
            self.xgb_models[tw] = XGBClassifier(
                n_estimators=50, # Lightweight to save memory
                learning_rate=0.1, 
                max_depth=4,
                eval_metric='logloss',
                random_state=42
            )
            if TORCH_AVAILABLE:
                self.lstm_models[tw] = SimpleLSTM(input_size=len(self.features))

    def _prepare_lstm_data(self, X_df, y_series=None, seq_length=5):
        """Prepare sequences for LSTM"""
        X_vals = X_df.values
        X_seq = []
        y_seq = []
        
        for i in range(len(X_vals) - seq_length + 1):
            X_seq.append(X_vals[i:i+seq_length])
            if y_series is not None:
                y_seq.append(y_series.iloc[i + seq_length - 1])
                
        if y_series is not None:
            return torch.tensor(np.array(X_seq), dtype=torch.float32), torch.tensor(np.array(y_seq), dtype=torch.float32).unsqueeze(1)
        return torch.tensor(np.array(X_seq), dtype=torch.float32)

    def train(self, data: pd.DataFrame, ticker: str = "GLOBAL"):
        """
        Train XGBoost and LSTM on the provided dataset.
        Converts Target_Ret_X to binary Target_Up_X.
        """
        train_data = data.dropna(subset=self.features + [f'Target_Ret_{tw}' for tw in self.target_windows]).copy()
        
        if train_data.empty or len(train_data) < 10:
            logger.warning("Not enough valid training data.")
            return

        # Normalize features for LSTM
        X_df = train_data[self.features]
        # Simple Min-max scaling
        X_df_norm = (X_df - X_df.min()) / (X_df.max() - X_df.min() + 1e-8)
        
        for tw in self.target_windows:
            # Create Binary Target: 1 if Return > 0 else 0
            y = (train_data[f'Target_Ret_{tw}'] > 0).astype(int)
            logger.info(f"Training models for {tw} window on {len(X_df)} samples...")
            
            # Train XGBoost
            # If all targets are the same class (e.g. all 1s or all 0s), XGBoost will error. Handle this.
            if len(y.unique()) > 1:
                self.xgb_models[tw].fit(X_df, y)
            else:
                logger.warning(f"Only one class present for {tw}. Skipping XGBoost training.")
            
            # Train PyTorch LSTM (Lightweight training loop)
            if TORCH_AVAILABLE:
                X_seq, y_seq = self._prepare_lstm_data(X_df_norm, y, seq_length=5)
                if len(X_seq) > 0:
                    model = self.lstm_models[tw]
                    criterion = nn.BCELoss()
                    optimizer = optim.Adam(model.parameters(), lr=0.01)
                    
                    model.train()
                    # 10 Epochs for fast training
                    for epoch in range(10):
                        optimizer.zero_grad()
                        outputs = model(X_seq)
                        loss = criterion(outputs, y_seq)
                        loss.backward()
                        optimizer.step()

    def predict(self, recent_data: pd.DataFrame) -> dict:
        """
        Predict probability of rising based on the most recent data.
        Returns a dictionary mapping window -> probability (0.0 to 1.0).
        """
        predictions = {}
        if len(recent_data) < 5:
            # Fallback if not enough data
            return {tw: 0.5 for tw in self.target_windows}
            
        latest_row = recent_data.iloc[-1:]
        X_latest = latest_row[self.features]
        
        # Prepare for LSTM
        X_df_norm = (recent_data[self.features] - recent_data[self.features].min()) / (recent_data[self.features].max() - recent_data[self.features].min() + 1e-8)
        
        for tw in self.target_windows:
            # XGBoost Predict Probability
            try:
                # predict_proba returns [[prob_class_0, prob_class_1]]
                xgb_prob = self.xgb_models[tw].predict_proba(X_latest)[0][1]
            except Exception as e:
                logger.warning(f"XGB predict error (maybe untrained): {e}")
                xgb_prob = 0.5
                
            # LSTM Predict Probability
            lstm_prob = xgb_prob # fallback
            if TORCH_AVAILABLE:
                try:
                    X_seq = self._prepare_lstm_data(X_df_norm.iloc[-5:], seq_length=5) # Last 5 days
                    if len(X_seq) > 0:
                        self.lstm_models[tw].eval()
                        with torch.no_grad():
                            lstm_prob = self.lstm_models[tw](X_seq).item()
                except Exception as e:
                    logger.warning(f"LSTM predict error: {e}")
            
            # Ensemble Average Probability
            prob = (xgb_prob + lstm_prob) / 2.0
            predictions[tw] = prob
            
        return predictions

    def save_weights(self, ticker: str = "GLOBAL"):
        """Save models to disk"""
        for tw in self.target_windows:
            xgb_path = os.path.join(self.model_dir, f"{ticker}_xgb_{tw}.json")
            try:
                self.xgb_models[tw].save_model(xgb_path)
            except:
                pass # Model might not be trained
            
            if TORCH_AVAILABLE:
                lstm_path = os.path.join(self.model_dir, f"{ticker}_lstm_{tw}.pth")
                try:
                    torch.save(self.lstm_models[tw].state_dict(), lstm_path)
                except:
                    pass
        logger.info(f"Saved weights for {ticker} in {self.model_dir}")

    def load_weights(self, ticker: str = "GLOBAL") -> bool:
        """Load models from disk if they exist. Returns True if successful."""
        success = True
        for tw in self.target_windows:
            xgb_path = os.path.join(self.model_dir, f"{ticker}_xgb_{tw}.json")
            if os.path.exists(xgb_path):
                self.xgb_models[tw].load_model(xgb_path)
            else:
                success = False
                
            if TORCH_AVAILABLE:
                lstm_path = os.path.join(self.model_dir, f"{ticker}_lstm_{tw}.pth")
                if os.path.exists(lstm_path):
                    self.lstm_models[tw].load_state_dict(torch.load(lstm_path))
                else:
                    success = False
        return success

    def get_feature_importances(self, window: str):
        """Return XGBoost feature importances"""
        try:
            return dict(zip(self.features, self.xgb_models[window].feature_importances_))
        except:
            return {}
