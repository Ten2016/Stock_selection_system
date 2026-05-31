import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.database import SessionLocal
from app.models.stock_kline import StockKline
from app.models.stock import StockBasic

db = SessionLocal()

print('StockBasic count:', db.query(StockBasic).count())
print('StockKline count:', db.query(StockKline).count())

if db.query(StockKline).count() > 0:
    k = db.query(StockKline).first()
    print('Sample Kline:', k.stock_code, k.trade_date)
else:
    print('No K-line data in database')

db.close()
