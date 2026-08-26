import pytest
from handlers.division import DivisionHandler, DivisionPayload

def test_division_handler():
    """Test division handler"""
    handler = DivisionHandler()
    payload = DivisionPayload(a=10, b=5)
    result = handler.execute(payload)
    assert result == {"quotient": 2.0}

def test_division_by_zero():
    """Test division by zero"""
    handler = DivisionHandler()
    payload = DivisionPayload(a=10, b=0)
    with pytest.raises(ZeroDivisionError):
        handler.execute(payload)