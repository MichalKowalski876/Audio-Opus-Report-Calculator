from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile

import rarfile

from PySide6 import QtWidgets, QtCore


class ArchivePreview(QtWidgets.QWidget):
    MAX_ARCHIVE_DEPTH = 10
    MAX_PREVIEW_FILE_SIZE = 100 * 1024 * 1024

    def __init__(self, filename, data, parent=None):
        super().__init__(parent)

        self.filename = filename
        self.root_data = data

        self.archive_stack = []
        self.current_archive = None
        self.current_path = ""

        self.create_ui()
        self.open_root_archive()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        navigation_layout = QtWidgets.QHBoxLayout()
        navigation_layout.setSpacing(8)

        self.back_button = QtWidgets.QPushButton()
        self.back_button.setFixedSize(40, 32)

        back_icon = self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_ArrowBack
        )

        self.back_button.setIcon(back_icon)
        self.back_button.setIconSize(
            QtCore.QSize(18, 18)
        )
        self.back_button.setToolTip("Wstecz")
        self.back_button.setEnabled(False)

        self.back_button.clicked.connect(
            self.go_back
        )

        self.path_label = QtWidgets.QLabel("/")
        self.path_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        navigation_layout.addWidget(
            self.back_button
        )
        navigation_layout.addWidget(
            self.path_label
        )
        navigation_layout.addStretch()

        self.file_list = QtWidgets.QListWidget()

        self.file_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )

        self.file_list.itemClicked.connect(
            self.open_item
        )

        layout.addLayout(
            navigation_layout
        )
        layout.addWidget(
            self.file_list,
            1
        )

    def open_root_archive(self):
        try:
            archive = self.create_archive(
                self.filename,
                self.root_data
            )

            self.current_archive = archive

            self.archive_stack = [
                {
                    "archive": archive,
                    "name": self.filename,
                    "path": ""
                }
            ]

            self.current_path = ""

            self.show_directory("")

        except Exception as error:
            self.show_error(
                f"Nie udało się otworzyć archiwum.\n\n{error}"
            )

    def create_archive(self, filename, data):
        filename = filename.lower()

        if filename.endswith(".zip"):
            return ZipFile(
                BytesIO(data)
            )

        if filename.endswith(".rar"):
            return rarfile.RarFile(
                BytesIO(data)
            )

        raise ValueError(
            "Nieobsługiwany format archiwum."
        )

    def show_directory(self, path):
        self.current_path = path

        self.update_navigation()

        self.file_list.clear()

        entries = self.get_directory_entries(
            path
        )

        for entry in entries:
            if entry["type"] == "folder":
                text = (
                    f"📁  {entry['name']}"
                )

            elif self.is_archive(entry["name"]):
                size = self.format_file_size(
                    entry["size"]
                )

                text = (
                    f"📦  {entry['name']}    "
                    f"({size})"
                )

            else:
                size = self.format_file_size(
                    entry["size"]
                )

                text = (
                    f"📄  {entry['name']}    "
                    f"({size})"
                )

            item = QtWidgets.QListWidgetItem(
                text
            )

            item.setData(
                QtCore.Qt.ItemDataRole.UserRole,
                entry
            )

            item.setSizeHint(
                QtCore.QSize(
                    0,
                    34
                )
            )

            self.file_list.addItem(
                item
            )

    def get_directory_entries(self, path):
        entries = {}

        prefix = path

        if prefix and not prefix.endswith("/"):
            prefix += "/"

        for info in self.current_archive.infolist():
            filename = info.filename

            if not filename.startswith(prefix):
                continue

            relative = filename[
                len(prefix):
            ]

            if not relative:
                continue

            parts = relative.split("/")

            name = parts[0]

            if not name:
                continue

            if len(parts) > 1:
                if name not in entries:
                    entries[name] = {
                        "name": name,
                        "path": prefix + name + "/",
                        "type": "folder",
                        "size": 0
                    }

                continue

            if info.is_dir():
                entries[name] = {
                    "name": name,
                    "path": filename,
                    "type": "folder",
                    "size": 0
                }

            else:
                entries[name] = {
                    "name": name,
                    "path": filename,
                    "type": "file",
                    "size": info.file_size
                }

        return sorted(
            entries.values(),
            key=lambda entry: (
                entry["type"] != "folder",
                entry["name"].lower()
            )
        )

    def open_item(self, item):
        entry = item.data(
            QtCore.Qt.ItemDataRole.UserRole
        )

        if not entry:
            return

        if entry["type"] == "folder":
            self.show_directory(
                entry["path"]
            )
            return

        if self.is_archive(entry["name"]):
            self.open_nested_archive(
                entry
            )
            return

        self.open_file(
            entry
        )

    def open_nested_archive(self, entry):
        if len(self.archive_stack) >= self.MAX_ARCHIVE_DEPTH:
            QtWidgets.QMessageBox.warning(
                self,
                "Zbyt wiele archiwów",
                f"Podgląd obsługuje maksymalnie "
                f"{self.MAX_ARCHIVE_DEPTH} poziomów zagnieżdżonych archiwów."
            )
            return

        if entry["size"] > self.MAX_PREVIEW_FILE_SIZE:
            QtWidgets.QMessageBox.warning(
                self,
                "Archiwum jest zbyt duże",
                "To archiwum jest zbyt duże, aby otworzyć je bezpośrednio w podglądzie."
            )
            return

        try:
            data = self.current_archive.read(
                entry["path"]
            )

            archive = self.create_archive(
                entry["name"],
                data
            )

        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd archiwum",
                f"Nie udało się otworzyć archiwum.\n\n{error}"
            )
            return

        self.archive_stack.append(
            {
                "archive": archive,
                "name": entry["name"],
                "path": self.current_path
            }
        )

        self.current_archive = archive
        self.current_path = ""

        self.show_directory("")

    def open_file(self, entry):
        if entry["size"] > self.MAX_PREVIEW_FILE_SIZE:
            size = self.format_file_size(
                entry["size"]
            )

            QtWidgets.QMessageBox.warning(
                self,
                "Plik jest zbyt duży",
                f"Ten plik ma {size}.\n\n"
                "Jest zbyt duży, aby otworzyć go bezpośrednio w podglądzie."
            )
            return

        try:
            data = self.current_archive.read(
                entry["path"]
            )

        except rarfile.PasswordRequired:
            QtWidgets.QMessageBox.warning(
                self,
                "Archiwum zabezpieczone",
                "Ten plik jest zabezpieczony hasłem i nie można wyświetlić jego podglądu."
            )
            return

        except rarfile.RarCannotExec:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak obsługi tego pliku RAR",
                "Zawartość archiwum została odczytana, ale tego pliku nie można rozpakować.\n\n"
                "Brakuje odpowiedniego narzędzia do dekompresji RAR."
            )
            return

        except rarfile.Error as error:
            QtWidgets.QMessageBox.warning(
                self,
                "Nieobsługiwany plik RAR",
                "Nie udało się odczytać tego pliku z archiwum RAR.\n\n"
                f"{error}"
            )
            return

        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd",
                f"Nie udało się odczytać pliku.\n\n{error}"
            )
            return

        from Integrations.Gmail.AttachmentPreview.AttachmentPreviewWindow import (
            AttachmentPreviewWindow
        )

        window = AttachmentPreviewWindow(
            filename=entry["name"],
            data=data,
            parent=self
        )

        window.exec()

    def go_back(self):
        if self.current_path:
            path = self.current_path.rstrip("/")

            parent = str(
                PurePosixPath(path).parent
            )

            if parent == ".":
                parent = ""
            else:
                parent += "/"

            self.show_directory(
                parent
            )
            return

        if len(self.archive_stack) <= 1:
            return

        current = self.archive_stack.pop()

        current["archive"].close()

        previous = self.archive_stack[-1]

        self.current_archive = previous["archive"]

        self.show_directory(
            current["path"]
        )

    def update_navigation(self):
        self.back_button.setEnabled(
            bool(self.current_path)
            or len(self.archive_stack) > 1
        )

        parts = []

        for archive_info in self.archive_stack[1:]:
            parts.append(
                archive_info["name"]
            )

        if self.current_path:
            parts.extend(
                part
                for part in self.current_path.split("/")
                if part
            )

        if parts:
            self.path_label.setText(
                "/" + "/".join(parts) + "/"
            )
        else:
            self.path_label.setText("/")

    def is_archive(self, filename):
        filename = filename.lower()

        return filename.endswith(
            (
                ".zip",
                ".rar"
            )
        )

    def show_error(self, text):
        self.file_list.clear()

        item = QtWidgets.QListWidgetItem(
            text
        )

        item.setFlags(
            QtCore.Qt.ItemFlag.NoItemFlags
        )

        self.file_list.addItem(
            item
        )

    def format_file_size(self, size):
        if size < 1024:
            return f"{size} B"

        if size < 1024 * 1024:
            return (
                f"{size / 1024:.1f} KB"
            )

        if size < 1024 * 1024 * 1024:
            return (
                f"{size / (1024 * 1024):.1f} MB"
            )

        return (
            f"{size / (1024 * 1024 * 1024):.1f} GB"
        )

    def closeEvent(self, event):
        for archive_info in reversed(
            self.archive_stack
        ):
            try:
                archive_info["archive"].close()
            except Exception:
                pass

        self.archive_stack.clear()

        super().closeEvent(event)