"""
In-memory TTL cache implementation for scraping results.
Prevents excessive requests to BuscaCursos UC.
"""
import asyncio
import hashlib
from functools import wraps
from typing import Any, Callable, TypeVar, ParamSpec

from cachetools import TTLCache

from .config import get_settings
from .logging import get_logger

logger = get_logger("cache")

P = ParamSpec("P")
T = TypeVar("T")

# Global cache instance
_cache: TTLCache | None = None
_lock = asyncio.Lock()


def get_cache() -> TTLCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        settings = get_settings()
        _cache = TTLCache(
            maxsize=settings.cache_max_size,
            ttl=settings.cache_ttl_seconds
        )
        logger.info(
            f"Cache initialized: max_size={settings.cache_max_size}, "
            f"ttl={settings.cache_ttl_seconds}s"
        )
    return _cache


def make_cache_key(*args: Any, **kwargs: Any) -> str:
    """Generate a consistent cache key from function arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(func: Callable[P, T]) -> Callable[P, T]:
    """
    Async decorator that caches function results.
    
    Usage:
        @cached
        async def fetch_data(url: str) -> dict:
            ...
    """
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        cache = get_cache()
        cache_key = f"{func.__name__}:{make_cache_key(*args, **kwargs)}"
        
        # Check cache first
        async with _lock:
            if cache_key in cache:
                logger.debug(f"Cache HIT: {cache_key[:20]}...")
                return cache[cache_key]
        
        # Execute function and cache result
        logger.debug(f"Cache MISS: {cache_key[:20]}...")
        result = await func(*args, **kwargs)
        
        async with _lock:
            cache[cache_key] = result
        
        return result
    
    return wrapper


def clear_cache() -> int:
    """Clear all cached entries. Returns the number of entries cleared."""
    cache = get_cache()
    count = len(cache)
    cache.clear()
    logger.info(f"Cache cleared: {count} entries removed")
    return count


def get_cache_stats() -> dict:
    """Get cache statistics."""
    cache = get_cache()
    settings = get_settings()
    return {
        "current_size": len(cache),
        "max_size": settings.cache_max_size,
        "ttl_seconds": settings.cache_ttl_seconds,
        "hits": getattr(cache, "hits", "N/A"),
        "misses": getattr(cache, "misses", "N/A"),
    }
