from fastapi import WebSocket
from uuid import UUID

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[UUID, list[WebSocket]] = {}

    async def connect(self, job_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    async def disconnect(self, job_id: UUID, websocket: WebSocket) -> None:
        self.active_connections[job_id].remove(websocket)

    async def broadcast_to_job(self, job_id: UUID, message: dict) -> None:
        connections = self.active_connections.get(job_id, [])

        for connection in connections:
            await connection.send_json(message)
            