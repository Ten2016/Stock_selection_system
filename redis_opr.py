import redis



if __name__ == "__main__":
    client = redis.Redis()

    print(client.keys())

    print(client.get('stock_1'))
    print(client.lrange('stock_list', 0, -1))

    client.lpush('stock_list', '009988', 9989, 'start')

    stock_vec = ['006666', 6677, 'end']
    client.rpush('stock_list', *stock_vec)

    for x in client.lrange('stock_list', 0, -1):
        print('stock_list:', x)