from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import time

from app.models.stock import StockBasic
from app.models.stock_kline import StockKline


def check_strategy_consecutive_ma5(
    data: List[StockKline],
    x_days: int = 30,
    y_days: int = 10,
    z_days: int = 2
) -> Optional[dict]:
    """
    检查是否满足策略：
    - 最近 x 天内跌破布林下轨
    - 之后 y 天内连续 z 天站上 5 日均线
    从最新日期倒序找，找到第一个满足的即可
    
    :param data: 股票K线数据（按日期倒序排列）
    :param x_days: 最近 x 天内跌破布林下轨
    :param y_days: 之后 y 天内
    :param z_days: 连续 z 天站上 5 日均线
    :return: 如果满足条件返回策略信息，否则返回None
    """
    if len(data) < max(x_days, y_days, z_days) + 10:
        return None
    
    # 转换为正序以便检查（索引0是最老的日期，索引-1是最新的日期）
    sorted_data = sorted(data, key=lambda x: x.trade_date)
    
    # 获取最新日期的索引
    latest_idx = len(sorted_data) - 1
    
    # 从最新日期往回找，在最近 x 天内找跌破布林下轨的位置
    start_idx = max(0, latest_idx - x_days + 1)
    for i in range(latest_idx, start_idx - 1, -1):
        curr = sorted_data[i]
        
        # 检查是否跌破布林下轨
        if (curr.close is not None and curr.boll_lower is not None and 
            curr.close <= curr.boll_lower):
            
            # 找到跌破点，然后从这个日期往后（往更新的日期）找 y 天内连续 z 天站上 5 日线
            # i是跌破点的索引，从i+1开始往后找，最多找 y 天
            end_j = min(i + y_days, len(sorted_data) - 1)
            
            # 滑动窗口找连续 z 天
            for j in range(i + 1, end_j - z_days + 2):
                # 检查 j 到 j+z_days-1 这 z 天
                all_above = True
                matching_dates = []
                matching_days = []
                
                for k in range(j, j + z_days):
                    if k >= len(sorted_data):
                        all_above = False
                        break
                    
                    day = sorted_data[k]
                    if (day.close is not None and day.ma5 is not None and 
                        day.close >= day.ma5):
                        matching_dates.append(day.trade_date.strftime('%Y-%m-%d'))
                        matching_days.append(day)
                    else:
                        all_above = False
                        break
                
                if all_above and len(matching_dates) == z_days:
                    # 构建结果
                    strategy_name = (f'最近 {x_days} 天内跌破布林下轨，'
                                    f'之后 {y_days} 天内连续 {z_days} 天站上 5 日均线')
                    
                    result = {
                        'strategy': strategy_name,
                        'breakdown_date': curr.trade_date.strftime('%Y-%m-%d'),
                        'breakdown_close': curr.close,
                        'boll_lower': curr.boll_lower,
                        'matching_dates': matching_dates,
                        'details': {}
                    }
                    
                    # 添加详细信息
                    for idx, day in enumerate(matching_days):
                        result['details'][f'day{idx + 1}_date'] = day.trade_date.strftime('%Y-%m-%d')
                        result['details'][f'day{idx + 1}_close'] = day.close
                        result['details'][f'day{idx + 1}_ma5'] = day.ma5
                    
                    return result
    
    return None


def run_strategy_for_stock(
    db: Session,
    stock: StockBasic,
    strategy_name: str,
    x_days: int = 30,
    y_days: int = 10,
    z_days: int = 2
) -> Optional[dict]:
    """
    为单个股票运行策略
    
    :param db: 数据库会话
    :param stock: 股票信息
    :param strategy_name: 策略名称
    :param x_days: 最近 x 天内跌破布林下轨
    :param y_days: 之后 y 天内
    :param z_days: 连续 z 天站上 5 日均线
    :return: 策略结果
    """
    # 获取足够的K线数据（倒序）
    max_days = max(x_days, y_days, z_days) + 60
    data = db.query(StockKline).filter(
        StockKline.stock_code == stock.code
    ).order_by(StockKline.trade_date.desc()).limit(max_days).all()
    
    if len(data) < 20:
        return None
    
    # 运行策略
    if strategy_name == 'consecutive_ma5':
        result = check_strategy_consecutive_ma5(data, x_days, y_days, z_days)
        if result:
            return {
                'code': stock.code,
                'name': stock.name,
                'total_cap': stock.total_cap,
                'result': result
            }
    
    return None


def run_strategy(
    db: Session,
    strategy_name: str,
    min_market_cap: Optional[float] = None,
    x_days: int = 30,
    y_days: int = 10,
    z_days: int = 2
) -> List[dict]:
    """
    运行选股策略
    
    :param db: 数据库会话
    :param strategy_name: 策略名称
    :param min_market_cap: 最小市值（亿元）
    :param x_days: 最近 x 天内跌破布林下轨
    :param y_days: 之后 y 天内
    :param z_days: 连续 z 天站上 5 日均线
    :return: 策略结果列表
    """
    # 获取所有股票
    query = db.query(StockBasic)
    
    # 如果有最小市值筛选，添加条件
    if min_market_cap:
        # 转换为万元（数据库单位是万元）
        min_cap_wan = min_market_cap * 10000
        query = query.filter(StockBasic.total_cap >= min_cap_wan)
    
    stocks = query.all()
    
    results = []
    total_count = len(stocks)
    
    # 遍历所有股票
    for idx, stock in enumerate(stocks):
        time.sleep(0.01)  # 避免太频繁
        
        result = run_strategy_for_stock(db, stock, strategy_name, x_days, y_days, z_days)
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
