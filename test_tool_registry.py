"""Registry integration: metadata, signatures, delegates and safe migration."""

import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from google.adk.tools import FunctionTool
from google.adk.cli.utils._nested_agent_loader import NestedAgentLoader

from builder_models import configured_browser_bundle
from builder_tools import install_registered_tools, LEGACY_WRAPPER_SOURCE, render_entrypoint, WRAPPER_FILE
from shared_tools import registry


async def sample_async(query: str, count: int = 5) -> dict:
    """Test async argument forwarding."""
    return {"query": query, "count": count}


def sample_sync(value: int = 2) -> dict:
    """Test sync argument forwarding."""
    return {"value": value}


class RegistryTest(unittest.IsolatedAsyncioTestCase):
    async def test_bound_tools_preserve_signature_schema_and_call_behavior(self):
        tools = (registry.ToolSpec(sample_async, "异步工具", "测试"), registry.ToolSpec(sample_sync, "同步工具", "测试"))
        namespace = {"__name__": "sample_app.tool_entries"}
        with patch.object(registry, "TOOLS", tools):
            registry.bind_tools(namespace, [tool.name for tool in tools])
        async_entry, sync_entry = namespace["sample_async"], namespace["sample_sync"]
        self.assertTrue(inspect.iscoroutinefunction(async_entry))
        self.assertFalse(inspect.iscoroutinefunction(sync_entry))
        self.assertEqual(inspect.signature(async_entry), inspect.signature(sample_async))
        self.assertEqual(async_entry.__module__, "sample_app.tool_entries")
        self.assertEqual(async_entry.__qualname__, "sample_async")
        self.assertEqual(await async_entry("hello", count=3), {"query": "hello", "count": 3})
        self.assertEqual(sync_entry(), {"value": 2})
        schema = FunctionTool(async_entry)._get_declaration().parameters_json_schema
        self.assertEqual(schema["required"], ["query"])
        self.assertEqual(schema["properties"]["count"]["default"], 5)

    async def test_single_registration_updates_picker_and_generated_module(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "registry_probe"
            app.mkdir()
            (app / "root_agent.yaml").write_text("name: registry_probe\nagent_class: LlmAgent\n")
            extra = registry.ToolSpec(sample_async, "新增测试工具", "新增分类")
            with patch.object(registry, "TOOLS", (*registry.TOOLS, extra)):
                _, bundle = configured_browser_bundle()
                self.assertTrue('"新增测试工具"' in bundle)
                self.assertTrue('"新增分类"' in bundle)
                install_registered_tools(root)
                namespace = {"__name__": "registry_probe.tool_entries"}
                exec((app / WRAPPER_FILE).read_text(), namespace)
                self.assertEqual(await namespace["sample_async"]("new"), {"query": "new", "count": 5})
            # Removing a registration also updates the generated module.
            install_registered_tools(root)
            self.assertNotIn('"sample_async"', (app / WRAPPER_FILE).read_text())

    async def test_legacy_migration_and_custom_files_are_not_overwritten(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "legacy_probe"
            app.mkdir()
            (app / "root_agent.yaml").write_text("name: legacy_probe\nagent_class: LlmAgent\n")
            legacy = app / "deepseek_web_tools.py"
            legacy.write_text(LEGACY_WRAPPER_SOURCE)
            install_registered_tools(root)
            self.assertIn("shared_tools.registry", legacy.read_text())
            namespace = {"__name__": "legacy_probe.deepseek_web_tools"}
            exec(legacy.read_text(), namespace)
            self.assertEqual(inspect.signature(namespace["deepseek_search"]), inspect.signature(registry.deepseek_search))
            # A marker followed by arbitrary Python is not a managed template.
            custom = render_entrypoint(("deepseek_search",)) + "custom = True\n"
            (app / WRAPPER_FILE).write_text(custom)
            with self.assertRaisesRegex(RuntimeError, "custom content"):
                install_registered_tools(root)
            self.assertEqual((app / WRAPPER_FILE).read_text(), custom)

    async def test_old_yaml_references_still_load_and_shared_package_is_not_an_agent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "legacy_load_probe"
            app.mkdir()
            (app / "root_agent.yaml").write_text(
                "name: legacy_load_probe\nagent_class: LlmAgent\nmodel: deepseek-flash\ninstruction: Test legacy tools.\n"
                "tools:\n- name: legacy_load_probe.deepseek_web_tools.deepseek_search\n"
            )
            install_registered_tools(root)
            agent = NestedAgentLoader(str(root)).load_agent("legacy_load_probe")
            tool = FunctionTool(agent.tools[0])
            self.assertEqual(tool.name, "deepseek_search")
            schema = tool._get_declaration().parameters_json_schema
            self.assertEqual(schema["required"], ["query"])
        project = Path(__file__).resolve().parent
        self.assertNotIn("shared_tools", NestedAgentLoader(str(project)).list_agents())

    async def test_legacy_python_exports_still_reference_the_shared_functions(self):
        import model_runtime
        import web_tools
        self.assertIs(web_tools.deepseek_search, registry.deepseek_search)
        self.assertIs(web_tools.deepseek_fetch, registry.deepseek_fetch)
        self.assertIs(model_runtime.get_beijing_time, registry.get_beijing_time)


if __name__ == "__main__":
    unittest.main()
