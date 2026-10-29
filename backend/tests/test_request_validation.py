import unittest

from pydantic import ValidationError

from app.api.backtest import BacktestConfigRequest, BacktestRequest, ExitGroupSpec
from app.utils.db_helpers import safe_like


class TestRequestValidation(unittest.TestCase):
    def test_stock_codes_are_deduplicated(self):
        request = BacktestRequest(stock_codes=['600000', '600000'], entry_name='above_ma60')
        self.assertEqual(request.stock_codes, ['600000'])

    def test_oversized_stock_pool_is_rejected(self):
        with self.assertRaises(ValidationError):
            BacktestRequest(stock_codes=[f'{i:06d}' for i in range(101)], entry_name='above_ma60')

    def test_invalid_capital_and_execution_are_rejected(self):
        for config in ({'initial_capital': -1}, {'initial_capital': float('nan')},
                       {'slippage_rate': 1}, {'execution': 'same_day'},
                       {'execution': 'next_open'}, {'exit_timing': 'same_day'},
                       {'check_price_limit': 'false'}):
            with self.subTest(config=config), self.assertRaises(ValidationError):
                BacktestConfigRequest(**config)
        with self.assertRaises(ValidationError):
            ExitGroupSpec(logic='unknown')

    def test_like_escapes_backslashes_before_wildcards(self):
        self.assertEqual(safe_like('A\\B%_'), 'A\\\\B\\%\\_')
