"""Local, same-origin management API; independent of ADK Builder serialization."""

import ipaddress
import json
import base64
import binascii
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .runtime import discover_mcp
from .store import ConfigError, MAX_BYTES, slug
from .script_executor import runtime_status

STATIC = Path(__file__).parent / "static"


async def bounded_body(request, limit=MAX_BYTES):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise ConfigError("请求超过大小上限。", 413)
        chunks.append(chunk)
    return b"".join(chunks)


async def payload(request):
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise ConfigError("请使用 application/json。", 415)
    try:
        result = json.loads(await bounded_body(request, MAX_BYTES * 2))
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, UnicodeError):
        raise ConfigError("请求 JSON 无效。") from None


def install_management(app, store, loader):
    @app.middleware("http")
    async def local_management_only(request, call_next):
        if request.url.path.startswith("/capabilities"):
            try:
                host = request.client.host if request.client else ""
                if not ipaddress.ip_address(host).is_loopback:
                    raise ValueError()
                if request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
                    raise ValueError()
                origin = request.headers.get("origin")
                if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                    raise ValueError()
                if request.headers.get("sec-fetch-site") == "cross-site":
                    raise ValueError()
            except ValueError:
                return JSONResponse({"detail": "能力管理仅允许本机同源访问。"}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/capabilities"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'self'"
        return response

    @app.exception_handler(ConfigError)
    async def config_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    @app.get("/capabilities", include_in_schema=False)
    async def page():
        return FileResponse(STATIC / "index.html")

    @app.get("/capabilities/assets/{name}", include_in_schema=False)
    async def asset(name: str):
        if name not in {"app.js", "style.css", "adk-integration.js", "adk-integration.css", "model-thinking.js", "model-engines.js", "model-picker.js"}:
            raise HTTPException(404)
        return FileResponse(STATIC / name)

    def public_state():
        result = store.snapshot()
        result["agent_names"] = [n for n in loader.list_agents() if not n.startswith("__")]
        result["script_runtime"] = runtime_status()
        return result

    def revision_for(data):
        value = data.get("revision")
        if not isinstance(value, str) or len(value) != 64:
            raise ConfigError("缺少配置版本，请刷新后重试。", 409)
        return value

    def file_payload(data):
        files = data.get("files")
        if not isinstance(files, dict) or any(not isinstance(k, str) for k in files):
            raise ConfigError("files 需为文件名与内容的映射。")
        result = {}
        for name, value in files.items():
            if isinstance(value, str):
                result[name] = value.encode("utf-8")
            elif isinstance(value, dict) and set(value) <= {"encoding", "data", "size"} and value.get("encoding") == "base64" and isinstance(value.get("data"), str):
                try: result[name] = base64.b64decode(value["data"], validate=True)
                except (ValueError, binascii.Error): raise ConfigError("二进制资源的 Base64 内容无效。") from None
            else:
                raise ConfigError("文件需为 UTF-8 文本或 Base64 编码的二进制资源。")
        return result

    def file_response(value):
        try:
            text = value.decode("utf-8")
            if "\x00" in text: raise UnicodeError()
            return text
        except UnicodeError:
            return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii"), "size": len(value)}

    @app.get("/capabilities/api/state")
    async def state():
        return public_state()

    @app.put("/capabilities/api/mcp/{sid}")
    async def save_server(sid: str, request: Request):
        data = await payload(request)
        value = data.get("server")
        if not isinstance(value, dict) or value.get("id") != sid:
            raise ConfigError("服务 ID 与路径不一致。")
        store.save_server(value, revision_for(data))
        return public_state()

    @app.post("/capabilities/api/mcp/{sid}/test")
    async def test_server(sid: str, request: Request):
        slug(sid)
        data = await payload(request)
        revision = revision_for(data)
        config = store.snapshot()
        if revision != config["revision"]:
            raise ConfigError("配置已变化，请刷新重试。", 409)
        server = config["mcp_servers"].get(sid)
        if not server:
            raise ConfigError("服务不存在。", 404)
        tools = await discover_mcp(store, server)
        store.discovered(sid, tools, revision)
        return public_state()

    @app.delete("/capabilities/api/{kind}/{identifier}")
    async def remove(kind: str, identifier: str, request: Request):
        if kind not in {"mcp", "skills"}:
            raise ConfigError("未知能力类型。", 404)
        data = await payload(request)
        store.delete(kind, identifier, revision_for(data))
        return public_state()

    @app.post("/capabilities/api/skills/import")
    async def import_skill(request: Request, revision: str):
        if request.headers.get("content-type", "").split(";")[0] != "application/zip":
            raise ConfigError("请上传 ZIP 或 .skill 压缩包。", 415)
        files = store.unpack_skill(await bounded_body(request))
        store.save_skill(files, revision)
        return public_state()

    @app.post("/capabilities/api/skills")
    async def create_skill(request: Request):
        data = await payload(request)
        store.save_skill(file_payload(data), revision_for(data), enabled=data.get("enabled", True))
        return public_state()

    @app.get("/capabilities/api/skills/{sid}")
    async def read_skill(sid: str, version: int | None = None):
        metadata = store.read()["skills"].get(sid)
        if not metadata:
            raise ConfigError("Skill 不存在。", 404)
        files = store.skill_files(sid, version)
        versions = sorted(int(p.name) for p in (store.skills_dir / sid).iterdir() if p.name.isdigit())
        return {"metadata": metadata, "files": {k: file_response(v) for k, v in files.items()}, "versions": versions}

    @app.put("/capabilities/api/skills/{sid}")
    async def update_skill(sid: str, request: Request):
        if sid not in store.read()["skills"]:
            raise ConfigError("Skill 不存在。", 404)
        data = await payload(request)
        store.save_skill(file_payload(data), revision_for(data), expected_id=sid, enabled=data.get("enabled", True))
        return public_state()

    @app.post("/capabilities/api/skills/{sid}/restore/{version}")
    async def restore_skill(sid: str, version: int, request: Request):
        data = await payload(request)
        metadata = store.read()["skills"].get(sid)
        if not metadata:
            raise ConfigError("Skill 不存在。", 404)
        store.save_skill(store.skill_files(sid, version), revision_for(data), expected_id=sid, enabled=metadata["enabled"])
        return public_state()

    @app.put("/capabilities/api/agents/{agent_name}")
    async def bind_agent(agent_name: str, request: Request):
        if agent_name.startswith("__") or agent_name not in loader.list_agents():
            raise ConfigError("Agent 不存在。", 404)
        data = await payload(request)
        binding = data.get("binding")
        if not isinstance(binding, dict):
            raise ConfigError("缺少 binding 配置。")
        store.binding(agent_name, binding, revision_for(data))
        return public_state()

    app.state.capability_store = store
