import logging
import time
import os
import threading
from flask import Flask

import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token":
        logger.error("TELEGRAM_BOT_TOKEN is missing or not configured correctly in .env!")
        return

    # Start the dummy web server to keep Render happy
    def run_web():
        app = Flask(__name__)
        @app.route('/')
        def home():
            return "Bot is alive and polling!"
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port)

    threading.Thread(target=run_web, daemon=True).start()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    predict_handler = CommandHandler('predict', predict)
    top_handler = CommandHandler('top', top)
    predict_range_handler = CommandHandler('predict_range', predict_range)
    
    application.add_handler(start_handler)
    application.add_handler(predict_handler)
    application.add_handler(top_handler)
    application.add_handler(predict_range_handler)
    
    logger.info("Project Chronos Telegram Bot is up and running...")
    application.run_polling()

if __name__ == '__main__':
    main()
