"""Local model connections. Public settings and credentials stay separate."""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import urlsplit

from dotenv import dotenv_values, set_key

from capabilities.store import ConfigError

PROJECT_DIR = Path(__file__).resolve().parent
PROVIDERS = {
    "deepseek": {"name": "DeepSeek", "api_base": "https://api.deepseek.com", "env": "DEEPSEEK_API_KEY", "provider": "deepseek", "models": ["deepseek-flash", "deepseek-v4-pro"]},
    "kimi": {"name": "Kimi", "api_base": "https://api.moonshot.cn/v1", "env": "MOONSHOT_API_KEY", "provider": "openai", "models": ["kimi-k3.1-pro"]},
    "openai": {"name": "OpenAI", "api_base": "https://api.openai.com/v1", "env": "OPENAI_API_KEY", "provider": "openai", "models": ["gpt-4.1-mini"]},
    "claude": {"name": "Claude", "api_base": "https://api.anthropic.com", "env": "ANTHROPIC_API_KEY", "provider": "anthropic", "models": ["claude-sonnet-4-6"]},
    "openrouter": {"name": "OpenRouter", "api_base": "https://openrouter.ai/api/v1", "env": "OPENROUTER_API_KEY", "provider": "openrouter", "models": ["openai/gpt-4.1-mini"]},
}
_ACTIVE_STORE = ContextVar("model_engine_store", default=None)
_LOCK = threading.RLock()


def engine_reference(engine, model):
    return f"engine/{engine}/{model}"


def current_store():
    return _ACTIVE_STORE.get() or EngineStore(PROJECT_DIR)


@contextmanager
def use_engine_store(store):
    token = _ACTIVE_STORE.set(store)
    try:
        yield
    finally:
        _ACTIVE_STORE.reset(token)


def validate_model(model):
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9~][A-Za-z0-9._:/@+~-]{0,199}", model):
        raise ConfigError("模型 ID 无效，请使用供应商提供的完整模型 ID。")
    return model


def validate_base(value):
    if not isinstance(value, str) or len(value) > 500:
        raise ConfigError("API Base URL 无效。")
    value = value.strip().rstrip("/")
    try:
        url = urlsplit(value)
        valid_port = url.port is None or 0 < url.port < 65536
    except ValueError:
        raise ConfigError("API Base URL 无效。") from None
    local = url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}
    if (not (url.scheme == "https" or local) or not url.hostname or not valid_port
            or url.username or url.password or url.query or url.fragment
            or re.search(r"[\s\\\x00-\x1f]", value)):
        raise ConfigError("请填写 HTTPS API 根地址；本机测试服务也可使用 HTTP。地址不能包含凭据或查询参数。")
    if url.path.endswith(("/chat/completions", "/messages", "/models", "/responses")):
        raise ConfigError("请填写 API Base URL，不要包含 chat/completions、messages 或 models 路径。")
    return value


def safe_failure(error):
    """Never expose upstream response bodies, URLs or credential-bearing errors."""
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    if status in {401, 403}:
        return "认证失败或无模型权限，请检查该引擎的 API Key 和账户权限。"
    if status == 402:
        return "账户余额不足，请在供应商控制台检查额度。"
    if status == 429:
        return "请求受限，请检查额度或稍后重试。"
    if status in {400, 404, 422}:
        return "模型或接口参数不可用，请核对模型 ID、API 地址及模型支持的调用方式。"
    if "timeout" in type(error).__name__.lower():
        return "连接超时，请检查网络和 API 地址后重试。"
    return "模型连接失败，请检查 API 地址、网络和供应商服务状态后重试。"


class EngineStore:
    def __init__(self, root, legacy_path=None):
        self.root = Path(root).resolve()
        self.path = self.root / "model_engines.json"
        self.env_path = self.root / ".env"
        self.legacy_path = Path(legacy_path or PROJECT_DIR / "model_profiles.json")

    def legacy(self):
        return json.loads(self.legacy_path.read_text())

    def read(self):
        if self.path.exists():
            try:
                value = json.loads(self.path.read_text())
                if not isinstance(value, dict) or value.get("version") != 1 or set(value["engines"]) != set(PROVIDERS):
                    raise ValueError()
                for engine, settings in value["engines"].items():
                    self.settings(engine, settings)
                self.resolve(value["default_model"], config=value)
                return value
            except (ValueError, KeyError, TypeError, ConfigError):
                raise ConfigError("模型引擎配置无法读取，请检查本机 model_engines.json。", 500) from None
        old = self.legacy()
        engines = {key: {"api_base": item["api_base"], "models": list(item["models"])} for key, item in PROVIDERS.items()}
        engines["deepseek"] = {"api_base": old["api_base"], "models": list(dict.fromkeys(p["model"] for p in old["profiles"].values()))}
        return {"version": 1, "default_model": old["profiles"][old["default_profile"]]["model"], "engines": engines}

    def key(self, engine):
        name = self.provider(engine)["env"]
        values = dotenv_values(self.env_path) if self.env_path.exists() else {}
        return (values.get(name) or os.environ.get(name, "")).strip()

    @staticmethod
    def provider(engine):
        if engine not in PROVIDERS:
            raise ConfigError("未知模型引擎。", 404)
        return PROVIDERS[engine]

    def settings(self, engine, value):
        self.provider(engine)
        if not isinstance(value, dict) or set(value) - {"api_base", "models"}:
            raise ConfigError("引擎配置只接受 api_base 和 models。")
        models = value.get("models")
        if not isinstance(models, list) or not 1 <= len(models) <= 100:
            raise ConfigError("请配置 1–100 个对话模型 ID。")
        models = list(dict.fromkeys(validate_model(model) for model in models))
        return {"api_base": validate_base(value.get("api_base")), "models": models}

    def resolve(self, reference, config=None):
        if not isinstance(reference, str):
            raise ConfigError("模型引用无效，请重新选择模型。")
        config = config or self.read()
        legacy = self.legacy()
        candidate = reference.removeprefix("deepseek/")
        old_models = {item["model"] for item in legacy["profiles"].values()}
        if candidate in old_models:
            return "deepseek", candidate, config["engines"]["deepseek"]
        parts = reference.split("/", 2)
        if len(parts) != 3 or parts[0] != "engine" or parts[1] not in PROVIDERS:
            raise ConfigError("模型引用无效，请在 Agent 编辑页重新选择引擎和模型。")
        engine, model = parts[1], validate_model(parts[2])
        # Saved Agents remain usable if their model was removed from the picker.
        return engine, model, config["engines"][engine]

    def connection(self, reference):
        with _LOCK:
            engine, model, settings = self.resolve(reference)
            return engine, model, settings, self.key(engine)

    def catalog(self, config=None):
        config = config or self.read()
        legacy = self.legacy()
        aliases = {item["model"] for item in legacy["profiles"].values()}
        items = []
        for engine, settings in config["engines"].items():
            for model in settings["models"]:
                reference = model if engine == "deepseek" and model in aliases else engine_reference(engine, model)
                items.append({"engine": engine, "model": model, "reference": reference})
        return items

    def _revision(self, config):
        # Include key fingerprints to detect concurrent credential rotation.
        value = {"config": config, "keys": {engine: hashlib.sha256(self.key(engine).encode()).hexdigest() for engine in PROVIDERS}}
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def snapshot(self):
        with _LOCK:
            config = self.read()
            return {"revision": self._revision(config), "default_model": config["default_model"], "catalog": self.catalog(config),
                    "engines": {engine: {**deepcopy(settings), "name": item["name"], "key_env": item["env"], "has_key": bool(self.key(engine))}
                                for engine, settings in config["engines"].items() for item in [PROVIDERS[engine]]}}

    def _check_revision(self, expected):
        if expected != self.snapshot()["revision"]:
            raise ConfigError("模型配置已变化，请重新读取后再保存。", 409)

    def draft(self, engine, settings, api_key=None, clear_key=False):
        settings = self.settings(engine, settings)
        if api_key is not None and (not isinstance(api_key, str) or len(api_key) > 4096 or re.search(r"[\s\x00-\x1f]", api_key)):
            raise ConfigError("API Key 无效，请检查是否包含空格或换行。")
        if not isinstance(clear_key, bool) or (clear_key and api_key):
            raise ConfigError("清除与填写 API Key 不能同时进行。")
        key = api_key or ("" if clear_key else self.key(engine))
        old_host = urlsplit(self.read()["engines"][engine]["api_base"]).netloc
        if old_host != urlsplit(settings["api_base"]).netloc and key and not api_key:
            raise ConfigError("API 主机已修改，请重新输入对应 Key 后测试或保存。")
        return settings, key

    def _write(self, path, contents):
        self.root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".model-engine-", dir=self.root)
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(contents)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(name, 0o600)
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)

    def save(self, engine, settings, expected, api_key=None, clear_key=False):
        with _LOCK:
            self._check_revision(expected)
            settings, _ = self.draft(engine, settings, api_key, clear_key)
            config = self.read()
            config["engines"][engine] = settings
            original_env = self.env_path.read_text() if self.env_path.exists() else None
            key_changed = False
            if api_key or clear_key:
                self.root.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(prefix=".model-engine-", dir=self.root)
                os.close(fd)
                try:
                    Path(temporary).write_text(original_env or "")
                    set_key(temporary, self.provider(engine)["env"], api_key or "", quote_mode="always")
                    self._write(self.env_path, Path(temporary).read_text())
                    key_changed = True
                finally:
                    Path(temporary).unlink(missing_ok=True)
            try:
                self._write(self.path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
            except OSError:
                if key_changed:
                    if original_env is None:
                        self.env_path.unlink(missing_ok=True)
                    else:
                        self._write(self.env_path, original_env)
                raise ConfigError("模型配置保存失败，原 Key 已恢复，请检查本机目录是否可写。", 500) from None
            return self.snapshot()

    def set_default(self, reference, expected):
        with _LOCK:
            self._check_revision(expected)
            config = self.read()
            if reference not in {item["reference"] for item in self.catalog(config)}:
                raise ConfigError("请先保存这个模型的引擎配置。")
            engine, _, _ = self.resolve(reference, config)
            if not self.key(engine):
                raise ConfigError("请先为默认引擎填写 API Key。")
            config["default_model"] = reference
            self._write(self.path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
            return self.snapshot()


def connection_args(engine, model, settings, key):
    provider = PROVIDERS[engine]["provider"]
    base = settings["api_base"]
    # LiteLLM's Anthropic adapter appends /v1/messages itself. Accept the
    # common /v1 base spelling without producing /v1/v1/messages.
    if engine == "claude" and base.endswith("/v1"):
        base = base[:-3]
    return {"model": f"{provider}/{model}", "api_base": base, "api_key": key}
