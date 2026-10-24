from PySide6 import QtWidgets

from GUI.Widgets.Help.Base.HelpPage import HelpPage


class ReportHelp(HelpPage):
    def __init__(self):
        super().__init__(
            "Raport",
            "Generowanie raportów na podstawie danych zapisanych w aplikacji."
        )

        self.add_section(
            "Generowanie raportu",
            "Aby wygenerować raport:"
        )

        self.add_step(1, "Przejdź do zakładki raportów.")
        self.add_step(2, "Wybierz klienta, dla którego chcesz przygotować raport.")
        self.add_step(3, "Wprowadź dane dotyczące sprzedaży produktów.")
        self.add_step(4, "Sprawdź poprawność wprowadzonych danych.")
        self.add_step(5, "Wybierz miejsce, w którym raport ma zostać zapisany.")
        self.add_step(6, "Kliknij przycisk generowania raportu.")

        self.add_section(
            "Zapis raportu",
            "Wygenerowany raport zostanie zapisany w wybranym wcześniej folderze."
        )

        self.finish()