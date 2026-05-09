"""Character / band metadata for the chat-only fork.

Live2D model scanning has been removed. This module only loads display
metadata from outfit.json + band.json so the chat UI can show character
names, group them by band, and detect which characters have a markdown
persona file under characters/.
"""

import json
from pathlib import Path

from process_utils import app_base_dir

BASE_DIR = app_base_dir()
OUTFIT_JSON = BASE_DIR / "outfit.json"
BAND_JSON = BASE_DIR / "band.json"
CHARACTERS_DIR = BASE_DIR / "characters"


class ModelManager:
    def __init__(self):
        self._characters: dict[str, dict] = {}
        self._bands: list[dict] = []
        self._advanced_roleplay_cache: dict[str, bool] | None = None
        self._parse_outfit_json()
        self._parse_band_json()

    def _parse_outfit_json(self):
        if not OUTFIT_JSON.exists():
            return
        try:
            data = json.loads(OUTFIT_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        chars = data.get("characters", {})
        if not isinstance(chars, dict):
            return
        for key, info in chars.items():
            if not isinstance(info, dict):
                continue
            self._characters[key] = {
                "display": info.get("display", key),
            }

    def _parse_band_json(self):
        configured_bands: list = []
        if BAND_JSON.exists():
            try:
                data = json.loads(BAND_JSON.read_text(encoding="utf-8"))
                configured_bands = data.get("bands", []) or []
            except (json.JSONDecodeError, OSError):
                configured_bands = []

        seen: set[str] = set()
        for band in configured_bands:
            if not isinstance(band, dict):
                continue
            characters = [
                c for c in band.get("characters", [])
                if isinstance(c, str) and c in self._characters
            ]
            if not characters:
                continue
            seen.update(characters)
            self._bands.append({
                "id": band.get("id", ""),
                "display": band.get("display", band.get("id", "")),
                "characters": characters,
            })

        ungrouped = [c for c in self._characters if c not in seen]
        if ungrouped:
            self._bands.append({
                "id": "others",
                "display": "其他角色",
                "characters": ungrouped,
            })

    def _scan_advanced_roleplay_support(self) -> dict[str, bool]:
        support = {character: False for character in self._characters}
        if not CHARACTERS_DIR.exists():
            return support

        display_to_key = {
            self.get_display_name(character): character
            for character in self._characters
        }
        for entry in CHARACTERS_DIR.iterdir():
            if not entry.is_dir():
                continue
            character = display_to_key.get(entry.name)
            if not character:
                continue
            support[character] = any(
                path.is_file() and path.suffix.lower() == ".md"
                for path in entry.iterdir()
            )
        return support

    @property
    def characters(self) -> list[str]:
        return list(self._characters.keys())

    @property
    def bands(self) -> list[dict]:
        return self._bands

    def get_band_display_name(self, band_id: str) -> str:
        for band in self._bands:
            if band["id"] == band_id:
                return band["display"]
        return band_id

    def get_band_characters(self, band_id: str) -> list[str]:
        for band in self._bands:
            if band["id"] == band_id:
                return band["characters"]
        return []

    def get_character_band(self, character: str) -> str:
        for band in self._bands:
            if character in band["characters"]:
                return band["id"]
        return ""

    def get_display_name(self, character: str) -> str:
        return self._characters.get(character, {}).get("display", character.title())

    def has_advanced_roleplay(self, character: str) -> bool:
        if self._advanced_roleplay_cache is None:
            self._advanced_roleplay_cache = self._scan_advanced_roleplay_support()
        return self._advanced_roleplay_cache.get(character, False)
