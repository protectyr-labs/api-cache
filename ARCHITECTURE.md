# Architecture

Design decisions and rationale for api-cache.

## Why Sliding Window Over Fixed Window

Fixed-window rate limiting resets at interval boundaries (e.g., every minute on the minute). This creates a burst problem: a client can fire `max_requests` at :59, then another `max_requests` at :00, doubling the effective rate.

Sliding window tracks actual request timestamps and counts only those within the last N seconds. The result is smoother traffic with no burst-then-wait behavior. The trade-off is O(n) memory per tracked request, but for typical API rate limits (60-1000/hour) this is negligible.

## Why MD5 Keys

Cache keys are MD5 hashes of `endpoint + sorted(params)`. This gives us:

- **Determinism**: same endpoint + params always produce the same key, regardless of dict ordering.
- **Compact keys**: 32 hex characters, safe for any filesystem or key-value store.
- **No collision concern**: MD5 is not cryptographically secure, but for cache key deduplication among a single client's requests, collisions are effectively impossible.

We sort params with `json.dumps(sort_keys=True)` so `{"a": 1, "b": 2}` and `{"b": 2, "a": 1}` produce identical keys.

## Why diskcache Over dict

An in-memory dict cache dies when the process restarts. For API clients that run periodically (cron jobs, scheduled tasks, CI pipelines), losing cache between runs means redundant requests and wasted quota.

`diskcache` provides:
- **Persistence**: survives process restarts.
- **Shared access**: multiple processes can read/write the same cache directory.
- **Built-in TTL**: expiration handled at the storage layer.
- **SQLite-backed**: robust, no external service needed.

## Why Optional diskcache

Not every use case needs persistent caching. Some users only want rate limiting. Some environments (Lambda, containers) have ephemeral filesystems where disk caching adds no value.

Making `diskcache` an optional dependency means:
- Zero mandatory dependencies beyond the standard library.
- `pip install api-cache` works everywhere.
- `pip install api-cache[cache]` adds persistence when you want it.

When `diskcache` is absent, caching is silently disabled. Rate limiting still works.

## Known Limitations

- **No async support.** Uses `urllib.request` (blocking). For async workloads, consider wrapping with `asyncio.to_thread()` or contributing an async variant.
- **No POST/PUT/PATCH caching.** Only GET requests are cached. Non-idempotent methods should not be cached by default.
- **Single-process rate limit.** The sliding window is tracked in-process memory. Multiple processes sharing the same API key will each maintain independent counters. For distributed rate limiting, use a shared store (Redis, database).
- **No retry logic.** Failed requests return `{"error": "..."}`. Retry/backoff is left to the caller.
