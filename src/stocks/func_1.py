import pandas as pd
import datetime as dt

# 检查天数
day_num = 10

def check_valid_1(data):
    """
    从当前日期开始，向前遍历数据，寻找布林下轨大于等于当天收盘价的日期
    :param data: 包含日期、收盘价、布林下轨的 DataFrame
    :return: 符合条件的日期
    """

    # 获取当前日期的索引
    current_index = len(data) - 1  # 假设当前日期是最后一条数据

    # 向前遍历数据
    for i in range(current_index, max(current_index - day_num, -1), -1):
        # 获取当天的收盘价和布林下轨
        x = data.iloc[i]
        close_price = x['收盘']
        lower_band  = x['下轨']

        # 检查布林下轨是否大于等于当天收盘价
        if lower_band >= close_price:
            # 检查是否重新站上五日线
            for j in range(i, len(data), 1):
                y = data.iloc[j]
                cp = y['收盘']
                mp = y['MA5']
                if cp >= mp:
                    return [str(x['日期']), x['下轨'], x['收盘'], str(y['日期']), y['MA5'], y['收盘']]

    return []


def check_valid_2(data):
    """
    从当前日期开始，向前遍历数据，寻找布林下轨大于等于当天收盘价的日期
    :param data: 包含日期、收盘价、布林下轨的 DataFrame
    :return: 符合条件的日期
    """

    ans = []

    # 获取当前日期的索引
    current_index = len(data) - 1  # 假设当前日期是最后一条数据

    # 向前遍历数据
    for i in range(current_index, max(current_index - day_num, -1), -1):
        # 获取当天的收盘价和布林下轨
        x = data.iloc[i]
        close_price = x['收盘']
        lower_band  = x['下轨']

        # 检查布林下轨是否大于等于当天收盘价
        if lower_band >= close_price:
            ans.append([str(x['日期']), x['下轨'], x['收盘']])

    if len(ans) < 2:
        return []

    return ans

def check_valid_3(data):
    """
    从当前日期开始，向前遍历数据，寻找布林下轨大于等于当天收盘价的日期
    :param data: 包含日期、收盘价、布林下轨的 DataFrame
    :return: 符合条件的日期
    """

    ans = []

    # 获取当前日期的索引
    i = 0
    while i < len(data):

        x = data[i]

        if x['收盘'] == None or x['下轨'] == None or x['MA5'] == None:
            i += 1
            continue

        date_x = dt.datetime.fromtimestamp(x['日期'], tz=dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')

        # 检查布林下轨是否大于等于当天收盘价
        if x['收盘'] <= x['下轨']:
            # 检查是否重新站上五日线
            print(f"日期：{date_x}，收盘价：{x['收盘']}，下轨：{x['下轨']}")
            j = i + 1
            while j < len(data):
                y = data[j]
                if y['收盘'] >= y['MA5']:
                    date_y = dt.datetime.fromtimestamp(y['日期'], tz=dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')
                    print(f"  日期：{date_y}，收盘价：{y['收盘']}, MA5: {y['MA5']}")
                    ans.append([date_x, x['收盘'], x['下轨'], date_y, y['收盘'], y['MA5']])
                    break
                j += 1
            i = j
        i += 1

    return ans