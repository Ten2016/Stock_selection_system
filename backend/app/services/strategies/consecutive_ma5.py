"""跌破布林下轨后连续站上 5 日均线。

思路：先在近 x 天内找到一根收盘价跌破布林下轨的 K 线（超卖），
再看它之后 y 天内是否出现连续 z 天收盘价重新站上 MA5（企稳回升）。
"""

from typing import List, Optional

from .base import BaseStrategy, ParamSpec, StrategyMeta, tag


class ConsecutiveMa5Strategy(BaseStrategy):
    meta = StrategyMeta(
        name='consecutive_ma5',
        display_name='跌破布林下轨后连续站MA5',
        description='往前 x 天内跌破布林下轨，之后 y 天内连续 z 天站上 5 日均线',
        params=[
            ParamSpec('x_days', '最近', 30, '天内跌破布林下轨', minimum=1, maximum=500),
            ParamSpec('y_days', '之后', 10, '天内', minimum=1, maximum=500),
            ParamSpec('z_days', '连续', 2, '天站上 5 日均线', minimum=1, maximum=100),
        ],
    )

    def required_klines(self, x_days: int = 30, y_days: int = 10, z_days: int = 2) -> int:
        return max(self.min_klines, max(x_days, y_days, z_days) + 10)

    def check(self, klines: List, x_days: int = 30, y_days: int = 10, z_days: int = 2) -> Optional[dict]:
        if len(klines) < max(x_days, y_days, z_days) + 10:
            return None

        latest_idx = len(klines) - 1
        earliest_idx = max(0, latest_idx - x_days + 1)

        # 从最近的跌破日往前找，命中即返回最新的一次形态
        for i in range(latest_idx, earliest_idx - 1, -1):
            breakdown = klines[i]
            if breakdown.close is None or breakdown.boll_lower is None:
                continue
            if breakdown.close > breakdown.boll_lower:
                continue

            window_end = min(i + y_days, latest_idx)
            for start in range(i + 1, window_end - z_days + 2):
                streak = klines[start:start + z_days]
                if len(streak) < z_days:
                    break
                if not all(
                    bar.close is not None and bar.ma5 is not None and bar.close >= bar.ma5
                    for bar in streak
                ):
                    continue

                matching_dates = [bar.trade_date.strftime('%Y-%m-%d') for bar in streak]
                details = {}
                for idx, bar in enumerate(streak, start=1):
                    details[f'day{idx}_date'] = bar.trade_date.strftime('%Y-%m-%d')
                    details[f'day{idx}_close'] = bar.close
                    details[f'day{idx}_ma5'] = bar.ma5

                return {
                    'strategy': (f'往前 {x_days} 天内跌破布林下轨，'
                                 f'之后 {y_days} 天内连续 {z_days} 天站上 5 日均线'),
                    'breakdown_date': breakdown.trade_date.strftime('%Y-%m-%d'),
                    'breakdown_close': breakdown.close,
                    'boll_lower': breakdown.boll_lower,
                    'matching_dates': matching_dates,
                    'tags': [
                        tag(f'跌破 {breakdown.trade_date.strftime("%Y-%m-%d")}', 'warning'),
                        *[tag(d, 'success') for d in matching_dates],
                    ],
                    'details': details,
                }

        return None


STRATEGY = ConsecutiveMa5Strategy()
