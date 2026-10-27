"""Same-origin connection settings and explicit synthetic provider probes."""

import asyncio
import json
import time

import httpx
import litellm
from fastapi import Request

from capabilities.api import payload
from model_engines import ConfigError, connection_args, safe_failure, validate_model
from model_runtime import configure_default_models


async def probe_engine(store, engine, settings, key, *, discover=False):
    if not key:
        raise ConfigError("请先填写该引擎的 API Key。")
    start = time.monotonic()
    try:
        if discover:
            base = settings["api_base"]
            suffix = "/models" if engine != "claude" or base.endswith("/v1") else "/v1/models"
            headers = {"Authorization": "Bearer " + key}
            if engine == "claude":
                headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                async with client.stream("GET", base + suffix, headers=headers) as response:
                    response.raise_for_status()
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 4 * 1024 * 1024:
                            raise ConfigError("模型列表过大，请直接填写需要使用的模型 ID。")
                        chunks.append(chunk)
                    data = json.loads(b"".join(chunks))
            rows = data.get("data")
            if not isinstance(rows, list):
                raise ConfigError("供应商未返回标准模型列表，请直接填写模型 ID。")
            models = []
            for row in rows:
                try:
                    model = validate_model(row.get("id")) if isinstance(row, dict) else None
                except ConfigError:
                    continue
                if model and model not in models:
                    models.append(model)
            if not models:
                raise ConfigError("没有读取到模型 ID，请检查 Key 权限或直接填写模型。")
            return {"ok": True, "models": sorted(models), "message": "已读取模型列表；请选用支持对话和工具调用的模型。", "latency_ms": round((time.monotonic() - start) * 1000)}
        args = connection_args(engine, settings["models"][0], settings, key)
        # Use the same LiteLLM provider routes and credentials as Agent runtime.
        if engine == "deepseek":
            args["extra_body"] = {"thinking": {"type": "disabled"}}
        response = await asyncio.wait_for(litellm.acompletion(
            **args, messages=[{"role": "user", "content": "Reply only with OK."}],
            max_tokens=1024, timeout=20, num_retries=0,
        ), timeout=25)
        if not response.choices:
            raise ConfigError("接口没有返回有效模型响应，请检查所选模型。")
        return {"ok": True, "model": settings["models"][0], "message": "连接成功，已收到模型响应。", "latency_ms": round((time.monotonic() - start) * 1000)}
    except ConfigError:
        raise
    except Exception as error:
        raise ConfigError(safe_failure(error), 502) from None


def install_model_api(app, store, loader):
    @app.get("/capabilities/api/models")
    async def state():
        return store.snapshot()

    @app.put("/capabilities/api/models/default")
    async def default(request: Request):
        data = await payload(request)
        reference = data.get("reference")
        if not isinstance(reference, str):
            raise ConfigError("请选择默认模型。")
        result = store.set_default(reference, data.get("revision"))
        configure_default_models(store)
        loader.remove_agent_from_cache("__adk_agent_builder_assistant")
        return result

    @app.put("/capabilities/api/models/{engine}")
    async def save(engine: str, request: Request):
        data = await payload(request)
        return store.save(engine, data.get("settings"), data.get("revision"),
                          api_key=data.get("api_key"), clear_key=data.get("clear_key", False))

    @app.post("/capabilities/api/models/{engine}/test")
    async def test(engine: str, request: Request):
        data = await payload(request)
        store._check_revision(data.get("revision"))
        settings, key = store.draft(engine, data.get("settings"), data.get("api_key"), data.get("clear_key", False))
        purpose = data.get("purpose", "inference")
        if purpose not in {"inference", "models"}:
            raise ConfigError("未知连接测试类型。")
        return await probe_engine(store, engine, settings, key, discover=purpose == "models")

    app.state.model_engine_store = store
