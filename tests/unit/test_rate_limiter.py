from adaptive_agent.interface_layer.rate_limiter import RateLimiter


def test_allows_up_to_max_per_minute():
    now = [0.0]
    limiter = RateLimiter(max_per_minute=3, now_fn=lambda: now[0])

    assert limiter.allow("customer-a") is True
    assert limiter.allow("customer-a") is True
    assert limiter.allow("customer-a") is True


def test_blocks_the_n_plus_first_call_in_the_window():
    now = [0.0]
    limiter = RateLimiter(max_per_minute=3, now_fn=lambda: now[0])

    for _ in range(3):
        limiter.allow("customer-a")

    assert limiter.allow("customer-a") is False


def test_window_slides_and_old_calls_age_out():
    now = [0.0]
    limiter = RateLimiter(max_per_minute=2, now_fn=lambda: now[0])

    assert limiter.allow("customer-a") is True
    now[0] += 30
    assert limiter.allow("customer-a") is True
    assert limiter.allow("customer-a") is False  # 2 calls within the last 60s

    now[0] += 31  # first call is now > 60s old
    assert limiter.allow("customer-a") is True


def test_keys_are_independent():
    now = [0.0]
    limiter = RateLimiter(max_per_minute=1, now_fn=lambda: now[0])

    assert limiter.allow("customer-a") is True
    assert limiter.allow("customer-b") is True
    assert limiter.allow("customer-a") is False
    assert limiter.allow("customer-b") is False


def test_idle_sweep_drops_stale_keys_but_keeps_active_ones():
    now = [0.0]
    limiter = RateLimiter(max_per_minute=1, idle_ttl_seconds=100, now_fn=lambda: now[0])

    limiter.allow("stale-customer")  # call #1

    now[0] += 200  # past the 100s idle TTL
    for _ in range(498):
        limiter.allow("active-customer")  # calls #2..#499

    assert "stale-customer" in limiter._last_seen
    limiter.allow("active-customer")  # call #500 triggers the sweep

    assert "stale-customer" not in limiter._last_seen
    assert "active-customer" in limiter._last_seen
