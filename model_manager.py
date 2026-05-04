import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"


class ModelManager:
    def __init__(self):
        self._characters: dict[str, list[dict]] = {}
        self._scan()

    def _scan(self):
        for entry in sorted(MODELS_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            char_name = entry.name
            costumes = []
            for costume_dir in sorted(entry.iterdir()):
                if not costume_dir.is_dir():
                    continue
                model_json = costume_dir / "model.json"
                if model_json.exists():
                    costumes.append({
                        "name": costume_dir.name,
                        "path": str(model_json.resolve()),
                    })
            if costumes:
                self._characters[char_name] = costumes

    @property
    def characters(self) -> list[str]:
        return list(self._characters.keys())

    def get_costumes(self, character: str) -> list[dict]:
        return self._characters.get(character, [])

    def get_default_costume(self, character: str) -> str:
        costumes = self.get_costumes(character)
        if not costumes:
            return ""
        preferred = ["live_default", "casual", "school_winter", "school_summer"]
        costume_names = [c["name"] for c in costumes]
        for pref in preferred:
            if pref in costume_names:
                return pref
        return costumes[0]["name"]

    @staticmethod
    def get_model_json_path(character: str, costume: str) -> str:
        path = MODELS_DIR / character / costume / "model.json"
        if path.exists():
            return str(path.resolve())
        return ""
