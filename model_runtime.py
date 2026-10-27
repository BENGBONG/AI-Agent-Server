"""Shared DeepSeek configuration for the local ADK applications."""

import json
import os
import re
from pathlib import Path

from dotenv import dotenv_values
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.models.registry import LLMRegistry
from google.genai import types
from shared_tools.time import get_beijing_time

PROJECT_DIR = Path(__file__).resolve().parent
ENV_FILE = PROJECT_DIR / ".env"


def require_deepseek_key(callback_context, llm_request):
    """Load the local key before each request; never send an empty credential."""
    local_key = dotenv_values(ENV_FILE).get("DEEPSEEK_API_KEY", "")
    key = (local_key or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
    if not key:
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=(
                    "模型配置已就绪，还没有填写 DeepSeek API Key。"
                    "请在 google-adk-demo/.env 的 DEEPSEEK_API_KEY= 后填写并保存，"
                    "然后重新发送消息。所有 DeepSeek Agent 共用这份 Key。"
                ))],
            )
        )
    # LiteLLM's DeepSeek provider reads this standard environment variable.
    os.environ["DEEPSEEK_API_KEY"] = key
    return None


def load_model_config() -> dict:
    config = json.loads((PROJECT_DIR / "model_profiles.json").read_text())
    if config["default_profile"] not in config["profiles"]:
        raise ValueError("default_profile must refer to a configured model profile")
    return config


def configured_model_ids() -> list[str]:
    return list(dict.fromkeys(
        profile["model"] for profile in load_model_config()["profiles"].values()
    ))


def default_model_id() -> str:
    config = load_model_config()
    return config["profiles"][config["default_profile"]]["model"]


class ConfiguredDeepSeek(LiteLlm):
    """Resolve editable YAML model names to the shared local DeepSeek connection."""

    def __init__(self, model: str, **kwargs):
        config = load_model_config()
        model_id = model.removeprefix("deepseek/")
        profile = next(
            (p for p in config["profiles"].values() if p["model"] == model_id),
            None,
        )
        if profile is None:
            raise ValueError(f"DeepSeek model is not configured: {model_id}")
        thinking = profile.get("thinking", "disabled")
        if thinking not in {"enabled", "disabled"}:
            raise ValueError(f"Invalid thinking mode for {model_id}")
        super().__init__(
            model=f"deepseek/{model_id}",
            api_base=config["api_base"],
            extra_body={"thinking": {"type": thinking}},
            **kwargs,
        )

    @classmethod
    def supported_models(cls) -> list[str]:
        return [rf"(?:deepseek/)?{re.escape(model)}" for model in configured_model_ids()]

    async def generate_content_async(self, llm_request, stream: bool = False):
        missing_key = require_deepseek_key(None, llm_request)
        if missing_key is not None:
            yield missing_key
            return
        # ADK replaces the model's extra_body with per-Agent HTTP options.
        # Merge our defaults first so unrelated provider options cannot silently
        # re-enable thinking by removing the explicit disabled default.
        if llm_request.config.http_options and llm_request.config.http_options.extra_body is not None:
            llm_request = llm_request.model_copy(deep=True)
            http = llm_request.config.http_options
            http.extra_body = {**self._additional_args["extra_body"], **http.extra_body}
        async for response in super().generate_content_async(llm_request, stream=stream):
            yield response


def configure_default_models() -> None:
    LLMRegistry.register(ConfiguredDeepSeek)
    Agent.set_default_model(default_model_id())


def create_agent(profile_name: str) -> Agent:
    profile = load_model_config()["profiles"][profile_name]
    return Agent(
        name=f"deepseek_{profile_name}_assistant",
        model=ConfiguredDeepSeek(model=profile["model"]),
        description=profile["description"],
        instruction=(
            "使用简体中文回答。用户询问当前北京时间时，调用 get_beijing_time 工具，"
            "根据工具结果回答。"
        ),
        tools=[get_beijing_time],
    )
