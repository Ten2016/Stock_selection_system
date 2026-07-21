from datetime import timedelta
from typing import Dict, List, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.stock_kline import StockKline


# 策略只读这几列，按需 SELECT 可显著降低批量加载的内存与 IO。
# 列名与 StockKline 属性一致，因此策略函数无需区分 ORM 实体与 Row。
STRATEGY_COLUMNS = (
    StockKline.stock_code,
    StockKline.trade_date,
    StockKline.close,
    StockKline.low,
    StockKline.change_pct,
    StockKline.ma5,
    StockKline.ma60,
    StockKline.boll_lower,
    StockKline.macd,
)

# 200 个交易日约 290 个自然日，留出停牌与节假日余量
_CALENDAR_DAYS_PER_TRADING_DAY = 1.6

# 每批加载的股票数：批量查询要够大才能摊薄开销，又要小到不会把全市场 K 线读进内存。
# 同时远低于 SQLite 对 IN 子句绑定变量数的限制。
CHUNK_SIZE = 500


def get_sorted_klines(stock_code: str, db: Session, max_days: int = 200) -> List:
    data = db.query(*STRATEGY_COLUMNS).filter(
        StockKline.stock_code == stock_code
    ).order_by(StockKline.trade_date.desc()).limit(max_days).all()
    return sorted(data, key=lambda x: x.trade_date)


def load_klines_bulk(db: Session, stock_codes: Sequence[str], max_days: int = 200) -> Dict[str, List]:
    """批量加载多只股票最近 max_days 条 K 线，返回 {code: [按日期升序]}。

    替代逐股查询：全市场选股原本要发起数千次 SELECT。调用方应按 CHUNK_SIZE 分批，
    避免一次把全市场 K 线读进内存。
    """
    if not stock_codes:
        return {}

    latest_date = db.query(func.max(StockKline.trade_date)).scalar()
    if latest_date is None:
        return {}

    cutoff = latest_date - timedelta(days=int(max_days * _CALENDAR_DAYS_PER_TRADING_DAY))

    rows = db.query(*STRATEGY_COLUMNS).filter(
        StockKline.stock_code.in_(list(stock_codes)),
        StockKline.trade_date >= cutoff,
    ).order_by(StockKline.stock_code.asc(), StockKline.trade_date.asc()).all()

    grouped: Dict[str, List] = {}
    for row in rows:
        grouped.setdefault(row.stock_code, []).append(row)

    # 与 get_sorted_klines 保持一致：只保留最近 max_days 条
    return {code: bars[-max_days:] for code, bars in grouped.items()}
