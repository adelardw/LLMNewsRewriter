import redis
import numpy as np
np.random.seed(131200)

cache_db = redis.StrictRedis(host='localhost',port=6379,
                             db=13)
keys_deleted_count = 0
for key in cache_db.scan_iter(match='post_*'):

        cache_db.delete(key)
        keys_deleted_count += 1
        
print(keys_deleted_count)