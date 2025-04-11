import os
import time
from datetime import datetime

import akshare as ak
import pandas as pd
# import mplfinance as mpf
# import matplotlib.pyplot as plt

from stocks.mongo_opr import *
from utils.mongo import *
from stocks.func_1 import *

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

    condition = {"代码": "601600"}

    stocks = mongodb_query(db, STOCK_ALL_COLL_NAME, condition)

    # 遍历股票代码，筛选符合条件的股票
    for row in stocks:
        print(row["名称"], row["代码"], row["总市值"])
        coll_name = STOCK_ONE_COLL_NAME + row["代码"]
        data = mongodb_query(db, coll_name)
        if len(data) != 0:
            # 检查是否存在满足要求的日期
            valid_date = check_valid_3(data)
            if len(valid_date) == 0:
                break
            
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
    print(formatted_output)



if __name__ == "__main__":
    main()
