from adaptive_agent.interface_layer.dedupe import InMemoryDedupeStore


def test_first_sighting_of_an_id_is_not_a_duplicate():
    store = InMemoryDedupeStore()
    assert store.is_duplicate("msg-1") is False


def test_same_id_twice_is_flagged_a_duplicate():
    store = InMemoryDedupeStore()
    store.is_duplicate("msg-1")
    assert store.is_duplicate("msg-1") is True


def test_different_ids_are_independent():
    store = InMemoryDedupeStore()
    assert store.is_duplicate("msg-1") is False
    assert store.is_duplicate("msg-2") is False


def test_ttl_eviction_lets_an_id_be_seen_again_after_expiry():
    now = [0.0]
    store = InMemoryDedupeStore(ttl_seconds=100, now_fn=lambda: now[0])

    store.is_duplicate("msg-1")
    now[0] += 50
    assert store.is_duplicate("msg-1") is True  # still within TTL

    now[0] += 51  # msg-1 is now > 100s old
    assert store.is_duplicate("msg-1") is False  # evicted, treated as fresh


def test_ttl_eviction_only_drops_expired_entries_not_fresh_ones():
    now = [0.0]
    store = InMemoryDedupeStore(ttl_seconds=100, now_fn=lambda: now[0])

    store.is_duplicate("old-msg")
    now[0] += 60
    store.is_duplicate("fresh-msg")
    now[0] += 60  # old-msg is 120s old (expired), fresh-msg is 60s old (not)

    assert store.is_duplicate("old-msg") is False  # evicted, treated as fresh
    assert store.is_duplicate("fresh-msg") is True  # still tracked
