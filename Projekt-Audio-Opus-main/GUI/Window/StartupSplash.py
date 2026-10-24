from PySide6 import QtCore, QtGui, QtWidgets

from GUI.style import branding


class StartupSplash(QtWidgets.QWidget):
    finished = QtCore.Signal()

    def __init__(self, logo_path, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 310)

        panel = QtWidgets.QFrame()
        panel.setObjectName("splashPanel")
        panel.setStyleSheet(
            """
            QFrame#splashPanel {
                background: #ffffff;
                border: 1px solid #dedede;
                border-radius: 16px;
            }
            QLabel#splashTitle {
                color: #202020;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#splashStatus {
                color: #707070;
                font-size: 13px;
            }
            QProgressBar {
                border: none;
                background: #eeeeee;
                border-radius: 3px;
                min-height: 6px;
                max-height: 6px;
            }
            QProgressBar::chunk {
                background: #ff8c42;
                border-radius: 3px;
            }
            """
        )

        screen = QtGui.QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen is not None else 1.0

        logo = QtWidgets.QLabel()
        logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(branding.logo_pixmap(72, dpr))

        title = QtWidgets.QLabel("Audio Opus")
        title.setObjectName("splashTitle")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.status_label = QtWidgets.QLabel("Uruchamianie aplikacji")
        self.status_label.setObjectName("splashStatus")
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(28, 22, 28, 24)
        layout.setSpacing(8)
        layout.addWidget(logo, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addSpacing(8)
        layout.addWidget(self.progress_bar)

        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(panel)

        self._progress_timer = QtCore.QTimer(self)
        self._progress_timer.timeout.connect(self._advance_progress)
        self._progress_value = 0
        self._status_messages = (
            "Uruchamianie aplikacji",
            "Wczytywanie paneli",
            "Przygotowywanie widoku",
        )
        self._status_index = 0

        logo_effect = QtWidgets.QGraphicsOpacityEffect(logo)
        logo_effect.setOpacity(1.0)
        logo.setGraphicsEffect(logo_effect)
        self._logo_pulse = QtCore.QPropertyAnimation(logo_effect, b"opacity", self)
        self._logo_pulse.setDuration(720)
        self._logo_pulse.setStartValue(0.72)
        self._logo_pulse.setEndValue(1.0)
        self._logo_pulse.setLoopCount(-1)
        self._logo_pulse.setEasingCurve(QtCore.QEasingCurve.Type.InOutSine)

        self._fade_animation = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setDuration(320)
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.finished.connect(self._emit_finished)

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen() or QtGui.QGuiApplication.primaryScreen()
        if screen is not None:
            self.move(screen.availableGeometry().center() - self.rect().center())

    def start(self):
        self.setWindowOpacity(1.0)
        self._progress_value = 0
        self._status_index = 0
        self.status_label.setText(self._status_messages[0])
        self.progress_bar.setValue(0)
        self._progress_timer.start(20)
        self._logo_pulse.start()
        QtCore.QTimer.singleShot(1050, self.finish)

    def _advance_progress(self):
        self._progress_value = min(self._progress_value + 2, 100)
        self.progress_bar.setValue(self._progress_value)
        if self._progress_value in (34, 68):
            self._status_index += 1
            self.status_label.setText(self._status_messages[self._status_index])

    def finish(self):
        self._progress_timer.stop()
        self._logo_pulse.stop()
        self.progress_bar.setValue(100)
        self.status_label.setText("Gotowe")
        self._fade_animation.start()

    def _emit_finished(self):
        self.finished.emit()
        self.close()