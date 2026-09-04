from cache.redis import redis_client
import json

class Idempotency:
    def __init__(self, redis_client = redis_client):
        self.redis = redis_client

    def check_or_lock(self, key: str) -> tuple[str, dict | None]:
        key = f"idempotency:{key}"
        value = self.redis.get(key)
        if value:
            if value == "IN_PROGRESS":
                return ("IN_PROGRESS", None)
            else:
                return ("COMPLETED", json.loads(value))
        
        acquired = self.redis.set(key, "IN_PROGRESS", nx=True, ex=60)
        if not acquired:
            return ("IN_PROGRESS", None)
        
        return ("NEW", None)

    def save_response(self, key: str, response: dict, ttl: int = 86400) -> None:
        key = f"idempotency:{key}"
        self.redis.set(key, json.dumps(response), ex=ttl)

