import requests
import json

url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600008,day,2024-01-01,2026-05-29,500,qfq'
r = requests.get(url, headers={'Referer': 'https://finance.qq.com'}, timeout=15)
r.encoding = 'utf-8'
data = r.json()

klines = data.get('data', {}).get('sh600008', {}).get('qfqday', [])

print(f'Total rows: {len(klines)}')

lengths = {}
for row in klines:
    l = len(row)
    lengths[l] = lengths.get(l, 0) + 1

print(f'Length distribution: {lengths}')

six_rows = [r for r in klines if len(r) == 6]
seven_rows = [r for r in klines if len(r) == 7]

print(f'6-col rows: {len(six_rows)}, 7-col rows: {len(seven_rows)}')

if six_rows:
    print(f'\nSample 6-col row:')
    print(f'  {six_rows[0]}')
    
if seven_rows:
    print(f'\nSample 7-col row:')
    print(f'  {seven_rows[0]}')

# Show all rows with different lengths
print(f'\nAll rows with length != 6:')
for i, row in enumerate(klines):
    if len(row) != 6:
        print(f'  Row {i}: {row} (len={len(row)})')
