from PySide6 import QtWidgets

from GUI.Widgets.Help.Base.HelpPage import HelpPage


class IntroductionHelp(HelpPage):
    def __init__(self):
        super().__init__(
            "Wprowadzenie",
            "Aplikacja służy do zarządzania klientami, produktami i platformami streamingowymi oraz przygotowywania rozliczeń."
        )

        self.add_section(
            "Jak rozpocząć pracę?",
            "Przed przygotowaniem pierwszego raportu upewnij się, że w aplikacji znajdują się potrzebni klienci, produkty oraz platformy."
        )

        self.add_step(1, "Dodaj produkty, które będą wykorzystywane podczas rozliczeń.")
        self.add_step(2, "Dodaj klienta i przypisz do niego odpowiednie produkty.")
        self.add_step(3, "Dodaj platformy streamingowe oraz ustaw ich prowizje.")
        self.add_step(4, "Przejdź do zakładki raportów.")
        self.add_step(5, "Wybierz klienta i wprowadź dane potrzebne do rozliczenia.")
        self.add_step(6, "Wygeneruj raport lub wyślij go bezpośrednio przez e-mail.")

        self.add_section(
            title="Rozmiar tabel",
            text="Aby zmienić rozmiar tabel wraz z rozmiarem ich czcionki należy przytrzymać przycisk <b>CTRL</b>, następnie przesuwać kółko myszy w góre lub dół."

        )

        self.add_section(
            "Klienci",
            "Zakładka „Klienci” pozwala dodawać i usuwać klientów oraz przypisywać do nich produkty."
        )

        self.add_section(
            "Produkty",
            "Zakładka „Produkty” służy do zarządzania produktami wykorzystywanymi podczas przygotowywania rozliczeń."
        )

        self.add_section(
            "Platformy streamingowe",
            "Zakładka platform streamingowych pozwala zarządzać platformami oraz ich prowizjami."
        )

        self.add_section(
            "Raporty",
            "Zakładka raportów umożliwia przygotowanie rozliczenia dla wybranego klienta i zapisanie go na komputerze."
        )

        self.add_section(
            "Raport e-mail",
            "Zakładka raportu e-mail umożliwia przygotowanie rozliczenia i wysłanie go na adres przypisany do klienta."
        )

        self.add_section(
            "Pomoc",
            "Przycisk „?” znajdujący się przy poszczególnych elementach aplikacji otwiera pomoc dotyczącą aktualnie używanej funkcji."
        )

        self.finish()