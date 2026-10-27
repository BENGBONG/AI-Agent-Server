"""Opt-in live acceptance of native YAML thinking settings; synthetic data only.

Run with LITELLM_LOCAL_MODEL_COST_MAP=True .venv/bin/python validate_model_thinking.py
Consumes DeepSeek API usage. No production Agent/settings/session is modified.
Only booleans and field lengths are recorded, never reasoning text or keys.
"""
import asyncio
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.adk import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.lite_llm import LiteLLMClient
from google.adk.sessions import InMemorySessionService
from google.genai import types
import yaml

from adk_web import create_app, DraftAwareAgentLoader


async def verify(agent, mode):
    requests = []
    original = LiteLLMClient.acompletion

    async def observed(self, **kwargs):
        requests.append({
            "thinking": kwargs.get("extra_body", {}).get("thinking"),
            "assistant_history": [{"reasoning_chars": len(m.get("reasoning_content") or ""),
                                   "tool_call": bool(m.get("tool_calls"))}
                                  for m in kwargs.get("messages", []) if m.get("role") == "assistant"],
        })
        return await original(self, **kwargs)

    sessions = InMemorySessionService()
    runner = Runner(agent=agent, app_name=agent.name, session_service=sessions)
    session = await sessions.create_session(app_name=agent.name, user_id="synthetic")
    turns = []
    try:
        with patch.object(LiteLLMClient, "acompletion", observed):
            for prompt in ("请调用 get_beijing_time 查询当前北京时间，用一句话回答。", "请再次调用 get_beijing_time 重新查时间，用一句话回答。"):
                result = {"thinking_seen": False, "calls": [], "returns": [], "answer_seen": False, "errors": []}
                async for event in runner.run_async(user_id="synthetic", session_id=session.id,
                        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
                        run_config=RunConfig(streaming_mode=StreamingMode.SSE)):
                    if event.error_code:
                        result["errors"].append(event.error_code)
                    if event.partial:
                        continue
                    for part in event.content.parts if event.content else []:
                        if part.thought and part.text: result["thinking_seen"] = True
                        if part.function_call: result["calls"].append(part.function_call.name)
                        if part.function_response: result["returns"].append(part.function_response.name)
                        if part.text and not part.thought: result["answer_seen"] = True
                turns.append(result)
    finally:
        await runner.close()
    return {"mode": mode, "streaming": True, "turns": turns, "requests": requests,
            "passed": all(t["calls"] == ["get_beijing_time"] and t["returns"] == ["get_beijing_time"]
                          and t["answer_seen"] and not t["errors"] for t in turns)
                and all(r["thinking"] == {"type": mode} for r in requests)
                and (any(t["thinking_seen"] for t in turns) if mode == "enabled"
                     else not any(t["thinking_seen"] for t in turns))}


def main():
    results = []
    with TemporaryDirectory(prefix="adk-thinking-acceptance-") as directory:
        root = Path(directory)
        with TestClient(create_app(root, reload_agents=False), base_url="http://127.0.0.1",
                        client=("127.0.0.1", 12345)) as client:
            for model in ("deepseek-flash", "deepseek-v4-pro"):
                for mode in ("enabled", "disabled"):
                    name = "thinking_" + str(len(results))
                    config = dict(name=name, agent_class="LlmAgent", model=model,
                                  instruction="合成连通性验收。必须调用 get_beijing_time，再根据工具返回用一句话回答。",
                                  tools=[{"name": name + ".tool_entries.get_beijing_time"}],
                                  generate_content_config={"http_options": {"extra_body": {"thinking": {"type": mode}}}})
                    response = client.post(f"/dev/apps/{name}/builder/save",
                                           files={"files": (f"{name}/root_agent.yaml", yaml.safe_dump(config, allow_unicode=True))})
                    response.raise_for_status()
                    assert response.json() is True
                    reloaded = yaml.safe_load(client.get(f"/dev/apps/{name}/builder").text)
                    assert reloaded["generate_content_config"] == config["generate_content_config"]
                    agent = DraftAwareAgentLoader(str(root)).load_agent(name)
                    result = asyncio.run(asyncio.wait_for(verify(agent, mode), timeout=100))
                    result["model"] = model
                    result["native_yaml_save_reload"] = True
                    results.append(result)
                    print(json.dumps({"model": model, "mode": mode, "passed": result["passed"]}), flush=True)
    proof = {"checked_at": datetime.now().astimezone().isoformat(), "synthetic_only": True,
             "production_config_modified": False, "results": results,
             "passed": all(r["passed"] for r in results)}
    (Path(__file__).parent / "validation_model_thinking.json").write_text(json.dumps(proof, indent=2) + "\n")
    if not proof["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
