from cache.redis import redis_client
import time

LUA_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call("HMGET", key, "tokens", "last_updated")
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_updated = now
else
    local elapsed = now - last_updated
    tokens = tokens + (elapsed * refill_rate)
    tokens = math.min(capacity, tokens)
    last_updated = now
end

if tokens >= 1 then
    tokens = tokens - 1
    redis.call("HSET", key, "tokens", tokens, "last_updated", now)
    redis.call("EXPIRE", key, 60)
    return 1
else
    redis.call("HSET", key, "tokens", tokens, "last_updated", now)
    redis.call("EXPIRE", key, 60)
    return 0
end
"""

class RateLimiter:
    def __init__(self, redis_client = redis_client):
        self.redis = redis_client


    def is_allowed(self, key: str, capacity: int = 5, refill_rate: float = 1.0) -> bool:
        redis_key = f"rate_limit:{key}"
        now = time.time()
        
        result = self.redis.eval(LUA_SCRIPT, 1, redis_key, capacity, refill_rate, now)

        return result == 1

   