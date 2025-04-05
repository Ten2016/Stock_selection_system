import time

from stock_opr import *
from mongo_opr import *

start_date = "20240101"  # 开始日期
end_date   = "20260101"  # 结束日期


if __name__ == "__main__":

    client = MongoClient(MONGO_URI)

    db = client[DB_NAME]

    stock_zh_df = get_all_stocks()

    stock_zh_list = stock_zh_df.to_dict("records")

    save_to_mongodb(stock_zh_list, db, STOCK_ALL_COLL_NAME)

    print_from_mongodb(db, STOCK_ALL_COLL_NAME)

    # 遍历股票代码，筛选符合条件的股票
    cnt = 200
    for row in stock_zh_df.itertuples(index=False):
        print(row.名称, row.代码, row.总市值)
        data = get_one_stock_history(row.代码, start_date, end_date)
        if len(data) > 0:
            coll_name = STOCK_ONE_COLL_NAME + row.代码
            save_to_mongodb(data, db, coll_name)
            # print_from_mongodb(db, coll_name, 2)
            cnt -= 1
        if cnt < 0:
            break
        time.sleep(0.5)
    
    client.close()