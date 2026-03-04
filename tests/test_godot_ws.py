"""Tests for GodotWS WebSocket client (mocked server)."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.godot_ws import GodotWS


@pytest.mark.asyncio
async def test_connect_success():
    with patch("src.godot_ws.websockets.connect", new_callable=AsyncMock) as mock_connect:
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws

        gws = GodotWS(9877)
        result = await gws.connect_with_retry(timeout=1.0)

        assert result is True
        assert gws.connected is True
        assert gws.ws is mock_ws


@pytest.mark.asyncio
async def test_connect_failure_timeout():
    with patch("src.godot_ws.websockets.connect") as mock_connect:
        mock_connect.side_effect = ConnectionRefusedError()

        gws = GodotWS(9877)
        result = await gws.connect_with_retry(timeout=0.4)

        assert result is False
        assert gws.connected is False
        assert gws.ws is None


@pytest.mark.asyncio
async def test_connect_oserror():
    with patch("src.godot_ws.websockets.connect") as mock_connect:
        mock_connect.side_effect = OSError("network unreachable")

        gws = GodotWS(9877)
        result = await gws.connect_with_retry(timeout=0.4)

        assert result is False


@pytest.mark.asyncio
async def test_send_success():
    gws = GodotWS(9877)
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(return_value=json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"pong": True, "tick": 0},
    }))
    gws.ws = mock_ws
    gws.connected = True

    result = await gws.send("ping", {})

    assert result == {"pong": True, "tick": 0}
    mock_ws.send.assert_called_once()
    sent_data = json.loads(mock_ws.send.call_args[0][0])
    assert sent_data["method"] == "ping"
    assert sent_data["jsonrpc"] == "2.0"
    assert "id" in sent_data


@pytest.mark.asyncio
async def test_send_increments_req_id():
    gws = GodotWS(9877)
    mock_ws = AsyncMock()

    call_count = 0

    async def recv():
        nonlocal call_count
        call_count += 1
        return json.dumps({"jsonrpc": "2.0", "id": call_count, "result": {"n": call_count}})

    mock_ws.recv = recv
    gws.ws = mock_ws
    gws.connected = True

    await gws.send("ping", {})
    await gws.send("ping", {})

    calls = mock_ws.send.call_args_list
    id1 = json.loads(calls[0][0][0])["id"]
    id2 = json.loads(calls[1][0][0])["id"]
    assert id2 == id1 + 1


@pytest.mark.asyncio
async def test_send_error_response():
    gws = GodotWS(9877)
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(return_value=json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32601, "message": "Method not found"},
    }))
    gws.ws = mock_ws
    gws.connected = True

    result = await gws.send("nonexistent", {})

    assert "error" in result
    assert result["error"]["code"] == -32601
    assert "Method not found" in result["error"]["message"]


@pytest.mark.asyncio
async def test_send_not_connected_raises():
    gws = GodotWS(9877)
    # ws is None, connected is False

    with pytest.raises(RuntimeError, match="Not connected"):
        await gws.send("ping", {})


@pytest.mark.asyncio
async def test_send_with_params():
    gws = GodotWS(9877)
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(return_value=json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"ticks_run": 10, "tick_now": 10, "elapsed_ms": 50.0, "alive": 45},
    }))
    gws.ws = mock_ws
    gws.connected = True

    result = await gws.send("tick", {"n": 10})

    assert result["ticks_run"] == 10
    sent = json.loads(mock_ws.send.call_args[0][0])
    assert sent["params"]["n"] == 10


@pytest.mark.asyncio
async def test_close_disconnects():
    gws = GodotWS(9877)
    mock_ws = AsyncMock()
    gws.ws = mock_ws
    gws.connected = True

    await gws.close()

    mock_ws.close.assert_called_once()
    assert gws.connected is False
    assert gws.ws is None


@pytest.mark.asyncio
async def test_close_when_not_connected():
    gws = GodotWS(9877)
    # Should not raise even when not connected
    await gws.close()
    assert gws.ws is None


def test_uri_uses_port():
    gws = GodotWS(9999)
    assert "9999" in gws.uri
    assert "127.0.0.1" in gws.uri
