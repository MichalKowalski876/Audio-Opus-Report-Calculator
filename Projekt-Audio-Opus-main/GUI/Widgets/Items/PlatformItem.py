from PySide6 import QtCore, QtWidgets


class PlatformItem(QtWidgets.QFrame):
    def __init__(self, platform: dict):
        super().__init__()

        self.platform = platform

        self.setProperty("role", "PlatformItem")
        self.setMinimumHeight(64)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        platform_name = str(
            platform.get("name") or "Bez nazwy"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)

        name = QtWidgets.QLabel(platform_name)
        name.setProperty("role", "PlatformName")
        name.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        name.setToolTip(
            f"<b>{platform_name}</b><br><br>"
            "Platforma streamingowa obsługiwana przez aplikację."
        )

        layout.addWidget(name)