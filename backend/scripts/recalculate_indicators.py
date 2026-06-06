"""
重新计算所有历史数据的指标和涨跌幅
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.database import SessionLocal
from app.models.stock_kline import StockKline
from sqlalchemy import and_
import pandas as pd


def recalculate_stock_indicators(stock_code: str):
    """重新计算单个股票的所有指标"""
    with SessionLocal() as db:
        # 获取该股票的所有K线数据
        klines = db.query(StockKline).filter(
            StockKline.stock_code == stock_code
        ).order_by(StockKline.trade_date.asc()).all()
        
        if not klines:
            return 0
        
        # 转换为DataFrame
        df = pd.DataFrame([{
            'trade_date': k.trade_date,
            'open': float(k.open) if k.open else None,
            'high': float(k.high) if k.high else None,
            'low': float(k.low) if k.low else None,
            'close': float(k.close) if k.close else None,
            'volume': float(k.volume) if k.volume else None,
        } for k in klines])
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 计算 change_pct
        change_pcts = []
        for i in range(len(df)):
            if i == 0:
                change_pcts.append(None)
            else:
                prev_close = df.iloc[i - 1]['close']
                curr_close = df.iloc[i]['close']
                if prev_close and curr_close and prev_close > 0:
                    pct = ((curr_close - prev_close) / prev_close) * 100
                    change_pcts.append(round(pct, 2))
                else:
                    change_pcts.append(None)
        df['change_pct'] = change_pcts
        
        # 计算 MA
        df['MA5'] = df['close'].rolling(window=5).mean().round(2)
        df['MA10'] = df['close'].rolling(window=10).mean().round(2)
        df['MA20'] = df['close'].rolling(window=20).mean().round(2)
        df['MA30'] = df['close'].rolling(window=30).mean().round(2)
        df['MA60'] = df['close'].rolling(window=60).mean().round(2)
        df['MA120'] = df['close'].rolling(window=120).mean().round(2)
        
        # 计算布林带
        std = df['close'].rolling(window=20).std()
        df['boll_upper'] = (df['MA20'] + 2 * std).round(2)
        df['boll_mid'] = df['MA20']
        df['boll_lower'] = (df['MA20'] - 2 * std).round(2)
        
        # 计算 amplitude
        amplitudes = []
        for i in range(len(df)):
            if i == 0:
                amplitudes.append(None)
            else:
                prev_close = df.iloc[i - 1]['close']
                high = df.iloc[i]['high']
                low = df.iloc[i]['low']
                if prev_close and high and low and prev_close > 0:
                    amp = ((high - low) / prev_close) * 100
                    amplitudes.append(round(amp, 2))
                else:
                    amplitudes.append(None)
        df['amplitude'] = amplitudes
        
        # 更新数据库
        updated = 0
        for i, kline in enumerate(klines):
            row = df.iloc[i]
            
            kline.change_pct = row['change_pct']
            kline.ma5 = row['MA5']
            kline.ma10 = row['MA10']
            kline.ma20 = row['MA20']
            kline.ma30 = row['MA30']
            kline.ma60 = row['MA60']
            kline.ma120 = row['MA120']
            kline.boll_upper = row['boll_upper']
            kline.boll_mid = row['boll_mid']
            kline.boll_lower = row['boll_lower']
            kline.amplitude = row['amplitude']
            
            updated += 1
        
        db.commit()
        return updated


def main():
    print("=" * 60)
    print("重新计算所有历史数据的指标和涨跌幅")
    print("=" * 60)
    
    with SessionLocal() as db:
        # 获取所有有K线数据的股票代码
        from sqlalchemy import func
        stock_codes = db.query(StockKline.stock_code).distinct().all()
        stock_codes = [row[0] for row in stock_codes]
    
    print(f"找到 {len(stock_codes)} 只股票需要重新计算")
    
    total_updated = 0
    for idx, code in enumerate(stock_codes):
        try:
            updated = recalculate_stock_indicators(code)
            total_updated += updated
            if (idx + 1) % 100 == 0:
                print(f"[{idx + 1}/{len(stock_codes)}] 已处理 {code}，累计更新 {total_updated} 条记录")
        except Exception as e:
            print(f"[ERROR] 处理 {code} 时出错: {e}")
    
    print("=" * 60)
    print(f"完成！共处理 {len(stock_codes)} 只股票，更新 {total_updated} 条记录")
    print("=" * 60)


if __name__ == "__main__":
    main()
