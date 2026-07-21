"""策略注册表：自动发现本包下的所有策略模块。

约定：每个策略模块在文件末尾导出一个 `STRATEGY` 实例（BaseStrategy 子类）。
新增策略 = 新建一个文件，无需在任何地方登记。
"""

import importlib
import pkgutil
from typing import Dict, List, Optional

from .base import BaseStrategy, ParamSpec, StrategyMeta, tag

# 不参与策略发现的基础模块
_INFRA_MODULES = {'base', 'common'}

_registry: Dict[str, BaseStrategy] = {}


def _discover() -> None:
    if _registry:
        return
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name in _INFRA_MODULES or module_info.name.startswith('_'):
            continue
        module = importlib.import_module(f'{__name__}.{module_info.name}')
        strategy = getattr(module, 'STRATEGY', None)
        if strategy is None:
            continue
        if strategy.meta.name in _registry:
            raise RuntimeError(f'策略标识重复：{strategy.meta.name}')
        _registry[strategy.meta.name] = strategy


def get_strategy(name: str) -> Optional[BaseStrategy]:
    _discover()
    return _registry.get(name)


def all_strategies() -> List[BaseStrategy]:
    _discover()
    # 按模块发现顺序不稳定，按显示名排序保证前端下拉顺序固定
    return sorted(_registry.values(), key=lambda s: s.meta.display_name)


__all__ = [
    'BaseStrategy', 'ParamSpec', 'StrategyMeta', 'tag',
    'get_strategy', 'all_strategies',
]
