import requests
import json

# Check response structure variations
codes = ['sh600000', 'sh688808', 'sz000003', 'sh688012']

for code in codes:
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,2026-05-01,2026-05-30,10,qfq'
    r = requests.get(url, headers={'Referer': 'https://finance.qq.com'}, timeout=15)
    r.encoding = 'utf-8'
    data = r.json()
    
    print(f'\n=== {code} ===')
    print(f'code field: {data.get("code")}')
    print(f'msg field: {data.get("msg")}')
    
    raw_data = data.get('data', {})
    print(f'data type: {type(raw_data).__name__}')
    
    if isinstance(raw_data, dict):
        stock_data = raw_data.get(code, {})
        print(f'stock_data type: {type(stock_data).__name__}')
        if isinstance(stock_data, dict):
            print(f'keys: {list(stock_data.keys())}')
            if 'qfqday' in stock_data:
                print(f'qfqday count: {len(stock_data["qfqday"])}')
                if stock_data['qfqday']:
                    print(f'sample qfqday row: {stock_data["qfqday"][0]}')
            if 'day' in stock_data:
                print(f'day count: {len(stock_data["day"])}')
                if stock_data['day']:
                    print(f'sample day row: {stock_data["day"][0]}')
        elif isinstance(stock_data, list):
            print(f'stock_data is list, length: {len(stock_data)}')
            if stock_data:
                print(f'first element type: {type(stock_data[0]).__name__}')
                print(f'first element: {stock_data[0]}')
    elif isinstance(raw_data, list):
        print(f'raw_data is list, length: {len(raw_data)}')
        if raw_data:
            print(f'first element: {raw_data[0]}')
