# api-cache

Rate-limited API client with disk caching. Sliding window throttle, MD5-keyed cache, configurable TTL.

## Why This Exists

Every developer who calls external APIs ends up reimplementing the same two things:

1. **Rate limiting** — don't get banned.
2. **Caching** — don't repeat identical requests.

`api-cache` solves both in a single class. Drop it in, configure limits and TTL, and stop thinking about it.

## Demo

```python
from api_cache import CachedApiClient, RateLimitConfig, CacheConfig

client = CachedApiClient(
    base_url="https://jsonplaceholder.typicode.com",
    rate_limit=RateLimitConfig(max_requests=30, window_seconds=60),
    cache=CacheConfig(cache_dir=".cache", default_ttl=300),
)

# First call hits the network
post = client.get("/posts/1")

# Second call returns cached data instantly
post = client.get("/posts/1")

# Check remaining budget
print(client.requests_remaining)  # 29

# Force a fresh fetch
post = client.get("/posts/1", skip_cache=True)
```

## Quick Start

```bash
pip install api-cache[cache]   # with disk caching (recommended)
pip install api-cache           # without disk caching (in-memory only)
```

### Basic usage

```python
from api_cache import CachedApiClient

client = CachedApiClient(base_url="https://httpbin.org")
data = client.get("/get", params={"foo": "bar"})
```

### Custom rate limits

```python
from api_cache import CachedApiClient, RateLimitConfig

client = CachedApiClient(
    base_url="https://httpbin.org",
    rate_limit=RateLimitConfig(
        max_requests=10,       # 10 requests
        window_seconds=60,     # per minute
        min_interval=0.5,      # at least 0.5s between calls
    ),
)
```

### Custom cache

```python
from api_cache import CachedApiClient, CacheConfig

client = CachedApiClient(
    base_url="https://httpbin.org",
    cache=CacheConfig(
        cache_dir="/tmp/my_api_cache",
        default_ttl=600,       # 10 minute TTL
    ),
)

# Override TTL per request
data = client.get("/get", ttl=60)  # cache for 1 minute only
```

### Headers

```python
client = CachedApiClient(
    base_url="https://httpbin.org",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
)
```

## API Reference

### `CachedApiClient(base_url, headers, rate_limit, cache)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | required | Base URL for all requests |
| `headers` | `dict` | `{}` | HTTP headers sent with every request |
| `rate_limit` | `RateLimitConfig` | 60/hour | Rate limiting configuration |
| `cache` | `CacheConfig` | `.cache/`, 1hr TTL | Disk cache configuration |

### `client.get(endpoint, params, ttl, skip_cache)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | required | URL path appended to base_url |
| `params` | `dict` | `None` | Query parameters |
| `ttl` | `int` | config default | Cache TTL override (seconds) |
| `skip_cache` | `bool` | `False` | Bypass cache for this request |

### `client.clear_cache()`

Empties all cached responses.

### `client.requests_remaining` (property)

Number of requests available in the current rate limit window.

### `client.cache_stats` (property)

Returns `{"enabled": bool, "size": int, "volume": int}`.

### `RateLimitConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_requests` | `int` | 60 | Max requests per window |
| `window_seconds` | `float` | 3600 | Window size in seconds |
| `min_interval` | `float` | 0.0 | Minimum seconds between requests |

### `CacheConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_dir` | `str` | `.cache` | Directory for cache files |
| `default_ttl` | `int` | 3600 | Default TTL in seconds |
| `enabled` | `bool` | `True` | Enable/disable caching |

## Works Without diskcache

If `diskcache` is not installed, the client still works -- it just skips caching entirely. Rate limiting remains active. This is useful in minimal environments or when you only need throttling.

```python
# No diskcache installed? No problem.
from api_cache import CachedApiClient

client = CachedApiClient(base_url="https://httpbin.org")
data = client.get("/get")  # rate-limited, not cached
```

## Development

```bash
git clone https://github.com/protectyr-labs/api-cache.git
cd api-cache
pip install -e ".[dev]"
pytest
```

## License

MIT
