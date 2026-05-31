import csv
import os
from typing import Dict, List, Tuple, Set

SKIPPED_STOCKS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'skipped_stocks.csv')


def load_skipped_stocks() -> Dict[str, str]:
    """加载跳过的股票列表，返回 {code: name}"""
    skipped = {}
    if os.path.exists(SKIPPED_STOCKS_FILE):
        with open(SKIPPED_STOCKS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'code' in row and 'name' in row:
                    skipped[row['code']] = row['name']
    return skipped


def load_skipped_codes() -> Set[str]:
    """加载跳过的股票代码集合"""
    skipped = set()
    if os.path.exists(SKIPPED_STOCKS_FILE):
        with open(SKIPPED_STOCKS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'code' in row:
                    skipped.add(row['code'])
    return skipped


def save_skipped_stocks(skipped: Dict[str, str]):
    """保存跳过的股票列表"""
    os.makedirs(os.path.dirname(SKIPPED_STOCKS_FILE), exist_ok=True)
    with open(SKIPPED_STOCKS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'name'])
        writer.writeheader()
        for code, name in sorted(skipped.items()):
            writer.writerow({'code': code, 'name': name})


def add_skipped_stocks(stocks: List[Tuple[str, str]]):
    """增量添加股票到跳过列表（重复的会过滤）"""
    skipped = load_skipped_stocks()
    for code, name in stocks:
        skipped[code] = name
    save_skipped_stocks(skipped)


def remove_skipped_stocks(codes: Set[str]):
    """增量删除股票（从跳过列表中移除指定代码）"""
    skipped = load_skipped_stocks()
    for code in codes:
        skipped.pop(code, None)
    save_skipped_stocks(skipped)


def is_skipped(code: str, cached_codes: Set[str] = None) -> bool:
    """检查股票是否在跳过列表中，支持传入缓存集合"""
    if cached_codes is not None:
        return code in cached_codes
    skipped = load_skipped_codes()
    return code in skipped


def remove_skipped_stock(code: str) -> bool:
    """从跳过列表中移除单个股票"""
    skipped = load_skipped_stocks()
    if code in skipped:
        del skipped[code]
        save_skipped_stocks(skipped)
        return True
    return False
