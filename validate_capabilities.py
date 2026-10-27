"""Opt-in live DeepSeek acceptance. Uses only synthetic data and temporary apps.

Run: LITELLM_LOCAL_MODEL_COST_MAP=True .venv/bin/python validate_capabilities.py
Consumes model API usage; never sends real uploaded bills.
"""

import json
from pathlib import Path
import socket
import threading
import time
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from mcp.server.mcpserver import MCPServer
import uvicorn

from adk_web import create_app


def digest(events):
    result = {"calls": [], "tool_results": [], "text": ""}
    texts = []
    for event in events:
        for part in (event.get("content") or {}).get("parts", []):
            call = part.get("functionCall") or part.get("function_call")
            response = part.get("functionResponse") or part.get("function_response")
            if call:
                result["calls"].append({"name": call["name"], "args": call.get("args")})
            if response:
                result["tool_results"].append({"name": response["name"], "response": response.get("response")})
            if part.get("text"):
                texts.append(part["text"])
    result["text"] = "\n".join(texts)
    return result


def main():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    mcp = MCPServer("Synthetic acceptance", log_level="ERROR")
    remote_calls = []

    @mcp.tool()
    def echo(value: str) -> dict:
        remote_calls.append(value)
        return {"status": "ok", "value": value, "synthetic_only": True}

    service = uvicorn.Server(uvicorn.Config(mcp.streamable_http_app(), host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=service.run, daemon=True)
    thread.start()
    proof = {"synthetic_data_only": True, "model": "deepseek-flash"}
    try:
        for _ in range(100):
            if service.started:
                break
            time.sleep(.02)
        assert service.started
        with TemporaryDirectory(prefix="adk-capability-acceptance-") as temporary:
            root = Path(temporary)
            app_name = "capability_live_probe"
            folder = root / app_name
            folder.mkdir()
            source = """name: capability_live_probe
agent_class: LlmAgent
model: deepseek-flash
instruction: |
  使用简体中文，使用本轮实际可用的技能完成用户的合成连通性验证。先 list_skills，再 load_skill，按技能正文调用工具并返回实际结果。没有当前可用技能或工具时直接说明未启用，不虚构调用，不沿用历史结果冒充新调用。
tools:
- name: get_user_choice
"""
            (folder / "root_agent.yaml").write_text(source)
            application = create_app(root, reload_agents=False)
            with TestClient(application, base_url="http://127.0.0.1", client=("127.0.0.1", 10000)) as client:
                def invoke(method, path, body=None):
                    response = client.request(method, path, json=body)
                    if response.status_code != 200:
                        raise RuntimeError("Acceptance API returned HTTP " + str(response.status_code))
                    return response.json()

                state = invoke("GET", "/capabilities/api/state")
                server = {"id": "synthetic", "name": "合成验证", "transport": "streamable_http", "url": f"http://127.0.0.1:{port}/mcp", "token_env": "", "auth_header": "Authorization", "auth_prefix": "Bearer ", "enabled": True}
                state = invoke("PUT", "/capabilities/api/mcp/synthetic", {"revision": state["revision"], "server": server})
                state = invoke("POST", "/capabilities/api/mcp/synthetic/test", {"revision": state["revision"]})
                proof["mcp_discovered_tools"] = state["mcp_servers"]["synthetic"]["tools"]
                content = """---
name: validation-skill
description: 执行纯合成的 MCP 连通性验证，不处理真实业务信息。
---

调用 mcp_synthetic_echo(value="ADK-SKILL-OK")，取得结果后回复 SKILL-MCP-OK 并附上返回的 value。未调用成功时不得输出通过标记。不进行真实金融业务操作。
"""
                state = invoke("POST", "/capabilities/api/skills", {"revision": state["revision"], "files": {"SKILL.md": content}, "enabled": True})
                state = invoke("PUT", "/capabilities/api/agents/" + app_name, {"revision": state["revision"], "binding": {"mcp": [{"server_id": "synthetic", "tools": ["echo"]}], "skills": ["validation-skill"]}})
                session = invoke("POST", f"/apps/{app_name}/users/synthetic/sessions", {})

                def run(text):
                    return digest(invoke("POST", "/run", {"app_name": app_name, "user_id": "synthetic", "session_id": session["id"], "new_message": {"role": "user", "parts": [{"text": text}]}}))

                proof["bound_invocation"] = run("请使用 validation-skill 技能完成合成连通性测试。")
                names = [x["name"] for x in proof["bound_invocation"]["calls"]]
                assert all(x in names for x in ["list_skills", "load_skill", "mcp_synthetic_echo"])
                assert "SKILL-MCP-OK" in proof["bound_invocation"]["text"] and remote_calls == ["ADK-SKILL-OK"]
                calls_before_unbind = len(remote_calls)
                state = invoke("PUT", "/capabilities/api/agents/" + app_name, {"revision": state["revision"], "binding": {"mcp": [], "skills": []}})
                proof["same_runner_after_unbind"] = run("再次执行合成测试，只用当前绑定工具与技能；如果没有就说明未启用，不能用上次结果冒充执行。")
                proof["no_remote_execution_after_unbind"] = len(remote_calls) == calls_before_unbind
                assert proof["no_remote_execution_after_unbind"]
                for result in proof["same_runner_after_unbind"]["tool_results"]:
                    assert "error" in (result["response"] or {}), "Unbound capability unexpectedly executed."
                proof["agent_yaml_unchanged"] = (folder / "root_agent.yaml").read_text() == source
                assert proof["agent_yaml_unchanged"]
        proof["status"] = "PASS"
    except Exception as error:
        proof.update(status="FAILED", error_type=type(error).__name__)
        raise
    finally:
        service.should_exit = True
        thread.join(3)
        Path("validation_capabilities.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(proof, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
