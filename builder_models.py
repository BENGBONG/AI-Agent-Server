"""Apply local model and web-tool catalogs to ADK 2.12.0's Visual Builder."""

import json
from pathlib import Path

from google.adk.cli import fast_api

from model_runtime import configured_model_ids, default_model_id, load_model_config
from shared_tools.registry import ENTRYPOINT_MODULE, list_tools

SELECTOR_TOKEN = 'models=["gemini-2.5-flash","gemini-2.5-pro"]'
DEFAULT_TOKEN = 'model:"gemini-2.5-flash"'
TOOL_CATALOG_TOKEN = 'selectedBuiltInTool="google_search";toolCategories=['
TOOL_RESULT_TOKEN = 'addTool(){let t={toolType:"Built-in tool",name:this.selectedBuiltInTool'
TOOL_LABEL_TOKEN = 'ee(i.getToolIcon(e)),b(2),ee(e)}}function znt'


def configure_thinking_editor(source: str) -> str:
    """Preserve native per-node generation config and expose the active form.

    These are response-only adaptations of the existing model picker. The
    control itself lives in source-maintained JS/CSS; installed ADK is untouched.
    Fail closed on version drift instead of showing a switch that cannot save.
    """
    replacements = {
        'this.agentConfig=t,this.currentSelectedAgent=t,':
            'this.agentConfig=t,this.currentSelectedAgent=t,window.__adkModelEditor=this,window.dispatchEvent(new Event("adk:model-editor")),',
        'Gn(o.agentConfig.model,r)||(o.agentConfig.model=r),L(r)':
            'Gn(o.agentConfig.model,r)||(o.agentConfig.model=r),window.dispatchEvent(new Event("adk:model-editor")),L(r)',
        'description:r.description||""},r.max_iterations':
            'description:r.description||"",generate_content_config:r.generate_content_config},r.max_iterations',
        'description:o.description||""},o.max_iterations':
            'description:o.description||"",generate_content_config:o.generate_content_config},o.max_iterations',
        'tools:n.buildToolsConfig(t.tools,r)};if(t.isRoot':
            'tools:n.buildToolsConfig(t.tools,r)};if(t.agent_class==="LlmAgent"&&t.generate_content_config)c.generate_content_config=t.generate_content_config;if(t.isRoot',
    }
    for token, replacement in replacements.items():
        if source.count(token) != 1:
            raise RuntimeError("ADK model form changed; check thinking settings integration")
        source = source.replace(token, replacement)
    defaults = {
        profile["model"]: profile.get("thinking", "disabled")
        for profile in load_model_config()["profiles"].values()
    }
    return "window.__adkThinkingDefaults=" + json.dumps(defaults) + ";\n" + source


def local_picker_config() -> tuple[str, dict[str, str], list[str]]:
    """Build categories, labels and recognized references from the registry."""
    categories = {}
    labels = {}
    for tool in list_tools():
        suffix = f"{ENTRYPOINT_MODULE}.{tool.name}"
        categories.setdefault(tool.category, []).append(suffix)
        labels[f".{suffix}"] = tool.label
        for module in tool.legacy_modules:
            labels[f".{module}.{tool.name}"] = tool.label
    prefix = 'new URLSearchParams(window.location.search).get("app")'
    catalog = ",".join(
        '{name:' + json.dumps(category, ensure_ascii=False) + ',tools:'
        + json.dumps(names) + '.map(n=>' + prefix + '+"."+n)}'
        for category, names in categories.items()
    )
    return catalog, labels, list(labels)


def configured_browser_bundle() -> tuple[str, str]:
    browser_dir = Path(fast_api.__file__).resolve().parent / "browser"
    for path in browser_dir.glob("main-*.js"):
        source = path.read_text()
        if SELECTOR_TOKEN not in source:
            continue
        models = json.dumps(configured_model_ids(), ensure_ascii=False)
        default = json.dumps(default_model_id(), ensure_ascii=False)
        source = source.replace(SELECTOR_TOKEN, f"models={models}")
        source = source.replace(DEFAULT_TOKEN, f"model:{default}")
        source = source.replace("Ask Gemini to build your agent", "Ask DeepSeek to build your agent")
        # Add local functions to the native picker. They remain ordinary Python
        # function references in YAML, not ADK built-ins or arguments/factories.
        for token in (TOOL_CATALOG_TOKEN, TOOL_RESULT_TOKEN, TOOL_LABEL_TOKEN):
            if source.count(token) != 1:
                raise RuntimeError("ADK Builder tool picker changed; check the local tool integration")
        catalog, labels, suffixes = local_picker_config()
        first_tool = next(iter(list_tools()), None)
        if first_tool is None:
            raise RuntimeError("The local tool registry must not be empty")
        app_prefix = 'new URLSearchParams(window.location.search).get("app")'
        source = source.replace(
            TOOL_CATALOG_TOKEN,
            'selectedBuiltInTool=' + app_prefix + '+'
            + json.dumps(f".{ENTRYPOINT_MODULE}.{first_tool.name}")
            + ';toolCategories=[' + catalog + ',',
        )
        source = source.replace(
            TOOL_RESULT_TOKEN,
            'addTool(){let t={toolType:' + json.dumps(suffixes)
            + '.some(n=>this.selectedBuiltInTool.endsWith(n))?"Function tool":"Built-in tool",name:this.selectedBuiltInTool',
        )
        source = source.replace(
            TOOL_LABEL_TOKEN,
            'ee(i.getToolIcon(e)),b(2),ee(('
            + json.dumps(labels, ensure_ascii=False)
            + ')[e.slice(e.indexOf("."))]||e)}}function znt',
        )
        return f"/dev-ui/{path.name}", configure_thinking_editor(source)
    raise RuntimeError("ADK Builder UI layout changed; check the model selector integration")
