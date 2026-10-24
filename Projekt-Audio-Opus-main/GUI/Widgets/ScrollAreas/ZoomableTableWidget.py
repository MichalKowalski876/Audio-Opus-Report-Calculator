from PySide6 import QtCore, QtGui, QtWidgets


class ZoomableTableWidget(QtWidgets.QTableWidget):
    """QTableWidget z obsługą przybliżania/oddalania za pomocą Ctrl + scroll."""

    MIN_ZOOM = 0.6
    MAX_ZOOM = 2.0
    ZOOM_STEP = 0.1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_font_size = self.font().pointSize()
        if self._base_font_size <= 0:
            self._base_font_size = 13
        self._zoom_factor = 1.0

    def wheelEvent(self, event: QtGui.QWheelEvent):
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta == 0:
                # Niektóre gładziki (np. na macOS) nie wysyłają
                # angleDelta, tylko pixelDelta.
                delta = event.pixelDelta().y()

            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()

            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
            and event.key() == QtCore.Qt.Key.Key_0
        ):
            self.reset_zoom()
            event.accept()
            return
        super().keyPressEvent(event)

    def zoom_in(self):
        self.set_zoom(self._zoom_factor + self.ZOOM_STEP)

    def zoom_out(self):
        self.set_zoom(self._zoom_factor - self.ZOOM_STEP)

    def reset_zoom(self):
        self.set_zoom(1.0)

    def set_zoom(self, zoom_factor: float):
        zoom_factor = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom_factor))
        if zoom_factor == self._zoom_factor:
            return
        self._zoom_factor = zoom_factor
        self._apply_zoom()

    def _apply_zoom(self):
        new_size = max(6, round(self._base_font_size * self._zoom_factor))
        self.setStyleSheet(
            f"""
            QTableWidget {{
                font-size: {new_size}px;
            }}
            QHeaderView::section {{
                font-size: {new_size}px;
            }}
            """
        )
        self.resizeRowsToContents()