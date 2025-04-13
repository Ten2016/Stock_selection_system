import time

from stocks.mongo_opr import *
from stocks.select_trategy import *


def get_all_stocks(db):
    """
    从MongoDB获取所有股票信息

    :param db: db对象
    :return: 股票信息列表
    """

    # 选择沪深主板，市值大于100亿
    condition = {
        '代码': {"$regex": "^(60|00)\\d{4}$"},
        '总市值': {"$gte": 100}
    }
    options = {
        'projection': {"_id": 0, "名称": 1, '代码': 1, '总市值': 1},
        'sort': [('总市值', -1)]
    }

    # 查询数据
    stocks = mongodb_query(db, STOCK_ALL_COLL_NAME, condition, options)
    if len(stocks) == 0:
        print("没有符合条件的股票")
        return []
    
    print(f"符合条件的股票数量: {len(stocks)}")

    return stocks



def data_select(db, stocks):
    """
    根据选股策略筛选符合条件的股票

    :param db: db对象
    :param stocks: 股票信息列表

    :return: 符合筛选条件的股票数据
    """

    results = []

    # 遍历股票代码，筛选符合条件的股票
    for row in stocks:
        coll_name = STOCK_ONE_COLL_NAME + row["代码"]
        options = {'sort': [("日期", -1)]}
        limit = 30
        data = mongodb_query(db, coll_name, options=options, limit=limit)
        if len(data) == 0:
            continue
        
        # 检查是否存在满足要求的日期
        valid_date = select_trategy_1(data)
        if valid_date == None or len(valid_date) == 0:
            continue

        # 绘制走势图
        # data_plot(df, stock_code)

        results.append([row["名称"], row["代码"], row["总市值"], valid_date])

        print(results.len(), results[-1])

        time.sleep(0.1)
    
    return results


if __name__ == "__main__":

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # 获取待选择的股票列表
    stocks_list = get_all_stocks(db)
    if len(stocks_list) == 0:
        print("没有符合条件的股票")
        client.close()
        exit(0)


    # 挑选符合条件的股票
    ans = data_select(db, stocks_list)
    print("符合条件的股票数量: ", len(ans))

    formatted_output = '\n'.join(map(str, ans))

    file_name = 'output.txt'
    with open(file_name, 'w', encoding='utf-8') as file:
        file.write(formatted_output)

    print(f"结果已保存到 {file_name}")

    client.close()
