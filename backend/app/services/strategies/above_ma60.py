from typing import List, Optional

from app.models.stock_kline import StockKline


def check_above_ma60(klines: List[StockKline], y_days: int = 20, z_days: int = 10) -> Optional[dict]:
    if len(klines) < y_days + 60:
        return None

    latest_idx = len(klines) - 1
    start_idx = max(0, latest_idx - y_days + 1)

    above_ma60_dates = []

    for i in range(start_idx, latest_idx + 1):
        day = klines[i]
        if (day.close is not None and day.ma60 is not None and
                day.close >= day.ma60):
            above_ma60_dates.append(day.trade_date.strftime('%Y-%m-%d'))

    if len(above_ma60_dates) >= z_days:
        strategy_name = f'最近 {y_days} 天内有 {z_days} 天站上 60 日均线'

        result = {
            'strategy': strategy_name,
            'above_ma60_dates': above_ma60_dates,
            'above_count': len(above_ma60_dates),
            'details': {}
        }

        for idx, day in enumerate(klines[start_idx:start_idx + 10]):
            result['details'][f'day{idx + 1}_date'] = day.trade_date.strftime('%Y-%m-%d')
            result['details'][f'day{idx + 1}_close'] = day.close
            result['details'][f'day{idx + 1}_ma60'] = day.ma60

        return result

    return None
