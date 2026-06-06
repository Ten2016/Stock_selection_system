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
    - 从当前日期开始，往前最多找x天，在这些天中，找到第一个满足收盘价跌破布林下轨的日期
    - 然后从这天开始再往后找，在y天内找到连续有z天收盘价都站上5天均线的票
    从最新日期倒序找，找到第一个满足的即可
    
    :param data: 股票K线数据（按日期倒序排列）
    :param x_days: 往前找x天
    :param y_days: 往后找y天
    :param z_days: 连续z天站上5日均线
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
                    strategy_name = (f'往前 {x_days} 天内跌破布林下轨，'
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


def check_strategy_rise_then_fall(
    data: List[StockKline],
    x_days: int = 30,
    y_pct: float = 5.0,
    z_days: int = 3
) -> Optional[dict]:
    """
    检查是否满足策略：
    - 从当前日期开始，往前最多找x天
    - 对每一天做判断，查看当天收盘涨幅是否大于y%
    - 且之后连续z天都是下跌（收盘价低于前一天）
    - 找到第一个满足这一系列条件的日期就停止
    
    :param data: 股票K线数据（按日期倒序排列）
    :param x_days: 往前找x天
    :param y_pct: 当天收盘涨幅大于y%
    :param z_days: 之后连续z天都是下跌
    :return: 如果满足条件返回策略信息，否则返回None
    """
    if len(data) < x_days + z_days + 5:
        return None
    
    # 转换为正序以便检查（索引0是最老的日期，索引-1是最新的日期）
    sorted_data = sorted(data, key=lambda x: x.trade_date)
    
    # 获取最新日期的索引
    latest_idx = len(sorted_data) - 1
    
    # 从最新日期往回找，在最近 x 天内找满足条件的日期
    # 找到第一个满足"涨幅大于y% 且 之后连续z天下跌"的就停止
    start_idx = max(0, latest_idx - x_days + 1)
    
    for i in range(latest_idx, start_idx - 1, -1):
        curr = sorted_data[i]
        
        # 检查当天涨幅是否大于y%
        if curr.change_pct is None or curr.change_pct <= y_pct:
            continue
        
        # 涨幅满足，检查之后连续z天是否都是下跌
        end_idx = i + z_days
        
        if end_idx >= len(sorted_data):
            continue
        
        # 检查从i+1开始的连续z天是否都是下跌
        all_fall = True
        falling_dates = []
        falling_days = []
        
        for k in range(i + 1, end_idx + 1):
            if k >= len(sorted_data):
                all_fall = False
                break
            
            curr_day = sorted_data[k]
            prev_day = sorted_data[k - 1]
            
            # 检查当天收盘价是否低于前一天
            if (curr_day.close is not None and prev_day.close is not None and 
                curr_day.close < prev_day.close):
                falling_dates.append(curr_day.trade_date.strftime('%Y-%m-%d'))
                falling_days.append(curr_day)
            else:
                all_fall = False
                break
        
        # 如果满足所有条件，找到第一个就停止
        if all_fall and len(falling_dates) == z_days:
            strategy_name = (f'往前 {x_days} 天内涨幅大于 {y_pct}%，'
                            f'之后连续 {z_days} 天都是下跌')
            
            result = {
                'strategy': strategy_name,
                'rise_date': curr.trade_date.strftime('%Y-%m-%d'),
                'rise_pct': curr.change_pct,
                'rise_close': curr.close,
                'falling_dates': falling_dates,
                'details': {}
            }
            
            # 添加详细信息
            for idx, day in enumerate(falling_days):
                result['details'][f'fall_day{idx + 1}_date'] = day.trade_date.strftime('%Y-%m-%d')
                result['details'][f'fall_day{idx + 1}_close'] = day.close
                if idx > 0:
                    prev_fall = falling_days[idx - 1]
                    result['details'][f'fall_day{idx + 1}_change'] = round((day.close - prev_fall.close) / prev_fall.close * 100, 2)
            
            return result
    
    return None


def run_strategy_for_stock(
    db: Session,
    stock: StockBasic,
    strategy_name: str,
    x_days: int = 30,
    y_days: int = 10,
    z_days: int = 2,
    y_pct: float = 5.0
) -> Optional[dict]:
    """
    为单个股票运行策略
    
    :param db: 数据库会话
    :param stock: 股票信息
    :param strategy_name: 策略名称
    :param x_days: 往前找x天
    :param y_days: 往后找y天（用于consecutive_ma5策略）
    :param z_days: 连续z天（用于两个策略）
    :param y_pct: 涨幅大于y%（用于rise_then_fall策略）
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
    elif strategy_name == 'rise_then_fall':
        result = check_strategy_rise_then_fall(data, x_days, y_pct, z_days)
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
    z_days: int = 2,
    y_pct: float = 5.0
) -> List[dict]:
    """
    运行选股策略
    
    :param db: 数据库会话
    :param strategy_name: 策略名称
    :param min_market_cap: 最小市值（亿元）
    :param x_days: 往前找x天
    :param y_days: 往后找y天（用于consecutive_ma5策略）
    :param z_days: 连续z天（用于两个策略）
    :param y_pct: 涨幅大于y%（用于rise_then_fall策略）
    :return: 策略结果列表
    """
    # 获取所有股票
    query = db.query(StockBasic)
    
    # 如果有最小市值筛选，添加条件
    if min_market_cap:
        # 数据库单位是亿元，直接比较
        query = query.filter(StockBasic.total_cap >= min_market_cap)
    
    stocks = query.all()
    
    results = []
    total_count = len(stocks)
    
    # 遍历所有股票
    for idx, stock in enumerate(stocks):
        time.sleep(0.01)  # 避免太频繁
        
        result = run_strategy_for_stock(db, stock, strategy_name, x_days, y_days, z_days, y_pct)
        if result:
            results.append(result)
        
        # 每处理100个股票打印进度，或处理完最后一个时打印
        if (idx + 1) % 100 == 0 or idx + 1 == total_count:
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
            'display_name': '跌破布林下轨后连续站上5日线',
            'description': '从当前日期开始，往前最多找x天，找到第一个跌破布林下轨的日期，然后从这天开始再往后找，在y天内找到连续有z天收盘价都站上5天均线的票'
        },
        {
            'name': 'rise_then_fall',
            'display_name': '大涨后连续下跌',
            'description': '针对总市值大于p亿的股票，从当前日期往前查x天，对每一天做判断，查看当天收盘涨幅是否大于y%，且之后连续z天都是下跌'
        }
    ]
