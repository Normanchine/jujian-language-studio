"""One JSON request interface for local Ollama and optional cloud models."""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from model_settings import cloud_key, is_qwen_endpoint, read_settings

LOCAL_MODEL = "qwen3-8b-nothink:latest"


def _parse_json(value: str) -> dict:
    value = value.strip()
    if not value:
        raise ValueError("云端模型返回了空内容；请重试，或提高输出额度。")
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("模型没有返回 JSON 对象")
    return parsed


def ask_json(prompt: str, task: str, token_limit: int = 1600, *, careful: bool = False) -> dict:
    settings = read_settings()
    if task not in {"translation", "analysis", "writing"}:
        raise ValueError("未知模型任务")
    backend = settings[f"{task}_backend"]
    if backend == "cloud":
        endpoint = settings["cloud_endpoint"].rstrip("/")
        model = settings["cloud_model"]
        qwen = is_qwen_endpoint(endpoint)
        key = cloud_key(endpoint)
        if not endpoint or not model or not key:
            raise ValueError("请先在设置中填写云端接口、模型和 API Key")
        url = endpoint if endpoint.endswith("/chat/completions") else endpoint + "/chat/completions"
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
                   "temperature": 0.2,
                   "max_tokens": max(1600, token_limit) if qwen else max(6000, token_limit + 5500),
                   "response_format": {"type": "json_object"}}
        if qwen:
            payload["enable_thinking"] = bool(careful and task == "writing")
        else:
            payload["reasoning_effort"] = "low"
        try:
            for attempt in range(2):
                # DeepSeek's thinking tokens count against max_tokens. If they
                # consume the whole budget, retry JSON output without thinking.
                if attempt:
                    if qwen:
                        payload["enable_thinking"] = False
                        payload["max_tokens"] = max(3200, token_limit * 2)
                    else:
                        payload.pop("reasoning_effort", None)
                        payload["thinking"] = {"type": "disabled"}
                        payload["max_tokens"] = max(1600, token_limit)
                request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                  headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
                for transport_attempt in range(3):
                    try:
                        with urlopen(request, timeout=180) as response:
                            raw = json.load(response)
                        break
                    except HTTPError as exc:
                        if exc.code not in {500, 503} or transport_attempt == 2:
                            raise
                        time.sleep(2 ** transport_attempt)
                    except (URLError, TimeoutError):
                        if transport_attempt >= 1:
                            raise
                        time.sleep(1)
                choice = raw["choices"][0]
                content = choice["message"].get("content") or ""
                if choice.get("finish_reason") == "length" or not content.strip():
                    if attempt == 0:
                        continue
                    raise ValueError("云端模型输出被截断或返回空内容，请缩短输入后重试。")
                try:
                    return _parse_json(content)
                except (ValueError, json.JSONDecodeError) as exc:
                    if attempt == 0:
                        continue
                    raise ValueError("云端模型没有返回完整的 JSON，请重试。") from exc
        except HTTPError as exc:
            messages = {
                401: "云端 API Key 验证失败，请检查密钥。",
                402: "云端账户余额不足，请检查服务账户。",
                404: "云端接口返回 HTTP 404，请检查接口地址与模型名。",
                429: "云端请求过于频繁（HTTP 429），请稍后再试。",
                500: "云端服务暂时出错（HTTP 500），稍后再试；原稿已保留。",
                503: "云端服务器繁忙（HTTP 503），稍后再试；原稿已保留。",
            }
            raise ValueError(messages.get(exc.code, f"云端接口返回 HTTP {exc.code}，请检查服务状态与设置。")) from exc
        except (URLError, TimeoutError) as exc:
            raise ValueError("云端接口连接失败或超时") from exc
    payload = {"model": LOCAL_MODEL, "prompt": prompt, "format": "json", "stream": False,
               "think": False, "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": token_limit}}
    request = Request("http://127.0.0.1:11434/api/generate",
                      data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=180) as response:
            raw = json.load(response)
        return _parse_json(raw["response"])
    except (URLError, TimeoutError) as exc:
        raise ValueError("本地 Ollama 连接失败或超时") from exc
