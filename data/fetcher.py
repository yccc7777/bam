import yfinance as yf
import requests
import pandas as pd
import time
import logging
import datetime
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self):
        # TWSE API Endpoint for institutional investors trading (三大法人買賣超)
        self.twse_api_url = "https://www.twse.com.tw/fund/T86?response=json&selectType=ALL&date={date}"

    def fetch_yahoo_finance_data(self, tickers: list, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch OHLCV data for given tickers and the market index (^TWII).
        Uses FinMind API to avoid yfinance rate limits for Taiwan stocks.
        """
        logger.info(f"Fetching FinMind data for {len(tickers)} tickers and ^TWII...")
        
        all_tickers = tickers + ["^TWII"]
        df_list = []
        
        for ticker in all_tickers:
            try:
                # Convert ^TWII to TAIEX, and strip .TW/.TWO for stock codes
                clean_ticker = 'TAIEX' if ticker == '^TWII' else ticker.replace('.TW', '').replace('.TWO', '')
                url = f'https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={clean_ticker}&start_date={start_date}&end_date={end_date}'
                
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json().get('data', [])
                    if data:
                        df = pd.DataFrame(data)
                        df = df.rename(columns={
                            'open': 'Open',
                            'max': 'High',
                            'min': 'Low',
                            'close': 'Close',
                            'Trading_Volume': 'Volume',
                            'date': 'Date'
                        })
                        df['Date'] = pd.to_datetime(df['Date'])
                        df = df.set_index('Date')
                        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
                        
                        # Create MultiIndex columns to match yfinance format
                        df.columns = pd.MultiIndex.from_product([df.columns, [ticker]])
                        df_list.append(df)
            except Exception as e:
                logger.warning(f"Error fetching {ticker} from FinMind: {e}")
            time.sleep(0.5) # Prevent rate limiting on FinMind
            
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

    def get_latest_twse_institutional(self, ticker: str) -> str:
        """
        Get the latest available institutional trading data for a specific ticker.
        Searches backwards up to 10 days to find a valid trading day.
        Returns a formatted string describing the institutional actions.
        """
        logger.info(f"Fetching latest TWSE institutional data for {ticker}...")
        # yfinance tickers often have '.TW' suffix, remove it for TWSE API
        clean_ticker = ticker.split('.')[0]
        
        for i in range(10):
            dt = datetime.datetime.now() - datetime.timedelta(days=i)
            date_str = dt.strftime('%Y%m%d')
            df = self.fetch_twse_institutional_data(date_str, max_retries=1)
            if not df.empty:
                stock_data = df[df['證券代號'] == clean_ticker]
                if not stock_data.empty:
                    row = stock_data.iloc[0]
                    foreign = row.get('外陸資買賣超股數(不含外資自營商)', '0').replace(',', '')
                    trust = row.get('投信買賣超股數', '0').replace(',', '')
                    total = row.get('三大法人買賣超股數', '0').replace(',', '')
                    
                    try:
                        foreign_lots = int(foreign) // 1000
                        trust_lots = int(trust) // 1000
                        total_lots = int(total) // 1000
                        
                        return (f"最近交易日 ({dt.strftime('%Y-%m-%d')}): "
                                f"外資買賣超 {foreign_lots} 張, "
                                f"投信買賣超 {trust_lots} 張, "
                                f"三大法人合計買賣超 {total_lots} 張。")
                    except ValueError:
                        return "無法解析籌碼數據格式。"
            time.sleep(0.5)
            
        return "近期無籌碼數據變動。"

    def fetch_ptt_comments(self, ticker: str, limit: int = 30) -> str:
        """
        Scrape the PTT Stock board for the latest post regarding the ticker,
        and extract the latest comments to reflect retail sentiment.
        """
        logger.info(f"Fetching PTT comments for {ticker}...")
        clean_ticker = ticker.split('.')[0]
        search_url = f"https://www.ptt.cc/bbs/Stock/search?q={clean_ticker}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        cookies = {'over18': '1'}
        
        try:
            res = requests.get(search_url, headers=headers, cookies=cookies, timeout=10)
            if res.status_code != 200:
                return "無法連線至 PTT。"
                
            soup = BeautifulSoup(res.text, 'html.parser')
            titles = soup.find_all('div', class_='title')
            
            latest_url = None
            article_title = ""
            for t in titles:
                if t.a:
                    latest_url = "https://www.ptt.cc" + t.a['href']
                    article_title = t.a.text.strip()
                    break
                    
            if not latest_url:
                return "PTT 股票版近期無此標的之討論文章。"
                
            # Fetch the actual article
            art_res = requests.get(latest_url, headers=headers, cookies=cookies, timeout=10)
            if art_res.status_code != 200:
                return f"找到文章「{article_title}」，但無法讀取內文。"
                
            art_soup = BeautifulSoup(art_res.text, 'html.parser')
            pushes = art_soup.find_all('div', class_='push')
            
            if not pushes:
                return f"PTT 最新文章：「{article_title}」\n(目前尚無鄉民推文)"
                
            comments = []
            # Get the last `limit` comments to reflect the most recent sentiment
            for p in pushes[-limit:]:
                push_content = p.find('span', class_='push-content')
                if push_content:
                    text = push_content.text.strip().replace(':', '', 1).strip()
                    if text:
                        comments.append(text)
                        
            comments_str = "\n".join([f"- {c}" for c in comments])
            return f"PTT 最新討論：「{article_title}」\n真實鄉民推文：\n{comments_str}"
            
        except Exception as e:
            logger.error(f"Error fetching PTT comments: {e}")
            return "抓取 PTT 留言時發生錯誤。"

    def fetch_mops_investor_conference(self, ticker: str) -> str:
        """
        Fetch Investor Conference (法說會) information from Old MOPS for the given ticker.
        """
        import urllib3
        urllib3.disable_warnings()
        
        logger.info(f"Fetching MOPS investor conference for {ticker}...")
        clean_ticker = ticker.split('.')[0]
        url = 'https://mopsov.twse.com.tw/mops/web/ajax_t100sb07_1'
        payload = {
            'encodeURIComponent': '1',
            'step': '1',
            'firstin': '1',
            'off': '1',
            'co_id': clean_ticker,
            'TYPEK': 'all',
        }
        
        try:
            res = requests.post(url, data=payload, verify=False, timeout=10)
            if res.status_code != 200:
                return "無法連線至公開資訊觀測站。"
                
            soup = BeautifulSoup(res.text, 'html.parser')
            tables = soup.find_all('table', class_='hasBorder')
            
            if not tables:
                return "無近期法說會資訊。"
                
            info_dict = {}
            # Just take the first table (most recent conference)
            for tr in tables[0].find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 2:
                    key = tds[0].text.strip().replace('：', '')
                    val = tds[1].text.strip()
                    info_dict[key] = val
                    
            if not info_dict:
                return "無近期法說會資訊。"
                
            date = info_dict.get('召開法人說明會日期', '未提供')
            msg = info_dict.get('法人說明會擇要訊息', '未提供')
            
            return f"最新法說會日期：{date}\n法說會重點摘要：{msg}"
            
        except Exception as e:
            logger.error(f"Error fetching MOPS investor conference: {e}")
            return "抓取法說會資訊時發生錯誤。"

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
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        try:
            yf_ticker = yf.Ticker(ticker, session=session)
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
