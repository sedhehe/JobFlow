from uuid import UUID
import json
import redis.asyncio as aioredis
from cache.redis import redis_client
from realtime.connection_manager import ConnectionManager



def publish_job_event(job_id: UUID, event: dict) -> None:
    channel = f"job_events:{job_id}"
    redis_client.publish(channel, json.dumps(event))

async def start_redis_listener(manager: ConnectionManager) -> None:
    r = aioredis.from_url("redis://localhost:6379/0")
    pubsub = r.pubsub()    
    await pubsub.psubscribe("job_events:*")
    
    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
            job_id_str = channel.split(":")[-1]
            job_id = UUID(job_id_str)

            raw_data = message["data"].decode() if isinstance(message["data"], bytes) else message["data"]
            event_data = json.loads(raw_data)

            await manager.broadcast_to_job(job_id, event_data)

