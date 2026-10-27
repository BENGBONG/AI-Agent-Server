"""Native ADK Skill script backend: macOS sandbox or a Docker worker.

Only the SkillToolset uses this executor; it is not a general agent shell.
No project directory, credentials or user upload directories are mounted.
"""

import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from google.adk.code_executors.base_code_executor import BaseCodeExecutor
from google.adk.code_executors.code_execution_utils import CodeExecutionResult
from pydantic import Field

MAX_OUTPUT = 4 * 1024 * 1024
DOCKER_IMAGE = "adk-skill-runtime:local"


def runtime_status():
    selected = os.environ.get("ADK_SKILL_SCRIPT_BACKEND", "auto")
    backend = selected
    if selected == "auto":
        backend = "macos" if platform.system() == "Darwin" else "docker"
    available = (backend == "macos" and platform.system() == "Darwin" and Path("/usr/bin/sandbox-exec").is_file()) or (backend == "docker" and bool(shutil.which("docker")))
    return {"backend": backend, "available": bool(available),
            "supported_scripts": [".py", ".sh", ".bash"],
            "network": "disabled", "timeout_seconds": 30,
            "description": "macOS 独立沙箱进程" if backend == "macos" else "Docker 独立容器（需已构建运行镜像且 Docker 服务可用）" if backend == "docker" else "脚本运行已关闭",
            "image": os.environ.get("ADK_SKILL_SCRIPT_IMAGE", DOCKER_IMAGE) if backend == "docker" else None}


def _macos_profile(work):
    # Resolve paths because /tmp, interpreter and Homebrew may be symlinks.
    reads = {str(Path(p).resolve()) for p in (
        str(work),
        sys.prefix, sys.base_prefix,
        "/opt/homebrew/Cellar", "/opt/homebrew/opt", "/opt/homebrew/bin",
    )}
    paths = " ".join("(subpath " + json.dumps(p, ensure_ascii=False) + ")" for p in sorted(reads))
    return (
        # macOS dyld needs OS-managed caches outside /System and /usr.
        # Keep system reads available, block user data and all host writes.
        '(version 1) (allow default) (deny network*) (deny appleevent-send) '
        '(deny file-read* (subpath "/Users") (subpath "/Volumes") '
        '(subpath "/private/var/folders") (subpath "/private/tmp") '
        '(subpath "/Library/Keychains")) (deny file-write*) '
        '(allow file-read* ' + paths + ') '
        '(allow file-write* (subpath ' + json.dumps(str(work), ensure_ascii=False) + ') (literal "/dev/null"))'
    )


class SkillScriptExecutor(BaseCodeExecutor):
    timeout_seconds: int = Field(default=30, ge=1, le=120)

    def execute_code(self, invocation_context, code_execution_input):
        status = runtime_status()
        if not status["available"]:
            return CodeExecutionResult(stderr="脚本运行环境不可用。macOS 需要 sandbox-exec；Linux/服务器需要 Docker 与预构建 Skill 镜像。", exit_code=125)
        with tempfile.TemporaryDirectory(prefix="adk-skill-run-") as directory:
            work = Path(directory).resolve()
            (work / "entry.py").write_text(code_execution_input.code, encoding="utf-8")
            (work / "bootstrap.py").write_text(
                "import resource,runpy,sys\n"
                f"resource.setrlimit(resource.RLIMIT_CPU, ({self.timeout_seconds + 1}, {self.timeout_seconds + 1}))\n"
                "resource.setrlimit(resource.RLIMIT_FSIZE, (67108864, 67108864))\n"
                "resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))\n"
                "runpy.run_path(sys.argv[1],run_name='__main__')\n", encoding="utf-8")
            env = {"PATH": os.pathsep.join([str(Path(sys.executable).parent), "/opt/homebrew/bin", "/usr/bin", "/bin"]),
                   "HOME": str(work), "TMPDIR": str(work), "LANG": "en_US.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
            container = None
            if status["backend"] == "macos":
                (work / "sandbox.sb").write_text(_macos_profile(work))
                command = ["/usr/bin/sandbox-exec", "-f", str(work / "sandbox.sb"), sys.executable, "-I", "-B", str(work / "bootstrap.py"), str(work / "entry.py")]
            else:
                container = "adk-skill-" + work.name.removeprefix("adk-skill-run-").lower().replace("_", "-")
                command = [shutil.which("docker"), "run", "--rm", "--pull=never", "--name", container,
                           "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                           "--read-only", "--pids-limit=64", "--memory=512m", "--cpus=1",
                           "--user", f"{os.getuid()}:{os.getgid()}",
                           "--mount", f"type=bind,src={work},dst=/workspace", "--workdir=/workspace",
                           "--env=HOME=/workspace", "--env=TMPDIR=/workspace", "--env=PYTHONDONTWRITEBYTECODE=1",
                           status["image"], "python", "-I", "-B", "/workspace/bootstrap.py", "/workspace/entry.py"]
                # Docker client needs its own socket/config location; those
                # values are never passed into the script's container.
                env = {**env, "HOME": os.path.expanduser("~")}
                for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
                    if key in os.environ: env[key] = os.environ[key]
            started = time.monotonic()
            reason = None
            with (work / "stdout.log").open("wb") as stdout, (work / "stderr.log").open("wb") as stderr:
                try:
                    process = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                               stdout=stdout, stderr=stderr, start_new_session=True)
                    while process.poll() is None:
                        if time.monotonic() - started > self.timeout_seconds:
                            reason = "脚本超过执行时间上限，已终止。"; break
                        if sum((work / name).stat().st_size for name in ("stdout.log", "stderr.log")) > MAX_OUTPUT:
                            reason = "脚本输出超过 4 MiB 上限，已终止。"; break
                        time.sleep(.04)
                    if reason:
                        try: os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                    process.wait()
                    # Reap any child still sharing the execution process group.
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    rc = process.returncode
                except OSError:
                    return CodeExecutionResult(stderr="脚本执行器无法启动，请检查运行环境。", exit_code=125)
                finally:
                    if container:
                        try:
                            subprocess.run([shutil.which("docker"), "rm", "-f", container],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           env=env, timeout=10, check=False)
                        except (OSError, subprocess.TimeoutExpired):
                            pass
            out = (work / "stdout.log").read_bytes()[:MAX_OUTPUT].decode("utf-8", errors="replace")
            err = (work / "stderr.log").read_bytes()[:MAX_OUTPUT].decode("utf-8", errors="replace")
            if reason:
                return CodeExecutionResult(stderr=reason, exit_code=124)
            if (work / "stdout.log").stat().st_size + (work / "stderr.log").stat().st_size > MAX_OUTPUT:
                return CodeExecutionResult(stderr="脚本输出超过 4 MiB 上限。", exit_code=124)
            return CodeExecutionResult(stdout=out, stderr=err, exit_code=rc)
