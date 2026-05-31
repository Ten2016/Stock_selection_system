import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.database import SessionLocal
from app.models.stock_kline import StockKline
from app.models.stock import StockBasic
import pandas as pd


def main():
    print("Starting MA30/MA120 backfill...")
    
    db = SessionLocal()
    
    stocks = db.query(StockBasic.code).all()
    stock_codes = [s[0] for s in stocks]
    print(f"Found {len(stock_codes)} stocks")
    
    total_updated = 0
    success = 0
    failed = 0
    
    for idx, code in enumerate(stock_codes, 1):
        try:
            klines = db.query(StockKline).filter(
                StockKline.stock_code == code
            ).order_by(StockKline.trade_date).all()
            
            if not klines:
                continue
            
            print(f"[{idx}/{len(stock_codes)}] Processing {code} ({len(klines)} records)...")
            
            df = pd.DataFrame([{'close': float(k.close) if k.close else None} for k in klines])
            df['MA30'] = df['close'].rolling(window=30).mean().round(2)
            df['MA120'] = df['close'].rolling(window=120).mean().round(2)
            
            for i, kline in enumerate(klines):
                if pd.notna(df.loc[i, 'MA30']):
                    kline.ma30 = float(df.loc[i, 'MA30'])
                if pd.notna(df.loc[i, 'MA120']):
                    kline.ma120 = float(df.loc[i, 'MA120'])
            
            db.commit()
            total_updated += len(klines)
            success += 1
                
        except Exception as e:
            failed += 1
            print(f"Error: {code} - {e}")
            db.rollback()
    
    print(f"\nDone! Success: {success}, Failed: {failed}, Total records: {total_updated}")
    db.close()


if __name__ == "__main__":
    main()
