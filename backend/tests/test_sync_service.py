import unittest
import time
import random
from unittest.mock import patch, MagicMock
import sys
import os
import pandas as pd
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.services import sync_service


class TestTencentFinanceAPI(unittest.TestCase):
    
    def test_delay_constants_exist(self):
        self.assertTrue(hasattr(sync_service, 'REQUEST_DELAY_MIN'))
        self.assertTrue(hasattr(sync_service, 'REQUEST_DELAY_MAX'))
        self.assertGreaterEqual(sync_service.REQUEST_DELAY_MIN, 0.5)
        self.assertGreaterEqual(sync_service.REQUEST_DELAY_MAX, sync_service.REQUEST_DELAY_MIN)
        print(f"\n[OK] Delay constants exist: MIN={sync_service.REQUEST_DELAY_MIN}s, MAX={sync_service.REQUEST_DELAY_MAX}s")
    
    def test_get_stock_prefix(self):
        self.assertEqual(sync_service._get_stock_prefix('600000'), 'sh')
        self.assertEqual(sync_service._get_stock_prefix('000001'), 'sz')
        self.assertEqual(sync_service._get_stock_prefix('300001'), 'sz')
        print("\n[OK] Stock prefix function works correctly")
    
    def test_tencent_api_accessible(self):
        import requests
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600000,day,2025-01-01,2025-01-10,10,qfq"
        headers = {"Referer": "https://finance.qq.com"}
        response = requests.get(url, headers=headers, timeout=10)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('code'), 0)
        print(f"\n[OK] Tencent Finance API is accessible")
    
    @patch('app.services.sync_service.time.sleep')
    @patch('app.services.sync_service.random.uniform')
    def test_fetch_one_stock_history_has_delay(self, mock_uniform, mock_sleep):
        mock_uniform.return_value = 1.5
        
        mock_response_data = {
            "code": 0,
            "msg": "",
            "data": {
                "sh600000": {
                    "qfqday": [
                        ["2025-01-01", "10.0", "10.2", "10.5", "9.8", "1000"],
                        ["2025-01-02", "10.2", "10.5", "10.8", "10.0", "1200"]
                    ]
                }
            }
        }
        
        with patch('app.services.sync_service.get_existing_dates', return_value=set()):
            with patch('app.services.sync_service.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_response_data
                mock_response.encoding = 'utf-8'
                mock_get.return_value = mock_response
                
                with patch('app.services.sync_service.calculate_all_indicators', side_effect=lambda df: df):
                    sync_service.fetch_one_stock_history('600000', '2025-01-01', '2025-01-10')
                    
                    mock_uniform.assert_called_once_with(
                        sync_service.REQUEST_DELAY_MIN, 
                        sync_service.REQUEST_DELAY_MAX
                    )
                    mock_sleep.assert_called_once_with(1.5)
                    print("\n[OK] fetch_one_stock_history calls delay before API request")


class TestCodeSyntax(unittest.TestCase):
    
    def test_sync_service_imports(self):
        try:
            from app.services import sync_service
            self.assertTrue(hasattr(sync_service, 'fetch_all_stocks_basic_info'))
            self.assertTrue(hasattr(sync_service, 'fetch_one_stock_history'))
            self.assertTrue(hasattr(sync_service, 'REQUEST_DELAY_MIN'))
            self.assertTrue(hasattr(sync_service, 'REQUEST_DELAY_MAX'))
            self.assertTrue(hasattr(sync_service, '_get_stock_prefix'))
            print("\n[OK] sync_service module imports successfully with all required functions")
        except Exception as e:
            self.fail(f"Failed to import sync_service: {e}")
    
    def test_sync_api_imports(self):
        try:
            from app.api import sync
            self.assertTrue(hasattr(sync, 'run_sync_task'))
            self.assertTrue(hasattr(sync, 'router'))
            print("\n[OK] sync API module imports successfully")
        except Exception as e:
            self.fail(f"Failed to import sync API: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
