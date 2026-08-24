from uuid import UUID
from pydantic import BaseModel


class JobsPayload(BaseModel):
    type: str
    payload: dict


class JobsResponse(BaseModel):
    id: UUID
    type: str
    status: str
    payload: dict
    result: dict | None = None