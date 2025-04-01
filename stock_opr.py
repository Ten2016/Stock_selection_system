import akshare as ak
import pandas as pd
from datetime import datetime, date

def get_all_stocks():

    df = ak.stock_zh_a_spot_em()
    print('A股所有股票信息, 数量: ', len(df), '数据类型: ', type(df))

    # 基于股票代码去重
    df = df.drop_duplicates(subset=['代码'], keep='first')  # 保留第一条记录
    print("去重后数量: ", len(df))

    # 总市值转为数值类型
    df['总市值'] = pd.to_numeric(df['总市值'], errors='coerce')
    # 删除总市值为空的行
    df = df.dropna(subset=['总市值'])

    # 总市值转为数值类型
    df['流通市值'] = pd.to_numeric(df['流通市值'], errors='coerce')
    # 删除总市值为空的行
    df = df.dropna(subset=['流通市值'])

    # 将总市值转换为亿为单位
    df['总市值'] = (df['总市值'] / 1e8).astype(int)

    # 将总市值转换为亿为单位
    df['流通市值'] = (df['流通市值'] / 1e8).astype(int)

    del df['序号']

    df.sort_values('总市值', inplace=True, ascending=False, na_position='last')

    print("去除异常数据后数量: ", len(df))

    return df


def calculate_move_mean(data):
    """
    计算移动平均线
    :param data: 包含收盘价的 DataFrame
    """
    data['MA5'] = data['收盘'].rolling(window=5).mean().round(2)
    data['MA10'] = data['收盘'].rolling(window=10).mean().round(2)
    data['MA20'] = data['收盘'].rolling(window=20).mean().round(2)
    data['MA30'] = data['收盘'].rolling(window=30).mean().round(2)
    data['MA60'] = data['收盘'].rolling(window=60).mean().round(2)
    return data

def calculate_bollinger_bands(data, window=20):
    """
    计算布林带
    :param data: 包含收盘价的 DataFrame
    :param window: 布林带窗口（默认20天）
    :return: 包含中轨、上轨、下轨的 DataFrame
    """

    bzc = data['收盘'].rolling(window=window).std().round(2)  # 20日标准差

    data['上轨'] = (data['MA20'] + 2 * bzc).round(2)  # 上轨
    data['下轨'] = (data['MA20'] - 2 * bzc).round(2)  # 下轨
    return data

def get_one_stock_history(code, start_date, end_date):
    # 获取历史数据
    df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

    df['日期'] = (pd.to_datetime(df['日期']).astype('int64') // 10**9).astype('int64')

    # 计算移动平均线
    df = calculate_move_mean(df)

    # 计算布林线
    df = calculate_bollinger_bands(df)

    # 转换数据：处理日期类型和 NaN
    records = []
    for _, row in df.iterrows():

        del row['股票代码']

        record = row.to_dict()
        
        # 处理 NaN 值（MongoDB 无法存储 NaN）
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None
        
        records.append(record)
    
    return records