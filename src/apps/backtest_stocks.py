from stocks.mongo_opr import *
from stocks.select_trategy import *



def backtest_stock(db, stock_code, start_date, end_date):
    """
    回测指定股票在指定日期范围内的表现

    :param db: pymongo数据库对象
    :param stock_code: 股票代码
    :param start_date: 开始日期
    :param end_date: 结束日期
    :return: 符合条件的日期列表 
    """

    coll_name = STOCK_ONE_COLL_NAME + stock_code
    options = {'sort': [("日期", -1)]}
    limit = 30
    data = mongodb_query(db, coll_name, options=options, limit=limit)
    
    if len(data) == 0:
        print(f"没有找到股票 {stock_code} 的数据")
        return []

    # 筛选符合条件的日期
    valid_dates = select_trategy_1(data)
    
    return valid_dates







if __name__ == "__main__":

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # 指定股票代码
    stock_code = '000063'

    # 回测历史数据
    start_date = '20240101'
    end_date = '20260401'
    stock_date_list = backtest_stock(db, stock_code, start_date, end_date)
    if len(stock_date_list) == 0:
        print("没有符合条件的日期")
        client.close()
        exit(0)

    money = 10000
    print(f"初始资金: {money:.2f} 元")

    for v in stock_date_list:
        diff = v['end_price'] - v['start_price']
        money *= diff / v['start_price'] + 1
    
    print(f"最终资金: {money:.2f} 元")