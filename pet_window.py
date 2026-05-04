import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QApplication, QSystemTrayIcon, QMenu,
)

from qfluentwidgets import (
    setTheme, Theme, FluentIcon,
)
from qfluentwidgets.components.widgets.menu import DWMMenu

from live2d_widget import Live2DWidget
from model_manager import ModelManager
from settings_dialog import ModelSelectDialog


class PetWindow(QWidget):
    def __init__(self, live2d_module):
        super().__init__()
        self._live2d = live2d_module
        self._model_manager = ModelManager()
        self._current_char = ""
        self._current_costume = ""
        self._tray_icon = None
        self._opacity = 1.0
        self._init_ui()
        self._init_tray()
        self._load_default_model()

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
        layout.addWidget(self._live2d_widget)

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

        models_action = menu.addAction(self.tr("Change Model..."))
        models_action.triggered.connect(self._open_model_dialog)

        menu.addSeparator()

        opacity_menu = menu.addMenu(self.tr("Opacity"))
        for pct in [100, 80, 60, 40, 20]:
            act = opacity_menu.addAction(f"{pct}%")
            act.triggered.connect(lambda checked, v=pct: self.set_opacity(v / 100.0))

        menu.addSeparator()

        exit_action = menu.addAction(self.tr("Exit"))
        exit_action.triggered.connect(self._quit)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.show()

    def _load_default_model(self):
        chars = self._model_manager.characters
        if not chars:
            return
        char = chars[0]
        costume = self._model_manager.get_default_costume(char)
        if not costume:
            return
        self._current_char = char
        self._current_costume = costume
        path = self._model_manager.get_model_json_path(char, costume)
        self._live2d_widget.set_model_path(path)

    def _switch_model(self, character: str, costume: str):
        path = self._model_manager.get_model_json_path(character, costume)
        if not path:
            return
        self._current_char = character
        self._current_costume = costume
        self._live2d_widget.set_model_path(path)
        self._tray_icon.setToolTip(
            f"Bandori Desktop Pet - {character.title()} ({costume})"
        )

    def _on_drag(self, dx: int, dy: int):
        self.move(self.x() + dx, self.y() + dy)

    def _on_click(self):
        pass

    def _toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def _open_model_dialog(self):
        dlg = ModelSelectDialog(
            self._model_manager,
            self._current_char,
            self._current_costume,
            self,
        )
        dlg.model_changed.connect(self._switch_model)
        dlg.exec()

    def set_opacity(self, value: float):
        self._opacity = value
        self.setWindowOpacity(value)

    def _quit(self):
        self._tray_icon.hide()
        QApplication.quit()

    def contextMenuEvent(self, event):
        menu = DWMMenu(self)

        menu.addAction(
            FluentIcon.APPLICATION,
            self.tr("Change Model..."),
            triggered=self._open_model_dialog,
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

        from qfluentwidgets import isDarkTheme
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
        from qfluentwidgets import isDarkTheme
        setTheme(Theme.LIGHT if isDarkTheme() else Theme.DARK)

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 20, geo.bottom() - self.height() - 40)
