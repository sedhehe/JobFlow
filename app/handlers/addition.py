from models.jobs import AddPayload

class AdditionHandler:
    payload_schema = AddPayload

    def execute(self, payload: AddPayload) -> dict:
        return {"sum": payload.a + payload.b}