import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.stock import StockBasic
from app.models.stock_kline import StockKline
from app.services.backtest_service import _load_bars, run


class TestBacktestPeriod(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite:///:memory:')
        self.addCleanup(engine.dispose)
        StockBasic.__table__.create(engine)
        StockKline.__table__.create(engine)
        self.db = Session(engine)
        self.addCleanup(self.db.close)
        self.dates = [date(2020, 1, 1) + timedelta(days=i) for i in range(200)]
        self.db.add_all([
            StockKline(stock_code='600000', trade_date=day,
                       open=10, close=10, high=10, low=10, ma60=9, change_pct=0, volume=1000)
            for day in self.dates
        ])
        self.db.commit()

    def backtest(self, start, end, params=None):
        return run(self.db, ['600000'], 'above_ma60', entry_params=params,
                   exit_groups=[{'rules': [{'name': 'fixed_days'}]}],
                   start_date=start, end_date=end)

    def test_loader_uses_nearest_history_and_respects_end_date(self):
        bars = _load_bars(self.db, '600000', self.dates[150], self.dates[169])
        self.assertEqual([bar.trade_date for bar in bars], self.dates[30:170])

    def test_selected_period_is_not_consumed_by_warmup(self):
        result = self.backtest(self.dates[150], self.dates[169])
        self.assertEqual(result['skipped'], [])
        detail = result['details']['600000']
        self.assertEqual([point['date'] for point in detail['equity_curve']],
                         [day.isoformat() for day in self.dates[150:170]])
        self.assertEqual(detail['trades'][0]['entry_date'], self.dates[151].isoformat())
        self.assertEqual(result['per_stock'][0]['bars'], 20)

    def test_insufficient_prior_history_does_not_shift_start(self):
        result = self.backtest(self.dates[100], self.dates[199])
        self.assertEqual(result['per_stock'], [])
        self.assertIn('预热K线不足（100 根，至少需 120 根）', result['skipped'][0]['reason'])

    def test_long_strategy_window_requires_more_history(self):
        result = self.backtest(self.dates[150], self.dates[169], {'y_days': 100})
        self.assertEqual(result['per_stock'], [])
        self.assertIn('至少需 159 根', result['skipped'][0]['reason'])
        sufficient = self.backtest(self.dates[170], self.dates[189], {'y_days': 100})
        self.assertEqual(sufficient['skipped'], [])
        self.assertEqual(sufficient['details']['600000']['trades'][0]['entry_date'],
                         self.dates[171].isoformat())

    def test_unspecified_start_uses_first_bars_for_warmup(self):
        result = self.backtest(None, self.dates[139])
        self.assertEqual(result['skipped'], [])
        self.assertEqual(result['details']['600000']['equity_curve'][0]['date'],
                         self.dates[120].isoformat())
        self.assertEqual(result['per_stock'][0]['bars'], 20)
