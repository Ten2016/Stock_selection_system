"""策略基础设施：参数声明、元数据、基类。

新增策略只需在本目录下建一个模块，定义 `STRATEGY = YourStrategy()`，
注册表会自动发现它，API 层与前端表单都无需改动。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ParamSpec:
    """一个策略参数的完整声明，同时驱动后端校验与前端表单渲染。"""

    name: str                      # API 参数名（snake_case）
    label: str                     # 前端表单前缀文案
    default: Any
    suffix: str = ''               # 前端表单后缀文案（单位/说明）
    param_type: str = 'int'        # 'int' | 'float'
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: float = 1

    def coerce(self, raw: Any) -> Any:
        """把外部传入的原始值转换并夹取到合法区间；无法解析时回落到默认值。"""
        if raw is None or raw == '':
            return self.default
        try:
            value = int(raw) if self.param_type == 'int' else float(raw)
        except (TypeError, ValueError):
            return self.default
        if self.minimum is not None:
            value = max(value, self.minimum)
        if self.maximum is not None:
            value = min(value, self.maximum)
        return int(value) if self.param_type == 'int' else float(value)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'label': self.label,
            'default': self.default,
            'suffix': self.suffix,
            'type': self.param_type,
            'min': self.minimum,
            'max': self.maximum,
            'step': self.step,
        }


@dataclass(frozen=True)
class StrategyMeta:
    name: str
    display_name: str
    description: str
    params: List[ParamSpec] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'params': [p.to_dict() for p in self.params],
        }


def tag(text: str, tone: str = 'info') -> dict:
    """构造一个前端通用渲染的结果标签。tone 对应 Element Plus 的 tag type。"""
    return {'text': text, 'tone': tone}


class BaseStrategy:
    """策略基类。

    子类必须提供 `meta` 与 `check()`。`check()` 只判断「最后一根 K 线所在时点是否命中」，
    回测由基类默认实现逐日重放得到；若某策略有更高效或语义更准确的历史扫描方式，
    覆写 `find_signals()` 即可。
    """

    meta: StrategyMeta

    # check() 需要的最少 K 线根数，不足则直接跳过该股票
    min_klines: int = 20

    def check(self, klines: List, **params) -> Optional[dict]:
        raise NotImplementedError

    def find_signals(self, klines: List, start_year: int, **params) -> List[dict]:
        """默认回测：从 start_year 起逐日重放 check()，同一天只记一个信号。"""
        signals = []
        prev_date = None

        start_idx = next(
            (i for i, bar in enumerate(klines) if bar.trade_date.year >= start_year), 0
        )
        start_idx = max(start_idx, self.min_klines)

        for i in range(start_idx, len(klines)):
            result = self.check(klines[:i + 1], **params)
            if not result:
                continue
            signal_date = klines[i].trade_date.strftime('%Y-%m-%d')
            if signal_date == prev_date:
                continue
            prev_date = signal_date
            signals.append({
                'date': signal_date,
                'close': float(klines[i].close) if klines[i].close is not None else None,
                **result,
            })

        return signals

    def defaults(self) -> Dict[str, Any]:
        return {p.name: p.default for p in self.meta.params}

    def coerce_params(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """按 ParamSpec 提取并校验参数，忽略无关的 query 参数。"""
        return {p.name: p.coerce(raw.get(p.name)) for p in self.meta.params}
