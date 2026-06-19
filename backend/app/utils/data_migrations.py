import json
from sqlalchemy import text


def sanitize_jsonish_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        try:
            return json.loads(text_value)
        except Exception:
            return None
    return value


def repair_json_columns(conn):
    repaired = {
        'stock_kline_dividend_info': 0,
        'sync_record_failed_stocks': 0,
        'sync_record_no_data_stocks': 0,
    }

    rows = conn.execute(text('SELECT id, dividend_info FROM stock_kline WHERE dividend_info IS NOT NULL')).fetchall()
    for row_id, value in rows:
        cleaned = sanitize_jsonish_value(value)
        if cleaned != value:
            conn.execute(text('UPDATE stock_kline SET dividend_info = :val WHERE id = :id'), {'val': json.dumps(cleaned, ensure_ascii=False) if isinstance(cleaned, (dict, list)) else cleaned, 'id': row_id})
            repaired['stock_kline_dividend_info'] += 1

    rows = conn.execute(text('SELECT id, failed_stocks, no_data_stocks FROM sync_record')).fetchall()
    for row_id, failed_stocks, no_data_stocks in rows:
        new_failed = sanitize_jsonish_value(failed_stocks)
        new_no_data = sanitize_jsonish_value(no_data_stocks)
        changed = False
        if new_failed != failed_stocks:
            conn.execute(text('UPDATE sync_record SET failed_stocks = :val WHERE id = :id'), {'val': json.dumps(new_failed, ensure_ascii=False) if isinstance(new_failed, (dict, list)) else new_failed, 'id': row_id})
            repaired['sync_record_failed_stocks'] += 1
            changed = True
        if new_no_data != no_data_stocks:
            conn.execute(text('UPDATE sync_record SET no_data_stocks = :val WHERE id = :id'), {'val': json.dumps(new_no_data, ensure_ascii=False) if isinstance(new_no_data, (dict, list)) else new_no_data, 'id': row_id})
            repaired['sync_record_no_data_stocks'] += 1
            changed = True
        if changed:
            pass
    return repaired
