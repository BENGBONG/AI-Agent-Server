"""Model connections, credential boundaries and native Agent persistence."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from litellm import ModelResponse
import yaml

from adk_web import create_app
from model_engines import EngineStore, PROVIDERS, ConfigError, engine_reference, use_engine_store
from model_runtime import ConfiguredEngine, DynamicDefaultModel
from model_engine_api import probe_engine


class ModelEnginesTest(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = EngineStore(self.root)

    def save(self, engine, key=None, models=None):
        state = self.store.snapshot()
        current = state["engines"][engine]
        return self.store.save(engine, {"api_base": current["api_base"], "models": models or current["models"]},
                               state["revision"], api_key=key)

    def test_legacy_seed_has_five_engines_without_creating_or_migrating_files(self):
        state = self.store.snapshot()
        self.assertEqual(set(state["engines"]), set(PROVIDERS))
        self.assertEqual(state["default_model"], "deepseek-flash")
        self.assertEqual(self.store.resolve("deepseek-flash")[:2], ("deepseek", "deepseek-flash"))
        self.assertFalse(self.store.path.exists())
        self.assertFalse(self.store.env_path.exists())

    def test_key_is_private_blank_preserves_and_explicit_clear_works(self):
        self.store.env_path.write_text("UNRELATED_SETTING='preserve'\n")
        self.save("kimi", "synthetic-kimi-key")
        self.assertTrue(self.store.snapshot()["engines"]["kimi"]["has_key"])
        self.assertNotIn("synthetic-kimi-key", json.dumps(self.store.snapshot()))
        self.assertNotIn("synthetic-kimi-key", self.store.path.read_text())
        self.save("kimi", "")
        self.assertEqual(self.store.key("kimi"), "synthetic-kimi-key")
        state = self.store.snapshot()
        config = state["engines"]["kimi"]
        self.store.save("kimi", {"api_base": config["api_base"], "models": config["models"]}, state["revision"], clear_key=True)
        self.assertFalse(self.store.snapshot()["engines"]["kimi"]["has_key"])
        self.assertIn("UNRELATED_SETTING='preserve'", self.store.env_path.read_text())
        self.assertEqual(self.store.env_path.stat().st_mode & 0o777, 0o600)

    def test_stale_save_does_not_change_key_and_draft_does_not_save(self):
        before = self.store.snapshot()
        self.save("openai", "synthetic-first-key")
        config = before["engines"]["openai"]
        settings = {"api_base": config["api_base"], "models": config["models"]}
        with self.assertRaises(ConfigError) as error:
            self.store.save("openai", settings, before["revision"], api_key="synthetic-stale-key")
        self.assertEqual(error.exception.status, 409)
        _, key = self.store.draft("openai", settings, api_key="synthetic-draft-key")
        self.assertEqual(key, "synthetic-draft-key")
        self.assertEqual(self.store.key("openai"), "synthetic-first-key")

    def test_failed_config_write_restores_the_previous_key(self):
        self.save("openai", "synthetic-original-key")
        write = self.store._write
        def fail_config(path, contents):
            if path == self.store.path:
                raise OSError("Synthetic disk error")
            write(path, contents)
        with patch.object(self.store, "_write", side_effect=fail_config), self.assertRaises(ConfigError):
            self.save("openai", "synthetic-replacement-key")
        self.assertEqual(self.store.key("openai"), "synthetic-original-key")

    def test_invalid_local_default_is_a_recoverable_configuration_error(self):
        config = self.store.read()
        config["default_model"] = None
        self.store.path.write_text(json.dumps(config))
        with self.assertRaises(ConfigError):
            self.store.snapshot()

    def test_different_api_host_cannot_reuse_saved_key_implicitly(self):
        self.save("openai", "synthetic-private-key")
        with self.assertRaises(ConfigError):
            self.store.draft("openai", {"api_base": "https://other.example/v1", "models": ["gpt-4.1-mini"]})

    def test_invalid_settings_do_not_touch_credentials(self):
        for base in ("https://user:secret@example.com", "https://example.com?key=bad", "http://example.com", "https://example.com/v1/chat/completions"):
            with self.subTest(base=base), self.assertRaises(ConfigError):
                self.store.draft("kimi", {"api_base": base, "models": ["kimi-test"]}, "synthetic")
        self.assertFalse(self.store.env_path.exists())

    def test_five_routes_use_only_the_selected_key_and_no_deepseek_options_leak(self):
        for engine in PROVIDERS:
            self.save(engine, "synthetic-" + engine)
        environment = dict(os.environ)
        async def check():
            captured = []
            async def complete(*args, **kwargs):
                captured.append(kwargs)
                return ModelResponse(model=kwargs["model"], choices=[{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}])
            request = LlmRequest(contents=[types.Content(role="user", parts=[types.Part(text="Synthetic")])],
                                 config=types.GenerateContentConfig(temperature=0.3, http_options=types.HttpOptions(extra_body={"thinking": {"type": "enabled"}, "custom_setting": "retained"})))
            with use_engine_store(self.store), patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", side_effect=complete):
                for engine in PROVIDERS:
                    model_id = self.store.read()["engines"][engine]["models"][0]
                    model = ConfiguredEngine(model=engine_reference(engine, model_id))
                    async for _ in model.generate_content_async(request):
                        pass
                    args = captured[-1]
                    self.assertEqual(args["api_key"], "synthetic-" + engine)
                    self.assertEqual(args["model"], PROVIDERS[engine]["provider"] + "/" + model_id)
                    self.assertEqual(args["extra_body"].get("thinking"), {"type": "enabled"} if engine == "deepseek" else None)
                    self.assertEqual(args["extra_body"]["custom_setting"], "retained")
                self.assertEqual(request.config.http_options.extra_body["thinking"]["type"], "enabled")
        asyncio.run(check())
        self.assertEqual(dict(os.environ), environment)

    def test_cached_model_reads_rotated_key_and_endpoint_on_next_request(self):
        self.save("openai", "synthetic-old")
        with use_engine_store(self.store):
            model = ConfiguredEngine(model="engine/openai/gpt-4.1-mini")
        state = self.store.snapshot()
        self.store.save("openai", {"api_base": "https://api.openai.com/custom/v1", "models": ["gpt-4.1-mini"]},
                        state["revision"], api_key="synthetic-new")
        async def check():
            args = []
            async def complete(*a, **kw):
                args.append(kw)
                return ModelResponse(choices=[{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}])
            with patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", side_effect=complete):
                async for _ in model.generate_content_async(LlmRequest(contents=[types.Content(role="user", parts=[types.Part(text="Synthetic")])])):
                    pass
            self.assertEqual(args[0]["api_key"], "synthetic-new")
            self.assertEqual(args[0]["api_base"], "https://api.openai.com/custom/v1")
        asyncio.run(check())

    def test_missing_key_never_calls_provider(self):
        async def check():
            with use_engine_store(self.store), patch.dict(os.environ, {}, clear=True), patch("google.adk.models.lite_llm.LiteLLMClient.acompletion") as complete:
                model = ConfiguredEngine(model="engine/openai/gpt-4.1-mini")
                result = [event async for event in model.generate_content_async(LlmRequest())]
                self.assertIn("API Key", result[0].content.parts[0].text)
                complete.assert_not_called()
        asyncio.run(check())

    def test_same_origin_api_redacts_keys_and_saves_native_parent_and_child_models(self):
        with TestClient(create_app(self.root, reload_agents=False, engine_store=self.store), base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
            state = client.get("/capabilities/api/models").json()
            response = client.put("/capabilities/api/models/openai", json={"revision": state["revision"], "settings": {"api_base": "https://api.openai.com/v1", "models": ["gpt-4.1-mini"]}, "api_key": "synthetic-secret-key"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("synthetic-secret-key", response.text)
            self.assertEqual(client.get("/capabilities/api/models", headers={"origin": "https://outside.example"}).status_code, 403)
            root = {"name": "engine_parent", "agent_class": "LlmAgent", "model": "engine/openai/gpt-4.1-mini", "instruction": "Synthetic", "sub_agents": [{"config_path": "./child.yaml"}], "generate_content_config": {"temperature": 0.3}, "tools": []}
            child = {"name": "engine_child", "agent_class": "LlmAgent", "model": "engine/claude/claude-sonnet-4-6", "instruction": "Synthetic", "tools": []}
            response = client.post("/dev/apps/engine_parent/builder/save", files=[("files", ("engine_parent/root_agent.yaml", yaml.safe_dump(root))), ("files", ("engine_parent/child.yaml", yaml.safe_dump(child)))])
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json())
            graph = client.get("/dev/apps/engine_parent/build_graph")
            self.assertEqual(graph.status_code, 200, graph.text)
            self.assertEqual(graph.json()["root_agent"]["model"], root["model"])
            self.assertNotIn("synthetic-secret-key", graph.text)
            saved = yaml.safe_load(client.get("/dev/apps/engine_parent/builder").text)
            self.assertEqual(saved["generate_content_config"], {"temperature": 0.3})

    def test_draft_connection_probes_all_providers_without_saving_and_redacts_failures(self):
        with TestClient(create_app(self.root, reload_agents=False, engine_store=self.store), base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
            for engine in PROVIDERS:
                state = self.store.snapshot()
                settings = state["engines"][engine]
                body = {"revision": state["revision"], "settings": {"api_base": settings["api_base"], "models": settings["models"]}, "api_key": "synthetic-probe-private"}
                result = ModelResponse(choices=[{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}])
                with patch("model_engine_api.litellm.acompletion", new=AsyncMock(return_value=result)) as complete:
                    response = client.post("/capabilities/api/models/" + engine + "/test", json=body)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()["ok"])
                self.assertEqual(complete.call_args.kwargs["api_key"], "synthetic-probe-private")
                self.assertNotIn("synthetic-probe-private", response.text)
                self.assertFalse(self.store.path.exists())
                self.assertFalse(self.store.env_path.exists())
                with patch("model_engine_api.litellm.acompletion", new=AsyncMock(side_effect=RuntimeError("synthetic-probe-private upstream reflected key"))):
                    failed = client.post("/capabilities/api/models/" + engine + "/test", json=body)
                self.assertEqual(failed.status_code, 502)
                self.assertNotIn("synthetic-probe-private", failed.text)

    def test_claude_model_discovery_uses_native_auth_and_does_not_replace_form_model(self):
        import httpx
        real_client = httpx.AsyncClient
        def serve(request):
            self.assertEqual(request.url.path, "/v1/models")
            self.assertEqual(request.headers["x-api-key"], "synthetic-claude")
            self.assertIn("anthropic-version", request.headers)
            return httpx.Response(200, json={"data": [{"id": "claude-sonnet-4-6"}, {"id": "invalid model"}]})
        settings = self.store.read()["engines"]["claude"]
        with patch("model_engine_api.httpx.AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(serve), **kwargs)):
            result = asyncio.run(probe_engine(self.store, "claude", settings, "synthetic-claude", discover=True))
        self.assertEqual(result["models"], ["claude-sonnet-4-6"])
        self.assertFalse(self.store.path.exists())

    def test_default_model_updates_bundle_and_keeps_existing_agent_yaml(self):
        self.save("openai", "synthetic-openai")
        from builder_models import configured_browser_bundle
        with TestClient(create_app(self.root, reload_agents=False, engine_store=self.store), base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
            app_dir = self.root / "legacy_agent"
            app_dir.mkdir()
            original = "name: legacy_agent\nagent_class: LlmAgent\nmodel: deepseek-flash\ninstruction: Synthetic\n"
            (app_dir / "root_agent.yaml").write_text(original)
            state = self.store.snapshot()
            response = client.put("/capabilities/api/models/default", json={"revision": state["revision"], "reference": "engine/openai/gpt-4.1-mini"})
            self.assertEqual(response.status_code, 200, response.text)
            path, _ = configured_browser_bundle(self.store)
            bundle = client.get(path)
            self.assertIn('model:"engine/openai/gpt-4.1-mini"', bundle.text)
            self.assertEqual((app_dir / "root_agent.yaml").read_text(), original)

    def test_cached_builder_assistant_follows_the_new_default_connection(self):
        self.save("deepseek", "synthetic-deepseek")
        assistant_model = DynamicDefaultModel(model="deepseek-flash", engine_store=self.store)
        self.save("openai", "synthetic-openai")
        state = self.store.snapshot()
        self.store.set_default("engine/openai/gpt-4.1-mini", state["revision"])
        async def check():
            result = ModelResponse(choices=[{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}])
            for outer_model in ("deepseek-flash", "engine/openai/gpt-4.1-mini"):
                request = LlmRequest(model=outer_model, contents=[types.Content(role="user", parts=[types.Part(text="Synthetic")])])
                with patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", new=AsyncMock(return_value=result)) as complete:
                    async for _ in assistant_model.generate_content_async(request):
                        pass
                self.assertEqual(complete.call_args.kwargs["api_key"], "synthetic-openai")
                self.assertEqual(complete.call_args.kwargs["model"], "openai/gpt-4.1-mini")
                self.assertEqual(request.model, outer_model)
        asyncio.run(check())
