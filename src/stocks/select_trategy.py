import datetime as dt


def select_trategy_1(data):
    """
    从当前日期开始，向前遍历数据，寻找布林下轨大于等于当天收盘价，且:
    1. 在之后重新站上五日线的日期
    2. 在之后出现阴线，且收盘价低于前一天收盘价

    :param data: 包含日期、收盘价、布林下轨的股票历史数据
    :return: 符合条件的日期
    :rtype: list or None
    """

    # 向前遍历数据
    for i in range(0, len(data), 1):
        x = data[i]
        # 如果收盘价、布林下轨或五日线为空，则跳过
        if x['收盘'] == None or x['下轨'] == None or x['MA5'] == None:
            continue

        # 检查布林下轨是否大于等于当天收盘价
        if x['收盘'] <= x['下轨']:
            date_x = dt.datetime.fromtimestamp(x['日期'],
                        tz=dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')
            # print(f"日期：{date_x}，收盘价：{x['收盘']}，下轨：{x['下轨']}")

            # 检查是否重新站上五日线
            for j in range(i - 1, -1, -1):
                y = data[j]
                if y['收盘'] == None or y['下轨'] == None or y['MA5'] == None:
                    continue

                if y['收盘'] >= y['MA5']:
                    date_y = dt.datetime.fromtimestamp(y['日期'],
                                tz=dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')
                    # print(f"  日期：{date_y}，收盘价：{y['收盘']}, MA5: {y['MA5']}")

                    # 检查是否再次出现阴线
                    for k in range(j - 1, -1, -1):
                        z = data[k]
                        if z['开盘'] == None or z['收盘'] == None:
                            continue

                        if z['收盘'] <= z['开盘'] and z['收盘'] <= data[k + 1]['收盘']:
                            date_z = dt.datetime.fromtimestamp(z['日期'],
                                        tz=dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')
                            # print(f"    日期：{date_z}，开盘价：{z['开盘']}, 收盘价: {z['收盘']}")

                            # 返回符合条件的日期
                            return [date_x, x['收盘'], x['下轨'],
                                    date_y, y['收盘'], y['MA5'],
                                    date_z, z['收盘'], z['开盘']]
                
    return None


def select_trategy_2(data):
    """
    从当前日期开始，向前遍历数据，寻找布林下轨大于等于当天收盘价的日期

    :param data: 包含日期、收盘价、布林下轨的股票历史数据
    :return: 符合条件的日期
    :rtype: list or None
    """

    # 向前遍历数据
    for i in range(len(data) - 1, -1, -1):
        x = data[i]
        # 如果收盘价、布林下轨或五日线为空，则跳过
        if x['收盘'] == None or x['下轨'] == None or x['MA5'] == None:
            continue

        # 检查布林下轨是否大于等于当天收盘价
        if x['收盘'] <= x['下轨']:
            date_x = dt.datetime.fromtimestamp(x['日期'],
                        tz=dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')
            print(f"日期：{date_x}，收盘价：{x['收盘']}，下轨：{x['下轨']}")

            # 返回符合条件的日期
            return [date_x, x['收盘'], x['下轨']]
                
    return None


def select_trategy_3(data):
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

        # 检查布林下轨是否大于等于当天收盘价
        if x['收盘'] <= x['下轨']:
            date_x = dt.datetime.fromtimestamp(x['日期'], 
                        tz=dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')
            print(f"日期：{date_x}，收盘价：{x['收盘']}，下轨：{x['下轨']}")

            # 检查是否重新站上五日线
            j = i + 1
            while j < len(data):
                y = data[j]
                if y['收盘'] >= y['MA5']:
                    date_y = dt.datetime.fromtimestamp(y['日期'],
                                tz=dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')
                    print(f"  日期：{date_y}，收盘价：{y['收盘']}, MA5: {y['MA5']}")

                    ans.append([date_x, x['收盘'], x['下轨'], date_y, y['收盘'], y['MA5']])
                    break
                j += 1
            i = j
        i += 1

    return ans


def select_strategy_new(data):
    """
    检查是否在最近的10天内，连续两天站上5日线
    :param data: 包含日期、收盘价、MA5的 DataFrame
    :return: 如果满足条件返回 True，否则返回 False
    """
    # 获取最近10天的数据
    recent_data = data[-10:]
    consecutive_days = 0
    for x in recent_data:
        # 检查收盘价和MA5是否为空
        
        if x['收盘'] is not None and x['MA5'] is not None and x['收盘'] >= x['MA5']:
            consecutive_days += 1
            if consecutive_days >= 2:
                return True
        else:
            consecutive_days = 0
    return False
    