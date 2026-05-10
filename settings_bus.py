import json
import time
import uuid
from pathlib import Path

from process_utils import app_base_dir


BASE_DIR = app_base_dir()
SETTINGS_DIR = BASE_DIR / ".runtime" / "settings"


def publish_settings(data: dict):
    if not isinstance(data, dict):
        return
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": uuid.uuid4().hex,
            "created": time.time(),
            "settings": data,
        }
        path = SETTINGS_DIR / f"{payload['id']}.json"
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)
    except Exception:
        pass


def consume_settings(seen: set[str]) -> list[dict]:
    updates = []
    now = time.time()
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        for path in SETTINGS_DIR.glob("*.json"):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            update_id = item.get("id", path.stem)
            created = float(item.get("created", 0))
            if now - created > 30.0:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                continue
            if update_id in seen:
                continue
            seen.add(update_id)
            settings = item.get("settings", {})
            if isinstance(settings, dict):
                updates.append(settings)
    except Exception:
        pass
    return updates
