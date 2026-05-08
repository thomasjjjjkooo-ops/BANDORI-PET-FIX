import json
import time
import uuid
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ACTION_DIR = BASE_DIR / ".runtime" / "actions"


def publish_action(character: str, action: str):
    if not character or not action:
        return
    try:
        ACTION_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": uuid.uuid4().hex,
            "character": character,
            "action": action,
            "created": time.time(),
        }
        path = ACTION_DIR / f"{payload['id']}.json"
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)
    except Exception:
        pass


def consume_actions(character: str, seen: set[str]) -> list[str]:
    if not character:
        return []
    actions = []
    now = time.time()
    try:
        ACTION_DIR.mkdir(parents=True, exist_ok=True)
        for path in ACTION_DIR.glob("*.json"):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            action_id = item.get("id", path.stem)
            created = float(item.get("created", 0))
            if now - created > 30.0:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                continue
            if action_id in seen:
                continue
            if item.get("character") != character:
                continue
            seen.add(action_id)
            actions.append(item.get("action", ""))
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass
    return [action for action in actions if action]
