from PySide6 import QtCore, QtGui, QtWidgets


class SendConfirmationDialog(QtWidgets.QDialog):

  def __init__(
      self,
      recipients: list[str],
      attachment_name: str,
      subject: str,
      body: str,
      parent=None,
  ):
    super().__init__(parent)
    self.setWindowTitle("Potwierdzenie wysyłki")
    self.resize(450, 460)

    layout = QtWidgets.QVBoxLayout(self)

    layout.addWidget(QtWidgets.QLabel("<b>Odbiorcy:</b>"))
    recipients_list = QtWidgets.QListWidget()
    recipients_list.addItems(recipients)
    recipients_list.setFixedHeight(100)
    layout.addWidget(recipients_list)

    layout.addWidget(QtWidgets.QLabel(f"<b>Załącznik:</b> {attachment_name}"))

    layout.addWidget(QtWidgets.QLabel("<b>Temat:</b>"))
    self.subject_input = QtWidgets.QLineEdit(subject)
    layout.addWidget(self.subject_input)

    layout.addWidget(QtWidgets.QLabel("<b>Treść wiadomości:</b>"))
    self.body_preview = QtWidgets.QTextEdit()
    self.body_preview.setPlainText(body)
    layout.addWidget(self.body_preview)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
        | QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(
        "Wyślij"
    )
    buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText(
        "Anuluj"
    )
    buttons.accepted.connect(self.accept)
    buttons.rejected.connect(self.reject)
    layout.addWidget(buttons)

    self.enter_shortcut = QtGui.QShortcut(
        QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
        self,
    )
    self.enter_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
    self.enter_shortcut.activated.connect(self._handle_enter_pressed)

    self.numpad_enter_shortcut = QtGui.QShortcut(
        QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter),
        self,
    )
    self.numpad_enter_shortcut.setContext(
        QtCore.Qt.ShortcutContext.WindowShortcut
    )
    self.numpad_enter_shortcut.activated.connect(self._handle_enter_pressed)

  def _handle_enter_pressed(self):
    if not self.isVisible():
      return
    if self.body_preview.hasFocus():
      return
    self.accept()