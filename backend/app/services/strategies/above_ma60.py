"""站上 60 日均线（中期趋势确认）。

思路：最近 y 天里，只要有 z 天收盘价站在 MA60 之上，
说明中期趋势已经转强或正在转强。
"""

from typing import List, Optional

from .base import BaseStrategy, ParamSpec, StrategyMeta, tag


class AboveMa60Strategy(BaseStrategy):
    meta = StrategyMeta(
        name='above_ma60',
        display_name='站上60日均线',
        description='最近 y 天内有 z 天站上 60 日均线',
        params=[
            ParamSpec('y_days', '最近', 5, '天内', minimum=1, maximum=500),
            ParamSpec('z_days', '有', 3, '天站上 60 日均线', minimum=1, maximum=500),
        ],
    )

    # MA60 需要 60 根才有值，再加上观察窗口
    min_klines = 80

    def check(self, klines: List, y_days: int = 5, z_days: int = 3) -> Optional[dict]:
        if len(klines) < y_days + 60:
            return None
        if z_days > y_days:
            return None

        window = klines[max(0, len(klines) - y_days):]
        above = [
            bar for bar in window
            if bar.close is not None and bar.ma60 is not None and bar.close >= bar.ma60
        ]

        if len(above) < z_days:
            return None

        above_dates = [bar.trade_date.strftime('%Y-%m-%d') for bar in above]
        details = {}
        for idx, bar in enumerate(window[:10], start=1):
            details[f'day{idx}_date'] = bar.trade_date.strftime('%Y-%m-%d')
            details[f'day{idx}_close'] = bar.close
            details[f'day{idx}_ma60'] = bar.ma60

        return {
            'strategy': f'最近 {y_days} 天内有 {z_days} 天站上 60 日均线',
            'above_ma60_dates': above_dates,
            'above_count': len(above_dates),
            'tags': [
                tag(f'站上60日线 {len(above_dates)} 天', 'success'),
                *[tag(d, 'info') for d in above_dates],
            ],
            'details': details,
        }


STRATEGY = AboveMa60Strategy()
