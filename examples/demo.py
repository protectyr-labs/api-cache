"""
Demo: using api_cache with JSONPlaceholder.

Shows cached requests, rate limiting, and cache stats.
"""

from api_cache import CachedApiClient, RateLimitConfig, CacheConfig


def main():
    client = CachedApiClient(
        base_url="https://jsonplaceholder.typicode.com",
        rate_limit=RateLimitConfig(
            max_requests=30,
            window_seconds=60,
            min_interval=0.5,
        ),
        cache=CacheConfig(
            cache_dir=".demo_cache",
            default_ttl=300,
        ),
    )

    print(f"Requests remaining: {client.requests_remaining}")

    # First call — hits the network
    print("\n--- First request (cache miss) ---")
    post = client.get("/posts/1")
    print(f"Title: {post.get('title', 'N/A')}")
    print(f"Requests remaining: {client.requests_remaining}")

    # Second call — served from cache
    print("\n--- Second request (cache hit) ---")
    post_cached = client.get("/posts/1")
    print(f"Title: {post_cached.get('title', 'N/A')}")
    print(f"Requests remaining: {client.requests_remaining}")

    # Different endpoint
    print("\n--- Different endpoint ---")
    users = client.get("/users", params={"_limit": 3})
    if isinstance(users, list):
        for u in users[:3]:
            print(f"  - {u.get('name', 'N/A')}")

    # Cache stats
    print(f"\nCache stats: {client.cache_stats}")

    # Force bypass
    print("\n--- skip_cache=True ---")
    fresh = client.get("/posts/1", skip_cache=True)
    print(f"Title: {fresh.get('title', 'N/A')}")

    # Cleanup
    client.clear_cache()
    print("\nCache cleared.")


if __name__ == "__main__":
    main()
