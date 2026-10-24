import shutil
import subprocess
import time
import urllib.error
import urllib.request

from PySide6 import QtCore

from core import assistant_client


class AssistantWorker(QtCore.QThread):
    LEGACY_MODELS = ("qwen2.5:0.5b",)
    finished_ok = QtCore.Signal(bool, str)
    progress = QtCore.Signal(str)
    answer_chunk = QtCore.Signal(str)

    def __init__(self, operation, question="", parent=None):
        super().__init__(parent)
        self.operation = operation
        self.question = question

    def run(self):
        try:
            if self.operation == "setup":
                self._setup()
            else:
                answer = ""
                for chunk in assistant_client.ask_stream(self.question):
                    answer += chunk
                    self.answer_chunk.emit(chunk)
                self.finished_ok.emit(
                    True,
                    answer.strip() or "Model nie zwrócił odpowiedzi.",
                )
        except Exception as error:
            self.finished_ok.emit(False, self._friendly_error(error))

    def _setup(self):
        if shutil.which("ollama") is None:
            self.finished_ok.emit(False, "Ollama nie jest zainstalowana.")
            return

        self.progress.emit("Uruchamianie lokalnego silnika...")
        if not assistant_client.is_available():
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(20):
                if assistant_client.is_available():
                    break
                time.sleep(0.25)

        if not assistant_client.is_available():
            self.finished_ok.emit(False, "Nie udało się uruchomić Ollama.")
            return

        models = assistant_client.installed_models()
        if assistant_client.DEFAULT_MODEL in models:
            self._remove_legacy_models(models)
            self.finished_ok.emit(True, "Asystent jest gotowy.")
            return

        self.progress.emit(f"Pobieranie modelu {assistant_client.DEFAULT_MODEL}...")
        completed = subprocess.run(
            ["ollama", "pull", assistant_client.DEFAULT_MODEL],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(detail or "Nie udało się pobrać modelu.")
        self._remove_legacy_models(models)
        self.finished_ok.emit(True, "Asystent jest gotowy.")

    def _remove_legacy_models(self, installed_models):
        for model in self.LEGACY_MODELS:
            if model not in installed_models:
                continue
            self.progress.emit(f"Usuwanie starego modelu {model}...")
            subprocess.run(
                ["ollama", "rm", model],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

    @staticmethod
    def _friendly_error(error):
        if isinstance(error, urllib.error.URLError):
            return "Nie można połączyć się z lokalnym asystentem."
        return f"Nie udało się przygotować asystenta: {error}"
