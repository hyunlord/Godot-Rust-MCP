extends Node

## HarnessServer — WebSocket server autoload for AI agent testing.
## Only activates in --headless or --harness mode. Zero impact on normal gameplay.

const PORT: int = 9877

var _tcp_server: TCPServer = null
var _ws_peers: Array = []
var _router: Node = null


func _ready() -> void:
	if not _should_start():
		return

	_router = load("res://addons/harness/harness_router.gd").new()
	_router.name = "HarnessRouter"
	add_child(_router)

	var invariants: Node = load("res://addons/harness/harness_invariants.gd").new()
	invariants.name = "HarnessInvariants"
	add_child(invariants)

	# Auto-load project-specific adapter if present (e.g. worldsim_adapter.gd).
	# The adapter bridges harness generic interface to project-specific APIs.
	const ADAPTER_PATH := "res://addons/harness/worldsim_adapter.gd"
	if ResourceLoader.exists(ADAPTER_PATH):
		var adapter = load(ADAPTER_PATH).new()
		adapter.name = "WorldSimAdapter"
		add_child(adapter)
		_router.set_adapter(adapter)
		invariants.set_adapter(adapter)
		print("[Harness] WorldSim adapter loaded")

	_tcp_server = TCPServer.new()
	var err: int = _tcp_server.listen(PORT)
	if err != OK:
		push_error("[Harness] Failed to listen on port %d: error %d" % [PORT, err])
		_tcp_server = null
		return

	print("[Harness] Listening on ws://127.0.0.1:%d" % PORT)


func _process(_delta: float) -> void:
	if _tcp_server == null:
		return

	# Accept new TCP connections and upgrade to WebSocket
	while _tcp_server.is_connection_available():
		var tcp_conn: StreamPeerTCP = _tcp_server.take_connection()
		var ws_peer: WebSocketPeer = WebSocketPeer.new()
		var err: int = ws_peer.accept_stream(tcp_conn)
		if err == OK:
			_ws_peers.append(ws_peer)
		else:
			push_warning("[Harness] Failed to accept WebSocket stream: error %d" % err)

	# Process existing peers
	var to_remove: Array = []
	for peer in _ws_peers:
		peer.poll()
		var state: int = peer.get_ready_state()
		if state == WebSocketPeer.STATE_OPEN:
			while peer.get_available_packet_count() > 0:
				var packet: PackedByteArray = peer.get_packet()
				var text: String = packet.get_string_from_utf8()
				var response: String = _handle_message(text)
				peer.send_text(response)
		elif state == WebSocketPeer.STATE_CLOSED:
			to_remove.append(peer)

	# Remove closed peers (iterate backwards for safe removal)
	for i in range(to_remove.size() - 1, -1, -1):
		_ws_peers.erase(to_remove[i])


func _handle_message(text: String) -> String:
	var data = JSON.parse_string(text)
	if data == null or typeof(data) != TYPE_DICTIONARY:
		return _error_response(null, -32700, "Parse error")

	var req_id = data.get("id", null)
	var method: String = data.get("method", "")
	var params: Dictionary = data.get("params", {})

	if method == "":
		return _error_response(req_id, -32600, "Invalid Request: missing method")

	# Route to router
	var result: Dictionary = _router.execute(method, params)

	if result.has("error"):
		var err: Dictionary = result["error"]
		return _error_response(req_id, err.get("code", -32000), err.get("message", "Internal error"))

	return _success_response(req_id, result.get("result", {}))


func _success_response(req_id, result) -> String:
	var response: Dictionary = {
		"jsonrpc": "2.0",
		"id": req_id,
		"result": result,
	}
	return JSON.stringify(response)


func _error_response(req_id, code: int, message: String) -> String:
	var response: Dictionary = {
		"jsonrpc": "2.0",
		"id": req_id,
		"error": {
			"code": code,
			"message": message,
		},
	}
	return JSON.stringify(response)


func _should_start() -> bool:
	# Start in --headless mode or when --harness flag is passed
	var args: PackedStringArray = OS.get_cmdline_args()
	if OS.has_feature("headless"):
		return true
	for arg in args:
		if arg == "--harness":
			return true
	return false
