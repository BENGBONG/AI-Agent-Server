"""Per-node thinking survives native YAML lifecycle and reaches the provider."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient
from google.adk.cli.utils._nested_agent_loader import NestedAgentLoader
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from litellm import ModelResponse

from adk_web import create_app
from builder_models import configure_thinking_editor, configured_browser_bundle


def agent_yaml(name, mode=None, model="deepseek-flash"):
    config = dict(name=name, agent_class="LlmAgent", model=model, instruction="Synthetic test", tools=[])
    if mode:
        config["generate_content_config"] = {
            "temperature": 0.3,
            "http_options": {"extra_body": {"thinking": {"type": mode}}},
        }
    return yaml.safe_dump(config)


class ModelThinkingTest(unittest.TestCase):
    def test_native_save_reload_and_provider_parameters_are_isolated_per_agent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with TestClient(create_app(root, reload_agents=False), base_url="http://127.0.0.1",
                            client=("127.0.0.1", 12345)) as client:
                for name, mode in (("think_on", "enabled"), ("think_off", "disabled"), ("legacy", None)):
                    response = client.post(f"/dev/apps/{name}/builder/save?tmp=true",
                                           files={"files": (f"{name}/root_agent.yaml", agent_yaml(name, mode))})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertTrue(response.json())
                    draft = client.get(f"/dev/apps/{name}/builder").text
                    self.assertEqual(yaml.safe_load(draft), yaml.safe_load(agent_yaml(name, mode)))
                    saved = client.post(f"/dev/apps/{name}/builder/save",
                                        files={"files": (f"{name}/root_agent.yaml", draft)})
                    self.assertEqual(saved.status_code, 200, saved.text)
                    self.assertTrue(saved.json())
                    self.assertFalse((root/name/"tmp").exists())
                    self.assertEqual(yaml.safe_load(client.get(f"/dev/apps/{name}/builder").text),
                                     yaml.safe_load(draft))

                # Same model, opposite switches: each Agent's native request
                # overrides the shared disabled profile, without mutating it.
                async def capture(agent):
                    args = []
                    async def complete(*a, **kw):
                        args.append(kw)
                        return ModelResponse(model="deepseek-flash", choices=[{
                            "index": 0, "message": {"role": "assistant", "content": "OK"},
                            "finish_reason": "stop"}])
                    request = LlmRequest(contents=[types.Content(role="user", parts=[types.Part(text="Synthetic")])],
                                         config=agent.generate_content_config or types.GenerateContentConfig())
                    with patch("model_runtime.require_deepseek_key", return_value=None), patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", side_effect=complete):
                        async for _ in agent.canonical_model.generate_content_async(request):
                            pass
                    return args[0]
                loader = NestedAgentLoader(str(root))
                for name, expected in (("think_on", "enabled"), ("think_off", "disabled"), ("legacy", "disabled")):
                    agent = loader.load_agent(name)
                    args = asyncio.run(capture(agent))
                    self.assertEqual(args["extra_body"]["thinking"]["type"], expected)
                    self.assertEqual(agent.canonical_model._additional_args["extra_body"]["thinking"]["type"], "disabled")
                    if name != "legacy":
                        self.assertEqual(agent.generate_content_config.temperature, 0.3)

                # Reconfigure model + switch, then reload through a new loader.
                changed = client.post("/dev/apps/think_on/builder/save", files={"files": (
                    "think_on/root_agent.yaml", agent_yaml("think_on", "disabled", "deepseek-v4-pro"))})
                self.assertTrue(changed.json())
                agent = NestedAgentLoader(str(root)).load_agent("think_on")
                args = asyncio.run(capture(agent))
                self.assertEqual(args["model"], "deepseek/deepseek-v4-pro")
                self.assertEqual(args["extra_body"]["thinking"]["type"], "disabled")

                unrelated = yaml.safe_load(agent_yaml("custom_body", "disabled"))
                unrelated["generate_content_config"]["http_options"]["extra_body"] = {"custom_setting": "retained"}
                response = client.post("/dev/apps/custom_body/builder/save", files={"files": (
                    "custom_body/root_agent.yaml", yaml.safe_dump(unrelated))})
                self.assertTrue(response.json())
                agent = NestedAgentLoader(str(root)).load_agent("custom_body")
                args = asyncio.run(capture(agent))
                self.assertEqual(args["extra_body"], {"custom_setting": "retained", "thinking": {"type": "disabled"}})
                self.assertEqual(agent.generate_content_config.http_options.extra_body, {"custom_setting": "retained"})

    def test_nested_agents_keep_their_own_settings(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = yaml.safe_load(agent_yaml("parent", "disabled"))
            config["sub_agents"] = [{"config_path": "./child.yaml"}]
            with TestClient(create_app(root, reload_agents=False), base_url="http://127.0.0.1",
                            client=("127.0.0.1", 12345)) as client:
                saved = client.post("/dev/apps/parent/builder/save", files=[
                    ("files", ("parent/root_agent.yaml", yaml.safe_dump(config))),
                    ("files", ("parent/child.yaml", agent_yaml("child", "enabled"))),
                ])
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertTrue(saved.json())
            agent = NestedAgentLoader(str(root)).load_agent("parent")
            def mode(node): return node.generate_content_config.http_options.extra_body["thinking"]["type"]
            self.assertEqual(mode(agent), "disabled")
            self.assertEqual(mode(agent.sub_agents[0]), "enabled")

    def test_editor_adaptation_rejects_version_drift(self):
        with self.assertRaisesRegex(RuntimeError, "model form changed"):
            configure_thinking_editor("unknown upstream bundle")
        _, source = configured_browser_bundle()
        self.assertIn("window.__adkModelEditor=this", source)
        self.assertIn("generate_content_config:r.generate_content_config", source)
        self.assertIn("generate_content_config:o.generate_content_config", source)
        self.assertIn("c.generate_content_config=t.generate_content_config", source)


if __name__ == "__main__":
    unittest.main()
