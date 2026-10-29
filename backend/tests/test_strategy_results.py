import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.strategies import get_latest_strategy_result, select_stocks
from app.models.strategy_result import StrategyResult


class TestStrategyResults(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite:///:memory:')
        self.addCleanup(engine.dispose)
        StrategyResult.__table__.create(engine)
        self.db = Session(engine)
        self.addCleanup(self.db.close)
        self.db.add(StrategyResult(
            strategy_name='above_ma60', run_date=date(2020, 1, 1),
            params={'min_market_cap': 100}, total_count=1,
            results=[{'code': '600000'}],
        ))
        self.db.commit()

    def test_empty_success_replaces_old_result_and_preserves_params(self):
        with patch('app.api.strategies.strategy_service.run_strategy', return_value=[]):
            response = select_stocks(SimpleNamespace(query_params={'y_days': '10'}),
                                     'above_ma60', None, self.db)
        self.assertEqual(response.code, 0)
        self.assertEqual(self.db.query(StrategyResult).count(), 1)
        saved = get_latest_strategy_result('above_ma60', self.db).data
        self.assertEqual(saved['run_date'], date.today().isoformat())
        self.assertEqual(saved['selected_stocks'], [])
        self.assertEqual(saved['total_count'], 0)
        self.assertEqual(saved['params']['y_days'], 10)
        self.assertIsNone(saved['params']['min_market_cap'])

    def test_failed_selection_preserves_previous_result(self):
        with patch('app.api.strategies.strategy_service.run_strategy', side_effect=ValueError('失败')):
            response = select_stocks(SimpleNamespace(query_params={}), 'above_ma60', None, self.db)
        self.assertNotEqual(response.code, 0)
        saved = get_latest_strategy_result('above_ma60', self.db).data
        self.assertEqual(saved['selected_stocks'], [{'code': '600000'}])
        self.assertEqual(saved['run_date'], '2020-01-01')

    def test_never_run_strategy_has_no_run_date(self):
        saved = get_latest_strategy_result('rise_then_fall', self.db).data
        self.assertIsNone(saved['run_date'])
        self.assertIsNone(saved['params'])
        self.assertEqual(saved['selected_stocks'], [])
