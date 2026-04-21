"""
Simple caching utility for WebFace.
Supports both Redis (production) and in-memory (development).
"""

import os
import json
import time
from functools import wraps

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from config import Config


class Cache:
    """Simple cache with Redis or in-memory fallback"""

    def __init__(self):
        self.redis_url = os.environ.get('REDIS_URL', '')
        self._client = None
        self._memory_cache = {}

        if self.redis_url and REDIS_AVAILABLE:
            try:
                self._client = redis.from_url(self.redis_url)
                self._client.ping()
                print("[CACHE] Redis connected")
            except Exception as e:
                print(f"[CACHE] Redis error: {e}, using memory")
                self._client = None
        else:
            print("[CACHE] Using in-memory cache")

    def get(self, key, default=None):
        """Get value from cache"""
        if self._client:
            try:
                value = self._client.get(key)
                if value:
                    return json.loads(value)
            except:
                pass
        return self._memory_cache.get(key, default)

    def set(self, key, value, expire=300):
        """Set value in cache"""
        if self._client:
            try:
                self._client.setex(key, expire, json.dumps(value))
                return
            except:
                pass
        self._memory_cache[key] = value
        self._memory_cache[f"{key}_expire"] = time.time() + expire

    def delete(self, key):
        """Delete key from cache"""
        if self._client:
            try:
                self._client.delete(key)
            except:
                pass
        self._memory_cache.pop(key, None)
        self._memory_cache.pop(f"{key}_expire", None)

    def clear_expired(self):
        """Clear expired memory cache entries"""
        now = time.time()
        expired = [
            k for k, exp in self._memory_cache.items()
            if k.endswith('_expire') and exp < now
        ]
        for k in expired:
            self._memory_cache.pop(k, None)
            self._memory_cache.pop(k.replace('_expire', ''), None)


cache = Cache()


def cached(expire=300, key_prefix=''):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}{func.__name__}_{args}_{kwargs}"
            result = cache.get(cache_key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, expire)
            return result
        return wrapper
    return decorator