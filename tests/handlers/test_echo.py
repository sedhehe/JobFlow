import pytest
from handlers.echo import EchoHandler, EchoPayload

def test_echo_handler():
    """Test the echo handler."""
    handler = EchoHandler()
    payload = EchoPayload(message="Pytest testing")
    result = handler.execute(payload)
    assert result == {"message": "Pytest testing"}

    
