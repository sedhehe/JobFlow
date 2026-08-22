from models.jobs import AddPayload

class AdditionHandler:
    def execute(self, payload: AddPayload) -> dict:
        return {"sum": payload.a + payload.b}