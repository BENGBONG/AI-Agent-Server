"""Compatibility exports. Maintain implementations in shared_tools/web.py."""

from shared_tools.web import deepseek_fetch, deepseek_search

# Preserve the original public import paths for existing Python integrations.
TOOL_NAMES = ("web_tools.deepseek_search", "web_tools.deepseek_fetch")
__all__ = ["deepseek_search", "deepseek_fetch", "TOOL_NAMES"]
