"""Performance instrumentation and caching utilities.

Lightweight timing and caching to meet sub-200ms targets for scoring
operations on ~3,500 cells.
"""

import functools
import time
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def timed(name: str | None = None) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to time function execution and log results.

    Args:
        name: Optional name for the timing log (defaults to function name)

    Returns:
        Decorated function that logs timing
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        timer_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                print(f"[timing] {timer_name}: {elapsed_ms:.2f}ms")

        return wrapper
    return decorator


class SimpleLRUCache:
    """Simple LRU cache with size limit for scenario-based results.

    Used to cache expensive scoring results keyed by scenario hash.
    For the heatmap endpoint, this can skip recomputation when users
    toggle weights but keep other parameters constant.
    """

    def __init__(self, maxsize: int = 128):
        self._maxsize = maxsize
        self._cache: dict = {}
        self._order: list = []

    def _make_key(self, *args, **kwargs) -> str:
        """Create a cache key from arguments."""
        # Simple hash-based key (for ScenarioRequest, this works well)
        try:
            return str(hash((args, tuple(sorted(kwargs.items())))))
        except TypeError:
            # Fall back to string representation
            return str((args, kwargs))

    def get(self, *args, **kwargs) -> tuple[bool, any]:
        """Get cached value if exists.

        Returns:
            (hit, value) tuple where hit is True if cache hit
        """
        key = self._make_key(*args, **kwargs)
        if key in self._cache:
            # Move to end (most recently used)
            self._order.remove(key)
            self._order.append(key)
            return (True, self._cache[key])
        return (False, None)

    def set(self, value, *args, **kwargs) -> None:
        """Set cached value."""
        key = self._make_key(*args, **kwargs)

        if key in self._cache:
            # Update existing, move to end
            self._order.remove(key)
        elif len(self._cache) >= self._maxsize:
            # Evict least recently used
            lru_key = self._order.pop(0)
            del self._cache[lru_key]

        self._cache[key] = value
        self._order.append(key)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._order.clear()

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)


# Global cache instance for heatmap scoring results
# Cache keyed by scenario parameters that affect scoring results.
heatmap_cache = SimpleLRUCache(maxsize=32)


def cache_key_for_scenario(
    technology: str,
    capacity_mw: float,
    capex: float,
    opex: float,
    discount_rate: float,
    project_lifetime_years: int,
    carbon_price: float,
    cost_weight: float,
    revenue_weight: float,
    carbon_weight: float,
) -> str:
    """Create a consistent cache key from scenario parameters.

    Only includes parameters that affect the score computation.
    """
    return (
        f"{technology}:{capacity_mw}:{capex}:{opex}:{discount_rate}:{project_lifetime_years}:"
        f"{carbon_price}:{cost_weight}:{revenue_weight}:{carbon_weight}"
    )
