from pydantic import BaseModel
from handlers.registry import register_handler


class AddPayload(BaseModel):
    a: int
    b: int


@register_handler("add", priority="high_priority")
class AdditionHandler:
    payload_schema = AddPayload

    def execute(self, payload: AddPayload) -> dict:
        return {"sum": payload.a + payload.b}