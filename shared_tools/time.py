"""Local clock tools, independent of the model provider."""

from datetime import datetime
from zoneinfo import ZoneInfo


def get_beijing_time() -> dict[str, str]:
    """返回当前北京时间、日期和时区。需要判断今天、临近到期日或核验时间时使用。"""
    return {
        "timezone": "Asia/Shanghai",
        "time": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    }
