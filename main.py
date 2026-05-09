"""Chat-only launcher for the BANDORI chat fork.

The original project is a Live2D desktop pet that opens a chat window when
clicked. This fork strips out everything Live2D / pixel-pet / multi-process
and just keeps the LLM chat features (persona, POV, group chat).
"""

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from qfluentwidgets import setTheme, Theme

from process_utils import app_base_dir
from config_manager import ConfigManager
from i18n_manager import set_language, detect_system_language, current_language
from model_manager import ModelManager
from chat_window import ChatWindow
from chat_settings_dialog import ChatSettingsDialog


BASE_DIR = str(app_base_dir())


def _resolve_character(cfg: ConfigManager, mgr: ModelManager) -> str:
    requested = cfg.get("character", "")
    if requested and requested in mgr.characters:
        return requested
    return mgr.characters[0] if mgr.characters else ""


def _open_chat(cfg: ConfigManager, mgr: ModelManager) -> ChatWindow | None:
    character = _resolve_character(cfg, mgr)
    if not character:
        print(
            "[main] No characters available. Make sure outfit.json has a "
            "characters[...] entry.",
            file=sys.stderr,
        )
        return None
    group = [c for c in (cfg.get("group_characters", []) or []) if c in mgr.characters]
    chat = ChatWindow(
        character=character,
        model_manager=mgr,
        config_manager=cfg,
        group_characters=group,
    )
    geo_x = cfg.get("window_x", -1)
    geo_y = cfg.get("window_y", -1)
    geo_w = cfg.get("window_width", 720) or 720
    geo_h = cfg.get("window_height", 720) or 720
    chat.resize(int(geo_w), int(geo_h))
    if geo_x >= 0 and geo_y >= 0:
        chat.move(int(geo_x), int(geo_y))
    chat.show()
    return chat


def main() -> int:
    cfg = ConfigManager()

    lang = cfg.get("language", "") or detect_system_language()
    set_language(lang)

    app = QApplication(sys.argv)
    app.setApplicationName("BandoriChat")
    app.setOrganizationName("BandoriChat")
    app.setQuitOnLastWindowClosed(False)

    icon_path = os.path.join(BASE_DIR, "logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    setTheme(Theme.DARK if cfg.get("dark_theme", False) else Theme.LIGHT)

    mgr = ModelManager()
    state: dict = {"chat": None}

    def open_settings():
        dialog = ChatSettingsDialog(cfg, mgr, parent=state.get("chat"))

        def apply_changes():
            chat = state.get("chat")
            if chat is None:
                state["chat"] = _open_chat(cfg, mgr)
                return
            current = chat.property("character_key") or chat._character
            new_char = _resolve_character(cfg, mgr)
            new_group = [c for c in (cfg.get("group_characters", []) or []) if c in mgr.characters]
            char_changed = new_char != current
            group_changed = sorted(new_group) != sorted(chat._group_characters)
            if char_changed or group_changed:
                chat.close()
                state["chat"] = _open_chat(cfg, mgr)
            else:
                setTheme(Theme.DARK if cfg.get("dark_theme", False) else Theme.LIGHT)

        dialog.settings_applied.connect(apply_changes)
        dialog.exec()

    def quit_all():
        chat = state.get("chat")
        if chat is not None:
            try:
                geo = chat.geometry()
                cfg.set("window_x", geo.x())
                cfg.set("window_y", geo.y())
                cfg.set("window_width", geo.width())
                cfg.set("window_height", geo.height())
            except Exception:
                pass
        cfg.set("language", current_language())
        try:
            cfg.save()
        except Exception as e:
            print(f"[main] config save failed on quit: {e}", file=sys.stderr)
        app.quit()

    tray = QSystemTrayIcon(app)
    tray.setIcon(QIcon(icon_path) if os.path.exists(icon_path) else QIcon())
    tray.setToolTip("BandoriChat")
    menu = QMenu()
    menu.addAction("打开聊天").triggered.connect(
        lambda: state.setdefault("chat", None) or _ensure_chat(state, cfg, mgr)
    )
    menu.addAction("设置").triggered.connect(open_settings)
    menu.addSeparator()
    menu.addAction("退出").triggered.connect(quit_all)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: _ensure_chat(state, cfg, mgr)
        if reason == QSystemTrayIcon.ActivationReason.Trigger
        else None
    )
    tray.show()

    state["chat"] = _open_chat(cfg, mgr)
    if state["chat"] is None:
        # No characters → still bring up settings so the user can configure / debug.
        open_settings()

    return app.exec()


def _ensure_chat(state: dict, cfg: ConfigManager, mgr: ModelManager) -> None:
    chat = state.get("chat")
    if chat is None or not chat.isVisible():
        state["chat"] = _open_chat(cfg, mgr)
    else:
        chat.raise_()
        chat.activateWindow()


if __name__ == "__main__":
    sys.exit(main())
