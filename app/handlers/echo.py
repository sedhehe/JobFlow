from models.jobs import EchoPayload

class EchoHandler:
    def execute(self, payload: EchoPayload) -> dict:
        return {"message": payload.message}