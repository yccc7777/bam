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
