import datetime

from freezegun import freeze_time

from google_nest_sdm.rate_limiter import RateLimiter


def test_rate_limiter_progressive_delays() -> None:
    """Test progressive delay schedule (0s -> 3s -> 10s -> 20s)."""
    with freeze_time("2026-08-16 12:00:00") as frozen_time:
        limiter = RateLimiter()

        # 1st command: 0s delay (immediate)
        assert limiter.try_acquire() is True
        assert limiter.streak == 1

        # Immediate next attempt at t+1.0s (elapsed 1.0s < 3.0s required)
        frozen_time.tick(delta=datetime.timedelta(seconds=1))
        assert limiter.try_acquire() is False

        # At t+3.0s (elapsed 3.0s >= 3.0s required)
        frozen_time.tick(delta=datetime.timedelta(seconds=2))
        assert limiter.try_acquire() is True
        assert limiter.streak == 2

        # 3rd attempt at t+5.0s (elapsed 2.0s < 10.0s required)
        frozen_time.tick(delta=datetime.timedelta(seconds=2))
        assert limiter.try_acquire() is False

        # At t+13.0s (elapsed 10.0s >= 10.0s required)
        frozen_time.tick(delta=datetime.timedelta(seconds=8))
        assert limiter.try_acquire() is True
        assert limiter.streak == 3

        # 4th attempt at t+23.0s (elapsed 10.0s < 20.0s required)
        frozen_time.tick(delta=datetime.timedelta(seconds=10))
        assert limiter.try_acquire() is False

        # At t+33.0s (elapsed 20.0s >= 20.0s required)
        frozen_time.tick(delta=datetime.timedelta(seconds=10))
        assert limiter.try_acquire() is True
        assert limiter.streak == 4


def test_rate_limiter_idle_reset() -> None:
    """Test rate limiter resets streak after idle period."""
    with freeze_time("2026-08-16 12:00:00") as frozen_time:
        limiter = RateLimiter()

        # 1st and 2nd dispatches
        assert limiter.try_acquire() is True
        frozen_time.tick(delta=datetime.timedelta(seconds=3))
        assert limiter.try_acquire() is True
        assert limiter.streak == 2

        # Idle for 35 seconds (exceeds 30s reset threshold)
        frozen_time.tick(delta=datetime.timedelta(seconds=35))

        # Streak resets back to 0, immediate 0s dispatch
        assert limiter.try_acquire() is True
        assert limiter.streak == 1


async def test_rate_limiter_acquire_async() -> None:
    """Test async acquire waits for remaining window."""
    limiter = RateLimiter(delays=(0.0, 0.05, 0.1), reset_after_seconds=1.0)

    # 1st acquire is immediate
    assert limiter.try_acquire() is True

    # 2nd acquire should wait 50ms and succeed
    await limiter.acquire()
    assert limiter.streak == 2
