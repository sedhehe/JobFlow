from pydantic import BaseModel
from handlers.registry import register_handler


class DivisionPayload(BaseModel):
    a: int
    b: int


@register_handler("division")
class DivisionHandler:
    payload_schema = DivisionPayload

    def execute(self, payload: DivisionPayload) -> dict:
        return {"quotient": payload.a / payload.b}