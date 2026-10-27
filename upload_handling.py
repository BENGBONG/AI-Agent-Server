"""Keep unsupported raw files away from the model when file tools are enabled."""

from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from google.genai import types


def _uses_file_tools(agent) -> bool:
    if agent is None:
        return False
    for tool in getattr(agent, "tools", []):
        name = getattr(tool, "name", getattr(tool, "__name__", ""))
        if name in {"list_uploaded_files", "parse_uploaded_file"}:
            return True
    return any(_uses_file_tools(child) for child in getattr(agent, "sub_agents", []))


class UploadedFilesPlugin(SaveFilesAsArtifactsPlugin):
    def __init__(self, name: str = "uploaded_files"):
        super().__init__(name=name, attach_file_reference=False)

    async def on_user_message_callback(self, *, invocation_context, user_message):
        if not _uses_file_tools(invocation_context.agent):
            return None
        result = await super().on_user_message_callback(invocation_context=invocation_context, user_message=user_message)
        content = result or user_message
        # The stock plugin retains raw bytes after storage errors. Avoid sending
        # those unsupported files to the model as a fallback.
        if any(part.inline_data is not None for part in content.parts or []):
            return types.Content(role=content.role, parts=[
                types.Part(text="[文件保存失败，暂时无法解析，请重新上传。]") if part.inline_data is not None else part
                for part in content.parts
            ])
        return result
