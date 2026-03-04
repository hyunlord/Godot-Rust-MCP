"""Tests for MCP server tools (mocked subprocess and WebSocket)."""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import src.server as srv


def make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


@pytest.fixture(autouse=True)
def reset_server_state():
    """Reset global server state between tests."""
    srv._godot = None
    srv._godot_proc = None
    yield
    # Cleanup after test
    if srv._godot is not None:
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.run_until_complete(srv._godot.close())
        except Exception:
            pass
    srv._godot = None
    srv._godot_proc = None


# ── _cargo() tests ─────────────────────────────────────────────────────────────

class TestCargo:
    def test_build_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0, "Compiling mylib\nFinished")
            result = srv._cargo("build", "mylib")

        assert result["success"] is True
        assert result["returncode"] == 0
        cmd = mock_run.call_args[0][0]
        assert "cargo" in cmd
        assert "build" in cmd
        assert "-p" in cmd
        assert "mylib" in cmd

    def test_build_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(1, "", "error[E0001]: undeclared")
            result = srv._cargo("build")

        assert result["success"] is False
        assert "E0001" in result["stderr"]

    def test_release_flag(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0)
            srv._cargo("build", "", ["--release"])
            cmd = mock_run.call_args[0][0]
        assert "--release" in cmd

    def test_stdout_truncated_to_3000(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0, "x" * 5000)
            result = srv._cargo("build")
        assert len(result["stdout"]) <= 3000

    def test_stderr_truncated_to_3000(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(1, "", "e" * 5000)
            result = srv._cargo("build")
        assert len(result["stderr"]) <= 3000

    def test_cargo_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = srv._cargo("build")
        assert result["success"] is False
        assert "not found" in result["stderr"].lower()

    def test_timeout(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cargo", 300)):
            result = srv._cargo("build")
        assert result["success"] is False
        assert "Timeout" in result["stderr"]

    def test_clippy_args(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0)
            srv._cargo("clippy", "", ["--", "-D", "warnings"])
            cmd = mock_run.call_args[0][0]
        assert "clippy" in cmd
        assert "--" in cmd
        assert "-D" in cmd
        assert "warnings" in cmd


# ── _godot_check() tests ───────────────────────────────────────────────────────

class TestGodotCheck:
    def test_returns_error_when_not_started(self):
        result = srv._godot_check()
        assert result is not None
        assert "error" in result
        assert "godot_start" in result["error"]

    def test_returns_none_when_connected(self):
        mock_gws = MagicMock()
        mock_gws.connected = True
        srv._godot = mock_gws
        result = srv._godot_check()
        assert result is None

    def test_returns_error_when_disconnected(self):
        mock_gws = MagicMock()
        mock_gws.connected = False
        srv._godot = mock_gws
        result = srv._godot_check()
        assert result is not None
        assert "error" in result


# ── _godot_start() tests ───────────────────────────────────────────────────────

class TestGodotStart:
    @pytest.mark.asyncio
    async def test_no_project_godot(self, tmp_path):
        with patch.object(srv, "ROOT", tmp_path):
            result = await srv._godot_start()
        assert "error" in result
        assert "project.godot" in result["error"]

    @pytest.mark.asyncio
    async def test_finds_project_in_godot_subdir(self, tmp_path):
        godot_dir = tmp_path / "godot"
        godot_dir.mkdir()
        (godot_dir / "project.godot").write_text("")

        with (
            patch.object(srv, "ROOT", tmp_path),
            patch("subprocess.Popen") as mock_popen,
            patch("src.server.GodotWS") as MockGWS,
        ):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_gws = AsyncMock()
            mock_gws.connect_with_retry = AsyncMock(return_value=False)
            MockGWS.return_value = mock_gws

            result = await srv._godot_start()

        # Should have tried to start (connection failed but project found)
        assert "error" in result
        assert "Failed to connect" in result["error"]

    @pytest.mark.asyncio
    async def test_godot_binary_not_found(self, tmp_path):
        (tmp_path / "project.godot").write_text("")
        with (
            patch.object(srv, "ROOT", tmp_path),
            patch("subprocess.Popen", side_effect=FileNotFoundError()),
        ):
            result = await srv._godot_start()
        assert "error" in result
        assert "not found" in result["error"].lower() or "Godot binary" in result["error"]

    @pytest.mark.asyncio
    async def test_connection_failure_kills_process(self, tmp_path):
        (tmp_path / "project.godot").write_text("")
        with (
            patch.object(srv, "ROOT", tmp_path),
            patch("subprocess.Popen") as mock_popen,
            patch("src.server.GodotWS") as MockGWS,
        ):
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_gws = AsyncMock()
            mock_gws.connect_with_retry = AsyncMock(return_value=False)
            MockGWS.return_value = mock_gws

            result = await srv._godot_start()

        assert "error" in result
        mock_proc.kill.assert_called_once()
        assert srv._godot_proc is None
        assert srv._godot is None

    @pytest.mark.asyncio
    async def test_already_running(self):
        mock_gws = MagicMock()
        mock_gws.connected = True
        srv._godot = mock_gws
        result = await srv._godot_start()
        assert result["status"] == "already_running"


# ── _godot_stop() tests ────────────────────────────────────────────────────────

class TestGodotStop:
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        result = await srv._godot_stop()
        assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_stop_closes_ws_and_kills_proc(self):
        mock_gws = AsyncMock()
        mock_proc = MagicMock()
        srv._godot = mock_gws
        srv._godot_proc = mock_proc

        result = await srv._godot_stop()

        mock_gws.close.assert_called_once()
        mock_proc.terminate.assert_called_once()
        assert srv._godot is None
        assert srv._godot_proc is None
        assert result["status"] == "stopped"


# ── _dispatch() tests ──────────────────────────────────────────────────────────

class TestDispatch:
    @pytest.mark.asyncio
    async def test_rust_build(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0)
            result = await srv._dispatch("rust_build", {})
        assert "success" in result

    @pytest.mark.asyncio
    async def test_rust_build_with_release(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0)
            await srv._dispatch("rust_build", {"release": True})
            cmd = mock_run.call_args[0][0]
        assert "--release" in cmd

    @pytest.mark.asyncio
    async def test_rust_test(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0, "test result: ok. 3 passed")
            result = await srv._dispatch("rust_test", {})
        assert "success" in result

    @pytest.mark.asyncio
    async def test_rust_test_with_filter(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0)
            await srv._dispatch("rust_test", {"filter": "test_physics"})
            cmd = mock_run.call_args[0][0]
        assert "test_physics" in cmd

    @pytest.mark.asyncio
    async def test_rust_clippy(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_proc(0)
            result = await srv._dispatch("rust_clippy", {})
            cmd = mock_run.call_args[0][0]
        assert "clippy" in cmd
        assert "-D" in cmd
        assert "warnings" in cmd

    @pytest.mark.asyncio
    async def test_godot_tick_not_started(self):
        result = await srv._dispatch("godot_tick", {"n": 5})
        assert "error" in result
        assert "godot_start" in result["error"]

    @pytest.mark.asyncio
    async def test_godot_snapshot_not_started(self):
        result = await srv._dispatch("godot_snapshot", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_query_not_started(self):
        result = await srv._dispatch("godot_query", {"type": "entity", "id": 1})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_scene_tree_not_started(self):
        result = await srv._dispatch("godot_scene_tree", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_invariant_not_started(self):
        result = await srv._dispatch("godot_invariant", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_reset_not_started(self):
        result = await srv._dispatch("godot_reset", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_bench_not_started(self):
        result = await srv._dispatch("godot_bench", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_tick_proxied_when_connected(self):
        mock_gws = AsyncMock()
        mock_gws.connected = True
        mock_gws.send = AsyncMock(return_value={"ticks_run": 10, "tick_now": 10, "elapsed_ms": 5.0, "alive": 50})
        srv._godot = mock_gws

        result = await srv._dispatch("godot_tick", {"n": 10})

        mock_gws.send.assert_called_once_with("tick", {"n": 10})
        assert result["ticks_run"] == 10

    @pytest.mark.asyncio
    async def test_godot_tick_clamps_n(self):
        mock_gws = AsyncMock()
        mock_gws.connected = True
        mock_gws.send = AsyncMock(return_value={"ticks_run": 100000})
        srv._godot = mock_gws

        await srv._dispatch("godot_tick", {"n": 999999999})
        sent_n = mock_gws.send.call_args[0][1]["n"]
        assert sent_n == 100000

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await srv._dispatch("totally_unknown_tool_xyz", {})
        assert "error" in result or "Unknown" in str(result)


# ── Tool list tests ────────────────────────────────────────────────────────────

class TestToolList:
    def test_has_all_tools(self):
        names = {t.name for t in srv.TOOLS}
        expected = {
            "rust_build", "rust_test", "rust_clippy",
            "godot_start", "godot_stop",
            "godot_tick", "godot_snapshot", "godot_query",
            "godot_scene_tree", "godot_invariant", "godot_reset", "godot_bench",
            "godot_force_event", "godot_set_config", "godot_golden_dump",
            "verify",
        }
        assert expected.issubset(names)

    def test_all_tools_have_schema(self):
        for tool in srv.TOOLS:
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema


# ── New tool dispatch tests ─────────────────────────────────────────────────────

class TestNewToolDispatch:
    @pytest.mark.asyncio
    async def test_godot_force_event_not_started(self):
        result = await srv._dispatch("godot_force_event", {"entity_id": 1, "event_type": "test"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_force_event_proxied(self):
        mock_gws = AsyncMock()
        mock_gws.connected = True
        mock_gws.send = AsyncMock(return_value={"applied": True, "entity_id": 1, "event_type": "test"})
        srv._godot = mock_gws
        result = await srv._dispatch("godot_force_event", {"entity_id": 1, "event_type": "test"})
        mock_gws.send.assert_called_once_with("force_event", {
            "entity_id": 1, "event_type": "test", "params": {},
        })
        assert result["applied"] is True

    @pytest.mark.asyncio
    async def test_godot_set_config_not_started(self):
        result = await srv._dispatch("godot_set_config", {"key": "speed", "value": 2.0})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_set_config_proxied(self):
        mock_gws = AsyncMock()
        mock_gws.connected = True
        mock_gws.send = AsyncMock(return_value={"key": "speed", "value": 2.0, "applied": True})
        srv._godot = mock_gws
        result = await srv._dispatch("godot_set_config", {"key": "speed", "value": 2.0})
        assert result["applied"] is True

    @pytest.mark.asyncio
    async def test_godot_golden_dump_not_started(self):
        result = await srv._dispatch("godot_golden_dump", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_godot_golden_dump_proxied(self):
        mock_gws = AsyncMock()
        mock_gws.connected = True
        mock_gws.send = AsyncMock(return_value={"path": "user://golden_dump.json", "entities_count": 50, "tick": 100})
        srv._godot = mock_gws
        result = await srv._dispatch("godot_golden_dump", {})
        assert result["entities_count"] == 50


# ── _verify() clippy tests ─────────────────────────────────────────────────────

class TestVerifyClippy:
    @pytest.mark.asyncio
    async def test_verify_runs_clippy(self):
        with patch("subprocess.run") as mock_run:
            # Build succeeds, clippy fails
            mock_run.side_effect = [
                make_proc(0),  # build
                make_proc(1, "", "warning: unused variable"),  # clippy
            ]
            result = await srv._verify({})
        assert result["passed"] is False
        assert result["failed_at"] == "clippy"
        assert "clippy" in result["steps"]

    @pytest.mark.asyncio
    async def test_verify_clippy_pass_proceeds_to_test(self):
        with patch("subprocess.run") as mock_run:
            # Build succeeds, clippy succeeds, test fails
            mock_run.side_effect = [
                make_proc(0),  # build
                make_proc(0),  # clippy
                make_proc(1, "", "FAILED"),  # test
            ]
            result = await srv._verify({})
        assert result["passed"] is False
        assert result["failed_at"] == "test"
        assert "clippy" in result["steps"]
