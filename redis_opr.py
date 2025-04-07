import redis

import time



if __name__ == "__main__":
    client = redis.Redis()

    print('ping:', client.ping())
    print('echo:', client.echo('hello, redis!'))
    print('key size:', client.dbsize())

    print(client.keys())

    # 字符串
    print('字符串')

    client.set('stock_str', '600000')
    print(client.get('stock_str'))
    client.incr('stock_str')
    print(client.get('stock_str'))
    print(client.getset('stock_str', 600006))
    client.decr('stock_str')
    print(client.get('stock_str'))
    print(client.strlen('stock_str'))

    # 列表
    print('列表')

    print(client.lpush('stock_list', '100001', '100002', 100003, 'start'))
    print(client.rpush('stock_list', '200001', 200002, '200003', 'end'))
    print(client.llen('stock_list'))
    print(client.lpushx('stock_list', '100005'))
    print(client.lpushx('stock_list_2', '100005'))
    print(client.lrange('stock_list', 0, -1))

    client.lpop('stock_list')
    client.rpop('stock_list', 2)
    print(client.lrange('stock_list', 0, -1))

    stock_vec = ['200004', 200004, '200004', 200005, '200006']
    client.rpush('stock_list', *stock_vec)
    print(client.lrange('stock_list', 0, -1))

    client.lrem('stock_list', 2, '200004')
    print(client.lrange('stock_list', 0, -1))
    client.lrem('stock_list', 0, '200004')
    print(client.lrange('stock_list', 0, -1))

    client.ltrim('stock_list', 0, -3)
    print(client.lrange('stock_list', 0, -1))
    print(client.lindex('stock_list', 2))

    client.linsert('stock_list', 'before', '200001', 200000)
    client.linsert('stock_list', 'after', '200001', '200003')
    print(client.lrange('stock_list', 0, -1))

    client.rpoplpush('stock_list', 'stock_list_cp')
    client.rpoplpush('stock_list', 'stock_list_cp')
    print(client.lrange('stock_list', 0, -1))
    print(client.lrange('stock_list_cp', 0, -1))

    for x in client.lrange('stock_list', 0, -1):
        print('stock_list:', x)

    # 哈希
    print('哈希')

    client.hset('stock_hash', mapping = {'code': 100001, 'name': 'china'})
    print(client.hget('stock_hash', 'code'))
    print(client.hgetall('stock_hash'))
    client.hsetnx('stock_hash', 'value', '1000000')
    client.hsetnx('stock_hash', 'code', '100002')
    print(client.hgetall('stock_hash'))
    print(client.hmget('stock_hash', ['code', 'value']))
    print(client.hkeys('stock_hash'))
    print(client.hvals('stock_hash'))

    #集合 (无序)
    print('集合')
    client.delete('stock_set')

    client.sadd('stock_set', '300000', 300001, '300002', 300002)
    print(client.scard('stock_set'), client.smembers('stock_set'))
    print(client.srem('stock_set', 300000, 300000, '300002'))
    print(client.scard('stock_set'), client.smembers('stock_set'))

    client.sadd('stock_set_cp', '100000_cp', '100002_cp')
    client.smove('stock_set', 'stock_set_cp', '300001')
    print(client.scard('stock_set'), client.smembers('stock_set'))
    print(client.scard('stock_set_cp'), client.smembers('stock_set_cp'))

    # 随机删除一个元素
    print(client.spop('stock_set_cp'))
    print(client.smembers('stock_set_cp'))

    client.sadd('stock_set', '400001', '400002', '400003', '400004', '400005')
    print(client.srandmember('stock_set'))
    print(client.srandmember('stock_set'))
    print(client.srandmember('stock_set'))
    print(client.srandmember('stock_set', 2))
    print(client.srandmember('stock_set', 2))

    client.sadd('stock_set_cp', '400003', '400004')

    print(client.smembers('stock_set'))
    print(client.smembers('stock_set_cp'))

    # 并集
    print('并集:', client.sinter('stock_set', 'stock_set_cp'))
    # 交集
    print('交集:', client.sunion('stock_set', 'stock_set_cp'))
    # 差集
    print('差集:', client.sdiff('stock_set', 'stock_set_cp'))
    print('差集:', client.sdiff('stock_set_cp', 'stock_set'))

    # 有序集合 (Sorted set)
    print('有序集合')
    client.delete('stock_zset')

    client.zadd('stock_zset', {'one': 1, 'two': 2, 'three': 3, 'two_2': 2})
    print(client.zcard('stock_zset'), client.zrange('stock_zset', 0, -1))
    print(client.zcount('stock_zset', 1, 2))
    client.zrem('stock_zset', 'one')
    print(client.zcard('stock_zset'), client.zrange('stock_zset', 0, -1, withscores = True))

    score = client.zscore('stock_zset', 'three')
    print('three:', score)
    client.zincrby('stock_zset', 1, 'three')
    print(client.zrevrange('stock_zset', 0, -1, withscores=True))

    client.zadd('stock_zset_cp', {'one': 1, 'two' : 2, 'three' : 3, 'four' : 4, 'five' : 5})
    print(client.zrank('stock_zset_cp', 'two'), client.zrevrank('stock_zset_cp', 'two'))

    print('并集:', client.zintercard(2, ['stock_zset', 'stock_zset_cp']),
          client.zinter(['stock_zset', 'stock_zset_cp'], withscores=True))
    print('交集:', client.zunion(['stock_zset', 'stock_zset_cp']))  
    print('差集:', client.zdiff(['stock_zset', 'stock_zset_cp']))
    print('差集:', client.zdiff(['stock_zset_cp', 'stock_zset']))

    # HyperLogLog
    print('HyperLogLog')

    client.pfadd('stock_hll_1', '000001', '000001', '000002', '000003')
    client.pfadd('stock_hll_2', '000001', '000004', '000005', '000006')
    print(client.pfcount('stock_hll_1'), client.pfcount('stock_hll_2'))
    client.pfmerge('stock_hll_merge', 'stock_hll_1', 'stock_hll_2')
    print(client.pfcount('stock_hll_merge'))
    

    print(client.keys())
    print(client.exists('stock_str'))
    print(client.expire('stock_str', 10))
    time.sleep(3)
    print(client.ttl('stock_str'))
    client.persist('stock_str')
    print(client.ttl('stock_str'))

    client.select(1)
    client.set('stock_1', 'abc')
    client.lpush('stock_2', '111', 222, 'ddd')
    print('db1.stock_1:', client.get('stock_1'))

    client.move('stock_2', 3)

    client.select(0)

    print('range_key:', client.randomkey())
    print('range_key:', client.randomkey())
    print('range_key:', client.randomkey())


    print('str:', client.type('stock_str'))
    print('list:', client.type('stock_list'))
    print('hash:', client.type('stock_hash'))
    print('set:', client.type('stock_set'))
    print('zset:', client.type('stock_zset'))
    print('hyperLogLog:', client.type('stock_hll_merge'))


    client.rename('stock_list', 'stock_list_nm')
    print(client.lrange('stock_list', 0, -1))
    print(client.lrange('stock_list_nm', 0, -1))

    print('key size:', client.dbsize())

    print(client.info())

    client.flushdb()
    client.flushall()

    client.quit()

