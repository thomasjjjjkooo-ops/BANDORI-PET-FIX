import os

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QApplication, QSystemTrayIcon, QMenu,
)

from qfluentwidgets import (
    setTheme, Theme, FluentIcon,
)
from qfluentwidgets.components.widgets.menu import DWMMenu

from live2d_widget import Live2DWidget
from model_manager import ModelManager
from settings_window import SettingsWindow
from radial_menu import RadialMenu


class PetWindow(QWidget):
    def __init__(self, live2d_module, model_manager=None,
                 character="", costume="", fps=120, opacity=1.0,
                 config_manager=None):
        super().__init__()
        self._live2d = live2d_module
        self._model_manager = model_manager or ModelManager()
        self._current_char = character
        self._current_costume = costume
        self._fps = fps
        self._opacity = opacity
        self._tray_icon = None
        self._settings_window = None
        self._cfg = config_manager
        self._radial_menu = None
        self._show_pos_set = False

        self._init_ui()
        self._init_tray()
        self._load_initial_model()

        self.setWindowOpacity(self._opacity)

    def _init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)

        self.resize(400, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._live2d_widget = Live2DWidget(self)
        self._live2d_widget.set_live2d_module(self._live2d)
        self._live2d_widget.set_window_drag_callback(self._on_drag)
        self._live2d_widget.set_click_callback(self._on_click)
        self._live2d_widget.set_right_click_callback(self._on_right_click)
        self._live2d_widget.set_fps(self._fps)
        layout.addWidget(self._live2d_widget)

    def set_fps(self, fps: int):
        self._fps = fps
        self._live2d_widget.set_fps(fps)

    def _init_tray(self):
        self._tray_icon = QSystemTrayIcon(self)
        icon_path = os.path.join(
            os.path.dirname(__file__),
            "third_party", "PyQt-Fluent-Widgets", "qfluentwidgets",
            "_rc", "images", "logo.png"
        )
        if os.path.exists(icon_path):
            self._tray_icon.setIcon(QIcon(icon_path))
        else:
            self._tray_icon.setIcon(QIcon())

        self._tray_icon.setToolTip("Bandori Desktop Pet")

        menu = QMenu()

        show_action = menu.addAction(self.tr("Show/Hide"))
        show_action.triggered.connect(self._toggle_visible)

        settings_action = menu.addAction(self.tr("Settings..."))
        settings_action.triggered.connect(self._open_settings)

        menu.addSeparator()

        opacity_menu = menu.addMenu(self.tr("Opacity"))
        for pct in [100, 80, 60, 40, 20]:
            act = opacity_menu.addAction(f"{pct}%")
            act.triggered.connect(lambda checked, v=pct: self.set_opacity(v / 100.0))

        menu.addSeparator()

        exit_action = menu.addAction(self.tr("Exit"))
        exit_action.triggered.connect(self._quit)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _load_initial_model(self):
        if not self._current_char or not self._current_costume:
            chars = self._model_manager.characters
            if not chars:
                return
            self._current_char = chars[0]
            self._current_costume = self._model_manager.get_default_costume(self._current_char)

        path = self._model_manager.get_model_json_path(
            self._current_char, self._current_costume
        )
        if path:
            self._live2d_widget.set_model_path(path)
            self._update_tooltip()

    def _switch_model(self, character: str, costume: str):
        path = self._model_manager.get_model_json_path(character, costume)
        if not path:
            return
        self._current_char = character
        self._current_costume = costume
        self._live2d_widget.set_model_path(path)
        self._update_tooltip()
        self._save_config()

    def _apply_settings(self, data: dict):
        if "fps" in data:
            self.set_fps(data["fps"])
        if "opacity" in data:
            self.set_opacity(data["opacity"])
        if "dark_theme" in data:
            setTheme(Theme.DARK if data["dark_theme"] else Theme.LIGHT)
        self._save_config()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._open_settings()

    def _update_tooltip(self):
        display = self._model_manager.get_display_name(self._current_char)
        costume_name = self._model_manager.get_costume_display_name(
            self._current_char, self._current_costume
        )
        self._tray_icon.setToolTip(
            f"Bandori Desktop Pet - {display} ({costume_name})"
        )

    def _on_drag(self, dx: int, dy: int):
        self.move(self.x() + dx, self.y() + dy)

    def _on_click(self):
        if self._radial_menu and self._radial_menu.isVisible():
            self._radial_menu.dismiss()

    def _on_right_click(self, gx: int, gy: int):
        if self._radial_menu is not None and self._radial_menu.isVisible():
            self._radial_menu.dismiss()
            return

        self._radial_menu = RadialMenu()
        self._radial_menu.set_animation_fps(self._fps)
        self._radial_menu.set_locked(self._live2d_widget._drag_locked)
        self._radial_menu.lock_toggled.connect(self._on_lock_toggled)
        self._radial_menu.closed.connect(lambda: setattr(self, '_radial_menu', None))

        self._radial_menu.add_item(
            "", "Chat", QColor(138, 43, 226),
            glyph="\U0001F4AC",
            on_click=self._on_radial_chat,
        )
        self._radial_menu.add_item(
            "", "Costume", QColor(220, 50, 120),
            glyph="\U0001F457",
            on_click=self._on_radial_costume,
        )
        self._radial_menu.add_item(
            "", "Motion", QColor(30, 144, 255),
            glyph="\U0001F3AC",
            on_click=self._on_radial_motion,
        )
        self._radial_menu.add_item(
            "", "Pixel", QColor(34, 180, 140),
            glyph="\U0001F47E",
            on_click=self._on_radial_pixel,
        )

        self._radial_menu.show_at(QPoint(gx, gy))

    def _on_radial_chat(self):
        pass

    def _on_radial_costume(self):
        self._open_settings()

    def _on_radial_motion(self):
        model = self._live2d_widget.model
        if model is None:
            return
        try:
            model.StartRandomMotion(
                priority=self._live2d.MotionPriority.FORCE,
                onFinishMotionHandler=self._on_motion_finished,
            )
        except Exception:
            pass

    def _on_motion_finished(self):
        model = self._live2d_widget.model
        if model is not None:
            model.ClearMotions()

    def _on_lock_toggled(self, locked: bool):
        self._live2d_widget.set_drag_locked(locked)

    def _on_radial_pixel(self):
        pass

    def _toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def _open_settings(self):
        if self._settings_window is not None and self._settings_window.isVisible():
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return

        self._settings_window = SettingsWindow(
            self._model_manager,
            current_char=self._current_char,
            current_costume=self._current_costume,
            current_fps=self._fps,
            current_opacity=self._opacity,
            show_launch=False,
        )
        self._settings_window.model_selected.connect(self._switch_model)
        self._settings_window.settings_changed.connect(self._apply_settings)
        self._settings_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._settings_window.destroyed.connect(lambda: setattr(self, '_settings_window', None))
        self._settings_window.show()

    def set_opacity(self, value: float):
        self._opacity = value
        self.setWindowOpacity(value)

    def _save_config(self):
        if self._cfg:
            from qfluentwidgets import isDarkTheme
            self._cfg.set("character", self._current_char)
            self._cfg.set("costume", self._current_costume)
            self._cfg.set("fps", self._fps)
            self._cfg.set("opacity", self._opacity)
            self._cfg.set("dark_theme", isDarkTheme())
            self._cfg.set("drag_locked", self._live2d_widget._drag_locked)
            self._cfg.set("window_x", self.x())
            self._cfg.set("window_y", self.y())
            self._cfg.set("window_width", self.width())
            self._cfg.set("window_height", self.height())
            self._cfg.save()

    def _quit(self):
        self._tray_icon.hide()
        QApplication.quit()

    def contextMenuEvent(self, event):
        menu = DWMMenu(self)

        menu.addAction(
            FluentIcon.SETTING,
            self.tr("Settings..."),
            triggered=self._open_settings,
        )
        menu.addSeparator()

        opacity_menu = DWMMenu(self.tr("Opacity"), menu)
        for pct in [100, 80, 60, 40, 20]:
            opacity_menu.addAction(
                f"{pct}%",
                triggered=lambda checked, v=pct: self.set_opacity(v / 100.0),
            )
        menu.addMenu(opacity_menu)

        menu.addSeparator()

        theme_text = self.tr("Light Theme") if isDarkTheme() else self.tr("Dark Theme")
        menu.addAction(
            FluentIcon.CONTRAST,
            theme_text,
            triggered=self._toggle_theme,
        )
        menu.addSeparator()

        menu.addAction(
            FluentIcon.HIDE,
            self.tr("Hide"),
            triggered=self.hide,
        )
        menu.addAction(
            FluentIcon.CLOSE,
            self.tr("Exit"),
            triggered=self._quit,
        )

        menu.exec(event.globalPos())

    @staticmethod
    def _toggle_theme():
        setTheme(Theme.LIGHT if isDarkTheme() else Theme.DARK)

    def showEvent(self, event):
        super().showEvent(event)
        if self._show_pos_set:
            return
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 20, geo.bottom() - self.height() - 40)


def isDarkTheme():
    from qfluentwidgets import isDarkTheme as _is_dark
    return _is_dark()
