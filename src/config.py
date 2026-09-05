import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = ROOT / "data" / "snapshot_nvda.json"


def snapshot_path() -> Path:
    override = os.environ.get("DATA_SNAPSHOT_PATH")
    return Path(override) if override else DEFAULT_SNAPSHOT
