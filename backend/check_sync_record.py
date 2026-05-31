import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.database import SessionLocal
from app.models.sync import SyncRecord
import json

db = SessionLocal()

try:
    latest = db.query(SyncRecord).order_by(SyncRecord.sync_date.desc()).first()
    if latest:
        print("=" * 80)
        print("最新同步记录：")
        print("=" * 80)
        print(f"ID: {latest.id}")
        print(f"同步日期: {latest.sync_date}")
        print(f"股票总数: {latest.stock_count}")
        print(f"状态: {latest.status}")
        print(f"成功: {latest.success_count}")
        print(f"跳过: {latest.skipped_count}")
        print(f"失败: {latest.failed_count}")
        print(f"无数据: {latest.no_data_count}")
        print("\n失败股票列表:")
        if latest.failed_stocks:
            failed = json.loads(latest.failed_stocks)
            print(f"  共 {len(failed)} 个:")
            for s in failed[:10]:  # 只显示前10个
                print(f"    {s['code']} {s['name']}")
            if len(failed) > 10:
                print(f"    ... 还有 {len(failed)-10} 个")
        else:
            print("  (空)")
        print("\n无数据股票列表:")
        if latest.no_data_stocks:
            no_data = json.loads(latest.no_data_stocks)
            print(f"  共 {len(no_data)} 个:")
            for s in no_data[:10]:  # 只显示前10个
                print(f"    {s['code']} {s['name']}")
            if len(no_data) > 10:
                print(f"    ... 还有 {len(no_data)-10} 个")
        else:
            print("  (空)")
        print("=" * 80)
    else:
        print("数据库中没有同步记录")
finally:
    db.close()
