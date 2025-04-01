import akshare as ak
import pandas as pd

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# 配置 MongoDB 连接
MONGO_URI = "mongodb://localhost:27017/"  # 默认本地连接
DB_NAME = "stock_db"
STOCK_ALL_COLL_NAME = "stock_data"
STOCK_ONE_COLL_NAME = "stock_"


def save_to_mongodb(data, db, collection_name):
    """
    将数据保存到MongoDB
    """
    # 连接MongoDB
    collection = db[collection_name]
    
    # 清空现有集合（可选）
    collection.drop()
    
    collection.insert_many(data)
    
    print(f"成功插入 {len(data)} 条数据到 {collection_name}")


def print_from_mongodb(db, collection_name, limit=10):
    """
    从MongoDB读取并打印数据
    """

    collection = db[collection_name]
        
    # 查询数据
    cursor = collection.find().limit(limit)
    
    # 转换为DataFrame显示
    df = pd.DataFrame(list(cursor))
    
    if not df.empty:
        print(f"\n从 {collection_name} 读取的数据 (前{limit}条):")
        print(df.to_string(index=False))
    else:
        print("集合中没有数据")



def mongodb_query()



























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