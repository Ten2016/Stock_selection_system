import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.backtest.base import BacktestConfig, TradeCost
from app.services.backtest.engine import ExitGroup, run_backtest
from app.services.backtest.metrics import aggregate, summarize
from app.services.backtest.exits.below_ma import BelowMaExit
from app.services.backtest.exits.fixed_days import FixedDaysExit
from app.services.strategies.base import BaseStrategy, ParamSpec
from app.services.strategies.macd_green_pullback import MacdGreenPullbackStrategy


def make_bars(count=4, price=1.0):
    return [
        SimpleNamespace(
            trade_date=date(2020, 1, 1) + timedelta(days=i),
            open=price, close=price, high=price, low=price, change_pct=0, volume=1000,
        )
        for i in range(count)
    ]


class TestBacktestAccounting(unittest.TestCase):
    def test_warmup_is_excluded_from_trades_curve_and_metrics(self):
        bars = make_bars(count=260)
        bars[0].close = 0.5
        signals = {bars[119].trade_date.isoformat(), bars[120].trade_date.isoformat()}
        result = run_backtest('600000', '', bars, signals, [], BacktestConfig(), warmup=120)
        self.assertEqual(result.open_position['entry_date'], bars[121].trade_date.isoformat())
        self.assertEqual(result.trades, [])
        self.assertEqual([day for day, _ in result.equity_curve], [bar.trade_date for bar in bars[120:]])
        self.assertEqual(result.total_bars, 140)
        stats = summarize(result, 100_000)
        self.assertEqual(stats['bars'], 140)
        self.assertIsNone(stats['annual_return_pct'])
        self.assertEqual(stats['benchmark_return_pct'], 0)
        self.assertEqual(stats['exposure_pct'], round(139 / 140 * 100, 2))

    def test_only_warmup_data_has_no_curve_or_benchmark(self):
        result = run_backtest('600000', '', make_bars(), set(), [], BacktestConfig(), warmup=4)
        self.assertEqual(result.equity_curve, [])
        self.assertEqual(result.total_bars, 0)
        self.assertIsNone(result.benchmark_return_pct)

    def test_buy_reserves_fees_and_final_equity_matches_closed_trades(self):
        bars = make_bars(count=5)
        config = BacktestConfig(
            initial_capital=1000,
            cost=TradeCost(commission_rate=0, min_commission=5,
                           stamp_tax_rate=0, transfer_fee_rate=0, slippage_rate=0),
        )
        result = run_backtest('600000', '', bars, {bars[1].trade_date.isoformat()},
                              [ExitGroup('any', [(FixedDaysExit(), {'hold_days': 1})])], config)
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].shares, 900)
        self.assertEqual(result.equity_curve[-1][1], 990)
        stats = summarize(result, config.initial_capital)
        self.assertAlmostEqual(stats['final_equity'], config.initial_capital + stats['total_pnl'])
        self.assertEqual(stats['total_return_pct'], -1)

    def test_price_limit_check_can_be_disabled(self):
        bars = make_bars(price=10)
        for bar in bars[2:]:
            bar.change_pct = 10
        signals = {bars[1].trade_date.isoformat()}
        blocked = run_backtest('600000', '', bars, signals, [], BacktestConfig())
        allowed = run_backtest('600000', '', bars, signals, [], BacktestConfig(check_price_limit=False))
        self.assertEqual(blocked.trades, [])
        self.assertIsNotNone(allowed.open_position)

    def test_both_sides_execute_at_next_close(self):
        bars = make_bars(count=5, price=10)
        bars[2].open, bars[2].close = 8, 12
        bars[3].close = 13
        bars[4].open, bars[4].close = 15, 14
        result = run_backtest(
            '600000', '', bars, {bars[1].trade_date.isoformat()},
            [ExitGroup('any', [(FixedDaysExit(), {'hold_days': 1})])],
            BacktestConfig(cost=TradeCost(slippage_rate=0)),
        )
        trade = result.trades[0]
        self.assertEqual((trade.entry_date, trade.entry_price), (bars[2].trade_date, 12))
        self.assertEqual((trade.exit_date, trade.exit_price), (bars[4].trade_date, 14))

    def test_pending_exit_at_end_is_marked_without_forced_sale(self):
        bars = make_bars(price=10)
        result = run_backtest(
            '600000', '', bars, {bars[1].trade_date.isoformat()},
            [ExitGroup('any', [(FixedDaysExit(), {'hold_days': 1})])], BacktestConfig(),
        )
        self.assertEqual(result.trades, [])
        self.assertTrue(result.open_position['pending_exit'])
        stats = summarize(result, 100_000)
        self.assertEqual(stats['realized_pnl'], 0)
        self.assertEqual(stats['total_cost'], round(result.open_position['entry_fee'], 2))
        self.assertAlmostEqual(stats['final_equity'], 100_000 + stats['unrealized_pnl'])

    def test_last_bar_buy_signal_is_not_filled(self):
        bars = make_bars()
        result = run_backtest('600000', '', bars, {bars[-1].trade_date.isoformat()}, [], BacktestConfig())
        self.assertEqual(result.trades, [])
        self.assertIsNone(result.open_position)

    def test_zero_volume_cannot_fill_even_with_limit_check_disabled(self):
        bars = make_bars()
        bars[2].volume = 0
        bars[3].volume = None
        result = run_backtest('600000', '', bars, {bars[1].trade_date.isoformat()}, [],
                              BacktestConfig(check_price_limit=False))
        self.assertIsNone(result.open_position)

    def test_limit_close_blocks_fill_even_if_intraday_board_opened(self):
        bars = make_bars(count=6, price=10)
        bars[2].change_pct, bars[2].low = 10, 9
        bars[5].change_pct, bars[5].high = -10, 11
        result = run_backtest(
            '600000', '', bars, {bars[1].trade_date.isoformat()},
            [ExitGroup('any', [(FixedDaysExit(), {'hold_days': 1})])], BacktestConfig(),
        )
        self.assertEqual(result.open_position['entry_date'], bars[3].trade_date.isoformat())
        self.assertEqual(result.trades, [])
        self.assertTrue(result.open_position['pending_exit'])

    def test_exit_calculation_failure_is_not_treated_as_hold(self):
        bars = make_bars()
        rule = Mock()
        rule.should_exit.side_effect = ValueError('invalid indicator')
        with self.assertRaisesRegex(ValueError, 'invalid indicator'):
            run_backtest('600000', '', bars, {bars[1].trade_date.isoformat()},
                         [ExitGroup('any', [(rule, {})])], BacktestConfig())

    def test_empty_result_has_no_trade_metrics_and_sample_warning(self):
        result = aggregate([], [])
        self.assertEqual(result['stock_count'], 0)
        self.assertIsNone(result['pool']['expectancy_pct'])
        self.assertTrue(result['pool']['sample_warning'])

    def test_nonstored_ma_period_is_not_replaced_with_another_period(self):
        bars = make_bars(count=15, price=10)
        bars[-1].close = 9
        bars[-1].ma10 = 8
        self.assertEqual(BelowMaExit().should_exit(bars, None, ma_period=15), '跌破MA15')


class AlwaysMatches(BaseStrategy):
    min_klines = 2

    def check(self, klines, **params):
        return {'matched': True}


class TestStrategyBoundaries(unittest.TestCase):
    def test_future_start_year_has_no_signals(self):
        self.assertEqual(AlwaysMatches().find_signals(make_bars(), 2025), [])

    def test_first_sufficient_history_is_evaluated(self):
        bars = make_bars()
        signals = AlwaysMatches().find_signals(bars, 2020)
        self.assertEqual(signals[0]['date'], bars[1].trade_date.isoformat())

    def test_nonfinite_params_use_default(self):
        param = ParamSpec('threshold', '阈值', 2.0, param_type='float')
        for value in ('nan', 'inf', '-inf'):
            with self.subTest(value=value):
                self.assertEqual(param.coerce(value), 2.0)
        integer = ParamSpec('days', '天数', 5, maximum=500)
        self.assertEqual(integer.coerce(float('inf')), 5)
        self.assertEqual(integer.coerce(10 ** 1000), 500)


class TestMacdSignalHistory(unittest.TestCase):
    def make_wave_bars(self):
        bars = make_bars(count=67, price=10)
        for bar in bars:
            bar.macd = 0
            bar.low = 2
        for i, macd in {55: -3, 56: -2, 57: -1, 60: -4, 61: -3,
                        62: -2, 63: 1, 64: -0.5, 65: 1, 66: 2}.items():
            bars[i].macd = macd
        for bar in bars[55:58]:
            bar.low = 1
        return bars

    def test_tolerated_red_signal_does_not_depend_on_later_green_bar(self):
        bars = self.make_wave_bars()
        strategy = MacdGreenPullbackStrategy()
        complete = strategy.find_signals(bars, 2020, confirm_days=3)
        self.assertEqual([s['date'] for s in complete], [bars[63].trade_date.isoformat()])
        for length in range(60, len(bars) + 1):
            with self.subTest(length=length):
                expected = [s for s in complete if s['date'] <= bars[length - 1].trade_date.isoformat()]
                self.assertEqual(strategy.find_signals(bars[:length], 2020, confirm_days=3), expected)

    def test_future_green_bar_cannot_qualify_a_short_wave(self):
        bars = self.make_wave_bars()[:64]
        bars[62].macd = 1
        bars[63].macd = -2
        self.assertEqual(MacdGreenPullbackStrategy().find_signals(bars, 2020), [])

    def test_live_check_rejects_red_streak_beyond_tolerance(self):
        bars = self.make_wave_bars()[:65]
        bars[64].macd = 2
        self.assertIsNone(MacdGreenPullbackStrategy().check(bars, confirm_days=3))
