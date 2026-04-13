# api-cache

> Rate-limited HTTP client with disk caching.

[![CI](https://github.com/protectyr-labs/api-cache/actions/workflows/ci.yml/badge.svg)](https://github.com/protectyr-labs/api-cache/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB.svg)](https://python.org)

## Quick Start

```bash
pip install api-cache[cache]   # with disk caching (recommended)
pip install api-cache           # rate limiting only, no disk cache
```

```python
from api_cache import CachedApiClient, RateLimitConfig, CacheConfig

client = CachedApiClient(
    base_url="https://jsonplaceholder.typicode.com",
    rate_limit=RateLimitConfig(max_requests=30, window_seconds=60),
    cache=CacheConfig(cache_dir=".cache", default_ttl=300),
)

post = client.get("/posts/1")        # hits network, caches result
post = client.get("/posts/1")        # returns cached instantly
print(client.requests_remaining)     # 29
print(client.cache_stats)            # {"enabled": True, "size": 1, "volume": 834}
```

## Why This?

- **Sliding window rate limit** -- not fixed-window, so you never get burst-then-blocked behavior
- **MD5 deterministic cache keys** -- same URL + params always hits the same cache entry
- **Optional diskcache** -- works without `diskcache` installed (graceful fallback to no caching)
- **`requests_remaining` property** -- check your budget before making a call
- **Per-request TTL override** -- `client.get("/data", ttl=60)` for short-lived entries

## API

| Method / Property | Purpose |
|-------------------|---------|
| `CachedApiClient(base_url, headers, rate_limit, cache)` | Create a client |
| `.get(endpoint, params, ttl, skip_cache)` | GET request with throttle + cache |
| `.requests_remaining` | Requests left in current rate limit window |
| `.cache_stats` | `{"enabled", "size", "volume"}` |
| `.clear_cache()` | Empty all cached responses |

### Configuration

```python
RateLimitConfig(
    max_requests=60,       # per window
    window_seconds=3600,   # 1 hour sliding window
    min_interval=0.5,      # minimum seconds between calls
)

CacheConfig(
    cache_dir=".cache",
    default_ttl=3600,      # seconds
    enabled=True,
)
```

## Limitations

- **No async** -- synchronous `requests` library only
- **No POST caching** -- only GET requests are cached
- **Single-process rate limit** -- counter is in-memory, not shared across processes
- **No cache invalidation by key** -- clear all or nothing

## License

MIT
