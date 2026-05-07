import yfinance as yf
import requests
import time
import pandas as pd

print("Fetching TWSE eq codes...")
res = requests.get('https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL')
data = res.json()
twse_codes = [d['Code'] + '.TW' for d in data if d['Code'].isdigit() and len(d['Code']) == 4]

print("Fetching OTC eq codes...")
print(f"Found {len(twse_codes)} TWSE codes")

start = time.time()
df = yf.download(twse_codes[:500], period="1mo", threads=True, progress=False)
print(f"Time to download 500 TWSE stocks: {time.time() - start:.2f}s")
