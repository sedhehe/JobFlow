from models.jobs import EchoPayload

class EchoHandler:
    payload_schema = EchoPayload

    def execute(self, payload: EchoPayload) -> dict:
        return {"message": payload.message}