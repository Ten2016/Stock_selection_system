from typing import List, Optional

from app.models.stock_kline import StockKline


def check_rise_then_fall(klines: List[StockKline], x_days: int = 30, y_pct: float = 5.0, z_days: int = 3) -> Optional[dict]:
    if len(klines) < x_days + z_days + 5:
        return None

    latest_idx = len(klines) - 1
    start_idx = max(0, latest_idx - x_days + 1)

    for i in range(latest_idx, start_idx - 1, -1):
        curr = klines[i]

        if curr.change_pct is not None and curr.change_pct > y_pct:
            end_idx = i + z_days

            if end_idx >= len(klines):
                continue

            all_fall = True
            falling_dates = []

            for k in range(i + 1, end_idx + 1):
                if k >= len(klines):
                    all_fall = False
                    break

                curr_day = klines[k]
                prev_day = klines[k - 1]

                if (curr_day.close is not None and prev_day.close is not None and
                        curr_day.close < prev_day.close):
                    falling_dates.append(curr_day.trade_date.strftime('%Y-%m-%d'))
                else:
                    all_fall = False
                    break

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

                for idx, day in enumerate(falling_dates):
                    result['details'][f'fall_day{idx + 1}_date'] = day
                    result['details'][f'fall_day{idx + 1}_close'] = klines[i + 1 + idx].close
                    if idx > 0:
                        prev_close = klines[i + idx].close
                        curr_close = klines[i + 1 + idx].close
                        if prev_close and curr_close:
                            result['details'][f'fall_day{idx + 1}_change'] = round(
                                (curr_close - prev_close) / prev_close * 100, 2
                            )

                return result

    return None
