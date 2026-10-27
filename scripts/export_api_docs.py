"""Export the running API and source-reviewed documentation enrichments.

Only reads /openapi.json; never reads sessions, model keys or business files.
The exported document does not replace the server's native OpenAPI endpoint.
"""

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
ENGINES = ["deepseek", "kimi", "openai", "claude", "openrouter"]


def ref(name):
    return {"$ref": "#/components/schemas/" + name}


def obj(properties, required=(), extra=False):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": extra}


def array(items, **kwargs):
    return {"type": "array", "items": items, **kwargs}


def schemas():
    string = {"type": "string"}
    revision = {"type": "string", "pattern": "^[0-9a-f]{64}$", "description": "从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。"}
    model = {"type": "string", "pattern": "^[A-Za-z0-9~][A-Za-z0-9._:/@+~-]{0,199}$"}
    slug = {"type": "string", "pattern": "^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", "maxLength": 48}
    any_map = {"type": "object", "additionalProperties": True}
    settings = obj({"api_base": {"type": "string", "format": "uri", "description": "HTTPS API 根地址；HTTP 只接受本机。不能含登录信息、查询参数或 /chat/completions、/messages 等操作路径。"},
                    "models": array(model, minItems=1, maxItems=100)}, ["api_base", "models"])
    result = {
        "ProjectError": obj({"detail": string}, ["detail"]),
        "ProjectRevisionBody": obj({"revision": revision}, ["revision"]),
        "ProjectEngineSettings": settings,
        "ProjectEnginePublic": obj({**settings["properties"], "name": string, "key_env": string, "has_key": {"type": "boolean"}}, ["api_base", "models", "name", "key_env", "has_key"]),
        "ProjectModelCatalogItem": obj({"engine": {"type": "string", "enum": ENGINES}, "model": model, "reference": string}, ["engine", "model", "reference"]),
        "ProjectModelState": obj({"revision": revision, "default_model": string, "catalog": array(ref("ProjectModelCatalogItem")),
                                  "engines": {"type": "object", "properties": {engine: ref("ProjectEnginePublic") for engine in ENGINES}, "required": ENGINES, "additionalProperties": False}},
                                 ["revision", "default_model", "catalog", "engines"]),
        "ProjectEngineSave": obj({"revision": revision, "settings": ref("ProjectEngineSettings"),
                                  "api_key": {"anyOf": [{"type": "string", "maxLength": 4096}, {"type": "null"}], "writeOnly": True, "description": "空白或省略保留原 Key；不能含空白字符。"},
                                  "clear_key": {"type": "boolean", "default": False, "description": "仅清除本机保存值；环境变量仍可提供 Key。不能与非空 api_key 同时提交。"}}, ["revision", "settings"]),
        "ProjectDefaultModel": obj({"revision": revision, "reference": string}, ["revision", "reference"]),
        "ProjectProbeInference": obj({"ok": {"const": True}, "model": string, "message": string, "latency_ms": {"type": "integer", "minimum": 0}}, ["ok", "model", "message", "latency_ms"]),
        "ProjectProbeModels": obj({"ok": {"const": True}, "models": array(model), "message": string, "latency_ms": {"type": "integer", "minimum": 0}}, ["ok", "models", "message", "latency_ms"]),
        "ProjectMcpServerInput": obj({"id": slug, "name": {"type": "string", "minLength": 1, "maxLength": 100},
                                      "transport": {"type": "string", "enum": ["streamable_http", "sse"], "default": "streamable_http"},
                                      "url": {"type": "string", "format": "uri", "maxLength": 2048},
                                      "token_env": {"type": "string", "default": "", "maxLength": 128, "description": "鉴权环境变量名，禁止填写真实 Token。"},
                                      "auth_header": {"type": "string", "default": "Authorization"},
                                      "auth_prefix": {"type": "string", "maxLength": 32, "default": "Bearer "},
                                      "enabled": {"type": "boolean", "default": True}}, ["id", "url"]),
        "ProjectMcpSave": obj({"revision": revision, "server": ref("ProjectMcpServerInput")}, ["revision", "server"]),
        "ProjectMcpTool": obj({"name": string, "description": string}, ["name", "description"]),
        "ProjectMcpBinding": obj({"server_id": slug, "tools": array(string, minItems=1, uniqueItems=True)}, ["server_id", "tools"]),
        "ProjectAgentBinding": obj({"mcp": array(ref("ProjectMcpBinding"), maxItems=30), "skills": array(slug, maxItems=50, uniqueItems=True)}, ["mcp", "skills"]),
        "ProjectBindingSave": obj({"revision": revision, "binding": ref("ProjectAgentBinding")}, ["revision", "binding"]),
        "ProjectBinaryFile": obj({"encoding": {"const": "base64"}, "data": {"type": "string", "contentEncoding": "base64"}, "size": {"type": "integer", "minimum": 0}}, ["encoding", "data"]),
        "ProjectFileValue": {"oneOf": [string, ref("ProjectBinaryFile")]},
        "ProjectSkillSave": obj({"revision": revision, "files": {"type": "object", "additionalProperties": ref("ProjectFileValue"), "minProperties": 1, "maxProperties": 100},
                                 "enabled": {"type": "boolean", "default": True}}, ["revision", "files"]),
        "ProjectSkillMetadata": obj({"id": slug, "description": string, "enabled": {"type": "boolean"}, "version": {"type": "integer", "minimum": 1},
                                     "updated_at": string, "files": array(string), "scripts": array(string)}, ["id", "description", "enabled", "version", "updated_at", "files", "scripts"]),
        "ProjectSkillRead": obj({"metadata": ref("ProjectSkillMetadata"), "files": {"type": "object", "additionalProperties": ref("ProjectFileValue")},
                                 "versions": array({"type": "integer", "minimum": 1})}, ["metadata", "files", "versions"]),
        "ProjectSseError": obj({"error": string, "error_details": any_map}, ["error", "error_details"]),
    }
    test = deepcopy(result["ProjectEngineSave"])
    test["properties"]["purpose"] = {"type": "string", "enum": ["inference", "models"], "default": "inference", "description": "inference 实际发送简短消息；models 仅读模型目录。均不保存配置。"}
    result["ProjectEngineTest"] = test
    server = deepcopy(result["ProjectMcpServerInput"])
    server["properties"].update({"tools": array(ref("ProjectMcpTool")), "tested_at": {"type": ["string", "null"]}})
    server["required"] = list(server["properties"])
    result["ProjectMcpServer"] = server
    result["ProjectCapabilityState"] = obj({"version": {"const": 1}, "revision": revision,
        "mcp_servers": {"type": "object", "additionalProperties": ref("ProjectMcpServer")},
        "skills": {"type": "object", "additionalProperties": ref("ProjectSkillMetadata")},
        "agents": {"type": "object", "additionalProperties": ref("ProjectAgentBinding")},
        "agent_names": array(string), "script_runtime": any_map},
        ["version", "revision", "mcp_servers", "skills", "agents", "agent_names", "script_runtime"])
    return result


def classify(path):
    if path.startswith("/capabilities/api/models"):
        return "Model engines", "local-management"
    if path.startswith("/capabilities"):
        return "MCP and Skills", "local-management"
    if path.startswith("/dev/apps/"):
        if "/deploy/" in path:
            return "Cloud deployment", "conditional"
        if "/builder" in path or "/build_graph" in path:
            return "Builder", "development"
        if "/eval" in path:
            return "Evaluation", "development"
        if "/tests" in path:
            return "Agent tests", "development"
        return "Debug", "development"
    if path == "/agent-identity/finalize":
        return "Agent Identity", "conditional"
    if path.startswith("/apps/"):
        if "/artifacts" in path:
            return "Artifacts", "business"
        if path.endswith("/memory"):
            return "Memory", "conditional"
        if path.endswith("/app-info"):
            return "Applications", "business"
        return "Sessions", "business"
    if path in {"/run", "/run_sse"}:
        return "Agent invocation", "business"
    if path == "/list-apps":
        return "Applications", "business"
    if path in {"/health", "/version"}:
        return "System", "business"
    return "Web UI and telemetry", "development"


def enrich(runtime, raw, date, source_commit):
    spec = deepcopy(runtime)
    spec["info"] = {"title": "AI-Agent-Server API", "version": date,
                    "description": "当前项目接口文档快照。ADK 2.12.0；本机服务，无应用级身份鉴权。业务接口与仅限本机的管理接口按 x-integration-scope 区分。"}
    spec["servers"] = [{"url": "http://127.0.0.1:8000", "description": "当前启动器的本机监听地址"}]
    spec["security"] = []
    spec["x-documentation-source"] = {"date": date, "code_commit": source_commit,
        "runtime_openapi_sha256": hashlib.sha256(raw).hexdigest(), "runtime_info": runtime["info"],
        "enrichments": ["自有管理接口请求/响应 schema 和错误响应", "SSE 正确媒体类型和事件说明", "访问范围与条件能力标记", "兼容路由重复 operationId 的文档层去重"],
        "note": "文档补全版，不更改服务端 /openapi.json；HTTP method/path 集合与运行服务保持一致。"}
    spec["x-websocket-routes"] = [{"path": "/run_live", "status": "registered-but-not-supported-by-configured-engines",
        "reason": "当前五引擎适配器没有实现 BaseLlm.connect；此路由不进入可用业务调用契约。", "reference": "README.md#10-实时连接与条件能力"}]
    spec["components"]["schemas"].update(schemas())
    ids = {}
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method in METHODS:
                ids.setdefault(operation["operationId"], []).append((method, path, operation))
    for original, entries in ids.items():
        if len(entries) > 1:
            for method, path, operation in entries:
                operation["x-runtime-operation-id"] = original
                operation["operationId"] = original + "__" + hashlib.sha256(f"{method} {path}".encode()).hexdigest()[:8]
    cap = "/capabilities/api"
    custom = {
        ("get", cap + "/state"): (None, "ProjectCapabilityState", "读取 MCP、Skill 与应用绑定状态"),
        ("put", cap + "/mcp/{sid}"): ("ProjectMcpSave", "ProjectCapabilityState", "保存 MCP 服务，不自动连接或绑定"),
        ("post", cap + "/mcp/{sid}/test"): ("ProjectRevisionBody", "ProjectCapabilityState", "连接已保存 MCP 服务并发布发现的工具"),
        ("delete", cap + "/{kind}/{identifier}"): ("ProjectRevisionBody", "ProjectCapabilityState", "移出 MCP 服务或 Skill；被绑定时拒绝"),
        ("post", cap + "/skills/import"): ("zip", "ProjectCapabilityState", "导入单个 Skill ZIP / .skill 包"),
        ("post", cap + "/skills"): ("ProjectSkillSave", "ProjectCapabilityState", "新建 Skill，不自动绑定应用"),
        ("get", cap + "/skills/{sid}"): (None, "ProjectSkillRead", "读取 Skill 文件及版本目录"),
        ("put", cap + "/skills/{sid}"): ("ProjectSkillSave", "ProjectCapabilityState", "编辑 Skill，发布新的不可变版本"),
        ("post", cap + "/skills/{sid}/restore/{version}"): ("ProjectRevisionBody", "ProjectCapabilityState", "将历史内容恢复为新的 Skill 版本"),
        ("put", cap + "/agents/{agent_name}"): ("ProjectBindingSave", "ProjectCapabilityState", "按应用保存 MCP 工具白名单与 Skill 绑定"),
        ("get", cap + "/models"): (None, "ProjectModelState", "读取模型引擎状态，不返回已保存 Key"),
        ("put", cap + "/models/default"): ("ProjectDefaultModel", "ProjectModelState", "设置新 Agent 默认模型"),
        ("put", cap + "/models/{engine}"): ("ProjectEngineSave", "ProjectModelState", "保存引擎连接及本机 Key"),
        ("post", cap + "/models/{engine}/test"): ("ProjectEngineTest", None, "测试当前表单或读取模型列表，不保存"),
    }
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in METHODS:
                continue
            tag, scope = classify(path)
            operation["tags"] = [tag]
            operation["x-integration-scope"] = scope
            if path.startswith(cap):
                body, response, summary = custom[(method, path)]
                operation["summary"] = summary
                operation["x-schema-source"] = "capabilities/api.py + capabilities/store.py" if not path.startswith(cap + "/models") else "model_engine_api.py + model_engines.py"
                if body:
                    mime, schema = ("application/zip", {"type": "string", "format": "binary"}) if body == "zip" else ("application/json", ref(body))
                    operation["requestBody"] = {"required": True, "content": {mime: {"schema": schema}}}
                if response:
                    schema = ref(response)
                else:
                    schema = {"oneOf": [ref("ProjectProbeInference"), ref("ProjectProbeModels")]}
                operation["responses"]["200"] = {"description": "操作完成；具体含义见接口说明", "content": {"application/json": {"schema": schema}}}
                errors = ["403", "500"] if method == "get" else ["400", "403", "409", "413", "415", "500"]
                if method == "get" and path.endswith("/skills/{sid}"):
                    errors += ["400", "404"]
                if path.endswith(("/test", "/{kind}/{identifier}", "/skills/{sid}", "/restore/{version}", "/agents/{agent_name}", "/models/{engine}")):
                    errors += ["404"]
                if path.endswith("/test"):
                    errors += ["502"]
                for code in sorted(set(errors)):
                    operation["responses"][code] = {"description": {"400": "业务参数或资源约束不满足", "403": "本机同源访问检查失败", "404": "资源或引擎不存在", "409": "版本冲突或资源已存在", "413": "请求过大", "415": "Content-Type 不支持", "500": "本机配置或存储错误", "502": "上游连接/推理失败"}[code], "content": {"application/json": {"schema": ref("ProjectError")}}}
                for parameter in operation.get("parameters", []):
                    if parameter["name"] == "engine":
                        parameter["schema"] = {"type": "string", "enum": ENGINES}
                    if parameter["name"] == "kind":
                        parameter["schema"] = {"type": "string", "enum": ["mcp", "skills"]}
    sse = spec["paths"]["/run_sse"]["post"]
    sse["responses"]["200"] = {"description": "SSE 流；每个 data 帧为 Event 或流内错误 JSON，结束时关闭连接，无 [DONE] 帧。", "content": {"text/event-stream": {"schema": {"type": "string"},
        "x-event-schema": {"oneOf": [ref("Event-Output"), ref("ProjectSseError")]}}}}
    sse["description"] = "POST 请求返回 text/event-stream；streaming 控制模型是否增量输出。HTTP 200 不代表后续无流内错误。"
    spec["paths"]["/run"]["post"]["description"] = "收集完整 Event 数组后返回。streaming 字段在此接口不启用 SSE。不是 OpenAI Chat Completions 接口。"
    for path in ("/run", "/run_sse"):
        for code in ("400", "403", "404"):
            spec["paths"][path]["post"]["responses"][code] = {"description": "应用参数、访问来源或会话检查失败", "content": {"application/json": {"schema": ref("ProjectError")}}}
        spec["paths"][path]["post"]["responses"]["403"]["content"]["text/plain"] = {"schema": {"type": "string"}}
    return spec


def type_name(schema):
    if "$ref" in schema:
        return "`" + schema["$ref"].rsplit("/", 1)[-1] + "`"
    if "const" in schema:
        return "`" + json.dumps(schema["const"], ensure_ascii=False) + "`"
    if "enum" in schema:
        return " / ".join("`" + str(value) + "`" for value in schema["enum"])
    if "anyOf" in schema or "oneOf" in schema:
        return " / ".join(type_name(item) for item in schema.get("anyOf", schema.get("oneOf")))
    kind = schema.get("type", "any")
    if kind == "array":
        return type_name(schema.get("items", {})) + "[]"
    return "`" + str(kind) + (" (" + schema["format"] + ")" if "format" in schema else "") + "`"


def clean(text):
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def body_properties(schema, spec):
    if "$ref" in schema:
        return body_properties(spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]], spec)
    if "anyOf" in schema:
        return next((result for item in schema["anyOf"] if (result := body_properties(item, spec))[0]), ({}, []))
    return schema.get("properties", {}), schema.get("required", [])


def reference_markdown(spec):
    entries = [(path, method, operation) for path, item in spec["paths"].items() for method, operation in item.items() if method in METHODS]
    lines = ["# 完整 HTTP 接口参考", "", "本文件由 `scripts/export_api_docs.py` 生成；业务接入流程见 [接入指南](README.md)，完整嵌套类型见 [OpenAPI 3.1](openapi.json)。", "",
             f"共 {len(spec['paths'])} 个路径、{len(entries)} 个 HTTP 操作。WebSocket `/run_live` 的当前限制见接入指南，不计入 HTTP 数量。", "",
             "范围：business＝业务调用；local-management＝本机同源配置；development＝开发 UI/调试；conditional＝需要额外服务或云配置。所有接口仍受当前监听地址与来源检查约束。", "", "## 端点索引", "",
             "| 方法 | 路径 | 分类 | 范围 |", "| --- | --- | --- | --- |"]
    for path, method, operation in entries:
        lines.append(f"| {method.upper()} | [`{path}`](#op-{operation['operationId'].lower()}) | {operation['tags'][0]} | {operation['x-integration-scope']} |")
    for path, method, operation in entries:
        lines.extend(["", f"<a id=\"op-{operation['operationId'].lower()}\"></a>", "", f"## {method.upper()} `{path}`", "", operation.get("summary", ""), "",
                      f"范围：`{operation['x-integration-scope']}`。Operation ID：`{operation['operationId']}`。"])
        if operation.get("deprecated"):
            lines.extend(["", "此操作已由框架标记为弃用；新接入使用指南中的推荐路径。"])
        parameters = operation.get("parameters", [])
        if parameters:
            lines.extend(["", "### 路径与查询参数", "", "| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |", "| --- | --- | --- | --- | --- |"])
            for parameter in parameters:
                schema = parameter.get("schema", {})
                note = ("默认 " + json.dumps(schema["default"], ensure_ascii=False) + "。" if "default" in schema else "") + parameter.get("description", schema.get("description", ""))
                lines.append(f"| `{parameter['name']}` | {parameter['in']} | {'是' if parameter.get('required') else '否'} | {clean(type_name(schema))} | {clean(note)} |")
        request = operation.get("requestBody")
        if request:
            lines.extend(["", "### 请求体", "", "是否必填：" + ("是。" if request.get("required") else "否。")])
            for mime, content in request["content"].items():
                schema = content.get("schema", {})
                lines.extend(["", f"Content-Type：`{mime}`。类型：{clean(type_name(schema))}。"])
                fields, required = body_properties(schema, spec)
                if fields:
                    lines.extend(["", "| 字段 | 必填 | 类型 | 默认值 / 说明 |", "| --- | --- | --- | --- |"])
                    for name, item in fields.items():
                        note = ("默认 " + json.dumps(item["default"], ensure_ascii=False) + "。" if "default" in item else "") + item.get("description", "")
                        lines.append(f"| `{name}` | {'是' if name in required else '否'} | {clean(type_name(item))} | {clean(note)} |")
        lines.extend(["", "### 响应", "", "| HTTP 状态 | Content-Type | 类型 | 说明 |", "| --- | --- | --- | --- |"])
        for code, response in operation["responses"].items():
            if not response.get("content"):
                lines.append(f"| {code} | — | — | {clean(response.get('description', ''))} |")
            for mime, content in response.get("content", {}).items():
                lines.append(f"| {code} | `{mime}` | {clean(type_name(content.get('schema', {})))} | {clean(response.get('description', ''))} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--source", type=Path, help="已有原始 OpenAPI 文件，适用于离线重建")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "api")
    parser.add_argument("--date", default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    args = parser.parse_args()
    if args.source:
        raw = args.source.read_bytes()
    else:
        with urllib.request.urlopen(args.base_url.rstrip("/") + "/openapi.json", timeout=20) as response:
            raw = response.read()
    runtime = json.loads(raw)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    spec = enrich(runtime, raw, args.date, commit)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "openapi.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
    (args.output / "ENDPOINTS.md").write_text(reference_markdown(spec))
    print(json.dumps({"paths": len(spec["paths"]), "operations": sum(method in METHODS for item in spec["paths"].values() for method in item), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
