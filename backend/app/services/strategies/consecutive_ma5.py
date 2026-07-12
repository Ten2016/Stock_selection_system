from typing import List, Optional

from app.models.stock_kline import StockKline


def check_consecutive_ma5(klines: List[StockKline], x_days: int = 30, y_days: int = 10, z_days: int = 2) -> Optional[dict]:
    if len(klines) < max(x_days, y_days, z_days) + 10:
        return None

    latest_idx = len(klines) - 1
    start_idx = max(0, latest_idx - x_days + 1)

    for i in range(latest_idx, start_idx - 1, -1):
        curr = klines[i]

        if (curr.close is not None and curr.boll_lower is not None and
                curr.close <= curr.boll_lower):

            end_j = min(i + y_days, len(klines) - 1)

            for j in range(i + 1, end_j - z_days + 2):
                all_above = True
                matching_dates = []

                for k in range(j, j + z_days):
                    if k >= len(klines):
                        all_above = False
                        break

                    day = klines[k]
                    if (day.close is not None and day.ma5 is not None and
                            day.close >= day.ma5):
                        matching_dates.append(day.trade_date.strftime('%Y-%m-%d'))
                    else:
                        all_above = False
                        break

                if all_above and len(matching_dates) == z_days:
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

                    for idx, day in enumerate(matching_dates):
                        result['details'][f'day{idx + 1}_date'] = day
                        result['details'][f'day{idx + 1}_close'] = klines[j + idx].close
                        result['details'][f'day{idx + 1}_ma5'] = klines[j + idx].ma5

                    return result

    return None
