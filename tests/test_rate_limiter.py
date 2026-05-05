from app.services.cache import InMemoryCache
from app.services.rate_limiter import RateLimitPolicy, RateLimiter


async def test_rate_limiter_counts_within_window(monkeypatch):
    import app.services.rate_limiter as module

    monkeypatch.setattr(module, "cache", InMemoryCache())
    limiter = RateLimiter()
    policy = RateLimitPolicy("test", requests=2, window_seconds=60)

    assert await limiter.hit("client", policy) == (True, 1)
    assert await limiter.hit("client", policy) == (True, 0)
    assert await limiter.hit("client", policy) == (False, 0)
