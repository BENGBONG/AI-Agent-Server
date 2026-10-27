"""Prompt locally for the API key without echoing it into terminal history."""

from getpass import getpass
from pathlib import Path

from dotenv import set_key


def main() -> None:
    key = getpass("请输入 DeepSeek API Key（输入不回显）: ").strip()
    if not key:
        raise SystemExit("没有输入 Key，配置未修改。")
    env_file = Path(__file__).resolve().with_name(".env")
    env_file.touch(mode=0o600, exist_ok=True)
    env_file.chmod(0o600)
    set_key(str(env_file), "DEEPSEEK_API_KEY", key, quote_mode="always")
    print("Key 已保存到本项目 .env。回到网页重新发送消息即可，无需重启。")


if __name__ == "__main__":
    main()
