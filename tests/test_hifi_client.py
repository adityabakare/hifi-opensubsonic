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
        ms.UPSTREAM_MAX_CONNECTIONS = 10
        ms.UPSTREAM_MAX_KEEPALIVE = 5
        ms.UPSTREAM_TIMEOUT = 5.0
        ms.UPSTREAM_MAX_CONCURRENCY = 5
        ms.CIRCUIT_BREAKER_THRESHOLD = 3
        ms.CIRCUIT_BREAKER_RECOVERY = 10
        ms.UPSTREAM_MAX_RETRIES = 1
        ms.UPSTREAM_RETRY_DELAY = 0.01  # Fast retries for tests
        ms.MONOCHROME_INSTANCES_URL = "https://example.com/instances.json"
        # Cache settings needed by cache module
        ms.CACHE_TTL_METADATA = 3600
        ms.CACHE_TTL_SEARCH = 300
        yield ms


def _make_client_with_instances(api=None, streaming=None):
    """Create a HifiClient and manually set instance pools (skip async init)."""
    client = HifiClient()
    client.api_instances = api or ["http://instance-a", "http://instance-b"]
    client.streaming_instances = streaming or ["http://stream-a", "http://stream-b"]
    client._initialized = True
    for url in set(client.api_instances + client.streaming_instances):
        client._get_circuit(url)
    return client


@pytest.mark.asyncio
async def test_circuit_breaker_skips_failed_instance(mock_settings):
    """After threshold failures, the instance should be skipped."""
    client = _make_client_with_instances()

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
        result = await client._request("/test/", instance_type="api")
        assert result == {"data": "ok"}

    await client.close()


@pytest.mark.asyncio
async def test_all_circuits_open_retries_then_raises(mock_settings):
    """When all instances have open circuits, should retry then raise ConnectionError."""
    client = _make_client_with_instances()

    # Open all circuits
    for url in client.api_instances:
        circuit = client._get_circuit(url)
        for _ in range(3):
            circuit.record_failure()

    with pytest.raises(ConnectionError, match="unavailable after"):
        await client._request("/test/", instance_type="api")

    await client.close()


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(mock_settings):
    """Semaphore should limit simultaneous upstream calls."""
    mock_settings.UPSTREAM_MAX_CONCURRENCY = 2
    client = _make_client_with_instances()
    client._semaphore = asyncio.Semaphore(2)

    active = 0
    max_active = 0

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
        await asyncio.gather(*[client._request("/test/", instance_type="api") for _ in range(6)])

    # With semaphore=2, max concurrent should never exceed 2
    assert max_active <= 2

    await client.close()


@pytest.mark.asyncio
async def test_4xx_retries_on_other_instances(mock_settings):
    """4xx errors should try the next instance, not raise to the client."""
    client = _make_client_with_instances(api=["http://instance-a", "http://instance-b"])

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if "instance-a" in url:
            # First instance returns 404
            mock_resp.status_code = 404
        else:
            # Second instance succeeds
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": "ok"}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    with patch.object(client.client, "get", side_effect=mock_get):
        # Patch random.shuffle to ensure predictable order: instance-a first, then instance-b
        with patch("app.hifi_client.random.shuffle", side_effect=lambda x: x.sort()):
            result = await client._request("/test/", instance_type="api")

    assert result == {"data": "ok"}
    assert call_count == 2  # Tried both instances

    # Circuits should still be healthy (4xx doesn't trip circuit)
    for url in client.api_instances:
        assert client._get_circuit(url).failures == 0

    await client.close()


@pytest.mark.asyncio
async def test_streaming_uses_streaming_instances(mock_settings):
    """get_track should use streaming instances, not API instances."""
    client = _make_client_with_instances(
        api=["http://api-only"],
        streaming=["http://stream-only"],
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"trackId": 123}}
    mock_response.raise_for_status = MagicMock()

    called_urls = []

    async def capture_get(url, **kwargs):
        called_urls.append(url)
        return mock_response

    with patch.object(client.client, "get", side_effect=capture_get):
        await client._request("/track/", params={"id": 123}, instance_type="streaming")

    # Should have called the streaming instance, not the API one
    assert any("stream-only" in u for u in called_urls)
    assert not any("api-only" in u for u in called_urls)

    await client.close()
