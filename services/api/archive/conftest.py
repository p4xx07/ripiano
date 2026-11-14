import pytest


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Sign-in throttling lives in the cache; every test starts without earlier failures."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
