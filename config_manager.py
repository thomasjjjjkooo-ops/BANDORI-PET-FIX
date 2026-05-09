import json
import os
import tempfile
from pathlib import Path
from process_utils import app_base_dir

BASE_DIR = app_base_dir()
CONFIG_PATH = BASE_DIR / "config.json"

DEFAULTS = {
    "character": "",
    "language": "",
    "dark_theme": False,
    "llm_api_url": "",
    "llm_api_key": "",
    "llm_model_id": "",
    "llm_aux_model_id": "",
    "user_name": "",
    "user_avatar_color": "#2aabee",
    "pov_mode": "off",
    "pov_custom_prompt": "",
    "pov_role_character": "",
    "llm_enable_thinking": None,
    "llm_show_reasoning": True,
    "group_characters": [],
    "window_x": -1,
    "window_y": -1,
    "window_width": 720,
    "window_height": 720,
}


class ConfigManager:
    def __init__(self, path=CONFIG_PATH):
        self._path = Path(path)
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for k in DEFAULTS:
                    if k in loaded:
                        self._data[k] = loaded[k]
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=self._path.name + ".",
            suffix=".tmp",
            dir=str(self._path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def update(self, d: dict):
        self._data.update(d)

    @property
    def data(self):
        return dict(self._data)
