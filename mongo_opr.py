import akshare as ak
import pandas as pd

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# 配置 MongoDB 连接
MONGO_URI = "mongodb://localhost:27017/"  # 默认本地连接
DB_NAME = "stock_db"
STOCK_ALL_COLL_NAME = "stock_data"
STOCK_ONE_COLL_NAME = "stock_"


def save_to_mongodb(data, db, coll_name):
    """
    将数据保存到MongoDB
    """
    # 连接MongoDB
    collection = db[coll_name]
    
    # 清空现有集合（可选）
    collection.drop()
    
    collection.insert_many(data)
    
    print(f"成功插入 {len(data)} 条数据到 {coll_name}")


def print_from_mongodb(db, coll_name, limit=10):
    """
    从MongoDB读取并打印数据
    """

    collection = db[coll_name]
        
    # 查询数据
    cursor = collection.find().limit(limit)
    
    # 转换为DataFrame显示
    df = pd.DataFrame(list(cursor))
    
    if not df.empty:
        print(f"\n从 {coll_name} 读取的数据 (前{limit}条):")
        print(df.to_string(index=False))
    else:
        print("集合中没有数据")



def mongodb_query(
    db,
    coll_name,
    query_cond: dict[str, any] = None,
    options: dict[str, any] = None,
    limit: int = 0
) -> list[dict[str, any]]:
    """
    执行MongoDB查询
    
    :param collection: pymongo集合对象
    :param query_cond: 查询条件字典，例如 {"status": "active"}
    :param options: 查询选项字典，支持：
                   - projection: 字段投影，例如 {"_id": 0, "name": 1}
                   - sort: 排序规则，例如 [("create_time", -1)]
                   - skip: 跳过记录数
    :param limit: 返回结果最大数量 (0表示无限制)
    :return: 查询结果字典列表
    """
    if query_cond is None:
        query_cond = {}
    if options is None:
        options = {}

    try:

        collection = db[coll_name]

        # 构建查询游标
        cursor = collection.find(query_cond)
        
        # 应用选项参数
        if "projection" in options:
            cursor = cursor.projection(options["projection"])
        if "sort" in options:
            cursor = cursor.sort(options["sort"])
        if "skip" in options:
            cursor = cursor.skip(options["skip"])
        if limit > 0:
            cursor = cursor.limit(limit)
            
        # 转换为列表返回
        return list(cursor)
    
    except Exception as e:
        print(f"MongoDB查询失败: {e}")
        return []


























if __name__ == "__main__":
    """
    从MongoDB读取并打印数据
    """
    try:
        client = MongoClient(MONGO_URI)
        db = client['gp']
        collection = db['test']
        
        # 查询数据
        cursor = collection.find()
        for doc in cursor:
            print(doc)
            
    except ConnectionFailure as e:
        print(f"MongoDB连接失败: {e}")
    finally:
        client.close()