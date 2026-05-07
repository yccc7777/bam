

================================================================================
# 🗂️ 檔案位置 / FILE: ./main.py
================================================================================

import logging
import time
import os
import threading
import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import Conflict

from config.settings import TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, FORECAST_WINDOWS, TW50_TICKERS
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from models.ml_model import MLModel
from models.llm_generator import LLMGenerator
from strategies.signal import StrategySignal

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "👋 歡迎使用 *Project Chronos (時鐘神)* 台股機器人！\n\n"
        "我是你的專屬 AI 量化分析助理。我能預測台灣 50 成分股的各個時間窗格報酬率。\n\n"
        "你可以使用以下指令：\n"
        "🔹 `/top`：獲取預期報酬最高的 5 檔飆股排行。\n"
        "🔹 `/predict <股票代號>`：查詢單一個股的詳細預測（例如：`/predict 2330`）。\n"
        "🔹 `/predict_range <股票代號> <開始日期> <結束日期>`：預測指定日期區間走勢（例如：`/predict_range 2330 03/27 04/02`）。\n"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("⚠️ 請提供股票代號，例如：`/predict 2330`", parse_mode='Markdown')
        return
        
    ticker = context.args[0]
    if not ticker.endswith(".TW"):
        ticker += ".TW"
        
    loading_msg = await update.message.reply_text(f"⏳ [系統運算中] 正在從證交所與 Yahoo Finance 獲取 {ticker} 最新價量資料與訓練模型...")
    
    try:
        fetcher = DataFetcher()
        processor = DataProcessor()
        ml_model = MLModel(list(FORECAST_WINDOWS.keys()))
        llm = LLMGenerator(api_key=GEMINI_API_KEY)
        
        # 1. Fetch real data
        df_raw = fetcher.fetch_yahoo_finance_data([ticker], "2023-01-01", pd.Timestamp.now().strftime("%Y-%m-%d"))
        
        if df_raw.empty:
            raise ValueError(f"無法從 yfinance 獲取 {ticker} 的資料。")

        df_ticker = pd.DataFrame()
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if (col, ticker) in df_raw.columns:
                df_ticker[col] = df_raw[(col, ticker)]
            elif col in df_raw.columns:
                df_ticker[col] = df_raw[col]
                
        if df_ticker.empty or len(df_ticker) < 100:
            raise ValueError(f"資料不足夠訓練模型 (取得 {len(df_ticker)} 筆資料)")
            
        current_price = df_ticker['Close'].iloc[-1]
        if isinstance(current_price, pd.Series):
            current_price = current_price.iloc[0]
        
        # 2. Add features
        df_processed = processor.process_stock_data(df_ticker, FORECAST_WINDOWS)
        train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
        
        if train_data.empty:
            raise ValueError("計算特徵後無有效資料可供訓練。")
            
        # 3. Train & Predict
        ml_model.train(train_data)
        predictions = ml_model.predict(train_data)
        
        # Convert predictions safely
        for k, v in predictions.items():
            if hasattr(v, 'item'):
                predictions[k] = v.item()
            else:
                predictions[k] = float(v)
        
        inst_buy = True 
        is_top_5 = (predictions['1W'] > 0.02)
        
        # 4. Generate narrative
        narrative = llm.generate_narrative(ticker, predictions, is_top_5, inst_buy)
        
        # 5. Format beautiful output
        response_text = (
            f"📊 **{ticker} 即時預測報告**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 **最新收盤價：** ${current_price:.2f}\n\n"
            f"📈 **AI 預期報酬率：**\n"
            f"   • 1 週預期： {predictions.get('1W', 0)*100:+.2f}%\n"
            f"   • 2 週預期： {predictions.get('2W', 0)*100:+.2f}%\n"
            f"   • 3 週預期： {predictions.get('3W', 0)*100:+.2f}%\n"
            f"   • 1 個月預期：{predictions.get('1M', 0)*100:+.2f}%\n"
            f"   • 3 個月預期：{predictions.get('3M', 0)*100:+.2f}%\n\n"
            f"🤖 **AI 綜合短評：**\n"
            f"_{narrative}_\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=loading_msg.message_id,
            text=response_text,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error during prediction: {e}", exc_info=True)
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=loading_msg.message_id,
            text=f"❌ 系統發生錯誤：\n`{str(e)}`",
            parse_mode='Markdown'
        )


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loading_msg = await update.message.reply_text("⏳ [系統運算中] 正在下載市場價量日線資料，並計算特徵值與預期報酬...")
    
    try:
        fetcher = DataFetcher()
        processor = DataProcessor()
        
        # Sample top 10 tickers to save time, picking most popular basically
        scan_tickers = TW50_TICKERS[:10] 
        
        df_raw = fetcher.fetch_yahoo_finance_data(scan_tickers, "2023-01-01", pd.Timestamp.now().strftime("%Y-%m-%d"))
        
        top_stocks_unsorted = []
        for ticker in scan_tickers:
            df_ticker = pd.DataFrame()
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if (col, ticker) in df_raw.columns:
                    df_ticker[col] = df_raw[(col, ticker)]
                elif col in df_raw.columns:
                    df_ticker[col] = df_raw[col]
                    
            if len(df_ticker) < 100: continue
            
            # Process & Train inline
            df_processed = processor.process_stock_data(df_ticker, FORECAST_WINDOWS)
            train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
            if train_data.empty: continue
            
            model = MLModel(list(FORECAST_WINDOWS.keys()))
            model.train(train_data)
            preds = model.predict(train_data)
            
            current_price = df_ticker['Close'].iloc[-1]
            if isinstance(current_price, pd.Series):
                current_price = current_price.iloc[0]
            if hasattr(current_price, 'item'):
                current_price = current_price.item()
                
            pred_1w = preds['1W']
            if hasattr(pred_1w, 'item'):
                pred_1w = pred_1w.item()
            else:
                pred_1w = float(pred_1w)
                
            top_stocks_unsorted.append((ticker, current_price, pred_1w))
            
        # Sort and take top 5
        top_stocks = sorted(top_stocks_unsorted, key=lambda x: x[2], reverse=True)[:5]
        
        response_text = "🏆 **台灣 50 AI即時預測飆股排行 (Top 5)**\n━━━━━━━━━━━━━━━━━━━\n"
        for i, (ticker, price, ret_1w) in enumerate(top_stocks, 1):
            response_text += f"{i}. **{ticker}** | 價: ${price:.2f} | 1週預期: **{ret_1w*100:+.2f}%**\n"
            
        response_text += "━━━━━━━━━━━━━━━━━━━\n💡 _輸入 `/predict <代號>` 可查看單一個股詳細預測。_"
        
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=loading_msg.message_id,
            text=response_text,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error getting top stocks: {e}", exc_info=True)
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=loading_msg.message_id,
            text=f"❌ 系統運算中發生錯誤：\n`{str(e)}`",
            parse_mode='Markdown'
        )

async def predict_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("⚠️ 格式錯誤！請使用：`/predict_range <股票代號> <開始日期> <結束日期>`\n例如：`/predict_range 2330 03/27 04/02`", parse_mode='Markdown')
        return
        
    ticker = context.args[0]
    start_date_str = context.args[1]
    end_date_str = context.args[2]
    
    if not ticker.endswith(".TW"):
        ticker += ".TW"
        
    loading_msg = await update.message.reply_text(f"⏳ [系統運算中] 正在為 {ticker} 分析 {start_date_str} 到 {end_date_str} 的走勢...")
    
    try:
        from data.fetcher import DataFetcher
        from data.processor import DataProcessor
        from models.ml_model import MLModel
        from models.llm_generator import LLMGenerator
        import pandas as pd
        import numpy as np
        from config.settings import FORECAST_WINDOWS, GEMINI_API_KEY
        
        fetcher = DataFetcher()
        processor = DataProcessor()
        ml_model = MLModel(list(FORECAST_WINDOWS.keys()))
        llm = LLMGenerator(api_key=GEMINI_API_KEY)
        
        # Process dates to interpolate
        today = pd.Timestamp.now().normalize()
        try:
            if len(start_date_str.split('/')) == 2:
                start_date_str = f"{today.year}/{start_date_str}"
            elif len(start_date_str.split('-')) == 2:
                start_date_str = f"{today.year}-{start_date_str}"
                
            if len(end_date_str.split('/')) == 2:
                end_date_str = f"{today.year}/{end_date_str}"
            elif len(end_date_str.split('-')) == 2:
                end_date_str = f"{today.year}-{end_date_str}"
                
            start_date = pd.to_datetime(start_date_str)
            end_date = pd.to_datetime(end_date_str)
        except Exception:
            raise ValueError("日期格式錯誤，請使用 MM/DD 或 YYYY-MM-DD (例如 03/27)。")
            
        days_start = (start_date - today).days
        days_end = (end_date - today).days
        
        if days_start < 0 or days_end < 0:
            raise ValueError("預測日期必須在今天之後。")
            
        df_raw = fetcher.fetch_yahoo_finance_data([ticker], "2023-01-01", today.strftime("%Y-%m-%d"))
        if df_raw.empty:
            raise ValueError(f"無法從 yfinance 獲取 {ticker} 的資料。")

        df_ticker = pd.DataFrame()
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if (col, ticker) in df_raw.columns:
                df_ticker[col] = df_raw[(col, ticker)]
            elif col in df_raw.columns:
                df_ticker[col] = df_raw[col]
                
        if df_ticker.empty or len(df_ticker) < 100:
            raise ValueError("資料不足夠訓練模型。")
            
        current_price = df_ticker['Close'].iloc[-1]
        if isinstance(current_price, pd.Series):
            current_price = current_price.iloc[0]
            
        df_processed = processor.process_stock_data(df_ticker, FORECAST_WINDOWS)
        train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
        if train_data.empty:
            raise ValueError("計算特徵後無有效資料可供訓練。")
            
        ml_model.train(train_data)
        predictions = ml_model.predict(train_data)
        
        def convert_pred(v): return v.item() if hasattr(v, 'item') else float(v)
        preds = {k: convert_pred(v) for k, v in predictions.items()}
        
        window_days = {'1W': 7, '2W': 14, '3W': 21, '1M': 30, '3M': 90}
        days_arr = [0] + list(window_days.values())
        returns_arr = [0.0] + [preds.get(k, 0) for k in window_days.keys()]
        
        pred_start = np.interp(days_start, days_arr, returns_arr)
        pred_end = np.interp(days_end, days_arr, returns_arr)
        
        price_start = current_price * (1 + pred_start)
        price_end = current_price * (1 + pred_end)
        
        narrative = llm.generate_range_narrative(ticker, start_date.strftime("%Y/%m/%d"), end_date.strftime("%Y/%m/%d"), pred_start, pred_end)
        
        response_text = (
            f"🎯 **{ticker} 專屬區間預測報告**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 **目前參考價：** ${current_price:.2f}\n\n"
            f"📅 **預估區間：{start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')}**\n"
            f"   • 入場 ({start_date.strftime('%Y/%m/%d')}) 預期估價： **${price_start:.2f}** ({pred_start*100:+.2f}%)\n"
            f"   • 出場 ({end_date.strftime('%Y/%m/%d')}) 預期估價： **${price_end:.2f}** ({pred_end*100:+.2f}%)\n"
            f"   • **波段淨預期報酬率： {(pred_end - pred_start)*100:+.2f}%**\n\n"
            f"🤖 **AI 綜合短評：**\n"
            f"_{narrative}_\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=loading_msg.message_id,
            text=response_text,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error during predict_range: {e}", exc_info=True)
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=loading_msg.message_id,
            text=f"❌ 系統發生錯誤：\n`{str(e)}`",
            parse_mode='Markdown'
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # 這裡專門處理 Conflict 錯誤
    if isinstance(context.error, Conflict):
        logger.error("\n" + "!"*60)
        logger.error("⚠️  [偵測到 Token 衝突 (Conflict)]")
        logger.error("原因：另一個程式正在使用同一個 Bot Token。")
        logger.error("解決建議：")
        logger.error("  1. 檢查你的本地電腦是否也正在執行 `python main.py`？如果是，請按 Ctrl+C 關閉。")
        logger.error("  2. 檢查 Render 是否有多個實體正在跑 (Instances > 1)？")
        logger.error("  3. 建議向 @BotFather 申請測試用 Token 並在 .env 中區分環境。")
        logger.error("!"*60 + "\n")
    else:
        logger.error(f"發生未預期錯誤: {context.error}", exc_info=context.error)

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token":
        logger.error("TELEGRAM_BOT_TOKEN is missing or not configured correctly in .env!")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    predict_handler = CommandHandler('predict', predict)
    top_handler = CommandHandler('top', top)
    predict_range_handler = CommandHandler('predict_range', predict_range)
    
    application.add_handler(start_handler)
    application.add_handler(predict_handler)
    application.add_handler(top_handler)
    application.add_handler(predict_range_handler)
    
    # 註冊全域錯誤處理器
    application.add_error_handler(error_handler)
    
    logger.info("Project Chronos Telegram Bot is starting...")
    
    # --- 根據環境決定要用 Webhook 還是 Polling ---
    # 如果有 RENDER_EXTERNAL_URL 環境變量，表示我們部署在 Render 上，啟用 Webhook
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    port = int(os.environ.get("PORT", 8080))
    
    try:
        if render_url:
            logger.info(f"Running on Render with Webhook URL: {render_url}")
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=render_url,
                drop_pending_updates=True
            )
        else:
            logger.info("Running locally with Long Polling")
            application.run_polling(drop_pending_updates=True)
            
    except Exception as e:
        if "Conflict" in str(e):
            logger.error("\n" + "!"*60)
            logger.error("⚠️  [偵測到 Token 衝突 (Conflict)]")
            logger.error("原因：另一個程式正在使用同一個 Bot Token。")
            logger.error("解決建議：")
            logger.error("  1. 檢查你的本地電腦是否也正在執行 `python main.py`？如果是，請按 Ctrl+C 關閉。")
            logger.error("  2. 檢查 Render 是否有多個實體正在跑 (Instances > 1)？")
            logger.error("  3. 建議向 @BotFather 申請測試用 Token 並在 .env 中區分環境。")
            logger.error("!"*60 + "\n")
        else:
            logger.error(f"機器人啟動發生非預期錯誤: {e}")

if __name__ == '__main__':
    main()



================================================================================
# 🗂️ 檔案位置 / FILE: data/__init__.py
================================================================================




================================================================================
# 🗂️ 檔案位置 / FILE: data/fetcher.py
================================================================================

import yfinance as yf
import requests
import pandas as pd
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self):
        # TWSE API Endpoint for institutional investors trading (三大法人買賣超)
        self.twse_api_url = "https://www.twse.com.tw/fund/T86?response=json&selectType=ALL&date={date}"

    def fetch_yahoo_finance_data(self, tickers: list, start_date: str, end_date: str) -> dict:
        """
        Fetch OHLCV data for given tickers and the market index (^TWII).
        """
        logger.info(f"Fetching Yahoo Finance data for {len(tickers)} tickers and ^TWII...")
        
        # Append Taiwan Weighted Index to the list of tickers to fetch
        all_tickers = tickers + ["^TWII"]
        
        # yfinance download
        try:
            data = yf.download(all_tickers, start=start_date, end=end_date)
            return data
        except Exception as e:
            logger.error(f"Error fetching data from Yahoo Finance: {e}")
            return pd.DataFrame()

    def fetch_twse_institutional_data(self, date_str: str, max_retries=3) -> pd.DataFrame:
        """
        Fetch Institutional Investors trading data from TWSE.
        date_str format: YYYYMMDD (e.g. 20231005)
        """
        url = self.twse_api_url.format(date=date_str)
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('stat') == 'OK':
                        # Convert to DataFrame
                        columns = data['fields']
                        records = data['data']
                        df = pd.DataFrame(records, columns=columns)
                        return df
                    else:
                        logger.warning(f"TWSE API returned non-OK status for date {date_str}: {data.get('stat')}")
                        return pd.DataFrame()
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Error fetching TWSE data: {e}")
                time.sleep(2)  # Delay between retries
                
        logger.error(f"Failed to fetch TWSE data after {max_retries} attempts.")
        return pd.DataFrame()
    
    def fetch_historical_twse_data(self, start_date: str, end_date: str) -> dict:
        """
        Fetch multiple days of TWSE data (Be careful with rate limits).
        Returns a dictionary mapping dates to DataFrames.
        """
        logger.info(f"Fetching TWSE data from {start_date} to {end_date}...")
        dates = pd.date_range(start=start_date, end=end_date, freq='B') # Business days
        results = {}
        for d in dates:
            date_str = d.strftime("%Y%m%d")
            df = self.fetch_twse_institutional_data(date_str)
            if not df.empty:
                results[d.strftime("%Y-%m-%d")] = df
            time.sleep(3) # Politeness delay to avoid IP ban
        return results



================================================================================
# 🗂️ 檔案位置 / FILE: data/processor.py
================================================================================

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



================================================================================
# 🗂️ 檔案位置 / FILE: models/__init__.py
================================================================================




================================================================================
# 🗂️ 檔案位置 / FILE: models/llm_generator.py
================================================================================

import google.generativeai as genai
import logging
import os

logger = logging.getLogger(__name__)

class LLMGenerator:
    def __init__(self, api_key: str):
        if not api_key:
            logger.warning("Gemini API key is not set. Will fall back to rule-based generation.")
            self.use_llm = False
        else:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                self.use_llm = True
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.use_llm = False

    def generate_narrative(self, ticker: str, predictions: dict, top_5: bool, institutional_buy: bool) -> str:
        """
        Generate a human-readable summary combining ML predictions and institutional data.
        Falls back to rule-based generation if LLM fails or is unconfigured.
        """
        if self.use_llm:
            try:
                return self._generate_with_gemini(ticker, predictions, top_5, institutional_buy)
            except Exception as e:
                logger.error(f"LLM Generation failed: {e}. Falling back to rules.")
        
        return self._generate_with_rules(ticker, predictions, top_5, institutional_buy)

    def _generate_with_gemini(self, ticker: str, predictions: dict, top_5: bool, institutional_buy: bool) -> str:
        prompt = f"""
        你是台灣股市的資深量化分析師。請用繁體中文，針對股票 {ticker} 寫一段專業、簡潔 (約50字以內) 且易讀的投資建議評語。
        目前 AI 模型的預測數據為：
        - 未來1週預期報酬：{predictions.get('1W', 0) * 100:.2f}%
        - 未來2週預期報酬：{predictions.get('2W', 0) * 100:.2f}%
        - 是否排名全體前五大看漲標的：{'是' if top_5 else '否'}
        - 近3日三大法人籌碼狀態：{'買超(看多)' if institutional_buy else '賣超/無動作(中性或看空)'}
        
        請直接給出綜合評語，不需問候語，並依照上述數據指出這檔股票是否具有強勢動能。
        """
        response = self.model.generate_content(prompt)
        text = response.text.strip()
        return text

    def _generate_with_rules(self, ticker: str, predictions: dict, top_5: bool, institutional_buy: bool) -> str:
        pred_1w = predictions.get('1W', 0) * 100
        
        parts = []
        if pred_1w >= 2.0:
            parts.append(f"未來一週預期報酬達 +{pred_1w:.2f}%，表現強勢。")
        elif pred_1w < 0:
            parts.append(f"未來一週預期報酬為 {pred_1w:.2f}%，具下行風險。")
        else:
            parts.append(f"未來一週預期報酬為 +{pred_1w:.2f}%，處於盤整。")
            
        if institutional_buy:
            parts.append("且三大法人近期呈現連買，籌碼面動能穩健。")
        else:
            parts.append("惟三大法人未顯著買超，建議保守觀望。")
            
        if top_5:
            parts.append("目前為系統精選的前五大飆股潛力標的。")
            
        return " ".join(parts)

    def generate_range_narrative(self, ticker: str, start_date: str, end_date: str, pred_start: float, pred_end: float) -> str:
        """
        Generate a human-readable summary specifically for the requested date range.
        """
        if self.use_llm:
            try:
                prompt = f"""
                你是台灣股市的資深量化分析師。請用繁體中文，針對股票 {ticker} 寫一段專業、簡潔且易讀的投資建議評語 (約50字內)。
                目前 AI 模型預測該股票在您指定的期間表現如下：
                - {start_date} 預期累積報酬率為：{pred_start * 100:.2f}%
                - {end_date} 預期累積報酬率為：{pred_end * 100:.2f}%
                
                請直接給出綜合評語，不需問候語，並指出這段期間（{start_date} 到 {end_date}）該股票的動能趨勢與投資建議。
                """
                response = self.model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                logger.error(f"LLM Generation failed for date range: {e}. Falling back to rules.")
        
        # Rule-based fallback
        trend = "呈現上漲趨勢" if pred_end > pred_start else "呈現下跌趨勢"
        return f"根據模型預測，從 {start_date} 到 {end_date} 股票預期報酬將從 {pred_start*100:.2f}% 變動至 {pred_end*100:.2f}%，整體{trend}，建議投資人謹慎評估進場時機。"



================================================================================
# 🗂️ 檔案位置 / FILE: models/ml_model.py
================================================================================

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



================================================================================
# 🗂️ 檔案位置 / FILE: strategies/__init__.py
================================================================================




================================================================================
# 🗂️ 檔案位置 / FILE: strategies/signal.py
================================================================================

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



================================================================================
# 🗂️ 檔案位置 / FILE: backtest/__init__.py
================================================================================




================================================================================
# 🗂️ 檔案位置 / FILE: backtest/evaluator.py
================================================================================

import yfinance as yf
import pandas as pd
import numpy as np
import logging

from config.settings import TRANSACTION_FEE, TRANSACTION_TAX

logger = logging.getLogger(__name__)

class BacktestEvaluator:
    def __init__(self, start_date: str = "2022-01-01", end_date: str = "2025-12-31"):
        self.start_date = start_date
        self.end_date = end_date
        self.tx_cost = TRANSACTION_FEE + TRANSACTION_TAX
        
    def fetch_benchmark(self) -> pd.DataFrame:
        """
        Fetch 0050.TW (Taiwan 50 ETF) as the benchmark for buy-and-hold strategy
        """
        logger.info(f"Fetching 0050.TW as benchmark from {self.start_date} to {self.end_date}...")
        try:
            benchmark = yf.download("0050.TW", start=self.start_date, end=self.end_date)
            
            # Buy and hold return calculation
            if not benchmark.empty:
                initial_price = benchmark['Close'].iloc[0].item() if hasattr(benchmark['Close'].iloc[0], 'item') else float(benchmark['Close'].iloc[0])
                final_price = benchmark['Close'].iloc[-1].item() if hasattr(benchmark['Close'].iloc[-1], 'item') else float(benchmark['Close'].iloc[-1])
                
                total_return = (final_price - initial_price) / initial_price
                annualized_return = (1 + total_return) ** (252 / len(benchmark)) - 1
                
                logger.info(f"Benchmark (0050) Total Return: {total_return*100:.2f}%")
                return {
                    'total_return': total_return,
                    'annualized_return': annualized_return,
                    'initial_price': initial_price,
                    'final_price': final_price
                }
        except Exception as e:
            logger.error(f"Error fetching benchmark: {e}")
        return {}

    def run_strategy_backtest(self, mock_trades: list):
        """
        Simulate the strategy performance over time using a list of mock trades.
        mock_trades is a list of dicts:
        [{'ticker': '2330', 'entry_date': '...', 'exit_date': '...', 'entry_price': 100, 'exit_price': 120}, ...]
        """
        # Note: In a full pipeline, this would iterate day-by-day, predict, buy, and sell.
        # This is the simplified evaluator engine that calculates metrics from trade records.
        
        if not mock_trades:
            logger.warning("No trades provided for backtest.")
            return {}
            
        total_pnl_pct = 0.0
        winning_trades = 0
        total_trades = len(mock_trades)
        
        for trade in mock_trades:
            # Gross Return
            ret = (trade['exit_price'] - trade['entry_price']) / trade['entry_price']
            
            # Net Return (Deducting buy fee and sell fee+tax)
            net_ret = ret - (self.tx_cost * 2) # approx: cost on buy and cost on sell
            
            total_pnl_pct += net_ret
            if net_ret > 0:
                winning_trades += 1
                
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        logger.info(f"--- Strategy Backtest Results ---")
        logger.info(f"Total Trades: {total_trades}")
        logger.info(f"Win Rate: {win_rate*100:.2f}%")
        logger.info(f"Cumulative Net Return (Sum of non-compounded trades): {total_pnl_pct*100:.2f}%")
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'cumulative_net_return': total_pnl_pct
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    evaluator = BacktestEvaluator()
    
    # 1. Evaluate Benchmark (0050 Buy and Hold)
    evaluator.fetch_benchmark()
    
    # 2. Simulate Strategy Backtest
    # This is a mocked list of trades for architectural validation
    mocked_strategy_trades = [
        {'ticker': '2330.TW', 'entry_date': '2022-01-05', 'exit_date': '2022-01-12', 'entry_price': 650, 'exit_price': 660},
        {'ticker': '2317.TW', 'entry_date': '2022-02-10', 'exit_date': '2022-02-17', 'entry_price': 105, 'exit_price': 102}, # Loss
        {'ticker': '2454.TW', 'entry_date': '2022-03-01', 'exit_date': '2022-03-08', 'entry_price': 900, 'exit_price': 960},
        # ... generated by combining fetching -> modeling -> signals in a loop.
    ]
    
    evaluator.run_strategy_backtest(mocked_strategy_trades)



================================================================================
# 🗂️ 檔案位置 / FILE: config/__init__.py
================================================================================




================================================================================
# 🗂️ 檔案位置 / FILE: config/settings.py
================================================================================

import os
from dotenv import load_dotenv

load_dotenv()# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Google Gemini Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Model Training Parameters
TRAIN_START_DATE = "2022-01-01"
TRAIN_END_DATE = "2025-12-31"

# Trading Cost (0.1425% fee, 0.3% tax)
TRANSACTION_FEE = 0.001425
TRANSACTION_TAX = 0.003

# Top N Stocks for /top command
TOP_N_STOCKS = 5

# Taiwan 50 (0050.TW) Constituent Stock Tickers (Can be updated dynamically or statically)
# Hardcoding some major tickers for prototype purposes, but this should be fetched or updated periodically.
TW50_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", 
    "2882.TW", "1303.TW", "2891.TW", "2382.TW", "1301.TW",
    "2886.TW", "1216.TW", "2002.TW", "2884.TW", "2892.TW",
    "2303.TW", "2885.TW", "5871.TW", "1326.TW", "2357.TW",
    # We will implement logic to dynamically fetch the other tickers or read from a CSV.
]

# Forecast Window Options (in trading days)
FORECAST_WINDOWS = {
    "1W": 5,    # 1 Week (5 trading days)
    "2W": 10,   # 2 Weeks (10 trading days)
    "3W": 15,   # 3 Weeks (15 trading days)
    "1M": 21,   # 1 Month (21 trading days)
    "3M": 63    # 3 Months (63 trading days)
}

