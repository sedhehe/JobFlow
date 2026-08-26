import pytest
from handlers.addition import AdditionHandler, AddPayload

def test_add_handler():
    """Test add handler"""
    handler = AdditionHandler()
    payload = AddPayload(a=5, b=10)
    result = handler.execute(payload)
    assert result == {"sum": 15}