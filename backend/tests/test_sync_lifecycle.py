import copy
import queue
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.sync import _run_save_worker
from app.services import sync_service
from app.utils.sync_state import begin_sync, end_sync, request_cancel, sync_status


class TestSyncLifecycle(unittest.TestCase):
    def setUp(self):
        self.saved_state = copy.deepcopy(sync_status)
        sync_status['is_syncing'] = False
        begin_sync()

    def tearDown(self):
        sync_status.clear()
        sync_status.update(self.saved_state)

    def test_duplicate_start_preserves_running_task(self):
        sync_status['progress'] = 35
        request_cancel()
        self.assertFalse(begin_sync())
        self.assertEqual(sync_status['progress'], 35)
        self.assertTrue(sync_status['cancelled'])

    def test_failure_and_cancellation_are_not_reported_as_success(self):
        request_cancel()
        end_sync()
        self.assertEqual(sync_status['status'], 'cancelled')
        self.assertFalse(sync_status['is_syncing'])
        begin_sync()
        end_sync('磁盘写入失败')
        self.assertEqual(sync_status['status'], 'failed')
        self.assertEqual(sync_status['error_msg'], '磁盘写入失败')

    @patch('app.api.sync.sync_service.save_kline_batch', side_effect=RuntimeError('disk full'))
    def test_writer_failure_is_propagated_without_counting_success(self, save):
        pending = queue.Queue()
        pending.put(('600000', object()))
        pending.put(None)
        state = {'saved_codes': set(), 'error': None}
        _run_save_worker(pending, 1, state)
        self.assertEqual(str(state['error']), 'disk full')
        self.assertEqual(state['saved_codes'], set())

    @patch('app.api.sync.sync_service.save_kline_batch', return_value={'stock_count': 1, 'row_count': 1})
    def test_cancelled_writer_waits_for_end_marker_and_drains_queue(self, save):
        request_cancel()
        pending = MagicMock()
        pending.get.side_effect = [queue.Empty(), ('600000', object()), None]
        state = {'saved_codes': set(), 'error': None}
        _run_save_worker(pending, 40, state)
        self.assertEqual(state['saved_codes'], {'600000'})
        self.assertIsNone(state['error'])

    @patch('app.services.sync_service.fetch_all_stocks_basic_info', side_effect=RuntimeError('network error'))
    def test_basic_info_failure_releases_task(self, fetch):
        sync_service.run_basic_info_sync()
        self.assertFalse(sync_status['is_syncing'])
        self.assertEqual(sync_status['status'], 'failed')

    @patch('app.utils.data_migrations.repair_json_columns')
    @patch('app.services.sync_service.engine')
    @patch('app.services.sync_service.SessionLocal')
    def test_indicator_repair_preserves_source_fields(self, session_factory, engine, repair_json):
        db = session_factory.return_value.__enter__.return_value
        db.query.return_value.distinct.return_value.all.return_value = [('600000',)]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            SimpleNamespace(id=1, trade_date=date(2020, 1, 1), open=10, high=11,
                            low=9, close=10, volume=0),
        ]
        sync_service.run_repair_indicators()
        updates = db.bulk_update_mappings.call_args.args[1]
        self.assertEqual(updates[0]['id'], 1)
        self.assertIn('macd', updates[0])
        for field in ('amount', 'volume', 'dividend_info', 'open', 'close'):
            self.assertNotIn(field, updates[0])
        self.assertEqual(sync_status['status'], 'success')
