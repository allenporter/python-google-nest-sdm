"""Rate limiting utilities."""

import asyncio
import time
from collections.abc import Callable

DEFAULT_DELAYS: tuple[float, ...] = (0.0, 3.0, 10.0, 20.0)
"""Graduated schedule of delays between commands:
- 1st command: Immediate (0s delay).
- 2nd command: 3s spacing (allows short coalescing window for natural multi-taps).
- 3rd command: 10s spacing.
- 4th+ command: 20s spacing (sustained rate limit protection).
"""

DEFAULT_RESET_SECONDS: float = 30.0
"""Idle duration after which the rate limiter resets back to immediate dispatch."""


class RateLimiter:
    """Async progressive rate limiter for SDM commands.

    Enforces graduated delays between consecutive commands and resets
    back to immediate dispatch after an idle period.
    """

    def __init__(
        self,
        delays: tuple[float, ...] = DEFAULT_DELAYS,
        reset_after_seconds: float = DEFAULT_RESET_SECONDS,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self._delays = delays
        self._reset_after_seconds = reset_after_seconds
        self._time_func = time_func or time.time
        self._last_dispatch = 0.0
        self._streak = 0
        self._lock = asyncio.Lock()

    @property
    def delays(self) -> tuple[float, ...]:
        """Configured graduated delay schedule."""
        return self._delays

    @property
    def streak(self) -> int:
        """Current consecutive dispatch streak."""
        return self._streak

    def _get_wait_time(self) -> float:
        """Calculate wait time required for the next dispatch."""
        now = self._time_func()
        if (
            self._last_dispatch == 0.0
            or (now - self._last_dispatch) >= self._reset_after_seconds
        ):
            self._streak = 0
            return 0.0

        required_interval = self._delays[min(self._streak, len(self._delays) - 1)]
        elapsed = now - self._last_dispatch
        return max(0.0, required_interval - elapsed)

    def try_acquire(self) -> bool:
        """Attempt to acquire permission to dispatch immediately without waiting."""
        now = self._time_func()
        if self._get_wait_time() == 0.0:
            self._last_dispatch = now
            self._streak += 1
            return True
        return False

    async def acquire(self) -> None:
        """Acquire permission to dispatch, waiting if necessary."""
        while True:
            async with self._lock:
                wait_time = self._get_wait_time()
                if wait_time == 0.0:
                    self._last_dispatch = self._time_func()
                    self._streak += 1
                    return
            await asyncio.sleep(wait_time)
