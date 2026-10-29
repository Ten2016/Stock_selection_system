"""大涨之后连续下跌（回调买点）。

思路：在近 x 天内找到一根涨幅超过 y% 的大阳线，
之后紧接着连续 z 天收盘价逐日走低，视为放量拉升后的健康回调。
"""

from typing import List, Optional

from .base import BaseStrategy, ParamSpec, StrategyMeta, tag


class RiseThenFallStrategy(BaseStrategy):
    meta = StrategyMeta(
        name='rise_then_fall',
        display_name='大涨后连续下跌',
        description='往前 x 天内涨幅大于 y%，之后连续 z 天都是下跌',
        params=[
            ParamSpec('x_days', '往前', 30, '天', minimum=1, maximum=500),
            ParamSpec('y_pct', '涨幅大于', 5.0, '%', param_type='float', minimum=0.1, maximum=100, step=0.5),
            ParamSpec('z_days', '连续', 3, '天下跌', minimum=1, maximum=100),
        ],
    )

    def required_klines(self, x_days: int = 30, z_days: int = 3, **params) -> int:
        return max(self.min_klines, x_days + z_days + 5)

    def check(self, klines: List, x_days: int = 30, y_pct: float = 5.0, z_days: int = 3) -> Optional[dict]:
        if len(klines) < x_days + z_days + 5:
            return None

        latest_idx = len(klines) - 1
        earliest_idx = max(0, latest_idx - x_days + 1)

        for i in range(latest_idx, earliest_idx - 1, -1):
            rise_bar = klines[i]
            if rise_bar.change_pct is None or rise_bar.change_pct <= y_pct:
                continue

            end_idx = i + z_days
            if end_idx > latest_idx:
                continue

            falling = klines[i + 1:end_idx + 1]
            if not all(
                bar.close is not None and prev.close is not None and bar.close < prev.close
                for prev, bar in zip(klines[i:end_idx], falling)
            ):
                continue

            falling_dates = [bar.trade_date.strftime('%Y-%m-%d') for bar in falling]
            details = {}
            for idx, bar in enumerate(falling, start=1):
                details[f'fall_day{idx}_date'] = bar.trade_date.strftime('%Y-%m-%d')
                details[f'fall_day{idx}_close'] = bar.close
                prev_close = klines[i + idx - 1].close
                if idx > 1 and prev_close and bar.close:
                    details[f'fall_day{idx}_change'] = round(
                        (bar.close - prev_close) / prev_close * 100, 2
                    )

            return {
                'strategy': f'往前 {x_days} 天内涨幅大于 {y_pct}%，之后连续 {z_days} 天都是下跌',
                'rise_date': rise_bar.trade_date.strftime('%Y-%m-%d'),
                'rise_pct': rise_bar.change_pct,
                'rise_close': rise_bar.close,
                'falling_dates': falling_dates,
                'tags': [
                    tag(f'大涨 {rise_bar.trade_date.strftime("%Y-%m-%d")} ({rise_bar.change_pct}%)', 'danger'),
                    *[tag(d, 'info') for d in falling_dates],
                ],
                'details': details,
            }

        return None


STRATEGY = RiseThenFallStrategy()
