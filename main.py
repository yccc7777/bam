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
from models.multi_agent import AgentDebateEngine
from strategies.signal import StrategySignal
from data.portfolio_db import PortfolioDB
from strategies.execution import PaperBroker
from data.storage import StorageHelper
import json
import datetime

# 載入台股代號與市場後綴的對應表 (TWSE: .TW, TPEx: .TWO)
TW_STOCK_DICT = {}
dict_path = os.path.join(os.path.dirname(__file__), 'data', 'tw_stock_dict.json')
try:
    with open(dict_path, 'r') as f:
        TW_STOCK_DICT = json.load(f)
except FileNotFoundError:
    logger.warning("tw_stock_dict.json not found. Run update_tickers.py to generate it.")


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database and broker
portfolio_db = PortfolioDB()
paper_broker = PaperBroker(portfolio_db)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "👋 歡迎使用 *Project Chronos (時鐘神)* 台股機器人！\n\n"
        "我是你的專屬 AI 量化分析助理。我能預測台灣 50 成分股的各個時間窗格報酬率。\n\n"
        "你可以使用以下指令：\n"
        "🔹 `/top`：獲取預期報酬最高的 5 檔飆股排行。\n"
        "🔹 `/predict <股票代號>`：查詢單一個股的詳細預測（例如：`/predict 2330`）。\n"
        "🔹 `/predict_range <股票代號> <開始日期> <結束日期>`：預測指定日期區間走勢（例如：`/predict_range 2330 03/27 04/02`）。\n"
        "🔹 `/portfolio`：查看您的虛擬投資組合與損益。\n"
        "🔹 `/buy <股票代號> <股數>`：模擬買進股票。\n"
        "🔹 `/sell <股票代號> <股數>`：模擬賣出股票。\n"
        "🔹 `/subscribe`：訂閱每日盤前推播與盤後檢討。\n"
        "🔹 `/unsubscribe`：取消訂閱。\n"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    StorageHelper.add_subscriber(chat_id)
    await update.message.reply_text("✅ 已成功訂閱每日盤前推播與盤後檢討！", parse_mode='Markdown')

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    StorageHelper.remove_subscriber(chat_id)
    await update.message.reply_text("❌ 已取消訂閱每日盤前推播與盤後檢討。", parse_mode='Markdown')

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("⚠️ 請提供股票代號，例如：`/predict 2330`", parse_mode='Markdown')
        return
        
    ticker = context.args[0]
    # Check for suffix or append from dictionary
    if not ticker.endswith(".TW") and not ticker.endswith(".TWO"):
        suffix = TW_STOCK_DICT.get(ticker, ".TW") # fallback to .TW if not found
        ticker += suffix
        
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
        
        # 4. Fetch recent news for RAG
        news_context = fetcher.fetch_recent_news(ticker)

        # 5. Generate narrative via Multi-Agent Debate
        debate_engine = AgentDebateEngine(api_key=GEMINI_API_KEY)
        debate_result = debate_engine.run_debate(ticker, predictions, news_context)
        
        # 6. Format beautiful output
        news_display = "無即時新聞"
        if news_context and news_context != "無最新新聞。":
            first_news_title = news_context.split("標題：")[1].split("\n")[0] if "標題：" in news_context else ""
            news_display = first_news_title if first_news_title else "無即時新聞"

        response_text = (
            f"📊 **{ticker} 即時預測報告**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 **最新收盤價：** ${current_price:.2f}\n"
            f"📰 **即時頭條：** _{news_display}_\n\n"
            f"📈 **AI 預期報酬率：**\n"
            f"   • 1 週預期： {predictions.get('1W', 0)*100:+.2f}%\n"
            f"   • 2 週預期： {predictions.get('2W', 0)*100:+.2f}%\n"
            f"   • 3 週預期： {predictions.get('3W', 0)*100:+.2f}%\n"
            f"   • 1 個月預期：{predictions.get('1M', 0)*100:+.2f}%\n"
            f"   • 3 個月預期：{predictions.get('3M', 0)*100:+.2f}%\n\n"
            f"🤖 **AI 多智能體辯論結論：**\n"
            f"👤 **技術面分析師 (判斷短線趨勢)**：\n_{debate_result['tech_view']}_\n\n"
            f"📊 **基本面分析師 (評估長線價值)**：\n_{debate_result['fund_view']}_\n\n"
            f"🛡️ **風險控管員 (專門找碴與挑毛病)**：\n_{debate_result['risk_view']}_\n\n"
            f"👑 **首席經理人 (綜合決策與資金配置)**：\n_{debate_result['pm_view']}_\n\n"
            f"🔍 **覆核稽核員 (敗因推演與防呆機制)**：\n_{debate_result['review_view']}_\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 **最終行動建議**：\n**{debate_result['final_action']}**\n\n"
            f"💡 _提示：輸入_ `/buy {ticker} 1000` _模擬買進 1 張。_"
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
    
    if not ticker.endswith(".TW") and not ticker.endswith(".TWO"):
        suffix = TW_STOCK_DICT.get(ticker, ".TW") # fallback to .TW if not found
        ticker += suffix
        
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

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    balance = portfolio_db.get_or_create_user(user_id)
    holdings = portfolio_db.get_all_holdings(user_id)
    
    response_text = f"💼 **您的虛擬投資組合**\n━━━━━━━━━━━━━━━━━━━\n"
    response_text += f"💵 **可用資金：** ${balance:,.0f}\n\n"
    
    if not holdings:
        response_text += "目前沒有任何持股。\n"
    else:
        response_text += "📈 **目前持股：**\n"
        for ticker, qty, avg_price in holdings:
            current_price = paper_broker.get_current_price(ticker)
            unrealized_pnl = (current_price - avg_price) * qty
            pnl_pct = (unrealized_pnl / (avg_price * qty)) * 100 if avg_price > 0 else 0
            response_text += f"• **{ticker}**: {qty} 股 | 均價 ${avg_price:.2f} | 現價 ${current_price:.2f}\n"
            response_text += f"  未實現損益: ${unrealized_pnl:,.0f} ({pnl_pct:+.2f}%)\n"
    
    response_text += "━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(response_text, parse_mode='Markdown')

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ 格式錯誤！請使用：`/buy <股票代號> <股數>`\n例如：`/buy 2330 1000`", parse_mode='Markdown')
        return
    ticker = context.args[0]
    
    # Auto append TW suffix if not provided and it is a number
    if ticker.isdigit():
        suffix = TW_STOCK_DICT.get(ticker, ".TW")
        ticker += suffix
        
    try:
        qty = int(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ 股數必須是整數。")
        return
        
    result = paper_broker.buy(user_id, ticker, qty)
    await update.message.reply_text(result["message"])

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ 格式錯誤！請使用：`/sell <股票代號> <股數>`\n例如：`/sell 2330 1000`", parse_mode='Markdown')
        return
    ticker = context.args[0]
    
    if ticker.isdigit():
        suffix = TW_STOCK_DICT.get(ticker, ".TW")
        ticker += suffix
        
    try:
        qty = int(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ 股數必須是整數。")
        return
        
    result = paper_broker.sell(user_id, ticker, qty)
    await update.message.reply_text(result["message"])

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

async def _run_premarket_report(context: ContextTypes.DEFAULT_TYPE):
    ticker = StorageHelper.get_tomorrow_target()
    if not ticker:
        ticker = "2330.TW"
        
    try:
        fetcher = DataFetcher()
        processor = DataProcessor()
        ml_model = MLModel(list(FORECAST_WINDOWS.keys()))
        llm = LLMGenerator(api_key=GEMINI_API_KEY)
        
        # 1. Fetch data
        df_raw = fetcher.fetch_yahoo_finance_data([ticker], "2023-01-01", pd.Timestamp.now().strftime("%Y-%m-%d"))
        if df_raw.empty: return

        df_ticker = pd.DataFrame()
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if (col, ticker) in df_raw.columns:
                df_ticker[col] = df_raw[(col, ticker)]
            elif col in df_raw.columns:
                df_ticker[col] = df_raw[col]
                
        if df_ticker.empty or len(df_ticker) < 100: return
            
        current_price = df_ticker['Close'].iloc[-1]
        if isinstance(current_price, pd.Series):
            current_price = current_price.iloc[0]
            
        # 2. Features
        df_processed = processor.process_stock_data(df_ticker, FORECAST_WINDOWS)
        train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
        if train_data.empty: return
            
        # 3. Train & Predict
        ml_model.train(train_data)
        predictions = ml_model.predict(train_data)
        for k, v in predictions.items():
            if hasattr(v, 'item'): predictions[k] = v.item()
            else: predictions[k] = float(v)
                
        # 4. Debate & News
        news_context = fetcher.fetch_recent_news(ticker)
        debate_engine = AgentDebateEngine(api_key=GEMINI_API_KEY)
        debate_result = debate_engine.run_debate(ticker, predictions, news_context)
        
        # 5. Save State
        date_str = pd.Timestamp.now().strftime("%Y-%m-%d")
        StorageHelper.save_daily_state(date_str, ticker, predictions, debate_result['pm_view'], float(current_price))
        
        # 6. Broadcast
        news_display = "無即時新聞"
        if news_context and news_context != "無最新新聞。":
            first_news_title = news_context.split("標題：")[1].split("\n")[0] if "標題：" in news_context else ""
            news_display = first_news_title if first_news_title else "無即時新聞"

        response_text = (
            f"🌅 **盤前策略報告 ({date_str})**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 **標的**：{ticker}\n"
            f"💰 **早盤參考價**：${current_price:.2f}\n"
            f"📰 **即時頭條**：_{news_display}_\n\n"
            f"🤖 **首席經理人盤前決策**：\n"
            f"_{debate_result['pm_view']}_\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 系統將於下午為您覆核此決策的準確度。"
        )
        
        subs = StorageHelper.get_subscribers()
        for chat_id in subs:
            try:
                await context.bot.send_message(chat_id=chat_id, text=response_text, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Failed to send to {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Premarket job error: {e}")

async def _run_postmarket_review(context: ContextTypes.DEFAULT_TYPE):
    date_str = pd.Timestamp.now().strftime("%Y-%m-%d")
    state = StorageHelper.get_daily_state(date_str)
    if not state:
        logger.info("No morning state found for review.")
        return
        
    ticker = state['ticker']
    try:
        fetcher = DataFetcher()
        # Fetch today's close price
        df_raw = fetcher.fetch_yahoo_finance_data([ticker], "2023-01-01", (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        if df_raw.empty: return
        
        close_series = df_raw['Close'][ticker] if ('Close', ticker) in df_raw.columns else df_raw['Close']
        actual_close = float(close_series.iloc[-1])
        
        debate_engine = AgentDebateEngine(api_key=GEMINI_API_KEY)
        review_text = debate_engine.run_daily_review(ticker, state['pm_view'], state['morning_price'], actual_close)
        
        # --- Scan for tomorrow's target ---
        best_ticker = "2330.TW"
        best_pred = -999.0
        try:
            scan_tickers = TW50_TICKERS[:15] # Scan top 15 to save time
            processor = DataProcessor()
            df_scan_raw = fetcher.fetch_yahoo_finance_data(scan_tickers, "2023-01-01", pd.Timestamp.now().strftime("%Y-%m-%d"))
            for t in scan_tickers:
                df_t = pd.DataFrame()
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if (col, t) in df_scan_raw.columns: df_t[col] = df_scan_raw[(col, t)]
                    elif col in df_scan_raw.columns: df_t[col] = df_scan_raw[col]
                if len(df_t) < 100: continue
                
                df_processed = processor.process_stock_data(df_t, FORECAST_WINDOWS)
                train_data = df_processed.dropna(subset=['MA_60', 'MACD'])
                if train_data.empty: continue
                
                model = MLModel(list(FORECAST_WINDOWS.keys()))
                model.train(train_data)
                preds = model.predict(train_data)
                pred_1w = preds['1W'].item() if hasattr(preds['1W'], 'item') else float(preds['1W'])
                
                if pred_1w > best_pred:
                    best_pred = pred_1w
                    best_ticker = t
            StorageHelper.set_tomorrow_target(best_ticker)
        except Exception as e:
            logger.error(f"Error scanning for tomorrow target: {e}")
            StorageHelper.set_tomorrow_target("2330.TW") # fallback
        # -----------------------------------
        
        response_text = (
            f"🌇 **盤後檢討與反思報告 ({date_str})**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 **標的**：{ticker}\n"
            f"💰 **今日收盤價**：${actual_close:.2f} (早盤參考：${state['morning_price']:.2f})\n\n"
            f"🔍 **AI 覆核稽核員檢討報告**：\n"
            f"_{review_text}_\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 **明日觀測預告**：\n"
            f"AI 已於盤後掃描大盤，鎖定明日觀測標的：【**{best_ticker}**】(預期報酬最強)，將於明早 08:30 進行詳細盤前推演。"
        )
        
        subs = StorageHelper.get_subscribers()
        for chat_id in subs:
            try:
                await context.bot.send_message(chat_id=chat_id, text=response_text, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Failed to send to {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Postmarket job error: {e}")

async def send_premarket_report(context: ContextTypes.DEFAULT_TYPE):
    await _run_premarket_report(context)

async def send_postmarket_review(context: ContextTypes.DEFAULT_TYPE):
    await _run_postmarket_review(context)

async def test_pre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ 手動觸發盤前報告測試...", parse_mode='Markdown')
    await _run_premarket_report(context)

async def test_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ 手動觸發盤後檢討測試...", parse_mode='Markdown')
    await _run_postmarket_review(context)

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
    application.add_handler(CommandHandler('portfolio', portfolio))
    application.add_handler(CommandHandler('buy', buy))
    application.add_handler(CommandHandler('sell', sell))
    application.add_handler(CommandHandler('subscribe', subscribe))
    application.add_handler(CommandHandler('unsubscribe', unsubscribe))
    application.add_handler(CommandHandler('test_pre', test_pre))
    application.add_handler(CommandHandler('test_post', test_post))
    
    # 排程任務已移交給 GitHub Actions 執行
    # tz = datetime.timezone(datetime.timedelta(hours=8)) # Asia/Taipei timezone
    # application.job_queue.run_daily(send_premarket_report, time=datetime.time(hour=8, minute=30, tzinfo=tz))
    # application.job_queue.run_daily(send_postmarket_review, time=datetime.time(hour=14, minute=30, tzinfo=tz))
    
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
