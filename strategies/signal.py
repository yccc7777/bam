import pandas as pd
import logging

logger = logging.getLogger(__name__)

class StrategySignal:
    def __init__(self, stop_loss_pct: float = -0.05, top_n: int = 5):
        self.stop_loss_pct = stop_loss_pct
        self.top_n = top_n

    def generate_buy_signals(self, predictions: dict, institutional_data: dict) -> list:
        """
        Filter stocks based on predictions and institutional data to generate buy signals.
        predictions: {ticker: {'1W': pred_ret, ...}}
        institutional_data: {ticker: sum_buy_sell_last_3_days}
        """
        # Create a dataframe for easier manipulation
        records = []
        for ticker, preds in predictions.items():
            records.append({
                'Ticker': ticker,
                'Pred_1W': preds.get('1W', 0),
                'Inst_Buy_3D': institutional_data.get(ticker, 0)
            })
            
        df = pd.DataFrame(records)
        if df.empty:
            return []
            
        # Condition 1: Expected return > 2.0%
        cond1 = df['Pred_1W'] > 0.02
        
        # Condition 2: Institutional investors net buy > 0 over last 3 days
        cond2 = df['Inst_Buy_3D'] > 0
        
        valid_candidates = df[cond1 & cond2].copy()
        
        # Sort by Pred_1W descending and pick top_n
        top_picks = valid_candidates.sort_values(by='Pred_1W', ascending=False).head(self.top_n)
        return top_picks['Ticker'].tolist()

    def check_sell_signal(self, current_price: float, buy_price: float, pred_1W: float) -> (bool, str):
        """
        Determine if a stock currently held should be sold.
        Return (sell_flag, reason)
        """
        # Condition 1: Stop loss (-5%)
        actual_return = (current_price - buy_price) / buy_price
        if actual_return <= self.stop_loss_pct:
            return True, f"達停損條件 (實際虧損: {actual_return*100:.2f}%)"
            
        # Condition 2: Model outlook turns negative
        if pred_1W < 0:
            return True, f"模型預期報酬轉負 (預期: {pred_1W*100:.2f}%)"
            
        return False, ""
        
    def screen_top_stocks(self, df_predictions: pd.DataFrame) -> pd.DataFrame:
        """
        Screen the overall top N stocks based on predicted 1W return for the /top command.
        df_predictions should have columns: 'Ticker', 'Pred_1W', 'Pred_2W', 'Pred_1M', 'Pred_3M'
        """
        # Filter for positive returns only, then sort
        positive_df = df_predictions[df_predictions['Pred_1W'] > 0]
        top_df = positive_df.sort_values(by='Pred_1W', ascending=False).head(self.top_n)
        return top_df
