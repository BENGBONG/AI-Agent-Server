"""Single catalog for project-owned tools, Builder labels and app entry points."""

from dataclasses import dataclass
from functools import wraps
import inspect
from typing import Callable

from .time import get_beijing_time
from .web import deepseek_fetch, deepseek_search
from .files import list_uploaded_files, parse_uploaded_file

ENTRYPOINT_MODULE = "tool_entries"


@dataclass(frozen=True)
class ToolSpec:
    function: Callable
    label: str
    category: str
    legacy_modules: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self.function.__name__

    def reference(self, app_name: str) -> str:
        return f"{app_name}.{ENTRYPOINT_MODULE}.{self.name}"


TOOLS = (
    ToolSpec(deepseek_search, "DeepSeek 网页搜索", "DeepSeek 联网工具（本地）", ("deepseek_web_tools",)),
    ToolSpec(deepseek_fetch, "DeepSeek 网页读取", "DeepSeek 联网工具（本地）", ("deepseek_web_tools",)),
    ToolSpec(get_beijing_time, "查询北京时间", "通用工具（本地）"),
    ToolSpec(list_uploaded_files, "列出上传文件", "文件解析（本地 + DeepSeek）"),
    ToolSpec(parse_uploaded_file, "解析上传文件", "文件解析（本地 + DeepSeek）"),
)


def list_tools() -> tuple[ToolSpec, ...]:
    names = [tool.name for tool in TOOLS]
    if len(set(names)) != len(names) or any(not name.isidentifier() or name.startswith("_") for name in names):
        raise ValueError("Tool names must be unique public Python identifiers")
    for tool in TOOLS:
        if any(not module.isidentifier() or module.startswith("_") for module in tool.legacy_modules):
            raise ValueError("Legacy tool modules must be public Python identifiers")
    return TOOLS


def entrypoint_groups() -> dict[str, tuple[str, ...]]:
    tools = list_tools()
    groups = {ENTRYPOINT_MODULE: tuple(tool.name for tool in tools)}
    for tool in tools:
        for module in tool.legacy_modules:
            groups[module] = (*groups.get(module, ()), tool.name)
    return groups


def _entrypoint(function: Callable, module_name: str) -> Callable:
    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def entry(*args, **kwargs):
            return await function(*args, **kwargs)
    else:
        @wraps(function)
        def entry(*args, **kwargs):
            return function(*args, **kwargs)
    # Keep inspect.signature/docstrings/types, but expose the app-local identity.
    entry.__module__ = module_name
    entry.__qualname__ = function.__name__
    return entry


def bind_tools(namespace: dict, names: list[str]) -> None:
    catalog = {tool.name: tool for tool in list_tools()}
    for name in names:
        namespace[name] = _entrypoint(catalog[name].function, namespace["__name__"])
