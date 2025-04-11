import os
import time
from datetime import datetime

import akshare as ak
import pandas as pd
# import mplfinance as mpf
# import matplotlib.pyplot as plt

from utils.mongo import *
from stocks.mongo_opr import *
from stocks.select_func import *

# # 绘制蜡烛图并叠加布林线
# def data_plot(df, stock_code):
#     # 重命名列名以符合 mplfinance 的要求
#     df.rename(columns={
#         '日期': 'Date',
#         '开盘': 'Open',
#         '最高': 'High',
#         '最低': 'Low',
#         '收盘': 'Close',
#         '成交量': 'Volume'
#     }, inplace=True)

#     # 将日期列设置为索引，并转换为 DatetimeIndex
#     df['Date'] = pd.to_datetime(df['Date'])
#     df.set_index('Date', inplace=True)

#     # 创建布林线的绘图对象
#     apds = [
#         mpf.make_addplot(df['中轨'], color='blue', width=1.8),  # 中轨
#         mpf.make_addplot(df['上轨'], color='red', width=1.8),   # 上轨
#         mpf.make_addplot(df['下轨'], color='green', width=1.8),  # 下轨
#         mpf.make_addplot(df['MA5'], color='orange', width=1.0),  # 5日移动平均线
#         mpf.make_addplot(df['MA10'], color='black', width=1.0)  # 10日移动平均线
#     ]

#     # 绘制蜡烛图并叠加布林线
#     mpf.plot(df, type='candle', style='charles', title=f'{stock_code}', volume=True, addplot=apds)


def data_select():

    results = []

    client = MongoClient(MONGO_URI)

    db = client[DB_NAME]

    # 选择沪深主板，市值大于100亿
    condition = {"代码": {"$regex": "^[0-9]{6}$"}, "总市值": {"$gte": 100}}
    options = {'sort': [("总市值", -1)]}
    limit = 1000

    # 查询数据
    stocks = mongodb_query(db, STOCK_ALL_COLL_NAME, condition, options, limit)
    if len(stocks) == 0:
        print("没有符合条件的股票")
        return results
    print(f"符合条件的股票数量: {len(stocks)}")


    # 遍历股票代码，筛选符合条件的股票
    for row in stocks:
        print(row["名称"], row["代码"], row["总市值"])
        coll_name = STOCK_ONE_COLL_NAME + row["代码"]
        options = {'sort': [("日期", -1)]}
        limit = 20
        data = mongodb_query(db, coll_name, options=options, limit=limit)
        if len(data) != 0:
            # 检查是否存在满足要求的日期
            valid_date = select_trategy_1(data)
            if valid_date == None or len(valid_date) == 0:
                continue
            
            # 绘制走势图
            # data_plot(df, stock_code)

            results.append([row["名称"], row["代码"], row["总市值"], valid_date])
    
    return results


def main():
    """
    主函数
    """

    # 挑选符合条件的股票
    ans = data_select()
    print("符合条件的股票数量: ", len(ans))

    formatted_output = '\n'.join(map(str, ans))

    file_name = 'output.txt'
    with open(file_name, 'w', encoding='utf-8') as file:
        file.write(formatted_output)

    print(f"结果已保存到 {file_name}")


if __name__ == "__main__":
    main()
