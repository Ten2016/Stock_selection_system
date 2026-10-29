import unittest
from concurrent.futures import CancelledError
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlite3 import IntegrityError

from app.api.sync import _load_sync_context, _process_single_stock
from app.models.stock_kline import StockKline
from app.services import sync_service
from app.utils.data_migrations import ensure_kline_indexes


class TestSyncConsistency(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        self.addCleanup(self.engine.dispose)
        StockKline.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.db.close)
        self.days = [date(2020, 1, 1) + timedelta(days=i) for i in range(200)]
        self.db.add_all([
            StockKline(stock_code='600000', trade_date=day, open=10, close=10, high=10, low=10)
            for day in self.days
        ])
        self.db.commit()

    def frame(self, start=150, close=10):
        return pd.DataFrame({'trade_date': self.days[start:], 'close': close})

    def process(self, responses):
        with patch('app.api.sync.SessionLocal', side_effect=lambda: Session(self.engine)), \
                patch('app.api.sync.is_cancelled', return_value=False), \
                patch('app.api.sync.sync_service.fetch_one_stock_history', side_effect=responses) as fetch:
            result = _process_single_stock(SimpleNamespace(code='600000', name='示例'),
                                           self.days[150].isoformat(), self.days[170].isoformat(), set())
        return result, fetch

    def test_context_retains_all_history_and_refreshes_existing_tail(self):
        ctx = _load_sync_context(self.db, '600000', self.days[150], self.days[170])
        self.assertEqual(len(ctx['history']), 150)
        self.assertEqual(ctx['fetch_end'], self.days[-1])
        self.assertEqual(len(ctx['overlap']), 50)

    def test_long_gap_is_bridged_to_last_stored_day(self):
        future = self.days[-1] + timedelta(days=200)
        ctx = _load_sync_context(self.db, '600000', future, future + timedelta(days=90))
        self.assertEqual(ctx['fetch_start'], self.days[-1])
        self.assertIn(self.days[-1], ctx['overlap'])

    def test_new_stock_gets_indicator_history(self):
        ctx = _load_sync_context(self.db, '000001', self.days[150], self.days[170])
        self.assertEqual(ctx['fetch_start'], self.days[150] - timedelta(days=365))
        self.assertEqual(ctx['history'], [])

    def test_one_cent_drift_refreshes_entire_stored_range(self):
        result, fetch = self.process([self.frame(close=9.99), self.frame(0, close=9.99)])
        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['full_resync'])
        self.assertEqual(fetch.call_args.args[1:3], (self.days[0].isoformat(), self.days[-1].isoformat()))

    def test_incomplete_full_refresh_is_not_saved(self):
        full = self.frame(0, close=9)
        result, _ = self.process([self.frame(close=9), full.drop(index=10)])
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['kline_data'])
        self.assertIn('缺少 1 个已存交易日', result['reason'])

    def test_unchanged_prices_do_not_repeat_full_refresh_for_dividend_marker(self):
        frame = self.frame()
        frame['dividend_info'] = [{'event': '分红'}] * len(frame)
        result, fetch = self.process([frame])
        self.assertEqual(result['status'], 'success')
        self.assertFalse(result['full_resync'])
        self.assertEqual(fetch.call_count, 1)

    def test_idempotent_upsert_preserves_dividend_metadata(self):
        frame = pd.DataFrame([{
            'trade_date': self.days[0], 'open': 10, 'close': 10, 'high': 10, 'low': 10,
            'volume': 100, 'dividend_info': {'event': '分红'},
        }])
        with patch('app.services.sync_service.SessionLocal', side_effect=lambda: Session(self.engine)):
            self.assertEqual(sync_service.save_kline_batch([('600000', frame)])['row_count'], 1)
            frame['dividend_info'] = None
            self.assertEqual(sync_service.save_kline_batch([('600000', frame)])['row_count'], 0)
        saved = self.db.query(StockKline).filter(StockKline.trade_date == self.days[0]).one()
        self.assertEqual(saved.dividend_info, {'event': '分红'})

    def test_batch_failure_rolls_back_preceding_stock_updates(self):
        frame = pd.DataFrame([{
            'trade_date': self.days[0], 'open': 11, 'close': 11, 'high': 11, 'low': 11,
        }])
        invalid = frame.copy()
        invalid['close'] = None
        with patch('app.services.sync_service.SessionLocal', side_effect=lambda: Session(self.engine)):
            with self.assertRaises(IntegrityError):
                sync_service.save_kline_batch([('600000', frame), ('000001', invalid)])
        saved = self.db.query(StockKline).filter(StockKline.trade_date == self.days[0]).one()
        self.assertEqual(float(saved.close), 10)

    def test_index_cleanup_retains_unique_constraint_and_custom_indexes(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql('CREATE INDEX idx_stock_code_trade_date ON stock_kline(stock_code, trade_date)')
            conn.exec_driver_sql('CREATE INDEX ix_stock_kline_stock_code ON stock_kline(stock_code)')
            conn.exec_driver_sql('CREATE INDEX custom_date ON stock_kline(trade_date)')
            ensure_kline_indexes(conn)
            ensure_kline_indexes(conn)
            indexes = conn.exec_driver_sql('PRAGMA index_list("stock_kline")').fetchall()
        names = {row[1] for row in indexes}
        self.assertNotIn('idx_stock_code_trade_date', names)
        self.assertNotIn('ix_stock_kline_stock_code', names)
        self.assertIn('custom_date', names)
        self.assertTrue(any(row[2] for row in indexes))


class TestIndicatorContinuity(unittest.TestCase):
    @patch('app.services.sync_service.datetime')
    def test_unfinished_today_is_excluded(self, clock):
        clock.now.return_value = datetime(2026, 10, 27, 14, 59)
        self.assertEqual(sync_service.latest_completed_date(), date(2026, 10, 26))
        clock.now.return_value = datetime(2026, 10, 27, 15, 0)
        self.assertEqual(sync_service.latest_completed_date(), date(2026, 10, 27))

    @patch('app.services.sync_service._fetch_kline_paged')
    def test_incremental_indicators_equal_full_history_and_amount_is_unknown(self, fetch):
        days = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
        prices = [10 + (i % 17) / 10 for i in range(300)]
        raw = [[str(day), price, price, price, price, 1000] for day, price in zip(days, prices)]
        fetch.return_value = raw
        full = sync_service.fetch_one_stock_history('600000', str(days[0]), str(days[-1]))
        fetch.return_value = raw[200:]
        history = [{'trade_date': day, 'close': price} for day, price in zip(days[:210], prices[:210])]
        incremental = sync_service.fetch_one_stock_history('600000', str(days[200]), str(days[-1]), history)
        columns = ['trade_date', 'MA5', 'MA60', 'dif', 'dea', 'macd', 'change_pct', 'amplitude']
        assert_frame_equal(incremental[columns], full.iloc[200:][columns].reset_index(drop=True))
        self.assertTrue(incremental['amount'].isna().all())

    @patch('app.services.sync_service._fetch_kline_paged')
    def test_invalid_upstream_price_is_rejected(self, fetch):
        fetch.return_value = [['2020-01-01', '10', 'nan', '10', '10', '1000']]
        with self.assertRaisesRegex(ValueError, '无效数值'):
            sync_service.fetch_one_stock_history('600000', '2020-01-01', '2020-01-02')

    @patch('app.services.sync_service.is_cancelled', return_value=False)
    @patch('app.services.sync_service._fetch_kline_page')
    def test_paging_uses_minimum_date_instead_of_first_row(self, fetch, cancelled):
        fetch.side_effect = [
            [['2020-01-04', 10], ['2020-01-03', 10]],
            [['2020-01-02', 10], ['2020-01-01', 10]],
        ]
        with patch('app.services.sync_service.KLINE_PAGE_SIZE', 2):
            rows = sync_service._fetch_kline_paged('sh600000', date(2020, 1, 1), date(2020, 1, 4))
        self.assertEqual(len(rows), 4)
        self.assertEqual(fetch.call_args.args[2], '2020-01-02')

    @patch('app.services.sync_service.is_cancelled', side_effect=[False, True])
    @patch('app.services.sync_service._fetch_kline_page')
    def test_cancelled_paging_never_returns_a_partial_history(self, fetch, cancelled):
        fetch.return_value = [['2020-01-04', 10], ['2020-01-03', 10]]
        with patch('app.services.sync_service.KLINE_PAGE_SIZE', 2), self.assertRaises(CancelledError):
            sync_service._fetch_kline_paged('sh600000', date(2020, 1, 1), date(2020, 1, 4))
