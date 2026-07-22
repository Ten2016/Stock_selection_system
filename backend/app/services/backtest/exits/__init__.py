"""出场规则注册表：自动发现本目录下的所有规则模块。

约定与买入条件一致：每个模块导出 `STRATEGY` 实例。新增出场规则 = 新建一个文件。
"""

import importlib
import pkgutil
from typing import Dict, List, Optional

from ..base import BaseExitRule

_registry: Dict[str, BaseExitRule] = {}


def _discover() -> None:
    if _registry:
        return
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith('_'):
            continue
        module = importlib.import_module(f'{__name__}.{module_info.name}')
        rule = getattr(module, 'STRATEGY', None)
        if rule is None:
            continue
        if rule.meta.name in _registry:
            raise RuntimeError(f'出场规则标识重复：{rule.meta.name}')
        _registry[rule.meta.name] = rule


def get_exit_rule(name: str) -> Optional[BaseExitRule]:
    _discover()
    return _registry.get(name)


def all_exit_rules() -> List[BaseExitRule]:
    _discover()
    # 按优先级排序，前端展示顺序即触发优先级顺序
    return sorted(_registry.values(), key=lambda r: (r.meta.priority, r.meta.name))
