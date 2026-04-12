"""
API Cache — rate-limited HTTP client with disk caching.

Provides sliding-window rate limiting and MD5-keyed disk caching
for any API client. Prevents rate limit violations and reduces
redundant API calls.
"""

import hashlib
import json
import time
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from pathlib import Path

__version__ = "0.1.0"

try:
    import diskcache
    HAS_DISKCACHE = True
except ImportError:
    HAS_DISKCACHE = False


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    max_requests: int = 60          # max requests per window
    window_seconds: float = 3600    # window size (default: 1 hour)
    min_interval: float = 0.0       # minimum seconds between requests


@dataclass
class CacheConfig:
    """Disk cache configuration."""
    cache_dir: str = ".cache"       # directory for cache files
    default_ttl: int = 3600         # default TTL in seconds
    enabled: bool = True


class CachedApiClient:
    """
    API client with built-in rate limiting and disk caching.

    Rate limiting uses a sliding window: tracks timestamps of recent
    requests and sleeps when approaching the limit.

    Caching uses MD5 hashes of endpoint + params as keys, with
    configurable TTL per request.
    """

    def __init__(
        self,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
        rate_limit: Optional[RateLimitConfig] = None,
        cache: Optional[CacheConfig] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.rate_config = rate_limit or RateLimitConfig()
        self.cache_config = cache or CacheConfig()

        self._request_times: list[float] = []
        self._cache: Optional[Any] = None

        if self.cache_config.enabled and HAS_DISKCACHE:
            cache_path = os.path.abspath(self.cache_config.cache_dir)
            os.makedirs(cache_path, exist_ok=True)
            self._cache = diskcache.Cache(cache_path)

    def _cache_key(self, endpoint: str, params: Optional[dict] = None) -> str:
        """Generate MD5 cache key from endpoint + sorted params."""
        raw = endpoint + ":" + json.dumps(params or {}, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()

    def _rate_limit(self) -> None:
        """Enforce sliding window rate limit. Sleeps if needed."""
        now = time.time()
        window = self.rate_config.window_seconds

        # Remove requests outside the window
        self._request_times = [t for t in self._request_times if now - t < window]

        # Check if we're at the limit
        if len(self._request_times) >= self.rate_config.max_requests:
            oldest = self._request_times[0]
            sleep_time = window - (now - oldest) + 0.1
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Enforce minimum interval
        if self._request_times and self.rate_config.min_interval > 0:
            elapsed = now - self._request_times[-1]
            if elapsed < self.rate_config.min_interval:
                time.sleep(self.rate_config.min_interval - elapsed)

        self._request_times.append(time.time())

    def get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        ttl: Optional[int] = None,
        skip_cache: bool = False,
    ) -> Any:
        """
        Make a cached, rate-limited GET request.

        Args:
            endpoint: URL path (appended to base_url).
            params: Query parameters.
            ttl: Cache TTL override (seconds). None = use default.
            skip_cache: If True, bypass cache for this request.

        Returns:
            Parsed JSON response, or None on error.
        """
        cache_ttl = ttl if ttl is not None else self.cache_config.default_ttl
        key = self._cache_key(endpoint, params)

        # Check cache first
        if not skip_cache and self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

        # Rate limit then fetch
        self._rate_limit()

        try:
            import urllib.request
            import urllib.parse

            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            if params:
                url += "?" + urllib.parse.urlencode(params)

            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())

            # Store in cache
            if self._cache is not None:
                self._cache.set(key, data, expire=cache_ttl)

            return data

        except Exception as e:
            return {"error": str(e)}

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        if self._cache is not None:
            self._cache.clear()

    @property
    def requests_remaining(self) -> int:
        """Approximate requests remaining in the current rate limit window."""
        now = time.time()
        window = self.rate_config.window_seconds
        recent = [t for t in self._request_times if now - t < window]
        return max(0, self.rate_config.max_requests - len(recent))

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Cache statistics (size, volume)."""
        if self._cache is None:
            return {"enabled": False}
        return {
            "enabled": True,
            "size": len(self._cache),
            "volume": self._cache.volume(),
        }
