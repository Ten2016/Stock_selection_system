import time
import datetime as dt

from utils.stock import *
from stocks.mongo_opr import *

DFT_START_DATE = "20240101"                         # 默认开始日期
DFT_END_DATE   = "20250411"  #dt.datetime.now().strftime("%Y%m%d")  # 默认结束日期


if __name__ == "__main__":

    client = MongoClient(MONGO_URI)

    db = client[DB_NAME]

    stock_zh_df = get_all_stocks()

    stock_zh_list = stock_zh_df.to_dict("records")

    save_to_mongodb(stock_zh_list, db, STOCK_ALL_COLL_NAME, True)

    print_from_mongodb(db, STOCK_ALL_COLL_NAME, 50)

    # 遍历股票代码，筛选符合条件的股票
    cnt = 0
    for row in stock_zh_df.itertuples(index=False):
        if not row.代码.startswith(('00', '60')):
            continue

        cnt += 1
        if cnt > 1000:
            break

        start_date = get_stock_history_end_date(db, row.代码)
        if start_date == None:
            start_date = DFT_START_DATE
        print(cnt, ':', row.名称, row.代码, row.总市值, start_date, DFT_END_DATE)
        if start_date >= DFT_END_DATE:
            print('数据已存在，跳过')
            continue

        # 获取股票历史数据
        data = get_one_stock_history(row.代码, start_date, DFT_END_DATE)
        if len(data) > 0:
            coll_name = STOCK_ONE_COLL_NAME + row.代码
            save_to_mongodb(data, db, coll_name)

        time.sleep(0.5)
    
    client.close()