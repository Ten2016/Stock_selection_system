from typing import Optional, Any

from pymongo import MongoClient
from pymongo import ReturnDocument
from pymongo.errors import ConnectionFailure
from pymongo.results import InsertOneResult, InsertManyResult, UpdateResult, DeleteResult


# 配置 MongoDB 连接
MONGO_URI = "mongodb://localhost:27017/"  # 默认本地连接
DB_NAME = "stock_db"
STOCK_ALL_COLL_NAME = "stock_data"
STOCK_ONE_COLL_NAME = "stock_"


def mongodb_insert_one(
    db,
    coll_name: str,
    document: dict[str, Any],
    **kwargs: Any
) -> Optional[InsertOneResult]:
    """
    向MongoDB集合插入单个文档
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
    :param document: 要插入的文档字典
    :param kwargs: 其他插入选项(如session等)
    :return: InsertOneResult对象或None(失败时)
    """
    try:
        collection = db[coll_name]
        return collection.insert_one(document, **kwargs)
    except Exception as e:
        print(f"MongoDB插入文档失败: {e}")
        return None


def mongodb_insert_many(
    db,
    coll_name: str,
    documents: list[dict[str, Any]],
    **kwargs: Any
) -> Optional[InsertManyResult]:
    """
    向MongoDB集合批量插入文档
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
    :param documents: 要插入的文档列表
    :param kwargs: 其他插入选项(如ordered, session等)
    :return: InsertManyResult对象或None(失败时)
    """
    try:
        collection = db[coll_name]
        return collection.insert_many(documents, **kwargs)
    except Exception as e:
        print(f"MongoDB批量插入文档失败: {e}")
        return None


def mongodb_query(
    db,
    coll_name: str,
    query_cond: dict[str, Any] = None,
    options: dict[str, Any] = None,
    limit: int = 0
) -> list[dict[str, Any]]:
    """
    执行MongoDB查询
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
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
            
        return list(cursor)
    except Exception as e:
        print(f"MongoDB查询失败: {e}")
        return []


def mongodb_update_one(
    db,
    coll_name: str,
    query_cond: dict[str, Any],
    update_data: dict[str, Any],
    upsert: bool = False,
    **kwargs: Any
) -> Optional[UpdateResult]:
    """
    更新MongoDB集合中的单个文档
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
    :param query_cond: 查询条件字典
    :param update_data: 更新操作字典，例如 {"$set": {"status": "inactive"}}
    :param upsert: 如果不存在是否插入新文档
    :param kwargs: 其他更新选项(如array_filters, session等)
    :return: UpdateResult对象或None(失败时)
    """
    try:
        collection = db[coll_name]
        return collection.update_one(query_cond, update_data, upsert=upsert, **kwargs)
    except Exception as e:
        print(f"MongoDB更新文档失败: {e}")
        return None


def mongodb_update_many(
    db,
    coll_name: str,
    query_cond: dict[str, Any],
    update_data: dict[str, Any],
    upsert: bool = False,
    **kwargs: Any
) -> Optional[UpdateResult]:
    """
    更新MongoDB集合中的多个文档
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
    :param query_cond: 查询条件字典
    :param update_data: 更新操作字典
    :param upsert: 如果不存在是否插入新文档
    :param kwargs: 其他更新选项
    :return: UpdateResult对象或None(失败时)
    """
    try:
        collection = db[coll_name]
        return collection.update_many(query_cond, update_data, upsert=upsert, **kwargs)
    except Exception as e:
        print(f"MongoDB批量更新文档失败: {e}")
        return None


def mongodb_find_one_and_update(
    db,
    coll_name: str,
    query_cond: dict[str, Any],
    update_data: dict[str, Any],
    options: dict[str, Any] = None,
    **kwargs: Any
) -> Optional[dict[str, Any]]:
    """
    查找并更新MongoDB集合中的单个文档
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
    :param query_cond: 查询条件字典
    :param update_data: 更新操作字典
    :param options: 选项字典，支持：
                   - projection: 字段投影
                   - sort: 排序规则
                   - upsert: 如果不存在是否插入
                   - return_document: ReturnDocument.BEFORE/AFTER
    :param kwargs: 其他选项
    :return: 更新前或后的文档(根据return_document选项)
    """
    if options is None:
        options = {}

    try:
        collection = db[coll_name]
        return collection.find_one_and_update(
            query_cond,
            update_data,
            projection=options.get("projection"),
            sort=options.get("sort"),
            upsert=options.get("upsert", False),
            return_document=options.get("return_document", ReturnDocument.AFTER),
            **kwargs
        )
    except Exception as e:
        print(f"MongoDB查找并更新文档失败: {e}")
        return None


def mongodb_delete_one(
    db,
    coll_name: str,
    query_cond: dict[str, Any],
    **kwargs: Any
) -> Optional[DeleteResult]:
    """
    删除MongoDB集合中的单个文档
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
    :param query_cond: 查询条件字典
    :param kwargs: 其他删除选项(如session等)
    :return: DeleteResult对象或None(失败时)
    """
    try:
        collection = db[coll_name]
        return collection.delete_one(query_cond, **kwargs)
    except Exception as e:
        print(f"MongoDB删除文档失败: {e}")
        return None


def mongodb_delete_many(
    db,
    coll_name: str,
    query_cond: dict[str, Any],
    **kwargs: Any
) -> Optional[DeleteResult]:
    """
    删除MongoDB集合中的多个文档
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
    :param query_cond: 查询条件字典
    :param kwargs: 其他删除选项
    :return: DeleteResult对象或None(失败时)
    """
    try:
        collection = db[coll_name]
        return collection.delete_many(query_cond, **kwargs)
    except Exception as e:
        print(f"MongoDB批量删除文档失败: {e}")
        return None


def mongodb_count(
    db,
    coll_name: str,
    query_cond: dict[str, Any] = None,
    **kwargs: Any
) -> int:
    """
    统计MongoDB集合中符合条件的文档数量
    
    :param db: pymongo数据库对象
    :param coll_name: 集合名称
    :param query_cond: 查询条件字典
    :param kwargs: 其他选项(如skip, limit, session等)
    :return: 文档数量(失败时返回-1)
    """
    if query_cond is None:
        query_cond = {}

    try:
        collection = db[coll_name]
        return collection.count_documents(query_cond, **kwargs)
    except Exception as e:
        print(f"MongoDB统计文档数量失败: {e}")
        return -1






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