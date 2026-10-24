import shutil
import webbrowser

from PySide6 import QtCore, QtGui, QtWidgets

from core import assistant_client
from GUI.Widgets.Workers.AssistantWorker import AssistantWorker


class AssistantTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("assistantTab")
        self._worker = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Asystent Audio Opus")
        title.setProperty("role", "Title")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Zapytaj, jak wykonać czynność w aplikacji. Asystent działa lokalnie."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        setup_group = QtWidgets.QGroupBox("Przygotowanie")
        setup_layout = QtWidgets.QHBoxLayout(setup_group)
        self.status_label = QtWidgets.QLabel("Sprawdzanie lokalnego modelu...")
        self.status_label.setObjectName("assistantStatus")
        setup_layout.addWidget(self.status_label, 1)
        self.setup_button = QtWidgets.QPushButton("Przygotuj asystenta")
        self.setup_button.clicked.connect(self.prepare_assistant)
        setup_layout.addWidget(self.setup_button)
        layout.addWidget(setup_group)

        self.answer_box = QtWidgets.QPlainTextEdit()
        self.answer_box.setReadOnly(True)
        self.answer_box.setPlaceholderText("Odpowiedź asystenta pojawi się tutaj...")
        layout.addWidget(self.answer_box, 1)

        question_layout = QtWidgets.QHBoxLayout()
        self.question_input = QtWidgets.QLineEdit()
        self.question_input.setPlaceholderText("Np. Jak zaimportować raport?")
        self.question_input.returnPressed.connect(self.ask_question)
        question_layout.addWidget(self.question_input, 1)
        self.ask_button = QtWidgets.QPushButton("Zapytaj")
        self.ask_button.clicked.connect(self.ask_question)
        question_layout.addWidget(self.ask_button)
        layout.addLayout(question_layout)

        self.progress_label = QtWidgets.QLabel()
        self.progress_label.setObjectName("assistantProgress")
        self.progress_label.hide()
        layout.addWidget(self.progress_label)

        self._set_ready_state(False)
        QtCore.QTimer.singleShot(0, self.check_status)

    def check_status(self):
        if not shutil.which("ollama"):
            self.status_label.setText("Ollama nie jest zainstalowana.")
            self.setup_button.setText("Zainstaluj Ollama")
            self._set_ready_state(False)
            return
        if assistant_client.is_available():
            self.status_label.setText("Ollama działa lokalnie. Kliknij przygotowanie modelu.")
        else:
            self.status_label.setText("Ollama jest zainstalowana, ale nie działa.")
        self._set_ready_state(False)

    def prepare_assistant(self):
        if not shutil.which("ollama"):
            webbrowser.open("https://ollama.com/download")
            self.status_label.setText("Otworzono oficjalną stronę instalacji Ollama.")
            return
        self._start_worker("setup")

    def ask_question(self):
        question = self.question_input.text().strip()
        if not question or self._worker is not None:
            return
        self.answer_box.setPlainText("Przygotowuję odpowiedź...")
        self._start_worker("ask", question)

    def _start_worker(self, operation, question=""):
        self._set_ready_state(False)
        self.progress_label.show()
        self.progress_label.setText("Pracuję...")
        self._worker = AssistantWorker(operation, question, self)
        self._worker.progress.connect(self.progress_label.setText)
        self._worker.answer_chunk.connect(self._append_answer_chunk)
        self._worker.finished_ok.connect(self._on_worker_finished)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _on_worker_finished(self, success, message):
        self.progress_label.hide()
        operation = self._worker.operation if self._worker is not None else None
        if success and operation == "ask":
            self.status_label.setText("Odpowiedź gotowa.")
            self.answer_box.setPlainText(message)
            self._set_ready_state(True)
        elif success:
            self.status_label.setText(message)
            self._set_ready_state(True)
        else:
            self.status_label.setText(message)
            self._set_ready_state(False)

    def _append_answer_chunk(self, chunk):
        if self.answer_box.toPlainText() == "Przygotowuję odpowiedź...":
            self.answer_box.clear()
        self.answer_box.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self.answer_box.insertPlainText(chunk)
        self.answer_box.ensureCursorVisible()

    def _clear_worker(self):
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            self.setup_button.setEnabled(True)

    def _set_ready_state(self, ready):
        self.ask_button.setEnabled(ready)
        self.question_input.setEnabled(ready)
        self.setup_button.setEnabled(self._worker is None)

    def closeEvent(self, event):
        is_running = getattr(self._worker, "isRunning", lambda: False)
        if self._worker is not None and is_running():
            self._worker.requestInterruption()
            self._worker.wait(1000)
        super().closeEvent(event)
