
import datetime as dt

from utils.mongo import *

def save_to_mongodb(data, db, coll_name, drop = False):
    """
    将数据保存到MongoDB
    """
    # 连接MongoDB
    collection = db[coll_name]
    
    # 清空现有集合（可选）
    if drop:
        collection.drop()
    
    collection.insert_many(data)
    
    print(f"成功插入 {len(data)} 条数据到 {coll_name}")


def print_from_mongodb(db, coll_name, limit=10):
    """
    从MongoDB读取并打印数据

    :param db: db对象
    :param coll_name: 集合名称
    :param limit: 返回条数
    :return: None
    """

    # 查询数据
    data = mongodb_query(db, coll_name, limit=10)
    
    if len(data) > 0:
        print(f"\n从 {coll_name} 读取的数据 (前{limit}条):")
        print(data)
    else:
        print("集合中没有数据")


def get_stock_history_end_date(db, stock_code):
    """
    从MongoDB读取制定股票代码的最新一条记录的日期

    :param db: db对象
    :param stock_code: 股票代码
    :return: 返回最新一条记录的日期
    """

    coll_name = STOCK_ONE_COLL_NAME + stock_code
    options = {'sort': [("日期", -1)]}
    limit = 1

    # 查询数据
    data = mongodb_query(db, coll_name, None, options, limit)
    if len(data) == 0:
        return None
    
    end_date = data[0]['日期']
    return dt.datetime.fromtimestamp(end_date).strftime("%Y%m%d")




