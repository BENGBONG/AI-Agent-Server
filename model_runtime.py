"""Model-engine routing with legacy DeepSeek references and isolated credentials."""

import json
import re
from pathlib import Path

from google.adk import Agent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.models.registry import LLMRegistry
from google.genai import types
from shared_tools.time import get_beijing_time
from pydantic import PrivateAttr
from model_engines import (ConfigError, PROVIDERS, current_store, use_engine_store,
                           connection_args, safe_failure)

PROJECT_DIR = Path(__file__).resolve().parent


def require_deepseek_key(callback_context, llm_request):
    """Legacy guard; credentials are passed per request, never via shared env."""
    if not current_store().key("deepseek"):
        return model_error("请在模型引擎页面为 DeepSeek 填写 API Key，然后重新发送消息。")
    return None


def model_error(text):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def load_model_config() -> dict:
    config = json.loads((PROJECT_DIR / "model_profiles.json").read_text())
    if config["default_profile"] not in config["profiles"]:
        raise ValueError("default_profile must refer to a configured model profile")
    return config


def configured_model_ids(store=None) -> list[str]:
    return [item["reference"] for item in (store or current_store()).catalog()]


def default_model_id(store=None) -> str:
    return (store or current_store()).read()["default_model"]


class ConfiguredEngine(LiteLlm):
    """Resolve a stable Agent reference with invocation-local credentials."""

    _engine_store: object = PrivateAttr()
    _engine_reference: str = PrivateAttr()
    _engine_kwargs: dict = PrivateAttr(default_factory=dict)

    def __init__(self, model: str, **kwargs):
        store = kwargs.pop("engine_store", None) or current_store()
        engine, model_id, settings = store.resolve(model)
        defaults = self.thinking_defaults(store, engine, model_id)
        args = connection_args(engine, model_id, settings, "")
        args.pop("api_key")
        super().__init__(**args, extra_body=defaults, **kwargs)
        self._engine_store = store
        self._engine_reference = model
        self._engine_kwargs = dict(kwargs)

    @staticmethod
    def thinking_defaults(store, engine, model):
        if engine != "deepseek":
            return {}
        profile = next((p for p in store.legacy()["profiles"].values() if p["model"] == model), {})
        mode = profile.get("thinking", "disabled")
        if mode not in {"enabled", "disabled"}:
            raise ValueError("Invalid DeepSeek thinking mode")
        return {"thinking": {"type": mode}}

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"engine/(?:deepseek|kimi|openai|claude|openrouter)/.+"]

    async def generate_content_async(self, llm_request, stream: bool = False):
        store = self._engine_store
        try:
            engine, model, settings, key = store.connection(self._engine_reference)
            if engine == "deepseek":
                with use_engine_store(store):
                    missing = require_deepseek_key(None, llm_request)
                if missing is not None:
                    yield missing
                    return
            elif not key:
                yield model_error("请在模型引擎页面为 " + PROVIDERS[engine]["name"] + " 填写 API Key，然后重新发送消息。")
                return
            request = llm_request.model_copy(deep=True)
            args = connection_args(engine, model, settings, key)
            # ADK may populate this from an outer/default wrapper. LiteLlm
            # prefers request.model to its own model, so normalize it here.
            request.model = args["model"]
            defaults = self.thinking_defaults(store, engine, model)
            if request.config.http_options is None:
                request.config.http_options = types.HttpOptions()
            body = dict(request.config.http_options.extra_body or {})
            if engine != "deepseek":
                # A DeepSeek switch saved in an Agent must not become an
                # invalid Anthropic/OpenAI/OpenRouter provider parameter.
                body.pop("thinking", None)
            request.config.http_options.extra_body = {**defaults, **body}
            runtime = LiteLlm(**args,
                             extra_body=defaults, **self._engine_kwargs)
            async for response in runtime.generate_content_async(request, stream=stream):
                yield response
        except ConfigError as error:
            yield model_error(str(error))
        except Exception as error:
            yield model_error(safe_failure(error))


class ConfiguredDeepSeek(ConfiguredEngine):
    """Compatibility for existing bare DeepSeek names in saved YAML."""

    @classmethod
    def supported_models(cls) -> list[str]:
        return [rf"(?:deepseek/)?{re.escape(profile['model'])}"
                for profile in load_model_config()["profiles"].values()]


class DynamicDefaultModel(BaseLlm):
    """The Builder assistant follows new defaults even when its Runner is cached."""

    _engine_store: object = PrivateAttr()

    def __init__(self, *, engine_store, **kwargs):
        super().__init__(**kwargs)
        self._engine_store = engine_store

    @property
    def capabilities(self):
        return ConfiguredEngine(model=default_model_id(self._engine_store), engine_store=self._engine_store).capabilities

    async def generate_content_async(self, llm_request, stream=False):
        runtime = ConfiguredEngine(model=default_model_id(self._engine_store), engine_store=self._engine_store)
        async for response in runtime.generate_content_async(llm_request, stream=stream):
            yield response


def configure_default_models(store=None) -> None:
    LLMRegistry.register(ConfiguredEngine)
    LLMRegistry.register(ConfiguredDeepSeek)
    Agent.set_default_model(default_model_id(store))


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
