from PySide6 import QtCore, QtWidgets


class ZoomableScrollArea(QtWidgets.QScrollArea):
    zoom_requested = QtCore.Signal(int)

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta > 0:
                self.zoom_requested.emit(1)
            elif delta < 0:
                self.zoom_requested.emit(-1)

            event.accept()
            return

        super().wheelEvent(event)