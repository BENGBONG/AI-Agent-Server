"""Start ADK Web with discovery of unsaved Visual Builder drafts.

ADK 2.12.0 creates drafts in <app>/tmp/<app>/root_agent.yaml, but its
default loader skips tmp directories. This loader keeps those drafts visible
without saving, moving, or changing the user's agent configuration.
"""

from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode

from fastapi.responses import Response
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.utils._nested_agent_loader import NestedAgentLoader
import uvicorn

from builder_models import configured_browser_bundle
from builder_tools import install_registered_tools
from model_runtime import configure_default_models, configured_model_ids, default_model_id
from capabilities.api import install_management
from capabilities.store import CapabilityStore
from capabilities.runtime import BoundCapabilities
from capabilities.web_integration import install_adk_integration

class DraftAwareAgentLoader(NestedAgentLoader):
    def __init__(self, agents_dir, capability_store=None):
        super().__init__(agents_dir)
        self.capability_store = capability_store or CapabilityStore(agents_dir)

    def _perform_load(self, agent_path: str):
        if agent_path == "__adk_agent_builder_assistant":
            self._validate_agent_name(agent_path)
            from google.adk.cli.built_in_agents.adk_agent_builder_assistant import AgentBuilderAssistant

            assistant = AgentBuilderAssistant.create_agent(
                model=default_model_id(), working_directory=self.agents_dir,
            )
            original_instruction = assistant.instruction
            model_ids = configured_model_ids()

            def instruction(context):
                text = original_instruction(context)
                for old, model_id in zip(
                    ["gemini-2.5-flash", "gemini-2.5-pro"], model_ids,
                ):
                    text = text.replace(old, model_id)
                return text + (
                    "\nUse only these locally configured model IDs: "
                    + ", ".join(model_ids)
                    + ". Default: " + default_model_id() + "."
                )

            assistant.instruction = instruction
            return assistant
        loaded = super()._perform_load(agent_path)
        agent = getattr(loaded, "root_agent", loaded)
        def attach(node):
            if hasattr(node, "tools"):
                node.tools = [tool for tool in node.tools if not isinstance(tool, BoundCapabilities)] + [BoundCapabilities(self.capability_store, agent_path)]
            for child in getattr(node, "sub_agents", []):
                attach(child)
        attach(agent)
        return loaded

    def list_agents(self) -> list[str]:
        names = set(super().list_agents())
        if self.is_single_agent:
            return sorted(names)
        for app_dir in Path(self.agents_dir).iterdir():
            name = app_dir.name
            if (
                name.isidentifier()
                and not name.startswith("__")
                and app_dir.is_dir()
                and (app_dir / "tmp" / name / "root_agent.yaml").is_file()
            ):
                names.add(name)
        return sorted(names)

    def _load_from_yaml_config(self, agent_name: str, agents_dir: str):
        agent = super()._load_from_yaml_config(agent_name, agents_dir)
        if agent is not None or not agent_name.isidentifier():
            return agent
        if agent_name.startswith("__"):
            return None
        tmp_dir = Path(agents_dir) / agent_name / "tmp"
        if (tmp_dir / agent_name / "root_agent.yaml").is_file():
            # Reuse ADK's config loader, including its YAML validation rules.
            return super()._load_from_yaml_config(agent_name, str(tmp_dir))
        return None


def create_app(agents_dir: Path, *, reload_agents: bool = True):
    root = str(agents_dir.resolve())
    install_registered_tools(Path(root))
    configure_default_models()
    browser_path, browser_source = configured_browser_bundle()
    capability_store = CapabilityStore(root)
    loader = DraftAwareAgentLoader(root, capability_store)
    app = get_fast_api_app(
        agents_dir=root,
        agent_loader=loader,
        web=True,
        bind_host="127.0.0.1",
        port=8000,
        reload_agents=reload_agents,
        default_llm_model=default_model_id(),
        extra_plugins=["upload_handling.UploadedFilesPlugin", "capabilities.runtime.CapabilityCleanupPlugin"],
    )
    install_management(app, capability_store, loader)
    install_adk_integration(app)

    @app.middleware("http")
    async def read_builder_draft_when_unsaved(request, call_next):
        if request.method == "GET" and request.url.path == browser_path:
            return Response(
                browser_source,
                media_type="application/javascript",
                headers={"Cache-Control": "no-store"},
            )
        # The UI enables Edit only when GET /builder returns YAML. ADK's
        # endpoint normally reads only saved files unless tmp=true is explicit.
        # Reuse that same endpoint (and its guards) for unsaved drafts as well.
        match = re.fullmatch(r"/dev/apps/([A-Za-z][A-Za-z0-9_]*)/builder", request.url.path)
        if request.method == "GET" and match:
            name = match.group(1)
            pairs = parse_qsl(request.scope.get("query_string", b"").decode())
            query = dict(pairs)
            relative = Path(query.get("file_path", "root_agent.yaml"))
            if (
                query.get("tmp", "false").lower() not in {"true", "1"}
                and not relative.is_absolute()
                and ".." not in relative.parts
                and relative.suffix.lower() in {".yaml", ".yml"}
            ):
                app_dir = Path(root) / name
                draft = app_dir / "tmp" / name / relative
                if not (app_dir / relative).is_file() and draft.is_file():
                    updated = [(key, value) for key, value in pairs if key != "tmp"]
                    updated.append(("tmp", "true"))
                    request.scope["query_string"] = urlencode(updated).encode()
        response = await call_next(request)
        # Install only after ADK's original local-client and upload checks ran.
        saved = re.fullmatch(r"/dev/apps/([A-Za-z_][A-Za-z0-9_]*)/builder/save", request.url.path)
        if request.method == "POST" and saved and response.status_code == 200:
            install_registered_tools(Path(root), saved.group(1))
        return response

    return app


if __name__ == "__main__":
    app = create_app(Path(__file__).resolve().parent)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
