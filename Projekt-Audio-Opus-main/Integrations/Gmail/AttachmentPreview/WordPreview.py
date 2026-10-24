from io import BytesIO

from PySide6 import QtWidgets, QtGui
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


class WordPreview(QtWidgets.QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)

        self.data = data
        self.create_ui()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            document = Document(BytesIO(self.data))

            text_edit = QtWidgets.QTextEdit()
            text_edit.setReadOnly(True)

            cursor = text_edit.textCursor()

            for element in document.iter_inner_content():
                if isinstance(element, Paragraph):
                    self.insert_paragraph(cursor, element)

                elif isinstance(element, Table):
                    self.insert_table(cursor, element)

            layout.addWidget(text_edit)

        except Exception as error:
            error_label = QtWidgets.QLabel(
                "Nie udało się wyświetlić pliku Word.\n\n"
                f"{error}"
            )

            error_label.setWordWrap(True)
            layout.addWidget(error_label)

    def insert_paragraph(self, cursor, paragraph):
        block_format = QtGui.QTextBlockFormat()
        char_format = QtGui.QTextCharFormat()

        style_name = ""

        if paragraph.style:
            style_name = paragraph.style.name.lower()

        # Nagłówki
        if style_name.startswith("heading"):
            try:
                level = int(
                    style_name.replace("heading", "").strip()
                )
            except ValueError:
                level = 1

            sizes = {
                1: 22,
                2: 18,
                3: 16,
                4: 14,
            }

            char_format.setFontPointSize(
                sizes.get(level, 13)
            )

            char_format.setFontWeight(
                QtGui.QFont.Weight.Bold
            )

            block_format.setTopMargin(12)
            block_format.setBottomMargin(6)

        # Listy
        is_list = (
            "list" in style_name
            or "bullet" in style_name
        )

        if is_list:
            block_format.setLeftMargin(20)

        cursor.insertBlock(block_format)

        if is_list:
            cursor.insertText("• ")

        # Poszczególne fragmenty tekstu
        for run in paragraph.runs:
            run_format = QtGui.QTextCharFormat(char_format)

            if run.bold:
                run_format.setFontWeight(
                    QtGui.QFont.Weight.Bold
                )

            if run.italic:
                run_format.setFontItalic(True)

            if run.underline:
                run_format.setFontUnderline(True)

            cursor.insertText(
                run.text,
                run_format
            )

    def insert_table(self, cursor, table):
        rows = len(table.rows)

        if rows == 0:
            return

        columns = len(table.columns)

        if columns == 0:
            return

        cursor.insertBlock()

        text_table = cursor.insertTable(
            rows,
            columns
        )

        table_format = text_table.format()
        table_format.setBorder(1)
        table_format.setCellPadding(5)
        table_format.setCellSpacing(0)

        text_table.setFormat(table_format)

        for row_index, row in enumerate(table.rows):
            for column_index, cell in enumerate(row.cells):
                text_cell = text_table.cellAt(
                    row_index,
                    column_index
                )

                cell_cursor = text_cell.firstCursorPosition()

                for paragraph_index, paragraph in enumerate(cell.paragraphs):
                    if paragraph_index > 0:
                        cell_cursor.insertBlock()

                    for run in paragraph.runs:
                        run_format = QtGui.QTextCharFormat()

                        if run.bold:
                            run_format.setFontWeight(
                                QtGui.QFont.Weight.Bold
                            )

                        if run.italic:
                            run_format.setFontItalic(True)

                        if run.underline:
                            run_format.setFontUnderline(True)

                        cell_cursor.insertText(
                            run.text,
                            run_format
                        )

        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.End
        )

        cursor.insertBlock()