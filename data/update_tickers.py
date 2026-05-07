import requests
import json
import os

def update_tickers():
    tw_dict = {}

    # Get TWSE (market: .TW)
    try:
        res = requests.get('https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL', timeout=10)
        if res.status_code == 200:
            for item in res.json():
                code = item.get('Code', '')
                if code and code.strip():
                    tw_dict[code.strip()] = '.TW'
    except Exception as e:
        print(f"Error fetching TWSE: {e}")

    # Get TPEx (OTC market: .TWO)
    try:
        res = requests.get('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes', timeout=10)
        if res.status_code == 200:
            for item in res.json():
                code = item.get('SecuritiesCompanyCode', '')
                if code and code.strip():
                    tw_dict[code.strip()] = '.TWO'
    except Exception as e:
        print(f"Error fetching TPEx: {e}")

    # Save to tw_stock_dict.json
    output_path = os.path.join(os.path.dirname(__file__), 'tw_stock_dict.json')
    with open(output_path, 'w') as f:
        json.dump(tw_dict, f)
    print(f"Saved {len(tw_dict)} tickers to {output_path}")

if __name__ == '__main__':
    update_tickers()
