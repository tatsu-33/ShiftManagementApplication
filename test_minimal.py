import pytest
from hypothesis import given, strategies as st, settings

@pytest.mark.property
@settings(max_examples=10, deadline=None)
@given(x=st.integers())
def test_simple(x: int):
    """Simple test."""
    assert isinstance(x, int)

print("Test function defined:", test_simple)
print("Test function name:", test_simple.__name__)
