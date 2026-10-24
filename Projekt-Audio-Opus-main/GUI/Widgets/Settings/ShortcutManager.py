from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence


class ShortcutManager:

    def __init__(self, settings: QSettings = None):
        if settings is None:
            settings = QSettings()
        self.settings = settings
        self.defaults = {
            "add_client": "Ctrl+N",
            "add_product": "Ctrl+Shift+N",
            "search_focus": "Ctrl+F",
            "send_report": "Ctrl+E",
            "open_calculator": "Ctrl+K",
            "switch_clients": "Ctrl+1",
            "switch_products": "Ctrl+2",
            "switch_streaming": "Ctrl+3",
            "switch_reports": "Ctrl+4",
        }
        self.shortcuts = {}
        self.load()

    def load(self):
        self.settings.beginGroup("shortcuts")
        for action, default in self.defaults.items():
            seq_str = self.settings.value(action, default)
            self.shortcuts[action] = QKeySequence(seq_str)
        self.settings.endGroup()

    def save(self):
        self.settings.beginGroup("shortcuts")
        for action, seq in self.shortcuts.items():
            self.settings.setValue(action, seq.toString())
        self.settings.endGroup()
        self.settings.sync()

    def get_shortcut(self, action: str) -> QKeySequence:
        return self.shortcuts.get(action, QKeySequence())

    def set_shortcut(self, action: str, sequence: QKeySequence) -> tuple:
        for other_action, other_seq in self.shortcuts.items():
            if other_action != action and other_seq == sequence and not sequence.isEmpty():
                return False, f"Skrót {sequence.toString()} jest już używany przez {other_action}"
        self.shortcuts[action] = sequence
        return True, ""
