from PySide6 import QtWidgets

from core import debug_config


class DebugSettings(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        title = QtWidgets.QLabel("Debugowanie")
        title.setProperty("role", "Title")

        description = QtWidgets.QLabel(
            "Narzędzia przeznaczone do testowania i rozwijania aplikacji."
        )
        description.setWordWrap(True)

        self.debug_checkbox = QtWidgets.QCheckBox(
            "Włącz tryb debugowania"
        )
        self.debug_checkbox.setChecked(debug_config.is_enabled())
        self.debug_checkbox.toggled.connect(self.on_debug_toggled)

        info = QtWidgets.QLabel(
            "Po włączeniu w głównym oknie aplikacji pojawi się dodatkowy "
            "panel Debug."
        )
        info.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(8)
        layout.addWidget(self.debug_checkbox)
        layout.addWidget(info)
        layout.addStretch()

    def on_debug_toggled(self, checked):
        debug_config.set_enabled(checked)