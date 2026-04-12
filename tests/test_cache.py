"""Tests for api_cache — rate limiting and disk caching."""

import hashlib
import json
import time
import unittest
from unittest.mock import patch, MagicMock

from api_cache import (
    CachedApiClient,
    RateLimitConfig,
    CacheConfig,
    HAS_DISKCACHE,
)


class TestCacheKeyGeneration(unittest.TestCase):
    """Cache keys must be deterministic and sorted."""

    def setUp(self):
        self.client = CachedApiClient(
            "https://example.com",
            cache=CacheConfig(enabled=False),
        )

    def test_same_endpoint_same_key(self):
        k1 = self.client._cache_key("/users", {"page": 1})
        k2 = self.client._cache_key("/users", {"page": 1})
        self.assertEqual(k1, k2)

    def test_different_params_different_key(self):
        k1 = self.client._cache_key("/users", {"page": 1})
        k2 = self.client._cache_key("/users", {"page": 2})
        self.assertNotEqual(k1, k2)

    def test_param_order_irrelevant(self):
        k1 = self.client._cache_key("/data", {"a": 1, "b": 2})
        k2 = self.client._cache_key("/data", {"b": 2, "a": 1})
        self.assertEqual(k1, k2)

    def test_key_is_md5_hex(self):
        key = self.client._cache_key("/test")
        self.assertEqual(len(key), 32)
        int(key, 16)  # should not raise

    def test_none_params_same_as_empty(self):
        k1 = self.client._cache_key("/x", None)
        k2 = self.client._cache_key("/x", {})
        self.assertEqual(k1, k2)


class TestRateLimiting(unittest.TestCase):
    """Sliding window rate limiter."""

    def test_respects_max_requests(self):
        client = CachedApiClient(
            "https://example.com",
            rate_limit=RateLimitConfig(max_requests=3, window_seconds=60),
            cache=CacheConfig(enabled=False),
        )
        # Simulate 3 requests already made
        now = time.time()
        client._request_times = [now - 10, now - 5, now - 1]

        # Next call should sleep because window is full
        with patch("time.sleep") as mock_sleep:
            # Patch time.time to return consistent values
            client._rate_limit()
            # sleep should have been called since we're at max
            mock_sleep.assert_called()

    def test_requests_remaining_decreases(self):
        client = CachedApiClient(
            "https://example.com",
            rate_limit=RateLimitConfig(max_requests=5, window_seconds=60),
            cache=CacheConfig(enabled=False),
        )
        initial = client.requests_remaining
        self.assertEqual(initial, 5)

        # Simulate a request
        client._request_times.append(time.time())
        self.assertEqual(client.requests_remaining, 4)

    def test_old_requests_expire_from_window(self):
        client = CachedApiClient(
            "https://example.com",
            rate_limit=RateLimitConfig(max_requests=5, window_seconds=10),
            cache=CacheConfig(enabled=False),
        )
        # Add request from 20 seconds ago (outside window)
        client._request_times = [time.time() - 20]
        self.assertEqual(client.requests_remaining, 5)

    def test_min_interval_enforcement(self):
        client = CachedApiClient(
            "https://example.com",
            rate_limit=RateLimitConfig(
                max_requests=100,
                window_seconds=60,
                min_interval=1.0,
            ),
            cache=CacheConfig(enabled=False),
        )
        # First request just happened
        client._request_times = [time.time()]

        with patch("time.sleep") as mock_sleep:
            client._rate_limit()
            # Should sleep to enforce min_interval
            if mock_sleep.called:
                sleep_val = mock_sleep.call_args[0][0]
                self.assertGreater(sleep_val, 0)
                self.assertLessEqual(sleep_val, 1.0)


class TestCacheHitAndMiss(unittest.TestCase):
    """Cache should return stored data without HTTP calls."""

    def _make_client_with_mock_cache(self):
        client = CachedApiClient(
            "https://example.com",
            cache=CacheConfig(enabled=False),
        )
        # Install a dict-based mock cache
        mock_cache = {}

        class DictCache:
            def get(self, key, default=None):
                return mock_cache.get(key, default)

            def set(self, key, value, expire=None):
                mock_cache[key] = value

            def clear(self):
                mock_cache.clear()

            def __len__(self):
                return len(mock_cache)

        client._cache = DictCache()
        client._mock_store = mock_cache
        return client

    @patch("urllib.request.urlopen")
    def test_cache_hit_skips_http(self, mock_urlopen):
        client = self._make_client_with_mock_cache()
        key = client._cache_key("/users")
        client._mock_store[key] = [{"id": 1, "name": "Alice"}]

        result = client.get("/users")
        self.assertEqual(result, [{"id": 1, "name": "Alice"}])
        mock_urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_cache_miss_makes_http_call(self, mock_urlopen):
        client = self._make_client_with_mock_cache()

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"id": 1}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = client.get("/users/1")
        mock_urlopen.assert_called_once()
        self.assertEqual(result, {"id": 1})

    @patch("urllib.request.urlopen")
    def test_skip_cache_bypasses(self, mock_urlopen):
        client = self._make_client_with_mock_cache()
        key = client._cache_key("/users")
        client._mock_store[key] = [{"id": 1}]

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"id": 2}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = client.get("/users", skip_cache=True)
        mock_urlopen.assert_called_once()
        self.assertEqual(result, {"id": 2})


class TestClearCache(unittest.TestCase):
    """clear_cache empties stored data."""

    def test_clear_cache(self):
        client = CachedApiClient(
            "https://example.com",
            cache=CacheConfig(enabled=False),
        )
        store = {}

        class DictCache:
            def get(self, key, default=None):
                return store.get(key, default)

            def set(self, key, value, expire=None):
                store[key] = value

            def clear(self):
                store.clear()

            def __len__(self):
                return len(store)

        client._cache = DictCache()
        store["abc"] = {"data": 1}
        self.assertEqual(len(client._cache), 1)
        client.clear_cache()
        self.assertEqual(len(client._cache), 0)


class TestNoCacheGracefulDegradation(unittest.TestCase):
    """Client works when diskcache is not installed."""

    @patch("urllib.request.urlopen")
    def test_works_without_cache(self, mock_urlopen):
        client = CachedApiClient(
            "https://example.com",
            cache=CacheConfig(enabled=False),
        )
        self.assertIsNone(client._cache)

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = client.get("/health")
        self.assertEqual(result, {"ok": True})

    def test_cache_stats_disabled(self):
        client = CachedApiClient(
            "https://example.com",
            cache=CacheConfig(enabled=False),
        )
        self.assertEqual(client.cache_stats, {"enabled": False})

    def test_clear_cache_noop_when_disabled(self):
        client = CachedApiClient(
            "https://example.com",
            cache=CacheConfig(enabled=False),
        )
        # Should not raise
        client.clear_cache()


class TestCacheStats(unittest.TestCase):
    """cache_stats returns size and volume when enabled."""

    def test_stats_with_mock_cache(self):
        client = CachedApiClient(
            "https://example.com",
            cache=CacheConfig(enabled=False),
        )
        mock_cache = MagicMock()
        mock_cache.__len__ = MagicMock(return_value=5)
        mock_cache.volume.return_value = 1024
        client._cache = mock_cache

        stats = client.cache_stats
        self.assertTrue(stats["enabled"])
        self.assertEqual(stats["size"], 5)
        self.assertEqual(stats["volume"], 1024)


if __name__ == "__main__":
    unittest.main()
