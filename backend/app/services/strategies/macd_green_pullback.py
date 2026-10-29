"""MACD 绿柱拐点 + 股价底部抬高（上升通道）。

思路：把 MACD 柱为负的连续区间视为一个「绿柱波段」。当最新波段的绿柱从谷底
开始持续缩短（动能衰竭），且这一波的最低价高于上一波的最低价（底部抬高），
说明下跌动能减弱且重心上移，是上升通道中的回调买点。
"""

from typing import List, Optional

from .base import BaseStrategy, ParamSpec, StrategyMeta, tag


def find_green_waves(klines: List, min_days: int = 3, tolerate_red: int = 1) -> List[dict]:
    """切分出所有绿柱波段。波段内允许夹杂至多 tolerate_red 天红柱，避免被单日反弹打断。"""
    waves = []
    n = len(klines)
    i = 0

    while i < n:
        macd = klines[i].macd
        if macd is None or macd >= 0:
            i += 1
            continue

        start_idx = i
        end_idx = i
        valley_idx = i
        valley_macd = macd
        min_low = klines[i].low
        min_low_date = klines[i].trade_date

        red_streak = 0
        j = i + 1

        while j < n:
            bar = klines[j]
            if bar.macd is not None and bar.macd < 0:
                red_streak = 0
                end_idx = j
                if bar.macd < valley_macd:
                    valley_idx = j
                    valley_macd = bar.macd
                if bar.low is not None and (min_low is None or bar.low < min_low):
                    min_low = bar.low
                    min_low_date = bar.trade_date
            else:
                red_streak += 1
                if red_streak > tolerate_red:
                    break
            j += 1

        if end_idx - start_idx + 1 >= min_days:
            waves.append({
                'start_idx': start_idx,
                'end_idx': end_idx,
                'valley_idx': valley_idx,
                'valley_macd': valley_macd,
                'min_low': min_low,
                'min_low_date': min_low_date,
            })

        i = j

    return waves


def _is_shortening(klines: List, valley_idx: int, until_idx: int) -> bool:
    """谷底之后绿柱是否逐日缩短（MACD 柱单调不降）。"""
    for k in range(valley_idx + 1, until_idx + 1):
        curr, prev = klines[k].macd, klines[k - 1].macd
        if curr is None or prev is None or curr < prev:
            return False
    return True


def _build_result(klines, wave, prev_wave, valley_idx, signal_idx, y_days, confirm_days) -> dict:
    low_diff_pct = round(
        (float(wave['min_low']) - float(prev_wave['min_low'])) / float(prev_wave['min_low']) * 100, 2
    )
    valley_date = klines[valley_idx].trade_date.strftime('%Y-%m-%d')

    return {
        'strategy': (f'MACD绿柱拐点上升通道：最近 {y_days} 天内出现绿柱拐点，'
                     f'缩短 {confirm_days} 天确认，股价一底比一底高'),
        'valley_date': valley_date,
        'valley_macd': float(wave['valley_macd']) if wave['valley_macd'] is not None else None,
        'shortening_days': signal_idx - valley_idx,
        'current_min_low': float(wave['min_low']),
        'current_min_low_date': wave['min_low_date'].strftime('%Y-%m-%d'),
        'prev_min_low': float(prev_wave['min_low']),
        'prev_min_low_date': prev_wave['min_low_date'].strftime('%Y-%m-%d'),
        'low_diff_pct': low_diff_pct,
        'tags': [
            tag(f'拐点 {valley_date}', 'success'),
            tag(f'已缩短 {signal_idx - valley_idx} 天', 'warning'),
            tag(f'底部抬高 {low_diff_pct}%', 'success'),
        ],
        'details': {
            'prev_min_low': float(prev_wave['min_low']),
            'prev_min_low_date': prev_wave['min_low_date'].strftime('%Y-%m-%d'),
            'current_min_low': float(wave['min_low']),
            'current_min_low_date': wave['min_low_date'].strftime('%Y-%m-%d'),
        },
    }


def _lows_rising(wave, prev_wave) -> bool:
    if wave['min_low'] is None or prev_wave['min_low'] is None:
        return False
    return wave['min_low'] > prev_wave['min_low']


def _min_low_until(klines: List, start_idx: int, until_idx: int):
    """截至 until_idx 为止的波段最低价。

    `find_green_waves` 给出的 min_low 是**整个波段**的最低价，而波段结束点可能
    晚于买点——在买点当天用它就是未来函数。回测必须只用已经发生的部分。
    """
    lows = [
        klines[k].low for k in range(start_idx, min(until_idx, len(klines) - 1) + 1)
        if klines[k].low is not None and klines[k].macd is not None and klines[k].macd < 0
    ]
    if not lows:
        return None, None
    min_low = min(lows)
    for k in range(start_idx, min(until_idx, len(klines) - 1) + 1):
        if klines[k].low == min_low and klines[k].macd is not None and klines[k].macd < 0:
            return min_low, klines[k].trade_date
    return min_low, None


class MacdGreenPullbackStrategy(BaseStrategy):
    meta = StrategyMeta(
        name='macd_green_pullback',
        display_name='MACD绿柱拐点上升通道',
        description='绿柱拐点后缩短确认，股价一底比一底高',
        params=[
            ParamSpec('y_days', '最近', 5, '天内出现绿柱拐点', minimum=1, maximum=200),
            ParamSpec('confirm_days', '缩短确认', 2, '天', minimum=1, maximum=60),
            ParamSpec('min_wave_days', '绿柱波段至少', 3, '天', minimum=1, maximum=60),
            ParamSpec('tolerate_red', '波段内容忍红柱', 1, '天', minimum=0, maximum=10),
        ],
    )

    min_klines = 60

    def check(
        self, klines: List, y_days: int = 5, confirm_days: int = 2,
        min_wave_days: int = 3, tolerate_red: int = 1,
    ) -> Optional[dict]:
        if len(klines) < self.min_klines:
            return None

        waves = find_green_waves(klines, min_days=min_wave_days, tolerate_red=tolerate_red)
        if len(waves) < 2:
            return None

        wave, prev_wave = waves[-1], waves[-2]
        latest_idx = len(klines) - 1
        valley_idx = wave['valley_idx']

        if latest_idx - wave['end_idx'] > tolerate_red:
            return None
        if not (confirm_days <= latest_idx - valley_idx <= y_days):
            return None
        if not _is_shortening(klines, valley_idx, latest_idx):
            return None
        if not _lows_rising(wave, prev_wave):
            return None

        return _build_result(klines, wave, prev_wave, valley_idx, latest_idx, y_days, confirm_days)

    def find_signals(
        self, klines: List, start_year: int, y_days: int = 5, confirm_days: int = 2,
        min_wave_days: int = 3, tolerate_red: int = 1,
    ) -> List[dict]:
        """按波段扫描历史买点。

        比基类的逐日重放快一个数量级：绿柱波段只需切分一次。

        **但波段的谷底和最低价都必须按「截至当日」重新求**——`find_green_waves`
        给出的 valley_idx / min_low 是整个波段的极值，而波段结束点可能晚于买点。
        直接拿来用会让买点依赖尚未发生的行情（已被截断测试抓到过两次）。
        """
        waves = find_green_waves(klines, min_days=min_wave_days, tolerate_red=tolerate_red)
        signals = []
        last_idx = len(klines) - 1

        for idx in range(1, len(waves)):
            wave, prev_wave = waves[idx], waves[idx - 1]
            start = wave['start_idx']

            # 上一波段完全在过去，可以直接用它的极值
            if prev_wave['min_low'] is None:
                continue

            running_valley = start
            running_macd = klines[start].macd
            known_end = start

            for j in range(start, min(wave['end_idx'] + tolerate_red, last_idx) + 1):
                macd = klines[j].macd
                if macd is not None and macd < 0:
                    known_end = j

                # 刚创出新低 → 谷底右移，当日不可能是「缩短确认」点
                if macd is not None and (running_macd is None or macd < running_macd):
                    running_valley, running_macd = j, macd
                    continue

                # 波段长度、确认天数、时效窗口都按截至 j 的已知信息判定
                if known_end - start + 1 < min_wave_days or j + 1 < self.min_klines:
                    continue
                if not (confirm_days <= j - running_valley <= y_days):
                    continue
                if klines[j].trade_date.year < start_year:
                    continue
                if not _is_shortening(klines, running_valley, j):
                    continue

                min_low, min_low_date = _min_low_until(klines, start, j)
                wave_so_far = {
                    **wave, 'min_low': min_low, 'min_low_date': min_low_date,
                    'valley_idx': running_valley, 'valley_macd': running_macd,
                }
                if not _lows_rising(wave_so_far, prev_wave):
                    continue

                bar = klines[j]
                signals.append({
                    'date': bar.trade_date.strftime('%Y-%m-%d'),
                    'close': float(bar.close) if bar.close is not None else None,
                    **_build_result(klines, wave_so_far, prev_wave, running_valley, j,
                                    y_days, confirm_days),
                })
                break   # 每个波段只取第一个买点

        return signals


STRATEGY = MacdGreenPullbackStrategy()
