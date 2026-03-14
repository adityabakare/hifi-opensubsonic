"""
Unit tests for HifiClient circuit breaker, semaphore, and failover logic.
"""
import asyncio
import time
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.hifi_client import HifiClient, _CircuitState


# ---------------------------------------------------------------------------
# _CircuitState unit tests
# ---------------------------------------------------------------------------

class TestCircuitState:
    def test_initial_state_is_closed(self):
        cs = _CircuitState()
        assert cs.failures == 0
        assert not cs.is_open
        assert not cs.is_half_open

    def test_failures_below_threshold_stay_closed(self):
        cs = _CircuitState()
        for _ in range(4):  # threshold is 5
            cs.record_failure()
        assert cs.failures == 4
        assert not cs.is_open

    def test_reaches_threshold_opens_circuit(self):
        cs = _CircuitState()
        for _ in range(5):
            cs.record_failure()
        assert cs.failures == 5
        assert cs.is_open

    def test_open_circuit_becomes_half_open_after_recovery(self):
        cs = _CircuitState()
        for _ in range(5):
            cs.record_failure()
        assert cs.is_open

        # Simulate recovery period passing
        cs.open_until = time.monotonic() - 1
        assert not cs.is_open
        assert cs.is_half_open

    def test_success_resets_circuit(self):
        cs = _CircuitState()
        for _ in range(5):
            cs.record_failure()
        assert cs.is_open

        # Simulate recovery, then success
        cs.open_until = time.monotonic() - 1
        cs.record_success()
        assert cs.failures == 0
        assert not cs.is_open
        assert not cs.is_half_open

    def test_record_success_on_healthy_circuit_is_noop(self):
        cs = _CircuitState()
        cs.record_success()
        assert cs.failures == 0


# ---------------------------------------------------------------------------
# HifiClient integration tests (mocked HTTP)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    """Provide test-friendly settings."""
    with patch("app.hifi_client.settings") as ms:
        ms.HIFI_INSTANCES = ["http://instance-a", "http://instance-b"]
        ms.UPSTREAM_MAX_CONNECTIONS = 10
        ms.UPSTREAM_MAX_KEEPALIVE = 5
        ms.UPSTREAM_TIMEOUT = 5.0
        ms.UPSTREAM_MAX_CONCURRENCY = 5
        ms.CIRCUIT_BREAKER_THRESHOLD = 3
        ms.CIRCUIT_BREAKER_RECOVERY = 10
        # Cache settings needed by cache module
        ms.CACHE_TTL_METADATA = 3600
        ms.CACHE_TTL_SEARCH = 300
        yield ms


@pytest.mark.asyncio
async def test_circuit_breaker_skips_failed_instance(mock_settings):
    """After threshold failures, the instance should be skipped."""
    client = HifiClient()

    # Open circuit on instance-a
    circuit_a = client._get_circuit("http://instance-a")
    for _ in range(3):
        circuit_a.record_failure()

    assert circuit_a.is_open

    # Mock the HTTP GET to succeed for instance-b
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "ok"}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await client._get("/test/")
        assert result == {"data": "ok"}

    await client.close()


@pytest.mark.asyncio
async def test_all_circuits_open_raises_error(mock_settings):
    """When all instances have open circuits, should raise ConnectionError."""
    client = HifiClient()

    # Open all circuits
    for url in client.instances:
        circuit = client._get_circuit(url)
        for _ in range(3):
            circuit.record_failure()

    with pytest.raises(ConnectionError, match="All upstream instances are unavailable"):
        await client._get("/test/")

    await client.close()


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(mock_settings):
    """Semaphore should limit simultaneous upstream calls."""
    mock_settings.UPSTREAM_MAX_CONCURRENCY = 2
    client = HifiClient()
    client._semaphore = asyncio.Semaphore(2)

    active = 0
    max_active = 0

    original_get = client.client.get

    async def slow_get(*args, **kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    with patch.object(client.client, "get", side_effect=slow_get):
        await asyncio.gather(*[client._get("/test/") for _ in range(6)])

    # With semaphore=2, max concurrent should never exceed 2
    assert max_active <= 2

    await client.close()


@pytest.mark.asyncio
async def test_4xx_does_not_trip_circuit(mock_settings):
    """Client errors (4xx) should not count as instance failures."""
    client = HifiClient()

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )

    import httpx as httpx_mod
    with patch.object(client.client, "get", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(httpx.HTTPStatusError):
            await client._get("/test/")

    # Circuit should still be healthy (4xx = client's fault, not instance failure)
    for url in client.instances:
        assert client._get_circuit(url).failures == 0

    await client.close()
