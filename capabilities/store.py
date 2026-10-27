"""Atomic, revision-checked settings; credentials are environment references."""

from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import threading
from urllib.parse import parse_qsl, urlsplit
import zipfile

from google.adk.skills import load_skill_from_dir
import yaml

SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
ENV = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".yaml", ".yml"}
ROOT_FILES = {"SKILL.md", "README.md", "LICENSE", "LICENSE.txt", "NOTICE", "requirements.txt", "pyproject.toml", "package.json"}
MAX_BYTES = 10 * 1024 * 1024


class ConfigError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def slug(value):
    if not isinstance(value, str) or len(value) > 48 or not SLUG.fullmatch(value):
        raise ConfigError("ID 需以小写字母开头，仅含小写字母、数字和单个连字符，最多 48 字符。")
    return value


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def server_config(data):
    allowed = {"id", "name", "transport", "url", "token_env", "auth_header", "auth_prefix", "enabled"}
    if set(data) - allowed:
        raise ConfigError("存在不支持的服务配置字段。")
    sid = slug(data.get("id"))
    url = data.get("url", "")
    if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() for c in url):
        raise ConfigError("请填写有效的 MCP HTTP/HTTPS 地址。")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ConfigError("MCP 地址或端口无效。") from None
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ConfigError("仅支持无登录凭据和片段的 HTTP/HTTPS 地址。")
    if any(k.lower() in {"key", "token", "api_key", "access_token", "password", "signature", "secret"} for k, _ in parse_qsl(parts.query)):
        raise ConfigError("不要在 URL 中放凭据，请使用环境变量鉴权。")
    transport = data.get("transport", "streamable_http")
    if transport not in {"streamable_http", "sse"}:
        raise ConfigError("首版支持 Streamable HTTP 或 SSE，不执行本机启动命令。")
    token_env = data.get("token_env", "")
    header = data.get("auth_header", "Authorization")
    prefix = data.get("auth_prefix", "Bearer ")
    if not isinstance(token_env, str) or len(token_env) > 128 or (token_env and not ENV.fullmatch(token_env)):
        raise ConfigError("凭据填写环境变量名，例如 LOAN_MCP_TOKEN，不填写真实 Token。")
    if not isinstance(header, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,63}", header) or header.lower() in {"host", "content-length", "connection"}:
        raise ConfigError("鉴权 Header 名无效。")
    if not isinstance(prefix, str) or len(prefix) > 32 or "\r" in prefix or "\n" in prefix:
        raise ConfigError("鉴权前缀无效。")
    name = data.get("name", sid)
    if not isinstance(name, str) or not name.strip() or len(name) > 100 or type(data.get("enabled", True)) is not bool:
        raise ConfigError("请填写服务名称，并使用有效的启用状态。")
    return dict(id=sid, name=name.strip(), transport=transport, url=url, token_env=token_env,
                auth_header=header, auth_prefix=prefix, enabled=data.get("enabled", True))


class CapabilityStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / "capability_config.json"
        self.skills_dir = self.root / "capabilities" / "skill_library"
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            try:
                data = json.loads(self.path.read_text()) if self.path.exists() else {"version": 1, "mcp_servers": {}, "skills": {}, "agents": {}}
                if data.get("version") != 1 or any(not isinstance(data.get(k), dict) for k in ("mcp_servers", "skills", "agents")):
                    raise ValueError()
            except (ValueError, OSError):
                raise ConfigError("能力配置文件损坏或不可读，请先恢复配置备份。", 500) from None
            return data

    @staticmethod
    def revision(data):
        return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def snapshot(self):
        data = self.read()
        return {**data, "revision": self.revision(data)}

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, prefix=".capability-", delete=False) as stream:
            temp = Path(stream.name)
            try:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
            except BaseException:
                temp.unlink(missing_ok=True)
                raise
        try:
            temp.replace(self.path)
        finally:
            temp.unlink(missing_ok=True)

    def mutate(self, revision, operation):
        with self.lock:
            data = self.read()
            if revision != self.revision(data):
                raise ConfigError("配置已被其他操作更新，请刷新管理页后重试。", 409)
            operation(data)
            self._save(data)
            return self.snapshot()

    def save_server(self, payload, revision):
        clean = server_config(payload)
        def change(data):
            old = data["mcp_servers"].get(clean["id"], {})
            same_connection = all(old.get(k) == clean[k] for k in ("transport", "url", "token_env", "auth_header", "auth_prefix"))
            data["mcp_servers"][clean["id"]] = {**clean, "tools": old.get("tools", []) if same_connection else [], "tested_at": old.get("tested_at") if same_connection else None}
        return self.mutate(revision, change)

    def discovered(self, sid, tools, revision):
        def change(data):
            server = data["mcp_servers"].get(sid)
            if not server:
                raise ConfigError("服务不存在。", 404)
            server.update(tools=tools, tested_at=now())
        return self.mutate(revision, change)

    def delete(self, kind, identifier, revision):
        slug(identifier)
        key = "mcp_servers" if kind == "mcp" else "skills"
        def change(data):
            if identifier not in data[key]:
                raise ConfigError("配置不存在。", 404)
            for binding in data["agents"].values():
                used = [x["server_id"] for x in binding.get("mcp", [])] if kind == "mcp" else binding.get("skills", [])
                if identifier in used:
                    raise ConfigError("仍有 Agent 使用此项，请先取消相应绑定。", 409)
            del data[key][identifier]
        # Keep immutable skill files for recovery; remove only the registry entry.
        return self.mutate(revision, change)

    def binding(self, app_name, payload, revision):
        if set(payload) != {"mcp", "skills"} or not isinstance(payload["mcp"], list) or not isinstance(payload["skills"], list):
            raise ConfigError("Agent 绑定需包含 mcp 与 skills 数组。")
        def change(data):
            if len(payload["mcp"]) > 30 or len(payload["skills"]) > 50:
                raise ConfigError("单个 Agent 最多绑定 30 个服务和 50 个 Skill。")
            seen = set()
            for item in payload["mcp"]:
                if not isinstance(item, dict) or set(item) != {"server_id", "tools"}:
                    raise ConfigError("MCP 绑定格式无效。")
                sid = item["server_id"]
                if not isinstance(sid, str):
                    raise ConfigError("服务 ID 无效。")
                server = data["mcp_servers"].get(sid)
                names = item["tools"]
                if sid in seen or not server or not server["enabled"] or not server.get("tested_at"):
                    raise ConfigError("服务不存在、已停用、重复或尚未连接测试。")
                if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
                    raise ConfigError("每个服务需明确选择至少一个工具，不能使用空白名单。")
                available = {x["name"] for x in server["tools"]}
                if not set(names) <= available:
                    raise ConfigError("所选工具已变化，请重新测试连接并选择。")
                seen.add(sid)
            skills = payload["skills"]
            if any(not isinstance(s, str) or s not in data["skills"] or not data["skills"][s]["enabled"] for s in skills) or len(set(skills)) != len(skills):
                raise ConfigError("Skill 不存在、已停用或重复。")
            data["agents"][app_name] = payload
        return self.mutate(revision, change)

    def skill_files(self, sid, version=None):
        slug(sid)
        if version is not None and (type(version) is not int or version < 1):
            raise ConfigError("版本无效。")
        if version is None:
            metadata = self.read()["skills"].get(sid)
            if not metadata:
                raise ConfigError("Skill 不存在。", 404)
            version = metadata["version"]
        folder = self.skills_dir / sid / str(version) / sid
        if not folder.is_dir() or folder.is_symlink():
            raise ConfigError("Skill 或版本不存在。", 404)
        files = {}
        for file in folder.rglob("*"):
            if file.is_symlink():
                raise ConfigError("Skill 不允许符号链接。")
            if file.is_file():
                files[file.relative_to(folder).as_posix()] = file.read_bytes()
        return files

    @staticmethod
    def validate_skill_files(files):
        if not files or len(files) > 100 or sum(len(x) for x in files.values()) > MAX_BYTES:
            raise ConfigError("Skill 最多 100 个文件、合计 10 MiB。")
        for name, content in files.items():
            path = PurePosixPath(name)
            if not name or path.is_absolute() or ".." in path.parts or path.as_posix() != name or "\\" in name or ":" in name or len(name) > 200 or any(ord(c) < 32 for c in name):
                raise ConfigError("Skill 文件路径无效。")
            if any(parent.as_posix() in files for parent in path.parents):
                raise ConfigError("Skill 文件与目录路径冲突。")
            if name not in ROOT_FILES and (len(path.parts) < 2 or path.parts[0] not in {"references", "assets", "scripts"}):
                raise ConfigError("请使用 SKILL.md、references/、scripts/、assets/ 和常见根目录说明/依赖文件。")
            if path.parts[0] not in {"references", "assets"}:
                try:
                    content.decode("utf-8")
                except UnicodeError:
                    raise ConfigError("Skill 指令、说明与脚本需为 UTF-8 文本；二进制资源请放 references/ 或 assets/。") from None
        content = files.get("SKILL.md", b"").decode("utf-8")
        if len(content) > 100000 or not content.startswith("---\n"):
            raise ConfigError("SKILL.md 需以 YAML frontmatter 开始，且不超过 100,000 字符。")
        try:
            front, body = content[4:].split("\n---", 1)
            meta = yaml.safe_load(front)
            sid = slug(meta["name"])
            if not body.strip():
                raise ValueError()
        except (ValueError, TypeError, KeyError, yaml.YAMLError):
            raise ConfigError("SKILL.md 需包含 name、description 和非空正文。") from None
        with tempfile.TemporaryDirectory(prefix="adk-skill-validate-") as directory:
            folder = Path(directory) / sid
            for name, value in files.items():
                dest = folder / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(value)
            try:
                skill = load_skill_from_dir(folder)
            except (ValueError, OSError, TypeError):
                raise ConfigError("Skill 未通过 ADK 格式校验，请核对名称、描述和资源。") from None
        return sid, skill.description

    def save_skill(self, files, revision, expected_id=None, enabled=True):
        sid, description = self.validate_skill_files(files)
        if expected_id is not None and sid != expected_id:
            raise ConfigError("编辑时不能更改 Skill ID；请另行创建。")
        if type(enabled) is not bool:
            raise ConfigError("启用状态无效。")
        with self.lock:
            def change(data):
                old = data["skills"].get(sid, {})
                if expected_id is None and old:
                    raise ConfigError("Skill 已存在，请使用编辑入口更新。", 409)
                existing = self.skills_dir / sid
                versions = [int(p.name) for p in existing.iterdir() if p.name.isdigit()] if existing.exists() else []
                version = max([old.get("version", 0), *versions]) + 1
                destination = existing / str(version) / sid
                destination.mkdir(parents=True, exist_ok=False)
                for name, value in files.items():
                    path = destination / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(value)
                # The config update publishes an immutable version atomically.
                data["skills"][sid] = dict(id=sid, description=description, enabled=enabled, version=version, updated_at=now(), files=sorted(files), scripts=sorted(n for n in files if n.startswith("scripts/")))
            return self.mutate(revision, change)

    def skill_object(self, sid):
        with self.lock:
            files = self.skill_files(sid)
            self.validate_skill_files(files)
            version = self.read()["skills"][sid]["version"]
            return load_skill_from_dir(self.skills_dir / sid / str(version) / sid)

    @staticmethod
    def unpack_skill(data):
        if len(data) > MAX_BYTES:
            raise ConfigError("导入包最多 10 MiB。")
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 150 or sum(x.file_size for x in entries) > MAX_BYTES:
                    raise ConfigError("导入包文件过多或解压后超过 10 MiB。")
                files = {}
                for item in entries:
                    if stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                        raise ConfigError("不支持符号链接或加密压缩包。")
                    name = item.filename
                    path = PurePosixPath(name)
                    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                        raise ConfigError("压缩包包含不安全路径。")
                    if path.parts and (path.parts[0] == "__MACOSX" or path.name == ".DS_Store"):
                        continue
                    if not item.is_dir():
                        if name in files:
                            raise ConfigError("压缩包有重复文件。")
                        files[name] = archive.read(item)
                if "SKILL.md" not in files:
                    roots = [k[:-len("SKILL.md")] for k in files if k.endswith("/SKILL.md")]
                    if len(roots) != 1 or not all(k.startswith(roots[0]) for k in files):
                        raise ConfigError("每次只导入一个 Skill，根目录需有 SKILL.md。")
                    files = {k[len(roots[0]):]: v for k, v in files.items()}
                return files
        except (zipfile.BadZipFile, RuntimeError, OSError):
            raise ConfigError("无法读取 Skill ZIP 包。") from None
