"""Check the cloud request shape against a local fake endpoint without a real key."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import ai_client
from model_settings import credential_user, is_qwen_endpoint

requests = []
retry_mode = False
overload_remaining = 0

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        global overload_remaining
        length = int(self.headers["Content-Length"])
        requests.append((self.path, self.headers.get("Authorization"),
                         json.loads(self.rfile.read(length))))
        if overload_remaining:
            overload_remaining -= 1
            self.send_error(503)
            return
        if retry_mode and len(requests) == 1:
            choice = {"finish_reason": "length", "message": {"content": "", "reasoning_content": "thinking"}}
        else:
            choice = {"finish_reason": "stop", "message": {"content": '{"ok": true}'}}
        body = json.dumps({"choices": [choice]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass

server = HTTPServer(("127.0.0.1", 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
ai_client.read_settings = lambda: {
    "writing_backend": "cloud", "translation_backend": "local", "analysis_backend": "local",
    "cloud_endpoint": f"http://127.0.0.1:{server.server_port}/v1", "cloud_model": "test-model"}
ai_client.cloud_key = lambda _endpoint: "test-only-key"
ai_client.time.sleep = lambda _seconds: None
try:
    assert ai_client.ask_json("sample essay", "writing", 100) == {"ok": True}
    assert requests[0][0] == "/v1/chat/completions"
    assert requests[0][1] == "Bearer test-only-key"
    assert requests[0][2]["messages"][0]["content"] == "sample essay"
    requests.clear()
    retry_mode = True
    assert ai_client.ask_json("sample essay", "writing", 100) == {"ok": True}
    assert len(requests) == 2
    assert requests[0][2]["reasoning_effort"] == "low"
    assert requests[0][2]["max_tokens"] >= 6000
    assert requests[1][2]["thinking"] == {"type": "disabled"}
    requests.clear()
    retry_mode = False
    overload_remaining = 2
    assert ai_client.ask_json("sample essay", "writing", 100) == {"ok": True}
    assert len(requests) == 3
    requests.clear()
    overload_remaining = 3
    try:
        ai_client.ask_json("sample essay", "writing", 100)
    except ValueError as exc:
        assert "服务器繁忙" in str(exc) and "检查模型" not in str(exc)
    else:
        raise AssertionError("Persistent HTTP 503 should be reported")
    assert len(requests) == 3
    assert is_qwen_endpoint("https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert is_qwen_endpoint("https://example.cn-beijing.maas.aliyuncs.com/compatible-mode/v1")
    assert not is_qwen_endpoint("https://dashscope.aliyuncs.com.evil.example/v1")
    assert credential_user("https://api.deepseek.com") != credential_user("https://dashscope.aliyuncs.com/compatible-mode/v1")
    requests.clear()
    retry_mode = True
    overload_remaining = 0
    ai_client.read_settings = lambda: {
        "writing_backend": "cloud", "translation_backend": "local", "analysis_backend": "local",
        "cloud_endpoint": f"http://127.0.0.1:{server.server_port}/v1", "cloud_model": "qwen3.7-flash"}
    ai_client.is_qwen_endpoint = lambda _endpoint: True
    assert ai_client.ask_json("Return JSON", "writing", 4500) == {"ok": True}
    assert len(requests) == 2
    for request in requests:
        assert request[2]["enable_thinking"] is False
        assert "reasoning_effort" not in request[2]
        assert "thinking" not in request[2]
    assert requests[0][2]["max_tokens"] == 4500
    assert requests[1][2]["max_tokens"] == 9000
    print("cloud route shape: OK")
finally:
    server.shutdown()
