from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import time

from app.models.stock import StockBasic
from app.models.stock_kline import StockKline


def check_strategy_consecutive_ma5(data: List[StockKline]) -> Optional[dict]:
    """
    检查是否满足策略：跌破布林下轨后，10天内连续两天站上5日线
    从最新日期倒序找，找到第一个满足的即可
    
    :param data: 股票K线数据（按日期倒序排列）
    :return: 如果满足条件返回策略信息，否则返回None
    """
    if len(data) < 20:
        return None
    
    # 转换为正序以便检查（索引0是最老的日期，索引-1是最新的日期）
    sorted_data = sorted(data, key=lambda x: x.trade_date)
    
    # 从最新日期往回找，找到跌破布林下轨的位置
    for i in range(len(sorted_data) - 1, -1, -1):
        curr = sorted_data[i]
        
        # 检查是否跌破布林下轨
        if (curr.close is not None and curr.boll_lower is not None and 
            curr.close <= curr.boll_lower):
            
            # 找到跌破点，然后从这个日期往后（往更新的日期）找10天内连续两天站上5日线
            # i是跌破点的索引，从i+1开始往后找
            for j in range(i + 1, min(i + 11, len(sorted_data) - 1)):
                day1 = sorted_data[j]
                day2 = sorted_data[j + 1]
                
                # 检查这两天是否都站上5日线
                if (day1.close is not None and day1.ma5 is not None and day1.close >= day1.ma5 and
                    day2.close is not None and day2.ma5 is not None and day2.close >= day2.ma5):
                    
                    result = {
                        'strategy': '跌破布林下轨后，10天内连续两天站上5日线',
                        'breakdown_date': curr.trade_date.strftime('%Y-%m-%d'),
                        'breakdown_close': curr.close,
                        'boll_lower': curr.boll_lower,
                        'matching_dates': [day1.trade_date.strftime('%Y-%m-%d'), day2.trade_date.strftime('%Y-%m-%d')],
                        'details': {
                            'day1_date': day1.trade_date.strftime('%Y-%m-%d'),
                            'day1_close': day1.close,
                            'day1_ma5': day1.ma5,
                            'day2_date': day2.trade_date.strftime('%Y-%m-%d'),
                            'day2_close': day2.close,
                            'day2_ma5': day2.ma5
                        }
                    }
                    return result
    
    return None


def run_strategy_for_stock(db: Session, stock: StockBasic, strategy_name: str) -> Optional[dict]:
    """
    为单个股票运行策略
    
    :param db: 数据库会话
    :param stock: 股票信息
    :param strategy_name: 策略名称
    :return: 策略结果
    """
    # 获取最近60条K线数据（倒序）
    data = db.query(StockKline).filter(
        StockKline.stock_code == stock.code
    ).order_by(StockKline.trade_date.desc()).limit(60).all()
    
    if len(data) < 20:
        return None
    
    # 运行策略
    if strategy_name == 'consecutive_ma5':
        result = check_strategy_consecutive_ma5(data)
        if result:
            return {
                'code': stock.code,
                'name': stock.name,
                'total_cap': stock.total_cap,
                'result': result
            }
    
    return None


def run_strategy(db: Session, strategy_name: str, min_market_cap: Optional[float] = None) -> List[dict]:
    """
    运行选股策略
    
    :param db: 数据库会话
    :param strategy_name: 策略名称
    :param min_market_cap: 最小市值筛选
    :return: 符合条件的股票列表
    """
    # 获取符合条件的股票
    query = db.query(StockBasic).filter(StockBasic.is_active == True)
    
    if min_market_cap is not None:
        query = query.filter(StockBasic.total_cap >= min_market_cap)
    
    stocks = query.order_by(StockBasic.total_cap.desc()).all()
    
    results = []
    total_count = len(stocks)
    
    # 遍历所有股票
    for idx, stock in enumerate(stocks):
        time.sleep(0.01)  # 避免太频繁
        
        result = run_strategy_for_stock(db, stock, strategy_name)
        if result:
            results.append(result)
        
        # 每处理100个股票打印进度
        if (idx + 1) % 100 == 0:
            print(f"已处理 {idx + 1}/{total_count} 股票，找到 {len(results)} 个符合条件的")
    
    return results


def get_available_strategies() -> List[dict]:
    """
    获取可用策略列表
    
    :return: 策略列表
    """
    return [
        {
            'name': 'consecutive_ma5',
            'display_name': '跌破布林下轨后连续两天站上5日线',
            'description': '在跌破布林下轨后，10天内寻找连续两天收盘价站在5日线上方的股票'
        }
    ]
