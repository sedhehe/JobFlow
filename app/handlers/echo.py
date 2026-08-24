from pydantic import BaseModel
from handlers.registry import register_handler


class EchoPayload(BaseModel):
    message: str


@register_handler("echo")
class EchoHandler:
    payload_schema = EchoPayload

    def execute(self, payload: EchoPayload) -> dict:
        return {"message": payload.message}