"""Regression coverage for Visual Builder's create/edit/save lifecycle."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from adk_web import create_app
from builder_models import configured_browser_bundle, DEFAULT_TOKEN, SELECTOR_TOKEN
from model_runtime import ConfiguredDeepSeek, default_model_id
from builder_tools import local_tool_names, WRAPPER_FILE
from google.adk import Agent
from google.adk.cli.utils._nested_agent_loader import NestedAgentLoader


class BuilderLifecycleTest(unittest.TestCase):
    def test_capability_extension_is_served_in_adk_without_touching_native_assets(self):
        with TemporaryDirectory() as directory:
            with TestClient(create_app(Path(directory), reload_agents=False),
                            base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
                for path in ("/dev-ui/", "/dev-ui/index.html"):
                    page = client.get(path + "?app=synthetic&mode=builder")
                    self.assertEqual(page.status_code, 200)
                    self.assertIn('/capabilities/assets/adk-integration.js', page.text)
                    self.assertIn('/capabilities/assets/adk-integration.css', page.text)
                    self.assertIn('<app-root', page.text)
                    self.assertEqual(int(page.headers['content-length']), len(page.content))
                    self.assertEqual(page.headers['cache-control'], 'no-store')
                self.assertIn('/capabilities/assets/model-thinking.js', page.text)
                for name in ('adk-integration.js', 'adk-integration.css', 'model-thinking.js'):
                    asset = client.get('/capabilities/assets/' + name)
                    self.assertEqual(asset.status_code, 200)
                    denied = client.get('/capabilities/assets/' + name,
                                        headers={'Origin': 'https://outside.example'})
                    self.assertEqual(denied.status_code, 403)
                refreshed = client.get('/dev-ui/', headers={'If-None-Match': '*',
                                        'If-Modified-Since': 'Wed, 01 Jan 2099 00:00:00 GMT'})
                self.assertEqual(refreshed.status_code, 200)
                self.assertIn('/capabilities/assets/adk-integration.js', refreshed.text)
                self.assertEqual(client.get('/list-apps').json(), [])

    def test_new_draft_can_be_discovered_loaded_edited_and_saved(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            yaml = (
                "name: builder_probe\n"
                "agent_class: LlmAgent\n"
                "model: deepseek-flash\n"
                "instruction: Original instruction\n"
                "tools: []\n"
            )
            app = create_app(root, reload_agents=False)
            with TestClient(
                app,
                base_url="http://127.0.0.1",
                client=("127.0.0.1", 12345),
            ) as client:
                url = "/dev/apps/builder_probe/builder/save"
                response = client.post(
                    url + "?tmp=true",
                    files={"files": ("builder_probe/root_agent.yaml", yaml)},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json())
                self.assertFalse((root / "builder_probe/root_agent.yaml").exists())
                self.assertIn("builder_probe", client.get("/list-apps").json())
                info = client.get("/apps/builder_probe/app-info")
                self.assertEqual(info.status_code, 200, info.text)
                # This exact request controls the UI's Edit button. A draft
                # must be editable even before its first explicit Save.
                editor_config = client.get("/dev/apps/builder_probe/builder")
                self.assertEqual(editor_config.status_code, 200, editor_config.text)
                self.assertIn("Original instruction", editor_config.text)
                draft = client.get("/dev/apps/builder_probe/builder?tmp=true")
                self.assertEqual(draft.status_code, 200, draft.text)
                self.assertIn("Original instruction", draft.text)

                updated = yaml.replace("Original instruction", "Updated instruction").replace(
                    "model: deepseek-flash", "model: deepseek-v4-pro",
                )
                saved = client.post(
                    url,
                    files={"files": ("builder_probe/root_agent.yaml", updated)},
                )
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertTrue(saved.json())
                self.assertIn("builder_probe", client.get("/list-apps").json())
                self.assertFalse((root / "builder_probe/tmp").exists())
                self.assertIn(
                    "Updated instruction",
                    client.get("/dev/apps/builder_probe/builder").text,
                )
                self.assertIn("model: deepseek-v4-pro", client.get(
                    "/dev/apps/builder_probe/builder",
                ).text)
                reloaded = NestedAgentLoader(str(root)).load_agent("builder_probe")
                self.assertIsInstance(reloaded.canonical_model, ConfiguredDeepSeek)
                self.assertEqual(reloaded.canonical_model.model, "deepseek/deepseek-v4-pro")

    def test_frontend_default_catalog_and_builder_assistant_use_deepseek(self):
        with TemporaryDirectory() as directory:
            app = create_app(Path(directory), reload_agents=False)
            with TestClient(
                app,
                base_url="http://127.0.0.1",
                client=("127.0.0.1", 12345),
            ) as client:
                path, _ = configured_browser_bundle()
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn(SELECTOR_TOKEN, response.text)
                self.assertNotIn(DEFAULT_TOKEN, response.text)
                self.assertIn('models=["deepseek-flash", "deepseek-v4-pro",', response.text)
                for engine in ("kimi", "openai", "claude", "openrouter"):
                    self.assertIn('"engine/' + engine + '/', response.text)
                self.assertIn('model:"deepseek-flash"', response.text)
                self.assertTrue('name:"DeepSeek 联网工具（本地）"' in response.text, "Local web tool category missing")
                self.assertTrue('name:"通用工具（本地）"' in response.text, "Common tool category missing")
                for name in ("deepseek_search", "deepseek_fetch"):
                    self.assertTrue(name in response.text, f"Tool missing from bundle: {name}")
                self.assertTrue('.some(n=>this.selectedBuiltInTool.endsWith(n))?"Function tool"' in response.text, "Local tool must serialize as Function tool")
                self.assertTrue('"DeepSeek 网页搜索"' in response.text and '"DeepSeek 网页读取"' in response.text, "Tool labels must remain readable in the picker")
                assistant = client.get("/dev/apps/__adk_agent_builder_assistant/build_graph")
                self.assertEqual(assistant.status_code, 200, assistant.text)
                self.assertEqual(assistant.json()["root_agent"]["model"], default_model_id())
                default = Agent(name="default_probe").canonical_model
                self.assertIsInstance(default, ConfiguredDeepSeek)
                self.assertEqual(default.model, "deepseek/deepseek-flash")

    def test_web_tools_survive_builder_save_and_agent_load(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            yaml = (
                "name: web_probe\nagent_class: LlmAgent\nmodel: deepseek-flash\n"
                "instruction: Use public web tools.\ntools:\n"
                + "".join(f"- name: {name}\n" for name in local_tool_names("web_probe"))
            )
            with TestClient(create_app(root, reload_agents=False), base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
                response = client.post("/dev/apps/web_probe/builder/save", files={"files": ("web_probe/root_agent.yaml", yaml)})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json())
                self.assertTrue((root / "web_probe" / WRAPPER_FILE).is_file())
                graph = client.get("/dev/apps/web_probe/build_graph")
                self.assertEqual(graph.status_code, 200, graph.text)
                editor = client.get("/dev/apps/web_probe/builder")
                for name in local_tool_names("web_probe"):
                    self.assertIn(name, editor.text)
                    self.assertIn(name.rsplit(".", 1)[-1], graph.text)
            agent = NestedAgentLoader(str(root)).load_agent("web_probe")
            names = [getattr(tool, "name", getattr(tool, "__name__", "")) for tool in agent.tools]
            self.assertEqual(names, [name.rsplit(".", 1)[-1] for name in local_tool_names("web_probe")])


if __name__ == "__main__":
    unittest.main()
