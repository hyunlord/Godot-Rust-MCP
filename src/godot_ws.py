import asyncio
import json
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection


class GodotWS:
    """Async WebSocket client for Godot Harness server."""

    def __init__(self, port: int = 9877) -> None:
        self.uri: str = f"ws://127.0.0.1:{port}"
        self.ws: ClientConnection | None = None
        self.connected: bool = False
        self._req_id: int = 0

    async def connect_with_retry(self, timeout: float = 15.0) -> bool:
        """Try connecting every 0.3s until timeout. Returns True if connected."""
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            try:
                self.ws = await websockets.connect(self.uri)
                self.connected = True
                return True
            except (ConnectionRefusedError, OSError):
                await asyncio.sleep(0.3)
        return False

    async def send(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC 2.0 request and return result dict."""
        if not self.ws:
            raise RuntimeError("Not connected to Godot harness")
        self._req_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params,
        }
        await self.ws.send(json.dumps(request))
        raw = await asyncio.wait_for(self.ws.recv(), timeout=300.0)
        response = json.loads(raw)
        if "error" in response:
            return {"error": response["error"]}
        return response.get("result", {})

    async def close(self) -> None:
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.connected = False
            self.ws = None
