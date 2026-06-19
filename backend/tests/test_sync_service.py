import unittest
import sys
import os
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services import sync_service
from app.utils.rate_limiter import RateLimiter


class TestRateLimiter(unittest.TestCase):

    def test_rate_limiter_interval(self):
        limiter = RateLimiter(10.0)
        self.assertEqual(limiter._min_interval, 0.1)


class TestTencentFinanceAPI(unittest.TestCase):

    def test_delay_constants_exist(self):
        self.assertTrue(hasattr(sync_service, 'REQUEST_DELAY_MIN'))
        self.assertTrue(hasattr(sync_service, 'REQUEST_DELAY_MAX'))
        self.assertGreater(sync_service.REQUEST_DELAY_MAX, sync_service.REQUEST_DELAY_MIN)
        self.assertGreater(sync_service.KLINE_API_RATE_PER_SECOND, 0)

    def test_get_stock_prefix(self):
        self.assertEqual(sync_service._get_stock_prefix('600000'), 'sh')
        self.assertEqual(sync_service._get_stock_prefix('000001'), 'sz')
        self.assertEqual(sync_service._get_stock_prefix('300001'), 'sz')

    def test_tencent_api_accessible(self):
        import requests
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600000,day,2025-01-01,2025-01-10,10,qfq"
        headers = {"Referer": "https://finance.qq.com"}
        response = requests.get(url, headers=headers, timeout=10)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('code'), 0)

    @patch('app.services.sync_service.requests.get')
    @patch('app.services.sync_service._kline_rate_limiter')
    def test_fetch_one_stock_history_uses_rate_limiter(self, mock_limiter, mock_get):
        mock_limiter.acquire = MagicMock()
        mock_response_data = {
            "code": 0,
            "msg": "",
            "data": {
                "sh600000": {
                    "qfqday": [
                        ["2025-01-01", "10.0", "10.2", "10.5", "9.8", "1000"],
                        ["2025-01-02", "10.2", "10.5", "10.8", "10.0", "1200"],
                    ]
                }
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.encoding = 'utf-8'
        mock_get.return_value = mock_response

        with patch('app.services.sync_service.calculate_all_indicators', side_effect=lambda df: df):
            sync_service.fetch_one_stock_history('600000', '2025-01-01', '2025-01-10')

        mock_limiter.acquire.assert_called_once()
        mock_get.assert_called_once()


class TestSaveKlineBatch(unittest.TestCase):

    def test_df_to_rows_builds_tuple(self):
        df = pd.DataFrame({
            'trade_date': [pd.Timestamp('2025-01-01').date()],
            'open': [10.0],
            'high': [10.5],
            'low': [9.8],
            'close': [10.2],
            'volume': [1000.0],
            'amount': [10200.0],
            'amplitude': [5.0],
            'change_pct': [1.0],
            'MA5': [10.0],
            'MA10': [10.0],
            'MA20': [10.0],
            'MA30': [10.0],
            'MA60': [10.0],
            'MA120': [10.0],
            'boll_upper': [11.0],
            'boll_mid': [10.0],
            'boll_lower': [9.0],
            'dividend_info': [None],
        })
        rows = sync_service._df_to_rows('600000', df)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], '600000')
        self.assertEqual(rows[0][1], pd.Timestamp('2025-01-01').date())

    def test_save_kline_batch_empty(self):
        result = sync_service.save_kline_batch([])
        self.assertEqual(result['row_count'], 0)
        self.assertEqual(result['stock_count'], 0)


class TestCodeSyntax(unittest.TestCase):

    def test_sync_service_imports(self):
        from app.services import sync_service as svc
        self.assertTrue(hasattr(svc, 'fetch_all_stocks_basic_info'))
        self.assertTrue(hasattr(svc, 'fetch_one_stock_history'))
        self.assertTrue(hasattr(svc, 'save_kline_batch'))
        self.assertTrue(hasattr(svc, 'KLINE_UPSERT_SQL'))

    def test_sync_api_imports(self):
        from app.api import sync
        self.assertTrue(hasattr(sync, 'run_sync_task'))
        self.assertTrue(hasattr(sync, 'router'))

    def test_sync_state_module(self):
        from app.utils.sync_state import sync_status, is_cancelled, begin_sync
        self.assertIn('is_syncing', sync_status)
        self.assertFalse(is_cancelled())


if __name__ == '__main__':
    unittest.main(verbosity=2)
