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
        
        # yfinance download - sequentially to avoid thread hanging
        df_list = []
        for ticker in all_tickers:
            try:
                temp = yf.download(ticker, start=start_date, end=end_date, progress=False)
                if not temp.empty:
                    # Create MultiIndex columns to match batch download format
                    temp.columns = pd.MultiIndex.from_product([temp.columns, [ticker]])
                    df_list.append(temp)
            except Exception as e:
                logger.warning(f"Error fetching {ticker}: {e}")
            time.sleep(0.1) # Prevent rate limiting
            
        if df_list:
            return pd.concat(df_list, axis=1)
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

    def fetch_recent_news(self, ticker: str, limit: int = 3) -> str:
        """
        Fetch the latest news for a given ticker using yfinance.
        Returns a formatted string containing titles and summaries.
        """
        logger.info(f"Fetching recent news for {ticker}...")
        try:
            # yfinance requires .TW for Taiwan stocks, assume ticker has it or we might need to append
            # Wait, in this project ticker usually is passed as e.g. "2330.TW"
            yf_ticker = yf.Ticker(ticker)
            news_items = yf_ticker.news
            
            if not news_items:
                return "無最新新聞。"
                
            formatted_news = []
            for item in news_items[:limit]:
                content = item.get('content', {})
                title = content.get('title', 'No Title')
                summary = content.get('summary', 'No Summary')
                formatted_news.append(f"標題：{title}\n摘要：{summary}")
                
            return "\n\n".join(formatted_news)
        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            return "無法取得最新新聞。"

    def fetch_fundamentals(self, ticker: str) -> dict:
        """
        Fetch fundamental data (PE, PB, EPS, YoY) for a ticker using yfinance.
        """
        logger.info(f"Fetching fundamentals for {ticker}...")
        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info
            
            # yfinance info keys can vary, handle missing gracefully
            pe = info.get("trailingPE", "N/A")
            pb = info.get("priceToBook", "N/A")
            eps = info.get("trailingEps", "N/A")
            yoy = info.get("revenueGrowth", "N/A")
            
            if isinstance(pe, float): pe = round(pe, 2)
            if isinstance(pb, float): pb = round(pb, 2)
            if isinstance(eps, float): eps = round(eps, 2)
            if isinstance(yoy, float): yoy = f"{round(yoy * 100, 2)}%" # Convert to percentage string
            
            return {
                "PE": pe,
                "PB": pb,
                "EPS": eps,
                "YOY": yoy
            }
        except Exception as e:
            logger.error(f"Error fetching fundamentals for {ticker}: {e}")
            return {"PE": "N/A", "PB": "N/A", "EPS": "N/A", "YOY": "N/A"}
