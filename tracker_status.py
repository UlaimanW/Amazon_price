import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


STATUS_FILE = Path("tracker_status.json")
SAUDI_TIMEZONE = timezone(timedelta(hours=3))


def record_successful_run(completed_at=None):
    completed_at = completed_at or datetime.now(timezone.utc)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)

    data = {
        "last_successful_run": completed_at.astimezone(timezone.utc).isoformat()
    }
    STATUS_FILE.write_text(
        json.dumps(data, indent=4) + "\n",
        encoding="utf-8",
    )


def load_last_successful_run():
    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        value = data.get("last_successful_run")
        if not value:
            return None
        completed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return None

    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    return completed_at


def format_last_successful_run(completed_at):
    if completed_at is None:
        return "Last successful run: Not available yet"

    saudi_time = completed_at.astimezone(SAUDI_TIMEZONE)
    return (
        "Last successful run: "
        f"{saudi_time.strftime('%d %B %Y at %I:%M %p')} (Saudi time)"
    )
