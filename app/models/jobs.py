from uuid import UUID
from pydantic import BaseModel, ConfigDict


class JobsPayload(BaseModel):
    type: str
    payload: dict


class JobsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    type: str
    status: str
    payload: dict
    result: dict | None = None
    retry_count: int | None = None
    max_retries: int | None = None
    error_message: str | None = None
    