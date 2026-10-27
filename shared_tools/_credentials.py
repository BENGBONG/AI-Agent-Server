"""Read shared provider credentials without exposing them in tool results."""

import os
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def read_deepseek_key() -> str:
    return (dotenv_values(ENV_FILE).get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
