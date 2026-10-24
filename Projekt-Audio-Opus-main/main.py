import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core import paths
from GUI.Window.MainWindow import MainWindow
from GUI.Window.StartupSplash import StartupSplash
from GUI.style.theme_manager import ThemeManager


APP_ICON = paths.resource_path("Assets", "Logo", "Stemp_apk.png")


if __name__ == '__main__':
    app = QApplication(sys.argv)

    app.setApplicationName("Audio Opus")
    app.setWindowIcon(QIcon(APP_ICON))

    try:
        ThemeManager.apply_theme(app)
    except Exception as e:
        print(f"Nie udało się wczytać stylu aplikacji: {e}")

    splash = StartupSplash(APP_ICON)
    splash.show()
    app.processEvents()

    window = MainWindow(defer_show=True)
    splash.finished.connect(window.showMaximized)
    splash.start()

    app.exec()