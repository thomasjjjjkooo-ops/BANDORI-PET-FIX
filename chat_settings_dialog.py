"""Minimal settings dialog for the chat-only fork.

Replaces the 85KB settings_window.py from the original Live2D-pet build with
just the things relevant to LLM chat: API config, identity / POV, theme,
language, plus character + group selection.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout, QListWidget,
    QListWidgetItem, QWidget, QStackedWidget, QSpacerItem, QSizePolicy,
)

from qfluentwidgets import (
    LineEdit, PasswordLineEdit, ComboBox, SwitchButton, ColorPickerButton,
    PrimaryPushButton, PushButton, BodyLabel, StrongBodyLabel, FluentIcon,
    TextEdit, IndicatorPosition,
)

from i18n_manager import current_language, set_language, available_languages


class ChatSettingsDialog(QDialog):
    settings_applied = Signal()

    def __init__(self, config_manager, model_manager, parent=None):
        super().__init__(parent)
        self._cfg = config_manager
        self._mm = model_manager
        self.setWindowTitle("设置")
        self.setMinimumSize(640, 520)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        self._nav = QListWidget(self)
        self._nav.setFixedWidth(140)
        for name in ("角色", "LLM", "POV", "外观"):
            self._nav.addItem(QListWidgetItem(name))
        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        root.addWidget(self._nav)

        right = QVBoxLayout()
        right.setSpacing(10)
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_character_page())
        self._stack.addWidget(self._build_llm_page())
        self._stack.addWidget(self._build_pov_page())
        self._stack.addWidget(self._build_appearance_page())
        right.addWidget(self._stack, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = PushButton("取消", self)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        apply_btn = PrimaryPushButton("应用", self)
        apply_btn.clicked.connect(self._on_apply)
        button_row.addWidget(apply_btn)
        right.addLayout(button_row)

        root.addLayout(right, 1)

    def _on_nav_changed(self, row: int):
        self._stack.setCurrentIndex(row)

    # --- Pages ---

    def _build_character_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        layout.addWidget(StrongBodyLabel("当前对话角色", page))
        self._character_combo = ComboBox(page)
        for char_key in self._mm.characters:
            label = self._mm.get_display_name(char_key)
            band = self._mm.get_character_band(char_key)
            if band:
                label = f"{label}（{self._mm.get_band_display_name(band)}）"
            self._character_combo.addItem(label, userData=char_key)
        layout.addWidget(self._character_combo)

        layout.addWidget(BodyLabel(
            "提示：只有 characters/<姓名>/*.md 存在的角色才有深度人设。", page
        ))

        layout.addSpacing(12)
        layout.addWidget(StrongBodyLabel("群聊角色（可多选）", page))
        layout.addWidget(BodyLabel(
            "勾选 ≥ 2 个角色，下次发消息会触发群聊（所有角色按顺序回复）。", page
        ))

        self._group_list = QListWidget(page)
        self._group_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for char_key in self._mm.characters:
            item = QListWidgetItem(self._mm.get_display_name(char_key))
            item.setData(Qt.ItemDataRole.UserRole, char_key)
            self._group_list.addItem(item)
        layout.addWidget(self._group_list, 1)

        return page

    def _build_llm_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._llm_url = LineEdit(page)
        self._llm_url.setPlaceholderText("https://api.openai.com/v1/chat/completions")
        form.addRow(BodyLabel("API URL"), self._llm_url)

        self._llm_key = PasswordLineEdit(page)
        self._llm_key.setPlaceholderText("sk-...")
        form.addRow(BodyLabel("API Key"), self._llm_key)

        self._llm_model = LineEdit(page)
        self._llm_model.setPlaceholderText("gpt-4o-mini / deepseek-chat / ...")
        form.addRow(BodyLabel("主模型"), self._llm_model)

        self._llm_aux_model = LineEdit(page)
        self._llm_aux_model.setPlaceholderText("（可选）群聊调度用更便宜的模型")
        form.addRow(BodyLabel("辅助模型"), self._llm_aux_model)

        self._enable_thinking = ComboBox(page)
        self._enable_thinking.addItem("自动（让模型自己决定）", userData=None)
        self._enable_thinking.addItem("强制开启 thinking", userData=True)
        self._enable_thinking.addItem("强制关闭 thinking", userData=False)
        form.addRow(BodyLabel("Thinking 模式"), self._enable_thinking)

        self._show_reasoning = SwitchButton(page, indicatorPos=IndicatorPosition.RIGHT)
        self._show_reasoning.setOnText("显示")
        self._show_reasoning.setOffText("隐藏")
        form.addRow(BodyLabel("展示思考过程"), self._show_reasoning)

        return page

    def _build_pov_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._user_name = LineEdit(page)
        self._user_name.setPlaceholderText("LLM 会以这个名字称呼你")
        form.addRow(BodyLabel("你的名字"), self._user_name)

        self._user_color = ColorPickerButton(QColor("#2aabee"), "用户气泡颜色", page)
        form.addRow(BodyLabel("气泡颜色"), self._user_color)

        self._pov_mode = ComboBox(page)
        self._pov_mode.addItem("关闭（普通用户）", userData="off")
        self._pov_mode.addItem("自定义视角", userData="custom")
        self._pov_mode.addItem("扮演角色", userData="role")
        self._pov_mode.currentIndexChanged.connect(self._on_pov_mode_changed)
        form.addRow(BodyLabel("POV 模式"), self._pov_mode)

        self._pov_custom_prompt = TextEdit(page)
        self._pov_custom_prompt.setPlaceholderText("例：用户是 X 的青梅竹马，从小学就认识")
        self._pov_custom_prompt.setMaximumHeight(120)
        form.addRow(BodyLabel("自定义视角"), self._pov_custom_prompt)

        self._pov_role_character = ComboBox(page)
        for char_key in self._mm.characters:
            self._pov_role_character.addItem(
                self._mm.get_display_name(char_key), userData=char_key,
            )
        form.addRow(BodyLabel("扮演角色"), self._pov_role_character)

        return page

    def _build_appearance_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._dark_theme = SwitchButton(page, indicatorPos=IndicatorPosition.RIGHT)
        self._dark_theme.setOnText("深色")
        self._dark_theme.setOffText("浅色")
        form.addRow(BodyLabel("主题"), self._dark_theme)

        self._language = ComboBox(page)
        lang_labels = {"zh_CN": "简体中文", "en_US": "English", "ja_JP": "日本語"}
        for lang_code in available_languages():
            self._language.addItem(lang_labels.get(lang_code, lang_code), userData=lang_code)
        form.addRow(BodyLabel("语言"), self._language)

        return page

    # --- Load / Save ---

    def _load_values(self):
        char = self._cfg.get("character", "")
        idx = self._character_combo.findData(char)
        if idx >= 0:
            self._character_combo.setCurrentIndex(idx)
        elif self._character_combo.count() > 0:
            self._character_combo.setCurrentIndex(0)

        group_chars = self._cfg.get("group_characters", []) or []
        for i in range(self._group_list.count()):
            item = self._group_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) in group_chars:
                item.setSelected(True)

        self._llm_url.setText(self._cfg.get("llm_api_url", ""))
        self._llm_key.setText(self._cfg.get("llm_api_key", ""))
        self._llm_model.setText(self._cfg.get("llm_model_id", ""))
        self._llm_aux_model.setText(self._cfg.get("llm_aux_model_id", ""))

        thinking = self._cfg.get("llm_enable_thinking", None)
        for i in range(self._enable_thinking.count()):
            if self._enable_thinking.itemData(i) == thinking:
                self._enable_thinking.setCurrentIndex(i)
                break
        self._show_reasoning.setChecked(bool(self._cfg.get("llm_show_reasoning", True)))

        self._user_name.setText(self._cfg.get("user_name", ""))
        try:
            self._user_color.setColor(QColor(self._cfg.get("user_avatar_color", "#2aabee")))
        except Exception:
            pass

        pov_mode = self._cfg.get("pov_mode", "off")
        for i in range(self._pov_mode.count()):
            if self._pov_mode.itemData(i) == pov_mode:
                self._pov_mode.setCurrentIndex(i)
                break

        self._pov_custom_prompt.setPlainText(self._cfg.get("pov_custom_prompt", ""))

        pov_role = self._cfg.get("pov_role_character", "")
        idx = self._pov_role_character.findData(pov_role)
        if idx >= 0:
            self._pov_role_character.setCurrentIndex(idx)

        self._on_pov_mode_changed()

        self._dark_theme.setChecked(bool(self._cfg.get("dark_theme", False)))

        cur_lang = self._cfg.get("language", "") or current_language()
        idx = self._language.findData(cur_lang)
        if idx >= 0:
            self._language.setCurrentIndex(idx)

    def _on_pov_mode_changed(self):
        mode = self._pov_mode.currentData()
        self._pov_custom_prompt.setEnabled(mode == "custom")
        self._pov_role_character.setEnabled(mode == "role")

    def _on_apply(self):
        cfg = self._cfg

        cfg.set("character", self._character_combo.currentData() or "")

        group = []
        for i in range(self._group_list.count()):
            item = self._group_list.item(i)
            if item.isSelected():
                group.append(item.data(Qt.ItemDataRole.UserRole))
        cfg.set("group_characters", group)

        cfg.set("llm_api_url", self._llm_url.text().strip())
        cfg.set("llm_api_key", self._llm_key.text().strip())
        cfg.set("llm_model_id", self._llm_model.text().strip())
        cfg.set("llm_aux_model_id", self._llm_aux_model.text().strip())
        cfg.set("llm_enable_thinking", self._enable_thinking.currentData())
        cfg.set("llm_show_reasoning", bool(self._show_reasoning.isChecked()))

        cfg.set("user_name", self._user_name.text().strip())
        try:
            cfg.set("user_avatar_color", self._user_color.color.name())
        except Exception:
            pass

        cfg.set("pov_mode", self._pov_mode.currentData() or "off")
        cfg.set("pov_custom_prompt", self._pov_custom_prompt.toPlainText().strip())
        cfg.set("pov_role_character", self._pov_role_character.currentData() or "")

        cfg.set("dark_theme", bool(self._dark_theme.isChecked()))
        new_lang = self._language.currentData() or ""
        cfg.set("language", new_lang)
        if new_lang and new_lang != current_language():
            set_language(new_lang)

        try:
            cfg.save()
        except Exception as e:
            print(f"[settings] save failed: {e}", flush=True)

        self.settings_applied.emit()
        self.accept()
