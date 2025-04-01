import os
import time
from datetime import datetime

import akshare as ak
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt

from func_1 import *


# 绘制蜡烛图并叠加布林线
def data_plot(df, stock_code):
    # 重命名列名以符合 mplfinance 的要求
    df.rename(columns={
        '日期': 'Date',
        '开盘': 'Open',
        '最高': 'High',
        '最低': 'Low',
        '收盘': 'Close',
        '成交量': 'Volume'
    }, inplace=True)

    # 将日期列设置为索引，并转换为 DatetimeIndex
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)

    # 创建布林线的绘图对象
    apds = [
        mpf.make_addplot(df['中轨'], color='blue', width=1.8),  # 中轨
        mpf.make_addplot(df['上轨'], color='red', width=1.8),   # 上轨
        mpf.make_addplot(df['下轨'], color='green', width=1.8),  # 下轨
        mpf.make_addplot(df['MA5'], color='orange', width=1.0),  # 5日移动平均线
        mpf.make_addplot(df['MA10'], color='black', width=1.0)  # 10日移动平均线
    ]

    # 绘制蜡烛图并叠加布林线
    mpf.plot(df, type='candle', style='charles', title=f'{stock_code}', volume=True, addplot=apds)

def plot_bollinger_bands(stock_code, start_date, end_date):
    """
    获取股票历史数据，计算布林带，并绘制轨迹
    :param stock_code: 股票代码（带交易所前缀，如 sh600000）
    :param start_date: 开始日期（格式：YYYYMMDD）
    :param end_date: 结束日期（格式：YYYYMMDD）
    """

    file_name = f'./history/{stock_code}.xlsx'

    # 判断文件夹是否存在
    if os.path.exists(file_name):
        # print(f'{file_name} exist, read')
        df = pd.read_excel(file_name)
    else:
        # print(f'{file_name} not find, download')
        time.sleep(0.2)
        # 获取历史数据
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

        # 计算布林线
        df = calculate_bollinger_bands(df)

        # 计算移动平均线
        df = calculate_move_mean(df)

        # 保存到文件
        df.to_excel(file_name, index=False)


    # 检查是否存在满足要求的日期
    valid_date = check_valid_3(df)
    if len(valid_date) == 0:
        return None
    
    print(valid_date)

    # 绘制走势图
    # data_plot(df, stock_code)

    return valid_date



def data_select():

    results = []
    # 遍历股票代码，筛选符合条件的股票
    for row in df.itertuples(index=False):
        print(row.名称, row.代码, row.总市值)
        data = plot_bollinger_bands(row.代码, start_date, end_date)
        if data != None:
            results.append([row.名称, row.代码, row.总市值, data])
    
    return results


def main():
    """
    主函数
    """

    # 挑选符合条件的股票
    ans = data_select()
    print("符合条件的股票数量: ", len(ans))

    first_column = [row[1] for row in ans]
    print(first_column)

    first_column = '\n'.join(first_column)
    with open(f'code_{cur_time}.sel', 'w', encoding='utf-8') as file:
        file.writelines(first_column)  # 注意：每个元素需要包含换行符

    formatted_output = '\n'.join(map(str, ans))
    print(formatted_output)



if __name__ == "__main__":
    main()
