from pydantic import BaseModel, Field
from uuid import UUID
from typing import Literal, Annotated


class EchoPayload(BaseModel):
    message: str


class AddPayload(BaseModel):
    a: int
    b: int


class EchoJob(BaseModel):
    type: Literal["echo"]
    payload: EchoPayload


class AddJob(BaseModel):
    type: Literal["add"]
    payload: AddPayload


JobsPayload = Annotated[
    EchoJob | AddJob,
    Field(discriminator="type"),
]


class JobsResponse(BaseModel):
    id: UUID
    type: str
    status: str
    payload: EchoPayload | AddPayload
    result: dict | None = None